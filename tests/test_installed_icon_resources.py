"""Bounded installed DBPF image lookup, independent of the game process."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / name) for name in ('Source', 'tools')]
from apex_core import installed_icon_resources as images
from dbpf_build import build


class InstalledIconResourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'Data/Client').mkdir(parents=True)
        (self.root / 'Game/Bin/Python/DLLs').mkdir(parents=True)
        (self.root / 'Game/Bin/TS4_x64.exe').write_bytes(b'MZ')
        self.key = (0x00b2d882, 0, 55)
        self.path = self.root / 'Data/Client/ClientDeltaBuild7.package'
        self.path.write_bytes(build({self.key: b'exact resource'}))

    def test_only_exact_tgi_and_client_containers_are_read_without_any_writes(self):
        ignored = self.root / 'Data/Client/NotAClient.package'
        ignored.write_bytes(b'not a package')
        before = self.path.read_bytes()
        rows = images.read(images.game_root(self.root / 'Game/Bin/Python/DLLs'), [self.key])
        self.assertEqual(rows[self.key]['raw'], b'exact resource')
        self.assertEqual(rows[self.key]['sources'][0]['container'], str(self.path.relative_to(self.root)))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(images.read(self.root, [(0x2f7d0004, 0, 55)]), {})

    def test_same_bytes_duplicate_is_explicit_but_different_bytes_are_a_conflict(self):
        directory = self.root / 'GP04'
        directory.mkdir()
        other = directory / 'ClientFullBuild0.package'
        other.write_bytes(self.path.read_bytes())
        row = images.read(self.root, [self.key])[self.key]
        self.assertEqual(len(row['sources']), 2)
        self.assertNotIn('conflict', row)
        other.write_bytes(build({self.key: b'other resource'}))
        self.assertTrue(images.read(self.root, [self.key])[self.key]['conflict'])

    def test_changed_package_is_rejected_instead_of_certifying_raced_bytes(self):
        original = images.signature
        calls = []
        def changed(path):
            calls.append(path)
            row = original(path)
            return row if len(calls) == 1 else row[:-1] + (row[-1] + 1,)
        with patch.object(images, 'signature', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed'):
            images.read(self.root, [self.key])

    def test_index_and_payload_budget_and_truncation_are_enforced(self):
        with patch.object(images, 'MAX_INDEX_TOTAL', 1), self.assertRaisesRegex(ValueError, 'bound'):
            images.read(self.root, [self.key])
        original = self.path.read_bytes()
        self.path.write_bytes(original[:-1])
        with self.assertRaises(ValueError):
            images.read(self.root, [self.key])
        bad = bytearray(original)
        start = struct.unpack_from('<I', bad, 64)[0]
        struct.pack_into('<I', bad, start, 8)
        self.path.write_bytes(bad)
        with self.assertRaisesRegex(ValueError, 'shared'):
            images.read(self.root, [self.key])

    def test_wrong_game_path_or_key_batch_cannot_expand_resource_access(self):
        for path in (self.root, self.root / 'Game/Bin'):
            with self.assertRaises(ValueError):
                images.game_root(path)
        for keys in ([], [(0, 0, index) for index in range(7)], [('not a type', 0, 1)]):
            with self.assertRaises(ValueError):
                images.read(self.root, keys)


if __name__ == '__main__':
    unittest.main()
