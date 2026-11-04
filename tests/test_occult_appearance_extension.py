from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import occult_appearance_extension as extension, form_appearance as appearance
from test_native_witch_persistence import NativeRecord


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.record = NativeRecord(occult_type=32)
        # Unrelated future field and group must survive extension replacement.
        self.other = b'\xa0\x06\x7b' + b'\xab\x06\x08\x42\xac\x06'
        self.record.MergeFromString(self.other)
        self.fields = {'pelt_layers': appearance.encode(b'\x0a\x04\x08\x01\x10\x02'),
                       'custom_texture': appearance.encode((1 << 64) - 1)}

    def test_save_parse_copy_and_replace_keep_per_owner_extras_and_unknown_bytes(self):
        before = self.record.SerializeToString()
        extension.write(self.record, self.fields)
        copied = NativeRecord(); copied.ParseFromString(self.record.SerializeToString())
        self.assertEqual(extension.read(copied), self.fields)
        self.assertEqual(extension._parts(copied)[0], before)
        changed = dict(self.fields, pelt_layers=appearance.encode(b'\x0a\x04\x08\x03\x10\x04'))
        extension.write(copied, changed)
        self.assertEqual(extension.read(copied), changed)
        self.assertEqual(extension._parts(copied)[0], before)
        self.assertEqual(len(extension._parts(copied)[1]), 1)

    def test_missing_extension_is_native_and_does_not_generate_an_appearance(self):
        before = self.record.SerializeToString()
        self.assertEqual(extension.read(self.record), {})
        extension.write(self.record, {'voice_actor': appearance.encode(2)})
        self.assertEqual(before, self.record.SerializeToString())

    def test_extension_for_another_occult_never_authorizes_restoration(self):
        extension.write(self.record, self.fields)
        self.record.occult_type = 2
        with self.assertRaisesRegex(ValueError, 'identity'):
            extension.read(self.record)

    def test_checksum_corruption_never_replaces_original(self):
        extension.write(self.record, self.fields)
        raw = self.record.SerializeToString().replace(b'"schema":1', b'"schema":2')
        self.record.ParseFromString(raw)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            extension.write(self.record, self.fields)
        self.assertEqual(self.record.SerializeToString(), raw)

    def test_duplicate_extension_and_foreign_collision_never_discard_unknown_data(self):
        extension.write(self.record, self.fields)
        raw, frames = extension._parts(self.record)
        framed = self.record.SerializeToString()[len(raw):]
        self.record.MergeFromString(framed)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            extension.read(self.record)
        self.record.ParseFromString(raw + extension._varint(extension.FIELD << 3) + b'\x01')
        before = self.record.SerializeToString()
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            extension.write(self.record, self.fields)
        self.assertEqual(self.record.SerializeToString(), before)

    def test_new_native_schema_field_collision_refuses_before_copy(self):
        with patch.object(extension, 'FIELD', 1):
            with self.assertRaisesRegex(ValueError, 'Native schema'):
                extension.write(self.record, self.fields)

    def test_declared_values_cannot_be_overridden_via_an_extension(self):
        for value in (True, -1, 1 << 64, 'resource name'):
            before = self.record.SerializeToString()
            with self.assertRaisesRegex(ValueError, 'texture'):
                extension.write(self.record, dict(self.fields, custom_texture=appearance.encode(value)))
            self.assertEqual(before, self.record.SerializeToString())


if __name__ == '__main__':
    unittest.main()
