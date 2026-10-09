import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
from apex_core import cas_ui
import apex_cli
import cas_return
from test_cas_accept import HOUSEHOLD, SIM, live_snapshot, native_client


class CasReturnTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / cas_return.reusable_profile.PROTECTED_NAME
        (self.profile / 'Mods/Apex').mkdir(parents=True)
        (self.original / 'saves').mkdir(parents=True)
        (self.original / 'saves/original.save').write_bytes(b'untouched owner save')
        self.token = 'a' * 32
        (self.profile / cas_return.reusable_profile.legacy.MARKER).write_text(json.dumps({'token': self.token}))
        script = self.profile / 'Mods/Apex/ApexOccultHybrid.ts4script'
        script.write_bytes(b'exact script')
        self.digest = hashlib.sha256(script.read_bytes()).hexdigest()
        self.state = self.root / 'session.json'
        journal = {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active', 'token': self.token,
                   'profile': str(self.profile), 'protected_original': str(self.original),
                   'artifacts': [{'name': script.name, 'relative': 'Apex/' + script.name, 'sha256': self.digest}]}
        self.state.write_text(json.dumps(journal))
        self.identity = {'pid': 42, 'test_token': self.token, 'script_sha256': self.digest, 'profile': str(self.profile)}
        self.output = self.root / 'return-proof.json'
        self.clock = 0
        self.ticks = 100
        self.speed = 0
        self.increment = 10
        self.alive = True
        self.detach = True
        self.overlay_visible = False
        self.calls = []
        self.handler = None
        self.transport_calls = []
        self.transport_handler = None
        self.received = set()
        cas_ui._RECORDS.clear()
        cas_ui._PEERS.clear()
        self.peer = cas_ui.attach_client(SIM)
        self.accept_id = None
        self.legacy_finished = False

    def tick(self, seconds):
        self.clock += seconds

    def tree(self, root):
        return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def transport(self, path, query=None, timeout=12):
        self.assertLessEqual(timeout, 2)
        self.transport_calls.append((path, copy.deepcopy(query), timeout))
        if self.transport_handler is not None:
            result = self.transport_handler(path, query, timeout)
            if result is not None:
                return result
        if path == '/api/bridge':
            return dict(self.identity, ok=True, alarm_ready=True, core_tick_ready=True)
        if path == '/api/requests/status':
            self.assertEqual(query, {'request_id': json.loads(self.output.read_text())['cas_bank_observe_request_id']})
            return {'ok': False, 'request_id': query['request_id'], 'state': 'unknown'}
        self.assertEqual(path, '/api/command')
        self.assertTrue(cas_return.uuid_id(query['request_id']))
        return {'ok': True}

    def snapshot(self):
        return live_snapshot(str(self.ticks), self.speed)

    def request(self, state, action, sim_id=None, value=None, transport=None, **_kwargs):
        self.calls.append((action, value))
        self.clock += .02
        self.assertEqual(sim_id, SIM)
        transport('/api/bridge')
        transport('/api/command', {'action': action, 'request_id': uuid.uuid4().hex})
        if self.handler is not None:
            result = self.handler(action, value)
            if result is not None:
                return result
        if action == 'overlay_status':
            return {'ok': True, 'visible': self.overlay_visible}
        if action == 'overlay_hide':
            self.overlay_visible = False
            return {'ok': True, 'visible': False}
        if action == 'overlay_show':
            self.overlay_visible = True
            return {'ok': True, 'visible': True}
        if action == 'cas_session_finish':
            self.legacy_finished = True
            return {'ok': True, 'lane': '1', 'edited': True, 'request_state': 'completed'}
        if action == 'cas_session_status':
            return {'ok': True, 'captured': True, 'active_lane': '1', 'bank_lanes': ['1', '2', '4', '8', '16', '32', '64'],
                    'pending_state': None if self.legacy_finished else 'captured',
                    'pending_schema': None if self.legacy_finished else 1, 'switch_pending': False}
        if action == 'cas_ui_diagnostics':
            if self.accept_id in self.received and self.detach:
                cas_ui.detach_client(self.peer)
            return {'ok': True, 'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021},
                    'requests': [{'cas_request_id': rid, 'state': row['state'], 'operation': row['request']['operation']}
                                 for rid, row in cas_ui._RECORDS.items()],
                    'native_peers': [{'sim_id': SIM, 'age_seconds': .2}] if cas_ui._PEERS else []}
        if action == 'cas_ui_request':
            operation = json.loads(value)
            result = cas_ui.submit(SIM, operation)
            self.assertIsNotNone(cas_ui.poll_client(self.peer))
            if operation['operation'] == 'accept':
                self.accept_id = result['cas_request_id']
            return result
        if action == 'cas_ui_result':
            row = cas_ui._RECORDS[value]
            if value not in self.received:
                reply = {'protocol': 1, 'ok': True, 'cas_request_id': value, 'client': native_client()}
                if row['request']['operation'] == 'accept':
                    reply.update(lifecycle_stage='accept-intent', commit_submitted=False)
                cas_ui.receive_socket(self.peer, value, json.dumps(reply))
                self.received.add(value)
            return cas_ui.result(value)
        if action.startswith('test_'):
            guarded = json.loads(value)
            self.assertEqual(guarded['test_token'], self.token)
            if action == 'test_snapshot':
                if self.speed == 1:
                    self.ticks += self.increment
                return self.snapshot()
            if action == 'test_play':
                self.speed = 1
                return self.snapshot()
            if action == 'test_pause':
                self.speed = 0
                return self.snapshot()
            if action == 'test_cas_return_observed':
                args = guarded['value']
                return cas_ui.observe_return(args['cas_request_id'], self.snapshot(), args['phase'],
                                             args['household_id'], args['minimum_ticks'])
        self.fail('Unexpected action: ' + action)

    def run_observer(self, **kwargs):
        seconds = kwargs.pop('seconds', 5)
        result = cas_return.observe(self.state, self.output, self.identity, self.request, SIM, HOUSEHOLD,
                    transport=self.transport, alive=lambda _pid: self.alive,
                    monotonic=lambda: self.clock, pause=self.tick, seconds=seconds, **kwargs)
        return result, json.loads(self.output.read_text())

    def modern_status(self, phase='captured', **overrides):
        transaction = {'ok': True, 'phase': phase, 'current_runtime': True,
            'expected_pending_sha256': 'b' * 64, 'checkpoint_sha256': 'c' * 64,
            'writer_lease_present': False, 'native_write_possible': False,
            'native_write_attempted': False, 'metadata_commit_persisted': False,
            'raw_return_sha256': 'd' * 64 if phase != 'captured' else None,
            'plan_sha256': 'e' * 64 if phase == 'planned' else None,
            'changed_lanes': ['1', '4'], 'changed_lane_summary': [
                {'lane': '1', 'changed_fields': ['physique', '__outfits__']},
                {'lane': '4', 'changed_fields': ['skin_tone', '__outfits__']}]}
        transaction.update(overrides)
        return {'ok': True, 'captured': True, 'bank_lanes': ['1', '4'], 'active_lane': '1',
                'pending_state': 'captured', 'pending_schema': 2, 'switch_pending': False,
                'cas_transaction': transaction}

    def modern_handler(self, initial='captured', observe=None, **overrides):
        phase = [initial]
        def handler(action, value):
            if action == 'cas_session_status':
                return self.modern_status(phase[0], **overrides)
            if action == 'cas_bank_observe':
                disk = json.loads(self.output.read_text())
                original_uuid = disk['cas_bank_observe_request_id']
                self.assertTrue(cas_return.uuid_id(original_uuid))
                self.assertTrue(disk['cas_bank_observe_attempted'])
                self.assertEqual(disk['owner_requests'][-1],
                    {'action': 'cas_bank_observe', 'request_id': original_uuid})
                self.assertTrue(disk['return_metadata_completed'])
                self.assertTrue(disk['clock_progress_verified'])
                self.assertTrue(disk['final_paused'])
                self.assertEqual(json.loads(value), {'expected_pending_sha256': 'b' * 64})
                phase[0] = 'observed'
                if observe is not None:
                    return observe(original_uuid)
                return {'ok': True, 'expected_pending_sha256': 'b' * 64,
                    'checkpoint_sha256': 'c' * 64, 'raw_return_sha256': 'd' * 64,
                    'journal_sha256': 'f' * 64, 'native_write_attempted': False,
                    'request_id': original_uuid, 'request_state': 'completed'}
        self.handler = handler
        return phase

    def assert_no_cas_edit_commit(self):
        self.assertFalse(any(action in ('cas_session_finish', 'cas_bank_prepare', 'cas_bank_commit',
            'studio_apply', 'test_save', 'test_outfit', 'test_input') for action, _ in self.calls))

    def cancelled_complete_handler(self, cancellation=None, after_cancel=None, rebound=None):
        completions = [0]
        def handler(action, value):
            if action == 'test_cas_return_observed':
                args = json.loads(value)['value']
                if args['phase'] == 'complete':
                    completions[0] += 1
                    disk = json.loads(self.output.read_text())
                    intent = disk['return_metadata_observations'][-1]
                    owner = intent['owner_request_id']
                    self.assertTrue(cas_return.uuid_id(owner))
                    self.assertEqual(intent['cas_request_id'], self.accept_id)
                    self.assertEqual(intent['household_id'], HOUSEHOLD)
                    if completions[0] == 1:
                        result = {'ok': False, 'request_state': 'cancelled', 'request_id': owner,
                                  'message': cas_return.ZONE_CANCELLED_BEFORE_EXECUTION}
                        return cancellation(result) if cancellation is not None else result
                    self.assertEqual(completions[0], 2, 'Metadata observation must never submit a third time.')
                    self.assertTrue(disk['return_metadata_rebound_attempted'])
                    self.assertEqual(intent['rebound_of'], disk['return_metadata_observations'][-2]['owner_request_id'])
                    if rebound is not None:
                        return rebound(owner, args)
                    result = cas_ui.observe_return(args['cas_request_id'], self.snapshot(), 'complete',
                                                   HOUSEHOLD, args['minimum_ticks'])
                    return dict(result, request_id=owner, request_state='completed')
            if completions[0] and after_cancel is not None:
                return after_cancel(action, value)
        self.handler = handler
        return completions

    def test_exact_before_execution_zone_cancel_rebinds_only_metadata_completion_once(self):
        before = self.tree(self.profile), self.tree(self.original)
        completions = self.cancelled_complete_handler()
        result, proof = self.run_observer(settle_ticks=30)
        self.assertTrue(result['ok'], proof.get('error'))
        self.assertEqual(completions[0], 2)
        self.assertTrue(result['return_metadata_rebound_attempted'])
        self.assertTrue(result['return_metadata_rebound_verified'])
        self.assertTrue(result['return_metadata_completed'])
        observations = proof['return_metadata_observations']
        self.assertEqual([row['phase'] for row in observations], ['baseline', 'complete', 'complete'])
        self.assertEqual(len({row['owner_request_id'] for row in observations}), 3)
        self.assertEqual(observations[-1]['rebound_of'], observations[-2]['owner_request_id'])
        self.assertEqual(proof['return_metadata_rebound_preflight']['cancellation'], observations[-2]['result'])
        self.assertEqual(proof['return_metadata_rebound_preflight']['snapshot']['clock_speed'], 0)
        self.assertEqual(sum(action == 'test_play' for action, _ in self.calls), 1)
        self.assertEqual(sum(action == 'test_pause' for action, _ in self.calls), 1)
        self.assertEqual([json.loads(value)['operation'] for action, value in self.calls
                          if action == 'cas_ui_request'], ['status', 'accept'])
        self.assertEqual((self.tree(self.profile), self.tree(self.original)), before)

    def test_metadata_cancellation_requires_exact_terminal_shape_message_and_original_owner(self):
        changes = ({'request_state': 'unknown'}, {'request_state': 'failed'}, {'request_state': 'rejected'},
                   {'ok': 0}, {'request_id': 'e' * 32}, {'message': 'Command expired before execution.'},
                   {'response_lost_or_failed': True}, {'outcome': 'unresolved'})
        for index, change in enumerate(changes):
            with self.subTest(change=change):
                if index:
                    self.setUp()
                completions = self.cancelled_complete_handler(cancellation=lambda result: dict(result, **change))
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertEqual(completions[0], 1)
                self.assertFalse(proof['return_metadata_rebound_attempted'])
                self.assertFalse(proof['return_metadata_completed'])

    def test_metadata_zone_rebind_refuses_fresh_foreign_or_unpaused_or_regressed_context(self):
        changes = ({'sim': {'id': '8', 'instanced': True}}, {'household_id': '8'}, {'client_id': '8'},
                   {'zone_id': '8'}, {'save_guid': '8'}, {'clock_speed': 1}, {'sim_now_ticks': '100'},
                   {'sim_time_source': 'services.game_clock_service().now()'})
        for index, change in enumerate(changes):
            with self.subTest(change=change):
                if index:
                    self.setUp()
                def after_cancel(action, _value):
                    if action == 'test_snapshot':
                        return dict(self.snapshot(), **change)
                completions = self.cancelled_complete_handler(after_cancel=after_cancel)
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertEqual(completions[0], 1)
                self.assertFalse(proof['return_metadata_rebound_attempted'])
                self.assertFalse(proof['return_metadata_completed'])

    def test_metadata_zone_rebind_requires_fresh_exact_bridge_runtime_and_ready_owner(self):
        changes = ({'pid': 43}, {'test_token': 'b' * 32}, {'script_sha256': 'b' * 64},
                   {'alarm_ready': False}, {'core_tick_ready': False})
        for index, change in enumerate(changes):
            with self.subTest(change=change):
                if index:
                    self.setUp()
                completions = self.cancelled_complete_handler()
                def changed_bridge(path, _query, _timeout):
                    if path == '/api/bridge' and completions[0]:
                        return {**self.identity, 'ok': True, 'alarm_ready': True, 'core_tick_ready': True, **change}
                self.transport_handler = changed_bridge
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertEqual(completions[0], 1)
                self.assertFalse(proof['return_metadata_rebound_attempted'])

    def test_second_metadata_zone_cancellation_cannot_rebind_again(self):
        completions = self.cancelled_complete_handler(rebound=lambda owner, _args: {
            'ok': False, 'request_state': 'cancelled', 'request_id': owner,
            'message': cas_return.ZONE_CANCELLED_BEFORE_EXECUTION})
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(completions[0], 2)
        self.assertTrue(proof['return_metadata_rebound_attempted'])
        self.assertFalse(proof['return_metadata_rebound_verified'])
        self.assertFalse(proof['return_metadata_completed'])

    def test_rebound_metadata_wrong_owner_and_lost_response_never_complete_or_repeat(self):
        for index, lose in enumerate((False, True)):
            with self.subTest(response_lost=lose):
                if index:
                    self.setUp()
                def rebound(owner, args):
                    result = cas_ui.observe_return(args['cas_request_id'], self.snapshot(), 'complete',
                                                   HOUSEHOLD, args['minimum_ticks'])
                    if lose:
                        raise OSError('rebound metadata response lost')
                    return dict(result, request_id='f' * 32, request_state='completed')
                completions = self.cancelled_complete_handler(rebound=rebound)
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertEqual(completions[0], 2)
                self.assertTrue(proof['return_metadata_rebound_attempted'])
                self.assertFalse(proof['return_metadata_rebound_verified'])
                self.assertFalse(proof['return_metadata_completed'])

    def test_zone_cancel_after_deadline_keeps_original_uuid_without_rebound(self):
        def cancellation(result):
            self.clock += 6
            return result
        completions = self.cancelled_complete_handler(cancellation=cancellation)
        result, proof = self.run_observer(seconds=5)
        self.assertFalse(result['ok'])
        self.assertEqual(completions[0], 1)
        self.assertFalse(proof['return_metadata_rebound_attempted'])
        self.assertTrue(cas_return.uuid_id(proof['return_metadata_observations'][-1]['owner_request_id']))

    def test_zone_cancel_baseline_cannot_borrow_unproven_progress_or_rebind(self):
        def handler(action, value):
            if action == 'test_cas_return_observed' and json.loads(value)['value']['phase'] == 'baseline':
                owner = json.loads(self.output.read_text())['return_metadata_observations'][-1]['owner_request_id']
                return {'ok': False, 'request_state': 'cancelled', 'request_id': owner,
                        'message': cas_return.ZONE_CANCELLED_BEFORE_EXECUTION}
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(proof['return_metadata_rebound_attempted'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))

    def test_exact_cancellation_after_observed_transport_loss_does_not_authorize_rebound(self):
        def lost_and_cancelled(result):
            try:
                self.transport_handler = lambda _path, _query, _timeout: (_ for _ in ()).throw(OSError('lost request response'))
                # Emulate a request adapter that catches response loss and later
                # returns a terminal cancellation; the durable intent keeps loss.
                raise_transport = self.active_transport
                raise_transport('/api/requests/status', {'request_id': result['request_id']})
            except OSError:
                pass
            finally:
                self.transport_handler = None
            return result
        original_request = self.request
        def request(*args, **kwargs):
            self.active_transport = kwargs['transport']
            return original_request(*args, **kwargs)
        self.request = request
        completions = self.cancelled_complete_handler(cancellation=lost_and_cancelled)
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(completions[0], 1)
        self.assertFalse(proof['return_metadata_rebound_attempted'])
        self.assertIn('transport_error', proof['return_metadata_observations'][-1])

    def test_completed_rebound_arriving_after_deadline_retains_receipt_without_success(self):
        def rebound(owner, args):
            result = cas_ui.observe_return(args['cas_request_id'], self.snapshot(), 'complete',
                                           HOUSEHOLD, args['minimum_ticks'])
            self.clock += 6
            return dict(result, request_id=owner, request_state='completed')
        completions = self.cancelled_complete_handler(rebound=rebound)
        result, proof = self.run_observer(seconds=5)
        self.assertFalse(result['ok'])
        self.assertEqual(completions[0], 2)
        self.assertTrue(proof['return_metadata_rebound_attempted'])
        self.assertFalse(proof['return_metadata_rebound_verified'])
        self.assertFalse(proof['return_metadata_completed'])
        self.assertEqual(proof['return_metadata_observations'][-1]['result']['request_state'], 'completed')

    def test_semantic_return_uses_one_intent_then_ticks_pause_and_bank_finish_without_pointer_or_save(self):
        before = self.tree(self.profile), self.tree(self.original)
        result, proof = self.run_observer(settle_ticks=30)
        self.assertTrue(result['ok'], proof.get('error'))
        self.assertEqual(result['outcome'], 'live-return')
        self.assertTrue(result['ui_transition_verified'])
        self.assertTrue(result['final_paused'])
        self.assertFalse(result['native_commit_submission_verified'])
        self.assertFalse(result['appearance_persistence_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertFalse(proof['accept_intent']['ui_transition_verified'])
        self.assertEqual(proof['live_snapshot']['save_slot'], 0xffffffff)
        operations = [json.loads(value)['operation'] for action, value in self.calls if action == 'cas_ui_request']
        self.assertEqual(operations, ['status', 'accept'])
        accept_request = next(json.loads(value) for action, value in self.calls
                              if action == 'cas_ui_request' and json.loads(value)['operation'] == 'accept')
        self.assertEqual(accept_request, {'operation': 'accept', 'household_id': HOUSEHOLD})
        self.assertEqual(sum(action == 'test_play' for action, _ in self.calls), 1)
        self.assertEqual(sum(action == 'test_pause' for action, _ in self.calls), 1)
        self.assertEqual(sum(action == 'cas_session_finish' for action, _ in self.calls), 1)
        self.assertTrue(result['form_bank_completion_verified'])
        self.assertTrue(all(action in ('cas_ui_diagnostics', 'cas_ui_request', 'cas_ui_result',
                        'test_snapshot', 'test_cas_return_observed', 'test_play', 'test_pause',
                        'overlay_status', 'overlay_hide', 'overlay_show', 'cas_session_finish', 'cas_session_status') for action, _ in self.calls))
        self.assertEqual((self.tree(self.profile), self.tree(self.original)), before)
        self.assertTrue(proof['owner_requests'])
        self.assertEqual(cas_ui.result(self.accept_id)['outcome'], 'live-return')

    def test_schema2_raw_return_is_observed_once_after_unpause_pause_without_edit_inference(self):
        before = self.tree(self.profile), self.tree(self.original)
        self.modern_handler()
        result, proof = self.run_observer(settle_ticks=30)
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'live-return-explicit-cas-decisions-required')
        self.assertTrue(result['ui_transition_verified'])
        self.assertTrue(result['clock_progress_verified'])
        self.assertTrue(result['final_paused'])
        self.assertTrue(result['cas_bank_observation_verified'])
        self.assertTrue(result['cas_explicit_decisions_required'])
        self.assertFalse(result['form_bank_finish_attempted'])
        self.assertFalse(result['form_bank_completion_verified'])
        self.assertFalse(result['appearance_persistence_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(result['cas_transaction_phase'], 'observed')
        actions = [action for action, _ in self.calls]
        self.assertEqual(actions.count('cas_bank_observe'), 1)
        self.assertEqual(actions.count('test_play'), 1)
        self.assertEqual(actions.count('test_pause'), 1)
        self.assertGreater(actions.index('cas_session_status'), actions.index('test_pause'))
        self.assertGreater(actions.index('cas_bank_observe'), actions.index('cas_session_status'))
        self.assertEqual(proof['raw_return_sha256'], 'd' * 64)
        self.assertEqual(proof['journal_sha256'], 'f' * 64)
        self.assertEqual(proof['changed_lanes'], ['1', '4'])
        receipt = json.dumps(proof['cas_bank_observation_receipt'], sort_keys=True,
                             ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        self.assertEqual(proof['cas_bank_observation_receipt_sha256'], hashlib.sha256(receipt).hexdigest())
        self.assertNotIn('error', proof)
        self.assert_no_cas_edit_commit()
        self.assertEqual((self.tree(self.profile), self.tree(self.original)), before)

    def test_schema2_lost_observer_ack_retains_original_uuid_and_never_replays(self):
        def lost(_uuid):
            raise OSError('Raw return was persisted; its serializer acknowledgment was lost')
        self.modern_handler(observe=lost)
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'live-return-cas-observation-unresolved')
        self.assertTrue(result['ui_transition_verified'])
        self.assertTrue(result['final_paused'])
        self.assertTrue(result['cas_bank_observe_attempted'])
        self.assertFalse(result['cas_bank_observation_verified'])
        self.assertTrue(cas_return.uuid_id(result['cas_bank_observe_request_id']))
        self.assertEqual(proof['owner_requests'][-1],
            {'action': 'cas_bank_observe', 'request_id': result['cas_bank_observe_request_id']})
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assertEqual(sum(action == 'cas_session_status' for action, _ in self.calls), 1)
        self.assert_no_cas_edit_commit()

    def test_schema2_running_observation_exhausts_whole_deadline_without_replay_or_finish(self):
        self.modern_handler(observe=lambda original_uuid: {'ok': False, 'outcome': 'unresolved',
                            'request_id': original_uuid, 'request_state': 'running'})
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'live-return-cas-observation-unresolved')
        self.assertTrue(result['ui_transition_verified'])
        self.assertFalse(result['cas_bank_observation_verified'])
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assertGreater(proof['cas_bank_observe_status_poll_count'], 1)
        self.assertEqual(result['elapsed_seconds'], 5)
        self.assertEqual({query['request_id'] for path, query, _timeout in self.transport_calls
                          if path == '/api/requests/status'}, {proof['cas_bank_observe_request_id']})
        self.assertNotIn('raw_return_sha256', proof)
        self.assert_no_cas_edit_commit()

    def completed_bank_observation(self, request_id):
        return {'ok': True, 'request_id': request_id, 'expected_pending_sha256': 'b' * 64,
                'checkpoint_sha256': 'c' * 64, 'raw_return_sha256': 'd' * 64,
                'journal_sha256': 'f' * 64, 'native_write_attempted': False}

    def test_schema2_delayed_raw_capture_completes_after_short_poll_without_new_submission(self):
        before = self.tree(self.profile), self.tree(self.original)
        def short_poll(request_id):
            self.clock += 2  # The first request's short completion budget elapsed.
            return {'ok': False, 'outcome': 'unresolved', 'request_id': request_id,
                    'request_state': 'running'}
        self.modern_handler(observe=short_poll)
        def transport(path, query, _timeout):
            if path == '/api/requests/status':
                done = self.clock >= 3
                return {'ok': True, 'request_id': query['request_id'],
                        'state': 'completed' if done else 'running',
                        'result': self.completed_bank_observation(query['request_id']) if done else None}
        self.transport_handler = transport
        result, proof = self.run_observer()
        self.assertTrue(result['cas_bank_observation_verified'], proof.get('error'))
        self.assertEqual(result['outcome'], 'live-return-explicit-cas-decisions-required')
        self.assertGreater(result['elapsed_seconds'], 3)
        self.assertLess(result['elapsed_seconds'], 5)
        self.assertGreater(proof['cas_bank_observe_status_poll_count'], 1)
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assertEqual(proof['cas_bank_observation_receipt']['request_id'], proof['cas_bank_observe_request_id'])
        for index, (path, query, timeout) in enumerate(self.transport_calls):
            if path == '/api/requests/status':
                self.assertEqual(self.transport_calls[index - 1][0], '/api/bridge')
                self.assertEqual(query, {'request_id': proof['cas_bank_observe_request_id']})
                self.assertGreater(timeout, 0)
        self.assertEqual((self.tree(self.profile), self.tree(self.original)), before)
        self.assert_no_cas_edit_commit()

    def test_schema2_lost_short_poll_response_can_observe_original_completion(self):
        def lost(_request_id):
            raise OSError('Initial completion response lost after raw capture')
        self.modern_handler(observe=lost)
        def transport(path, query, _timeout):
            if path == '/api/requests/status':
                return {'ok': True, 'request_id': query['request_id'], 'state': 'completed',
                        'result': self.completed_bank_observation(query['request_id'])}
        self.transport_handler = transport
        result, proof = self.run_observer()
        self.assertTrue(result['cas_bank_observation_verified'], proof.get('error'))
        self.assertEqual(proof['cas_bank_observe_status_poll_count'], 1)
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assertEqual(sum(row['action'] == 'cas_bank_observe' for row in proof['owner_requests']), 1)
        self.assert_no_cas_edit_commit()

    def test_schema2_status_response_loss_retries_only_observation_of_retained_uuid(self):
        self.modern_handler(observe=lambda request_id: {'ok': False, 'outcome': 'unresolved',
            'request_id': request_id, 'request_state': 'running'})
        count = [0]
        def transport(path, query, _timeout):
            if path == '/api/requests/status':
                count[0] += 1
                if count[0] == 1:
                    raise OSError('Read-only status response lost')
                return {'ok': True, 'request_id': query['request_id'], 'state': 'completed',
                        'result': self.completed_bank_observation(query['request_id'])}
        self.transport_handler = transport
        result, proof = self.run_observer()
        self.assertTrue(result['cas_bank_observation_verified'], proof.get('error'))
        self.assertEqual(count[0], 2)
        self.assertTrue(any(step['result'].get('response_lost_or_failed')
                            for step in proof['steps'] if step['action'] == 'observe-owner:cas_bank_observe'))
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assert_no_cas_edit_commit()

    def test_schema2_observation_poll_refuses_foreign_runtime_before_reading_owner_status(self):
        for field, foreign in (('pid', 43), ('test_token', '0' * 32), ('script_sha256', '0' * 64)):
            with self.subTest(field=field):
                self.setUp()
                begun = [False]
                def unresolved(request_id):
                    begun[0] = True
                    return {'ok': False, 'outcome': 'unresolved', 'request_id': request_id,
                            'request_state': 'running'}
                self.modern_handler(observe=unresolved)
                def transport(path, _query, _timeout):
                    if path == '/api/bridge' and begun[0]:
                        return dict(self.identity, **{field: foreign})
                self.transport_handler = transport
                result, proof = self.run_observer()
                self.assertFalse(result['cas_bank_observation_verified'])
                self.assertIn('changed PID/token/script', proof['error'])
                self.assertFalse(any(path == '/api/requests/status' for path, _query, _timeout in self.transport_calls))
                self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
                self.assert_no_cas_edit_commit()

    def test_schema2_terminal_failure_or_cancelled_owner_never_authorizes_bank_observation(self):
        for state in ('failed', 'cancelled'):
            with self.subTest(state=state):
                self.setUp()
                self.modern_handler(observe=lambda request_id: {'ok': False, 'outcome': 'unresolved',
                    'request_id': request_id, 'request_state': 'running'})
                def transport(path, query, _timeout):
                    if path == '/api/requests/status':
                        # Even a contradictory success body cannot upgrade a
                        # failed/cancelled outer owner state to success.
                        return {'ok': False, 'request_id': query['request_id'], 'state': state,
                                'result': self.completed_bank_observation(query['request_id'])}
                self.transport_handler = transport
                result, proof = self.run_observer()
                self.assertFalse(result['cas_bank_observation_verified'])
                self.assertFalse(proof['cas_bank_observation_receipt']['ok'])
                self.assertEqual(proof['cas_bank_observation_receipt']['request_state'], state)
                self.assertEqual(proof['cas_bank_observe_status_poll_count'], 1)
                self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
                self.assert_no_cas_edit_commit()

    def test_schema2_wrong_or_malformed_status_does_not_release_retained_owner(self):
        for case in ('wrong-row-id', 'wrong-terminal-id', 'missing-ok', 'coerced-ok', 'bad-state'):
            with self.subTest(case=case):
                self.setUp()
                self.modern_handler(observe=lambda request_id: {'ok': False, 'outcome': 'unresolved',
                    'request_id': request_id, 'request_state': 'running'})
                def transport(path, query, _timeout):
                    if path == '/api/requests/status':
                        terminal = self.completed_bank_observation(query['request_id'])
                        row = {'ok': True, 'request_id': query['request_id'], 'state': 'completed', 'result': terminal}
                        if case == 'wrong-row-id': row['request_id'] = '0' * 32
                        elif case == 'wrong-terminal-id': terminal['request_id'] = '0' * 32
                        elif case == 'missing-ok': terminal.pop('ok')
                        elif case == 'coerced-ok': terminal['ok'] = 1
                        else: row['state'] = 'done'
                        return row
                self.transport_handler = transport
                result, proof = self.run_observer()
                self.assertFalse(result['cas_bank_observation_verified'])
                self.assertIn('untyped or', proof['error'])
                self.assertTrue(cas_return.uuid_id(result['cas_bank_observe_request_id']))
                self.assertEqual(proof['cas_bank_observe_status_poll_count'], 1)
                self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
                self.assert_no_cas_edit_commit()

    def test_schema2_observation_completion_after_deadline_is_retained_without_success(self):
        self.modern_handler(observe=lambda request_id: {'ok': False, 'outcome': 'unresolved',
            'request_id': request_id, 'request_state': 'running'})
        def transport(path, query, timeout):
            if path == '/api/requests/status':
                self.assertLessEqual(timeout, 5 - self.clock)
                self.clock = 5.01
                return {'ok': True, 'request_id': query['request_id'], 'state': 'completed',
                        'result': self.completed_bank_observation(query['request_id'])}
        self.transport_handler = transport
        result, proof = self.run_observer()
        self.assertFalse(result['cas_bank_observation_verified'])
        self.assertIn('deadline expired', proof['error'])
        retained = next(step['result'] for step in proof['steps'] if step['action'] == 'observe-owner:cas_bank_observe')
        self.assertEqual(retained['state'], 'completed')
        self.assertEqual(retained['request_id'], result['cas_bank_observe_request_id'])
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assert_no_cas_edit_commit()

    def test_already_observed_or_planned_schema2_uses_status_only(self):
        # Separate fixture instances preserve one acceptance per observation.
        for phase in ('observed', 'planned'):
            with self.subTest(phase=phase):
                self.output = self.root / ('return-' + phase + '.json')
                self.calls.clear(); self.received.clear(); self.accept_id = None
                cas_ui._RECORDS.clear(); cas_ui._PEERS.clear(); self.peer = cas_ui.attach_client(SIM)
                self.modern_handler(initial=phase)
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertEqual(result['outcome'], 'live-return-explicit-cas-decisions-required')
                self.assertTrue(result['ui_transition_verified'])
                self.assertFalse(result['cas_bank_observe_attempted'])
                self.assertIsNone(result['cas_bank_observe_request_id'])
                self.assertFalse(any(action == 'cas_bank_observe' for action, _ in self.calls))
                self.assertEqual(sum(action == 'cas_session_status' for action, _ in self.calls), 1)
                self.assertEqual(proof['cas_transaction_phase'], phase)
                self.assert_no_cas_edit_commit()

    def test_schema2_recovery_or_stale_checkpoint_never_observed_or_finished(self):
        cases = [('recovery-required', {}), ('applying', {'native_write_possible': True}),
                 ('captured', {'current_runtime': False}), ('captured', {'writer_lease_present': True}),
                 ('completed', {'metadata_commit_persisted': True})]
        for index, (phase, overrides) in enumerate(cases):
            with self.subTest(phase=phase, overrides=overrides):
                self.output = self.root / ('return-refused-' + str(index) + '.json')
                self.calls.clear(); self.received.clear(); self.accept_id = None
                cas_ui._RECORDS.clear(); cas_ui._PEERS.clear(); self.peer = cas_ui.attach_client(SIM)
                self.modern_handler(initial=phase, **overrides)
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertTrue(result['ui_transition_verified'])
                self.assertTrue(result['final_paused'])
                self.assertFalse(result['cas_bank_observe_attempted'])
                self.assertEqual(result['outcome'], 'live-return-bank-unresolved')
                self.assertIn('error', proof)
                self.assert_no_cas_edit_commit()

    def test_schema2_missing_envelope_cannot_fall_back_to_legacy_finish(self):
        self.handler = lambda action, _value: {'ok': True, 'captured': True,
            'pending_schema': 2, 'pending_state': 'captured'} if action == 'cas_session_status' else None
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['ui_transition_verified'])
        self.assertFalse(result['form_bank_finish_attempted'])
        self.assertIn('checkpoint is unavailable', proof['error'])
        self.assert_no_cas_edit_commit()

    def test_schema2_observer_hash_drift_does_not_authorize_repeat_or_completion(self):
        self.modern_handler(observe=lambda original_uuid: {'ok': True,
            'expected_pending_sha256': '0' * 64, 'checkpoint_sha256': 'c' * 64,
            'raw_return_sha256': 'd' * 64, 'journal_sha256': 'f' * 64,
            'native_write_attempted': False, 'request_id': original_uuid, 'request_state': 'completed'})
        result, _proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['ui_transition_verified'])
        self.assertFalse(result['cas_bank_observation_verified'])
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assert_no_cas_edit_commit()

    def test_schema2_observer_response_from_other_uuid_is_not_accepted(self):
        self.modern_handler(observe=lambda _original_uuid: {'ok': True,
            'expected_pending_sha256': 'b' * 64, 'checkpoint_sha256': 'c' * 64,
            'raw_return_sha256': 'd' * 64, 'journal_sha256': 'f' * 64,
            'native_write_attempted': False, 'request_id': '0' * 32, 'request_state': 'completed'})
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['ui_transition_verified'])
        self.assertFalse(result['cas_bank_observation_verified'])
        self.assertNotEqual(result['cas_bank_observe_request_id'], '0' * 32)
        self.assertEqual(proof['cas_bank_observation_receipt']['request_id'], '0' * 32)
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assert_no_cas_edit_commit()

    def test_schema2_post_observation_status_hash_drift_blocks_completion_without_replay(self):
        self.modern_handler()
        base = self.handler
        calls = [0]
        def drift(action, value):
            result = base(action, value)
            if action == 'cas_session_status':
                calls[0] += 1
                if calls[0] == 2:
                    result['cas_transaction']['raw_return_sha256'] = '0' * 64
            return result
        self.handler = drift
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['ui_transition_verified'])
        self.assertFalse(result['cas_bank_observation_verified'])
        self.assertIn('journal status did not verify', proof['error'])
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.calls), 1)
        self.assert_no_cas_edit_commit()

    def test_schema2_overlay_restored_for_explicit_decisions_only_after_verified_return(self):
        self.overlay_visible = True
        self.modern_handler()
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['cas_explicit_decisions_required'])
        self.assertTrue(proof['overlay_suppression']['restored'])
        actions = [action for action, _ in self.calls]
        self.assertGreater(actions.index('overlay_show'), actions.index('cas_bank_observe'))
        self.assertGreater(actions.index('cas_bank_observe'), actions.index('test_pause'))
        self.assert_no_cas_edit_commit()

    def test_bank_finish_response_loss_preserves_live_proof_and_never_replays_finish(self):
        def handler(action, _value):
            if action == 'cas_session_finish': raise OSError('Lost after native bank reconciliation')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['ui_transition_verified'])
        self.assertTrue(result['form_bank_finish_attempted'])
        self.assertFalse(result['form_bank_completion_verified'])
        self.assertEqual(result['outcome'], 'live-return-bank-unresolved')
        self.assertEqual(sum(action == 'cas_session_finish' for action, _ in self.calls), 1)
        self.assertEqual(sum(action == 'test_pause' for action, _ in self.calls), 1)
        self.assertEqual(proof['owner_requests'][-1]['action'], 'cas_session_finish')

    def test_bank_still_pending_cannot_be_reported_as_completed(self):
        def handler(action, _value):
            if action == 'cas_session_status' and self.legacy_finished:
                return {'ok': True, 'captured': True, 'bank_lanes': ['1'], 'active_lane': '1',
                        'pending_state': 'recovery-required', 'switch_pending': False}
        self.handler = handler
        result, _ = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['ui_transition_verified'])
        self.assertFalse(result['form_bank_completion_verified'])
        self.assertEqual(sum(action == 'cas_session_finish' for action, _ in self.calls), 1)

    def test_missing_pending_unknown_or_malformed_legacy_schema_never_finishes(self):
        for overrides in ({'pending_state': None, 'pending_schema': None},
                          {'pending_schema': 3}, {'pending_schema': '1'},
                          {'pending_schema': True}, {'pending_state': 'recovery-required'},
                          {'switch_pending': True}, {'captured': False}):
            with self.subTest(overrides=overrides):
                self.setUp()
                def handler(action, _value):
                    if action == 'cas_session_status':
                        bank = {'ok': True, 'captured': True, 'pending_schema': 1,
                                'pending_state': 'captured', 'switch_pending': False}
                        bank.update(overrides)
                        return bank
                self.handler = handler
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertTrue(result['ui_transition_verified'])
                self.assertTrue(result['clock_progress_verified'])
                self.assertTrue(result['final_paused'])
                self.assertEqual(result['outcome'], 'live-return-bank-unresolved')
                self.assertFalse(proof['form_bank_finish_attempted'])
                self.assert_no_cas_edit_commit()

    def test_actual_old_runtime_captured_pending_without_schema_keeps_one_legacy_finish(self):
        def handler(action, _value):
            if action == 'cas_session_status':
                return {'ok': True, 'captured': True, 'active_lane': '1', 'bank_lanes': ['1'],
                        'pending_state': None if self.legacy_finished else 'captured', 'switch_pending': False}
        self.handler = handler
        result, proof = self.run_observer()
        self.assertTrue(result['ok'], proof.get('error'))
        self.assertEqual(sum(action == 'cas_session_finish' for action, _ in self.calls), 1)
        self.assertFalse(result['cas_bank_observe_attempted'])
        self.assertTrue(result['form_bank_completion_verified'])

    def test_visible_f11_is_hidden_before_first_native_request_and_restored_only_after_live_metadata(self):
        self.overlay_visible = True
        result, proof = self.run_observer()
        self.assertTrue(result['ok'], proof.get('error'))
        actions = [action for action, _ in self.calls]
        self.assertLess(actions.index('overlay_hide'), actions.index('cas_ui_request'))
        self.assertGreater(actions.index('overlay_show'), max(index for index, action in enumerate(actions)
                          if action == 'test_cas_return_observed'))
        self.assertEqual(actions.count('overlay_hide'), 1)
        self.assertEqual(actions.count('overlay_show'), 1)
        self.assertTrue(proof['overlay_suppression']['restored'])

    def test_unresolved_accept_leaves_initially_visible_f11_hidden_without_restore(self):
        self.overlay_visible = True
        self.detach = False
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(self.overlay_visible)
        self.assertFalse(any(action == 'overlay_show' for action, _ in self.calls))
        self.assertEqual(proof['overlay_suppression']['outcome'], 'left-hidden-unresolved')

    def test_intent_without_peer_disappearance_never_claims_live_or_unpauses(self):
        self.detach = False
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['accept_intent_observed'])
        self.assertFalse(proof['live_context_verified'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))
        self.assertEqual(cas_ui.result(self.accept_id)['cas_request_state'], 'accept-intent')

    def test_native_failure_before_commit_retains_exact_error_and_does_not_claim_an_attempt(self):
        self.detach = False
        native_error = 'ReferenceError: Error #1069: Property olympus not found'
        def handler(action, value):
            if action == 'cas_ui_result' and value == self.accept_id and value in self.received:
                reply = {'ok': False, 'protocol': 1, 'operation': 'accept', 'cas_request_id': value,
                         'lifecycle_stage': 'accept-result', 'commit_attempted': False,
                         'commit_submitted': False, 'ui_transition_verified': False, 'message': native_error}
                cas_ui.receive_socket(self.peer, value, json.dumps(reply))
                return cas_ui.result(value)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'accept-rejected')
        self.assertEqual(result['native_commit_outcome'], 'not-attempted')
        self.assertIn(native_error, proof['error'])
        self.assertIn('before SaveAndExitCAS', proof['error'])
        self.assertFalse(proof['native_failure_receipt']['commit_attempted'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))
        self.assertEqual(sum(action == 'cas_ui_request' and json.loads(value)['operation'] == 'accept'
                             for action, value in self.calls), 1)

    def test_native_false_after_one_attempt_is_distinct_from_precommit_failure(self):
        self.detach = False
        def handler(action, value):
            if action == 'cas_ui_result' and value == self.accept_id and value in self.received:
                reply = {'ok': False, 'protocol': 1, 'operation': 'accept', 'cas_request_id': value,
                         'lifecycle_stage': 'accept-result', 'commit_attempted': True, 'commit_accepted': False,
                         'commit_submitted': False, 'ui_transition_verified': False, 'message': 'native false'}
                cas_ui.receive_socket(self.peer, value, json.dumps(reply))
                return cas_ui.result(value)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertEqual(result['native_commit_outcome'], 'rejected')
        self.assertTrue(proof['native_failure_receipt']['commit_attempted'])
        self.assertIn('returned false on its one attempt', proof['error'])
        self.assertIn('native false', proof['error'])

    def test_initial_precommit_rejection_is_also_not_attempted_without_intent_or_replay(self):
        def handler(action, value):
            if action == 'cas_ui_result' and value == self.accept_id:
                reply = {'ok': False, 'protocol': 1, 'operation': 'accept', 'cas_request_id': value,
                         'lifecycle_stage': 'accept-result', 'commit_attempted': False,
                         'commit_submitted': False, 'ui_transition_verified': False, 'message': 'mode changed'}
                cas_ui.receive_socket(self.peer, value, json.dumps(reply))
                self.received.add(value)
                return cas_ui.result(value)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertEqual(result['native_commit_outcome'], 'not-attempted')
        self.assertFalse(proof['accept_intent_observed'])
        self.assertIn('mode changed', proof['error'])

    def test_no_tick_progress_stops_and_attempts_pause_once_without_completion(self):
        self.increment = 0
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['final_paused'])
        self.assertFalse(result['clock_progress_verified'])
        self.assertEqual(sum(action == 'test_pause' for action, _ in self.calls), 1)
        self.assertFalse(result['return_metadata_completed'])
        self.assertEqual(cas_ui.result(self.accept_id)['cas_request_state'], 'accept-intent')

    def test_old_or_wrong_simulation_origin_is_not_native_live_progress(self):
        for origin in (None, 'services.game_clock_service().now()', 'game-clock', True):
            with self.subTest(origin=origin):
                snapshot = self.snapshot()
                snapshot['sim_now_ticks'] = '100000'
                if origin is None:
                    snapshot.pop('sim_time_source')
                else:
                    snapshot['sim_time_source'] = origin
                self.assertFalse(cas_return.live_snapshot(snapshot, SIM, HOUSEHOLD))

    def test_advancing_old_clock_snapshot_never_unpauses_or_completes_return(self):
        def handler(action, _value):
            if action == 'test_snapshot':
                self.ticks += 1000
                snapshot = self.snapshot()
                snapshot.pop('sim_time_source')
                return snapshot
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(result['clock_progress_verified'])
        self.assertFalse(proof['live_context_verified'])
        self.assertFalse(proof['return_metadata_completed'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))
        self.assertFalse(any(action == 'test_cas_return_observed' for action, _ in self.calls))

    def test_producer_baseline_without_simulation_origin_is_refused_before_play(self):
        def handler(action, value):
            if action == 'test_cas_return_observed':
                args = json.loads(value)['value']
                if args['phase'] == 'baseline':
                    result = cas_ui.observe_return(args['cas_request_id'], self.snapshot(), 'baseline', HOUSEHOLD,
                                                  args['minimum_ticks'])
                    result['baseline'].pop('sim_time_source')
                    return result
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(proof['clock_progress_verified'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))
        self.assertIn('timeline origin', proof['error'])

    def test_final_metadata_with_game_clock_origin_never_claims_completed_return(self):
        def handler(action, value):
            if action == 'test_cas_return_observed':
                args = json.loads(value)['value']
                if args['phase'] == 'complete':
                    result = cas_ui.observe_return(args['cas_request_id'], self.snapshot(), 'complete', HOUSEHOLD,
                                                  args['minimum_ticks'])
                    result['final']['sim_time_source'] = 'services.game_clock_service().now()'
                    return result
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(proof['clock_progress_verified'])
        self.assertTrue(proof['final_paused'])
        self.assertFalse(proof['return_metadata_completed'])
        self.assertFalse(result['ui_transition_verified'])
        self.assertFalse(any(action == 'cas_session_finish' for action, _ in self.calls))

    def test_wrong_household_refuses_before_accept(self):
        original = native_client
        def handler(action, value):
            if action == 'cas_ui_result':
                client = original()
                client['sim']['householdId'] = '7'
                reply = {'ok': True, 'protocol': 1, 'cas_request_id': value, 'client': client}
                cas_ui.receive_socket(self.peer, value, json.dumps(reply))
                self.received.add(value)
                return cas_ui.result(value)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['accept_submitted'])
        self.assertIn('Requested household differs', proof['error'])

    def test_alternate_occult_layer_preflight_refuses_before_accept_submission(self):
        def handler(action, value):
            if action == 'cas_ui_result':
                client = native_client()
                client['sim']['occultLayer'] = 1
                client['sim']['occultType'] = 64
                cas_ui.receive_socket(self.peer, value, json.dumps({
                    'ok': True, 'protocol': 1, 'cas_request_id': value, 'client': client}))
                self.received.add(value)
                return cas_ui.result(value)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(result['accept_submitted'])
        self.assertFalse(proof['accept_submission_attempted'])
        self.assertIn('primary occult layer 0', proof['error'])
        operations = [json.loads(value)['operation'] for action, value in self.calls if action == 'cas_ui_request']
        self.assertEqual(operations, ['status'])
        self.assertIsNone(self.accept_id)
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))

    def test_layer_change_after_preflight_refuses_owner_ack_before_commit_is_armed(self):
        def handler(action, value):
            if action == 'cas_ui_result' and value == self.accept_id:
                client = native_client()
                client['sim']['occultLayer'] = 1
                cas_ui.receive_socket(self.peer, value, json.dumps({
                    'ok': True, 'protocol': 1, 'cas_request_id': value, 'client': client,
                    'lifecycle_stage': 'accept-intent', 'commit_attempted': False,
                    'commit_submitted': False}))
                self.fail('An alternate occult layer must never reach an owner ACK.')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['accept_submitted'])
        self.assertFalse(result['accept_intent_observed'])
        self.assertIn('primary occult layer 0', proof['error'])
        self.assertEqual(cas_ui._RECORDS[self.accept_id]['state'], 'pending')
        self.assertIsNone(cas_ui._RECORDS[self.accept_id]['result'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))

    def test_household_change_after_preflight_refuses_owner_ack_before_commit_is_armed(self):
        def handler(action, value):
            if action == 'cas_ui_result' and value == self.accept_id:
                client = native_client(); client['sim']['householdId'] = '9'
                cas_ui.receive_socket(self.peer, value, json.dumps({
                    'ok': True, 'protocol': 1, 'cas_request_id': value, 'client': client,
                    'lifecycle_stage': 'accept-intent', 'commit_attempted': False,
                    'commit_submitted': False}))
                self.fail('Mismatched household must never reach an owner ACK.')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['accept_submitted'])
        self.assertFalse(result['accept_intent_observed'])
        self.assertIn('bound original request', proof['error'])
        self.assertEqual(cas_ui._RECORDS[self.accept_id]['state'], 'pending')
        self.assertIsNone(cas_ui._RECORDS[self.accept_id]['result'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))

    def test_cached_bridge_and_instanced_sim_without_running_zone_are_insufficient(self):
        def handler(action, _value):
            if action == 'test_snapshot':
                return dict(self.snapshot(), zone_running=False)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(result['live_context_verified'])
        self.assertFalse(any(action == 'test_play' for action, _ in self.calls))

    def test_unknown_accept_response_retains_owner_uuid_and_never_repeats(self):
        def handler(action, value):
            if action == 'cas_ui_request' and json.loads(value)['operation'] == 'accept':
                cas_ui.submit(SIM, {'operation': 'accept'})  # Emulate delivery before response loss.
                raise OSError('response lost')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertIsNone(result['cas_request_id'])
        requests = [row for row in proof['owner_requests'] if row['action'] == 'cas_ui_request']
        self.assertEqual(len(requests), 2)  # One preflight, one acceptance; no replay.
        self.assertTrue(cas_return.uuid_id(requests[-1]['request_id']))

    def test_complete_metadata_response_loss_keeps_verified_live_and_owner_uuid_without_retry(self):
        def handler(action, value):
            if action == 'test_cas_return_observed':
                args = json.loads(value)['value']
                if args['phase'] == 'complete':
                    cas_ui.observe_return(args['cas_request_id'], self.snapshot(), 'complete', HOUSEHOLD, args['minimum_ticks'])
                    raise OSError('metadata response lost')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['clock_progress_verified'])
        self.assertTrue(result['final_paused'])
        self.assertFalse(result['return_metadata_completed'])
        self.assertEqual(sum(action == 'test_cas_return_observed' and json.loads(value)['value']['phase'] == 'complete'
                             for action, value in self.calls), 1)
        self.assertTrue(cas_ui.result(self.accept_id)['live_return_verified'])

    def test_new_crash_preserved_only_externally_and_process_exit_is_not_live_success(self):
        raw = b'<root><type>crash</type><categoryid>new-cas-crash</categoryid></root>'
        def handler(action, _value):
            if action == 'cas_ui_diagnostics' and self.accept_id in self.received:
                (self.profile / 'lastCrash.txt').write_bytes(raw)  # Emulate game producer.
                self.alive = False
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'crash')
        self.assertTrue(result['process_exit_verified'])
        self.assertEqual(Path(proof['crash']['path']).read_bytes(), raw)
        self.assertEqual((self.profile / 'lastCrash.txt').read_bytes(), raw)

    def test_bridge_identity_change_stops_before_submission(self):
        def transport(path, query=None, timeout=12):
            return dict(self.identity, pid=43, ok=True) if path == '/api/bridge' else {'ok': True}
        result = cas_return.observe(self.state, self.output, self.identity, self.request, SIM, HOUSEHOLD,
                    transport=transport, alive=lambda _: True, monotonic=lambda: self.clock, pause=self.tick, seconds=5)
        self.assertFalse(result['accept_submitted'])
        self.assertFalse(result['ok'])

    def test_exact_identity_new_external_proof_and_typed_ids_refuse_before_commands(self):
        for output in (self.state, self.profile / 'proof.json', self.original / 'proof.json', self.root / 'missing/proof.json'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                cas_return.observe(self.state, output, self.identity, self.request, SIM, HOUSEHOLD)
        for identity in (dict(self.identity, pid=True), dict(self.identity, test_token='b' * 32),
                         dict(self.identity, script_sha256='b' * 64)):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                cas_return.observe(self.state, self.output, identity, self.request, SIM, HOUSEHOLD)
        for sim in (int(SIM), '0' + SIM, '0', '１'):
            with self.subTest(sim=sim), self.assertRaises(ValueError):
                cas_return.observe(self.state, self.output, self.identity, self.request, sim, HOUSEHOLD)
        self.assertFalse(self.calls)
        self.assertFalse(self.output.exists())

    def test_cli_parser_wires_semantic_return_household_settling_and_external_evidence(self):
        args = apex_cli.parser().parse_args(['cas', 'return', '--state', 'session.json', '--sim-id', SIM,
                    '--household-id', HOUSEHOLD, '--settle-ticks', '75', '--seconds', '60', '--output', 'proof.json'])
        self.assertEqual(args.operation, 'return')
        self.assertEqual(args.household_id, HOUSEHOLD)
        self.assertEqual(args.settle_ticks, 75)


    def pause_cancellation_handler(self, cancellation=None, fresh_change=None, rebound=None):
        pauses = [0]
        def handler(action, value):
            disk = json.loads(self.output.read_text())
            if action == 'test_pause':
                pauses[0] += 1
                intent = disk['pause_observations'][-1]
                owner = intent['owner_request_id']
                self.assertTrue(cas_return.uuid_id(owner))
                if pauses[0] == 1:
                    result = {'ok': False, 'request_state': 'cancelled', 'request_id': owner,
                              'message': cas_return.ZONE_CANCELLED_BEFORE_EXECUTION}
                    return cancellation(result) if cancellation else result
                self.assertEqual(pauses[0], 2, 'No third pause submission is permitted.')
                self.assertTrue(disk['pause_rebound_attempted'])
                self.assertEqual(intent['rebound_of'], disk['pause_observations'][0]['owner_request_id'])
                if rebound:
                    return rebound(owner)
                self.speed = 0
                return dict(self.snapshot(), request_id=owner, request_state='completed')
            if action == 'test_snapshot' and pauses[0] == 1:
                snapshot = self.snapshot()
                return fresh_change(snapshot) if fresh_change else snapshot
        self.handler = handler
        return pauses

    def test_exact_unexecuted_pause_rebinds_once_after_fresh_same_live_progress(self):
        pauses = self.pause_cancellation_handler()
        result, proof = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertTrue(proof['pause_rebound_verified'])
        self.assertEqual(pauses[0], 2)
        self.assertEqual(len(proof['pause_observations']), 2)
        self.assertEqual(sum(action == 'test_play' for action, _ in self.calls), 1)
        self.assertEqual([json.loads(value)['operation'] for action, value in self.calls
                          if action == 'cas_ui_request'], ['status', 'accept'])

    def test_unexecuted_pause_observes_existing_pause_without_another_mutation(self):
        def already_paused(snapshot):
            self.speed = 0
            snapshot['clock_speed'] = 0
            return snapshot
        pauses = self.pause_cancellation_handler(fresh_change=already_paused)
        result, proof = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertTrue(proof['final_paused'])
        self.assertFalse(proof['pause_rebound_attempted'])
        self.assertEqual(pauses[0], 1)

    def test_pause_rebind_refuses_ambiguous_shape_state_owner_message_or_result(self):
        for change in ({'request_state': 'failed'}, {'request_state': 'unknown'},
                       {'request_id': 'b'*32}, {'ok': 0}, {'response_lost_or_failed': True},
                       {'message': 'Unknown execution outcome'}):
            with self.subTest(change=change):
                self.setUp()
                pauses = self.pause_cancellation_handler(cancellation=lambda r: dict(r, **change))
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertFalse(proof['pause_rebound_attempted'])
                self.assertEqual(pauses[0], 1)
                self.assertFalse(proof['return_metadata_completed'])

    def test_pause_rebind_requires_same_native_identity_ticks_and_runtime(self):
        for change in ({'zone_id': '999'}, {'client_id': '999'}, {'save_guid': '999'},
                       {'household_id': '999'}, {'sim_now_ticks': '1'},
                       {'sim_time_source': 'services.game_clock_service().now()'}):
            with self.subTest(change=change):
                self.setUp()
                pauses = self.pause_cancellation_handler(fresh_change=lambda r: dict(r, **change))
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertFalse(proof['pause_rebound_attempted'])
                self.assertEqual(pauses[0], 1)

    def test_second_pause_cancellation_or_lost_response_never_submits_a_third(self):
        for lost in (False, True):
            with self.subTest(lost=lost):
                self.setUp()
                def rebound(owner):
                    if lost:
                        raise OSError('Pause response was lost after submission.')
                    return {'ok': False, 'request_id': owner, 'request_state': 'cancelled',
                            'message': cas_return.ZONE_CANCELLED_BEFORE_EXECUTION}
                pauses = self.pause_cancellation_handler(rebound=rebound)
                result, proof = self.run_observer()
                self.assertFalse(result['ok'])
                self.assertTrue(proof['pause_rebound_attempted'])
                self.assertFalse(proof['pause_rebound_verified'])
                self.assertEqual(pauses[0], 2)
                self.assertFalse(proof['return_metadata_completed'])


if __name__ == '__main__':
    unittest.main()
