"""Native-only selection fixtures; no installed game/profile is controlled."""
import copy
import json
from pathlib import Path
import sys
import threading
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_form_select, form_bank, form_appearance as appearance, test_driver, cas_ui
from test_form_bank_seal import SealFixture, SIM, HH, GUID


class NativeFormSelectTests(SealFixture):
    def setUp(self):
        super().setUp()
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.tracker.has_occult_type = Mock(return_value=True)
        self.tracker.switch_to_occult_type = Mock(side_effect=self.native_switch)
        self.tracker._pending_occult_type = 2
        self.tracker.set_pending_occult_type = Mock(side_effect=lambda value: setattr(self.tracker, '_pending_occult_type', value))
        self.bank['records'][self.key]['runtime_pid'] = self.identity['pid'] - 99
        self.bank['records'][self.key]['bank']['1']['physique']['value'] = 'OLD UNCERTIFIED HUMAN'
        self.bank_path.write_text(json.dumps(self.bank))
        self.original_bank = copy.deepcopy(self.bank['records'][self.key]['bank'])
        self.original_save = self.slot.read_bytes()

    def argument(self, **overrides):
        return dict(form_flags=1, expected_current_form_flags=64, save_guid=GUID,
                    household_id=HH, ensure_witch_owner=True, **overrides)

    def native_switch(self, kind):
        pending = form_bank.load(self.bank_path)['records'][self.key]['switch_pending']
        self.assertEqual(pending['state'], 'native-only-intent')
        self.assertTrue(pending['native_switch_attempted'])
        self.assertEqual(pending['bank_sha256'], __import__('apex_core.form_bank_seal', fromlist=['_hash'])._hash(self.original_bank))
        self.sim.current_occult_types = kind
        # This is the native Human wrapper, never the OLD UNCERTIFIED lane.
        for name, value in vars(self.forms[kind]).items():
            if name != 'id': setattr(self.sim, name, value)

    def invoke(self, argument=None):
        return native_form_select.select(self.backend, self.sim, SIM, argument or self.argument())

    def test_native_switch_and_existing_witch_do_not_restore_old_bank_or_write_save(self):
        self.backend._restore_siminfo_payload = Mock(side_effect=AssertionError('No bank appearance may be restored'))
        result = self.invoke()
        self.assertTrue(result['ok']); self.assertTrue(result['native_switch_attempted'])
        self.assertEqual(result['native_after']['active_form'], 1)
        self.assertEqual(self.sim.physique, 'independent-1')
        self.assertFalse(result['witch_owner_created']); self.assertFalse(result['bank_appearance_restored'])
        self.tracker.switch_to_occult_type.assert_called_once_with(1)
        self.tracker._generate_sim_info.assert_not_called(); self.backend._restore_siminfo_payload.assert_not_called()
        self.assertEqual(form_bank.load(self.bank_path)['records'][self.key]['bank'], self.original_bank)
        self.assertEqual(self.slot.read_bytes(), self.original_save)
        self.assertEqual(self.tracker.has_occult_type.call_count, 12)
        self.assertIsNone(self.tracker._pending_occult_type)
        self.tracker.set_pending_occult_type.assert_called_once_with(None)

    def test_only_missing_explicit_witch_is_constructed_from_tuned_native_false_contract(self):
        self.forms.pop(16)
        result = self.invoke()
        self.assertTrue(result['witch_owner_created'])
        self.tracker._generate_sim_info.assert_called_once_with(16, generate_new=False)
        self.assertEqual(self.forms[16].physique, 'native incomplete Witch')
        self.assertNotEqual(self.forms[16].physique, appearance.decode(self.original_bank['16']['physique']))
        self.assertEqual(self.writes, [])

    def test_absent_witch_without_option_is_explicit_and_never_created(self):
        self.forms.pop(16)
        argument = self.argument(); argument['ensure_witch_owner'] = False
        result = self.invoke(argument)
        self.assertFalse(result['witch_owner_created']); self.assertNotIn('16', result['native_after']['stored'])
        self.tracker._generate_sim_info.assert_not_called()

    def test_unknown_context_wrong_form_owner_thread_or_membership_refuses_before_any_intent(self):
        original = self.bank_path.read_bytes()
        invalid = [dict(self.argument(), form_flags=4), dict(self.argument(), expected_current_form_flags=True),
                   dict(self.argument(), ensure_witch_owner=1), dict(self.argument(), household_id='1'),
                   dict(self.argument(), expected_current_form_flags=1), dict(self.argument(), unexpected=True)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError): self.invoke(value)
        self.backend._APEX_GAME_THREAD_IDENT = -1
        with self.assertRaisesRegex(ValueError, 'owner thread'): self.invoke()
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.tracker.has_occult_type.return_value = False
        with self.assertRaisesRegex(ValueError, 'membership'): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(), original)
        self.tracker.switch_to_occult_type.assert_not_called(); self.tracker._generate_sim_info.assert_not_called()

    def test_failure_retains_native_intent_and_second_request_never_replays_switch(self):
        self.tracker.switch_to_occult_type.side_effect = RuntimeError('native response lost')
        with self.assertRaisesRegex(RuntimeError, 'response lost'): self.invoke()
        pending = form_bank.load(self.bank_path)['records'][self.key]['switch_pending']
        self.assertEqual(pending['state'], 'native-only-unresolved'); self.assertFalse(pending['retry_safe'])
        self.assertEqual(pending['native_before']['active_form'], 64)
        with self.assertRaisesRegex(ValueError, '(?i)pending'): self.invoke()
        self.tracker.switch_to_occult_type.assert_called_once_with(1)
        self.assertEqual(self.writes, []); self.assertEqual(self.slot.read_bytes(), self.original_save)

    def test_unsupported_witch_tuning_and_failed_journal_refuse_before_native_selection(self):
        self.forms.pop(16); self.tracker.OCCULT_DATA.pop(16)
        original = self.bank_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'unsupported'): self.invoke()
        self.assertEqual(self.bank_path.read_bytes(), original)
        self.tracker.OCCULT_DATA[16] = object()
        with patch.object(form_bank, 'save', side_effect=OSError('evidence disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'): self.invoke()
        self.tracker.switch_to_occult_type.assert_not_called(); self.tracker._generate_sim_info.assert_not_called()

    def test_wrong_or_active_cas_ownership_refuses_without_native_writes(self):
        cas_ui._PEERS['native'] = {'sim_id': SIM}
        with self.assertRaisesRegex(ValueError, 'CAS'): self.invoke()
        cas_ui._PEERS.clear(); cas_ui._RECORDS['intent'] = {'state': 'accept-unresolved', 'operation': 'accept'}
        with self.assertRaisesRegex(ValueError, 'CAS'): self.invoke()
        self.tracker.switch_to_occult_type.assert_not_called()

    def test_dispatch_disposable_guard_precedes_native_helper(self):
        with patch.object(test_driver, 'guard', side_effect=ValueError('wrong disposable token')):
            with self.assertRaisesRegex(ValueError, 'token'):
                test_driver.dispatch(self.backend, 'test_native_form_select', SIM, '{}')
        self.tracker.switch_to_occult_type.assert_not_called()
