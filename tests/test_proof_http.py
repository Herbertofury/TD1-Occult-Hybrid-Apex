"""Actual BaseHTTPRequestHandler parsing via an in-memory socket; no server/network."""
import io
import sys
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_resource_catalog as resources
import dbpf_build
import live_cas_browser
import test_cas_resource_catalog as fixtures


class InMemorySocket:
    def __init__(self, request):
        self.reader = io.BytesIO(request); self.response = bytearray()
    def makefile(self, mode, *args):
        if mode != 'rb': raise AssertionError('Unexpected write buffering')
        return self.reader
    def sendall(self, data): self.response.extend(data)
    def settimeout(self, value): pass


def http(handler, port, path, host=None):
    host = host or '127.0.0.1:' + str(port)
    request = ('GET ' + path + ' HTTP/1.1\r\nHost: ' + host + '\r\nConnection: close\r\n\r\n').encode('ascii')
    socket = InMemorySocket(request)
    handler(socket, ('127.0.0.1', 12345), Obj(server_port=port))
    head, body = bytes(socket.response).split(b'\r\n\r\n', 1)
    status = int(head.split(b'\r\n', 1)[0].split()[1])
    return status, head, body


class ProofHttpTests(unittest.TestCase):
    def setUp(self):
        unlink = Path.unlink
        def compat(path, missing_ok=False):
            try: return unlink(path)
            except FileNotFoundError:
                if not missing_ok: raise
        p = patch.object(Path, 'unlink', compat); p.start(); self.addCleanup(p.stop)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name); part = (resources.CASP, 0x80000000, 0xFEDCBA9876543210)
        data = fixtures.part(body=35); self.source = root / 'fixture.package'
        self.source.write_bytes(dbpf_build.build({part: data, (resources.CAS_THUMB, 2, part[2]): b'synthetic'}))
        request = {'resource_tgi': resources.tgi(part), 'effective_resource_sha256': resources.digest(data), 'gender': 'female'}
        with patch.object(resources, 'studio_executable', return_value=resources.STUDIO), \
             patch.object(resources, 'thumbnail_png', return_value=(b'synthetic-png', 2, 2)):
            result = resources.prepare([{'path': str(self.source), 'origin': 'mod'}], [request], root / 'cache')
        self.broker = resources.Broker(result['manifest'], result['manifest_sha256'])
        self.row = result['catalog']['items'][0]; self.ident = self.row['resource_id']; self.proof = self.row['cache_proof']
        self.browser = object.__new__(live_cas_browser.Browser); self.browser.lock = threading.RLock()
        self.browser.assets = {self.ident: self.broker}

    def test_http_proof_and_legacy_routes_on_both_handlers(self):
        for port, handler in ((8022, resources.handler(self.broker)), (8023, live_cas_browser.handler(self.browser))):
            with self.subTest(port=port):
                path = '/v1/resources/' + self.ident + '/thumbnail'
                legacy = http(handler, port, path)
                bound = http(handler, port, path + '?cache_proof=' + self.proof)
                self.assertEqual(legacy[0], 200); self.assertEqual(bound[0], 200)
                self.assertEqual(legacy[2], b'synthetic-png'); self.assertEqual(bound[2], legacy[2])
                self.assertIn(b'Content-Type: image/png', legacy[1]); self.assertIn(b'Content-Type: image/png', bound[1])
                self.assertIn(b'X-Apex-Thumbnail-Proof: 1', legacy[1]); self.assertIn(b'X-Apex-Thumbnail-Proof: 1', bound[1])
                expected = 404 if port == 8022 else 409
                for query in ('?cache_proof=' + '0'*64, '?cache_proof=', '?cache_proof=' + 'g'*64,
                              '?cache_proof=' + self.proof.upper(), '?cache_proof=' + self.proof + '&x=1',
                              '?cache_proof=' + self.proof + '&cache_proof=' + self.proof):
                    self.assertEqual(http(handler, port, path + query)[0], expected, query)
                absent = '/v1/resources/' + '0'*64 + '/thumbnail'
                self.assertEqual(http(handler, port, absent)[0], expected)
                self.assertEqual(http(handler, port, absent + '?cache_proof=' + self.proof)[0], expected)

    def test_stale_proof_refuses_without_returning_current_broker_image(self):
        for port, handler in ((8022, resources.handler(self.broker)), (8023, live_cas_browser.handler(self.browser))):
            with self.subTest(port=port):
                path = '/v1/resources/' + self.ident + '/thumbnail'
                status, _, body = http(handler, port, path + '?cache_proof=' + '0'*64)
                self.assertNotEqual(status, 200); self.assertNotEqual(body, b'synthetic-png')
                self.assertEqual(http(handler, port, path)[2], b'synthetic-png')

    def test_replacement_current_broker_rejects_old_proof_and_keeps_legacy_current(self):
        root = Path(self.temp.name); part = (resources.CASP, 0x80000000, 0xFEDCBA9876543210)
        data = fixtures.part(body=35); other = root / 'new.package'
        other.write_bytes(dbpf_build.build({part: data, (resources.CAS_THUMB, 2, part[2]): b'new'}))
        request = {'resource_tgi': resources.tgi(part), 'effective_resource_sha256': resources.digest(data), 'gender': 'female'}
        with patch.object(resources, 'studio_executable', return_value=resources.STUDIO), \
             patch.object(resources, 'thumbnail_png', return_value=(b'new-png', 2, 2)):
            prepared = resources.prepare([{'path': str(other), 'origin': 'mod'}], [request], root / 'new-cache')
        current = resources.Broker(prepared['manifest'], prepared['manifest_sha256'])
        newrow = prepared['catalog']['items'][0]
        self.assertEqual(newrow['resource_id'], self.ident); self.assertNotEqual(newrow['cache_proof'], self.proof)
        self.browser.assets[self.ident] = current
        for port, handler in ((8022, resources.handler(current)), (8023, live_cas_browser.handler(self.browser))):
            path = '/v1/resources/' + self.ident + '/thumbnail'
            self.assertEqual(http(handler, port, path)[2], b'new-png')
            self.assertEqual(http(handler, port, path + '?cache_proof=' + newrow['cache_proof'])[2], b'new-png')
            self.assertNotEqual(http(handler, port, path + '?cache_proof=' + self.proof)[0], 200)


if __name__ == '__main__': unittest.main()
