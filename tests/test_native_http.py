import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_http


class Socket:
    def __init__(self, raw): self.raw = raw
    def settimeout(self, _): pass
    def recv(self, size):
        chunk, self.raw = self.raw[:size], self.raw[size:]; return chunk


class NativePostTests(unittest.TestCase):
    def wire(self, headers=''):
        body = json.dumps(dict(action='test_preview', request_id='a'*32, value='x'*20000)).encode()
        return ('POST /api/native HTTP/1.1\r\nHost: 127.0.0.1:8017\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body))+'\r\n'+headers+'\r\n').encode()+body
    def test_fragmented_large_fixed_control_body_is_read_in_full(self):
        raw = self.wire(); self.assertEqual(len(native_http.read(Socket(raw[17:]), raw[:17])['value']), 20000)
    def test_duplicate_length_foreign_origin_chunked_or_truncated_body_refuse(self):
        for headers in ('Content-Length: 1\r\n', 'Origin: https://evil.test\r\n', 'Transfer-Encoding: chunked\r\n'):
            with self.subTest(headers=headers), self.assertRaises(ValueError): native_http.read(Socket(b''), self.wire(headers))
        with self.assertRaisesRegex(ValueError, 'Truncated'): native_http.read(Socket(b''), self.wire()[:-1])
