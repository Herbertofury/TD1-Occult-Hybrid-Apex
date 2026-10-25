"""Canonical-owner adapter for the immutable native F11 mailbox.

No HTTP, worker, game-object transfer, disk scan or blocking Queue.wait occurs.
The caller supplies frozen loaded exports and the existing CommandQueue.
"""
from collections import OrderedDict
import json
import os
import re
import threading
import uuid
from urllib.parse import parse_qsl, urlsplit

ORIGIN = '_apex_native_origin'
LIMIT = 4 * 1024 * 1024


def _wire(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':'))


def _identity(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{32}', value) is not None


def _integer(value):
    return type(value) is int and 0 < value < 2**64


def _request(path):
    if not isinstance(path, str) or not 0 < len(path.encode('utf-8')) <= LIMIT or any(c in path for c in '\r\n\0'):
        raise ValueError('Bounded native request path required.')
    parts = urlsplit(path)
    if parts.scheme or parts.netloc or parts.fragment:
        raise ValueError('Native owner request must be local.')
    # Reject bad percent encodings rather than silently changing request bytes.
    if re.search('%(?![0-9a-fA-F]{2})', parts.query):
        raise ValueError('Native owner request has an invalid escape.')
    values = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=True, encoding='utf-8', errors='strict'):
        if key in values:
            raise ValueError('Native owner request repeats an intent field.')
        values[key] = value
    if parts.path == '/api/overlay/display':
        if set(values) - {'sim_id', 'count'}:
            raise ValueError('Native display accepts only a Sim and log count.')
        count = int(values.get('count', '220'))
        if not 0 <= count <= 260:
            raise ValueError('Native display log count is outside its bound.')
        return dict(action='overlay_display_status', sim_id=values.get('sim_id', ''), occult=None,
                    value=_wire({'count': count})), 2.5
    if parts.path != '/api/command' or set(values) - {'action', 'sim_id', 'occult', 'value'}:
        raise ValueError('Unsupported native owner route or intent field.')
    action = values.get('action', 'status').strip().lower()
    if re.fullmatch('[a-z0-9_]{1,80}', action) is None:
        raise ValueError('Typed native action required.')
    review = action in ('cas_bank_ui_status', 'cas_bank_ui_review', 'cas_bank_ui_prepare', 'cas_bank_ui_commit')
    return dict(action=action, sim_id=values.get('sim_id', ''), occult=values.get('occult'), value=values.get('value')), 60.0 if review else 8.0


class OwnerIngress:
    def __init__(self, queue, call, pending, owner_ident, nonce, pid, ready):
        self.queue, self.call, self.pending, self.owner_ident = queue, call, pending, owner_ident
        self.active = OrderedDict()
        self.runtime = None
        self.ready = ready
        self._owner()
        if not _identity(nonce) or type(pid) is not int or not 0 < pid <= 0xffffffff:
            raise ValueError('Exact runtime nonce and PID required.')
        result = call(dict(operation='bind', nonce=nonce, pid=pid))
        runtime = result.get('runtime')
        if (result.get('ok') is not True or not isinstance(runtime, dict) or
                set(runtime) != {'nonce', 'pid', 'owner', 'epoch'} or runtime['nonce'] != nonce or
                runtime['pid'] != pid or not _integer(runtime['owner']) or not _integer(runtime['epoch'])):
            raise ValueError('Native owner runtime did not bind.')
        self.runtime = dict(runtime)

    def _owner(self):
        if threading.current_thread().ident != self.owner_ident or self.queue.owner != self.owner_ident:
            raise ValueError('Native ingress requires the canonical Sims owner.')

    def _control(self, operation, **fields):
        return self.call(dict(operation=operation, runtime=self.runtime, **fields))

    def _publish(self, record, row):
        state = row.get('state')
        if row.get('request_id') != record['id'] or state not in ('pending', 'running', 'completed', 'failed', 'cancelled', 'unknown'):
            raise ValueError('Canonical queue lost the exact accepted UUID.')
        phase = ('terminal' if state in ('completed', 'failed', 'cancelled') else
                 'running' if state == 'running' else 'uncertain' if state == 'unknown' else 'submitted')
        # Freeze the exact canonical receipt once per state. A transport failure
        # retries publication of these bytes; it never repeats queue submission.
        if record.get('state') != state:
            record['outbound'] = _wire(row)
            record['state'] = state
        result = self._control('publish', ticket=record['ticket'], request_id=record['id'],
                               phase=phase, receipt=record['outbound'])
        record['retry'] = result.get('ok') is not True
        return not record['retry'], phase == 'terminal'

    def ingress(self):
        self._owner()
        if self.runtime is None or not self.pending():
            return 0
        packet = self._control('take')
        job = packet.get('job')
        if job is None:
            return 0
        if (packet.get('ok') is not True or not isinstance(job, dict) or
                set(job) != {'ticket', 'request_id', 'selection', 'request'} or
                not _integer(job['ticket']) or not _identity(job['request_id']) or
                type(job['selection']) is not int or not 0 <= job['selection'] < 2**64):
            raise ValueError('Native ingress packet is untyped.')
        rid = job['request_id']
        if rid in self.active:
            raise ValueError('A claimed native UUID was delivered twice.')
        record = dict(id=rid, ticket=job['ticket'], selection=job['selection'])
        self.active[rid] = record
        prior = self.queue.status(rid)
        if prior.get('state') != 'unknown':
            # A collision cannot be described as cancellation: an existing
            # canonical UUID might already own a different running action.
            record['refused'] = row = dict(ok=False, request_id=rid, state='unknown',
                message='Native UUID collides with an existing canonical owner; no native action was submitted.')
            self._publish(record, row)
            return 1
        try:
            payload, ttl = _request(job['request'])
            if self.ready(payload['action']) is not True:
                raise ValueError('The canonical game bridge is not ready for this action.')
            origin = dict(runtime=self.runtime, ticket=job['ticket'], request_id=rid, selection=job['selection'])
            payload[ORIGIN] = origin
            record['payload'] = payload
            row = self.queue.submit(payload, ttl=ttl, request_id=rid)
            if row.get('state') == 'rejected':
                raise ValueError(row.get('message', 'Canonical owner queue rejected before execution.'))
        except (ValueError, TypeError, UnicodeError) as error:
            # This transport accepted the UUID, but no domain action was queued.
            # Publish an exact, explicit pre-execution cancellation for that UUID.
            record['refused'] = row = dict(ok=False, request_id=rid, state='cancelled',
                result=dict(ok=False, owner_queue_accepted=False, message=str(error)))
        published, terminal = self._publish(record, row)
        if published and terminal:
            del self.active[rid]
        return 1

    def before_execute(self, payload):
        self._owner()
        if ORIGIN not in payload:
            return
        origin = payload[ORIGIN]
        if not isinstance(origin, dict):
            raise ValueError('Native origin is untyped.')
        record = self.active.get(origin.get('request_id'))
        if record is None or record.get('payload') != payload:
            raise ValueError('Native action bytes changed after owner admission.')
        authorized = self._control('authorize', ticket=record['ticket'], request_id=record['id'])
        if authorized.get('ok') is not True:
            raise ValueError('Native owner runtime or selected-Sim generation changed; no action executed.')
        published, _ = self._publish(record, self.queue.status(record['id']))
        if not published:
            raise ValueError('Native running receipt could not be retained; no action executed.')

    def completions(self):
        self._owner()
        if not self.active:
            return 0
        rid, record = next(iter(self.active.items()))
        self.active.move_to_end(rid)
        row = record.get('refused') or self.queue.status(rid)
        if row.get('state') == record.get('state') and not record.get('retry'):
            return 0
        published, terminal = self._publish(record, row)
        record['retry'] = not published
        if published and terminal:
            del self.active[rid]
        return 1

    def retire(self):
        self._owner()
        published = True
        for rid, record in list(self.active.items()):
            if 'payload' in record:
                self.queue.cancel(rid, 'Zone changed before execution; native UUID will not be resubmitted.')
            try:
                retained, _ = self._publish(record, record.get('refused') or self.queue.status(rid))
                published = published and retained
            except Exception:
                published = False
        try:
            result = self._control('retire')
        finally:
            self.runtime = None
            self.active.clear()
        return result.get('ok') is True and published


_ADAPTER = None
_FAULT = None


def _canonical(backend):
    if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
        raise ValueError('Native mailbox lifecycle requires the canonical Sims owner.')


def _ingress(backend):
    global _ADAPTER
    _canonical(backend)
    if _ADAPTER is None:
        from . import overlay_loader
        binding = overlay_loader.owner_mailbox_binding(backend.__file__)
        if binding is None:
            return 0
        call, pending = binding
        _ADAPTER = OwnerIngress(backend._APEX_COMMANDS, call, pending, backend._APEX_GAME_THREAD_IDENT,
                                uuid.uuid4().hex, os.getpid(), backend._apex_owner_action_ready)
    return _ADAPTER.ingress()


def _completions(backend):
    _canonical(backend)
    return _ADAPTER.completions() if _ADAPTER is not None else 0


def before_execute(backend, payload):
    _canonical(backend)
    if ORIGIN not in payload:
        return
    if _ADAPTER is None:
        raise ValueError('Native action lost its retained canonical ingress owner.')
    _ADAPTER.before_execute(payload)


def retire(backend):
    global _ADAPTER, _FAULT
    _canonical(backend)
    if _ADAPTER is not None:
        try:
            _ADAPTER.retire()
        except Exception as error:
            _fault(backend, error)
        _ADAPTER = None
    _FAULT = None


def _fault(backend, error):
    global _ADAPTER, _FAULT
    if _FAULT is not None:
        return 0
    _FAULT = str(error)
    if _ADAPTER is not None:
        try:
            _ADAPTER.retire()
        except Exception:
            pass
        _ADAPTER = None
    try:
        backend._log('Native F11 ingress stopped with retained UUID outcomes: ' + _FAULT)
    except Exception:
        pass
    return 0


def ingress(backend):
    if _FAULT is not None:
        return 0
    try:
        return _ingress(backend)
    except Exception as error:
        return _fault(backend, error)


def completions(backend):
    if _FAULT is not None:
        return 0
    try:
        return _completions(backend)
    except Exception as error:
        return _fault(backend, error)
