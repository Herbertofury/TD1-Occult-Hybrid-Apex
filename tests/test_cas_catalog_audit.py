import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
from apex_core import cas_ui
import cas_catalog_audit as audit
import test_cas_hair_audit as fixture

SIM = fixture.SIM
HIGH_ID = fixture.EXACT_HIGH_ID


class CasCatalogAuditTests(unittest.TestCase):
    def setUp(self):
        # Reuse the actual isolated-profile fixtures and native CAS producer.
        # Extend only its real panel navigation path, leaving identity, raw
        # inventory, ownership, F11 and failure machinery shared with the probe.
        self.fixture = fixture.CasHairAuditTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.game = self.fixture.game
        self.menu = cas_ui.PANELS['clothing_hair']
        self.visible = True
        original_client = self.game.client
        def client():
            value = original_client()
            value.update(menu_state=self.menu, panel_visible=self.visible)
            for row in value['catalogs']:
                row['futureCatalogRecord'] = {'id': HIGH_ID}
            return value
        self.game.client = client
        original_request = self.game.request
        def request(state, action, sim_id=None, **kwargs):
            operation = json.loads(kwargs['value']) if action == 'cas_ui_request' else None
            if operation is None or operation['operation'] != 'panel':
                return original_request(state, action, sim_id, **kwargs)
            self.game.calls.append((action, sim_id, kwargs))
            self.game.clock += .001
            self.game.submitted.append(operation)
            rid = '{:032x}'.format(len(self.game.submitted))
            self.menu, self.visible = cas_ui.panel(operation['panel']), True
            self.game.pending[rid] = {'ok': True, 'protocol': 1, 'operation': 'panel', 'cas_request_id': rid,
                'ui_transition_verified': True, 'cas_request_state': 'completed', 'client': self.game.client()}
            if self.game.fault:
                replacement = self.game.fault(action, operation, rid, kwargs)
                if replacement is not None:
                    return replacement
            return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': rid}
        self.game.request = request

    def run_audit(self, **kwargs):
        before = self.game.files(self.game.original), self.game.files(self.game.profile), self.game.state.read_bytes()
        options = {'panels': ['skin_details', 'earrings']}
        options.update(kwargs)
        result = audit.run(self.game.state, self.game.output, self.game.identity, self.fixture.request, SIM,
            transport=self.fixture.transport, alive=lambda _pid: self.game.alive,
            monotonic=lambda: self.game.clock,
            pause=lambda seconds: setattr(self.game, 'clock', self.game.clock + seconds), **options)
        self.assertEqual((self.game.files(self.game.original), self.game.files(self.game.profile), self.game.state.read_bytes()), before)
        proof = json.loads(self.game.output.read_text(encoding='utf-8'))
        self.assertTrue(proof['finalized'])
        self.assertLessEqual(self.game.output.stat().st_size, audit.MAX_PROOF_BYTES)
        self.assertTrue(all(row['operation'] in ('status', 'panel') for row in self.game.submitted))
        for flag in ('appearance_mutation_submitted', 'outfit_selection_submitted', 'outfit_creation_submitted',
                     'history_submitted', 'accept_submitted', 'entry_submitted', 'save_submitted', 'input_submitted'):
            self.assertFalse(proof[flag])
        return result, proof

    def test_supported_subset_retains_all_72_raw_catalogs_presets_sim_and_future_fields_per_panel(self):
        self.game.overlay_visible = True
        result, proof = self.run_audit()
        self.assertTrue(result['ok'], result['message'])
        self.assertEqual(result['outcome'], 'completed-with-partial-coverage')
        self.assertEqual(result['catalog_count'], len(cas_ui.PANELS))
        self.assertTrue(result['complete_catalog_inventory'])
        self.assertFalse(result['full_72_panel_transition_coverage'])
        self.assertEqual(result['verified_panels'], ['clothing_accessories_earrings', 'clothing_head_skin_details'])
        self.assertTrue(result['initial_panel_restored'])
        self.assertEqual(self.menu, cas_ui.PANELS['clothing_hair'])
        self.assertEqual([row['operation'] for row in self.game.submitted], ['status', 'panel', 'panel', 'panel', 'status'])
        for row in proof['observations']:
            self.assertTrue(row['validated'])
            raw = row['native_client']
            self.assertEqual(len(raw['catalogs']), len(cas_ui.PANELS))
            self.assertEqual(len(row['catalog_queries']), len(cas_ui.PANELS))
            self.assertEqual(raw['sim']['arbitraryFutureSimField']['exactId'], HIGH_ID)
            self.assertEqual(raw['futureSnapshotField']['identity'], HIGH_ID)
            self.assertTrue(all(catalog['futureCatalogRecord']['id'] == HIGH_ID for catalog in raw['catalogs']))
            hair = next(catalog for catalog in raw['catalogs'] if catalog['panel'] == 'clothing_hair')
            self.assertEqual(hair['preset']['futurePreset'], HIGH_ID)
        self.assertTrue(proof['overlay_suppression']['restored'])

    def test_unsupported_catalog_is_unavailable_separate_from_supported_empty_and_never_navigated(self):
        original_client = self.game.client
        def client():
            value = original_client()
            row = next(row for row in value['catalogs'] if row['panel'] == 'clothing_head_skin_details')
            row.update(supported=False, items=None, preset=None, preset_query='failed')
            return value
        self.game.client = client
        result, proof = self.run_audit()
        self.assertTrue(result['ok'])
        rows = {row['panel']: row for row in proof['catalog_coverage']}
        unavailable, empty = rows['clothing_head_skin_details'], rows['clothing_accessories_earrings']
        self.assertEqual(unavailable['catalog_state'], 'unavailable')
        self.assertIsNone(unavailable['catalog_item_count'])
        self.assertEqual(unavailable['preset_query'], 'failed')
        self.assertEqual(unavailable['navigation_outcome'], 'skipped-getter-unsupported')
        self.assertEqual(empty['catalog_state'], 'empty')
        self.assertEqual(empty['catalog_item_count'], 0)
        self.assertTrue(empty['transition_verified'])
        self.assertFalse(any(row.get('panel') == 'clothing_head_skin_details' for row in self.game.submitted))

    def test_lost_panel_ack_retains_native_and_owner_uuid_and_never_restores_or_replays(self):
        self.game.overlay_visible = True
        def lost(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'panel':
                raise OSError('ACK lost after the panel transition ran')
        self.game.fault = lost
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.game.submitted], ['status', 'panel'])
        self.assertTrue(audit.uuid_id(proof['steps'][-1]['cas_request_id']))
        self.assertTrue(all(audit.uuid_id(row['request_id']) for row in proof['steps'][-1]['owner_requests']))
        self.assertFalse(result['initial_panel_restored'])
        self.assertFalse(any(action == 'overlay_show' for action, _, _ in self.game.calls))

    def test_lost_submit_response_preserves_owner_uuid_without_unknown_native_id_replay(self):
        def lost(action, operation, rid, _kwargs):
            if action == 'cas_ui_request' and operation['operation'] == 'panel':
                raise OSError('Submission response was lost')
        self.game.fault = lost
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertIsNone(proof['steps'][-1]['cas_request_id'])
        self.assertTrue(audit.uuid_id(proof['steps'][-1]['owner_requests'][-1]['request_id']))
        self.assertEqual(len(self.game.submitted), 2)

    def test_stale_initial_peer_stops_before_status_and_never_enters_cas(self):
        self.game.diagnostic['native_peers'][0]['age_seconds'] = 4
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(self.game.submitted, [])
        self.assertFalse(proof['panel_navigation_submitted'])

    def test_wrong_sim_or_numeric_sim_ack_retains_raw_evidence_and_stops_before_restoration(self):
        for wrong in ('12', int(SIM)):
            with self.subTest(wrong=wrong):
                def changed(action, operation, rid, _kwargs):
                    if action == 'cas_ui_result' and operation['operation'] == 'panel':
                        value = copy.deepcopy(self.game.pending[rid])
                        value['client']['sim']['simId'] = wrong
                        return value
                self.game.fault = changed
                result, proof = self.run_audit()
                self.assertFalse(result['ok'])
                self.assertFalse(proof['observations'][-1]['validated'])
                self.assertEqual(proof['observations'][-1]['native_client']['sim']['simId'], wrong)
                self.assertEqual(len(self.game.submitted), 2)
                self.game.output.unlink()
                self.game.submitted.clear(); self.game.pending.clear()
                self.menu = cas_ui.PANELS['clothing_hair']

    def test_ok_ack_with_incomplete_catalog_inventory_never_proves_transition(self):
        def changed(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'panel':
                value = copy.deepcopy(self.game.pending[rid])
                value['client']['catalogs'].pop()
                return value
        self.game.fault = changed
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.game.submitted), 2)
        self.assertEqual(proof['observations'][-1]['catalog_count'] if 'catalog_count' in proof['observations'][-1] else None, None)
        self.assertFalse(proof['catalog_coverage'][0]['transition_verified'])

    def test_cached_old_panel_frame_cannot_pass_even_when_receipt_claims_a_verified_transition(self):
        def old(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'panel':
                value = copy.deepcopy(self.game.pending[rid])
                value['client']['menu_state'] = cas_ui.PANELS['clothing_hair']
                return value
        self.game.fault = old
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertFalse(proof['observations'][-1]['validated'])
        self.assertEqual(len(self.game.submitted), 2)
        self.assertFalse(result['initial_panel_restored'])

    def test_reused_native_uuid_stops_without_polling_old_receipt_or_restoration(self):
        def old_id(action, operation, rid, _kwargs):
            if action == 'cas_ui_request' and operation['operation'] == 'panel':
                return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': '{:032x}'.format(1)}
        self.game.fault = old_id
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(proof['steps'][-1]['cas_request_id'], '{:032x}'.format(1))
        self.assertEqual(proof['steps'][-1]['poll_count'], 0)
        self.assertEqual(len(self.game.submitted), 2)

    def test_pending_native_ack_polls_same_uuid_until_deadline_without_repeating_panel(self):
        def pending(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'panel':
                return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': rid}
        self.game.fault = pending
        result, proof = self.run_audit(step_seconds=.3)
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.game.submitted), 2)
        self.assertGreater(proof['steps'][-1]['poll_count'], 1)
        native_id = proof['steps'][-1]['cas_request_id']
        polled = [kwargs['value'] for action, _, kwargs in self.game.calls if action == 'cas_ui_result']
        self.assertTrue(all(value == native_id for value in polled[1:]))
        self.assertFalse(result['initial_panel_restored'])

    def test_unresolved_other_owner_blocks_initial_panel_restore_and_f11_restore(self):
        self.game.overlay_visible = True
        def busy(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation.get('panel') == 'clothing_accessories_earrings':
                self.game.diagnostic['requests'] = [{'cas_request_id': 'f' * 32, 'state': 'accept-intent',
                                                     'operation': 'accept', 'outcome': 'accept-intent'}]
        self.game.fault = busy
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual([row['operation'] for row in self.game.submitted], ['status', 'panel', 'panel'])
        self.assertFalse(result['initial_panel_restored'])
        self.assertFalse(proof['overlay_suppression']['restore_attempted'])
        self.assertEqual(proof['overlay_suppression']['blocking_native_requests'][0]['cas_request_id'], 'f' * 32)

    def test_small_step_budget_reserves_safe_restore_and_marks_incomplete_navigation(self):
        result, proof = self.run_audit(step_budget=4)
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.game.submitted), 4)
        self.assertTrue(result['initial_panel_restored'])
        self.assertEqual(result['verified_panels'], ['clothing_head_skin_details'])
        self.assertFalse(result['all_requested_supported_panels_verified'])

    def test_catalog_changes_are_recorded_separately_from_logical_sim_identity(self):
        def changed(action, operation, rid, _kwargs):
            if action == 'cas_ui_result' and operation['operation'] == 'panel':
                value = copy.deepcopy(self.game.pending[rid])
                row = next(row for row in value['client']['catalogs'] if row['panel'] == operation['panel'])
                row['items'] = [{'dataID': HIGH_ID, 'futureModifier': {'raw': 'preserved'}}]
                row['preset'] = {'presetId': HIGH_ID, 'futurePreset': [None, 1]}
                row['preset_query'] = 'returned-value'
                return value
        self.game.fault = changed
        result, proof = self.run_audit()
        self.assertTrue(result['ok'])
        change = proof['observations'][1]['catalog_changes_from_initial'][0]
        self.assertTrue(change['items_changed'])
        self.assertTrue(change['preset_changed'])
        self.assertTrue(proof['observations'][1]['logical_sim_identity_verified'])
        self.assertFalse(proof['observations'][1]['raw_sim_record_changed'])

    def test_unmapped_hidden_initial_panel_refuses_navigation_and_bounds_are_preflight_only(self):
        self.visible = False
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(result['catalog_count'], len(cas_ui.PANELS))
        self.assertTrue(result['complete_catalog_inventory'])
        self.assertFalse(result['initial_panel_restored'])
        self.assertFalse(result['all_requested_supported_panels_verified'])
        self.assertEqual(result['verified_panels'], [])
        self.assertFalse(proof['panel_navigation_submitted'])
        self.assertFalse(proof['initial_panel']['visible'])
        self.assertEqual(len(proof['observations'][0]['native_client']['catalogs']), len(cas_ui.PANELS))
        self.assertEqual([row['operation'] for row in self.game.submitted], ['status'])
        self.game.output.unlink(); self.game.submitted.clear(); self.game.pending.clear()
        for options in ({'seconds': 121}, {'step_budget': 25}, {'panels': ['hair', 'clothing_hair']}, {'panels': ['unknown']}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_audit(**options)
            self.assertFalse(self.game.output.exists())
            self.assertEqual(self.game.submitted, [])

    def test_unmapped_visible_initial_menu_retains_inventory_without_guessing_a_restoration(self):
        self.menu = -987654321
        result, proof = self.run_audit()
        self.assertFalse(result['ok'])
        self.assertEqual(result['catalog_count'], len(cas_ui.PANELS))
        self.assertTrue(result['complete_catalog_inventory'])
        self.assertIsNone(proof['initial_panel']['panel'])
        self.assertEqual(proof['initial_panel']['menu_state'], self.menu)
        self.assertTrue(proof['initial_panel']['visible'])
        self.assertFalse(proof['panel_navigation_submitted'])
        self.assertFalse(result['initial_panel_restored'])
        self.assertEqual([row['operation'] for row in self.game.submitted], ['status'])


if __name__ == '__main__':
    unittest.main()
