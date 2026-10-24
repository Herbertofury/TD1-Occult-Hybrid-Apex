"""Loopback Live CAS pages and lazily verified item assets. No game commands."""
import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from loopback_server import LoopbackHTTPServer
import json
import os
from pathlib import Path
import re
import threading
import tempfile

import cas_resource_catalog as resources
from live_cas_catalog import PinnedIndex, resolve

PORT = 8023
MAX_BODY = 2048


class Browser:
    def __init__(self, index, expected, cache=resources.CACHE_ROOT / 'live-browser', tray_root=None):
        self.index = PinnedIndex(index, expected)
        self.cache = Path(cache).absolute()
        resources.no_redirected_ancestors(self.cache)
        root = resources.CACHE_ROOT.resolve()
        if root not in self.cache.resolve().parents:
            self.index.close()
            raise ValueError('Browser assets must stay in the external CAS resource cache.')
        resources.ensure_directory(self.cache, '')
        self.lock = threading.RLock()
        self.preference_lock = threading.RLock()
        self.assets = {}
        self.asset_sources = {}
        self.tray_root = tray_root
        self.gallery = None
        self.favorites = set()
        self.recent = []
        self.preferences = self.cache / ('preferences-' + self.index.expected + '.json')
        if self.preferences.exists():
            if self.preferences.stat().st_size > 1024 * 1024:
                raise ValueError('Saved browser preferences exceed their bound.')
            data = json.loads(self.preferences.read_bytes())
            if set(data) != {'favorites', 'recent'}:
                raise ValueError('Saved browser preference fields differ.')
            for field in data.values():
                if not isinstance(field, list) or len(field) > 10000:
                    raise ValueError('Saved item list exceeds its bound.')
                for ident in field:
                    resources.sha(ident)
            self.favorites, self.recent = set(data['favorites']), data['recent'][:200]

    def _save(self):
        resources.no_redirected_ancestors(self.preferences)
        raw = resources.canonical({'favorites': sorted(self.favorites), 'recent': self.recent})
        # Exclusive creation prevents a pre-existing link from redirecting a
        # temporary write. Replace only this broker's private preference entry.
        fd, name = tempfile.mkstemp(prefix='preferences-', suffix='.tmp', dir=self.cache)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
            os.replace(temporary, self.preferences)
        finally:
            temporary.unlink(missing_ok=True)

    def query(self, request):
        fields = {'text', 'body_type', 'origin', 'name_mode', 'offset', 'limit', 'view'}
        if (not isinstance(request, dict) or set(request) - {'fuzzy'} not in (fields, fields | {'author', 'sort'}, fields | {'author', 'sort', 'grouped'}) or
                request['view'] not in ('all', 'favorites', 'recent')):
            raise ValueError('Catalog query fields differ.')
        with self.preference_lock:
            favorites = frozenset(self.favorites)
            recent = tuple(self.recent)
        ids = (sorted(favorites) if request['view'] == 'favorites' else
               list(recent) if request['view'] == 'recent' else None)
        # Asset preparation can read/hash/decode whole packages. Its lock must
        # never prevent a cached metadata search from returning immediately.
        result = self.index.query(text=request['text'], body_type=request['body_type'], origin=request['origin'],
            name_mode=request['name_mode'], offset=request['offset'], limit=request['limit'], part_ids=ids,
            author=request.get('author', ''), sort=request.get('sort', 'name'), grouped=request.get('grouped', False),
            fuzzy=request.get('fuzzy', False))
        for row in result['items']:
            row.pop('package_path')
            row['favorite'] = row['part_id'] in favorites
        result['query'] = request
        if len(resources.canonical(result)) > resources.MAX_RESPONSE:
            raise ValueError('Catalog page exceeds its transport bound; request fewer items.')
        return result

    def tray(self, operation, request):
        if self.tray_root is None: raise ValueError('Start the browser with its explicit read-only --tray-root.')
        from tray_browser import Gallery
        with self.lock:
            if operation=='query':
                self.gallery=Gallery(self.tray_root)
                return self.gallery.query(request)
            if self.gallery is None: raise ValueError('Query the Tray gallery before selecting an item.')
            return self.gallery.image(request) if operation=='image' else self.gallery.inspect(request)

    def inspect(self, request):
        if (not isinstance(request, dict) or set(request) not in ({'part_id', 'index_sha256'}, {'part_id', 'index_sha256', 'swatch_offset'}) or
                request['index_sha256'] != self.index.expected):
            raise ValueError('Selection must use this exact index snapshot.')
        with self.lock:
            selected = resolve(self.index.path, self.index.expected, resources.sha(request['part_id']))
            prepared = resources.prepare([selected['source']], [selected['request']], self.cache,
                                          locale=self.index.query(limit=1)['snapshot']['locale'], copy_packages=False)
            broker = resources.Broker(prepared['manifest'], prepared['manifest_sha256'])
            row = dict(prepared['catalog']['items'][0], broker_port=PORT)
            if row['status'] != 'resolved':
                raise ValueError(row.get('reason') or 'Selected package assets could not be verified.')
            self.assets[row['resource_id']] = broker
            self.asset_sources[row['resource_id']] = selected['item']['part_id']
            if len(self.assets) > 1024:
                # Old native rows become unavailable rather than silently rebinding.
                oldest = next(iter(self.assets))
                del self.assets[oldest]
                del self.asset_sources[oldest]
            ident = selected['item']['part_id']
            with self.preference_lock:
                self.recent = [ident] + [old for old in self.recent if old != ident][:199]
                self._save()
                favorite = ident in self.favorites
            item = dict(selected['item']); item.pop('package_path'); item['favorite']=favorite
            return {'ok': True, 'index_sha256': self.index.expected, 'item': item, 'resource': row,
                    'swatches': self.index.swatches(item['part_id'], request.get('swatch_offset', 0)),
                    'request': selected['request'], 'game_contacted': False,
                    'effective_load_source_verified': False, 'equip_verified': False}

    def images(self, request):
        if (not isinstance(request, dict) or set(request) != {'part_ids', 'index_sha256', 'gender'} or
                request['index_sha256'] != self.index.expected or request['gender'] not in ('male', 'female') or
                not isinstance(request['part_ids'], list) or not 0 < len(request['part_ids']) <= 24 or
                len(set(request['part_ids'])) != len(request['part_ids'])):
            raise ValueError('Images require one bounded exact catalog selection and explicit thumbnail gender.')
        ids = [resources.sha(ident) for ident in request['part_ids']]
        with self.lock:
            page = self.index.query(part_ids=ids, limit=len(ids))
            items = {row['part_id']: row for row in page['items']}
            if set(items) != set(ids) or any(row['status'] != 'indexed' for row in items.values()):
                raise ValueError('Image item is absent or unclassified in this pinned index.')
            sources, selected = {}, {}
            for item in items.values():
                sources[item['package_path']] = dict(path=item['package_path'], origin=item['origin'],
                                                     expected_sha256=item['package_sha256'])
                ident = resources.digest((item['resource_tgi'] + '\n' + item['resource_sha256']).encode('ascii'))
                selected[ident] = dict(resource_tgi=item['resource_tgi'], effective_resource_sha256=item['resource_sha256'],
                                      body_type=item['body_type'], gender=request['gender'])
            providers=self.index.thumbnail_sources(list(items.values()),request['gender'])
            prepared = resources.prepare(list(sources.values()) + [p for p in providers if p['path'] not in sources], list(selected.values()), self.cache,
                                          locale=page['snapshot']['locale'], copy_packages=False)
            broker = resources.Broker(prepared['manifest'], prepared['manifest_sha256'])
            rows = {row['resource_id']: dict(row, broker_port=PORT) for row in prepared['catalog']['items']}
            result = []
            for part_id in ids:
                item = items[part_id]
                ident = resources.digest((item['resource_tgi'] + '\n' + item['resource_sha256']).encode('ascii'))
                self.assets[ident] = broker; self.asset_sources[ident] = part_id
                result.append(dict(part_id=part_id, resource=rows[ident]))
            while len(self.assets) > 1024:
                oldest = next(iter(self.assets)); del self.assets[oldest]; del self.asset_sources[oldest]
            return dict(ok=True, index_sha256=self.index.expected, gender=request['gender'], part_ids=ids,
                        items=result, game_contacted=False)

    def favorite(self, request):
        if (not isinstance(request, dict) or set(request) != {'part_id', 'index_sha256', 'enabled'} or
                request['index_sha256'] != self.index.expected or type(request['enabled']) is not bool):
            raise ValueError('Favorite must use this exact item snapshot and a boolean.')
        ident = resources.sha(request['part_id'])
        with self.preference_lock:
            if not self.index.query(part_ids=[ident], limit=1)['items']:
                raise ValueError('Favorite item is absent from this snapshot.')
            if request['enabled']:
                if ident not in self.favorites and len(self.favorites) >= 10000:
                    raise ValueError('Favorite bound reached.')
                self.favorites.add(ident)
            else:
                self.favorites.discard(ident)
            self._save()
            return dict(request, ok=True, game_contacted=False)

    def thumbnail(self, ident):
        with self.lock:
            return self.assets[resources.sha(ident)].thumbnail(ident)

    def open(self, ident, proof):
        with self.lock:
            ident = resources.sha(ident)
            row = self.assets[ident].records[ident]['row']
            if (resources.sha(proof) != row['cache_proof'] or row['status'] != 'resolved' or
                    row['studio_open']['status'] != 'ready'):
                raise ValueError('Studio open requires the exact inspected item proof.')
            # Browsing and thumbnails never copy whole EA/CC packages. Only
            # an explicit open revalidates its source and creates the sealed
            # copy, followed by Studio's independent editable copy.
            selected = resolve(self.index.path, self.index.expected, self.asset_sources[ident])
            prepared = resources.prepare([selected['source']], [selected['request']], self.cache,
                                          locale=self.index.query(limit=1)['snapshot']['locale'])
            broker = resources.Broker(prepared['manifest'], prepared['manifest_sha256'])
            fresh = broker.records[ident]['row']
            return broker.open(ident, fresh['cache_proof'])


def handler(browser):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self):
            port = self.server.server_port
            hosts = ('127.0.0.1:' + str(port), 'localhost:' + str(port))
            return self.headers.get('Host') in hosts and self.headers.get('Origin') in (
                None, 'http://' + hosts[0], 'http://' + hosts[1])

        def reply(self, status, value, kind='application/json'):
            raw = value if isinstance(value, bytes) else resources.canonical(value)
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            try:
                if not self.allowed():
                    raise ValueError('Loopback origin required.')
                match = re.fullmatch(r'/v1/resources/([0-9a-f]{64})/thumbnail', self.path)
                if match is None:
                    raise ValueError('Unknown typed route.')
                self.reply(200, browser.thumbnail(match.group(1)), 'image/png')
            except (KeyError, ValueError, OSError) as error:
                self.reply(409, {'ok': False, 'reason': str(error)})

        def do_POST(self):
            try:
                if self.headers.get('Transfer-Encoding'):
                    raise ValueError('Loopback bounded JSON required.')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY:
                    raise ValueError('Invalid request length.')
                # Consume only a bounded, timed body before rejecting an origin
                # or content type. Closing over unread bytes can reset Windows
                # TCP before the client receives the typed 409 response.
                self.connection.settimeout(3)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('Incomplete bounded JSON body.')
                if not self.allowed() or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Loopback bounded JSON required.')
                request = json.loads(raw)
                if self.path == '/v1/catalog/query':
                    result = browser.query(request)
                elif self.path == '/v1/catalog/inspect':
                    result = browser.inspect(request)
                elif self.path == '/v1/catalog/images':
                    result = browser.images(request)
                elif self.path == '/v1/catalog/favorite':
                    result = browser.favorite(request)
                elif self.path in ('/v1/tray/query','/v1/tray/image','/v1/tray/inspect'):
                    result = browser.tray(self.path.rsplit('/',1)[1], request)
                elif self.path == '/v1/open' and isinstance(request, dict) and set(request) == {'resource_id', 'cache_proof'}:
                    result = browser.open(request['resource_id'], request['cache_proof'])
                else:
                    raise ValueError('Unknown typed route or fields.')
                self.reply(200, result)
            except (KeyError, TypeError, ValueError, OSError) as error:
                self.reply(409, {'ok': False, 'reason': str(error)})
    return Handler


def serve(index, expected, tray_root=None):
    browser = Browser(index, expected, tray_root=tray_root)
    try:
        with LoopbackHTTPServer(('127.0.0.1', PORT), handler(browser)) as server:
            server.daemon_threads = True
            print(json.dumps({'ok': True, 'endpoint': 'http://127.0.0.1:' + str(PORT),
                              'index_sha256': expected, 'game_contacted': False}), flush=True)
            server.serve_forever(poll_interval=0.25)
    finally:
        browser.index.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', required=True)
    parser.add_argument('--expected-index-sha256', required=True)
    parser.add_argument('--tray-root', type=Path)
    options = parser.parse_args()
    serve(options.index, options.expected_index_sha256, options.tray_root)
