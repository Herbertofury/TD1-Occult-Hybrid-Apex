from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from save_metadata import fields, project


class NativeSaveMetadataTests(unittest.TestCase):
    def raw(self):
        # Independent protobuf wire fixture: GUID7, Slot2, name Test, household3,
        # plus an opaque future field and known preferred-manual data.
        slot = b'\x09' + struct.pack('<Q', 2) + b'\x4a\x04Test\x58\x03\xa0\x01\x02\xaa\x01\x04Test\xf2\x01\x06opaque'
        return b'\x08\x07\x12' + bytes([len(slot)]) + slot

    def test_complete_native_identity_skips_unknown_fields_without_rebuilding_them(self):
        raw = self.raw()
        result = project(raw)
        self.assertEqual(result, {'save_guid': '7', 'slot_id': 2, 'slot_name': 'Test',
            'active_household_id': '3', 'preferred_manual_slot_id': 2, 'preferred_manual_slot_name': 'Test'})
        self.assertEqual(raw, self.raw())

    def test_root_identity_duplicate_absent_or_wrong_wire_is_refused(self):
        for raw in (self.raw() + b'\x08\x07', self.raw()[2:], b'\x0d\x07\x00\x00\x00' + self.raw()[2:]):
            with self.subTest(raw=raw[:8]), self.assertRaises(ValueError):
                project(raw)

    def test_duplicate_slot_and_missing_name_or_household_refused(self):
        for extra in (b'\x09' + struct.pack('<Q', 3), b'\x4a\x04Name', b'\x58\x04'):
            original = self.raw(); slot = original[4:] + extra
            raw = b'\x08\x07\x12' + bytes([len(slot)]) + slot
            with self.assertRaises(ValueError): project(raw)
        for replacement in (b'\x4a\x04Test', b'\x58\x03'):
            original = self.raw(); slot = original[4:].replace(replacement, b'')
            with self.assertRaises(ValueError): project(b'\x08\x07\x12' + bytes([len(slot)]) + slot)

    def test_truncated_overflow_zero_field_and_group_wire_rejected(self):
        for raw in (b'\x12\x05x', b'\x00', b'\x0b', b'\x08' + b'\xff' * 10 + b'\x01', b'\x09\x00'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): list(fields(raw))
