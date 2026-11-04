# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
import zlib

from large_package import (PinnedPackage, PackageError, MissingResource,
                           AmbiguousResource, UnsupportedResource, decode_refpack, parse_tgi)


def fixture(rows, flags=0):
    head = bytearray(96); head[:4] = b'DBPF'; struct.pack_into('<II', head, 4, 2, 1)
    shared = (0x034aeecb, 0x12345678, 0x87654321)
    body = bytearray(); entries = bytearray(); offset = 96
    for n, item in enumerate(rows):
        payload = item.get('payload', b'abc')
        compression = item.get('compression', 0)
        stored = item.get('stored', zlib.compress(payload) if compression == 0x5a42 else payload)
        values = (item.get('type', shared[0]), item.get('group', shared[1]), item.get('high', shared[2]))
        for j, value in enumerate(values):
            if not flags & (1 << j): entries += struct.pack('<I', value)
        extended = item.get('extended', bool(compression))
        entries += struct.pack('<IIII', item.get('low', n + 1), item.get('offset', offset), len(stored) | (0x80000000 if extended else 0), item.get('memory', len(payload)))
        if extended: entries += struct.pack('<HH', compression, item.get('committed', 1))
        body += stored; offset += len(stored)
    index = struct.pack('<I', flags) + b''.join(struct.pack('<I', v) for j, v in enumerate(shared) if flags & (1 << j)) + entries
    struct.pack_into('<I', head, 36, len(rows)); struct.pack_into('<I', head, 44, len(index)); struct.pack_into('<I', head, 64, offset)
    return bytes(head + body + index)


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / 'case.package'
    def write(self, data):
        self.path.write_bytes(data); return sha(self.path)
    @staticmethod
    def key(n=1): return (0x034aeecb, 0x12345678, 0x8765432100000000 | n)

    def test_preview_tgi_format_is_checked_without_losing_unsigned_bits(self):
        self.assertEqual(parse_tgi('034AEECB:12345678:8765432100000001'), self.key())
        for value in ('034aeecb:12345678:8765432100000001', '0:0:0', '034AEECB:12345678:10000000000000000', None):
            with self.assertRaises(PackageError): parse_tgi(value)

    def test_index_masks_and_selected_compression(self):
        for flags in range(8):
            data = bytearray(fixture([{'payload': b'plain'}, {'payload': b'compressed', 'compression': 0x5a42}], flags))
            if flags % 2:
                struct.pack_into('<I', data, 40, struct.unpack_from('<I', data, 64)[0]); struct.pack_into('<I', data, 64, 0)
            digest = self.write(data)
            with PinnedPackage(self.path, digest) as package:
                rows = list(package.iter_rows())
                self.assertEqual([r.key for r in rows], [self.key(1), self.key(2)])
                self.assertEqual(package.read_many([self.key(2), self.key(1)]), {self.key(2): b'compressed', self.key(1): b'plain'})

    def test_large_sparse_package_has_bounded_python_allocation(self):
        self.write(fixture([{'payload': b'large-package-tiny-selection'}]))
        with self.path.open('r+b') as file: file.truncate(70 * 1024 * 1024)
        digest = sha(self.path)
        tracemalloc.start()
        try:
            with PinnedPackage(self.path, digest) as package:
                self.assertEqual(package.read_many([self.key()])[self.key()], b'large-package-tiny-selection')
                self.assertEqual(package.source_size, 70 * 1024 * 1024)
                self.assertLessEqual(package.max_read, 1024 * 1024)
            _, peak = tracemalloc.get_traced_memory()
            self.assertLess(peak, 8 * 1024 * 1024)
        finally: tracemalloc.stop()

    def test_large_index_is_scanned_without_materializing_all_rows(self):
        count = 200000
        head = bytearray(96); head[:4] = b'DBPF'; struct.pack_into('<II', head, 4, 2, 1)
        struct.pack_into('<I', head, 36, count); struct.pack_into('<I', head, 44, 16 + count * 16); struct.pack_into('<I', head, 64, 96)
        with self.path.open('wb') as output:
            output.write(head); output.write(struct.pack('<IIII', 7, 0x034aeecb, 0x12345678, 0x87654321))
            for first in range(0, count, 4096):
                output.write(b''.join(struct.pack('<IIII', n + 1, 0, 0, 0) for n in range(first, min(first + 4096, count))))
        digest = sha(self.path)
        tracemalloc.start()
        try:
            with PinnedPackage(self.path, digest) as package:
                rows = package.resolve_many([self.key(count)])[self.key(count)]
                self.assertEqual(len(rows), 1); self.assertEqual(rows[0].ordinal, count - 1)
                self.assertEqual(package.read_many([self.key(count)])[self.key(count)], b'')
                self.assertLessEqual(package.max_read, 1024 * 1024)
            _, peak = tracemalloc.get_traced_memory()
            self.assertLess(peak, 8 * 1024 * 1024)
        finally: tracemalloc.stop()

    def test_large_selected_zlib_is_bounded_by_expanded_size(self):
        payload = b'A' * (24 * 1024 * 1024)
        expected = hashlib.sha256(payload).digest()
        digest = self.write(fixture([{'payload': payload, 'compression': 0x5a42}]))
        del payload
        tracemalloc.start()
        try:
            with PinnedPackage(self.path, digest) as package:
                result = package.read_many([self.key()])[self.key()]
                self.assertEqual(len(result), 24 * 1024 * 1024)
                self.assertEqual(hashlib.sha256(result).digest(), expected)
            _, peak = tracemalloc.get_traced_memory()
            self.assertLess(peak, 56 * 1024 * 1024)
        finally: tracemalloc.stop()

    def test_ambiguity_missing_and_unsupported_never_choose_winner(self):
        digest = self.write(fixture([{}, {'low': 1}, {'low': 3, 'compression': 0xbeef}, {'low': 4, 'compression': 0xffe0}]))
        with PinnedPackage(self.path, digest) as package:
            self.assertEqual(len(package.resolve_many([self.key()])[self.key()]), 2)
            with self.assertRaises(AmbiguousResource): package.read_many([self.key()])
            with self.assertRaises(MissingResource): package.read_many([self.key(9)])
            for n in (3, 4):
                with self.assertRaises(UnsupportedResource): package.read_many([self.key(n)])
            with self.assertRaises(PackageError): package.read_many([self.key(), self.key()])
            with self.assertRaises(PackageError): package.read_many([])
            with self.assertRaises(PackageError): package.read_many([(True, 0, 0)])

    def test_candidate_and_aggregate_payload_limits(self):
        digest = self.write(fixture([{'low': 1} for _ in range(33)]))
        with PinnedPackage(self.path, digest) as package:
            with self.assertRaisesRegex(PackageError, 'candidate limit'): package.resolve_many([self.key()])
        digest = self.write(fixture([{'memory': 32 * 1024 * 1024}, {'memory': 32 * 1024 * 1024}]))
        with PinnedPackage(self.path, digest) as package:
            with self.assertRaisesRegex(PackageError, 'budget'): package.read_many([self.key(1), self.key(2)])

    def test_reject_bad_hash_changed_file_and_closed_handle(self):
        digest = self.write(fixture([{}]))
        with self.assertRaises(PackageError): PinnedPackage(self.path, '0' * 64)
        with PinnedPackage(self.path, digest) as package:
            with self.path.open('r+b') as file: file.seek(96); file.write(b'zzz')
            with self.assertRaises(PackageError): package.read_many([self.key()])
        with self.assertRaises(PackageError): package.read_many([self.key()])

    def test_interleaved_operations_are_rejected_without_corrupting_cursor(self):
        digest = self.write(fixture([{}, {'payload': b'other'}]))
        with PinnedPackage(self.path, digest) as package:
            iterator = package.iter_rows()
            self.assertEqual(next(iterator).ordinal, 0)
            with self.assertRaisesRegex(PackageError, 'active'): package.read_many([self.key()])
            with self.assertRaisesRegex(PackageError, 'active'): package.close()
            self.assertEqual(next(iterator).ordinal, 1)
            iterator.close()
            self.assertEqual(package.read_many([self.key()])[self.key()], b'abc')

    def test_reject_malformed_headers_indexes_and_overlaps(self):
        original = fixture([{}])
        variants = []
        for offset, value in [(4, 3), (36, 250001), (44, 0xffffffff), (64, 0xffffffff)]:
            item = bytearray(original); struct.pack_into('<I', item, offset, value); variants.append(item)
        item = bytearray(original); item[:4] = b'NOPE'; variants.append(item)
        item = bytearray(original); struct.pack_into('<I', item, struct.unpack_from('<I', item, 64)[0], 8); variants.append(item)
        item = bytearray(original); start = struct.unpack_from('<I', item, 64)[0]; struct.pack_into('<I', item, start + 4 + 16, start); variants.append(item)
        variants.append(bytearray(original[:-1]))
        for item in variants:
            digest = self.write(bytes(item))
            with self.assertRaises(PackageError):
                with PinnedPackage(self.path, digest) as package: list(package.iter_rows())

    def test_payload_budget_and_malformed_zlib(self):
        data = fixture([{'payload': b'abc', 'memory': 64 * 1024 * 1024}])
        digest = self.write(data)
        with PinnedPackage(self.path, digest) as package:
            with self.assertRaisesRegex(PackageError, 'budget'): package.read_many([self.key()])
        digest = self.write(fixture([{'stored': zlib.compress(b'a'), 'memory': 32 * 1024 * 1024, 'compression': 0x5a42}]))
        with PinnedPackage(self.path, digest) as package:
            with self.assertRaisesRegex(PackageError, 'budget'): package.read_many([self.key()])
        for stored, memory in [(zlib.compress(b'a' * 3000000), 4), (zlib.compress(b'abc')[:-1], 3), (zlib.compress(b'abc') + b'extra', 3)]:
            digest = self.write(fixture([{'stored': stored, 'memory': memory, 'compression': 0x5a42}]))
            with PinnedPackage(self.path, digest) as package:
                with self.assertRaises(PackageError): package.read_many([self.key()])

    def test_refpack_and_corruption(self):
        stream = bytes.fromhex('10fb000007e0616263640003fc')
        self.assertEqual(decode_refpack(stream, 7), b'abcdabc')
        overlap = bytes.fromhex('10fb000408e061616161cc0000fffc')
        self.assertEqual(decode_refpack(overlap, 1032), b'a' * 1032)
        digest = self.write(fixture([{'stored': stream, 'payload': b'abcdabc', 'compression': 0xffff}]))
        with PinnedPackage(self.path, digest) as package: self.assertEqual(package.read_many([self.key()])[self.key()], b'abcdabc')
        for bad in (stream[:-1], stream + b'\0', bytes.fromhex('10fb0000040000fc')):
            with self.assertRaises(PackageError): decode_refpack(bad, 7 if bad != bytes.fromhex('10fb0000040000fc') else 4)

    @unittest.skipUnless(os.environ.get('S4PY_ROOT') and os.environ.get('S4PY_PYTHON'), 'independent reader unavailable')
    def test_selected_rows_and_payloads_match_s4py(self):
        digest = self.write(fixture([{'payload': b'plain'}, {'payload': b'compressed', 'compression': 0x5a42}]))
        bridge = pathlib.Path(__file__).with_name('s4py_oracle.py')
        with PinnedPackage(self.path, digest) as package:
            rows = list(package.iter_rows()); results = package.read_many([self.key(1), self.key(2)])
            for row in rows:
                expected = subprocess.check_output([os.environ['S4PY_PYTHON'], '-B', str(bridge), os.environ['S4PY_ROOT'], '--payload-hash', str(self.path), str(row.ordinal)], text=True).strip()
                self.assertEqual(hashlib.sha256(results[row.key]).hexdigest(), expected)
        overlap = bytes.fromhex('10fb000408e061616161cc0000fffc')
        reference = subprocess.check_output([os.environ['S4PY_PYTHON'], '-B', str(bridge), os.environ['S4PY_ROOT'], '--refpack', overlap.hex()], text=True).strip()
        self.assertEqual(decode_refpack(overlap, 1032), bytes.fromhex(reference))


if __name__ == '__main__': unittest.main()
