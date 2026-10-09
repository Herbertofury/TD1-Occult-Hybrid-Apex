from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from game_window import interfering_steam_window, focus


class InterferingSteamTests(unittest.TestCase):
    def row(self):
        return {'pid': 12, 'hwnd': 99, 'title': 'Steam',
                'image': r'C:\Games\Steam\bin\cef\cef.win64\steamwebhelper.exe'}

    def test_exact_observed_steam_main_window_is_the_only_recovery_target(self):
        self.assertTrue(interfering_steam_window(self.row(), 13))
        for field, value in [('pid', True), ('pid', 13), ('hwnd', 0), ('title', 'Steam Login'),
                             ('image', r'C:\other\steamwebhelper.exe'), ('image', r'C:\Games\Steam\steam.exe')]:
            row = self.row(); row[field] = value
            self.assertFalse(interfering_steam_window(row, 13), (field, value))

    def test_windows_case_equivalence_does_not_accept_other_paths(self):
        row = self.row(); row['image'] = row['image'].upper()
        self.assertTrue(interfering_steam_window(row, 13))
        self.assertFalse(interfering_steam_window(None, 13))


class NativeFocusTests(unittest.TestCase):
    def native(self, *, title='Steam', image=r'C:\Games\Steam\bin\cef\cef.win64\steamwebhelper.exe',
               accept_focus=True, accept_minimize=True):
        state = {'foreground': 99, 'owners': {99: 12, 100: 13}, 'clock': 0.0, 'actions': []}
        def owner(hwnd, value):
            if value is not None: value._obj.value = state['owners'].get(hwnd, 0)
            return 2 if hwnd == 99 else 3
        def inventory(callback, _parameter):
            callback(99, 0); callback(100, 0)
            return True
        def rect(_hwnd, value):
            value._obj.right, value._obj.bottom = 1280, 720
            return True
        def class_name(_hwnd, value, _size):
            value.value = 'Canvas-GL'
            return len(value.value)
        def window_title(_hwnd, value, _size):
            value.value = title
            return len(value.value)
        def path(_handle, _flags, value, _length):
            value.value = image
            return True
        def minimize(hwnd, code):
            state['actions'].append(('minimize', hwnd, code))
            return accept_minimize
        def foreground(hwnd):
            state['actions'].append(('focus', hwnd))
            if accept_focus: state['foreground'] = hwnd
            return accept_focus
        user = SimpleNamespace(**{name: Mock(side_effect=action) for name, action in {
            'GetWindowThreadProcessId': owner, 'EnumWindows': inventory, 'GetClientRect': rect,
            'GetClassNameW': class_name, 'GetWindowTextW': window_title,
            'GetForegroundWindow': lambda: state['foreground'], 'ShowWindowAsync': minimize,
            'SetForegroundWindow': foreground, 'IsWindowVisible': lambda _hwnd: True,
            'IsIconic': lambda _hwnd: False, 'ShowWindow': lambda *_args: True,
            'AttachThreadInput': lambda *_args: False}.items()})
        kernel = SimpleNamespace(GetCurrentThreadId=Mock(return_value=1), OpenProcess=Mock(return_value=44),
                                 QueryFullProcessImageNameW=Mock(side_effect=path), CloseHandle=Mock(return_value=True))
        def pause(seconds): state['clock'] += seconds
        return state, user, kernel, {'user': user, 'kernel': kernel, 'pause': pause, 'monotonic': lambda: state['clock']}

    def test_verified_steam_is_minimized_before_even_an_accepted_first_focus(self):
        state, user, kernel, options = self.native()
        result = focus(13, **options)
        self.assertTrue(result['foreground_verified'])
        self.assertEqual(state['actions'], [('minimize', 99, 6), ('focus', 100)])
        self.assertEqual(result['window']['hwnd'], 100)
        self.assertEqual(result['foreground_recovery']['pid'], 12)
        user.EnumWindows.assert_called_once(); user.ShowWindowAsync.assert_called_once_with(99, 6)
        kernel.CloseHandle.assert_called_once_with(44)

    def test_unrelated_foreground_title_or_executable_is_never_minimized(self):
        for change in ({'title': 'Codex'}, {'title': 'Steam Login'}, {'image': r'C:\other\steamwebhelper.exe'}):
            with self.subTest(change=change):
                state, user, _kernel, options = self.native(**change)
                result = focus(13, **options)
                self.assertTrue(result['foreground_verified'])
                self.assertEqual(state['actions'], [('focus', 100)])
                self.assertIsNone(result['foreground_recovery']); user.ShowWindowAsync.assert_not_called()

    def test_changed_selected_game_or_steam_owner_refuses_minimization(self):
        for changed in (99, 100):
            with self.subTest(changed=changed):
                state, user, kernel, options = self.native()
                read = kernel.QueryFullProcessImageNameW.side_effect
                def drift(*args):
                    value = read(*args); state['owners'][changed] = 42
                    return value
                kernel.QueryFullProcessImageNameW.side_effect = drift
                if changed == 100:
                    with self.assertRaisesRegex(ValueError, 'selected Sims window owner changed'):
                        focus(13, **options)
                    user.SetForegroundWindow.assert_not_called()
                else:
                    result = focus(13, **options)
                    self.assertTrue(result['foreground_verified'])
                user.ShowWindowAsync.assert_not_called(); user.EnumWindows.assert_called_once()

    def test_failed_minimization_or_late_focus_failure_never_repeats_recovery(self):
        for accepted in (True, False):
            with self.subTest(accepted=accepted):
                state, user, _kernel, options = self.native(accept_focus=False, accept_minimize=accepted)
                result = focus(13, **options)
                self.assertFalse(result['foreground_verified']); self.assertFalse(result['ok'])
                self.assertEqual(result['window']['hwnd'], 100)
                self.assertEqual(result['foreground_recovery']['accepted'], accepted)
                user.ShowWindowAsync.assert_called_once_with(99, 6)
                self.assertEqual(sum(action[0] == 'minimize' for action in state['actions']), 1)

    def test_foreground_switch_during_identity_read_cannot_minimize_old_window(self):
        state, user, kernel, options = self.native()
        read = kernel.QueryFullProcessImageNameW.side_effect
        def drift(*args):
            value = read(*args); state['foreground'] = 98
            return value
        kernel.QueryFullProcessImageNameW.side_effect = drift
        result = focus(13, **options)
        self.assertTrue(result['foreground_verified']); user.ShowWindowAsync.assert_not_called()
