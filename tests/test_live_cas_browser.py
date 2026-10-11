"""Real loopback transport and synthetic CASP assets; never touch a game."""
import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import test_live_cas_catalog as fixtures
from test_cas_resource_catalog import picture
import cas_resource_catalog as resources
import live_cas_browser as browser
import live_cas_catalog as catalog
from casp_fixture import casp


class BrowserTests(unittest.TestCase):
    package = fixtures.LiveCatalogTests.package
    build = fixtures.LiveCatalogTests.build

    def setUp(self):
        fixtures.LiveCatalogTests.setUp(self)
        self.resource_root = self.root / 'resource-cache'
        override = patch.object(resources, 'CACHE_ROOT', self.resource_root)
        override.start(); self.addCleanup(override.stop)
        key = (resources.CASP, 8, 91)
        self.source = self.package('Moonlight Jewelry.package', {key: casp(body=35),
            (resources.CAS_THUMB, 2, key[2]): picture()})
        built = self.build()
        self.hash = built['index_sha256']
        self.browser = browser.Browser(self.index, self.hash, self.resource_root / 'browser')
        self.addCleanup(self.browser.index.close)
        self.query = dict(text='', body_type=None, origin=None, name_mode='preferred', offset=0, limit=60, view='all')

    def test_page_has_categories_and_names_without_host_paths_or_source_reads(self):
        with patch.object(resources.Package, 'read', side_effect=AssertionError('browsing source package')):
            page = self.browser.query(self.query)
        self.assertEqual(page['categories'], [dict(body_type=35, count=1)])
        self.assertNotIn('package_path', page['items'][0])
        self.assertFalse(page['game_contacted'])
        self.assertEqual(page['items'][0]['name'], self.source.name)

    def test_lazy_thumbnail_exact_source_and_persistent_favorites(self):
        original = self.source.read_bytes()
        item = self.browser.query(self.query)['items'][0]
        selected = dict(part_id=item['part_id'], index_sha256=self.hash)
        with patch.object(resources, 'studio_executable', side_effect=ValueError('not installed in fixture')):
            receipt = self.browser.inspect(selected)
        row = receipt['resource']
        self.assertEqual(row['broker_port'], 8023)
        self.assertTrue(self.browser.thumbnail(row['resource_id']).startswith(b'\x89PNG'))
        self.assertFalse(receipt['equip_verified'])
        self.browser.favorite(dict(selected, enabled=True))
        favorites = self.browser.query(dict(self.query, view='favorites'))
        self.assertEqual(favorites['total'], 1)
        self.assertTrue(favorites['items'][0]['favorite'])
        self.assertEqual(self.browser.query(dict(self.query, view='recent'))['total'], 1)
        self.assertEqual(self.source.read_bytes(), original)
        other = browser.Browser(self.index, self.hash, self.resource_root / 'browser')
        try:
            self.assertEqual(other.query(dict(self.query, view='favorites'))['total'], 1)
        finally:
            other.index.close()
        self.browser.favorite(dict(selected, enabled=False))
        self.assertEqual(self.browser.query(dict(self.query, view='favorites'))['total'], 0)

    def test_source_change_refuses_lazy_assets_and_snapshot_identity_is_required(self):
        item = self.browser.query(self.query)['items'][0]
        selected = dict(part_id=item['part_id'], index_sha256=self.hash)
        with self.assertRaisesRegex(ValueError, 'exact index'):
            self.browser.inspect(dict(selected, index_sha256='0' * 64))
        original = self.source.read_bytes(); changed = bytearray(original); changed[97] ^= 1
        self.source.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'changed since indexing'):
            self.browser.inspect(selected)
        self.assertEqual(self.browser.recent, [])

    def test_immutable_browser_cannot_be_changed_with_preserved_times(self):
        if os.name == 'nt':
            with self.assertRaises(OSError):
                self.index.write_bytes(self.index.read_bytes())
        else:
            stat = self.index.stat()
            raw = bytearray(self.index.read_bytes()); raw[100] ^= 1; self.index.write_bytes(raw)
            os.utime(self.index, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.browser.query(self.query)

    def test_loopback_strict_routes_bad_origin_and_no_arbitrary_paths(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), browser.handler(self.browser))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            def send(route, value, origin=None):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                headers = {'Content-Type': 'application/json'}
                if origin: headers['Origin'] = origin
                connection.request('POST', route, json.dumps(value), headers)
                response = connection.getresponse(); result = json.loads(response.read()); connection.close()
                return response.status, result
            self.assertEqual(send('/v1/catalog/query', self.query)[0], 200)
            self.assertEqual(send('/v1/catalog/query', self.query, 'https://evil.example')[0], 409)
            self.assertEqual(send('/v1/catalog/query', dict(self.query, path=str(self.source)))[0], 409)
            self.assertEqual(send('/v1/catalog/query', dict(self.query, limit=241))[0], 409)
            self.assertEqual(send('/anything', self.query)[0], 409)
            self.assertEqual(send('/v1/open', dict(path=str(self.source)))[0], 409)
        finally:
            server.shutdown(); server.server_close(); thread.join(3)


if __name__ == '__main__':
    unittest.main()
