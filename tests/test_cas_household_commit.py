"""Whole-household decisions must stay bound to fresh independent receivers."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_household_commit as tool
from source_manifest import sha256


class HouseholdCommitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.identity = {'pid': 123, 'test_token': 'token', 'script_sha256': 'c' * 64}
        self.rows = [{'sim_id': sid, 'form_checkpoint': {'ok': True,
                     'expected_pending_sha256': pin * 64}} for sid, pin in [('100', 'a'), ('200', 'b')]]
        self.entry = dict(operation='observe-native-cas-entry', entry_accepted=True, entry_submitted=True,
                          identity=self.identity, steps=[{'action': 'test_cas', 'result': {'ok': True,
                          'household_form_checkpoints': {'ok': True, 'household_id': '55',
                             'roster_sim_ids': ['100', '200'], 'members': self.rows}}}])
        self.entry_path = self.root / 'entry.json'; self.entry_path.write_text(json.dumps(self.entry))
        self.args = Obj(state=self.root / 'state.json', entry_proof=self.entry_path,
                        entry_sha256=sha256(self.entry_path), accept=['100:2'],
                        output=self.root / 'out.json', seconds=10)
        self.calls = []; self.observations = 0
        self.journal = {'token': 'token', 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'c' * 64}]}

    def request(self, state, action, sim_id, value, seconds, submission_observer):
        rid = format(len(self.calls) + 1, '032x')
        submission_observer(action, rid)
        # Exact UUID must exist on disk before the mock native operation.
        self.assertEqual(json.loads(self.args.output.read_text())['steps'][-1]['request_id'], rid)
        value = None if value is None else json.loads(value)
        self.calls.append((sim_id, action, value))
        result = {'ok': True, 'request_id': rid}
        pending = 'a' * 64 if sim_id == '100' else 'b' * 64
        if action == 'test_snapshot':
            result.update(clock_speed=0, persistence={'household_sim_ids': ['100', '200']})
        elif action == 'cas_bank_status':
            result.update(current_runtime=True, phase='captured', expected_pending_sha256=pending,
                          native_write_possible=False, native_write_attempted=False, metadata_commit_persisted=False,
                          completed_receipt=True, native_availability_restore_verified=True)
        elif action == 'cas_bank_observe':
            self.observations += 1
            result.update(lane_change_evidence_available=True, changed_lanes=['1', '2'], raw_return_sha256='d' * 64)
        elif action == 'cas_bank_prepare':
            self.assertEqual(self.observations, 2)
            result['plan_sha256'] = 'e' * 64
        return result

    def run_tool(self, request=None):
        with patch.object(tool.reusable_profile, 'load', return_value=(self.args.state, self.journal,
                self.root / 'profile', self.root / 'original')), \
                patch.object(tool.cas_return, 'live_snapshot', return_value=True):
            return tool.run(self.args, self.identity, request or self.request)

    def test_every_member_observed_first_and_only_named_owner_keeps_edits(self):
        result = self.run_tool()
        self.assertTrue(result['ok'])
        plans = {sid: value for sid, action, value in self.calls if action == 'cas_bank_prepare'}
        self.assertEqual(plans['100']['dispositions'], [dict(lane='1', action='restore-original'),
                                                       dict(lane='2', action='accept-returned')])
        self.assertEqual(plans['200']['dispositions'], [dict(lane='1', action='restore-original'),
                                                       dict(lane='2', action='restore-original')])
        self.assertEqual(sum(action == 'cas_bank_commit' for sid, action, value in self.calls), 2)

    def test_failed_second_observation_prevents_every_plan_and_native_commit(self):
        def fail(*args, **kwargs):
            result = self.request(*args, **kwargs)
            if kwargs['action'] == 'cas_bank_observe' and kwargs['sim_id'] == '200':
                result['ok'] = False
            return result
        def invoke(state, action, **kwargs): return fail(state, action=action, **kwargs)
        result = self.run_tool(invoke)
        self.assertFalse(result['ok'])
        self.assertFalse(any(action in ('cas_bank_prepare', 'cas_bank_commit') for sid, action, value in self.calls))

    def test_old_runtime_entry_cannot_write_or_observe(self):
        self.identity = dict(self.identity, pid=999)
        with self.assertRaisesRegex(ValueError, 'runtime'):
            self.run_tool()
        self.assertEqual(self.calls, [])

    def test_advancing_core_ticks_and_queue_counts_do_not_change_runtime_identity(self):
        self.identity = dict(self.identity, core_ticks=5000, queue={'retained': 99})
        self.assertTrue(self.run_tool()['ok'])

    def test_semantic_return_observation_is_reused_without_replaying_selected_member(self):
        self.observations = 1  # One receiver already observed by CAS return.
        def invoke(state, action, **kwargs):
            result = self.request(state, action, **kwargs)
            if action == 'cas_bank_status' and kwargs['sim_id'] == '100':
                result.update(phase='observed', lane_change_evidence_available=True,
                              changed_lanes=['1', '2'], raw_return_sha256='d' * 64)
            return result
        result = self.run_tool(invoke)
        self.assertTrue(result['ok'])
        self.assertEqual([(sid, action) for sid, action, value in self.calls if action == 'cas_bank_observe'],
                         [('200', 'cas_bank_observe')])

    def test_foreign_or_duplicate_sim_form_intent_is_rejected(self):
        for values in (['999:2'], ['100:3'], ['100:2', '100:2']):
            with self.subTest(values=values), self.assertRaises(ValueError):
                tool.accepts(values, {'100': {}})

    def test_selected_only_legacy_entry_cannot_claim_household_protection(self):
        self.entry['steps'][0]['result'].pop('household_form_checkpoints')
        with self.assertRaisesRegex(ValueError, 'independent'):
            tool.entry_receipt(self.entry)

    def test_entry_packet_larger_than_intent_limit_remains_exact_and_bounded(self):
        self.entry['audit_padding'] = 'x' * 200000
        self.entry_path.write_text(json.dumps(self.entry))
        result = tool.read_entry(self.entry_path, sha256(self.entry_path), self.root / 'profile', self.root / 'original')
        self.assertEqual(result, self.entry)
        with self.assertRaisesRegex(ValueError, 'differs'):
            tool.read_entry(self.entry_path, '0' * 64, self.root / 'profile', self.root / 'original')


if __name__ == '__main__': unittest.main()
