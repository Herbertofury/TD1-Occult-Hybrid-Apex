"""Synthetic catalog snapshots; no game launch, input or installed content."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli
import cas_resource_catalog as resources
import dbpf_build
import live_cas_catalog as catalog
from casp_fixture import casp


class LiveCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.cache = self.root / 'external'
        override = patch.object(catalog, 'INDEX_ROOT', self.cache)
        override.start(); self.addCleanup(override.stop)
        self.index = self.cache / 'library.sqlite'
        self.sources = []

    def package(self, name, contents, origin='mod'):
        path = self.root / name
        path.write_bytes(dbpf_build.build(contents))
        self.sources.append({'path': str(path), 'origin': origin})
        return path

    def build(self):
        return catalog.build(self.sources, self.index)

    def test_all_parts_beyond_old_cache_bound_are_searchable_and_paginated(self):
        path = self.package('Every eyebrow.package',
            {(resources.CASP, 0x80000000, n): casp(body=3) for n in range(1057)})
        original = path.read_bytes()
        # A full-file verification per part would make a CC-heavy index unusable.
        with patch.object(resources.Package, 'read', side_effect=AssertionError('per-part full-file scan')):
            built = self.build()
        self.assertEqual((built['ok'], built['parts']), (True, 1057))
        seen, offset = set(), 0
        while offset is not None:
            page = catalog.query(self.index, built['index_sha256'], 'eyebrow', body_type=3, offset=offset, limit=240)
            self.assertEqual(page['total'], 1057)
            ids = {row['part_id'] for row in page['items']}
            self.assertFalse(ids & seen)
            seen.update(ids); offset = page['next_offset']
        self.assertEqual(len(seen), 1057)
        self.assertEqual(path.read_bytes(), original)

    def test_every_group_duplicate_container_unknown_body_and_unparsed_row_retained(self):
        same = (resources.CASP, 0x80000000, 77)
        self.package('Alien nails.package', {same: casp(body=4095), (resources.CASP, 0, 77): casp(body=7)})
        self.package('Duplicate nails.package', {same: casp(body=4095), (resources.CASP, 8, 78): b'bad'})
        built = self.build()
        page = catalog.query(self.index, built['index_sha256'])
        self.assertEqual(page['total'], 4)
        self.assertEqual(len({row['part_id'] for row in page['items']}), 4)
        unclassified = next(row for row in page['items'] if row['status'] == 'unclassified')
        self.assertTrue(unclassified['reason'])
        self.assertIsNone(unclassified['body_type'])
        with self.assertRaisesRegex(ValueError, 'Unclassified'):
            catalog.resolve(self.index, built['index_sha256'], unclassified['part_id'])
        matches = catalog.query(self.index, built['index_sha256'], body_type=4095)
        self.assertEqual(matches['total'], 2)
        for row in matches['items']:
            resolved = catalog.resolve(self.index, built['index_sha256'], row['part_id'])
            self.assertEqual(resolved['request']['resource_tgi'], resources.tgi(same))
            self.assertFalse(resolved['effective_load_source_verified'])
            self.assertFalse(resolved['equip_verified'])

    def test_names_filters_cli_and_snapshot_pin(self):
        self.package('Magic Lipstick.package', {(resources.CASP, 8, 9): casp(body=29)})
        self.package('EA brows.package', {(resources.CASP, 0, 10): casp(body=3)}, 'ea')
        built = self.build()
        args = apex_cli.parser().parse_args(['live-cas-catalog', 'query', '--index', str(self.index),
            '--expected-index-sha256', built['index_sha256'], '--query', 'magic lips', '--body-type', '29',
            '--origin', 'mod', '--name-mode', 'package'])
        with patch.object(apex_cli, 'get', side_effect=AssertionError('game bridge contacted')):
            page = apex_cli.execute(args)
        self.assertEqual(page['total'], 1)
        self.assertEqual(page['items'][0]['name'], 'Magic Lipstick.package')
        code = catalog.query(self.index, built['index_sha256'], 'apex test', origin='ea', name_mode='code')
        self.assertEqual(code['items'][0]['name'], 'Apex test part')
        with self.assertRaisesRegex(ValueError, 'snapshot SHA256'):
            catalog.query(self.index, '0' * 64)
        with self.assertRaises(ValueError):
            catalog.query(self.index, built['index_sha256'], limit=241)
        with self.assertRaises(ValueError):
            catalog.query(self.index, built['index_sha256'], text='*')

    def test_changed_source_same_times_never_resolves_cached_selection(self):
        path = self.package('Freckles.package', {(resources.CASP, 8, 9): casp(body=35)})
        built = self.build()
        row = catalog.query(self.index, built['index_sha256'])['items'][0]
        stat = path.stat()
        data = bytearray(path.read_bytes()); data[97] ^= 1
        path.write_bytes(data); os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, 'changed since indexing'):
            catalog.resolve(self.index, built['index_sha256'], row['part_id'])
        # Historical browsing remains available without trusting stale bytes.
        self.assertEqual(catalog.query(self.index, built['index_sha256'])['total'], 1)

    def test_bad_package_is_visible_diagnostic_and_cache_cannot_overwrite_sources(self):
        self.package('Good hair.package', {(resources.CASP, 8, 9): casp(body=2)})
        self.package('Broken CC.package', {(resources.CASP, 8, 9): casp()}).write_bytes(b'broken')
        built = self.build()
        self.assertFalse(built['ok'])
        self.assertFalse(built['complete'])
        self.assertEqual(built['source_errors'][0]['package_name'], 'Broken CC.package')
        self.assertEqual(catalog.query(self.index, built['index_sha256'])['total'], 1)
        before = self.index.read_bytes()
        with self.assertRaisesRegex(ValueError, 'new index'):
            self.build()
        self.assertEqual(self.index.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'external'):
            catalog.build(self.sources, self.root / 'source.sqlite')
        self.assertFalse((self.root / 'source.sqlite').exists())

    def test_batched_bytes_are_exact_and_changed_content_refuses_even_if_times_match(self):
        keys = [(resources.CASP, 8, n) for n in range(3)]
        path = self.package('Batch.package', {key: casp(body=n + 1) for n, key in enumerate(keys)})
        package = resources.Package(path, 'mod')
        batch = package.read_many(keys)
        self.assertEqual(batch, {key: package.read(key) for key in keys})
        with self.assertRaises(ValueError):
            package.read_many(keys, max_total=1)
        with self.assertRaises(ValueError):
            package.read_many([keys[0], keys[0]])
        data = bytearray(path.read_bytes()); data[97] ^= 1; path.write_bytes(data)
        with patch.object(resources, 'signature', return_value=package.before), self.assertRaisesRegex(ValueError, 'changed during'):
            package.read_many(keys)


if __name__ == '__main__':
    unittest.main()
