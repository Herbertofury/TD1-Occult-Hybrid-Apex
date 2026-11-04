"""Native growth-part cleanup preserves complete phenotype and unknown data."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import genetics_snapshot, form_appearance


def varint(value):
    result = []
    while value >= 128:
        result.append((value & 127) | 128); value >>= 7
    return bytes(result + [value])


def message(number, content):
    return varint((number << 3) | 2) + varint(len(content)) + content


def part(identity, body, color=4611686018427387904, future=b''):
    return (b'\x08' + varint(identity) + b'\x10' + varint(body) +
            b'\x18' + varint(color) + b'\x28\x00' + future)


def genetic(parts, growth, base_unknown=b'', root_unknown=b''):
    return (message(1, b'complete sculpts') + message(2, b'0.002,0.040') +
            message(5, b''.join(message(1, row) for row in parts) + base_unknown) +
            message(6, b''.join(message(1, row) for row in growth)) + root_unknown)


class NativeGrowthSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.hair = part(414264, 2)
        self.growth = part(300336, 78, future=message(100, b'future growth row'))
        self.root = message(99, b'future root')
        self.base = message(98, b'future list')

    def test_exact_cross_list_duplicates_match_real_native_cleanup_without_payload_write(self):
        original = genetic([self.hair, self.growth], [self.growth], self.base, self.root)
        native = genetic([self.hair], [self.growth], self.base, self.root)
        self.assertEqual(genetics_snapshot.normalize(original), native)
        self.assertEqual(genetics_snapshot.normalize(native), native)
        payload = {'genetic_data': form_appearance.encode(original)}
        self.assertEqual(form_appearance.fingerprint(payload),
                         form_appearance.fingerprint({'genetic_data': form_appearance.encode(native)}))
        self.assertEqual(form_appearance.decode(payload['genetic_data']), original)

    def test_same_part_id_with_different_color_or_future_data_is_not_removed(self):
        for changed in (part(300336, 78, color=7),
                        part(300336, 78, future=message(100, b'other future row'))):
            original = genetic([self.hair, changed], [self.growth])
            self.assertEqual(genetics_snapshot.normalize(original), original)
            self.assertNotEqual(genetics_snapshot.normalize(original), genetic([self.hair], [self.growth]))

    def test_unknown_container_root_and_growth_bytes_stay_part_of_identity(self):
        original = genetic([self.hair, self.growth], [self.growth], self.base, self.root)
        expected = genetics_snapshot.normalize(original)
        for changed in (genetic([self.hair], [self.growth], b'', self.root),
                        genetic([self.hair], [self.growth], self.base, b''),
                        genetic([self.hair], [], self.base, self.root)):
            self.assertNotEqual(expected, genetics_snapshot.normalize(changed))

    def test_required_identity_and_unknown_layouts_remain_opaque_exact(self):
        malformed = genetic([b'\x08\x01'], [b'\x08\x01'])
        duplicate_root = genetic([self.hair], [self.growth]) + message(5, b'')
        for raw in (malformed, duplicate_root, b'opaque future format', b'\x0a\x80', b''):
            self.assertEqual(genetics_snapshot.normalize(raw), raw)

    def test_known_wire_order_changes_preserve_unknown_chunks(self):
        canonical = genetic([self.hair], [self.growth], self.base, self.root)
        reordered = (message(6, message(1, self.growth)) + message(2, b'0.002,0.040') +
                     message(1, b'complete sculpts') + message(5, message(1, self.hair) + self.base) + self.root)
        self.assertEqual(genetics_snapshot.normalize(reordered), canonical)


if __name__ == '__main__':
    unittest.main()
