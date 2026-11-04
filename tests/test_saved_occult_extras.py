from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import saved_occult_extras as reader, occult_appearance_extension as extension, form_appearance as appearance
from dbpf_build import build
from test_native_witch_persistence import NativeRecord


def blob(number, raw):
    return extension._varint((number << 3) | 2) + extension._varint(len(raw)) + raw


class IndexedExtraTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root/'saves').mkdir()
        self.record = NativeRecord(occult_type=32, physique='saved independent wolf')
        self.extra = {'pelt_layers': appearance.encode(b'\x0a\x04\x08\x01\x10\x02'),
                      'custom_texture': appearance.encode(123)}
        extension.write(self.record, self.extra)
        self.native = NativeRecord(); self.native.ParseFromString(extension._parts(self.record)[0])
        self.sim = Obj(id=1, household_id=2)
        self.persistence = Obj(get_save_slot_proto_buff=lambda: Obj(slot_id=2), get_save_slot_proto_guid=lambda: 17)
        self.backend = Obj(services=Obj(get_persistence_service=lambda: self.persistence), __file__='same installed mod')
        self.enterContext(patch.object(reader, 'sidecar_paths', return_value=(self.root/'Mods/Apex/Native/ApexOverlay.dll', None)))
        reader._CACHE.clear()
        self.save()

    def save(self, sid=1, household=2, record=None, guid=17):
        row = (record or self.record).SerializeToString()
        tracker = blob(3, row)
        attrs = blob(17, tracker)
        sim = b'\x09' + struct.pack('<Q', sid) + b'\x21' + struct.pack('<Q', household) + blob(30, attrs)
        raw = b'\x08' + extension._varint(guid) + blob(6, sim)
        (self.root/'saves/Slot_00000002.save').write_bytes(build({(13, 0, guid): raw}))

    def test_exact_indexed_load_core_recovers_carrier_stripped_by_ea(self):
        before = self.native.SerializeToString(); original = (self.root/'saves/Slot_00000002.save').read_bytes()
        fields, receipt = reader.read(self.backend, self.sim, self.native)
        self.assertEqual(fields, self.extra); self.assertTrue(receipt['verified'])
        self.assertEqual(receipt['source'], 'indexed-save-matching-native-load-core')
        self.assertEqual(self.native.SerializeToString(), before)
        self.assertEqual((self.root/'saves/Slot_00000002.save').read_bytes(), original)

    def test_changed_incoming_core_does_not_authorize_old_saved_extras(self):
        self.native.physique = 'new native edit'
        with self.assertRaisesRegex(ValueError, 'core differs'):
            reader.read(self.backend, self.sim, self.native)

    def test_wrong_guid_household_and_duplicate_owner_refuse(self):
        self.save(household=3)
        with self.assertRaisesRegex(ValueError, 'household'):
            reader.read(self.backend, self.sim, self.native)
        self.save(guid=18)
        with self.assertRaisesRegex(ValueError, 'identity'):
            reader.read(self.backend, self.sim, self.native)

    def test_new_tray_sim_and_unknown_native_slot_cannot_select_an_older_save(self):
        self.sim.id = 3
        fields, receipt = reader.read(self.backend, self.sim, self.native)
        self.assertEqual(fields, {}); self.assertFalse(receipt['verified'])
        self.persistence.get_save_slot_proto_buff = lambda: Obj(slot_id=0)
        fields, receipt = reader.read(self.backend, self.sim, self.native)
        self.assertEqual(fields, {}); self.assertEqual(receipt['reason'], 'no-exact-native-slot')

    def test_already_carried_native_record_needs_no_disk_or_profile(self):
        fields, receipt = reader.read(Obj(), self.sim, self.record)
        self.assertEqual(fields, self.extra); self.assertEqual(receipt['source'], 'native-incoming-record')

    def test_refpack_literal_overlap_bounds_and_trailing_bytes(self):
        compressed = b'\x10\xfb\x00\x00\x07\xe0abcd\x00\x03\xfc'
        self.assertEqual(reader.refpack(compressed, 7), b'abcdabc')
        for raw, size in ((compressed + b'x', 7), (compressed, 6), (compressed[:-1], 7),
                          (b'\x10\xfb\x00\x00\x03\x00\x00\xfc', 3)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                reader.refpack(raw, size)

    def test_actual_indexed_v93_cell_fixture_retains_its_complete_core(self):
        # Synthetic fixture includes a future unknown group as well as pelt.
        self.native.MergeFromString(b'\xab\x06\x08\x42\xac\x06')
        saved = NativeRecord(); saved.CopyFrom(self.native); extension.write(saved, self.extra)
        self.save(record=saved)
        fields, receipt = reader.read(self.backend, self.sim, self.native)
        self.assertEqual(fields, self.extra); self.assertTrue(receipt['verified'])


if __name__ == '__main__':
    unittest.main()
