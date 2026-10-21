"""The loopback bridge must never follow redirects or load unrelated TLS state."""
import http.server
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli


class LocalBridgeHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', 'https://example.invalid/foreign')
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/html' if self.path == '/html' else 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_actual_http_json_does_not_construct_tls_or_use_proxy_environment(self):
        # Use the production get policy while routing only the local test port.
        original = apex_cli.urllib.request.OpenerDirector.open
        def local_open(opener, url, *args, **kwargs):
            return original(opener, url.replace(':8017', ':' + str(self.server.server_port)), *args, **kwargs)
        with patch.object(apex_cli.urllib.request.OpenerDirector, 'open', local_open), \
             patch.object(apex_cli.urllib.request, 'HTTPSHandler', side_effect=AssertionError('TLS setup')), \
             patch.dict('os.environ', {'HTTP_PROXY':'http://invalid.invalid:1', 'NO_PROXY':''}):
            self.assertEqual(apex_cli.get('/json', {'name':'a b'}), {'ok':True})
            with self.assertRaisesRegex(ValueError, 'redirects'):
                apex_cli.get('/redirect')
            with self.assertRaisesRegex(ValueError, 'non-JSON'):
                apex_cli.get('/html')

