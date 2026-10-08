from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_controls, overlay_loader, test_driver


class NativeControlTests(unittest.TestCase):
    def setUp(self):
        native_controls._RESULTS.clear()
        self.backend = Obj(__file__='fixed-script', services=Mock(side_effect=AssertionError('Game service read')))

    def test_response_loss_does_not_repeat_native_input_or_touch_game_services(self):
        with patch.object(test_driver, 'guard', return_value={'command': 1}), \
             patch.dict(sys.modules, {'paths': Obj(DLL_PATH='game-dlls')}), \
             patch.object(overlay_loader, 'input_event', return_value={'ok': True}) as submit:
            first = native_controls.dispatch(self.backend, 'test_input', 'typed', 'a' * 32)
            second = native_controls.dispatch(self.backend, 'test_input', 'typed', 'a' * 32)
            self.assertEqual(first, second)
            submit.assert_called_once()
            self.backend.services.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'reused'):
                native_controls.dispatch(self.backend, 'test_input', 'changed', 'a' * 32)

    def test_wrong_token_and_gameplay_actions_refuse_before_native_calls(self):
        with patch.object(test_driver, 'guard', side_effect=ValueError('wrong token')), patch.object(overlay_loader, 'start') as start:
            with self.assertRaisesRegex(ValueError, 'wrong token'):
                native_controls.dispatch(self.backend, 'overlay_start', 'typed', 'b' * 32)
            with self.assertRaisesRegex(ValueError, 'Unsupported'):
                native_controls.dispatch(self.backend, 'add_all', 'typed', 'c' * 32)
            start.assert_not_called()
