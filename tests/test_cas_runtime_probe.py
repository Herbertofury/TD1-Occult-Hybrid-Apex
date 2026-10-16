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
import cas_runtime_probe as probe
import reusable_profile
import test_profile
from source_manifest import write_json

SIM = '772674414928396571'
ORIGINAL = '414264'
ALTERNATE = '414266'


class CasRuntimeProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / reusable_profile.PROTECTED_NAME
        (self.profile / 'Mods/Apex').mkdir(parents=True)
        (self.profile / 'saves').mkdir()
        (self.original / 'saves').mkdir(parents=True)
        (self.original / 'Mods').mkdir()
        (self.profile / 'saves/test.save').write_bytes(b'test save stays untouched')
        (self.original / 'saves/original.save').write_bytes(b'protected original save')
        (self.original / 'Mods/owner.package').write_bytes(b'protected original mod')
        write_json(self.profile / test_profile.MARKER, {'token': 'a' * 32})
        script = self.profile / 'Mods/Apex/ApexOccultHybrid.ts4script'
        script.write_bytes(b'test script')
        digest = hashlib.sha256(script.read_bytes()).hexdigest()
        self.state, self.output = self.root / 'state.json', self.root / 'proof.json'
        self.identity = {'pid': 42, 'test_token': 'a' * 32, 'script_sha256': digest}
        write_json(self.state, {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active', 'generation': 1,
             'token': 'a' * 32, 'profile': str(self.profile), 'protected_original': str(self.original),
             'artifacts': [{'name': script.name, 'relative': 'Apex/' + script.name, 'sha256': digest}]})
        self.clock = 0
        self.alive = True
        self.calls, self.submitted, self.pending = [], [], {}
        self.current = (0, 0)
        self.hair = {(0, 0): ORIGINAL}
        self.history, self.redo = [], []
        self.inventory = {category: {'category': category, 'query': 'returned-value', 'supported': True,
           'data': {'max_outfits': 5, 'outfit_list': [{'outfit_type': category, 'outfit_index': 0}]}}
           for category in range(14)}
        self.diagnostic = {'ok': True, 'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021},
                           'native_peers': [{'sim_id': SIM, 'age_seconds': .1}], 'requests': []}
        self.overlay_visible = False
        self.overlay_started = True
        self.fault = None

    def files(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def client(self):
        return {'scope': 'native-cas-client', 'sim': {'simId': SIM, 'never_dump_raw_object': {'secret': 'private-raw-record'}},
          'menu_state': cas_ui.PANELS['clothing_hair'], 'panel_visible': True,
          'outfit': {'outfit_type': self.current[0], 'outfit_index': self.current[1]},
          'hair_selected_swatch_id': self.hair.get(self.current, ORIGINAL), 'hair_swatch_query': 'returned-value',
          'hair_swatches': [{'dataID': ALTERNATE}, {'dataID': ORIGINAL}],
          'planned_outfits': copy.deepcopy(list(self.inventory.values())),
          'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [], 'preset': None,
                        'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()]}

    def request(self, state, action, sim_id=None, **kwargs):
        self.calls.append((action, sim_id, kwargs))
        self.clock += .001
        if action == 'overlay_status':
            if not self.overlay_started:
                return {'ok': False, 'message': 'F11 sidecar has not been started.', 'request_state': 'completed'}
            return {'ok': True, 'visible': self.overlay_visible, 'request_id': 'c' * 32, 'request_state': 'completed'}
        if action in ('overlay_hide', 'overlay_show'):
            self.overlay_visible = action == 'overlay_show'
            return {'ok': True, 'visible': self.overlay_visible, 'request_id': 'd' * 32, 'request_state': 'completed'}
        if action == 'cas_ui_diagnostics':
            return self.diagnostic
        if action == 'cas_ui_request':
            operation = json.loads(kwargs['value'])
            self.submitted.append(operation)
            rid = '{:032x}'.format(len(self.submitted))
            op = operation['operation']
            created = None
            if op == 'hair-swatch':
                self.history.append(self.hair.get(self.current, ORIGINAL))
                self.hair[self.current] = operation['data_id']
                self.redo.clear()
            elif op == 'undo':
                self.redo.append(self.hair.get(self.current, ORIGINAL))
                self.hair[self.current] = self.history.pop()
            elif op == 'redo':
                self.history.append(self.hair.get(self.current, ORIGINAL))
                self.hair[self.current] = self.redo.pop()
            elif op == 'outfit':
                category, index = operation['category'], operation['index']
                actual = self.inventory[category]['data']['outfit_list']
                self.assertTrue(any(row['outfit_index'] == index for row in actual), 'No invented slot permitted')
                self.current = (category, index)
            elif op == 'outfit-add':
                category = operation['category']
                actual = self.inventory[category]['data']['outfit_list']
                before = len(actual)
                actual.append({'outfit_type': category, 'outfit_index': before})
                self.current = (category, before)
                created = {'before_count': before, 'after_count': len(actual)}
            elif op != 'status':
                self.fail('Unexpected native operation: ' + op)
            client = self.client()
            if created is not None:
                client['outfit_created'] = created
            self.pending[rid] = {'ok': True, 'protocol': 1, 'operation': op, 'cas_request_id': rid,
                                 'ui_transition_verified': True, 'cas_request_state': 'completed', 'client': client}
            if self.fault:
                replacement = self.fault(action, operation, rid, kwargs)
                if replacement is not None:
                    return replacement
            return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': rid}
        if action == 'cas_ui_result':
            rid = kwargs['value']
            operation = self.submitted[int(rid, 16) - 1]
            if self.fault:
                replacement = self.fault(action, operation, rid, kwargs)
                if replacement is not None:
                    return replacement
            return copy.deepcopy(self.pending[rid])
        self.fail('Probe must not launch, enter CAS, accept, save or use pointer input: ' + action)

    def run_probe(self, **kwargs):
        before_original, before_profile, before_state = self.files(self.original), self.files(self.profile), self.state.read_bytes()
        result = probe.run(self.state, self.output, self.identity, self.request, SIM,
                 alive=lambda _pid: self.alive, monotonic=lambda: self.clock,
                 pause=lambda seconds: setattr(self, 'clock', self.clock + seconds), **kwargs)
        self.assertEqual(self.files(self.original), before_original)
        self.assertEqual(self.state.read_bytes(), before_state)
        after_profile = self.files(self.profile)
        # A crash fixture emulates the GAME writing its report, never the runner.
        after_profile.pop('lastCrash.txt', None)
        before_profile.pop('lastCrash.txt', None)
        self.assertEqual(after_profile, before_profile)
        proof = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertTrue(proof['finalized'])
        self.assertNotIn('private-raw-record', self.output.read_text(encoding='utf-8'))
        self.assertFalse(proof['broad_cas_validation'])
        return result, proof

    def test_default_exact_history_and_all_eight_standard_categories_restore_initial_selection(self):
        result, proof = self.run_probe()
        self.assertTrue(result['ok'])
        self.assertEqual(result['outcome'], 'completed')
        operations = [row['operation'] for row in self.submitted]
        self.assertEqual(operations[:5], ['status', 'hair-swatch', 'undo', 'redo', 'undo'])
        self.assertEqual(operations[-1], 'status')
        self.assertNotIn('outfit-add', operations)
        self.assertEqual([row['category'] for row in self.submitted if row['operation'] == 'outfit'],
                         list(probe.STANDARD_CATEGORIES) + [0])
        self.assertEqual([row['observed']['hair_selected_swatch_id'] for row in proof['steps'][:5]],
                         [ORIGINAL, ALTERNATE, ORIGINAL, ALTERNATE, ORIGINAL])
        self.assertTrue(all(row['verified'] and probe.uuid_id(row['cas_request_id']) for row in proof['steps']))
        self.assertTrue(proof['final_status_observed'])
        self.assertTrue(proof['baseline_hair_restored'])
        self.assertTrue(proof['baseline_outfit_restored'])
        self.assertEqual(self.current, (0, 0))
        self.assertTrue(all(row['elapsed_seconds'] >= 0 for row in proof['steps']))

    def test_sparse_actual_slots_are_visited_without_inventing_slot_zero(self):
        self.inventory[1]['data']['outfit_list'] = [{'outfit_type': 1, 'outfit_index': 2}, {'outfit_type': 1, 'outfit_index': 4}]
        result, proof = self.run_probe()
        self.assertTrue(result['ok'])
        self.assertEqual([row['index'] for row in self.submitted if row['operation'] == 'outfit' and row['category'] == 1], [2, 4])
        self.assertEqual(proof['category_coverage'][1]['verified_slots'], [2, 4])

    def test_missing_and_unknown_categories_are_distinct_and_never_pass_complete_coverage(self):
        self.inventory[2]['data']['outfit_list'] = []
        self.inventory[3].update(query='failed', supported=False, data=None)
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertTrue(result['available_steps_verified'])
        self.assertFalse(result['all_standard_categories_tested'])
        self.assertEqual(result['outcome'], 'completed-with-skips')
        self.assertEqual(proof['category_coverage'][2]['state'], 'missing')
        self.assertEqual(proof['category_coverage'][3]['state'], 'unavailable')
        self.assertFalse(any(row['operation'] == 'outfit' and row['category'] in (2, 3) for row in self.submitted))

    def test_optional_second_outfit_creates_one_exact_slot_only_after_existing_series(self):
        result, proof = self.run_probe(everyday_second=True)
        self.assertTrue(result['ok'])
        self.assertEqual(proof['everyday_second']['outcome'], 'verified-created-second')
        additions = [index for index, row in enumerate(self.submitted) if row['operation'] == 'outfit-add']
        self.assertEqual(additions, [14])
        self.assertEqual(self.submitted[14], {'operation': 'outfit-add', 'category': 0})
        self.assertTrue(proof['outfit_add_submitted'])
        self.assertEqual(self.inventory[0]['data']['outfit_list'],
                         [{'outfit_type': 0, 'outfit_index': 0}, {'outfit_type': 0, 'outfit_index': 1}])
        self.assertFalse(proof['cas_changes_accepted'])

    def test_optional_existing_second_and_unsupported_capacity_never_append(self):
        self.inventory[0]['data']['outfit_list'].append({'outfit_type': 0, 'outfit_index': 1})
        result, proof = self.run_probe(everyday_second=True)
        self.assertTrue(result['ok'])
        self.assertEqual(proof['everyday_second']['outcome'], 'verified-existing-second')
        self.assertFalse(proof['outfit_add_submitted'])
        self.output.unlink()
        self.submitted.clear(); self.pending.clear()
        self.inventory[0]['data']['outfit_list'] = [{'outfit_type': 0, 'outfit_index': 0}]
        self.inventory[0]['data']['max_outfits'] = 1
        result, proof = self.run_probe(everyday_second=True)
        self.assertFalse(result['ok'])
        self.assertEqual(proof['everyday_second']['outcome'], 'skipped-unavailable')
        self.assertFalse(proof['outfit_add_submitted'])

    def test_wrong_sim_handshake_stops_before_status_without_entry_or_fallback(self):
        self.diagnostic['native_peers'][0]['sim_id'] = '12'
        result, _proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual(self.submitted, [])
        self.assertEqual(len(self.calls), 2)

    def test_wrong_sim_or_wrong_uuid_ack_stops_before_any_further_mutation(self):
        def wrong_sim(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'status':
                value = copy.deepcopy(self.pending[rid])
                value['client']['sim']['simId'] = '12'
                return value
        self.fault = wrong_sim
        result, _proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.submitted), 1)
        self.output.unlink(); self.submitted.clear(); self.pending.clear()
        def wrong_uuid(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'hair-swatch':
                return dict(self.pending[rid], cas_request_id='f' * 32)
        self.fault = wrong_uuid
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status', 'hair-swatch'])
        self.assertEqual(proof['steps'][-1]['cas_request_id'], '{:032x}'.format(2))

    def test_lost_mutation_ack_retains_native_uuid_without_cleanup_or_replay(self):
        def lost(action, operation, _rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'hair-swatch':
                raise OSError('lost ACK after native mutation')
        self.fault = lost
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status', 'hair-swatch'])
        self.assertEqual(proof['steps'][-1]['cas_request_id'], '{:032x}'.format(2))
        self.assertFalse(proof['final_status_observed'])

    def test_history_readback_mismatch_is_failure_even_if_native_ack_says_ok(self):
        def wrong_undo(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'undo':
                value = copy.deepcopy(self.pending[rid])
                value['client']['hair_selected_swatch_id'] = ALTERNATE
                return value
        self.fault = wrong_undo
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status', 'hair-swatch', 'undo'])
        self.assertIn('expected hair ID', proof['error'])

    def test_history_cannot_be_verified_if_it_changes_the_selected_outfit(self):
        def changed_slot(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'undo':
                value = copy.deepcopy(self.pending[rid])
                value['client']['outfit'] = {'outfit_type': 1, 'outfit_index': 0}
                return value
        self.fault = changed_slot
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertFalse(proof['steps'][-1]['verified'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status', 'hair-swatch', 'undo'])

    def test_duplicate_slots_and_missing_alternate_hair_refuse_before_any_mutation(self):
        self.inventory[1]['data']['outfit_list'].append({'outfit_type': 1, 'outfit_index': 0})
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status'])
        self.assertIn('duplicated', proof['error'])
        self.output.unlink(); self.submitted.clear(); self.pending.clear()
        self.inventory[1]['data']['outfit_list'].pop()
        original_client = self.client
        def no_alternate():
            value = original_client()
            value['hair_swatches'] = [{'dataID': ORIGINAL}]
            return value
        self.client = no_alternate
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status'])
        self.assertIn('No exact alternate', proof['error'])

    def test_probe_and_step_wait_bounds_reject_before_any_game_request(self):
        for options in ({'seconds': 0}, {'seconds': 301}, {'seconds': float('nan')},
                        {'step_seconds': True}, {'step_seconds': 61}, {'everyday_second': 1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                probe.run(self.state, self.output, self.identity, self.request, SIM, **options)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())

    def test_crash_after_second_undo_preserves_changed_xml_and_last_native_uuid(self):
        report = b'<root><type>crash</type><categoryid>0x14112c645</categoryid><memdumptxt>private memory</memdumptxt></root>'
        def crash(action, operation, _rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'undo' and len(self.submitted) == 5:
                (self.profile / 'lastCrash.txt').write_bytes(report)
                self.alive = False
                raise OSError('game disconnected')
        self.fault = crash
        result, proof = self.run_probe()
        self.assertEqual(result['outcome'], 'crash')
        self.assertEqual(proof['steps'][-1]['cas_request_id'], '{:032x}'.format(5))
        self.assertEqual(Path(proof['crash']['path']).read_bytes(), report)
        self.assertNotIn('private memory', self.output.read_text())
        self.assertTrue(proof['process_exit_verified'])
        self.assertEqual(len(self.submitted), 5)

    def test_pending_ack_deadline_only_polls_same_uuid_and_does_not_repeat_mutation(self):
        def pending(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'hair-swatch':
                return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': rid}
        self.fault = pending
        result, proof = self.run_probe(seconds=.5, step_seconds=.4)
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status', 'hair-swatch'])
        self.assertEqual(proof['steps'][-1]['cas_request_id'], '{:032x}'.format(2))
        self.assertLessEqual(result['elapsed_seconds'], .55)

    def test_external_proof_and_identity_validation_preserve_existing_evidence(self):
        for target in (self.profile / 'proof.json', self.original / 'proof.json', self.state):
            with self.subTest(target=target), self.assertRaises(ValueError):
                probe.run(self.state, target, self.identity, self.request, SIM)
        self.output.write_bytes(b'immutable previous evidence')
        with self.assertRaises(ValueError):
            probe.run(self.state, self.output, self.identity, self.request, SIM)
        self.assertEqual(self.output.read_bytes(), b'immutable previous evidence')
        self.assertEqual(self.calls, [])
        self.output.unlink()
        for identity in (dict(self.identity, pid=True), dict(self.identity, script_sha256='b' * 64),
                         dict(self.identity, test_token='wrong')):
            with self.assertRaisesRegex(ValueError, 'identity'):
                probe.run(self.state, self.output, identity, self.request, SIM)
        self.assertEqual(self.calls, [])

    def test_transport_failure_retains_predetermined_owner_uuid_and_pinned_bridge_cannot_change(self):
        original_request = self.request
        def request(state, action, sim_id=None, **kwargs):
            if action == 'cas_ui_request':
                kwargs['transport']('/api/command', {'action': 'cas_ui_request', 'request_id': 'e' * 32})
            return original_request(state, action, sim_id=sim_id, **kwargs)
        def lost_transport(path, query=None, timeout=12):
            raise OSError('owner response lost')
        self.request = request
        result, proof = self.run_probe(transport=lost_transport)
        self.assertFalse(result['ok'])
        self.assertEqual(proof['steps'][0]['owner_requests'], [{'action': 'cas_ui_request', 'request_id': 'e' * 32}])
        self.output.unlink()
        def changed_bridge(path, query=None, timeout=12):
            return dict(self.identity, pid=43)
        def check_bridge(state, action, sim_id=None, **kwargs):
            if action == 'cas_ui_request':
                kwargs['transport']('/api/bridge')
            return original_request(state, action, sim_id=sim_id, **kwargs)
        self.request = check_bridge
        result, proof = self.run_probe(transport=changed_bridge)
        self.assertFalse(result['ok'])
        self.assertIn('changed PID/token/script', proof['error'])
        self.assertEqual(self.submitted, [])

    def test_cli_requires_explicit_identity_output_and_outfit_add_is_opt_in(self):
        args = apex_cli.parser().parse_args(['cas-probe', '--state', str(self.state), '--sim-id', SIM, '--output', str(self.output)])
        self.assertFalse(args.outfit_add)
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity', return_value=self.identity), \
                patch.object(probe, 'run', return_value={'ok': True}) as runner:
            self.assertTrue(apex_cli.execute(args)['ok'])
            self.assertFalse(runner.call_args.kwargs['everyday_second'])
        args.outfit_add = True
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity', return_value=self.identity), \
                patch.object(probe, 'run', return_value={'ok': True}) as runner:
            apex_cli.execute(args)
            self.assertTrue(runner.call_args.kwargs['everyday_second'])
        self.assertTrue(probe.parser().parse_args(['--state', 'state', '--sim-id', SIM, '--output', 'proof', '--outfit-add']).everyday_second)

    def test_visible_overlay_is_hidden_before_native_slot_and_restored_after_terminal_probe(self):
        self.overlay_visible = True
        result, proof = self.run_probe()
        self.assertTrue(result['ok'])
        actions = [row[0] for row in self.calls]
        self.assertEqual(actions[:4], ['overlay_status', 'overlay_hide', 'cas_ui_diagnostics', 'cas_ui_request'])
        self.assertEqual(actions[-2:], ['cas_ui_diagnostics', 'overlay_show'])
        self.assertTrue(self.overlay_visible)
        suppression = proof['overlay_suppression']
        self.assertIs(suppression['initial_visibility'], True)
        self.assertTrue(suppression['suppression_verified'])
        self.assertTrue(suppression['restored'])
        self.assertEqual([row['action'] for row in suppression['controls']], ['overlay_status', 'overlay_hide', 'overlay_show'])
        self.assertTrue(all(probe.uuid_id(row['request_id']) for row in suppression['controls']))

    def test_hidden_or_never_loaded_overlay_is_not_started_or_shown_by_probe(self):
        result, proof = self.run_probe()
        self.assertTrue(result['ok'])
        self.assertEqual(proof['overlay_suppression']['outcome'], 'kept-hidden')
        self.assertNotIn('overlay_show', [row[0] for row in self.calls])
        self.output.unlink(); self.submitted.clear(); self.pending.clear(); self.calls.clear()
        self.overlay_started = False
        result, proof = self.run_probe()
        self.assertTrue(result['ok'])
        self.assertFalse(proof['overlay_suppression']['sidecar_started'])
        self.assertEqual(proof['overlay_suppression']['outcome'], 'not-started')
        self.assertFalse(any(row[0] in ('overlay_start', 'overlay_hide', 'overlay_show') for row in self.calls))

    def test_lost_ack_leaves_initially_visible_overlay_hidden_without_restore_or_replay(self):
        self.overlay_visible = True
        def lost(action, operation, _rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'hair-swatch':
                raise OSError('lost native ACK')
        self.fault = lost
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertFalse(self.overlay_visible)
        self.assertEqual(proof['overlay_suppression']['outcome'], 'left-hidden-unresolved')
        self.assertFalse(proof['overlay_suppression']['restore_attempted'])
        self.assertEqual([row['operation'] for row in self.submitted], ['status', 'hair-swatch'])

    def test_unknown_visibility_refuses_before_native_transaction(self):
        original_request = self.request
        self.request = lambda state, action, **kwargs: ({'ok': False, 'message': 'unknown native failure'}
                            if action == 'overlay_status' else original_request(state, action, **kwargs))
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual(self.submitted, [])
        self.assertFalse(proof['overlay_suppression']['suppression_verified'])

    def test_lost_hide_transport_retains_owner_uuid_before_any_native_cas_submission(self):
        self.overlay_visible = True
        original_request = self.request
        def request(state, action, **kwargs):
            if action == 'overlay_hide':
                kwargs['transport']('/api/native', {'action': action, 'request_id': 'e' * 32})
            return original_request(state, action, **kwargs)
        self.request = request
        def lost(_path, _query=None, timeout=12):
            raise OSError('hide response lost')
        result, proof = self.run_probe(transport=lost)
        self.assertFalse(result['ok'])
        self.assertEqual(self.submitted, [])
        self.assertEqual(proof['owner_control_requests'], [{'action': 'overlay_hide', 'request_id': 'e' * 32}])
        self.assertTrue(proof['overlay_suppression']['hide_attempted'])
        self.assertFalse(proof['overlay_suppression']['restore_attempted'])

    def test_pending_overlay_read_is_drained_without_inventing_or_replaying_native_input(self):
        rid = 'f' * 32
        self.overlay_visible = True
        self.diagnostic['requests'] = [{'cas_request_id': rid, 'state': 'pending', 'operation': 'status'}]
        original_request = self.request
        def request(state, action, **kwargs):
            result = original_request(state, action, **kwargs)
            if action == 'cas_ui_diagnostics' and sum(row[0] == action for row in self.calls) == 2:
                self.diagnostic['requests'][0]['state'] = 'completed'
            return result
        self.request = request
        result, proof = self.run_probe()
        self.assertTrue(result['ok'])
        self.assertEqual([row[0] for row in self.calls][:5],
                         ['overlay_status', 'overlay_hide', 'cas_ui_diagnostics', 'cas_ui_diagnostics', 'cas_ui_request'])
        self.assertEqual(proof['overlay_suppression']['observed_native_requests'],
                         [{'cas_request_id': rid, 'initial_state': 'pending', 'last_state': 'completed'}])

    def test_native_acceptance_and_unresolved_outcomes_block_slot_and_visibility_restore(self):
        for state, outcome in (('accept-intent', None), ('accept-unresolved', None), ('superseded-read', None),
                               ('completed', 'unresolved'), ('completed', 'accept-intent')):
            with self.subTest(state=state, outcome=outcome):
                self.overlay_visible = True
                evidence, actions = {}, []
                def call(action):
                    actions.append(action)
                    if action == 'overlay_status':
                        return {'ok': True, 'visible': True}
                    if action == 'overlay_hide':
                        return {'ok': True, 'visible': False}
                    row = {'cas_request_id': 'a' * 32, 'state': state, 'operation': 'accept'}
                    if outcome is not None:
                        row['outcome'] = outcome
                    return {'ok': True, 'requests': [row]}
                helper = probe.OverlaySuppression(call, evidence)
                helper.suppress()
                with self.assertRaisesRegex(RuntimeError, 'still owns'):
                    helper.wait_idle(monotonic=lambda: self.clock, pause=lambda value: setattr(self, 'clock', self.clock + value))
                helper.restore(True)
                self.assertNotIn('overlay_show', actions)
                self.assertFalse(evidence['restore_attempted'])
                self.assertEqual(evidence['blocking_native_requests'][0]['cas_request_id'], 'a' * 32)

    def test_pending_native_slot_has_bounded_wait_and_retains_original_uuid(self):
        self.overlay_visible = True
        self.diagnostic['requests'] = [{'cas_request_id': 'f' * 32, 'state': 'pending', 'operation': 'status'}]
        result, proof = self.run_probe(seconds=.25)
        self.assertFalse(result['ok'])
        self.assertEqual(self.submitted, [])
        self.assertLessEqual(result['elapsed_seconds'], .26)
        self.assertEqual(proof['overlay_suppression']['blocking_native_requests'][0]['cas_request_id'], 'f' * 32)
        self.assertFalse(self.overlay_visible)

    def test_only_superseded_status_reads_may_release_the_native_slot(self):
        self.diagnostic['requests'] = [{'cas_request_id': 'f' * 32, 'state': 'superseded-read',
                                       'operation': 'status', 'outcome': 'superseded-read'}]
        result, proof = self.run_probe()
        self.assertTrue(result['ok'])
        self.assertEqual(proof['overlay_suppression']['observed_native_requests'][0]['last_state'], 'superseded-read')
        self.output.unlink(); self.submitted.clear(); self.pending.clear()
        self.diagnostic['requests'][0]['operation'] = 'hair-swatch'
        result, proof = self.run_probe()
        self.assertFalse(result['ok'])
        self.assertEqual(self.submitted, [])
        self.assertIn('still owns', proof['error'])

    def test_ambiguous_visibility_restore_is_not_replayed(self):
        actions, evidence = [], {}
        def call(action):
            actions.append(action)
            if action == 'overlay_status':
                return {'ok': True, 'visible': True}
            if action == 'overlay_hide':
                return {'ok': True, 'visible': False}
            if action == 'cas_ui_diagnostics':
                return {'ok': True, 'requests': []}
            raise OSError('show response lost')
        helper = probe.OverlaySuppression(call, evidence)
        helper.suppress()
        helper.suppress()
        with self.assertRaises(OSError):
            helper.restore(True)
        helper.restore(True)
        self.assertEqual(actions.count('overlay_hide'), 1)
        self.assertEqual(actions.count('overlay_show'), 1)
        self.assertTrue(evidence['restore_attempted'])
        self.assertFalse(evidence['restored'])


if __name__ == '__main__':
    unittest.main()
