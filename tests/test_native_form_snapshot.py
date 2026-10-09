from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_bank, sim_data, test_driver


SIM, HOUSEHOLD, GUID = '285159751289798669', '285159751289798668', '1841692672'
NAMES = {2: 'ALIEN', 4: 'VAMPIRE', 8: 'MERMAID', 16: 'WITCH', 32: 'WEREWOLF', 64: 'FAIRY'}


class NativeFormSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tracker = Obj(has_occult_type=Mock(return_value=True))
        self.sim = Obj(id=int(SIM), household_id=int(HOUSEHOLD), occult_tracker=self.tracker, skin_tone=22)
        self.forms = {flags: Obj(id=int(SIM) + flags, skin_tone=flags) for flags in (1, 2, 4, 8, 16, 32, 64)}
        self.message = Obj(sim_id=int(SIM), household_id=int(HOUSEHOLD))
        self.persistence = Obj(get_sim_proto_buff=Mock(return_value=self.message))
        self.backend = Obj(_all_occults=lambda: tuple(NAMES), _safe_name=lambda kind: NAMES[kind],
                           _form_map=lambda _tracker: self.forms, _coerce_flags=lambda flags: flags,
                           _get_current_flags=lambda _sim: 1, _v8_read_outfit_blob=lambda _sim: b'\x0a\x02\x10\x00',
                           _get_sim_info_by_id=Mock(return_value=self.sim),
                           _has_occult=Mock(side_effect=AssertionError('Mask fallback must not be used')),
                           _ensure_form=Mock(side_effect=AssertionError('Must not create forms')),
                           _restore_siminfo_payload=Mock(side_effect=AssertionError('Must not mutate appearances')),
                           services=Obj(get_persistence_service=lambda: self.persistence))
        self.live = {'ok': True, 'save_guid': GUID, 'household_id': HOUSEHOLD, 'sim': {'id': SIM}}

    def argument(self, flags=1, include=False):
        return {'form_flags': flags, 'save_guid': GUID, 'household_id': HOUSEHOLD, 'include_native_record': include}

    def run_read(self, argument=None):
        with patch.object(test_driver, 'snapshot', return_value=self.live), patch.object(form_bank, 'load') as bank:
            result = test_driver.native_form_snapshot(self.backend, self.sim, SIM, argument or self.argument())
        bank.assert_not_called()
        self.backend._has_occult.assert_not_called()
        self.backend._ensure_form.assert_not_called()
        self.backend._restore_siminfo_payload.assert_not_called()
        return result

    def test_stored_active_wrapper_and_current_live_owner_are_independent_native_reads(self):
        result = self.run_read()
        self.assertTrue(result['ok'])
        self.assertEqual(result['source'], 'native-form-map')
        self.assertTrue(result['stored_form_present'])
        self.assertEqual(result['native_wrapper_id'], str(int(SIM) + 1))
        self.assertEqual(result['appearance']['typed_payload']['skin_tone']['value'], 1)
        self.assertEqual(result['active_live_appearance']['typed_payload']['skin_tone']['value'], 22)
        self.assertNotEqual(result['appearance']['appearance_sha256'], result['active_live_appearance']['appearance_sha256'])
        self.assertFalse(result['bank_read'])
        self.assertFalse(result['appearance_mutated'])

    def test_inactive_native_read_never_returns_cached_bank_or_live_payload(self):
        result = self.run_read(self.argument(flags=16))
        self.assertEqual(result['appearance']['typed_payload']['skin_tone']['value'], 16)
        self.assertIsNone(result['active_live_appearance'])
        self.assertEqual(result['form_flags'], 16)
        self.assertEqual([row['occult'] for row in result['native_membership']], list(NAMES.values()))
        self.assertTrue(all(row['query'] == 'returned-value' and row['has_occult'] is True for row in result['native_membership']))
        self.assertEqual(self.tracker.has_occult_type.call_count, 6)

    def test_missing_inactive_native_form_is_explicit_and_not_created(self):
        self.forms.pop(16)
        result = self.run_read(self.argument(flags=16))
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'missing-native-form')
        self.assertIsNone(result['appearance'])
        self.assertIsNone(result['native_wrapper_id'])
        self.assertFalse(result['form_created'])

    def test_missing_stored_active_wrapper_reports_live_only_without_claiming_stored_presence(self):
        self.forms.pop(1)
        result = self.run_read()
        self.assertTrue(result['ok'])
        self.assertEqual(result['source'], 'current-live-only')
        self.assertFalse(result['stored_form_present'])
        self.assertEqual(result['native_wrapper_id'], SIM)

    def test_membership_api_failure_is_retained_and_never_inferred_from_mask(self):
        self.tracker.has_occult_type.side_effect = lambda kind: (_ for _ in ()).throw(RuntimeError('Native getter failed')) if kind == 16 else True
        result = self.run_read(self.argument(flags=16))
        row = next(item for item in result['native_membership'] if item['flags'] == 16)
        self.assertEqual(row['query'], 'failed')
        self.assertIsNone(row['has_occult'])
        self.assertIn('Native getter failed', row['error'])

    def test_existing_persistence_bytes_schema_are_read_without_serializing_or_saving_a_sim(self):
        self.sim.save_sim = Mock(side_effect=AssertionError('No persistence-buffer mutation'))
        native_record = {'schema': 1, 'native_sha256': 'a' * 64, 'native_base64': 'AQ==',
                         'data': {'unknown': 'kept'}, 'field_schemas': {'schema': []}}
        with patch.object(sim_data, 'catalog', return_value=native_record) as catalog:
            result = self.run_read(self.argument(include=True))
        catalog.assert_called_once_with(self.message)
        self.persistence.get_sim_proto_buff.assert_called_once_with(int(SIM))
        self.sim.save_sim.assert_not_called()
        self.assertEqual(result['native_record']['source'], 'native-existing-save-buffer')
        self.assertEqual(result['native_record']['sim_id'], SIM)
        self.assertEqual(result['native_record']['data'], native_record['data'])

    def test_wrong_native_save_household_or_sim_and_untyped_request_refuse_before_form_reads(self):
        invalid = [dict(self.argument(), form_flags=True), dict(self.argument(), form_flags=127),
                   dict(self.argument(), include_native_record=1), dict(self.argument(), household_id='different'),
                   dict(self.argument(), unexpected_field=True)]
        for argument in invalid:
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                self.run_read(argument)
        self.tracker.has_occult_type.assert_not_called()
        self.live['save_guid'] = '99'
        with self.assertRaisesRegex(ValueError, 'context differs'):
            self.run_read()
        self.tracker.has_occult_type.assert_not_called()

    def test_dispatch_checks_disposable_guard_before_inspecting_native_sim(self):
        with patch.object(test_driver, 'guard', side_effect=ValueError('wrong profile token')):
            with self.assertRaisesRegex(ValueError, 'wrong profile token'):
                test_driver.dispatch(self.backend, 'test_form_snapshot', SIM, '{}')
        self.backend._get_sim_info_by_id.assert_not_called()
        with patch.object(test_driver, 'guard', return_value=self.argument(4)), patch.object(test_driver, 'snapshot', return_value=self.live):
            result = test_driver.dispatch(self.backend, 'test_form_snapshot', SIM, '{}')
        self.assertEqual(result['form_flags'], 4)


if __name__ == '__main__':
    unittest.main()
