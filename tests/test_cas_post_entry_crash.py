import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_crash
from cas_return import live_snapshot
from test_game_discard import live


class PostEntryCrashTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.profile = self.root / 'profile'; self.original = self.root / 'protected'
        self.profile.mkdir(); self.original.mkdir()
        self.identity = dict(pid=8, test_token='b' * 32, script_sha256='c' * 64, profile=str(self.profile))
        self.entry = dict(schema=1, operation='observe-native-cas-entry', ok=True, outcome='inventory',
            entry_submitted=True, entry_accepted=True, handshake_verified=True, inventory_verified=True,
            no_input_replay=True, requested_sim_id='11', identity=copy.deepcopy(self.identity),
            crash_before={'state': 'absent'}, steps=[{'action': 'test_cas', 'result':
                {'ok': True, 'before': dict(live(), sim={'id': '11', 'instanced': True}, save_slot=2, clock_speed=0)}}])
        self.entry_path = self.root / 'entry.json'
        self.crash_path = self.root / 'crash.xml'; self.crash_path.write_bytes(b'<report><type>crash</type></report>')
        self.proof = dict(schema=1, operation='observe-native-cas-post-entry-crash', ok=False,
            outcome='native-crash', process_absent_observed=True, identity=copy.deepcopy(self.identity),
            entry_proof=str(self.entry_path), crash={'outcome': 'preserved', 'preserved': True,
                'before': {'state': 'absent'}, 'after': {'sha256': hashlib.sha256(self.crash_path.read_bytes()).hexdigest()},
                'path': str(self.crash_path)})
        self.save_entry()

    def save_entry(self):
        self.entry_path.write_text(json.dumps(self.entry), encoding='utf-8')
        self.proof['entry_proof_sha256'] = hashlib.sha256(self.entry_path.read_bytes()).hexdigest()

    def validate(self):
        return cas_crash.validate(self.proof, self.identity, '11', '22', '33', 2, self.profile, self.original)

    def test_later_crash_keeps_successful_inventory_as_a_separate_immutable_leaf(self):
        initial = self.entry_path.read_bytes(); crash = self.crash_path.read_bytes()
        self.assertEqual(self.validate()['sim']['id'], '11')
        self.assertEqual(self.entry_path.read_bytes(), initial)
        self.assertEqual(self.crash_path.read_bytes(), crash)
        self.assertTrue(self.entry['inventory_verified'])

    def test_historical_game_clock_origin_is_retained_for_diagnosis_but_cannot_prove_fresh_simulation_progress(self):
        before = self.entry['steps'][0]['result']['before']
        before['sim_time_source'] = 'services.game_clock_service().now()'
        before['future_native_field'] = {'untouched': 'exact historical data'}
        self.save_entry()
        immutable = self.entry_path.read_bytes()
        preserved = self.validate()
        self.assertEqual(preserved, before)
        self.assertFalse(live_snapshot(preserved, '11', '22'))
        self.assertEqual(self.entry_path.read_bytes(), immutable)
        self.assertNotIn('clock_progress_verified', self.proof)

    def test_changed_entry_bytes_refused(self):
        self.entry_path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'): self.validate()

    def deferred_entry(self):
        receipt = copy.deepcopy(self.entry['steps'][0]['result'])
        request_id = 'a' * 32
        self.entry['entry_request_id'] = request_id
        self.entry['steps'] = [
            {'action': 'test_cas', 'result': dict(ok=False, outcome='unresolved', request_id=request_id)},
            {'action': 'test_cas_status', 'result': dict(ok=True, state='running', request_id=request_id, result=None)},
            {'action': 'test_cas_status', 'result': dict(ok=True, state='completed', request_id=request_id, result=receipt)},
            {'action': 'test_cas_completion', 'result': dict(receipt, request_id=request_id, request_state='completed')}]
        self.save_entry()

    def test_exact_deferred_original_completion_retains_native_crash_without_replaying_entry(self):
        self.deferred_entry()
        immutable = self.entry_path.read_bytes()
        self.assertEqual(self.validate()['sim']['id'], '11')
        self.assertEqual(self.entry_path.read_bytes(), immutable)

    def test_deferred_result_mismatch_wrong_uuid_duplicate_and_unknown_terminal_refused(self):
        self.deferred_entry()
        good = copy.deepcopy(self.entry)
        mutations = [
            lambda p: p['steps'][2]['result'].update(request_id='f' * 32),
            lambda p: p['steps'][3]['result'].update(request_id='f' * 32),
            lambda p: p['steps'][3]['result']['before'].update(save_slot=3),
            lambda p: p['steps'][2]['result'].update(state='running'),
            lambda p: p['steps'].append(copy.deepcopy(p['steps'][2])),
            lambda p: p['steps'].append(copy.deepcopy(p['steps'][3])),
            lambda p: p['steps'][2]['result'].update(result=None),
            lambda p: p['steps'][0]['result'].update(outcome='failed'),
            lambda p: p['steps'][2]['result'].update(extra=True)]
        for mutate in mutations:
            self.entry = copy.deepcopy(good); mutate(self.entry); self.save_entry()
            with self.subTest(mutation=mutate), self.assertRaises(ValueError): self.validate()

    def test_other_runtime_or_other_sim_refused_even_with_rehashed_entry(self):
        for field, value in [('pid', 9), ('test_token', 'd' * 32), ('script_sha256', 'e' * 64)]:
            self.entry['identity'] = dict(self.identity, **{field: value}); self.save_entry()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'exact completed'): self.validate()
        self.entry['identity'] = self.identity; self.entry['requested_sim_id'] = '44'; self.save_entry()
        with self.assertRaisesRegex(ValueError, 'exact completed'): self.validate()

    def test_failed_or_unknown_entry_does_not_become_post_inventory_crash(self):
        for field in ('ok', 'entry_accepted', 'handshake_verified', 'inventory_verified', 'no_input_replay'):
            self.entry[field] = False; self.save_entry()
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate()
            self.entry[field] = True

    def test_duplicate_native_entry_is_refused(self):
        self.entry['steps'].append(copy.deepcopy(self.entry['steps'][0])); self.save_entry()
        with self.assertRaisesRegex(ValueError, 'exactly once'): self.validate()

    def test_other_slot_household_guid_and_running_clock_refused(self):
        before = self.entry['steps'][0]['result']['before']
        for field, value in [('save_slot', 3), ('household_id', '55'), ('save_guid', '66'), ('clock_speed', 1)]:
            old = before[field]; before[field] = value; self.save_entry()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'paused native'): self.validate()
            before[field] = old

    def test_unchanged_or_tampered_crash_is_refused(self):
        self.proof['crash']['before'] = self.proof['crash']['after']
        with self.assertRaises(ValueError): self.validate()
        self.proof['crash']['before'] = {'state': 'absent'}; self.crash_path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'): self.validate()

    def test_profile_and_protected_original_are_not_valid_evidence_destinations(self):
        for root in (self.profile, self.original):
            relocated = root / 'crash.xml'; relocated.write_bytes(self.crash_path.read_bytes())
            self.proof['crash']['path'] = str(relocated)
            with self.subTest(root=root), self.assertRaisesRegex(ValueError, 'unsafe'): self.validate()

    def test_unknown_prior_process_state_is_refused(self):
        self.proof['process_absent_observed'] = None
        with self.assertRaises(ValueError): self.validate()
