"""F11 review model dispatch retains UUIDs; a queued mutation is never replayed."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_review_cli
import test_cas_client_intent as fixture


class CasReviewCliTests(unittest.TestCase):
    # Reuse only the isolated filesystem/identity fixture, not its CAS transport.
    def setUp(self):
        fixture.CasClientIntentTests.setUp(self)
        self.load.return_value = (self.state, {'token': 'a' * 32}, self.profile, self.original)
        self.args = Obj(operation='status', state=self.state, output=self.root / 'review.json',
                        view_proof=None, view_sha256=None, values=None, values_sha256=None, seconds=1)
        self.intent = self.args.output.with_suffix('.intent.json')
        self.enterContext(patch.object(cas_review_cli, 'session', side_effect=lambda _state: self.noop()))
        self.sent = []

    @staticmethod
    def noop():
        from contextlib import nullcontext
        return nullcontext()

    def file(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def preceding(self):
        self.args.view_proof, self.args.view_sha256 = self.file('preceding.json',
            {'ok': True, 'operation': 'cas-review', 'view': {'sim_id': '12', 'generation': 2, 'busy': False}})

    def request(self, state, action, **kwargs):
        rid = '{:032x}'.format(len(self.sent) + 1)
        kwargs['submission_observer'](action, rid)
        retained = json.loads(self.intent.read_text(encoding='utf-8'))
        self.assertEqual(retained['owner_requests'][-1]['request_id'], rid)
        argument = json.loads(kwargs['value'])['value'] if 'value' in kwargs else None
        self.sent.append((action, argument))
        if action == 'list_sims':
            return {'ok': True, 'request_id': rid, 'request_state': 'completed', 'sims': [{'id': '12'}]}
        return {'ok': True, 'request_id': rid, 'request_state': 'completed', 'operation': 'cas-review',
                'view': {'sim_id': '12', 'generation': 2, 'busy': False, 'unresolved': False, 'failed': False}}

    def test_status_uses_only_native_read_and_publishes_durable_owner_identity(self):
        result = cas_review_cli.execute(self.args, self.request)
        self.assertTrue(result['ok'])
        self.assertEqual(self.sent, [('test_preview', {'operation': 'cas-review', 'action': 'status'})])
        self.assertFalse(result['physical_imgui_click_proven'])

    def test_select_uses_fresh_source_roster_and_exact_previous_model(self):
        self.args.operation = 'select'; self.preceding()
        self.args.values, self.args.values_sha256 = self.file('choice.json', {'sim_id': '12'})
        self.assertTrue(cas_review_cli.execute(self.args, self.request)['ok'])
        self.assertEqual([action for action, _ in self.sent], ['list_sims', 'test_preview'])
        self.assertEqual(self.sent[1][1]['expected']['generation'], 2)
        self.assertEqual(self.sent[1][1]['roster']['sims'], [{'id': '12'}])

    def test_changed_previous_proof_refuses_before_any_transport(self):
        self.args.operation = 'commit'; self.preceding()
        self.args.view_proof.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            cas_review_cli.execute(self.args, self.request)
        self.assertEqual(self.sent, [])

    def test_foreign_fields_in_hair_intent_refuse_before_transport(self):
        self.args.operation = 'hair-none'; self.preceding()
        self.args.values, self.args.values_sha256 = self.file('choice.json', {'lane': '2', 'appearance': 'forged'})
        with self.assertRaisesRegex(ValueError, 'exact named'):
            cas_review_cli.execute(self.args, self.request)
        self.assertEqual(self.sent, [])

    def test_commit_is_submitted_once_and_only_readonly_status_is_polled(self):
        self.args.operation = 'commit'; self.preceding()
        def transport(*args, **kwargs):
            result = self.request(*args, **kwargs)
            result['view']['busy'] = len(self.sent) < 3
            return result
        result = cas_review_cli.execute(self.args, transport, pause=lambda _: None)
        self.assertTrue(result['ok'])
        self.assertEqual([value['action'] for _, value in self.sent], ['commit', 'status', 'status'])
        self.assertTrue(result['appearance_mutation_queued'])

    def test_lost_commit_keeps_original_uuid_and_does_not_poll_or_resubmit_mutation(self):
        self.args.operation = 'commit'; self.preceding()
        def lost(*args, **kwargs):
            self.request(*args, **kwargs)
            raise OSError('lost after dispatch')
        with self.assertRaises(OSError):
            cas_review_cli.execute(self.args, lost)
        self.assertEqual(len(self.sent), 1)
        retained = json.loads(self.intent.read_text(encoding='utf-8'))
        self.assertEqual(retained['owner_requests'][0]['request_id'], '0' * 31 + '1')
        self.assertFalse(retained['automatic_replay_allowed'])

    def test_existing_output_does_not_dispatch(self):
        self.args.output.write_bytes(b'previous evidence')
        with self.assertRaises(ValueError):
            cas_review_cli.execute(self.args, self.request)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.args.output.read_bytes(), b'previous evidence')

    def test_source_terminal_failure_is_retained_without_replaying_commit(self):
        self.args.operation = 'commit'; self.preceding()
        def failure(*args, **kwargs):
            result = self.request(*args, **kwargs)
            result['view']['failed'] = True
            return result
        result = cas_review_cli.execute(self.args, failure)
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.sent), 1)

    def test_readonly_status_can_inspect_a_failed_model_without_claiming_its_mutation_succeeded(self):
        def failed_model(*args, **kwargs):
            result = self.request(*args, **kwargs)
            result['view']['failed'] = True
            return result
        result = cas_review_cli.execute(self.args, failed_model)
        self.assertTrue(result['ok'])
        self.assertTrue(result['source_model_failed'])
        self.assertFalse(result['appearance_mutation_queued'])
        self.assertEqual(len(self.sent), 1)

    def test_native_integer_roster_ids_are_losslessly_encoded_without_changing_source_receipt(self):
        original = {'ok': True, 'sims': [{'id': (1 << 64)-1}, {'id': 12}]}
        converted = cas_review_cli.native_roster(original)
        self.assertEqual(converted['sims'][0]['id'], '18446744073709551615')
        self.assertEqual(converted['sims'][1]['id'], '12')
        self.assertIsInstance(original['sims'][0]['id'], int)
        for invalid in (True, 1.2, 0, -1, 1 << 64, '012'):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                cas_review_cli.native_roster({'ok': True, 'sims': [{'id': invalid}]})
        with self.assertRaises(ValueError):
            cas_review_cli.native_roster({'ok': True, 'sims': [{'id': 12}, {'id': '12'}]})


if __name__ == '__main__':
    unittest.main()
