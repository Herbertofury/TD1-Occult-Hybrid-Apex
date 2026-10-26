"""Single-owner loopback listener for Apex's local asset services."""
from http.server import ThreadingHTTPServer
import socket


class LoopbackHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if self.server_address[0] != '127.0.0.1':
            raise ValueError('Apex asset services require exact IPv4 loopback.')
        # Windows SO_REUSEADDR lets different processes bind one endpoint and
        # receive requests unpredictably. Exclusive ownership precedes bind.
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()
