from pathlib import Path
import random
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import color_shift
from apex_core.cas_catalog import slider_metadata
from casp_fixture import casp


class ColorShiftTests(unittest.TestCase):
    def test_layout_matches_independent_signed_struct_decoder(self):
        generator = random.Random(632)
        for raw in [0, 2**64-1, 1 << 62] + [generator.getrandbits(64) for _ in range(3000)]:
            lanes = struct.unpack('<4h', struct.pack('<Q', raw))
            self.assertEqual(color_shift.decode(raw), dict(zip(color_shift.CHANNELS, [lane / 16384 for lane in lanes])))
        self.assertEqual(color_shift.decode(1 << 62), dict(brightness=0, saturation=0, hue=0, opacity=1))

    def test_edit_preserves_other_lanes_and_negative_extremes(self):
        bounds = {name: dict(min=-2, max=32767 / 16384, enabled=True) for name in color_shift.CHANNELS}
        for position, name in enumerate(color_shift.CHANNELS):
            for signed in (-32768, -16384, -1, 0, 1, 16384, 32767):
                result = color_shift.replace(2**64-1, {name: signed / 16384}, bounds)
                lanes = list(struct.unpack('<4h', struct.pack('<Q', result)))
                self.assertEqual(lanes, [-1 if index != position else signed for index in range(4)])

    def test_disabled_nonfinite_unsupported_and_out_of_resource_bounds_fail(self):
        ranges = slider_metadata(casp())['ranges']
        for edits in ({'hue': float('nan')}, {'hue': float('inf')}, {'hue': True}, {'hue': 0.75}, {'unknown': 0}):
            with self.assertRaises(ValueError):
                color_shift.replace(1 << 62, edits, ranges)
        ranges['hue']['enabled'] = False
        with self.assertRaisesRegex(ValueError, 'disabled'):
            color_shift.replace(1 << 62, {'hue': 0.1}, ranges)

    def test_current_and_prior_known_headers_with_counts_are_parsed(self):
        for version in (44, 45, 46, 47, 48, 49, 50, 51, 52):
            metadata = slider_metadata(casp(version))
            self.assertEqual(metadata['version'], version)
            self.assertEqual(metadata['body_type'], 7)
            self.assertEqual(metadata['part_name'], 'Apex test part')
            self.assertEqual(metadata['ranges']['brightness']['min'], -0.125)
            self.assertEqual(metadata['ranges']['saturation']['max'], 0.75)

    def test_truncation_new_layout_reference_overlap_and_bad_metadata_fail(self):
        raw = casp()
        for count in (0, 63, 64, 150, len(raw)-1):
            with self.assertRaises(ValueError): slider_metadata(raw[:count])
        damaged = bytearray(raw); struct.pack_into('<I', damaged, 0, 53)
        with self.assertRaisesRegex(ValueError, 'verified'): slider_metadata(bytes(damaged))
        struct.pack_into('<I', damaged, 0, 52); struct.pack_into('<I', damaged, 4, 60)
        with self.assertRaisesRegex(ValueError, 'truncated|overlaps'): slider_metadata(bytes(damaged))
        damaged = bytearray(raw); struct.pack_into('<f', damaged, len(raw)-5, float('nan'))
        with self.assertRaisesRegex(ValueError, 'invalid'): slider_metadata(bytes(damaged))
        self.assertFalse(slider_metadata(casp(step=0))['ranges']['hue']['enabled'])


if __name__ == '__main__': unittest.main()
