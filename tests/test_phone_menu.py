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
        modules = {
            'apex_hybrid': Obj(), 'apex_hybrid.CoreLib': Obj(),
            'apex_hybrid.CoreLib.TD1_OccultHybrid_MenuUI': Obj(TD1OccultHybridMenuUIPicker=type('Picker', (), {}),
                MenuUIBaseIconsEnums=Obj(), parse_ui_icon_enum_to_data=lambda v: v),
            'sims4.localization': Obj(LocalizationHelperTuning=Obj()),
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
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.phone.select(backend, '5', 'apex:action:eval')

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('apex_core.phone_interactions', None)
