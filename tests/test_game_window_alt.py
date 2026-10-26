from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_window
import test_interfering_steam as focus_fixtures


class AltForegroundTests(unittest.TestCase):
    def native(self, *, desktop='Default', helper_desktop='Default', held=(), counts=(2,), opened=True):
        state = {'held': set(held), 'sent': [], 'owner': 13, 'counts': list(counts)}
        def name(handle, _index, value, _size, length):
            value.value = desktop if handle == 31 else helper_desktop
            length._obj.value = (len(value.value) + 1) * 2
            return True
        def send(count, values, size):
            import ctypes
            state['sent'].append({'size': size, 'events': [
                {'type': values[index].type, 'key': values[index].ki.wVk,
                 'scan': values[index].ki.wScan, 'flags': values[index].ki.dwFlags,
                 'time': values[index].ki.time, 'extra': values[index].ki.dwExtraInfo}
                for index in range(count)], 'structure_size': ctypes.sizeof(values[0])})
            accepted = state['counts'].pop(0)
            for event in state['sent'][-1]['events'][:accepted]:
                if event['flags'] == 2: state['held'].discard(event['key'])
                else: state['held'].add(event['key'])
            return accepted
        user = SimpleNamespace(OpenInputDesktop=Mock(return_value=31 if opened else None),
            GetThreadDesktop=Mock(return_value=32), GetUserObjectInformationW=Mock(side_effect=name),
            CloseDesktop=Mock(return_value=True), GetAsyncKeyState=Mock(side_effect=
                lambda key: 0x8000 if key in state['held'] else 0), SendInput=Mock(side_effect=send))
        kernel = SimpleNamespace(GetCurrentThreadId=Mock(return_value=1))
        return state, user, kernel

    def unlock(self, state, user, kernel):
        return game_window.unlock_foreground_alt(user, kernel,
            lambda _hwnd: state['owner'], 100, 13, lambda _seconds: None)

    def test_exact_two_event_alt_pair_releases_key_and_observes_default_desktop(self):
        state, user, kernel = self.native()
        result = self.unlock(state, user, kernel)
        self.assertTrue(result['ok']); self.assertTrue(result['release_verified'])
        self.assertEqual(result['sent_count'], 2)
        self.assertEqual(state['sent'][0]['events'], [
            {'type': 1, 'key': 0x12, 'scan': 0, 'flags': 0, 'time': 0, 'extra': 0},
            {'type': 1, 'key': 0x12, 'scan': 0, 'flags': 2, 'time': 0, 'extra': 0}])
        self.assertEqual(state['sent'][0]['size'], state['sent'][0]['structure_size'])
        user.SendInput.assert_called_once()
        self.assertEqual(user.CloseDesktop.call_count, 2)

    def test_nondefault_unreadable_or_different_helper_desktop_sends_nothing(self):
        for options in ({'desktop': 'Winlogon'}, {'desktop': 'Secure'},
                        {'helper_desktop': 'Other'}, {'opened': False}):
            with self.subTest(options=options):
                state, user, kernel = self.native(**options)
                result = self.unlock(state, user, kernel)
                self.assertFalse(result['ok']); self.assertFalse(result['attempted'])
                user.SendInput.assert_not_called()

    def test_any_held_shift_control_alt_or_win_modifier_sends_nothing(self):
        for key in (0x10, 0x11, 0x12, 0x5b, 0x5c, 0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5):
            with self.subTest(key=key):
                state, user, kernel = self.native(held=(key,))
                result = self.unlock(state, user, kernel)
                self.assertFalse(result['ok']); self.assertFalse(result['attempted'])
                self.assertEqual(result['held_modifiers_before'], [key])
                user.SendInput.assert_not_called()

    def test_partial_batch_releases_only_inserted_alt_down_and_refuses_success(self):
        state, user, kernel = self.native(counts=(1, 1))
        result = self.unlock(state, user, kernel)
        self.assertFalse(result['ok']); self.assertTrue(result['release_attempted'])
        self.assertTrue(result['release_verified'])
        self.assertEqual(result['release_sent_count'], 1)
        self.assertEqual(len(state['sent']), 2)
        self.assertEqual(state['sent'][1]['events'], [
            {'type': 1, 'key': 0x12, 'scan': 0, 'flags': 2, 'time': 0, 'extra': 0}])

    def test_zero_inserted_events_does_not_retry_or_release_a_foreign_key(self):
        state, user, kernel = self.native(counts=(0,))
        result = self.unlock(state, user, kernel)
        self.assertFalse(result['ok']); self.assertFalse(result['release_attempted'])
        user.SendInput.assert_called_once()

    def test_failed_partial_release_retains_explicit_unreleased_evidence(self):
        state, user, kernel = self.native(counts=(1, 0))
        result = self.unlock(state, user, kernel)
        self.assertFalse(result['ok']); self.assertFalse(result['release_verified'])
        self.assertEqual(result['held_modifiers_after'], [0x12])
        self.assertEqual(user.SendInput.call_count, 2)

    def test_window_owner_change_after_pair_refuses_foreground_retry(self):
        state, user, kernel = self.native()
        send = user.SendInput.side_effect
        def drift(*args):
            accepted = send(*args); state['owner'] = 99
            return accepted
        user.SendInput.side_effect = drift
        self.assertFalse(self.unlock(state, user, kernel)['ok'])

    def focus_native(self, *, counts=(2,)):
        frame, user, kernel, options = focus_fixtures.NativeFocusTests().native(
            title='Explorer', accept_focus=False)
        state, keyboard, _desktop_kernel = self.native(counts=counts)
        for key, value in vars(keyboard).items(): setattr(user, key, value)
        first = user.SetForegroundWindow.side_effect
        def foreground(hwnd):
            if state['sent'] and not state['held']:
                frame['actions'].append(('unlocked-focus', hwnd))
                frame['foreground'] = hwnd
                return True
            return first(hwnd)
        user.SetForegroundWindow.side_effect = foreground
        return frame, state, user, options

    def test_default_focus_never_uses_alt_even_when_foreground_is_refused(self):
        _frame, _state, user, options = self.focus_native()
        result = game_window.focus(13, **options)
        self.assertFalse(result['ok']); self.assertIsNone(result['foreground_alt_unlock'])
        user.SendInput.assert_not_called()

    def test_optin_pair_allows_one_final_focus_after_other_foreground_methods_fail(self):
        frame, state, user, options = self.focus_native()
        result = game_window.focus(13, allow_alt_unlock=True, **options)
        self.assertTrue(result['ok']); self.assertTrue(result['foreground_alt_unlock']['ok'])
        user.SendInput.assert_called_once()
        self.assertEqual(frame['actions'], [('focus', 100), ('focus', 100), ('unlocked-focus', 100)])
        self.assertEqual(len(state['sent']), 1)

    def test_partial_release_does_not_attempt_foreground_or_claim_game_ready(self):
        frame, _state, user, options = self.focus_native(counts=(1, 1))
        result = game_window.focus(13, allow_alt_unlock=True, **options)
        self.assertFalse(result['ok'])
        self.assertEqual(frame['actions'], [('focus', 100), ('focus', 100)])
        self.assertEqual(user.SendInput.call_count, 2)

    def test_failed_partial_alt_stays_refused_even_if_game_later_becomes_foreground(self):
        frame, state, user, options = self.focus_native(counts=(1, 1))
        def foreground():
            if len(state['sent']) == 2:
                frame['foreground'] = 100
            return frame['foreground']
        user.GetForegroundWindow.side_effect = foreground
        result = game_window.focus(13, allow_alt_unlock=True, **options)
        self.assertTrue(result['foreground_verified'])
        self.assertFalse(result['ok'])
        self.assertFalse(result['foreground_alt_unlock']['ok'])
        self.assertEqual(frame['actions'], [('focus', 100), ('focus', 100)])
        self.assertIn('no game input may follow', result['message'])
