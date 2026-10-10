"""Offline regression for the retained EA modal OCR; never sends native input."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ea_native_permission import dialog_button


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
