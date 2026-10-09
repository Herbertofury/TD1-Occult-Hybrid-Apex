from pathlib import Path
import importlib
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))


class PhoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Picker:
            def on_choice_selected(self, choice):
                self.legacy_calls.append(choice)
            def picker_rows_gen(self, target, context, **kwargs):
                yield from self.fixture_rows
        modules = {
            'apex_hybrid': Obj(), 'apex_hybrid.CoreLib': Obj(),
            'apex_hybrid.CoreLib.TD1_OccultHybrid_MenuUI': Obj(TD1OccultHybridMenuUIPicker=Picker,
                MenuUIBaseIconsEnums=Obj(SETTINGS_VARIATION='settings', MENU_PLACEHOLDER='menu',
                                        MENU_UNKNOWN='unknown'), parse_ui_icon_enum_to_data=lambda v: v),
            'sims4.localization': Obj(LocalizationHelperTuning=Obj(get_raw_text=lambda value: value)),
            'sims4.utils': Obj(flexmethod=lambda f: f),
            'ui': Obj(), 'ui.ui_dialog_picker': Obj(BasePickerRow=Obj),
            'ui.ui_dialog_notification': Obj(UiDialogNotification=Obj())}
        with patch.dict(sys.modules, modules):
            cls.phone = importlib.import_module('apex_core.phone_interactions')

    def backend(self):
        return Obj(_APEX7_SETTINGS={'scan_after_apex_commands': True}, _MCCC_CAS_SHIELD_ENABLED=False,
            _get_sim_info_by_id=lambda _id: Obj(occult_tracker='tracker'), _occult_by_name=lambda name: name,
            _has_occult=lambda _tracker, name: name == 'VAMPIRE', run_action=Mock(return_value={'ok': True}))

    def test_stale_setting_click_cannot_toggle_a_newer_setting(self):
        backend = self.backend()
        offered = {r[0] for r in self.phone.catalog(backend, '5', 'settings')}
        self.assertIn('action:drift_scan_after_commands_off', offered)
        backend._APEX7_SETTINGS['scan_after_apex_commands'] = False
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.phone.select(backend, '5', 'apex:action:drift_scan_after_commands_off')
        backend.run_action.assert_not_called()

    def test_form_membership_and_history_share_canonical_dispatcher(self):
        backend = self.backend()
        self.phone.select(backend, '5', 'apex:occult:switch:VAMPIRE')
        backend.run_action.assert_called_once_with('switch', sim_id='5', occult='VAMPIRE')
        backend.run_action.reset_mock()
        self.phone.select(backend, '5', 'apex:action:human')
        backend.run_action.assert_called_once_with('human', sim_id='5')
        backend.run_action.reset_mock()
        self.phone.select(backend, '5', 'apex:action:studio_undo')
        backend.run_action.assert_called_once_with('studio_undo', sim_id='5')
        backend.run_action.reset_mock()
        self.phone.select(backend, '5', 'apex:action:cas_bank_status')
        backend.run_action.assert_called_once_with('cas_bank_status', sim_id='5')
        backend.run_action.reset_mock()
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.phone.select(backend, '5', 'apex:action:cas_session_finish')
        backend.run_action.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.phone.select(backend, '5', 'apex:action:eval')

    def test_deferred_live_probe_opens_no_pausing_notification_until_its_game_thread_callback(self):
        picker = self.phone.ApexPhoneMenu()
        picker.sim = Obj(sim_info=Obj(id=5))
        picker._present_apex_result = Mock()
        backend = self.backend()
        with patch.dict(sys.modules, {'td1_occult_hybrid_apex': backend}), patch.object(
                self.phone, 'select', return_value={'ok': True, 'pending': True}) as selected:
            picker.on_choice_selected('apex:cas:observe')
        picker._present_apex_result.assert_not_called()
        callback = selected.call_args.kwargs['callback']
        callback({'ok': True, 'page': 'cas_review'})
        picker._present_apex_result.assert_called_once_with({'ok': True, 'page': 'cas_review'})

    def choice(self, *identities):
        return Obj(continuation=tuple(Obj(affordance=Obj(guid64=identity)) for identity in identities))

    def test_old_restore_and_edit_choices_route_to_modern_review_before_any_legacy_continuation(self):
        picker = self.phone.ApexPhoneMenu()
        picker.legacy_calls = []
        picker._present_apex_result = Mock()
        for identity, page in ((self.phone._LEGACY_RESTORE, 'cas_review'), (self.phone._LEGACY_CAS_EDIT, 'studio')):
            picker.on_choice_selected(self.choice(identity))
            self.assertEqual(picker._present_apex_result.call_args.args[0]['page'], page)
            self.assertIs(picker._present_apex_result.call_args.args[0]['legacy_mutation_submitted'], False)
        self.assertEqual(picker.legacy_calls, [])

    def test_mixed_unknown_and_stale_legacy_continuations_fail_closed_but_verified_settings_still_delegate(self):
        picker = self.phone.ApexPhoneMenu()
        picker.legacy_calls = []
        picker._present_apex_result = Mock()
        for choice in (self.choice(16827766500387554810, self.phone._LEGACY_CAS_EDIT),
                       self.choice(2**64 - 1), Obj(continuation=[])):
            picker.on_choice_selected(choice)
            self.assertIs(picker._present_apex_result.call_args.args[0]['ok'], False)
        self.assertEqual(picker.legacy_calls, [])
        settings = self.choice(16827766500387554810)
        picker.on_choice_selected(settings)
        self.assertEqual(picker.legacy_calls, [settings])

    def test_root_and_rewired_bypass_hide_unsafe_rows_and_keep_harmless_native_settings(self):
        picker = self.phone.ApexPhoneMenu()
        settings = self.choice(16827766500387554810)
        picker.fixture_rows = [Obj(tag=self.choice(self.phone._LEGACY_RESTORE)),
            Obj(tag=self.choice(self.phone._LEGACY_CAS_EDIT)), Obj(tag=settings)]
        context = Obj(sim=Obj(sim_info=Obj(id=5)))
        with patch.dict(sys.modules, {'td1_occult_hybrid_apex': self.backend()}):
            rows = list(self.phone.ApexPhoneMenu.picker_rows_gen(self.phone.ApexPhoneMenu, picker, None, context))
        self.assertEqual([row.tag for row in rows if not isinstance(row.tag, str)], [settings])
        self.assertTrue(any(row.tag == 'apex:page:studio' for row in rows))

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('apex_core.phone_interactions', None)
