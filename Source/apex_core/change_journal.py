"""Persistent, revision-checked appearance transactions and preserved branches.

Game services/HTTP do not belong here. The owner supplies bounded serialized
state and read/write callbacks. Every restore is recorded; states never vanish
when editing after undo. A pending write is persisted before touching the Sim.
"""
import base64
import copy
import hashlib
import json
import os
import tempfile
import time
import uuid

MAX_STATE = 8 * 1024 * 1024
MAX_JOURNAL = 64 * 1024 * 1024


def fingerprint(raw):
    if not isinstance(raw, bytes):
        raise ValueError('Appearance snapshot must retain its original bytes.')
    return hashlib.sha256(raw).hexdigest()


def encoded(raw):
    fingerprint(raw)
    return base64.b64encode(raw).decode('ascii')


def decoded(value):
    raw = base64.b64decode(value, validate=True)
    fingerprint(raw)
    return raw


class ChangeJournal:
    def __init__(self, path, lane, normalize=None, representation=None, capture_record=None):
        self.path, self.lane = path, str(lane)
        self.capture_record = capture_record
        self.data = {'schema': 1, 'lane': self.lane, 'cursor': None, 'nodes': [], 'operations': [], 'pending': None}
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as stream:
                self.data = json.load(stream)
            if self.data.get('schema') != 1 or self.data.get('lane') != self.lane:
                raise ValueError('History belongs to a different Sim/form/save lane.')
            identities = set()
            for node in self.data['nodes']:
                if node['id'] in identities or fingerprint(decoded(node['state'])) != node['sha256']:
                    raise ValueError('Corrupt/duplicate history state; no restore allowed.')
                if node['parent'] is not None and node['parent'] not in identities:
                    raise ValueError('History parent is missing.')
                if 'sim_record' in node:
                    from .sim_record import restore
                    restore(node['sim_record'])
                identities.add(node['id'])
            if self.data['cursor'] is not None and self.data['cursor'] not in identities:
                raise ValueError('History cursor is missing.')
            pending = self.data.get('pending')
            if pending and (pending['parent'] not in identities or
                fingerprint(decoded(pending['before'])) != pending['before_sha256'] or
                fingerprint(decoded(pending['after'])) != pending['after_sha256'] or
                (pending['restore_node'] is not None and pending['restore_node'] not in identities)):
                raise ValueError('Corrupt pending recovery state; no restore allowed.')
        if representation:
            prior = self.data.get('representation')
            if prior not in (None, representation):
                raise ValueError('History uses an incompatible appearance representation.')
            if prior is None:
                # Preserve every original snapshot while migrating verification
                # identities. Category order is not a lost appearance change.
                for node in self.data['nodes']:
                    raw = normalize(decoded(node['state']))
                    if fingerprint(raw) != node['sha256']:
                        node['original_state'], node['original_sha256'] = node['state'], node['sha256']
                        node['state'], node['sha256'] = encoded(raw), fingerprint(raw)
                pending = self.data.get('pending')
                if pending:
                    for name in ('before', 'after'):
                        raw = normalize(decoded(pending[name]))
                        if fingerprint(raw) != pending[name + '_sha256']:
                            pending['original_' + name] = pending[name]
                            pending['original_' + name + '_sha256'] = pending[name + '_sha256']
                            pending[name], pending[name + '_sha256'] = encoded(raw), fingerprint(raw)
                self.data['representation'] = representation
                if os.path.exists(path):
                    self._save()

    def _save(self):
        raw = json.dumps(self.data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        folder = os.path.dirname(os.path.abspath(self.path))
        if 'the sims 4 do not fucking touch!!!' in [part.casefold() for part in os.path.normpath(folder).split(os.sep)]:
            raise ValueError('Protected original is read-only.')
        os.makedirs(folder, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
                temporary = stream.name
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _node(self, identity):
        return next(node for node in self.data['nodes'] if node['id'] == identity)

    def _append(self, label, raw, parent, record=None):
        node = {'id': uuid.uuid4().hex, 'parent': parent, 'label': str(label)[:160], 'time': time.time(),
                'sha256': fingerprint(raw), 'state': encoded(raw)}
        if record is not None or self.capture_record is not None:
            node['sim_record'] = record if record is not None else self.capture_record()
        self.data['nodes'].append(node)
        self.data['cursor'] = node['id']
        return node

    def observe(self, raw, label='Observed external appearance change', force=False):
        if self.data['pending']:
            raise ValueError('Resolve the interrupted transaction before observing a new state.')
        record = self.capture_record() if self.capture_record else None
        if not force and self.data['cursor'] and self._node(self.data['cursor'])['sha256'] == fingerprint(raw):
            prior_records = [item.get('sim_record') for item in self.data['operations'] if item.get('sim_record')]
            prior_record = prior_records[-1] if prior_records else self._node(self.data['cursor']).get('sim_record')
            if record is not None and (prior_record is None or prior_record['sha256'] != record['sha256']):
                # Runtime/gameplay observations remain complete, but do not
                # advance the appearance cursor or intercept the next Undo.
                self.data['operations'].append({'kind': 'observed-native-record', 'node': self.data['cursor'],
                                                'time': time.time(), 'sim_record': record})
                self._save()
            return self.data['cursor']
        previous = copy.deepcopy(self.data)
        try:
            node = self._append(label, raw, self.data['cursor'], record)
            self.data['operations'].append({'kind': 'observe', 'id': node['id'], 'time': time.time()})
            self._save()
            return node['id']
        except Exception:
            self.data = previous
            raise

    def prepare(self, label, before, after, restore_node=None):
        if self.data['pending']:
            raise ValueError('An accepted transaction is still pending.')
        self.observe(before, 'Captured current appearance')
        if restore_node is not None and self._node(restore_node)['sha256'] != fingerprint(after):
            raise ValueError('Restore state identity does not match its target node.')
        pending = {'id': uuid.uuid4().hex, 'parent': self.data['cursor'], 'label': str(label)[:160],
                   'before': encoded(before), 'before_sha256': fingerprint(before),
                   'after': encoded(after), 'after_sha256': fingerprint(after), 'restore_node': restore_node,
                   'time': time.time(), 'stage': 'prepared'}
        self.data['pending'] = pending
        try:
            self._save()
        except Exception:
            self.data['pending'] = None
            raise
        return pending['id']

    def _finish(self, pending, recovered=False):
        if pending['restore_node']:
            self.data['cursor'] = pending['restore_node']
            node_id = pending['restore_node']
        else:
            node_id = self._append(pending['label'], decoded(pending['after']), pending['parent'])['id']
        operation_record = self.capture_record() if self.capture_record else None
        self.data['operations'].append({'id': pending['id'], 'kind': pending['label'], 'node': node_id,
            'sim_record': operation_record,
            'from': pending['parent'], 'time': time.time(), 'readback_verified': True, 'recovered': recovered,
            'save_reload_verified': False})
        self.data['pending'] = None
        self._save()
        return node_id

    def apply(self, identity, read, write):
        pending = self.data['pending']
        if not pending or pending['id'] != identity:
            raise ValueError('Unknown/expired preview identity.')
        if fingerprint(read()) != pending['before_sha256']:
            self.data['operations'].append({'id': identity, 'kind': 'rejected-stale', 'time': time.time()})
            self.data['pending'] = None
            self._save()
            raise ValueError('Appearance changed after preview; it was not overwritten.')
        pending['stage'] = 'applying'
        self._save()
        try:
            write(decoded(pending['after']))
            if fingerprint(read()) != pending['after_sha256']:
                raise ValueError('Appearance readback differs from the accepted preview.')
        except Exception:
            if fingerprint(read()) != pending['before_sha256']:
                write(decoded(pending['before']))
            if fingerprint(read()) != pending['before_sha256']:
                pending['stage'] = 'rollback-failed'
                self._save()
                raise ValueError('Rollback was not verified; preserve the recovery journal.')
            self.data['operations'].append({'id': identity, 'kind': 'failed-rolled-back', 'time': time.time()})
            self.data['pending'] = None
            self._save()
            raise
        return self._finish(pending)

    def cancel(self, identity):
        pending = self.data['pending']
        if not pending or pending['id'] != identity or pending['stage'] != 'prepared':
            raise ValueError('Only a prepared preview can be cancelled.')
        self.data['operations'].append({'id': identity, 'kind': 'cancel', 'time': time.time()})
        self.data['pending'] = None
        self._save()

    def recover(self, current):
        pending = self.data['pending']
        if not pending:
            return 'No interrupted transaction.'
        actual = fingerprint(current)
        if actual == pending['after_sha256']:
            self._finish(pending, recovered=True)
            return 'Recovered an already-applied, readback-matching transaction.'
        if actual == pending['before_sha256']:
            self.data['operations'].append({'id': pending['id'], 'kind': 'recovered-unapplied', 'time': time.time()})
            self.data['pending'] = None
            self._save()
            return 'Recovered the unchanged pre-transaction state.'
        raise ValueError('Current appearance matches neither interrupted state; choose recovery explicitly.')

    def restore(self, kind, current, node=None):
        if not self.data['cursor'] or fingerprint(current) != self._node(self.data['cursor'])['sha256']:
            raise ValueError('Newer external edits exist; capture them before restoring history.')
        cursor = self._node(self.data['cursor'])
        if kind == 'Undo':
            node = cursor['parent']
            # Preserve old redundant observations on disk, while an appearance
            # Undo goes back to the preceding distinct state.
            while node is not None and self._node(node)['sha256'] == cursor['sha256']:
                node = self._node(node)['parent']
        elif kind == 'Redo' and node is None:
            children = [item['id'] for item in self.data['nodes'] if item['parent'] == cursor['id']]
            if len(children) != 1:
                raise ValueError('Select the redo branch explicitly.')
            node = children[0]
        if node is None:
            raise ValueError('No history state is available for this operation.')
        if kind == 'Redo':
            parent = self._node(node)['parent']
            while parent is not None and parent != cursor['id'] and self._node(parent)['sha256'] == cursor['sha256']:
                parent = self._node(parent)['parent']
            if parent != cursor['id']:
                raise ValueError('Selected node is not a redo branch of the current state.')
        return self.prepare(kind, current, decoded(self._node(node)['state']), restore_node=node)

    def timeline(self):
        return [{key: value for key, value in node.items() if key not in ('state', 'sim_record')} for node in self.data['nodes']]
