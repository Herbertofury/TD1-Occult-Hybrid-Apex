"""Offline regression for the retained EA modal OCR; never sends native input."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import ctypes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ea_native_permission import dialog_button, NativeEA, blank_rgb


def retained_modal():
    def line(text, x, y, width, height):
        return {'text': text, 'words': [{'text': text, 'x': x, 'y': y, 'width': width, 'height': height}]}
    return {'ok': True, 'width': 635, 'height': 287, 'lines': [
        line('This game requires permissions', 50, 71.5, 379, 24.5),
        line('This game requires administrative privileges. Do you want to', 50, 114.5, 515.5, 18.5),
        line('grant access and launch the game?', 50.5, 138, 300.5, 18.5),
        line('0K', 459, 201, 18.5, 9.5),
        line('CLOSE', 523.5, 201, 45.5, 9.5)]}


class PermissionRecognitionTests(unittest.TestCase):
    def test_blank_qt_bitmap_ignores_alpha_but_never_accepts_nonuniform_rgb(self):
        self.assertTrue(blank_rgb(b'\0\0\0\0'+b'\0\0\0\xff'))
        self.assertTrue(blank_rgb(b'\x20\x30\x40\xff'*16))
        self.assertFalse(blank_rgb(b'\0\0\0\xff'+b'\0\x01\0\xff'))
        self.assertFalse(blank_rgb(b''));self.assertFalse(blank_rgb(b'bad'))
    def test_visible_client_fallback_refuses_occlusion_and_never_activates_a_window(self):
        native=NativeEA.__new__(NativeEA);row=dict(hwnd=42,width=635,height=287)
        native.identity=lambda hwnd:dict(row)
        native.user=Mock();native.user.ClientToScreen.return_value=True
        native.user.GetForegroundWindow.return_value=42
        native.user.WindowFromPoint.return_value=99;native.user.GetAncestor.return_value=99
        with self.assertRaisesRegex(ValueError,'obscured'):native.visible_client(row)
        native.user.GetAncestor.return_value=42;native.visible_client(row)
        native.user.SetForegroundWindow.assert_not_called()
        native.user.ShowWindowAsync.assert_not_called()
        native.user.GetForegroundWindow.return_value=99
        with self.assertRaisesRegex(ValueError,'behind another app'):native.visible_client(row)
    def minimized_native(self):
        native = NativeEA.__new__(NativeEA)
        native.pids = {123}
        native.owner = Mock(return_value=123)
        def text(_hwnd, target, _length): target.value = 'EA'; return 2
        def kind(_hwnd, target, _length): target.value = 'Qt5152QWindowOwnDCIcon'; return 24
        def placement(_hwnd, target):
            place = target._obj
            self.assertEqual(place.length, ctypes.sizeof(place))
            place.show = 2
            place.normal.left, place.normal.top = 4162, 552
            place.normal.right, place.normal.bottom = 4797, 839
            return True
        native.user = SimpleNamespace(GetWindowTextW=Mock(side_effect=text),
            GetClassNameW=Mock(side_effect=kind), GetWindowPlacement=Mock(side_effect=placement),
            IsWindowVisible=Mock(return_value=True), IsIconic=Mock(return_value=True),
            ShowWindowAsync=Mock(return_value=True))
        return native

    def test_minimized_modal_restores_without_activation_then_requires_normal_identity(self):
        native = self.minimized_native()
        before = native.minimized_identity(99)
        restored = {'pid': 123, 'hwnd': 99, 'class': before['class'], 'width': 635, 'height': 287}
        native.identity = Mock(return_value=restored)
        native.user.IsIconic.side_effect = [True, False]
        result = native.restore_minimized(before, 110, clock=lambda: 100)
        self.assertEqual(result, restored)
        native.user.ShowWindowAsync.assert_called_once_with(99, 4)
        self.assertEqual(before['normal'], [4162, 552, 4797, 839])

    def test_minimized_wrong_owner_changed_or_expired_window_never_restores(self):
        for variant in ('owner', 'hidden', 'not-minimized', 'wrong-title', 'main-size', 'changed', 'expired'):
            native = self.minimized_native()
            before = native.minimized_identity(99)
            if variant == 'owner': native.owner.return_value = 124
            elif variant == 'hidden': native.user.IsWindowVisible.return_value = False
            elif variant == 'not-minimized': native.user.IsIconic.return_value = False
            elif variant == 'wrong-title': native.user.GetWindowTextW.side_effect = lambda _h, b, _l: setattr(b, 'value', 'Other app')
            elif variant == 'main-size':
                def large(_hwnd, target):
                    target._obj.show = 2; target._obj.normal.right = 2601; target._obj.normal.bottom = 2601
                    return True
                native.user.GetWindowPlacement.side_effect = large
            elif variant == 'changed': before['normal'][0] += 1
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                native.restore_minimized(before, 100 if variant == 'expired' else 110, clock=lambda: 100)
            native.user.ShowWindowAsync.assert_not_called()

    def test_minimized_full_ea_window_is_a_capture_candidate_without_permission_authority(self):
        native = self.minimized_native()
        def full(_hwnd, target):
            target._obj.show = 2; target._obj.normal.right = 1280; target._obj.normal.bottom = 1376
            return True
        native.user.GetWindowPlacement.side_effect = full
        row = native.minimized_identity(99)
        self.assertEqual(row['normal'], [0, 0, 1280, 1376])
        native.user.ShowWindowAsync.assert_not_called()
        self.assertNotIn('acknowledged', row)

    def test_retained_zero_k_ocr_variant_resolves_only_measured_ok_word_center(self):
        # ea-broker-1791451035412101700.bmp: exact modal wording; OCR emits 0K.
        value = retained_modal()
        self.assertEqual(dialog_button(value), (468, 206))
        value['lines'][3]['text'] = value['lines'][3]['words'][0]['text'] = 'OK'
        self.assertEqual(dialog_button(value), (468, 206))

    def test_missing_or_duplicate_buttons_never_choose_a_guessed_position(self):
        for change in ('missing-ok', 'missing-close', 'duplicate-ok', 'duplicate-close', 'word-mismatch'):
            value = retained_modal()
            if change == 'missing-ok': value['lines'].pop(3)
            elif change == 'missing-close': value['lines'].pop()
            elif change == 'duplicate-ok': value['lines'].append(deepcopy(value['lines'][3]))
            elif change == 'duplicate-close': value['lines'].append(deepcopy(value['lines'][4]))
            else: value['lines'][3]['words'][0]['text'] = 'OK'
            with self.subTest(change=change), self.assertRaises(ValueError): dialog_button(value)

    def test_only_explicit_zero_o_variant_with_complete_exact_permission_wording_is_supported(self):
        for button in ('O K', '0 K', '0X', '0k?', 'CONFIRM'):
            value = retained_modal(); value['lines'][3]['text'] = value['lines'][3]['words'][0]['text'] = button
            with self.subTest(button=button), self.assertRaises(ValueError): dialog_button(value)
        for changed in ('body', 'heading', 'access-error'):
            value = retained_modal()
            if changed == 'body': value['lines'][2]['text'] = 'grant access and erase the game?'
            elif changed == 'heading': value['lines'][0]['text'] = 'This game requires permissions again'
            else:
                value['lines'][0]['text'] = 'You don’t have access'
                value['lines'][1]['text'] = 'Log in to a different account or restart the app to try again.'
            with self.subTest(changed=changed), self.assertRaises(ValueError): dialog_button(value)

    def test_wrong_row_overlapping_outside_or_nonfinite_bounds_refuse(self):
        for change in ('below', 'above', 'overlap', 'outside', 'nan', 'bool', 'untyped-width'):
            value = retained_modal(); word = value['lines'][3]['words'][0]
            if change == 'below': word['y'] = 250
            elif change == 'above': word['y'] = 50
            elif change == 'overlap': word['x'] = 530
            elif change == 'outside': word['x'] = 630
            elif change == 'nan': word['x'] = float('nan')
            elif change == 'bool': word['x'] = True
            else: value['width'] = '635'
            with self.subTest(change=change), self.assertRaises(ValueError): dialog_button(value)


if __name__ == '__main__':
    unittest.main()
