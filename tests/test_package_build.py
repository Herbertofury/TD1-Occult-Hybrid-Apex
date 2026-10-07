import struct
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import dbpf_build as dbpf


class PackageBuildTests(unittest.TestCase):
    def test_real_header_and_sorted_resource_round_trip_are_deterministic(self):
        resources = {(0x545ac67a, 0x5a8351, 0x654bb): b'DATA baseline',
                     (0x220557da, 0x80000000, 0xff00000000000001): b'STBL exact locale payload'}
        result = dbpf.build(resources)
        self.assertEqual(result[:12], b'DBPF\x02\0\0\0\x01\0\0\0')
        self.assertEqual(struct.unpack_from('<I', result, 36)[0], 2)
        self.assertEqual(dbpf.read(result), resources)
        self.assertEqual(result, dbpf.build(dict(reversed(list(resources.items())))))

    def test_conflicts_require_an_explicit_owner_instead_of_load_order(self):
        key = (1, 2, 3)
        inputs = [('main', {key: b'main'}), ('fairy-addon', {key: b'fairy'})]
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            dbpf.merge(inputs)
        result, owners, collisions = dbpf.merge(inputs, {dbpf.tgi(key): 'fairy-addon'})
        self.assertEqual(result[key], b'fairy')
        self.assertEqual(owners[key], 'fairy-addon')
        self.assertEqual(collisions[0]['selected'], 'fairy-addon')
        result, _, _ = dbpf.merge(inputs, {dbpf.tgi(key): 'main'})
        self.assertEqual(result[key], b'main')

    def test_truncated_or_overlapping_index_and_duplicate_keys_refuse(self):
        raw = dbpf.build({(1, 2, 3): b'contents'})
        for broken in (raw[:95], raw[:-1]):
            with self.assertRaises(ValueError):
                dbpf.read(broken)
        broken = bytearray(raw)
        offset = struct.unpack_from('<I', broken, 64)[0]
        struct.pack_into('<I', broken, offset + 4 + 16, offset)
        with self.assertRaisesRegex(ValueError, 'extent'):
            dbpf.read(bytes(broken))


if __name__ == '__main__':
    unittest.main()
