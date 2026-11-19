from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ea_native_permission import NativeEA


class EABackgroundPermissionTests(unittest.TestCase):
    def setUp(self):
        self.native = NativeEA.__new__(NativeEA)
        self.row = dict(hwnd=77, pid=42, width=635, height=287)
        self.native.identity = Mock(return_value=dict(self.row))
        self.native.user = Mock()
        self.native.user.SetForegroundWindow.side_effect = AssertionError('Foreground ownership changed.')
        self.native.user.GetForegroundWindow.side_effect = AssertionError('Foreground ownership required.')
        self.native.user.SetCursorPos.side_effect = AssertionError('Cursor moved.')
        self.native.user.SendMessageTimeoutW.return_value = 1

    def test_exact_dialog_receives_one_addressed_down_up_without_focus_or_cursor(self):
        with patch('ea_native_permission.time.sleep'):
            self.native.click(self.row, (468, 206))
        calls = self.native.user.SendMessageTimeoutW.call_args_list
        self.assertEqual([(c.args[0], c.args[1], c.args[2], c.args[3]) for c in calls],
                         [(77, 0x201, 1, 468 | (206 << 16)), (77, 0x202, 0, 468 | (206 << 16))])
        self.native.user.SetForegroundWindow.assert_not_called()
        self.native.user.GetForegroundWindow.assert_not_called()
        self.native.user.SetCursorPos.assert_not_called()

    def test_changed_window_and_outside_point_refuse_before_input(self):
        for changed, point in ((True, (468, 206)), (False, (635, 206))):
            self.native.identity.return_value = dict(self.row, pid=13) if changed else self.row
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.native.click(self.row, point)
        self.native.user.SendMessageTimeoutW.assert_not_called()

    def test_failed_down_or_release_is_unverified_and_not_retried(self):
        self.native.user.SendMessageTimeoutW.side_effect = [0]
        with self.assertRaises(OSError): self.native.click(self.row, (468, 206))
        self.assertEqual(self.native.user.SendMessageTimeoutW.call_count, 1)
        self.native.user.SendMessageTimeoutW.reset_mock()
        self.native.user.SendMessageTimeoutW.side_effect = [1, 0]
        with patch('ea_native_permission.time.sleep'), self.assertRaises(OSError):
            self.native.click(self.row, (468, 206))
        self.assertEqual(self.native.user.SendMessageTimeoutW.call_count, 2)


if __name__ == '__main__':
    unittest.main()
