"""Form-bank receiver for explicit, several-owner CAS transactions.

Importing this module does nothing. Every operation runs on the authenticated
game thread and selected manager-owned Sim. Only this receiver reads/writes
appearance payloads; bridge callers supply hashes, lane decisions and typed
outfit hair intent. Raw schema-2 checkpoints are never synthesized from legacy
pending data or an old bank.

The JSON compare-and-swap uses an exclusive cooperative writer lease, verifies
the complete file, atomically replaces it and reads it back. BEFORE EXPOSING A
ROUTE, form_bank.load/save must delegate to load_for_write/save_from_read below,
preserving the read-bound whole-file revision, and every native mutation must
use the persistent gate. An editor that ignores the lease
can still replace the file during the final check/replace interval; this is not
an atomic filesystem CAS against uncooperating external writers.

No game hook/router is registered here. Only fresh captured native availability
may be restored; traits, form generation, old-process recovery and save-file
writes are outside this receiver's scope.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
from contextlib import contextmanager

from . import cas_commit_plan as primitive
from . import form_appearance as appearance
from . import form_bank, outfit_hair, sim_data
from .overlay_loader import _unlinked


_LOCK = threading.RLock()
_ACTIVE = {}
_CAPTURED = {}
_WRITER_LEASES = {}
_UNSPECIFIED = object()
ACTION_NAMES = ('cas_bank_begin', 'cas_bank_observe', 'cas_bank_prepare',
                'cas_bank_commit', 'cas_bank_status')


def _thread(backend):
    expected = getattr(backend, '_APEX_GAME_THREAD_IDENT', None)
    if type(expected) is not int or expected != threading.current_thread().ident:
        raise ValueError('CAS bank operations require the actual game thread.')


def _identity(backend, sim):
    _thread(backend)
    resolver = getattr(backend, '_get_sim_info_by_id', None)
    if sim is None or not callable(resolver) or resolver(sim.id) is not sim:
        raise ValueError('CAS bank requires the exact current manager-owned Sim.')
    if (getattr(sim.occult_tracker, '_apex_seal_recovery_required', False) or
            getattr(sim.occult_tracker, '_apex_cas_bank_recovery_required', False)):
        raise ValueError('Native appearance recovery remains unresolved.')
    return primitive._identity({'runtime_pid': os.getpid(), 'sim_id': str(sim.id),
        'household_id': str(sim.household_id),
        'save_guid': str(backend.services.get_persistence_service().get_save_slot_proto_guid())})


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate form-bank JSON key; no transaction authorized.')
        result[key] = value
    return result


def _read(path):
    path = _unlinked(path)
    if not path.exists():
        return {'schema': 1, 'records': {}}, None
    if not path.is_file():
        raise ValueError('Form bank is not a regular file.')
    raw = path.read_bytes()
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)
    if (not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1 or
            not isinstance(value.get('records'), dict)):
        raise ValueError('Invalid form bank; no metadata replaced.')
    primitive.digest(value)
    return value, hashlib.sha256(raw).hexdigest()


class AtomicBankDocument(dict):
    """A normal JSON mapping with its exact read revision held outside JSON."""

    def __init__(self, value, path, file_sha256):
        super(AtomicBankDocument, self).__init__(value)
        self._bank_path = str(_unlinked(path))
        if file_sha256 is not None and not primitive._hash(file_sha256):
            raise ValueError('Bank document revision must be an exact hash or expected absence.')
        self._bank_file_sha256 = file_sha256


def load_for_write(path):
    """NEXT-epoch form_bank.load delegate; compare against this read, not now."""
    path = _unlinked(path)
    data, file_hash = _read(path)
    return AtomicBankDocument(data, path, file_hash)


def save_from_read(path, data):
    """NEXT-epoch form_bank.save delegate; stale whole-bank writes refuse.

    Deep copies keep the revision attributes. Plain mappings may create an
    absent file, but never replace an existing bank without a read-bound hash.
    The revision advances only after exact durable acknowledgment/readback.
    """
    path = _unlinked(path)
    if isinstance(data, AtomicBankDocument):
        if data._bank_path != str(path):
            raise ValueError('Bank document belongs to another read path.')
        expected = data._bank_file_sha256
    else:
        _current, current_hash = _read(path)
        if current_hash is not None:
            raise ValueError('Plain unpinned data cannot replace an existing form bank.')
        expected = None
    receipt = atomic_save(path, data, expected_file_sha256=expected)
    if isinstance(data, AtomicBankDocument):
        data._bank_file_sha256 = receipt['file_sha256']
    return receipt


def _lease_path(path):
    return _unlinked(Path(path).with_name('.' + Path(path).name + '.cas-writer.lock'))


def _valid_lease(path, lease):
    path = _unlinked(path)
    if (_WRITER_LEASES.get(str(path)) is not lease or lease.get('path') != str(path) or
            lease.get('thread') != threading.current_thread().ident):
        raise ValueError('No receiver-owned bank writer lease.')
    held = _lease_path(path)
    if not held.is_file() or held.stat().st_size > 4096 or held.read_bytes() != lease['raw']:
        raise ValueError('Bank writer lease changed; no replacement authorized.')
    return held


@contextmanager
def _writer_lease(path):
    """Exclusive, nonreentrant protocol for participating source/host writers.

    A stale/unknown lease is retained for inspection. No automatic deletion,
    prior-process guessing, lock stealing, or timed expiry grants write access.
    """
    path = _unlinked(path)
    held = _lease_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({'schema': 1, 'pid': os.getpid(), 'token': uuid.uuid4().hex},
                     sort_keys=True, separators=(',', ':')).encode('ascii')
    try:
        descriptor = os.open(str(held), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
    except FileExistsError:
        raise ValueError('Bank writer lease is already held or interrupted; mutation is blocked.')
    lease = {'path': str(path), 'raw': raw, 'thread': threading.current_thread().ident}
    _WRITER_LEASES[str(path)] = lease
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(descriptor, raw[offset:])
            if count <= 0:
                raise OSError('Bank writer lease could not be written completely.')
            offset += count
        os.fsync(descriptor)
        _valid_lease(path, lease)
        yield lease
    finally:
        safe_to_remove = False
        try:
            _valid_lease(path, lease)
            safe_to_remove = True
        finally:
            _WRITER_LEASES.pop(str(path), None)
            os.close(descriptor)
        if safe_to_remove:
            os.unlink(str(held))


def atomic_save(path, data, expected_file_sha256=_UNSPECIFIED, _lease=None):
    """Shared JSON writer for the NEXT epoch's form_bank.save delegation.

    Callers outside a receiver transaction acquire their own exclusive lease.
    Only the receiver can pass a currently held object capability. Existing
    files always require the exact hash from the caller's original read; an
    unspecified revision cannot replace them. None requires file absence.
    All writers must preserve their read revision and participate; delegating
    only save without preserving load revisions does not meet this contract.
    A process exit retains the lease and pending bytes, requiring inspection.
    """
    path = _unlinked(path)
    if _lease is None:
        with _writer_lease(path) as lease:
            return atomic_save(path, data, expected_file_sha256, _lease=lease)
    _valid_lease(path, _lease)
    if (not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1 or
            not isinstance(data.get('records'), dict)):
        raise ValueError('Invalid form bank for shared atomic save.')
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False).encode('utf-8')
    _current, current_hash = _read(path)
    if expected_file_sha256 is _UNSPECIFIED:
        if current_hash is not None:
            raise ValueError('Existing bank writes require an exact read-bound file SHA; unspecified replacement is forbidden.')
        expected_file_sha256 = None
    if expected_file_sha256 is not None and not primitive._hash(expected_file_sha256):
        raise ValueError('Bank write requires an exact file SHA or expected absence.')
    if expected_file_sha256 is not _UNSPECIFIED and current_hash != expected_file_sha256:
        raise ValueError('Bank file hash differs under the writer lease; no replacement.')
    pending = _unlinked(path.with_suffix('.pending'))
    with pending.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _valid_lease(path, _lease)
    # Participating writers cannot enter this interval. An external tool that
    # ignores the lease remains outside this compare-and-swap contract.
    os.replace(str(pending), str(path))
    observed, _observed_hash = _read(path)
    if observed != data:
        raise ValueError('Shared atomic save failed complete JSON readback.')
    return {'durable': True, 'file_sha256': hashlib.sha256(raw).hexdigest()}


def _context(backend, sim, fresh=True):
    if fresh:
        identity = _identity(backend, sim)
    else:
        _thread(backend)
        identity = None
    path, key = form_bank.context(backend, sim)
    path = _unlinked(path)
    data, file_hash = _read(path)
    record = data['records'].get(key)
    if record is not None and not isinstance(record, dict):
        raise ValueError('Selected form-bank record is malformed.')
    return identity, path, key, data, file_hash, record


def _record_guard(record):
    value = copy.deepcopy(record)
    value.pop('pending', None)
    value.pop('cas_transaction', None)
    return primitive.digest(value)


def _token(value):
    return (isinstance(value, str) and len(value) == 32 and
            all(character in '0123456789abcdef' for character in value))


def _native_context_envelope(transaction, envelope):
    if 'native_occult_context' in transaction or 'native_occult_context_sha256' in transaction:
        from .native_occult_context import validate
        context = validate(transaction.get('native_occult_context'))
        context_hash = transaction.get('native_occult_context_sha256')
        if not primitive._hash(context_hash) or primitive.digest(context) != context_hash:
            raise ValueError('Native availability checkpoint changed; no restoration authority.')
        envelope['native_occult_context_sha256'] = context_hash
    return envelope


def _completed(transaction):
    """Validate a complete OWNED historical receipt before opening the gate.

    Subsequent legitimate edits may change the current bank; those edits do not
    invalidate an old completed receipt. Every link inside that receipt still
    must match. Historical completion never authorizes old appearance replay.
    """
    try:
        if (not isinstance(transaction, dict) or type(transaction.get('schema')) is not int or transaction['schema'] != 1 or
                not _token(transaction.get('transaction_id'))):
            return False
        identity = transaction.get('identity')
        if (not isinstance(identity, dict) or set(identity) != primitive.IDENTITY_FIELDS or
                type(identity['runtime_pid']) is not int or not 0 < identity['runtime_pid'] <= 0xffffffff or
                not all(primitive._id(identity[name]) for name in ('save_guid', 'household_id', 'sim_id')) or
                transaction.get('owner_key') != identity['save_guid'] + ':' + identity['sim_id']):
            return False
        names = ('checkpoint_sha256', 'transaction_sha256', 'record_guard_sha256',
                 'hair_checkpoint_sha256', 'metadata_guard_sha256')
        if not all(primitive._hash(transaction.get(name)) for name in names):
            return False
        hair = transaction.get('hair_checkpoint')
        if (not isinstance(hair, dict) or set(hair) != {'enabled', 'forms'} or
                type(hair['enabled']) is not bool or not isinstance(hair['forms'], dict) or
                primitive.digest(hair) != transaction['hair_checkpoint_sha256']):
            return False
        envelope = {'transaction_id': transaction['transaction_id'], 'identity': identity,
                    'checkpoint_sha256': transaction['checkpoint_sha256'],
                    'record_guard_sha256': transaction['record_guard_sha256'],
                    'hair_checkpoint_sha256': transaction['hair_checkpoint_sha256']}
        if primitive.digest(_native_context_envelope(transaction, envelope)) != transaction['transaction_sha256']:
            return False
        journal, ack = transaction.get('journal'), transaction.get('metadata_commit')
        if (not isinstance(journal, dict) or type(journal.get('schema')) is not int or journal['schema'] != 1 or journal.get('identity') != identity or
                journal.get('state') != 'completed' or journal.get('bank_committed') is not True or
                journal.get('save_reload_verified') is not False or
                journal.get('pending_sha256') != transaction['checkpoint_sha256'] or
                not isinstance(ack, dict) or set(ack) != {'committed', 'plan_sha256', 'bank_sha256',
                    'hair_policy_sha256', 'native_verified_receipt_sha256'} or ack.get('committed') is not True):
            return False
        original, returned, before_write = (journal.get('original_owners'), journal.get('raw_return'),
                                           journal.get('pre_write_owners'))
        def valid_raw(raw):
            if (not isinstance(raw, dict) or set(raw) != {'identity', 'stored', 'active'} or raw['identity'] != identity or
                    not isinstance(raw['stored'], dict) or not raw['stored'] or
                    not isinstance(raw['active'], dict) or set(raw['active']) != {'lane', 'fields'}):
                return False
            for lane, fields in raw['stored'].items():
                if (not isinstance(lane, str) or not lane.isascii() or not lane.isdecimal() or
                        str(int(lane)) != lane or not 0 < int(lane) < 1 << 32 or int(lane) & (int(lane) - 1)):
                    return False
                appearance.fingerprint(fields)
            if raw['active']['lane'] not in raw['stored']:
                return False
            return (appearance.fingerprint(raw['active']['fields'])['appearance_sha256'] ==
                    appearance.fingerprint(raw['stored'][raw['active']['lane']])['appearance_sha256'])
        if not all(valid_raw(raw) for raw in (original, returned, before_write)):
            return False
        if set(original['stored']) != set(returned['stored']) or set(original['stored']) != set(before_write['stored']):
            return False
        checkpoint = {'schema': 2, 'state': 'captured', 'runtime_pid': identity['runtime_pid'],
                      'lane': original['active']['lane'], 'identity': identity, 'original_owners': original}
        if (primitive.digest(checkpoint) != transaction['checkpoint_sha256'] or
                primitive.digest(returned) != journal.get('raw_return_sha256') or
                primitive.digest(before_write) != journal.get('pre_write_owners_sha256')):
            return False
        if hair['enabled']:
            if set(hair['forms']) != set(original['stored']):
                return False
            for held in hair['forms'].values():
                outfit_hair._held_index(held)
        elif hair['forms']:
            return False
        plan = journal.get('plan')
        if (not isinstance(plan, dict) or type(plan.get('schema')) is not int or plan['schema'] != 1 or plan.get('identity') != identity or
                plan.get('pending_sha256') != transaction['checkpoint_sha256'] or
                plan.get('raw_return_sha256') != journal['raw_return_sha256'] or
                plan.get('pre_write_owners_sha256') != journal['pre_write_owners_sha256'] or
                plan.get('automatic_intent_classification') is not False or
                not primitive._hash(journal.get('plan_sha256')) or primitive.digest(plan) != journal['plan_sha256'] or
                ack.get('plan_sha256') != journal['plan_sha256'] or
                not isinstance(plan.get('desired'), dict) or set(plan['desired']) != set(original['stored'])):
            return False
        changed = {lane for lane in original['stored'] if
                   appearance.fingerprint(original['stored'][lane])['appearance_sha256'] !=
                   appearance.fingerprint(returned['stored'][lane])['appearance_sha256']}
        rows = plan.get('dispositions')
        if not isinstance(rows, list) or len(rows) != len(changed):
            return False
        decisions = {}
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {'lane', 'action'} or row['lane'] not in changed or
                    row['lane'] in decisions or row['action'] not in primitive.DECISIONS):
                return False
            decisions[row['lane']] = row['action']
        accepted = {lane for lane, action in decisions.items() if action == 'accept-returned'}
        if plan.get('changed_lanes') != sorted(changed, key=int) or plan.get('accepted_lanes') != sorted(accepted, key=int):
            return False
        for lane, fields in plan['desired'].items():
            appearance.fingerprint(fields)
            if lane not in accepted:
                if fields != original['stored'][lane]:
                    return False
            elif ({name: value for name, value in fields.items() if name != '__outfits__'} !=
                  {name: value for name, value in returned['stored'][lane].items() if name != '__outfits__'}):
                return False
            elif not hair['enabled'] and fields != returned['stored'][lane]:
                return False
        if ack.get('bank_sha256') != primitive.digest(plan['desired']) or not primitive._hash(ack.get('hair_policy_sha256')):
            return False
        final = journal.get('final_native_appearance')
        if (not isinstance(final, dict) or final.get('verified') is not True or
                not isinstance(final.get('stored'), dict) or set(final['stored']) != set(plan['desired']) or
                final.get('active_lane') != plan.get('active_lane') or plan.get('active_lane') != returned['active']['lane'] or
                not primitive._hash(final.get('raw_final_owners_sha256')) or
                ack.get('native_verified_receipt_sha256') != primitive.digest(final)):
            return False
        desired_hashes = {lane: appearance.fingerprint(fields)['appearance_sha256'] for lane, fields in plan['desired'].items()}
        _verify_context_final(transaction, final, plan['active_lane'])
        return (final['stored'] == desired_hashes and
                final.get('active_appearance_sha256') == desired_hashes[plan['active_lane']])
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return False


def _blocked(record, owner_key=None):
    if record is None:
        return False
    if record.get('pending') is not None or record.get('switch_pending') is not None:
        return True
    transaction = record.get('cas_transaction')
    return transaction is not None and (not _completed(transaction) or
            owner_key is not None and transaction.get('owner_key') != owner_key)


def assert_idle(backend, sim):
    """Persistent gate, including a consumed pending with an incomplete ACK."""
    with _LOCK:
        _identity(backend, sim)
        _identity_row, path, key, _data, _file_hash, record = _context(backend, sim)
        if _blocked(record, key) or _lease_path(path).exists():
            raise ValueError('CAS bank checkpoint/journal is unresolved; native mutation is blocked.')
        return True


def _mutate(backend, sim, transform):
    """One selected-record CAS, preserving other Sims and unrelated metadata."""
    with _LOCK:
        _identity(backend, sim)
        path, _key = form_bank.context(backend, sim)
        with _writer_lease(path) as lease:
            identity, path, key, data, file_hash, record = _context(backend, sim)
            expected = copy.deepcopy(data)
            updated = transform(data, record, identity)
            if updated is not None:
                raise ValueError('CAS metadata transform must mutate only its owned clone.')
            if type(data.get('schema')) is not int or data['schema'] != 1:
                raise ValueError('CAS metadata cannot replace the form-bank schema.')
            for other_key, other_record in expected['records'].items():
                if other_key != key and data['records'].get(other_key) != other_record:
                    raise ValueError('CAS metadata attempted to modify another Sim.')
            if set(data['records']) - set(expected['records']) - {key}:
                raise ValueError('CAS metadata attempted to create another Sim record.')
            primitive.digest(data)
            current, current_hash = _read(path)
            if current_hash != file_hash or current != expected:
                raise ValueError('Complete form bank changed before compare-and-swap; no replacement.')
            if _identity(backend, sim) != identity:
                raise ValueError('Runtime changed before atomic form-bank replacement.')
            atomic_save(path, data, expected_file_sha256=file_hash, _lease=lease)
            observed, _observed_hash = _read(path)
            if observed != data or _identity(backend, sim) != identity:
                raise ValueError('Atomic form-bank replacement did not read back exactly.')


def _selected(backend, sim, token=None, allow_consumed=False):
    identity, path, key, data, file_hash, record = _context(backend, sim)
    transaction = record.get('cas_transaction') if record else None
    if (not isinstance(transaction, dict) or transaction.get('schema') != 1 or
            not _token(transaction.get('transaction_id')) or
            transaction.get('identity') != identity or transaction.get('owner_key') != key or
            not primitive._hash(transaction.get('checkpoint_sha256')) or
            not primitive._hash(transaction.get('transaction_sha256')) or
            not primitive._hash(transaction.get('record_guard_sha256')) or
            not primitive._hash(transaction.get('hair_checkpoint_sha256')) or
            not isinstance(transaction.get('hair_checkpoint'), dict) or
            token is not None and transaction['transaction_id'] != token):
        raise ValueError('No exact current-runtime CAS receiver transaction.')
    envelope = {'transaction_id': transaction['transaction_id'],
                'identity': identity, 'checkpoint_sha256': transaction['checkpoint_sha256'],
                'record_guard_sha256': transaction['record_guard_sha256'],
                'hair_checkpoint_sha256': transaction['hair_checkpoint_sha256']}
    if primitive.digest(_native_context_envelope(transaction, envelope)) != transaction['transaction_sha256']:
        raise ValueError('CAS transaction envelope changed; no request authorized.')
    if 'metadata_guard_sha256' in transaction:
        ack = transaction.get('metadata_commit')
        if (not isinstance(ack, dict) or ack.get('committed') is not True or record.get('pending') is not None or
                not primitive._hash(transaction['metadata_guard_sha256']) or
                ack.get('bank_sha256') != primitive.digest(record.get('bank')) or
                ack.get('hair_policy_sha256') != primitive.digest(record.get('hair_policy'))):
            raise ValueError('Consumed CAS checkpoint has no exact owned metadata receipt.')
    guard = transaction.get('metadata_guard_sha256', transaction['record_guard_sha256'])
    if _record_guard(record) != guard:
        raise ValueError('Unrelated selected-Sim bank/policy metadata changed during CAS.')
    if primitive.digest(transaction['hair_checkpoint']) != transaction['hair_checkpoint_sha256']:
        raise ValueError('Fresh CAS hair checkpoint changed; prior policy cannot substitute.')
    pending = record.get('pending')
    if pending is None:
        if not allow_consumed or not isinstance(transaction.get('metadata_commit'), dict):
            raise ValueError('CAS raw checkpoint was consumed or lost.')
    elif primitive.digest(pending) != transaction['checkpoint_sha256']:
        raise ValueError('CAS raw checkpoint hash changed.')
    return path, key, record, transaction


def _write_journal(backend, sim, token, document, expected_previous_sha256):
    expected_document_hash = primitive.digest(document)
    def update(data, record, identity):
        _path, _key, _record, transaction = _selected(backend, sim, token, allow_consumed=True)
        if record != _record:
            raise ValueError('Selected CAS record changed during journal compare-and-swap.')
        previous = transaction.get('journal')
        previous_hash = None if previous is None else primitive.digest(previous)
        if previous_hash != expected_previous_sha256:
            raise ValueError('CAS journal compare-and-swap hash differs.')
        if (document.get('identity') != identity or
                document.get('pending_sha256') != transaction['checkpoint_sha256']):
            raise ValueError('Journal belongs to another native checkpoint.')
        record['cas_transaction']['journal'] = copy.deepcopy(document)
        record['cas_transaction']['phase'] = document['state']
    _mutate(backend, sim, update)
    _path, _key, _record, transaction = _selected(backend, sim, token, allow_consumed=True)
    if primitive.digest(transaction.get('journal')) != expected_document_hash:
        raise ValueError('CAS journal readback differs after atomic bank save.')
    return {'durable': True, 'sha256': expected_document_hash}


def _verify_context_final(transaction, final, active_lane, backend=None, sim=None):
    checkpoint = transaction.get('native_occult_context')
    if checkpoint is None:
        if 'native_occult_context' in final or 'native_occult_restore' in transaction:
            raise ValueError('Uncaptured native availability cannot establish completion.')
        return
    from .native_occult_context import read, verify, verify_receipt
    restored = verify_receipt(checkpoint, transaction.get('native_occult_restore'), active_lane)
    expected = {'checkpoint_sha256': transaction['native_occult_context_sha256'],
                'restore_receipt_sha256': primitive.digest(restored),
                'observed': restored['after'], 'verified': True}
    if final.get('native_occult_context') != expected:
        raise ValueError('Final native availability lacks the captured, durable restore receipt.')
    if backend is not None:
        verify(checkpoint, read(backend, sim), active_lane)


def _commit_metadata(backend, sim, token, receipt):
    def update(data, record, identity):
        _path, _key, selected_record, transaction = _selected(backend, sim, token)
        if record != selected_record:
            raise ValueError('CAS record changed before bank commit.')
        journal = transaction.get('journal')
        if (not isinstance(journal, dict) or journal.get('state') != 'verified' or
                receipt.get('identity') != identity or
                receipt.get('pending_sha256') != transaction['checkpoint_sha256'] or
                receipt.get('plan_sha256') != journal.get('plan_sha256') or
                primitive.digest(receipt['bank']) != primitive.digest(journal['plan']['desired']) or
                receipt['final_native_appearance'] != journal['final_native_appearance'] or
                receipt['final_native_appearance'].get('verified') is not True or
                receipt['active_lane'] != journal['plan']['active_lane']):
            raise ValueError('No complete verified native-owner receipt for the bank commit.')
        _verify_context_final(transaction, receipt['final_native_appearance'], receipt['active_lane'], backend, sim)
        history = record.setdefault('history', [])
        if not isinstance(history, list):
            raise ValueError('CAS history must retain its typed index.')
        # All parsing below is pure and runs on the owned clone. No metadata is
        # replaced unless every desired wardrobe can be captured successfully.
        policy = copy.deepcopy(record.get('hair_policy'))
        if transaction['hair_checkpoint']['enabled']:
            if not isinstance(policy, dict) or policy.get('enabled') is not True:
                raise ValueError('Enabled hair policy changed during CAS.')
            policy['forms'] = {lane: outfit_hair.capture(backend, fields)
                               for lane, fields in receipt['bank'].items()}
        record['bank'] = copy.deepcopy(receipt['bank'])
        if policy is not None:
            record['hair_policy'] = policy
        record['active_lane'] = receipt['active_lane']
        record['runtime_pid'] = os.getpid()
        record['native_rebase_requires_cas_completion'] = False
        record['pending'] = None
        history.append({'state': 'completed', 'transaction_id': token,
                        'kind': 'explicit-all-owner-cas-appearance',
                        'plan_sha256': receipt['plan_sha256'],
                        'checkpoint_sha256': transaction['checkpoint_sha256'],
                        'accepted_lanes': list(journal['plan']['accepted_lanes']),
                        'save_reload_verified': False})
        record['cas_transaction']['metadata_commit'] = {
            'committed': True, 'plan_sha256': receipt['plan_sha256'],
            'bank_sha256': primitive.digest(record['bank']),
            'hair_policy_sha256': primitive.digest(record.get('hair_policy')),
            'native_verified_receipt_sha256': primitive.digest(receipt['final_native_appearance'])}
        record['cas_transaction']['metadata_guard_sha256'] = _record_guard(record)
    _mutate(backend, sim, update)
    _path, _key, _record, transaction = _selected(backend, sim, token, allow_consumed=True)
    ack = transaction.get('metadata_commit')
    if not isinstance(ack, dict) or ack.get('plan_sha256') != receipt['plan_sha256'] or ack.get('committed') is not True:
        raise ValueError('Atomic bank commit lacks exact persisted acknowledgment.')
    _verify_context_final(transaction, receipt['final_native_appearance'], receipt['active_lane'], backend, sim)
    return {'committed': True, 'plan_sha256': receipt['plan_sha256']}


class _HairTransaction(primitive.CasCommitTransaction):
    """Trusted policy planner; external callers can never supply its fields."""

    def __init__(self, *args, **kwargs):
        self.hair_checkpoint = kwargs.pop('hair_checkpoint')
        self.native_context_final = kwargs.pop('native_context_final', None)
        super(_HairTransaction, self).__init__(*args, **kwargs)

    def _verify_desired(self):
        final = super(_HairTransaction, self)._verify_desired()
        if self.native_context_final is not None:
            final['native_occult_context'] = self.native_context_final(self.plan['active_lane'])
        return final

    def prepare(self, expected_pending_sha256, expected_raw_return_sha256,
                dispositions, hair_targets=None):
        # Validate the underlying explicit dispositions before any policy can
        # turn a changed/unknown owner into accepted appearance authority.
        if self.state != 'observed':
            raise ValueError('Hair planning requires a complete observed CAS return.')
        self._guard()
        if (expected_pending_sha256 != self.pending_sha256 or
                expected_raw_return_sha256 != self.raw_return_sha256):
            raise ValueError('CAS hair plan hashes differ from this native checkpoint.')
        raw = self.document['raw_return']
        primitive._consistent(raw)
        original = self.pending['original_owners']['stored']
        returned = raw['stored']
        changed = {lane for lane in original if appearance.fingerprint(original[lane])['appearance_sha256'] !=
                   appearance.fingerprint(returned[lane])['appearance_sha256']}
        if not isinstance(dispositions, list) or len(dispositions) != len(changed):
            raise ValueError('Every changed CAS lane requires one explicit disposition.')
        accepted, seen = set(), set()
        for row in dispositions:
            if (not isinstance(row, dict) or set(row) != {'lane', 'action'} or
                    not isinstance(row['lane'], str) or row['lane'] not in changed or row['lane'] in seen or
                    not isinstance(row['action'], str) or row['action'] not in primitive.DECISIONS):
                raise ValueError('Invalid or external-payload CAS disposition.')
            seen.add(row['lane'])
            if row['action'] == 'accept-returned':
                accepted.add(row['lane'])
        targets = primitive._hair_targets(hair_targets, accepted, original, returned, self.known)
        planned = {}
        if self.hair_checkpoint['enabled']:
            held = self.hair_checkpoint['forms']
            policy = {'hair_policy': {'enabled': True, 'forms': copy.deepcopy(held)}}
            for lane in accepted:
                if lane not in held or outfit_hair.capture(self.backend, original[lane]) != held[lane]:
                    raise ValueError('Hair isolation lacks its freshly captured original wardrobe.')
                observed = outfit_hair.capture(self.backend, returned[lane])
                original_index = outfit_hair._held_index(held[lane])
                current_index = outfit_hair._held_index(observed)
                if (set(original_index) != set(current_index) or
                        any(current_index[key]['outfit_id'] != value['outfit_id'] for key, value in original_index.items())):
                    raise ValueError('Hair-isolated outfit was added, removed, replaced, or reordered; explicit wardrobe acceptance is unfinished.')
                target = targets.get(lane)
                if target is None:
                    if any(current_index[key]['hair'] != value['hair'] for key, value in original_index.items()):
                        raise ValueError('Changed hair requires explicit category/ordinal/original-UID intent; propagation is not accepted.')
                    chosen = outfit_hair.reconcile(self.backend, returned[lane], held[lane], preserve=None, lane=lane)
                else:
                    chosen = outfit_hair.accept_cas(self.backend, policy, lane, returned[lane],
                        {'schema': 1, 'lane': lane, 'targets': target})
                if ({name: value for name, value in chosen.items() if name != '__outfits__'} !=
                        {name: value for name, value in returned[lane].items() if name != '__outfits__'}):
                    raise ValueError('Hair planner changed a non-outfit appearance field.')
                appearance.fingerprint(chosen)
                planned[lane] = chosen
        result = super(_HairTransaction, self).prepare(expected_pending_sha256,
                    expected_raw_return_sha256, dispositions, hair_targets=targets)
        if self.hair_checkpoint['enabled']:
            for lane, fields in planned.items():
                self.plan['desired'][lane] = copy.deepcopy(fields)
            self.plan['hair_policy_contract'] = {
                'enabled': True, 'held_source': 'fresh-raw-original-owners',
                'explicit_outfit_intent_required': True, 'automatic_intent_classification': False,
                'native_cas_propagation_verified': False,
                'reconciled_lanes': sorted(planned, key=int)}
            plan_hash = primitive.digest(self.plan)
            document = copy.deepcopy(self.document)
            document.update(plan=copy.deepcopy(self.plan), plan_sha256=plan_hash)
            try:
                self._write(document)
            except Exception as error:
                self._failure(error, 'trusted hair-policy plan journal')
            result['plan_sha256'] = plan_hash
        result['hair_isolation_planned'] = self.hair_checkpoint['enabled']
        result['native_cas_propagation_verified'] = False
        return result


def _cache_key(path, key, token):
    return str(path), key, token


def _instance(backend, sim, allow_primary_recreation=False):
    path, key, record, transaction = _selected(backend, sim)
    cache_key = _cache_key(path, key, transaction['transaction_id'])
    captured = _CAPTURED.get(cache_key)
    identity = _identity(backend, sim)
    if (captured is None or captured['backend'] is not backend or
            captured['identity'] != identity):
        raise ValueError('CAS checkpoint has no exact original native-Sim receiver capability; replay is blocked.')
    instance = _ACTIVE.get(cache_key)
    if instance is not None:
        if captured['sim'] is not sim or instance.backend is not backend or instance.sim is not sim:
            raise ValueError('CAS receiver object differs from the authenticated native owner.')
        return instance
    if transaction.get('journal') is not None or captured.get('receiver_bound') is True:
        raise ValueError('Observed/planned CAS journal has no live receiver; rehydration/replay is blocked.')
    if len(_ACTIVE) >= 256:
        raise ValueError('CAS receiver capacity reached; no original discarded.')
    if captured['sim'] is not sim:
        # Native CAS can replace the primary SimInfo as well as its wrappers.
        # Only the first observe may bind that current manager-owned object to
        # the still-held begin capability. A journal or previously bound
        # receiver cannot be reconstructed, transferred or replayed.
        if (allow_primary_recreation is not True or captured.get('receiver_bound') is not False or
                captured.get('primary_sim_recreated') is not False or
                transaction.get('phase') != 'captured' or
                'primary_receiver_binding' in transaction):
            raise ValueError('CAS primary receiver was replaced outside its initial observation; replay is blocked.')
        diagnostic = {'primary_sim_recreated': True, 'identity': copy.deepcopy(identity),
                      'begin_capability_retained': True, 'manager_owned_verified': True,
                      'bound_before_raw_observation': True, 'native_appearance_written': False}
        token = transaction['transaction_id']
        def bind(data_now, selected, fresh_identity):
            _p, _k, current_record, current_transaction = _selected(backend, sim, token)
            if (selected != current_record or fresh_identity != identity or
                    current_transaction.get('phase') != 'captured' or
                    current_transaction.get('journal') is not None or
                    'primary_receiver_binding' in current_transaction or
                    _CAPTURED.get(cache_key) is not captured or cache_key in _ACTIVE or
                    captured.get('receiver_bound') is not False):
                raise ValueError('Initial CAS receiver binding changed; no capability transferred.')
            selected['cas_transaction']['primary_receiver_binding'] = copy.deepcopy(diagnostic)
        _mutate(backend, sim, bind)
        captured['sim'] = sim
        captured['primary_sim_recreated'] = True
        captured['primary_receiver_binding'] = copy.deepcopy(diagnostic)
    token = transaction['transaction_id']
    def read_pending():
        _p, _k, selected, _transaction = _selected(backend, sim, token)
        return copy.deepcopy(selected['pending'])
    def read_journal():
        _p, _k, _selected_record, selected_transaction = _selected(backend, sim, token, allow_consumed=True)
        return copy.deepcopy(selected_transaction.get('journal'))
    context_receipt = None
    def restore_lane(lane, fields):
        nonlocal context_receipt
        _p, _k, _r, current_transaction = _selected(backend, sim, token)
        context = current_transaction.get('native_occult_context')
        if context is not None and context_receipt is None:
            journal = current_transaction.get('journal')
            if (not isinstance(journal, dict) or journal.get('state') != 'applying' or
                    journal.get('native_write_possible') is not True or journal.get('bank_commit_attempted') is not False):
                raise ValueError('Native availability restore requires durable explicit native-write intent.')
            from .native_occult_context import restore
            context_receipt = restore(backend, sim, context)
            def retain_context(data_now, selected, fresh_identity):
                _path, _key, own_record, own_transaction = _selected(backend, sim, token)
                if (selected != own_record or own_transaction.get('native_occult_restore') is not None or
                        own_transaction.get('native_occult_context') != context or
                        own_transaction['journal'].get('state') != 'applying'):
                    raise ValueError('Native availability restore receipt changed before durable acknowledgment.')
                selected['cas_transaction']['native_occult_restore'] = copy.deepcopy(context_receipt)
            _mutate(backend, sim, retain_context)
        form_bank.restore(backend, sim, lane, fields)
    def verify_context(active_lane):
        _p, _k, _r, current_transaction = _selected(backend, sim, token)
        from .native_occult_context import read, verify, verify_receipt
        context = current_transaction['native_occult_context']
        restored = verify_receipt(context, current_transaction.get('native_occult_restore'), active_lane)
        observed = verify(context, read(backend, sim), active_lane)
        return {'checkpoint_sha256': current_transaction['native_occult_context_sha256'],
                'restore_receipt_sha256': primitive.digest(restored), 'observed': observed, 'verified': True}
    instance = _HairTransaction(backend, sim, read_pending, lambda: _identity(backend, sim),
        read_journal, lambda document, previous: _write_journal(backend, sim, token, document, previous),
        restore_lane,
        lambda receipt: _commit_metadata(backend, sim, token, receipt),
        hair_checkpoint=copy.deepcopy(transaction['hair_checkpoint']),
        native_context_final=verify_context if 'native_occult_context' in transaction else None)
    captured['receiver_bound'] = True
    _ACTIVE[cache_key] = instance
    return instance


def begin(backend, sim, snapshot_reader=None):
    """Persist fresh raw owners first; optional native snapshot is audit only.

    The internal snapshot callback is never accepted through bridge JSON. It
    runs only after durable originals. Its output cannot supply missing lanes
    or replace the raw originals. Default begin avoids native serialization.
    """
    with _LOCK:
        assert_idle(backend, sim)
        identity, path, key, data, file_hash, existing = _context(backend, sim)
        record = copy.deepcopy(existing) if existing is not None else {'bank': {}, 'history': []}
        if (not isinstance(record.get('history', []), list) or
                not isinstance(record.get('cas_transaction_history', []), list)):
            raise ValueError('CAS history must retain its typed index.')
        raw_checkpoint = primitive.checkpoint(backend, sim, lambda: _identity(backend, sim))
        from .native_occult_context import capture
        native_context = capture(backend, sim)
        policy = record.get('hair_policy', {})
        if not isinstance(policy, dict) or type(policy.get('enabled', False)) is not bool:
            raise ValueError('Hair policy is malformed; no checkpoint written.')
        enabled = policy.get('enabled', False)
        hair_checkpoint = {'enabled': enabled, 'forms': {}}
        if enabled:
            hair_checkpoint['forms'] = {lane: outfit_hair.capture(backend, fields)
                for lane, fields in raw_checkpoint['original_owners']['stored'].items()}
            for wardrobe in hair_checkpoint['forms'].values():
                outfit_hair._held_index(wardrobe)
        previous = record.pop('cas_transaction', None)
        if previous is not None:
            record.setdefault('cas_transaction_history', []).append(copy.deepcopy(previous))
        from .bank_history import externalize
        externalize(path, record)
        token = uuid.uuid4().hex
        guard = _record_guard(record)
        checkpoint_hash = primitive.digest(raw_checkpoint)
        envelope = {'transaction_id': token, 'identity': identity,
                    'checkpoint_sha256': checkpoint_hash, 'record_guard_sha256': guard,
                    'hair_checkpoint_sha256': primitive.digest(hair_checkpoint)}
        transaction = {'schema': 1, 'transaction_id': token, 'owner_key': key,
                       'identity': identity, 'checkpoint_sha256': checkpoint_hash,
                       'transaction_sha256': primitive.digest(envelope),
                       'record_guard_sha256': guard, 'hair_checkpoint': hair_checkpoint,
                       'hair_checkpoint_sha256': envelope['hair_checkpoint_sha256'],
                       'prior_bank': copy.deepcopy(record.get('bank', {})),
                       'prior_hair_policy': copy.deepcopy(record.get('hair_policy')),
                       'phase': 'captured', 'journal': None,
                       'full_native_original_appended': False}
        if native_context is not None:
            transaction['native_occult_context'] = native_context
            transaction['native_occult_context_sha256'] = primitive.digest(native_context)
            transaction['transaction_sha256'] = primitive.digest(_native_context_envelope(transaction, envelope))
        record['pending'] = raw_checkpoint
        record['cas_transaction'] = transaction
        if len(_CAPTURED) >= 256:
            raise ValueError('CAS checkpoint receiver capacity reached; no original discarded.')
        def capture(data_now, selected, fresh_identity):
            _current_data, current_hash = _read(path)
            if fresh_identity != identity or selected != existing or current_hash != file_hash:
                raise ValueError('Bank changed while preparing raw CAS originals.')
            data_now['records'][key] = copy.deepcopy(record)
        _mutate(backend, sim, capture)
        # CAS can recreate the primary SimInfo and its stored wrappers. Hold
        # this original capability; only initial observe may bind the exact
        # same-runtime manager-owned return, once, before any raw journal.
        for old_key in list(_CAPTURED):
            if old_key[:2] == (str(path), key):
                _CAPTURED.pop(old_key, None)
                _ACTIVE.pop(old_key, None)
        _CAPTURED[_cache_key(path, key, token)] = {
            'backend': backend, 'sim': sim, 'begin_sim': sim, 'identity': copy.deepcopy(identity),
            'receiver_bound': False, 'primary_sim_recreated': False}
        if snapshot_reader is not None:
            try:
                native = primitive._serialized_append(snapshot_reader(), identity)
                post = primitive.read_owners(backend, sim, lambda: _identity(backend, sim))
                def append(data_now, selected, fresh_identity):
                    _p, _k, own_record, own_transaction = _selected(backend, sim, token)
                    if selected != own_record or fresh_identity != identity:
                        raise ValueError('CAS checkpoint changed before native audit append.')
                    selected['cas_transaction'].update(full_native_original_appended=True,
                        native_original_append=copy.deepcopy(native),
                        post_original_serializer_owners=post,
                        original_serializer_appearance_side_effects=(primitive.digest(post) != primitive.digest(raw_checkpoint['original_owners'])))
                _mutate(backend, sim, append)
            except Exception as error:
                instance = _instance(backend, sim)
                instance._failure(error, 'original serializer audit append')
        return {'ok': True, 'expected_pending_sha256': transaction['transaction_sha256'],
                'checkpoint_sha256': checkpoint_hash, 'lane': raw_checkpoint['lane'],
                'native_owner_lanes': sorted(raw_checkpoint['original_owners']['stored'], key=int),
                'hair_policy_enabled': enabled, 'full_native_original_appended': snapshot_reader is not None,
                'native_appearance_written': False, 'old_bank_restored': False}


def _argument(backend, sim, argument, required, optional=()):
    if (not isinstance(argument, dict) or not set(required).issubset(argument) or
            set(argument) - set(required) - set(optional) or
            not primitive._hash(argument.get('expected_pending_sha256'))):
        raise ValueError('CAS receiver requires exact hashes and typed intent; external fields are forbidden.')
    _path, _key, _record, transaction = _selected(backend, sim, allow_consumed=True)
    if transaction['transaction_sha256'] != argument['expected_pending_sha256']:
        raise ValueError('CAS request belongs to a stale/different transaction epoch.')
    return transaction


def _change_evidence(transaction):
    """Bounded hashes/names for explicit review, never appearance values.

    An unavailable observation is distinct from a verified empty change list.
    This evidence describes receiver-captured owners; it grants no edit intent.
    """
    unavailable = {'lane_change_evidence_available': False, 'changed_lanes': None,
                   'lane_change_evidence': [], 'evidence_establishes_edit_intent': False}
    try:
        if not isinstance(transaction, dict) or not isinstance(transaction.get('journal'), dict):
            return unavailable
        journal, identity = transaction['journal'], transaction.get('identity')
        original, returned = journal.get('original_owners'), journal.get('raw_return')
        if (not isinstance(identity, dict) or journal.get('identity') != identity or
                not isinstance(original, dict) or original.get('identity') != identity or
                not isinstance(returned, dict) or returned.get('identity') != identity or
                not isinstance(original.get('stored'), dict) or not original['stored'] or
                len(original['stored']) > 32 or not isinstance(returned.get('stored'), dict) or
                set(original['stored']) != set(returned['stored']) or
                primitive.digest(returned) != journal.get('raw_return_sha256')):
            return unavailable
        checkpoint = {'schema': 2, 'state': 'captured', 'runtime_pid': identity['runtime_pid'],
                      'lane': original['active']['lane'], 'identity': identity, 'original_owners': original}
        if primitive.digest(checkpoint) != transaction.get('checkpoint_sha256'):
            return unavailable
        rows, changed = [], []
        for lane in sorted(original['stored'], key=int):
            if (not isinstance(lane, str) or not lane.isascii() or not lane.isdecimal() or
                    str(int(lane)) != lane or not 0 < int(lane) < 1 << 32 or int(lane) & (int(lane) - 1)):
                return unavailable
            before = appearance.fingerprint(original['stored'][lane])
            after = appearance.fingerprint(returned['stored'][lane])
            fields = sorted(name for name in set(before['field_sha256']) | set(after['field_sha256'])
                            if before['field_sha256'].get(name) != after['field_sha256'].get(name))
            changed_row = before['appearance_sha256'] != after['appearance_sha256']
            if changed_row:
                changed.append(lane)
            rows.append({'lane': lane, 'changed': changed_row, 'changed_fields': fields,
                         'changed_field_labels': [name.strip('_').replace('_', ' ') for name in fields],
                         'before_fingerprint': before, 'returned_fingerprint': after})
        return {'lane_change_evidence_available': True, 'changed_lanes': changed,
                'lane_change_evidence': rows, 'evidence_establishes_edit_intent': False,
                'original_active_lane': original['active']['lane'],
                'returned_active_lane': returned['active']['lane']}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return unavailable


def observe(backend, sim, argument):
    """Persist all raw returned owners before a complete native Sim serializer."""
    with _LOCK:
        transaction = _argument(backend, sim, argument, {'expected_pending_sha256'})
        instance = _instance(backend, sim, allow_primary_recreation=True)
        result = instance.observe_return(snapshot_reader=lambda: sim_data.snapshot(backend, sim))
        result['checkpoint_sha256'] = result.pop('pending_sha256')
        result['expected_pending_sha256'] = transaction['transaction_sha256']
        _path, _key, _record, observed = _selected(backend, sim, allow_consumed=True)
        result['primary_sim_recreated'] = isinstance(observed.get('primary_receiver_binding'), dict)
        result.update(_change_evidence(observed))
        return result


def prepare(backend, sim, argument):
    with _LOCK:
        transaction = _argument(backend, sim, argument,
            {'expected_pending_sha256', 'expected_raw_return_sha256', 'dispositions'}, {'hair_targets'})
        if not primitive._hash(argument['expected_raw_return_sha256']):
            raise ValueError('CAS returned-owner hash must be exact.')
        instance = _instance(backend, sim)
        result = instance.prepare(transaction['checkpoint_sha256'],
            argument['expected_raw_return_sha256'], argument['dispositions'], argument.get('hair_targets'))
        result['expected_pending_sha256'] = transaction['transaction_sha256']
        return result


def commit(backend, sim, argument):
    with _LOCK:
        transaction = _argument(backend, sim, argument,
            {'expected_pending_sha256', 'expected_plan_sha256'})
        if not primitive._hash(argument['expected_plan_sha256']):
            raise ValueError('CAS plan hash must be exact.')
        if _completed(transaction):
            if transaction['journal']['plan_sha256'] != argument['expected_plan_sha256']:
                raise ValueError('Completed CAS plan differs; no replay allowed.')
            return {'ok': True, 'already_completed': True, 'replayed': False,
                    'receipt_historical': True, 'bank_committed': True,
                    'plan_sha256': argument['expected_plan_sha256'],
                    'expected_pending_sha256': transaction['transaction_sha256'],
                    'save_reload_verified': False}
        instance = _instance(backend, sim)
        result = instance.commit(argument['expected_plan_sha256'])
        result.update(expected_pending_sha256=transaction['transaction_sha256'], replayed=False)
        return result


def status(backend, sim):
    """Read small transaction evidence; never export private appearance bytes."""
    with _LOCK:
        _thread(backend)
        _identity_row, path, key, _data, _file_hash, record = _context(backend, sim, fresh=False)
        transaction = record.get('cas_transaction') if record else None
        pending = record.get('pending') if record else None
        lease_present = _lease_path(path).exists()
        result = {'ok': True, 'blocked': _blocked(record, key) or lease_present,
                  'writer_lease_present': lease_present,
                  'all_bank_writers_must_use_shared_protocol': True,
                  'uncooperating_external_writer_atomic_cas_supported': False,
                  'legacy_pending_not_converted': pending is not None and
                    (not isinstance(pending, dict) or pending.get('schema') != 2),
                  'save_reload_verified': False, 'membership_or_traits_modified': False,
                  'native_availability_restore_requires_fresh_checkpoint': True,
                  'automatic_intent_classification_supported': False,
                  'hair_isolation_requires_explicit_targets': True,
                  'added_removed_reordered_hair_wardrobe_acceptance_supported': False}
        if isinstance(transaction, dict):
            journal = transaction.get('journal')
            journal = journal if isinstance(journal, dict) else {}
            identity = transaction.get('identity')
            identity = identity if isinstance(identity, dict) else {}
            hair_checkpoint = transaction.get('hair_checkpoint')
            hair_checkpoint = hair_checkpoint if isinstance(hair_checkpoint, dict) else {}
            result.update(phase=journal.get('state', transaction.get('phase')),
                expected_pending_sha256=transaction.get('transaction_sha256'),
                checkpoint_sha256=transaction.get('checkpoint_sha256'),
                raw_return_sha256=journal.get('raw_return_sha256'), plan_sha256=journal.get('plan_sha256'),
                current_runtime=(identity.get('runtime_pid') == os.getpid()),
                hair_policy_enabled=hair_checkpoint.get('enabled'),
                completed_receipt=_completed(transaction),
                metadata_commit_persisted=isinstance(transaction.get('metadata_commit'), dict) and
                    transaction['metadata_commit'].get('committed') is True,
                native_write_possible=journal.get('native_write_possible', False),
                native_write_attempted=journal.get('native_write_attempted', False),
                bank_commit_outcome=journal.get('bank_commit_outcome'))
            result.update(native_availability_captured='native_occult_context' in transaction,
                          native_availability_restore_verified=isinstance(transaction.get('native_occult_restore'), dict) and
                            transaction['native_occult_restore'].get('verified') is True)
        result.update(_change_evidence(transaction))
        return result


def dispatch(backend, sim, action, value=None):
    """Passive typed bridge adapter; registers no hook or route by itself."""
    if action not in ACTION_NAMES:
        raise ValueError('Unknown typed CAS bank action.')
    if action in ('cas_bank_begin', 'cas_bank_status'):
        if value not in (None, ''):
            raise ValueError('CAS begin/status accepts no external payload or callback.')
        return begin(backend, sim) if action == 'cas_bank_begin' else status(backend, sim)
    if not isinstance(value, str) or len(value.encode('utf-8')) > 1024 * 1024:
        raise ValueError('CAS bridge intent must be bounded JSON text.')
    def reject_constant(value):
        raise ValueError('CAS bridge JSON cannot contain nonfinite numbers.')
    argument = json.loads(value, object_pairs_hook=_pairs, parse_constant=reject_constant)
    functions = {'cas_bank_observe': observe, 'cas_bank_prepare': prepare, 'cas_bank_commit': commit}
    return functions[action](backend, sim, argument)
