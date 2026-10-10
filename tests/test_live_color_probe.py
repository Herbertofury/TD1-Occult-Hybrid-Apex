import base64
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from live_color_probe import color_scope, expected_color, verify_color_owners


def v(number):
    result = bytearray()
    while number >= 128:
        result.append((number & 127) | 128)
        number >>= 7
    result.append(number)
    return bytes(result)


def blob(number, raw):
    return v(number * 8 + 2) + v(len(raw)) + raw


def outfit(category, colors, unknown=b'\xA0\x06\x07'):
    return (v(8) + v(category + 100) + v(16) + v(category)
            + blob(5, blob(1, v(101) + v(102)))
            + blob(12, blob(1, b''.join(v(item) for item in colors))) + unknown)


def packed(children):
    return {'__outfits__': {'kind': 'protobuf', 'value': base64.b64encode(
            b''.join(blob(1, child) for child in children) + blob(123, b'unknown-list')).decode()},
            'skin_tone': {'kind': 'value', 'value': 7}}


class LiveColorProofTests(unittest.TestCase):
    def test_active_and_stored_native_owners_are_verified_independently(self):
        original = packed([outfit(9, [1, 2])])
        accepted = packed([outfit(9, [1, 99])])
        def snapshot(active, live, stored):
            return {'sim': {'id': '7', 'current_form': active,
                    'full_appearance': {'typed_payload': copy.deepcopy(live)},
                    'form_appearances': [{'flags': lane, 'appearance': {
                        'typed_payload': copy.deepcopy(fields)}} for lane, fields in stored.items()]}}
        before = snapshot(2, original, {2: original, 4: original})
        after = snapshot(2, accepted, {2: original, 4: original})
        self.assertTrue(verify_color_owners(before, after, 2, '0:29:1', '0000000000000063'))
        for bad in (snapshot(2, original, {2: accepted, 4: original}),
                    snapshot(2, accepted, {2: original, 4: accepted}),
                    snapshot(4, accepted, {2: original, 4: original})):
            with self.assertRaises(ValueError):
                verify_color_owners(before, bad, 2, '0:29:1', '0000000000000063')
        before = snapshot(4, original, {2: original, 4: original})
        after = snapshot(4, original, {2: accepted, 4: original})
        self.assertTrue(verify_color_owners(before, after, 2, '0:29:1', '0000000000000063'))
        with self.assertRaisesRegex(ValueError, 'distinct Live owner'):
            verify_color_owners(before, snapshot(4, accepted, {2: accepted, 4: original}),
                                2, '0:29:1', '0000000000000063')

    def test_exact_q14_all_channels_and_unedited_bits(self):
        editor = {'color_hex': '4000000000000000', 'channels': {
            name: {'enabled': True, 'min': -.5 if name != 'opacity' else .2, 'max': 1}
            for name in ('brightness', 'saturation', 'hue', 'opacity')}}
        self.assertEqual(expected_color(editor, {'hue': .35, 'saturation': -.15,
                                                'brightness': .25, 'opacity': .25}),
                         '10001666F6661000')
        self.assertEqual(expected_color(editor, {'brightness': .25}), '4000000000001000')
        with self.assertRaises(ValueError):
            expected_color(editor, {'opacity': .1})
        with self.assertRaises(ValueError):
            expected_color(editor, {'hue': float('nan')})

    def test_target_uses_native_index_before_category_normalization(self):
        before = packed([outfit(9, [1, 2]), outfit(0, [3, 4])])
        after = packed([outfit(9, [1, 99]), outfit(0, [3, 4])])
        self.assertTrue(color_scope(before, after, '0:29:1', '0000000000000063'))
        for changed in (packed([outfit(9, [88, 99]), outfit(0, [3, 4])]),
                        packed([outfit(9, [1, 99]), outfit(0, [3, 77])]),
                        packed([outfit(9, [1, 99], b'\xA0\x06\x08'), outfit(0, [3, 4])])):
            with self.assertRaises(ValueError):
                color_scope(before, changed, '0:29:1', '0000000000000063')
        changed = copy.deepcopy(after)
        changed['skin_tone']['value'] = 8
        with self.assertRaisesRegex(ValueError, 'skin_tone'):
            color_scope(before, changed, '0:29:1', '0000000000000063')

    def test_unknown_list_fields_and_ambiguous_outfit_identity_are_refused(self):
        before = packed([outfit(9, [1, 2]), outfit(0, [3, 4])])
        after = packed([outfit(9, [1, 99]), outfit(0, [3, 4])])
        after['__outfits__']['value'] = base64.b64encode(base64.b64decode(
            after['__outfits__']['value']).replace(b'unknown-list', b'changed-list')).decode()
        with self.assertRaisesRegex(ValueError, 'unknown list field'):
            color_scope(before, after, '0:29:1', '0000000000000063')
        before = packed([outfit(9, [1, 2]), outfit(9, [1, 2])])
        after = packed([outfit(9, [1, 99]), outfit(9, [1, 99])])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            color_scope(before, after, '0:29:1', '0000000000000063')


if __name__ == '__main__':
    unittest.main()
