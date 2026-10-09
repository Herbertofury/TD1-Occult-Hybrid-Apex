import copy
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
import apex_cli
import cas_hair_audit as audit
import test_cas_runtime_probe as fixture

HOUSEHOLD = '285159751289798668'
EXACT_HIGH_ID = '18446744073709551614'
SIM = fixture.SIM


class CasHairAuditTests(unittest.TestCase):
    def setUp(self):
        # Reuse the established isolated profile/native-command producer, not a
        # second runtime or a collection of mock responses mirroring the audit.
        self.game = fixture.CasRuntimeProbeTests()
        self.game.setUp()
        self.addCleanup(self.game.doCleanups)
        self.game.current = (1, 0)
        original_client = self.game.client
        def client():
            value = original_client()
            value['sim'].update(householdId=HOUSEHOLD, speciesType=1, occultType=4, occultLayer=0,
                                arbitraryFutureSimField={'exactId': EXACT_HIGH_ID, 'raw': [1, None, 'a']})
            value['native_context'] = {'edit_mode': {'query': 'returned-value', 'value': 7},
                'new_family': {'query': 'returned-value', 'value': False},
                'entered_from_play_area': {'query': 'returned-value', 'value': {'result': True}}}
            swatch_id = value['hair_selected_swatch_id']
            value['hair_swatches'] = [{'dataID': swatch_id, 'color': 4262333968,
                                      'futureSwatch': {'id': EXACT_HIGH_ID}}]
            value['hair_color'] = swatch_id
            value['futureSnapshotField'] = {'identity': EXACT_HIGH_ID}
            for row in value['catalogs']:
                if row['panel'] == 'clothing_hair':
                    row['items'] = [{'dataID': swatch_id, 'hue_range_modifier': 0,
                                      'opacity_range_modifier': 1, 'futureModifier': {'exactId': EXACT_HIGH_ID}}]
                    row['preset'] = {'index': -1, 'presetId': '0', 'futurePreset': EXACT_HIGH_ID}
                    row['preset_query'] = 'returned-value'
            return value
        self.game.client = client
        self.transport_fault = None
        self.owner_requests = []

    def transport(self, path, query=None, timeout=12):
        self.assertLessEqual(timeout, 2)
        if self.transport_fault:
            replacement = self.transport_fault(path, query)
            if replacement is not None:
                return replacement
        if path == '/api/bridge':
            return copy.deepcopy(self.game.identity)
        self.assertEqual(path, '/api/command')
        self.assertTrue(audit.uuid_id(query['request_id']))
        self.owner_requests.append(copy.deepcopy(query))
        return {'ok': True}

    def request(self, state, action, sim_id=None, **kwargs):
        # Exercise the pinned transport and durable owner IDs even when the
        # producer loses a response after changing the UI's selected outfit.
        transport = kwargs['transport']
        transport('/api/bridge')
        transport('/api/command', {'action': action, 'request_id': uuid.uuid4().hex})
        return self.game.request(state, action, sim_id, **kwargs)

    def run_audit(self, **kwargs):
        before = self.game.files(self.game.original), self.game.files(self.game.profile), self.game.state.read_bytes()
        result = audit.run(self.game.state, self.game.output, self.game.identity, self.request, SIM,
             transport=self.transport, alive=lambda _pid: self.game.alive,
             monotonic=lambda: self.game.clock,
             pause=lambda seconds: setattr(self.game, 'clock', self.game.clock + seconds), **kwargs)
        self.assertEqual((self.game.files(self.game.original), self.game.files(self.game.profile), self.game.state.read_bytes()), before)
        proof = json.loads(self.game.output.read_text(encoding='utf-8'))
        self.assertTrue(proof['finalized'])
        self.assertLessEqual(self.game.output.stat().st_size, audit.MAX_PROOF_BYTES)
        self.assertFalse(proof['appearance_mutation_submitted'])
        self.assertFalse(proof['outfit_creation_submitted'])
        self.assertFalse(proof['accept_submitted'])
        self.assertFalse(proof['save_submitted'])
        self.assertFalse(proof['input_submitted'])
        self.assertTrue(all(row['operation'] in ('status', 'outfit') for row in self.game.submitted))
        return result, proof

    def test_all_returned_metadata_is_retained_but_only_verified_categories_are_selected_twice(self):
        result, proof = self.run_audit()
        self.assertTrue(result['ok'], proof.get('error'))
        self.assertEqual(result['outcome'], 'completed-with-partial-coverage')
        self.assertTrue(proof['verified_selector_slots_twice_observed'])
        self.assertFalse(proof['complete_returned_slot_coverage'])
        self.assertFalse(proof['returned_slots_twice_observed'])
        self.assertEqual(proof['explicit_existing_slot_count'], 14)
        self.assertEqual(proof['selectable_slot_count'], 8)
        self.assertEqual(len(proof['observations']), 16)
        self.assertEqual(len(proof['comparisons']), 8)
        selected = [row['category'] for row in self.game.submitted if row['operation'] == 'outfit']
        self.assertEqual(selected, list(audit.STANDARD_CATEGORIES) * 2 + [1])
        self.assertEqual([row['category'] for row in proof['category_coverage']], list(range(14)))
        self.assertEqual(proof['category_coverage'][6]['selector_unverified_slots'], [0])
        self.assertEqual(proof['category_coverage'][6]['state'], 'present')
        self.assertTrue(proof['initial_selection_restored'])
        self.assertTrue(proof['final_status_observed'])
        self.assertEqual(self.game.current, (1, 0))

    def test_existing_everyday_second_preserves_per_slot_raw_records_and_full_future_fields(self):
        self.game.inventory[0]['data']['outfit_list'].append({'outfit_type': 0, 'outfit_index': 1,
                                                             'futureSlotField': EXACT_HIGH_ID})
        self.game.hair[(0, 1)] = EXACT_HIGH_ID
        result, proof = self.run_audit()
        self.assertTrue(result['ok'], proof.get('error'))
        captures = [row for row in proof['observations'] if row['category'] == 0 and row['index'] == 1]
        self.assertEqual(len(captures), 2)
        for row in captures:
            raw = row['native_client']
            self.assertEqual(raw['sim']['arbitraryFutureSimField']['exactId'], EXACT_HIGH_ID)
            self.assertEqual(raw['futureSnapshotField']['identity'], EXACT_HIGH_ID)
            hair = next(item for item in raw['catalogs'] if item['panel'] == 'clothing_hair')
            self.assertEqual(hair['items'][0]['dataID'], EXACT_HIGH_ID)
            self.assertEqual(hair['items'][0]['futureModifier']['exactId'], EXACT_HIGH_ID)
            self.assertEqual(hair['preset']['futurePreset'], EXACT_HIGH_ID)
            self.assertEqual(raw['hair_swatches'][0]['futureSwatch']['id'], EXACT_HIGH_ID)
            self.assertEqual(row['observed']['style']['selected_part_resource_ids'], [EXACT_HIGH_ID])
            self.assertEqual(row['observed']['color']['ui_swatch_resource_id'], EXACT_HIGH_ID)
        self.assertEqual(proof['category_coverage'][0]['first_pass_slots'], [0, 1])
        self.assertEqual(proof['category_coverage'][0]['repeat_pass_slots'], [0, 1])
        variation = next(row for row in proof['within_pass_variation'][0]['comparisons']
                         if row['category'] == 0 and row['index'] == 1)
        self.assertTrue(variation['style']['selected_part_resource_ids_changed'])
        self.assertTrue(variation['color']['ui_swatch_resource_changed'])
        self.assertFalse(variation['modifiers_changed'])
        self.assertIsNone(variation['color']['packed_uint64_outfit_color_changed'])

    def test_repeat_style_resource_modifier_and_ui_color_differences_are_separate_and_never_packed_color(self):
        def changed(action, operation, rid, _kwargs):
            if (action == 'cas_ui_result' and operation == {'operation': 'outfit', 'category': 0, 'index': 0} and
                    sum(item == operation for item in self.game.submitted) == 2):
                value = copy.deepcopy(self.game.pending[rid])
                hair = next(row for row in value['client']['catalogs'] if row['panel'] == 'clothing_hair')
                hair['items'][0]['dataID'] = EXACT_HIGH_ID
                hair['items'][0]['opacity_range_modifier'] = .25
                value['client']['hair_swatches'][0]['color'] = 123
                return value
        self.game.fault = changed
        result, proof = self.run_audit()
        self.assertTrue(result['ok'], proof.get('error'))
        comparison = proof['comparisons'][0]
        self.assertTrue(comparison['style']['selected_part_resource_ids_changed'])
        self.assertIsNone(comparison['style']['hairstyle_family_changed'])
        self.assertFalse(comparison['color']['ui_swatch_resource_changed'])
        self.assertTrue(comparison['color']['ui_swatch_color_raw_changed'])
        self.assertIsNone(comparison['color']['packed_uint64_outfit_color_changed'])
        self.assertTrue(comparison['modifiers_changed'])
        self.assertFalse(comparison['outfit_independence_verified'])
        self.assertFalse(result['packed_uint64_color_verified'])
        self.assertFalse(result['hairstyle_family_verified'])

    def test_numeric_or_missing_native_resource_ids_are_unknown_not_coerced_to_exact_ids(self):
        original_client = self.game.client
        def client():
            value = original_client()
            hair = next(row for row in value['catalogs'] if row['panel'] == 'clothing_hair')
            hair['items'][0]['dataID'] = 18446744073709551614
            value['hair_selected_swatch_id'] = 414264
            return value
        self.game.client = client
        result, proof = self.run_audit()
        self.assertTrue(result['ok'])
        self.assertFalse(proof['resource_observations_complete'])
        self.assertTrue(all(not row['observed']['style']['selected_part_resource_ids_known'] for row in proof['observations']))
        self.assertTrue(all(not row['observed']['color']['ui_swatch_resource_known'] for row in proof['observations']))
        self.assertIsNone(proof['comparisons'][0]['style']['selected_part_resource_ids_changed'])

    def test_empty_unknown_missing_and_selector_unverified_categories_are_distinct(self):
        self.game.inventory[2]['data']['outfit_list'] = []
        self.game.inventory[3].update(query='failed', supported=False, data=None)
        self.game.inventory.pop(4)
        result, proof = self.run_audit()
        self.assertTrue(result['ok'])
        self.assertFalse(proof['all_native_categories_queried'])
        states = {row['category']: row for row in proof['category_coverage']}
        self.assertEqual(states[2]['state'], 'missing')
        self.assertEqual(states[3]['state'], 'unavailable')
        self.assertEqual(states[4]['state'], 'not-returned')
        self.assertEqual(states[6]['state'], 'present')
        self.assertFalse(states[6]['selector_verified'])
        self.assertFalse(any(row['operation'] == 'outfit' and row['category'] in (2, 3, 4, 6)
                             for row in self.game.submitted))

    def test_sparse_slot_list_is_enumerated_without_inventing_or_selecting_unsupported_ordinals(self):
        self.game.inventory[2]['data']['outfit_list'] = [{'outfit_type': 2, 'outfit_index': 1},
                                                       {'outfit_type': 2, 'outfit_index': 4}]
        result, proof = self.run_audit()
        self.assertTrue(result['ok'])
        coverage = proof['category_coverage'][2]
        self.assertEqual(coverage['slots'], [1, 4])
        self.assertEqual(coverage['selectable_slots'], [1])
        self.assertEqual(coverage['selector_unsupported_slots'], [4])
        self.assertEqual(coverage['first_pass_slots'], [1])
        self.assertFalse(any(row['operation'] == 'outfit' and row['category'] == 2 and row['index'] in (0, 4)
                             for row in self.game.submitted))

    def test_lost_selection_ack_retains_native_and_owner_uuids_without_restoration_or_replay(self):
        self.game.overlay_visible = True
        def lost(action, operation, _rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'outfit':
                raise OSError('lost after the native selector ran')
        self.game.fault = lost
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.game.submitted], ['status', 'outfit'])
        self.assertTrue(audit.uuid_id(proof['steps'][-1]['cas_request_id']))
        self.assertTrue(all(audit.uuid_id(row['request_id']) for row in proof['steps'][-1]['owner_requests']))
        self.assertFalse(proof['initial_selection_restored'])
        self.assertFalse(any(action == 'overlay_show' for action, _, _ in self.game.calls))
        self.assertEqual(self.game.current, (0, 0))

    def test_lost_submit_response_preserves_owner_uuid_before_native_uuid_is_known(self):
        def lost(action, operation, _rid, _kwargs):
            if action == 'cas_ui_request' and operation['operation'] == 'outfit':
                raise OSError('submission response lost')
        self.game.fault = lost
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertIsNone(proof['steps'][-1]['cas_request_id'])
        self.assertEqual(len(self.game.submitted), 2)
        self.assertTrue(audit.uuid_id(proof['steps'][-1]['owner_requests'][-1]['request_id']))
        self.assertFalse(proof['initial_selection_restored'])

    def test_pending_owner_does_not_resubmit_selection_or_attempt_cleanup(self):
        def pending(action, operation, _rid, _kwargs):
            if action == 'cas_ui_request' and operation['operation'] == 'outfit':
                return {'ok': False, 'outcome': 'unresolved', 'request_id': 'f' * 32}
        self.game.fault = pending
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.game.submitted), 2)
        self.assertIsNone(proof['steps'][-1]['cas_request_id'])
        self.assertFalse(proof['initial_selection_restored'])

    def test_wrong_sim_household_form_uuid_or_selected_slot_stops_without_next_command(self):
        for field in ('simId', 'householdId', 'occultType', 'outfit', 'cas_request_id'):
            with self.subTest(field=field):
                self.game.output.unlink(missing_ok=True)
                self.game.submitted.clear(); self.game.pending.clear(); self.game.current = (1, 0)
                def wrong(action, operation, rid, _kwargs):
                    if action == 'cas_ui_result' and operation['operation'] == 'outfit':
                        value = copy.deepcopy(self.game.pending[rid])
                        if field == 'cas_request_id': value[field] = 'f' * 32
                        elif field == 'outfit': value['client'][field] = {'outfit_type': 0, 'outfit_index': 1}
                        else: value['client']['sim'][field] = 8 if field == 'occultType' else '12'
                        return value
                self.game.fault = wrong
                result, proof = self.run_audit()
                self.assertFalse(result['ok'])
                self.assertEqual(len(self.game.submitted), 2)
                self.assertFalse(proof['initial_selection_restored'])

    def test_new_or_removed_outfit_during_audit_invalidates_retained_inventory_without_cleanup(self):
        def changed(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'outfit':
                value = copy.deepcopy(self.game.pending[rid])
                value['client']['planned_outfits'][0]['data']['outfit_list'].append({'outfit_type': 0, 'outfit_index': 1})
                return value
        self.game.fault = changed
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertIn('inventory changed', proof['error'])
        self.assertEqual(len(self.game.submitted), 2)

    def test_known_evidence_budget_stop_preserves_original_selection_and_reports_partial_coverage(self):
        result, proof = self.run_audit(max_raw_bytes=1)
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'completed-with-partial-coverage')
        self.assertEqual(proof['stop_reason'], 'raw-evidence-budget')
        self.assertEqual(proof['observations'], [])
        self.assertEqual(proof['raw_bytes_retained'], 0)
        self.assertTrue(proof['initial_selection_restored'])
        self.assertTrue(proof['final_status_observed'])
        self.assertEqual(self.game.current, (1, 0))

    def test_deadline_reserves_known_cleanup_but_does_not_continue_observation_pass(self):
        base_request = self.game.request
        def slow(*args, **kwargs):
            result = base_request(*args, **kwargs)
            self.game.clock += .15
            return result
        self.game.request = slow
        result, proof = self.run_audit(seconds=4, step_seconds=1)
        self.assertFalse(result['ok'])
        self.assertEqual(proof['stop_reason'], 'audit-budget-reserved-for-selection-restoration')
        self.assertTrue(proof['initial_selection_restored'])
        self.assertLess(len(proof['observations']), 16)

    def test_f11_visibility_is_hidden_before_selection_and_restored_after_final_verified_status(self):
        self.game.overlay_visible = True
        result, proof = self.run_audit()
        self.assertTrue(result['ok'])
        actions = [action for action, _, _ in self.game.calls]
        self.assertLess(actions.index('overlay_hide'), actions.index('cas_ui_request'))
        self.assertGreater(actions.index('overlay_show'), max(index for index, action in enumerate(actions) if action == 'cas_ui_result'))
        self.assertEqual(actions.count('overlay_hide'), 1)
        self.assertEqual(actions.count('overlay_show'), 1)
        self.assertTrue(proof['overlay_suppression']['restored'])

    def test_wrong_peer_or_pinned_bridge_stops_before_status_and_no_cas_entry_occurs(self):
        self.game.diagnostic['native_peers'][0]['sim_id'] = '12'
        result, _proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(self.game.submitted, [])
        self.game.output.unlink(); self.game.calls.clear()
        self.transport_fault = lambda path, _query: dict(self.game.identity, pid=43) if path == '/api/bridge' else None
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(proof['owner_requests'], [])
        self.assertEqual(self.game.submitted, [])

    def test_bad_output_or_identity_refuses_before_commands_and_preserves_existing_files(self):
        for output in (self.game.state, self.game.profile / 'proof.json', self.game.original / 'proof.json', self.game.root / 'missing/proof.json'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                audit.run(self.game.state, output, self.game.identity, self.request, SIM)
        for identity in (dict(self.game.identity, pid=True), dict(self.game.identity, test_token='b' * 32),
                         dict(self.game.identity, script_sha256='b' * 64)):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                audit.run(self.game.state, self.game.output, identity, self.request, SIM)
        for seconds in (0, -1, 301, float('nan'), True):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                audit.run(self.game.state, self.game.output, self.game.identity, self.request, SIM, seconds=seconds)
        self.assertEqual(self.game.calls, [])
        self.assertFalse(self.game.output.exists())

    def test_cli_requires_external_proof_and_wires_only_audit_parameters(self):
        args = apex_cli.parser().parse_args(['cas-hair-audit', '--state', 'state.json', '--sim-id', SIM,
                    '--output', 'audit.json', '--seconds', '200', '--step-seconds', '10'])
        self.assertEqual(args.command, 'cas-hair-audit')
        self.assertEqual(args.seconds, 200)
        self.assertEqual(args.step_seconds, 10)
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity', return_value=self.game.identity), \
                patch.object(audit, 'run', return_value={'ok': True}) as run:
            self.assertEqual(apex_cli.execute(args), {'ok': True})
        self.assertEqual(run.call_args.args[:5], (Path('state.json'), Path('audit.json'), self.game.identity, apex_cli.owned_request, SIM))
        self.assertEqual(run.call_args.kwargs['seconds'], 200)


if __name__ == '__main__':
    unittest.main()
