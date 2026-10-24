"""Independent protobuf wire fixtures; no descriptors or game modules."""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import dbpf_build
import save_household
from source_manifest import sha256


class SaveHouseholdTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'Slot_00000002.save'
        self.slot = b'\x09' + struct.pack('<Q', 2) + b'\x4a\x04Test\x58\x03'
        self.ids = b'\x0a\x10' + struct.pack('<QQ', 17, 18)
        self.household = (b'\x11' + struct.pack('<Q', 3) + b'\x1a\x04Home' +
            b'\x21' + struct.pack('<Q', 120) + b'\x49' + struct.pack('<Q', 17) +
            b'\x5a' + bytes([len(self.ids)]) + self.ids)
        self.sim = (b'\x09' + struct.pack('<Q', 17) + b'\x11' + struct.pack('<Q', 120) +
            b'\x21' + struct.pack('<Q', 3) + b'\x2a\x04Apex\x32\x04Test\xb2\x01\x04Home')

    def raw(self, household=None, sim=None, extra=b''):
        household = self.household if household is None else household
        sim = self.sim if sim is None else sim
        return (b'\x08\x07\x12' + bytes([len(self.slot)]) + self.slot +
                b'\x2a' + bytes([len(household)]) + household +
                b'\x32' + bytes([len(sim)]) + sim + extra)

    def write(self, raw, resources=None):
        values = {(13, 0, 7): raw} if resources is None else resources
        self.path.write_bytes(dbpf_build.build(values))
        return sha256(self.path)

    def test_exact_names_zone_ids_and_packed_membership_are_projected_read_only(self):
        raw = self.raw(extra=b'\xf2\x01\x06opaque')
        digest = self.write(raw)
        before = self.path.read_bytes()
        result = save_household.read(self.path, digest, '3', '17')
        self.assertEqual(result['household'], {'id': '3', 'name': 'Home', 'home_zone_id': '120',
            'last_played_sim_id': '17', 'member_ids': ['17', '18']})
        self.assertEqual(result['sim'], {'id': '17', 'zone_id': '120', 'household_id': '3',
            'first_name': 'Apex', 'last_name': 'Test', 'household_name': 'Home'})
        self.assertTrue(result['selected_membership_verified'])
        self.assertTrue(result['selected_household_is_active'])
        self.assertEqual(result['resource_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['household_record_sha256'], hashlib.sha256(self.household).hexdigest())
        self.assertEqual(result['sim_record_sha256'], hashlib.sha256(self.sim).hexdigest())
        self.assertFalse(result['save_file_written'])
        self.assertFalse(result['game_modules_executed'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_selected_records_are_found_by_ids_not_record_order_or_string_search(self):
        other_household = b'\x11' + struct.pack('<Q', 99) + b'\x1a\x04Home'
        other_sim = b'\x09' + struct.pack('<Q', 88) + b'\x2a\x04Apex'
        extra = (b'\x2a' + bytes([len(other_household)]) + other_household +
                 b'\x32' + bytes([len(other_sim)]) + other_sim)
        result = save_household.project(self.raw(extra=extra), '3', '17')
        self.assertEqual(result['household']['id'], '3')
        self.assertEqual(result['sim']['id'], '17')
        with self.assertRaisesRegex(ValueError, 'missing or duplicated'):
            save_household.project(self.raw(extra=extra), '3', '89')

    def test_large_fixed64_member_ids_remain_decimal_strings_without_float_rounding(self):
        ident = 285159751289798669
        raw = self.raw(
            household=self.household.replace(struct.pack('<Q', 17), struct.pack('<Q', ident)),
            sim=self.sim.replace(struct.pack('<Q', 17), struct.pack('<Q', ident)))
        result = save_household.project(raw, '3', str(ident))
        self.assertEqual(result['sim']['id'], str(ident))
        self.assertEqual(result['household']['member_ids'][0], str(ident))

    def test_duplicate_selected_record_or_identity_field_refuses(self):
        for extra in (b'\x2a' + bytes([len(self.household)]) + self.household,
                      b'\x32' + bytes([len(self.sim)]) + self.sim):
            with self.subTest(extra=extra[:1]), self.assertRaises(ValueError):
                save_household.project(self.raw(extra=extra), '3', '17')
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            save_household.project(self.raw(sim=self.sim + b'\x09' + struct.pack('<Q', 17)), '3', '17')

    def test_household_identity_or_member_list_mismatch_refuses(self):
        for household, sim in (
            (self.household, self.sim.replace(b'\x21' + struct.pack('<Q', 3), b'\x21' + struct.pack('<Q', 4))),
            (self.household.replace(struct.pack('<Q', 17), struct.pack('<Q', 19)), self.sim)):
            with self.subTest(household=household[-10:]), self.assertRaisesRegex(ValueError, 'disagree'):
                save_household.project(self.raw(household=household, sim=sim), '3', '17')

    def test_packed_membership_misaligned_duplicate_zero_and_wrong_wire_refuse(self):
        for raw in (b'\x0a\x07' + b'\x01' * 7,
                    b'\x0a\x10' + struct.pack('<QQ', 17, 17),
                    b'\x0a\x08' + struct.pack('<Q', 0),
                    b'\x09' + struct.pack('<Q', 17), b''):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                save_household.members(raw)

    def test_unknown_nested_fields_are_opaque_and_repeated_packed_chunks_are_read(self):
        ids = (b'\x0a\x08' + struct.pack('<Q', 17) + b'\x0a\x08' + struct.pack('<Q', 18) +
               b'\x12\x06future')
        self.assertEqual(save_household.members(ids), ['17', '18'])
        raw = self.raw(household=self.household + b'\xa2\x01\x06future',
                       sim=self.sim + b'\xe2\x01\x06opaque')
        before = bytes(raw)
        self.assertTrue(save_household.project(raw, '3', '17')['unknown_fields_skipped_read_only'])
        self.assertEqual(raw, before)

    def test_wrong_known_wire_duplicate_name_bad_utf8_and_missing_zone_refuse(self):
        for sim in (self.sim.replace(b'\x09' + struct.pack('<Q', 17), b'\x08\x11'),
                    self.sim + b'\x2a\x04Oops',
                    self.sim.replace(b'Apex', b'Ape\xff'),
                    self.sim.replace(b'\x11' + struct.pack('<Q', 120), b'')):
            with self.subTest(sim=sim[:10]), self.assertRaises(ValueError):
                save_household.project(self.raw(sim=sim), '3', '17')

    def test_exact_expected_file_hash_is_required_before_indexing(self):
        digest = self.write(self.raw())
        with patch.object(save_household, 'Package') as package:
            with self.assertRaisesRegex(ValueError, 'explicit file hash'):
                save_household.read(self.path, 'd' * 64, '3', '17')
            package.assert_not_called()
        self.assertEqual(sha256(self.path), digest)

    def test_changed_final_hash_guid_mismatch_or_ambiguous_resource_refuse(self):
        digest = self.write(self.raw())
        with patch.object(save_household, 'sha256', side_effect=[digest, 'e' * 64]):
            with self.assertRaisesRegex(ValueError, 'file changed'):
                save_household.read(self.path, digest, '3', '17')
        digest = self.write(self.raw(), {(13, 0, 8): self.raw()})
        with self.assertRaisesRegex(ValueError, 'GUID differs'):
            save_household.read(self.path, digest, '3', '17')
        digest = self.write(self.raw(), {(13, 0, 7): self.raw(), (13, 0, 8): self.raw()})
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            save_household.read(self.path, digest, '3', '17')

    def test_identity_arguments_and_truncated_wire_are_refused(self):
        for value in (17, '017', '0', '-1', str(1 << 64), '17.0'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                save_household.project(self.raw(), '3', value)
        with self.assertRaises(ValueError):
            save_household.project(self.raw()[:-1], '3', '17')


if __name__ == '__main__':
    unittest.main()
