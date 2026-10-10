"""Bounded transport-to-owner queue. Only the owner thread may execute a command."""
from collections import OrderedDict, deque
import copy
import threading
import time
import uuid


class CommandQueue:
    def __init__(self, capacity=48, completed_limit=128, clock=time.monotonic):
        self.capacity = capacity
        self.completed_limit = completed_limit
        self.clock = clock
        self.owner = threading.current_thread().ident
        self.lock = threading.RLock()
        self.pending = deque()
        self.records = OrderedDict()
        self.closed = False

    def bind_owner(self):
        with self.lock:
            if any(row['state'] == 'running' for row in self.records.values()):
                raise RuntimeError('Cannot transfer the owner during execution.')
            self.owner = threading.current_thread().ident

    def _prune(self):
        complete = [key for key, row in self.records.items() if row['state'] in ('completed', 'failed', 'cancelled')]
        for key in complete[:-self.completed_limit] if self.completed_limit else complete:
            del self.records[key]

    def submit(self, payload, ttl=8.0, request_id=None):
        if not isinstance(payload, dict) or not isinstance(payload.get('action'), str):
            raise ValueError('A typed command with an action is required.')
        if not 0 < ttl <= 60:
            raise ValueError('Command TTL must be between zero and 60 seconds.')
        payload = copy.deepcopy(payload)
        with self.lock:
            if self.closed:
                return {'ok': False, 'state': 'rejected', 'message': 'Command queue is closed.'}
            request_id = request_id or uuid.uuid4().hex
            existing = self.records.get(request_id)
            if existing:
                if existing['payload'] != payload:
                    raise ValueError('Request identity was reused for a different command.')
                return self._status(existing)
            if len(self.pending) >= self.capacity:
                return {'ok': False, 'state': 'rejected', 'message': 'Queue is full; no accepted command was dropped.'}
            row = {'request_id': request_id, 'payload': payload, 'state': 'pending',
                   'deadline': self.clock() + ttl, 'event': threading.Event(), 'result': None}
            self.records[request_id] = row
            self.pending.append(request_id)
            return self._status(row)

    def _status(self, row):
        return {'ok': row['state'] not in ('failed', 'cancelled'), 'request_id': row['request_id'],
                'state': row['state'], 'result': copy.deepcopy(row['result'])}

    def status(self, request_id):
        with self.lock:
            row = self.records.get(request_id)
            return self._status(row) if row else {'ok': False, 'state': 'unknown', 'request_id': request_id,
                                                  'message': 'Request is unknown or outside the retained completion window.'}

    def cancel(self, request_id, reason='Cancelled before execution.'):
        with self.lock:
            row = self.records.get(request_id)
            if row and row['state'] == 'pending':
                row['state'] = 'cancelled'
                row['result'] = {'ok': False, 'message': reason}
                row['event'].set()
                self.pending.remove(request_id)
                self._prune()
                return True
            return False

    def wait(self, request_id, seconds):
        with self.lock:
            row = self.records.get(request_id)
            if not row:
                return self.status(request_id)
            event = row['event']
        if not event.wait(seconds):
            self.cancel(request_id, 'Wait expired; command cancelled before execution.')
        result = self.status(request_id)
        if result['state'] == 'running':
            result.update({'ok': False, 'message': 'Execution already started; outcome is pending. Query this request ID; do not retry the mutation.'})
        return result

    def drain(self, execute, max_commands=4, budget_seconds=0.02):
        if threading.current_thread().ident != self.owner:
            raise RuntimeError('Command execution is restricted to the bound game thread.')
        start = self.clock()
        count = 0
        while count < max_commands and self.clock() - start < budget_seconds:
            with self.lock:
                if not self.pending:
                    break
                row = self.records[self.pending.popleft()]
                if row['deadline'] <= self.clock():
                    row['state'] = 'cancelled'
                    row['result'] = {'ok': False, 'message': 'Command expired before execution.'}
                    row['event'].set()
                    self._prune()
                    continue
                row['state'] = 'running'
            try:
                result = execute(copy.deepcopy(row['payload']))
                if not isinstance(result, dict) or 'ok' not in result:
                    raise ValueError('Domain action returned no explicit verification result.')
            except Exception as error:
                result = {'ok': False, 'message': str(error)}
            with self.lock:
                row['result'] = result
                row['state'] = 'completed' if result['ok'] else 'failed'
                row['event'].set()
                self._prune()
            count += 1
        return count

    def shutdown(self):
        with self.lock:
            self.closed = True
            for request_id in list(self.pending):
                self.cancel(request_id, 'Queue closed before execution.')

    def metrics(self):
        with self.lock:
            return {'pending': len(self.pending), 'retained': len(self.records),
                    'capacity': self.capacity, 'completed_limit': self.completed_limit, 'closed': self.closed}
