"""Durable CAS owner intent before transport; no game or real profiles."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli
import cas_client
import reusable_profile


class CasClientIntentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / 'The Sims 4 DO NOT TOUCH'
        self.profile.mkdir()
        self.original.mkdir()
        self.original_file = self.original / 'owner.save'
        self.original_file.write_bytes(b'never modify owner files')
        self.state = self.root / 'session.json'
        self.state.write_text('retained session sentinel')
        self.args = Obj(operation='select', state=self.state, output=self.root / 'proof.json',
                        sim_id='12', panel='clothing_hair', data_id='100', seconds=1)
        self.intent = self.args.output.with_suffix('.intent.json')
        self.load = self.enterContext(patch.object(reusable_profile, 'load', return_value=(
            self.state, {}, self.profile, self.original)))
        self.calls = []
        self.network = []

    def document(self):
        return json.loads(self.intent.read_text(encoding='utf-8'))

    def request(self, state, action, sim_id=None, **kwargs):
        self.calls.append((action, sim_id, kwargs))
        rid = '{:032x}'.format(len(self.calls))
        kwargs['submission_observer'](action, rid)
        # This is the simulated actual network boundary, after the callback.
        row = self.document()['owner_requests'][-1]
        self.assertEqual(row['request_id'], rid)
        self.assertEqual(row['action'], action)
        self.assertEqual(row['stage'], 'owner-submission-intent')
        self.network.append((action, rid))
        return {'ok': action == 'cas_ui_result', 'request_id': rid,
                'cas_request_id': 'c' * 32, 'request_state': 'completed',
                'outcome': 'pending-client' if action == 'cas_ui_request' else 'completed'}

    def test_success_retains_every_owner_uuid_before_transport_and_final_result(self):
        result = cas_client.execute(self.args, self.request)
        self.assertTrue(result['ok'])
        proof = self.document()
        self.assertEqual(proof['stage'], 'result-retained')
        self.assertEqual(proof['requested_operation'], 'select')
        self.assertEqual(proof['sim_id'], '12')
        self.assertEqual(proof['intended_request']['data_id'], '100')
        self.assertEqual([row['action'] for row in proof['owner_requests']], ['cas_ui_request', 'cas_ui_result'])
        self.assertEqual(len({row['request_id'] for row in proof['owner_requests']}), 2)
        self.assertTrue(all(row['stage'] == 'owner-response-retained' for row in proof['owner_requests']))
        self.assertFalse(proof['automatic_replay_allowed'])
        self.assertEqual(result['intent_sha256'], cas_client.sha256(self.intent))
        self.assertEqual(result['proof_sha256'], cas_client.sha256(self.args.output))
        self.assertEqual(self.original_file.read_bytes(), b'never modify owner files')

    def test_lost_transport_retains_original_uuid_and_never_repeats_the_mutation(self):
        def lost(state, action, sim_id=None, **kwargs):
            self.request(state, action, sim_id, **kwargs)
            raise OSError('response lost after submission')
        with self.assertRaisesRegex(OSError, 'response lost'):
            cas_client.execute(self.args, lost)
        self.assertEqual(self.network, [('cas_ui_request', '0' * 31 + '1')])
        proof = self.document()
        self.assertEqual(proof['stage'], 'execution-stopped')
        self.assertEqual(proof['owner_requests'][0]['request_id'], '0' * 31 + '1')
        self.assertEqual(proof['owner_requests'][0]['stage'], 'owner-request-unresolved')
        self.assertEqual(json.loads(self.args.output.read_text())['outcome'], 'unresolved')
        with self.assertRaisesRegex(ValueError, 'new external'):
            cas_client.execute(self.args, lost)
        self.assertEqual(len(self.network), 1)

    def test_foreign_owner_uuid_is_retained_as_rejected_reply_without_poll_or_replay(self):
        def foreign(*args, **kwargs):
            return dict(self.request(*args, **kwargs), request_id='f' * 32)
        with self.assertRaisesRegex(ValueError, 'missing or foreign UUID'):
            cas_client.execute(self.args, foreign)
        rows = self.document()['owner_requests']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['request_id'], '0' * 31 + '1')
        self.assertEqual(rows[0]['result']['request_id'], 'f' * 32)
        self.assertEqual(len(self.network), 1)

    def test_foreign_cas_result_uuid_stops_without_resubmitting_selection(self):
        def foreign(state, action, sim_id=None, **kwargs):
            result = self.request(state, action, sim_id, **kwargs)
            if action == 'cas_ui_result':
                result['cas_request_id'] = 'd' * 32
            return result
        with self.assertRaisesRegex(ValueError, 'CAS result has a missing or foreign'):
            cas_client.execute(self.args, foreign)
        self.assertEqual([action for action, _rid in self.network], ['cas_ui_request', 'cas_ui_result'])
        self.assertEqual(self.document()['owner_requests'][-1]['intended_request']['value'], 'c' * 32)

    def test_success_missing_owner_uuid_after_real_submission_callback_is_rejected_and_retained(self):
        def missing_owner(*args, **kwargs):
            result = self.request(*args, **kwargs)
            result.update(ok=True)
            result.pop('request_id')
            return result
        with self.assertRaisesRegex(ValueError, 'Owner acknowledgement has a missing or foreign UUID'):
            cas_client.execute(self.args, missing_owner)
        rows = self.document()['owner_requests']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['request_id'], '0' * 31 + '1')
        self.assertNotIn('request_id', rows[0]['result'])
        self.assertTrue(rows[0]['result']['ok'])
        self.assertFalse(rows[0]['owner_ack_identity_verified'])
        self.assertEqual(rows[0]['stage'], 'owner-request-unresolved')
        self.assertEqual(len(self.network), 1)

    def test_successful_cas_result_missing_cas_uuid_is_rejected_without_replaying_selection(self):
        def missing_cas(state, action, *args, **kwargs):
            result = self.request(state, action, *args, **kwargs)
            if action == 'cas_ui_result':
                result.pop('cas_request_id')
            return result
        with self.assertRaisesRegex(ValueError, 'CAS result has a missing or foreign request UUID'):
            cas_client.execute(self.args, missing_cas)
        rows = self.document()['owner_requests']
        self.assertEqual([action for action, _rid in self.network], ['cas_ui_request', 'cas_ui_result'])
        self.assertEqual(rows[-1]['request_id'], '0' * 31 + '2')
        self.assertNotIn('cas_request_id', rows[-1]['result'])
        self.assertTrue(rows[-1]['owner_ack_identity_verified'])
        self.assertFalse(rows[-1]['cas_ack_identity_verified'])
        self.assertEqual(rows[-1]['stage'], 'owner-request-unresolved')

    def test_successful_final_cas_reply_missing_owner_uuid_retains_both_owner_ids(self):
        def missing_final_owner(state, action, *args, **kwargs):
            result = self.request(state, action, *args, **kwargs)
            if action == 'cas_ui_result':
                result.pop('request_id')
            return result
        with self.assertRaisesRegex(ValueError, 'Owner acknowledgement has a missing or foreign UUID'):
            cas_client.execute(self.args, missing_final_owner)
        rows = self.document()['owner_requests']
        self.assertEqual([row['request_id'] for row in rows], ['0' * 31 + '1', '0' * 31 + '2'])
        self.assertEqual(rows[-1]['result']['cas_request_id'], 'c' * 32)
        self.assertNotIn('request_id', rows[-1]['result'])
        self.assertFalse(rows[-1]['owner_ack_identity_verified'])
        self.assertEqual([action for action, _rid in self.network], ['cas_ui_request', 'cas_ui_result'])

    def test_present_non_boolean_ok_refuses_truthy_and_falsey_values_and_retains_raw_reply(self):
        for index, invalid in enumerate((1, 0, 'true', '', None, {}, [])):
            with self.subTest(invalid=invalid):
                self.args.output = self.root / ('untyped-ok-' + str(index) + '.json')
                self.intent = self.args.output.with_suffix('.intent.json')
                before = len(self.network)
                def malformed(state, action, *args, **kwargs):
                    result = self.request(state, action, *args, **kwargs)
                    if action == 'cas_ui_result':
                        result['ok'] = invalid
                        result.pop('request_id')
                        result.pop('cas_request_id')
                    return result
                with self.assertRaisesRegex(ValueError, 'untyped ok value'):
                    cas_client.execute(self.args, malformed)
                rows = self.document()['owner_requests']
                self.assertEqual([action for action, _rid in self.network[before:]],
                                 ['cas_ui_request', 'cas_ui_result'])
                self.assertEqual(rows[-1]['request_id'], self.network[-1][1])
                self.assertEqual(type(rows[-1]['result']['ok']), type(invalid))
                self.assertEqual(rows[-1]['result']['ok'], invalid)
                self.assertNotIn('owner_ack_identity_verified', rows[-1])
                self.assertEqual(rows[-1]['stage'], 'owner-request-unresolved')
                self.assertIs(json.loads(self.args.output.read_text())['ok'], False)

    def test_failed_no_record_payload_without_ids_remains_unqualified_and_never_replays(self):
        self.args.operation = 'result'
        self.args.request_id = 'c' * 32
        def missing_record(state, action, *args, **kwargs):
            self.request(state, action, *args, **kwargs)
            return {'ok': False, 'message': 'No matching CAS request record'}
        result = cas_client.execute(self.args, missing_record)
        self.assertFalse(result['ok'])
        row = self.document()['owner_requests'][0]
        self.assertFalse(row['owner_ack_identity_verified'])
        self.assertFalse(row['cas_ack_identity_verified'])
        self.assertEqual(row['result'], {'ok': False, 'message': 'No matching CAS request record'})
        self.assertEqual([action for action, _rid in self.network], ['cas_ui_result'])

    def test_result_operation_only_polls_retained_cas_id(self):
        self.args.operation = 'result'
        self.args.request_id = 'c' * 32
        result = cas_client.execute(self.args, self.request)
        self.assertTrue(result['ok'])
        self.assertEqual([row[0] for row in self.calls], ['cas_ui_result'])
        self.assertEqual(self.calls[0][2]['value'], 'c' * 32)
        self.assertEqual(self.document()['intended_request']['request_id'], 'c' * 32)

    def test_panels_query_with_output_uses_same_collision_checks_and_durable_owner_request(self):
        self.args.operation = 'panels'
        self.assertFalse(cas_client.execute(self.args, self.request)['ok'])
        self.assertEqual([row[0] for row in self.calls], ['cas_ui_panels'])
        self.assertEqual(self.document()['stage'], 'result-retained')

    def test_existing_output_or_sidecar_is_never_replaced_and_no_action_is_called(self):
        for name in ('existing-output.json', 'existing-sidecar.json'):
            output = self.root / name
            collision = output if name == 'existing-output.json' else output.with_suffix('.intent.json')
            collision.write_text('retain existing bytes')
            self.args.output = output
            with self.assertRaisesRegex(ValueError, 'new external'):
                cas_client.execute(self.args, self.request)
            self.assertEqual(collision.read_text(), 'retain existing bytes')
        self.assertEqual(self.calls, [])

    def test_profile_protected_journal_and_missing_parent_paths_refuse_before_any_action(self):
        for output in (self.profile / 'proof.json', self.original / 'proof.json', self.state,
                       self.root / 'absent' / 'proof.json'):
            self.args.output = output
            with self.assertRaises(ValueError):
                cas_client.execute(self.args, self.request)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.original_file.read_bytes(), b'never modify owner files')
        self.assertEqual(self.state.read_text(), 'retained session sentinel')

    def test_noncanonical_loaded_profile_alias_cannot_bypass_output_containment(self):
        self.load.return_value = (self.state, {}, self.profile / '..' / self.profile.name, self.original)
        self.args.output = self.profile / 'proof.json'
        with self.assertRaisesRegex(ValueError, 'new external'):
            cas_client.execute(self.args, self.request)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.args.output.exists())

    def test_linked_output_or_sidecar_refuses_even_when_link_target_does_not_exist(self):
        actual = Path.is_symlink
        for linked in (self.args.output, self.intent):
            with patch.object(Path, 'is_symlink', lambda path, target=linked: path == target or actual(path)), \
                    self.assertRaisesRegex(ValueError, 'must not be linked'):
                cas_client.execute(self.args, self.request)
        self.assertEqual(self.calls, [])

    def test_observer_is_forwarded_after_durable_write_and_other_kwargs_are_preserved(self):
        evidence = cas_client.IntentEvidence(self.args)
        observer_calls, received = [], []
        transport = Mock()
        def previous(action, rid):
            self.assertEqual(self.document()['owner_requests'][-1]['request_id'], rid)
            observer_calls.append((action, rid))
        def request(state, action, *args, **kwargs):
            kwargs['submission_observer'](action, 'a' * 32)
            self.assertEqual(observer_calls, [(action, 'a' * 32)])
            received.append((state, action, args, kwargs))
            return {'ok': True, 'request_id': 'a' * 32}
        result = evidence.wrap(request)(self.state, 'cas_ui_diagnostics', '12', seconds=7,
            value='exact value', occult=8, transport=transport, submission_observer=previous)
        self.assertTrue(result['ok'])
        self.assertEqual(received[0][:3], (self.state, 'cas_ui_diagnostics', ('12',)))
        self.assertIs(received[0][3]['transport'], transport)
        self.assertEqual({key: received[0][3][key] for key in ('seconds', 'value', 'occult')},
                         {'seconds': 7, 'value': 'exact value', 'occult': 8})

    def test_bad_observer_action_duplicate_uuid_and_absent_callback_never_get_success(self):
        for kind in ('foreign-action', 'duplicate', 'absent'):
            self.args.output = self.root / (kind + '.json')
            def broken(state, action, *args, submission_observer, **kwargs):
                if kind != 'absent':
                    submission_observer('foreign' if kind == 'foreign-action' else action, 'a' * 32)
                if kind == 'duplicate':
                    submission_observer(action, 'a' * 32)
                return {'ok': True}
            with self.assertRaises(ValueError):
                cas_client.execute(self.args, broken)

    def test_existing_output_none_workbench_namespace_keeps_original_transport_contract(self):
        self.args.output = None
        requests = []
        def request(state, action, sim_id=None, **kwargs):
            self.assertNotIn('submission_observer', kwargs)
            requests.append(action)
            return {'ok': True, 'cas_request_id': 'c' * 32}
        self.assertTrue(cas_client.execute(self.args, request)['ok'])
        self.assertEqual(requests, ['cas_ui_request', 'cas_ui_result'])
        self.assertFalse(self.intent.exists())
        self.load.assert_not_called()

    def test_failed_atomic_uuid_publication_prevents_actual_network_dispatch(self):
        original_write = cas_client.write_json
        reached_network = []
        def write(path, value):
            if path == self.intent and value.get('stage') == 'owner-submission-intent':
                raise OSError('intent flush failed')
            return original_write(path, value)
        def request(state, action, *args, submission_observer, **kwargs):
            submission_observer(action, 'a' * 32)
            reached_network.append(action)
            return {'ok': True}
        with patch.object(cas_client, 'write_json', side_effect=write), \
                self.assertRaisesRegex(OSError, 'intent flush failed'):
            cas_client.execute(self.args, request)
        self.assertEqual(reached_network, [])
        self.assertEqual(self.document()['owner_requests'][0]['request_id'], 'a' * 32)

    def test_changed_sidecar_is_never_overwritten_to_repair_evidence_or_repeat_input(self):
        def request(state, action, *args, submission_observer, **kwargs):
            self.intent.write_text('foreign replacement must remain untouched')
            submission_observer(action, 'a' * 32)
            self.fail('Changed intent must stop before actual transport')
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            cas_client.execute(self.args, request)
        self.assertEqual(self.intent.read_text(), 'foreign replacement must remain untouched')
        self.assertEqual(self.original_file.read_bytes(), b'never modify owner files')

    def test_standard_owned_request_get_transport_sees_uuid_already_flushed(self):
        requests = []
        def get(path, query=None, timeout=12):
            self.assertEqual(path, '/api/command')
            row = self.document()['owner_requests'][-1]
            self.assertEqual(row['request_id'], query['request_id'])
            self.assertEqual(row['action'], query['action'])
            requests.append(query.copy())
            return {'ok': query['action'] == 'cas_ui_result', 'request_id': query['request_id'],
                    'cas_request_id': 'c' * 32}
        with patch.object(apex_cli, 'verified_identity', return_value={'alarm_ready': True}):
            result = cas_client.execute(self.args, partial(apex_cli.owned_request, transport=get))
        self.assertTrue(result['ok'])
        self.assertEqual([row['action'] for row in requests], ['cas_ui_request', 'cas_ui_result'])

    def test_standard_owned_request_lost_response_only_polls_same_owner_uuid(self):
        requests = []
        def get(path, query=None, timeout=12):
            self.assertEqual(self.document()['owner_requests'][-1]['request_id'], query['request_id'])
            requests.append((path, query.copy()))
            raise OSError('transport unavailable')
        with patch.object(apex_cli, 'verified_identity', return_value={'alarm_ready': True}), \
                self.assertRaisesRegex(OSError, 'transport unavailable'):
            cas_client.execute(self.args, partial(apex_cli.owned_request, transport=get))
        self.assertEqual([path for path, _query in requests], ['/api/command', '/api/requests/status'])
        self.assertEqual(requests[0][1]['request_id'], requests[1][1]['request_id'])
        self.assertEqual(len(self.document()['owner_requests']), 1)


if __name__ == '__main__':
    unittest.main()
