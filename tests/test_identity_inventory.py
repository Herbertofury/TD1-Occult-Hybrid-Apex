from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_bank, sim_data, test_driver

SIM, HOUSEHOLD, GUID = '285159751289798669', '285159751289798668', '1841692672'


class IdentityInventoryTests(unittest.TestCase):
    def setUp(self):
        self.sim = Obj(id=int(SIM), household_id=int(HOUSEHOLD), get_sim_instance=Mock(return_value=object()))
        self.other = Obj(id=int(SIM) + 1, household_id=0, get_sim_instance=Mock(return_value=None))
        self.manager = Obj(get=Mock(return_value=self.sim), get_all=Mock(return_value=[self.sim, self.other]),
                           add=Mock(side_effect=AssertionError('No manager insertion')), remove=Mock(side_effect=AssertionError('No removal')))
        self.household = Obj(id=int(HOUSEHOLD), sim_info_gen=Mock(return_value=iter([self.sim])))
        self.native_sim = Obj(sim_id=int(SIM), household_id=int(HOUSEHOLD))
        self.native_household = Obj(household_id=int(HOUSEHOLD), sims=Obj(ids=[int(SIM)]))
        self.persistence = Obj(get_household_proto_buff=Mock(return_value=self.native_household),
                               get_sim_proto_buff=Mock(return_value=self.native_sim),
                               save_game=Mock(side_effect=AssertionError('No save')), del_sim_proto_buff=Mock(side_effect=AssertionError('No deletion')))
        self.backend = Obj(services=Obj(sim_info_manager=lambda: self.manager, active_household=lambda: self.household,
                                       get_persistence_service=lambda: self.persistence),
                           _get_sim_info_by_id=Mock(return_value=None))
        self.live = {'ok': True, 'household_id': HOUSEHOLD, 'save_guid': GUID, 'zone_running': True,
                     'in_build_buy': False, 'client_id': '5', 'zone_id': '99',
                     'runtime_queries': {'client_id': 'returned-value', 'zone_running': 'returned-value'}}

    def argument(self, include=False):
        return {'household_id': HOUSEHOLD, 'save_guid': GUID, 'include_native_record': include}

    def read(self, argument=None, snapshots=None):
        with patch.object(test_driver, 'snapshot', side_effect=snapshots or [self.live, self.live]), \
                patch.object(form_bank, 'load') as bank:
            result = test_driver.native_identity_inventory(self.backend, SIM, argument or self.argument())
        bank.assert_not_called()
        self.manager.add.assert_not_called(); self.manager.remove.assert_not_called()
        self.persistence.save_game.assert_not_called(); self.persistence.del_sim_proto_buff.assert_not_called()
        return result

    def test_existing_owner_enumerates_exact_native_sources_and_unassigned_manager_sims(self):
        result = self.read()
        self.assertTrue(result['ok'])
        self.assertEqual(result['manager_selected']['sim_id'], SIM)
        self.assertEqual(result['manager_inventory']['sim_ids'], [SIM, str(int(SIM) + 1)])
        self.assertEqual(result['manager_inventory']['household_sim_ids'], [SIM])
        self.assertEqual(result['active_household']['sim_ids'], [SIM])
        self.assertEqual(result['persisted_household']['sim_ids'], [SIM])
        self.assertFalse(result['selected_native_absence_verified'])
        self.assertIsNone(result['native_record'])
        self.assertEqual(result['native_record_query'], 'not-requested')

    def test_missing_owner_is_verified_absent_without_claiming_deletion_or_replacement(self):
        self.manager.get.return_value = None; self.manager.get_all.return_value = [self.other]
        self.household.sim_info_gen.return_value = iter([])
        self.native_household.sims.ids = []; self.persistence.get_sim_proto_buff.return_value = None
        result = self.read(self.argument(include=True))
        self.assertTrue(result['ok'])
        self.assertTrue(result['selected_native_absence_verified'])
        self.assertFalse(result['identity_deletion_verified'])
        self.assertFalse(result['replacement_mapping_verified'])
        self.assertEqual(result['persisted_selected']['query'], 'returned-null')
        self.assertEqual(result['native_record_query'], 'returned-null')
        self.assertEqual(result['active_household']['sim_ids'], [])

    def test_missing_index_but_enumerated_owner_does_not_prove_absence(self):
        self.manager.get.return_value = None
        result = self.read()
        self.assertFalse(result['manager_selected']['present'])
        self.assertTrue(result['manager_inventory']['selected_present'])
        self.assertFalse(result['selected_native_absence_verified'])

    def test_persisted_owner_remains_visible_when_runtime_and_household_owner_are_missing(self):
        self.manager.get.return_value = None; self.manager.get_all.return_value = [self.other]
        self.household.sim_info_gen.return_value = iter([])
        result = self.read()
        self.assertTrue(result['ok'])
        self.assertTrue(result['persisted_selected']['present'])
        self.assertTrue(result['persisted_household']['selected_member'])
        self.assertFalse(result['selected_native_absence_verified'])

    def test_actual_changed_persisted_household_is_retained_without_inventing_original_ownership(self):
        self.native_sim.household_id = 0
        result = self.read()
        self.assertEqual(result['persisted_selected']['household_id'], '0')
        self.assertFalse(result['selected_native_absence_verified'])

    def test_existing_raw_persistence_record_retains_unknown_fields_without_runtime_serialization(self):
        self.sim.save_sim = Mock(side_effect=AssertionError('Do not serialize runtime Sim'))
        record = {'schema': 1, 'native_base64': 'AQ==', 'native_bytes': 1, 'unknown_fields_retained_in_native_bytes': True,
                  'data': {'futureField': {'raw': 'retained'}}, 'field_schemas': {}}
        with patch.object(sim_data, 'catalog', return_value=record) as catalog:
            result = self.read(self.argument(include=True))
        catalog.assert_called_once_with(self.native_sim)
        self.sim.save_sim.assert_not_called()
        self.assertEqual(result['native_record']['source'], 'native-existing-save-buffer')
        self.assertEqual(result['native_record']['data'], record['data'])
        self.assertEqual(result['native_record_query'], 'returned-value')

    def test_failed_native_queries_remain_failed_without_absence_fallback(self):
        self.manager.get_all.side_effect = RuntimeError('Native manager unavailable')
        result = self.read()
        self.assertFalse(result['ok'])
        self.assertEqual(result['manager_inventory']['query'], 'failed')
        self.assertIsNone(result['manager_inventory']['selected_present'])
        self.assertTrue(result['persisted_selected']['present'])
        self.assertFalse(result['selected_native_absence_verified'])

    def test_wrong_selected_proto_identity_and_duplicate_ids_fail_explicitly(self):
        self.native_sim.sim_id += 1
        self.native_household.sims.ids.append(int(SIM))
        result = self.read()
        self.assertFalse(result['ok'])
        self.assertEqual(result['persisted_selected']['query'], 'failed')
        self.assertEqual(result['persisted_household']['query'], 'failed')

    def test_wrong_initial_or_changed_final_context_refuses_inventory(self):
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            self.read(snapshots=[dict(self.live, save_guid='99')])
        self.manager.get.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'changed during'):
            self.read(snapshots=[self.live, dict(self.live, client_id='6')])

    def test_request_schema_and_canonical_ids_fail_before_native_reads(self):
        for change in ({'include_native_record': 1}, {'household_id': '0'}, {'save_guid': '01'}, {'extra': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.read(dict(self.argument(), **change))
        self.manager.get.assert_not_called()

    def test_dispatch_profile_guard_runs_before_absent_sim_lookup(self):
        with patch.object(test_driver, 'guard', side_effect=ValueError('wrong disposable token')):
            with self.assertRaisesRegex(ValueError, 'wrong disposable token'):
                test_driver.dispatch(self.backend, 'test_identity_inventory', SIM, '{}')
        self.backend._get_sim_info_by_id.assert_not_called()
        with patch.object(test_driver, 'guard', return_value=self.argument()), \
                patch.object(test_driver, 'snapshot', side_effect=[self.live, self.live]):
            result = test_driver.dispatch(self.backend, 'test_identity_inventory', SIM, '{}')
        self.assertTrue(result['ok'])
        self.backend._get_sim_info_by_id.assert_called_once_with(SIM)


if __name__ == '__main__':
    unittest.main()
