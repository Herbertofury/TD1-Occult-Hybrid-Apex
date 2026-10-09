import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
from apex_core import cas_ui
import apex_cli
import cas_transition


SIM_ID = '772674414928396571'


def client(sim_id=SIM_ID):
    return {'scope': 'native-cas-client', 'sim': {'simId': sim_id, 'future_field': {'raw': 'preserved'}},
            'menu_state': cas_ui.PANELS['clothing_hair'], 'panel_visible': True,
            'outfit': {'outfit_type': 0, 'outfit_index': 1},
            'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                          'preset': None, 'preset_query': 'returned-null'}
                         for name, state in cas_ui.PANELS.items()]}


def diagnostic(sim_id=SIM_ID, age=.2):
    return {'ok': True, 'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021,
                                           'native_connection_verified': True},
            'native_peers': [{'sim_id': sim_id, 'age_seconds': age}]}


class CasTransitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / cas_transition.reusable_profile.PROTECTED_NAME
        (self.profile / 'Mods/Apex').mkdir(parents=True)
        (self.original / 'saves').mkdir(parents=True)
        (self.original / 'Mods').mkdir()
        (self.original / 'saves/Slot_00000002.save').write_bytes(b'owner save must remain untouched')
        (self.original / 'Mods/owner.package').write_bytes(b'owner mods must remain untouched')
        (self.original / 'lastCrash.txt').write_bytes(b'owner original crash must remain untouched')
        self.token = 'a' * 32
        marker = self.profile / cas_transition.reusable_profile.legacy.MARKER
        marker.write_text(json.dumps({'token': self.token}), encoding='utf-8')
        script = self.profile / 'Mods/Apex/ApexOccultHybrid.ts4script'
        script.write_bytes(b'test exact script')
        self.digest = hashlib.sha256(script.read_bytes()).hexdigest()
        self.state = self.root / 'session.json'
        self.journal = {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active', 'token': self.token,
                        'profile': str(self.profile), 'protected_original': str(self.original),
                        'artifacts': [{'name': script.name, 'relative': 'Apex/' + script.name, 'sha256': self.digest}]}
        self.state.write_text(json.dumps(self.journal), encoding='utf-8')
        self.identity = {'pid': 42, 'test_token': self.token, 'script_sha256': self.digest}
        self.output = self.root / 'proof.json'
        self.clock = 0
        self.alive = True
        self.calls = []
        self.entry = {'ok': True, 'request_id': 'e' * 32, 'request_state': 'completed'}
        self.diagnostics = diagnostic()
        self.inventory = {'ok': True, 'cas_request_id': 'c' * 32, 'ui_transition_verified': True,
                          'client': client(), 'cas_request_state': 'completed'}
        self.handler = None

    def tree(self, path):
        return {str(item.relative_to(path)): item.read_bytes() for item in path.rglob('*') if item.is_file()}

    def request(self, state, action, sim_id=None, **kwargs):
        self.calls.append((action, {'sim_id': sim_id, **kwargs}))
        self.clock += .01
        if self.handler is not None:
            override = self.handler(action, kwargs)
            if override is not None:
                return override
        if action == 'test_cas':
            return copy.deepcopy(self.entry)
        if action == 'cas_ui_diagnostics':
            return copy.deepcopy(self.diagnostics)
        if action == 'cas_ui_request':
            return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': 'c' * 32}
        if action == 'cas_ui_result':
            return copy.deepcopy(self.inventory)
        self.fail('Unexpected action: ' + action)

    def pause(self, seconds):
        self.clock += seconds

    def pending_entry_transport(self, state='running', result=None, finish_at=None, initial_delay=0,
                                lost_submission=False, override=None):
        self.transport_calls = []
        request_id = 'e' * 32
        def transport(path, query=None, timeout=12):
            self.assertGreater(timeout, 0)
            self.transport_calls.append((path, copy.deepcopy(query), timeout))
            self.clock += .01
            if path == '/api/command':
                self.assertEqual(query['action'], 'test_cas')
                self.assertEqual(query['request_id'], request_id)
                self.clock += initial_delay
                if lost_submission:
                    raise OSError('Initial entry response lost after native submission')
                return {'ok': False, 'outcome': 'unresolved', 'request_id': request_id}
            if path == '/api/bridge':
                return copy.deepcopy(self.identity)
            self.assertEqual(path, '/api/requests/status')
            self.assertEqual(query, {'request_id': request_id})
            persisted = json.loads(self.output.read_text(encoding='utf-8'))
            self.assertEqual(persisted['entry_request_id'], request_id)
            self.assertEqual(persisted['owner_requests'], [{'action': 'test_cas', 'request_id': request_id}])
            if override is not None:
                return override(path, query)
            ready = finish_at is not None and self.clock >= finish_at
            return {'ok': True, 'request_id': request_id, 'state': 'completed' if ready else state,
                    'result': {'ok': True} if ready else copy.deepcopy(result)}
        def handler(action, kwargs):
            if action == 'test_cas':
                return kwargs['transport']('/api/command', {'action': 'test_cas', 'request_id': request_id})
        self.handler = handler
        return transport

    def run_observer(self, seconds=1, **kwargs):
        original_before, active_before = self.tree(self.original), self.tree(self.profile)
        result = cas_transition.observe(self.state, self.output, self.identity, self.request, SIM_ID,
                seconds=seconds, processes=lambda: [{'Id': 42}] if self.alive else [],
                monotonic=lambda: self.clock, pause=self.pause, **kwargs)
        self.assertEqual(self.tree(self.original), original_before)
        self.assertEqual(self.state.read_text(encoding='utf-8'), json.dumps(self.journal))
        if self.handler is None:
            self.assertEqual(self.tree(self.profile), active_before)
        proof = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(sum(action == 'test_cas' for action, _ in self.calls), 1 if proof['entry_submitted'] else 0)
        self.assertLessEqual(sum(action == 'cas_ui_request' for action, _ in self.calls), 1)
        self.assertTrue(all(action in ('test_cas', 'cas_ui_diagnostics', 'cas_ui_request', 'cas_ui_result')
                            for action, _ in self.calls))
        return result, proof

    def test_success_has_one_entry_then_exact_handshake_then_one_complete_inventory(self):
        result, proof = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertEqual(result['outcome'], 'inventory')
        self.assertEqual([action for action, _ in self.calls],
                         ['test_cas', 'cas_ui_diagnostics', 'cas_ui_request', 'cas_ui_result'])
        self.assertEqual(json.loads(self.calls[0][1]['value']), {'test_token': self.token, 'value': None})
        self.assertEqual(json.loads(self.calls[2][1]['value']), {'operation': 'status'})
        self.assertEqual(proof['inventory_result']['client']['sim']['future_field'], {'raw': 'preserved'})
        self.assertEqual(proof['identity'], self.identity)
        self.assertEqual(proof['inputs'], self.journal['artifacts'])
        self.assertEqual(proof['journal'], str(self.state))
        self.assertEqual(len(proof['inventory_result']['client']['catalogs']), len(cas_ui.PANELS))

    def test_wrong_sim_peer_cannot_trigger_native_snapshot_even_when_global_connected(self):
        self.diagnostics = diagnostic('12')
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(proof['handshake_verified'])
        self.assertEqual(proof['last_verified_stage'], 'entry-submitted')
        self.assertFalse(any(action == 'cas_ui_request' for action, _ in self.calls))
        self.assertLessEqual(result['elapsed_seconds'], 1.05)

    def test_no_peer_never_falls_back_to_distributor_or_input(self):
        self.diagnostics['native_peers'] = []
        result, proof = self.run_observer()
        self.assertEqual(result['outcome'], 'unresolved')
        self.assertFalse(proof['inventory_verified'])
        self.assertFalse(any(action == 'cas_ui_request' for action, _ in self.calls))

    def test_peer_freshness_requires_exact_typed_finite_age_and_bound_local_transport(self):
        for age in (-.01, 3.01, True, '0', float('nan'), float('inf')):
            with self.subTest(age=age):
                self.assertFalse(cas_transition.fresh_peer(diagnostic(age=age), SIM_ID))
        for change in ({'bound': False}, {'host': 'example.invalid'}, {'port': '8021'}):
            item = diagnostic()
            item['socket_transport'].update(change)
            self.assertFalse(cas_transition.fresh_peer(item, SIM_ID))
        self.assertTrue(cas_transition.fresh_peer(diagnostic(age=3), SIM_ID))

    def test_lost_entry_response_is_retained_without_replay(self):
        def handler(action, _kwargs):
            if action == 'test_cas':
                raise OSError('Response lost after entry may have been accepted')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertEqual(result['outcome'], 'unresolved')
        self.assertTrue(proof['entry_submitted'])
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(proof['steps'][0]['result']['response_lost_or_failed'])

    def test_unresolved_entry_preserves_owner_request_id_without_second_submission(self):
        self.entry = {'ok': False, 'outcome': 'unresolved', 'request_id': 'e' * 32}
        result, proof = self.run_observer()
        self.assertEqual(result['outcome'], 'unresolved')
        self.assertEqual(proof['steps'][0]['result']['request_id'], 'e' * 32)
        self.assertEqual(len(self.calls), 1)

    def test_initial_entry_longer_than_short_poll_completes_with_same_uuid_within_whole_deadline(self):
        transport = self.pending_entry_transport(finish_at=3.5, initial_delay=2.1)
        result, proof = self.run_observer(seconds=5, transport=transport)
        self.assertTrue(result['ok'])
        self.assertTrue(proof['entry_accepted'])
        self.assertEqual(proof['entry_request_id'], 'e' * 32)
        self.assertGreater(proof['entry_status_poll_count'], 1)
        self.assertGreaterEqual(result['elapsed_seconds'], 3.5)
        self.assertLess(result['elapsed_seconds'], 5)
        self.assertEqual(sum(path == '/api/command' for path, _, _ in self.transport_calls), 1)
        self.assertEqual({query['request_id'] for path, query, _ in self.transport_calls
                          if path == '/api/requests/status'}, {'e' * 32})
        self.assertEqual(self.calls[0][1]['seconds'], 2)
        self.assertEqual([action for action, _ in self.calls],
                         ['test_cas', 'cas_ui_diagnostics', 'cas_ui_request', 'cas_ui_result'])

    def test_lost_initial_response_recovers_only_same_predetermined_uuid(self):
        transport = self.pending_entry_transport(finish_at=.3, lost_submission=True)
        result, proof = self.run_observer(transport=transport)
        self.assertTrue(result['ok'])
        self.assertTrue(proof['steps'][0]['result']['response_lost_or_failed'])
        self.assertEqual(proof['entry_request_id'], 'e' * 32)
        self.assertEqual(sum(path == '/api/command' for path, _, _ in self.transport_calls), 1)
        self.assertGreater(proof['entry_status_poll_count'], 1)

    def test_unknown_initial_entry_uses_whole_deadline_retains_uuid_and_never_enters_inventory(self):
        transport = self.pending_entry_transport(state='unknown')
        result, proof = self.run_observer(seconds=.6, transport=transport)
        self.assertFalse(result['ok'])
        self.assertEqual(proof['outcome'], 'unresolved')
        self.assertEqual(proof['entry_request_id'], 'e' * 32)
        self.assertGreaterEqual(result['elapsed_seconds'], .6)
        self.assertLessEqual(result['elapsed_seconds'], .6)
        self.assertFalse(proof['entry_accepted'])
        self.assertEqual([action for action, _ in self.calls], ['test_cas'])
        self.assertEqual(sum(path == '/api/command' for path, _, _ in self.transport_calls), 1)

    def test_failed_and_cancelled_initial_entries_are_terminal_without_another_submission(self):
        for state in ('failed', 'cancelled'):
            with self.subTest(state=state):
                self.clock = 0; self.calls.clear()
                if self.output.exists(): self.output.unlink()
                transport = self.pending_entry_transport(state=state, result={'ok': False, 'message': 'Native refusal'})
                result, proof = self.run_observer(transport=transport)
                self.assertEqual(result['outcome'], 'entry-rejected')
                self.assertFalse(proof['entry_accepted'])
                self.assertEqual(proof['steps'][-1]['result']['request_state'], state)
                self.assertEqual(self.calls[0][0], 'test_cas')
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(sum(path == '/api/command' for path, _, _ in self.transport_calls), 1)

    def test_wrong_uuid_or_untyped_terminal_result_cannot_claim_initial_entry_completion(self):
        rows = ({'state': 'completed', 'request_id': 'd' * 32, 'result': {'ok': True}},
                {'state': 'completed', 'request_id': 'e' * 32, 'result': {'ok': 1}},
                {'state': 'completed', 'request_id': 'e' * 32, 'result': None},
                {'state': 'completed', 'request_id': 'e' * 32, 'result': {'ok': True, 'request_id': 'd' * 32}},
                {'state': 'unrecognised', 'request_id': 'e' * 32})
        for row in rows:
            with self.subTest(row=row):
                self.clock = 0; self.calls.clear()
                if self.output.exists(): self.output.unlink()
                transport = self.pending_entry_transport(override=lambda _p, _q: copy.deepcopy(row))
                result, proof = self.run_observer(transport=transport)
                self.assertFalse(result['ok'])
                self.assertFalse(proof['entry_accepted'])
                self.assertEqual(proof['outcome'], 'unresolved')
                self.assertEqual(proof['entry_request_id'], 'e' * 32)
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(sum(path == '/api/command' for path, _, _ in self.transport_calls), 1)

    def test_changed_bridge_identity_stops_before_original_entry_status_poll(self):
        base_transport = self.pending_entry_transport(finish_at=.1)
        def transport(path, query=None, timeout=12):
            result = base_transport(path, query, timeout=timeout)
            return dict(result, pid=43) if path == '/api/bridge' else result
        result, proof = self.run_observer(transport=transport)
        self.assertFalse(result['ok'])
        self.assertIn('pinned PID/token/script', proof['error'])
        self.assertFalse(any(path == '/api/requests/status' for path, _, _ in self.transport_calls))
        self.assertEqual(len(self.calls), 1)

    def test_lost_status_read_can_recover_without_entry_replay(self):
        reads = [0]
        def override(_path, _query):
            reads[0] += 1
            if reads[0] == 1:
                raise OSError('One read-only status response was lost')
            return {'state': 'completed', 'request_id': 'e' * 32, 'result': {'ok': True}}
        transport = self.pending_entry_transport(override=override)
        result, proof = self.run_observer(transport=transport)
        self.assertTrue(result['ok'])
        self.assertEqual(reads[0], 2)
        self.assertEqual(sum(path == '/api/command' for path, _, _ in self.transport_calls), 1)
        lost = [row for row in proof['steps'] if row['action'] == 'test_cas_status' and
                row['result'].get('response_lost_or_failed')]
        self.assertEqual(len(lost), 1)
        self.assertEqual(lost[0]['result']['request_id'], 'e' * 32)

    def test_process_exit_during_initial_completion_stops_reads_without_replay(self):
        def override(_path, _query):
            self.alive = False
            return {'state': 'running', 'request_id': 'e' * 32, 'result': None}
        transport = self.pending_entry_transport(override=override)
        result, proof = self.run_observer(transport=transport)
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'process-exited')
        self.assertTrue(proof['process_exit_verified'])
        self.assertFalse(proof['entry_accepted'])
        self.assertEqual(proof['entry_request_id'], 'e' * 32)
        self.assertEqual(proof['entry_status_poll_count'], 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(sum(path == '/api/command' for path, _, _ in self.transport_calls), 1)

    def test_lost_native_ack_only_polls_same_id_under_overall_deadline(self):
        self.inventory = {'ok': False, 'outcome': 'pending-client', 'cas_request_id': 'c' * 32}
        result, proof = self.run_observer(seconds=.5)
        self.assertFalse(result['ok'])
        self.assertTrue(result['handshake_verified'])
        self.assertEqual(proof['inventory_result']['cas_request_id'], 'c' * 32)
        self.assertTrue(all(row['value'] == 'c' * 32 for action, row in self.calls if action == 'cas_ui_result'))
        self.assertLessEqual(result['elapsed_seconds'], .5)
        self.assertEqual(proof['cas_request_id'], 'c' * 32)

    def test_ack_for_a_different_request_is_not_accepted_or_resubmitted(self):
        self.inventory['cas_request_id'] = 'd' * 32
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(proof['inventory_verified'])
        self.assertIn('different request identity', proof['error'])
        self.assertEqual(proof['cas_request_id'], 'c' * 32)

    def test_wrong_sim_readback_and_partial_catalogs_cannot_claim_inventory(self):
        self.inventory['client'] = client('12')
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertFalse(proof['inventory_verified'])
        self.assertIn('another selected Sim', proof['error'])
        self.output.unlink()
        self.calls.clear()
        self.inventory['client'] = client()
        self.inventory['client']['catalogs'].pop()
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertIn('every mapped panel', proof['error'])

    def test_process_exit_after_ack_does_not_claim_success(self):
        def handler(action, _kwargs):
            if action == 'cas_ui_result':
                self.alive = False
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['process_exit_verified'])
        self.assertEqual(result['outcome'], 'process-exited')
        self.assertFalse(proof['inventory_verified'])

    def test_crash_is_read_only_bounded_content_addressed_and_metadata_is_minimal(self):
        old = b'<root><type>crash</type><categoryid>prior</categoryid></root>'
        (self.profile / 'lastCrash.txt').write_bytes(old)
        crash = b'<root><report><type>crash</type><categoryid>new</categoryid><memdumptxt>private bytes</memdumptxt></report></root>'
        def handler(action, _kwargs):
            if action == 'test_cas':
                (self.profile / 'lastCrash.txt').write_bytes(crash)  # Emulate game, never observer.
                self.alive = False
        self.handler = handler
        result, proof = self.run_observer()
        self.assertEqual(result['outcome'], 'crash')
        digest = hashlib.sha256(crash).hexdigest()
        target = self.output.with_name('proof-crash-' + digest + '.xml')
        self.assertEqual(target.read_bytes(), crash)
        self.assertEqual((self.profile / 'lastCrash.txt').read_bytes(), crash)
        self.assertEqual(proof['crash']['metadata'], {'type': 'crash', 'categoryid': 'new'})
        self.assertNotIn('private bytes', self.output.read_text(encoding='utf-8'))
        self.assertEqual(proof['crash']['after']['sha256'], digest)

    def test_prior_crash_is_not_mislabeled_as_new(self):
        (self.profile / 'lastCrash.txt').write_bytes(b'<root><type>crash</type></root>')
        self.entry = {'ok': False, 'outcome': 'unresolved', 'request_id': 'e' * 32}
        result, proof = self.run_observer()
        self.assertEqual(result['outcome'], 'unresolved')
        self.assertFalse(proof['crash']['preserved'])
        self.assertFalse(list(self.root.glob('*-crash-*.xml')))

    def test_crash_dtd_entities_non_utf8_and_oversize_are_refused_before_copy(self):
        for raw in (b'<!DOCTYPE root [<!ENTITY x "bad">]><root>&x;</root>',
                    '<root/>'.encode('utf-16'), b'x' * (cas_transition.MAX_CRASH_BYTES + 1)):
            with self.subTest(bytes=len(raw)):
                (self.profile / 'lastCrash.txt').write_bytes(raw)
                outcome = cas_transition.preserve_crash(self.profile, self.output, {'state': 'absent'})
                self.assertFalse(outcome['preserved'])
                self.assertFalse(list(self.root.glob('*-crash-*.xml')))

    def test_missing_process_stops_before_entry_and_does_not_copy_old_crash(self):
        self.alive = False
        result, proof = self.run_observer()
        self.assertFalse(result['entry_submitted'])
        self.assertEqual(result['outcome'], 'process-exited')
        self.assertEqual(self.calls, [])

    def test_external_output_and_exact_identity_are_validated_before_any_action(self):
        for target in (self.profile / 'proof.json', self.original / 'proof.json', self.state,
                       self.root / 'missing/proof.json'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                cas_transition.observe(self.state, target, self.identity, self.request, SIM_ID)
        for change in ({'pid': True}, {'test_token': 'f' * 32}, {'script_sha256': 'f' * 64}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'identity'):
                cas_transition.observe(self.state, self.output, dict(self.identity, **change), self.request, SIM_ID)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())

    def test_exact_sim_and_sixty_second_limit_reject_before_action(self):
        for sim_id in (None, 12, '012', '１２', str(1 << 64)):
            with self.subTest(sim_id=sim_id), self.assertRaises(ValueError):
                cas_transition.observe(self.state, self.output, self.identity, self.request, sim_id)
        for seconds in (0, 61, True, float('nan'), float('inf')):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                cas_transition.observe(self.state, self.output, self.identity, self.request, SIM_ID, seconds=seconds)
        self.assertEqual(self.calls, [])

    def test_http_transport_shares_remaining_budget_instead_of_nesting_waits(self):
        observed_timeouts = []
        def transport(_path, _query=None, timeout=12):
            observed_timeouts.append(timeout)
            self.clock += timeout
            raise TimeoutError('bounded HTTP response timeout')
        def handler(_action, kwargs):
            kwargs['transport']('/api/command', {'action': 'test_cas', 'request_id': 'e' * 32})
        self.handler = handler
        result, proof = self.run_observer(seconds=.5, transport=transport)
        self.assertEqual(observed_timeouts, [.49])
        self.assertLessEqual(result['elapsed_seconds'], .5)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(proof['outcome'], 'unresolved')
        self.assertEqual(proof['owner_requests'], [{'action': 'test_cas', 'request_id': 'e' * 32}])

    def test_cli_output_route_uses_observer_and_low_level_route_is_compatible(self):
        args = apex_cli.parser().parse_args(['game', 'cas', '--state', str(self.state), '--sim-id', SIM_ID,
                                           '--output', str(self.output), '--seconds', '4'])
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity', return_value=self.identity), \
                patch.object(cas_transition, 'observe', return_value={'ok': True}) as observer, \
                patch.object(apex_cli, 'owned_request') as request:
            self.assertTrue(apex_cli.execute(args)['ok'])
            request.assert_not_called()
            self.assertEqual(observer.call_args.kwargs['seconds'], 4)
            self.assertEqual(observer.call_args.kwargs['sim_id'], SIM_ID)
            self.assertIs(observer.call_args.kwargs['transport'], apex_cli.get)
        args.output = None
        with patch.object(apex_cli, 'require_isolated'), patch.object(cas_transition, 'observe') as observer, \
                patch.object(apex_cli, 'owned_request', return_value={'ok': True}) as request:
            self.assertTrue(apex_cli.execute(args)['ok'])
            self.assertEqual(request.call_args.args[1], 'test_cas')
            observer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
