"""Fixed loopback CAS data transport, independent of gameplay client lifetime.

Only framed HELLO/POLL/ACK messages are accepted. No code, URLs, files, service
names, console text or untyped game actions are supplied by this listener.
Acknowledgements are routed back through the canonical game owner.
"""
import json
import socket
import threading
import time

HOST, PORT = '127.0.0.1', 8021
MAX_BYTES = 131072
IDLE_SECONDS = 3
CLAIM_SECONDS = 25
_SERVER = None
_START_ERROR = None
_LAST_CLIENT_ERROR = None
_CLIENT_LIMIT = threading.BoundedSemaphore(4)


def frame(value):
    if not isinstance(value, str):
        raise ValueError('Use a textual CAS transport frame.')
    raw = value.encode('utf-8')
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('CAS transport frame exceeds its bound.')
    return ('{:08d}'.format(len(raw))).encode('ascii') + raw


def read_exact(connection, size, deadline=None, clock=time.monotonic):
    chunks = []
    while size:
        if deadline is not None:
            remaining = deadline - clock()
            if remaining <= 0:
                raise socket.timeout('CAS frame exceeded its whole-frame deadline.')
            connection.settimeout(remaining)
        block = connection.recv(min(size, 16384))
        if not block:
            raise EOFError('CAS transport disconnected.')
        chunks.append(block)
        size -= len(block)
    return b''.join(chunks)


def read_frame(connection, deadline=None, clock=time.monotonic):
    header = read_exact(connection, 8, deadline, clock)
    if any(value < 48 or value > 57 for value in header):
        raise ValueError('Invalid CAS frame length.')
    size = int(header)
    if not 0 < size <= MAX_BYTES:
        raise ValueError('CAS transport frame exceeds its bound.')
    return read_exact(connection, size, deadline, clock).decode('utf-8', 'strict')


def response_wait(value, response):
    # A claimed command needs two or more UI ticks, possibly during an asset
    # stall. Give its owning nonce time to ACK; keep idle/handshake waits short.
    # This only extends transport lifetime. Peer/Sim/UUID checks and the ban on
    # replay remain in the canonical owner, including after a lost connection.
    if value.startswith('POLL|') and response != 'WAIT':
        return CLAIM_SECONDS
    fields = value.split('|', 3)
    if len(fields) == 4 and fields[0] == 'ACK' and response == 'ACK|' + fields[2]:
        # packet() has already routed this receipt through the canonical
        # owner. A prepared accept still owns its one later Timer invocation;
        # a short idle timeout must not discard a slow native refusal. This is
        # worker-only transport metadata, never permission to run game APIs.
        try:
            receipt = json.loads(fields[3])
        except (ValueError, TypeError):
            return IDLE_SECONDS
        if (isinstance(receipt, dict) and receipt.get('ok') is True and
                type(receipt.get('protocol')) is int and receipt['protocol'] == 1 and
                receipt.get('cas_request_id') == fields[2] and
                receipt.get('lifecycle_stage') == 'accept-intent' and
                receipt.get('commit_submitted') is False):
            return CLAIM_SECONDS
    return IDLE_SECONDS


def packet(value, peer, attach, poll, acknowledge, owner_mask=None):
    """Pure typed routing; native actions can only come from the owned queue."""
    if value.startswith('HELLO|'):
        if peer is not None:
            raise ValueError('CAS peer is already bound.')
        token = attach(value[6:])
        response = 'HELLO|' + token
        if owner_mask is not None:
            mask = owner_mask(token)
            if type(mask) is not int or not 0 <= mask <= 127 or mask and not mask & 1:
                raise ValueError('CAS membership display descriptor is untyped.')
            response += '|' + str(mask)
        return response, token
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
            'startup_error': _START_ERROR, 'last_client_error': _LAST_CLIENT_ERROR,
            'native_connection_verified': False}


def start(acknowledge, backend=None):
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
        global _LAST_CLIENT_ERROR
        from .cas_ui import attach_client, poll_client, detach_client, client_owned_mask, owner_metadata
        def poll(token):
            command = poll_client(token)
            return command or (owner_metadata(token, backend) if backend is not None else None)
        def attach(sim_id):
            token=attach_client(sim_id)
            try:
                if backend is not None:
                    from .native_cas_engine import entry_ready
                    entry_ready(backend,sim_id)
            except Exception:
                detach_client(token)
                raise
            return token
        peer = None
        wait_seconds = IDLE_SECONDS
        try:
            while True:
                # One absolute deadline covers header and payload, including
                # fragmented reads; arriving bytes do not renew it indefinitely.
                value = read_frame(connection, time.monotonic() + wait_seconds)
                response, peer = packet(value, peer, attach, poll, acknowledge, client_owned_mask)
                connection.settimeout(IDLE_SECONDS)
                connection.sendall(frame(response))
                wait_seconds = response_wait(value, response)
        except Exception as exc:
            # Keep one bounded diagnostic across reconnects. An ambiguous
            # claimed request stays pending; reporting a failure never replays it.
            _LAST_CLIENT_ERROR = {'type': type(exc).__name__, 'message': str(exc)[:256]}
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
