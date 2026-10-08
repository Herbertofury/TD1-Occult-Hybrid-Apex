"""Fixed loopback CAS data transport, independent of gameplay client lifetime.

Only framed HELLO/POLL/ACK messages are accepted. No code, URLs, files, service
names, console text or untyped game actions are supplied by this listener.
Acknowledgements are routed back through the canonical game owner.
"""
import socket
import threading

HOST, PORT = '127.0.0.1', 8021
MAX_BYTES = 131072
_SERVER = None
_START_ERROR = None
_CLIENT_LIMIT = threading.BoundedSemaphore(4)


def frame(value):
    if not isinstance(value, str):
        raise ValueError('Use a textual CAS transport frame.')
    raw = value.encode('utf-8')
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('CAS transport frame exceeds its bound.')
    return ('{:08d}'.format(len(raw))).encode('ascii') + raw


def read_exact(connection, size):
    chunks = []
    while size:
        block = connection.recv(min(size, 16384))
        if not block:
            raise EOFError('CAS transport disconnected.')
        chunks.append(block)
        size -= len(block)
    return b''.join(chunks)


def read_frame(connection):
    header = read_exact(connection, 8)
    if any(value < 48 or value > 57 for value in header):
        raise ValueError('Invalid CAS frame length.')
    size = int(header)
    if not 0 < size <= MAX_BYTES:
        raise ValueError('CAS transport frame exceeds its bound.')
    return read_exact(connection, size).decode('utf-8', 'strict')


def packet(value, peer, attach, poll, acknowledge):
    """Pure typed routing; native actions can only come from the owned queue."""
    if value.startswith('HELLO|'):
        if peer is not None:
            raise ValueError('CAS peer is already bound.')
        token = attach(value[6:])
        return 'HELLO|' + token, token
    if peer is None:
        raise ValueError('CAS peer must identify its selected Sim first.')
    if value == 'POLL|' + peer:
        return poll(peer) or 'WAIT', peer
    fields = value.split('|', 3)
    if len(fields) == 4 and fields[0] == 'ACK' and fields[1] == peer:
        accepted = acknowledge(peer, fields[2], fields[3])
        if not accepted:
            raise ValueError('CAS owner did not accept the acknowledgement.')
        return 'ACK|' + fields[2], peer
    raise ValueError('Unsupported CAS transport message.')


def status():
    return {'bound': _SERVER is not None, 'host': HOST, 'port': PORT,
            'startup_error': _START_ERROR, 'native_connection_verified': False}


def start(acknowledge):
    global _SERVER, _START_ERROR
    if _SERVER is not None:
        return True
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((HOST, PORT))
        listener.listen(4)
    except OSError as exc:
        listener.close()
        _START_ERROR = str(exc)
        return False
    _SERVER = listener
    def client(connection):
        from .cas_ui import attach_client, poll_client, detach_client
        peer = None
        connection.settimeout(3)
        try:
            while True:
                value = read_frame(connection)
                response, peer = packet(value, peer, attach_client, poll_client, acknowledge)
                connection.sendall(frame(response))
        except (OSError, EOFError, ValueError, UnicodeError):
            pass  # An ambiguous claimed request remains pending; never replay.
        finally:
            if peer is not None:
                detach_client(peer)
            connection.close()
            _CLIENT_LIMIT.release()
    def accept():
        while True:
            try:
                connection, address = listener.accept()
                if address[0] != HOST or not _CLIENT_LIMIT.acquire(False):
                    connection.close()
                    continue
                threading.Thread(target=client, args=(connection,), daemon=True).start()
            except OSError:
                return
    threading.Thread(target=accept, daemon=True).start()
    return True
