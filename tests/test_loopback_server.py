from pathlib import Path
import socket
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from loopback_server import LoopbackHTTPServer


class ListenerTests(unittest.TestCase):
    def test_same_endpoint_cannot_be_owned_by_two_helpers(self):
        with LoopbackHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler) as first:
            with self.assertRaises(OSError):
                LoopbackHTTPServer(first.server_address, BaseHTTPRequestHandler)
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                self.assertEqual(first.socket.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE), 1)

    def test_existing_legacy_reuse_listener_cannot_be_shadowed(self):
        with ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler) as first:
            with self.assertRaises(OSError):
                LoopbackHTTPServer(first.server_address, BaseHTTPRequestHandler)

    def test_non_loopback_refuses_before_binding(self):
        with self.assertRaisesRegex(ValueError, 'exact IPv4 loopback'):
            LoopbackHTTPServer(('0.0.0.0', 0), BaseHTTPRequestHandler)
