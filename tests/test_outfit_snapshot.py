from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.outfit_snapshot import normalize
from apex_core.change_journal import ChangeJournal, decoded


def varint(value):
    raw = bytearray()
    while value >= 128:
        raw.append((value & 127) | 128)
        value >>= 7
    return bytes(raw + bytes([value]))


def outfit(category, identity, color=(1 << 64) - 1):
    # Unknown fixed64/fixed32, repeated fields, groups, strings and full uint64
    # are deliberate: normalization must preserve every byte, not just parts.
    data = b'\x08' + varint(identity) + b'\x10' + varint(category)
    data += b'\x61' + color.to_bytes(8, 'little') + b'\x6a\x04name'
    data += b'\xa3\x01\x08\x07\xa4\x01\xad\x01\x11\x22\x33\x44'
    return b'\x0a' + varint(len(data)) + data


class OutfitSnapshotTests(unittest.TestCase):
    def test_category_permutation_preserves_unknowns_and_within_category_index(self):
        first, second, special = outfit(0, 9), outfit(0, 2), outfit(11, 3)
        unknown = b'\x42\x03top'
        canonical = first + unknown + second + special
        self.assertEqual(normalize(special + unknown + first + second), canonical)
        self.assertNotEqual(normalize(second + unknown + first + special), canonical)
        self.assertEqual(normalize(canonical), canonical)
        self.assertNotEqual(normalize(first + unknown + second + outfit(11, 3, 0)), canonical)

    def test_malformed_and_unbounded_data_are_rejected(self):
        for raw in (b'\x00', b'\x0a\x20x', b'\x0a\x02\x10\x80', b'\x0a\x03\xa3\x01\x08',
                    b'\x08\x01', b'\x0a\x0b\x10' + b'\xff' * 10, b'\x0a\x02\x14\x00'):
            with self.assertRaises(ValueError):
                normalize(raw)
        with self.assertRaises(ValueError):
            normalize(outfit(0, 1) * 1025)

    def test_old_history_migrates_without_losing_original_bytes_and_recovers_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'history.json')
            before = outfit(11, 3) + outfit(0, 9)
            after = outfit(11, 3, 0) + outfit(0, 9)
            journal = ChangeJournal(path, 'save:sim:human')
            journal.prepare('Color', before, after)
            journal.data['pending']['stage'] = 'rollback-failed'
            journal._save()
            migrated = ChangeJournal(path, journal.lane, normalize, 'outfit-category-group-order-v1')
            node = migrated.data['nodes'][0]
            self.assertEqual(decoded(node['original_state']), before)
            self.assertEqual(decoded(migrated.data['pending']['original_after']), after)
            self.assertIn('unchanged', migrated.recover(normalize(outfit(0, 9) + outfit(11, 3))))
            restored = ChangeJournal(path, journal.lane, normalize, 'outfit-category-group-order-v1')
            self.assertIsNone(restored.data['pending'])
            self.assertEqual(decoded(restored.data['nodes'][0]['original_state']), before)

    def test_native_group_reordering_is_accepted_but_actual_color_change_is_not(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = ChangeJournal(str(Path(folder) / 'history.json'), 'lane')
            before = normalize(outfit(0, 9) + outfit(11, 3))
            after = normalize(outfit(0, 9, 0) + outfit(11, 3))
            current = [before]
            def write(raw):
                # Model the actual game loader grouping categories differently.
                current[0] = raw[raw.index(outfit(11, 3)):] + raw[:raw.index(outfit(11, 3))]
            token = journal.prepare('Edit', before, after)
            journal.apply(token, lambda: normalize(current[0]), write)
            self.assertEqual(normalize(current[0]), after)


if __name__ == '__main__':
    unittest.main()
