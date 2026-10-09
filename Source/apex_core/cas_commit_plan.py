"""Unwired, fail-closed CAS commit primitives for several appearance owners.

Only receiver-read appearances can become a plan. A caller supplies hashes and
explicit lane decisions, never replacement appearance bytes. Native navigation
receipts do not classify a changed lane as an intentional edit.

The embedding code must provide trusted fresh identity/checkpoint readers,
durable compare-and-swap journal storage, a native appearance-only lane writer,
and an atomic metadata-only bank/hair-policy commit. This module deliberately
does not register game hooks, rewrite membership/traits, generate absent forms,
recover a previous process, or automatically replay an interrupted transaction.
It is not wired into form_bank.finish yet.
"""
import copy
import base64
import hashlib
import json
import os

from . import form_appearance as appearance
from . import outfit_snapshot


MAX_DOCUMENT_BYTES = 48 * 1024 * 1024
IDENTITY_FIELDS = {'runtime_pid', 'save_guid', 'household_id', 'sim_id'}
DECISIONS = {'accept-returned', 'restore-original'}


def _json(value):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=True,
                         allow_nan=False, separators=(',', ':')).encode('ascii')
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError('CAS record must contain bounded JSON values: ' + str(error))
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError('CAS record exceeds its preservation bound.')
    return raw


def digest(value):
    """Hash complete typed fields, including the original unnormalized bytes."""
    return hashlib.sha256(_json(value)).hexdigest()


def _hash(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(character in '0123456789abcdef' for character in value))


def _id(value):
    return (isinstance(value, str) and value.isascii() and value.isdecimal() and
            len(value) <= 20 and
            0 < int(value) < 1 << 64 and str(int(value)) == value)


def _identity(value):
    if (not isinstance(value, dict) or set(value) != IDENTITY_FIELDS or
            type(value['runtime_pid']) is not int or value['runtime_pid'] != os.getpid() or
            not all(_id(value[name]) for name in ('save_guid', 'household_id', 'sim_id'))):
        raise ValueError('CAS identity requires this runtime and exact Sim/household/save IDs.')
    return copy.deepcopy(value)


def _lane(value, known):
    if type(value) is int:
        value = str(value)
    if (not isinstance(value, str) or not value.isascii() or not value.isdecimal() or
            str(int(value)) != value or int(value) not in known):
        raise ValueError('CAS owner is unknown or is not one exact occult lane.')
    return value


def _known(backend):
    result = {1}
    for value in backend._all_occults():
        value = int(value)
        if value <= 1 or value >= 1 << 32 or value & (value - 1):
            raise ValueError('Native occult enumeration is not one-lane ownership.')
        result.add(value)
    return result


def _forms(backend, sim, known):
    result, owners = {}, set()
    for lane, owner in backend._form_map(sim.occult_tracker).items():
        lane = _lane(lane if isinstance(lane, str) else int(lane), known)
        if lane in result or owner is None or id(owner) in owners:
            raise ValueError('Native CAS owners are missing, duplicate, or aliased.')
        result[lane] = owner
        owners.add(id(owner))
    if not result:
        raise ValueError('Native CAS owner map is empty.')
    return result


def _rejected_owners(backend, sim, identity_reader, error):
    """Retain readable rows from an invalid map as diagnostics, never a plan."""
    identity = _identity(identity_reader())
    rows = []
    for lane, owner in backend._form_map(sim.occult_tracker).items():
        if len(rows) >= 128:
            raise ValueError('Rejected CAS owner map exceeds its diagnostic bound.')
        try:
            label = lane if isinstance(lane, str) else str(int(lane))
            if not isinstance(label, str) or len(label) > 32:
                raise ValueError('unbounded lane label')
        except (TypeError, ValueError):
            label = 'unsupported-native-lane-type'
        row = {'native_lane': label, 'native_lane_type': type(lane).__name__}
        try:
            row['fields'] = appearance.packed(backend, owner)
        except Exception as capture_error:
            row['capture_error'] = str(capture_error)
        rows.append(row)
    active = {'fields': appearance.packed(backend, sim),
              'native_lane': str(int(backend._get_current_flags(sim)))}
    result = {'identity': identity, 'stored_rows': rows, 'active': active,
              'validation_error': str(error), 'usable_as_plan': False,
              'identity_still_matches': _identity(identity_reader()) == identity}
    _json(result)
    return result


def _serialized_append(value, identity):
    required = {'schema', 'native_message_type', 'native_sha256', 'native_bytes',
                'native_base64', 'data', 'field_schemas',
                'unknown_fields_retained_in_native_bytes', 'sim_id', 'save_guid',
                'native_serializer_called', 'save_file_written'}
    if (not isinstance(value, dict) or not required.issubset(value) or
            type(value['schema']) is not int or value['schema'] != 1 or
            not isinstance(value['native_message_type'], str) or not 0 < len(value['native_message_type']) <= 512 or
            type(value['native_bytes']) is not int or not 0 < value['native_bytes'] <= 4 * 1024 * 1024 or
            not _hash(value['native_sha256']) or not isinstance(value['native_base64'], str) or
            len(value['native_base64']) > 6 * 1024 * 1024 or
            value['sim_id'] != identity['sim_id'] or value['save_guid'] != identity['save_guid'] or
            value['unknown_fields_retained_in_native_bytes'] is not True or
            value['native_serializer_called'] is not True or value['save_file_written'] is not False or
            not isinstance(value['data'], dict) or not isinstance(value['field_schemas'], dict)):
        raise ValueError('Complete native serializer append has invalid identity, bytes, or catalog metadata.')
    raw = base64.b64decode(value['native_base64'], validate=True)
    if (len(raw) != value['native_bytes'] or hashlib.sha256(raw).hexdigest() != value['native_sha256'] or
            base64.b64encode(raw).decode('ascii') != value['native_base64'] or
            value['data'].get('message_type') != value['native_message_type'] or
            not isinstance(value['data'].get('fields'), list) or
            not isinstance(value['field_schemas'].get(value['native_message_type']), list)):
        raise ValueError('Complete native serializer append failed exact byte/catalog readback.')
    _json(value)
    return copy.deepcopy(value)


def _consistent(raw):
    lane = raw['active']['lane']
    if lane not in raw['stored']:
        raise ValueError('Active CAS lane has no stored native owner.')
    if (appearance.fingerprint(raw['active']['fields'])['appearance_sha256'] !=
            appearance.fingerprint(raw['stored'][lane])['appearance_sha256']):
        raise ValueError('Active and stored CAS appearances disagree; no destination guessed.')


def _validate_raw(raw, known):
    if (not isinstance(raw, dict) or set(raw) != {'identity', 'stored', 'active'} or
            not isinstance(raw['stored'], dict) or not raw['stored'] or
            not isinstance(raw['active'], dict) or set(raw['active']) != {'lane', 'fields'}):
        raise ValueError('Separate raw stored and active CAS owners are required.')
    _identity(raw['identity'])
    seen = set()
    for lane, fields in raw['stored'].items():
        canonical = _lane(lane, known)
        if not isinstance(lane, str) or canonical in seen:
            raise ValueError('Checkpoint CAS lanes must have unique canonical keys.')
        seen.add(canonical)
        appearance.fingerprint(fields)
    _lane(raw['active']['lane'], known)
    appearance.fingerprint(raw['active']['fields'])
    _json(raw)


def read_owners(backend, sim, identity_reader):
    """Read raw wrappers separately, without calling Sim.save or snapshot.

    Known readable appearance fields and *all* outfit/protobuf bytes are kept.
    Additional native Sim fields require the separate complete serializer
    append; that serializer is intentionally never called by this function.
    """
    identity = _identity(identity_reader())
    if identity['sim_id'] != str(sim.id):
        raise ValueError('Selected native Sim differs from the authenticated identity.')
    resolver = getattr(backend, '_get_sim_info_by_id', None)
    if resolver is not None and resolver(sim.id) is not sim:
        raise ValueError('Selected native Sim is not the current manager-owned object.')
    known = _known(backend)
    owners = _forms(backend, sim, known)
    lane = _lane(int(backend._get_current_flags(sim)), known)
    raw = {'identity': identity,
           'stored': {name: appearance.packed(backend, owner) for name, owner in owners.items()},
           'active': {'lane': lane, 'fields': appearance.packed(backend, sim)}}
    if (_identity(identity_reader()) != identity or
            _lane(int(backend._get_current_flags(sim)), known) != lane or
            any(_forms(backend, sim, known).get(name) is not owner for name, owner in owners.items()) or
            set(_forms(backend, sim, known)) != set(owners)):
        raise ValueError('Native ownership changed during the raw CAS read.')
    _validate_raw(raw, known)
    return raw


def checkpoint(backend, sim, identity_reader):
    """Create a new-process raw checkpoint for the embedding durable writer.

    A legacy checkpoint with an active-overwritten owner map is insufficient
    evidence and cannot be upgraded by copying those bytes into this schema.
    """
    raw = read_owners(backend, sim, identity_reader)
    _consistent(raw)
    return {'schema': 2, 'state': 'captured', 'runtime_pid': os.getpid(),
            'lane': raw['active']['lane'], 'identity': copy.deepcopy(raw['identity']),
            'original_owners': raw}


def _outfits(fields):
    """Index current OutfitData field 1 UID and field 2 category without edits."""
    raw = appearance.decode(fields['__outfits__'])
    if not isinstance(raw, tuple) or raw[0] != 'protobuf':
        raise ValueError('CAS hair targets need the complete native outfit message.')
    raw = raw[1]
    outfit_snapshot.normalize(raw)  # Bounds and every unknown child field.
    offset, counts, result, uids = 0, {}, {}, set()
    while offset < len(raw):
        number, kind, offset, value = outfit_snapshot.field(raw, offset)
        if number != 1:
            continue
        if kind != 2:
            raise ValueError('Unknown native outfit-list entry.')
        child_offset, uid, category = 0, None, None
        while child_offset < len(value):
            child_number, child_kind, child_offset, child_value = outfit_snapshot.field(value, child_offset)
            if child_number in (1, 2):
                if child_kind != 0 or (child_number == 1 and uid is not None) or (child_number == 2 and category is not None):
                    raise ValueError('Duplicate or unknown native outfit UID/category fields.')
                if child_number == 1:
                    uid = str(child_value)
                else:
                    category = child_value
        if not _id(uid) or uid in uids or type(category) is not int or not 0 <= category < 1 << 32:
            raise ValueError('Hair ownership needs unique native outfit UIDs and categories.')
        ordinal = counts.get(category, 0)
        counts[category] = ordinal + 1
        result[(category, ordinal)] = uid
        uids.add(uid)
    return result


def _hair_targets(value, accepted, originals, returned, known):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > len(accepted):
        raise ValueError('Hair intent must be a typed set bound to accepted CAS lanes.')
    result = {}
    for lane, targets in value.items():
        _lane(lane, known)
        if not isinstance(lane, str) or lane not in accepted:
            raise ValueError('Hair intent cannot authorize an unaccepted CAS lane.')
        if not isinstance(targets, list) or not 0 < len(targets) <= 1024:
            raise ValueError('Hair intent requires a bounded nonempty outfit target list.')
        original_index, returned_index = _outfits(originals[lane]), _outfits(returned[lane])
        seen = set()
        for target in targets:
            if not isinstance(target, dict) or set(target) != {'category', 'ordinal', 'outfit_id'}:
                raise ValueError('Hair intent contains external bytes or lacks an exact outfit identity.')
            category, ordinal = target['category'], target['ordinal']
            if (type(category) is not int or not 0 <= category < 1 << 32 or
                    type(ordinal) is not int or not 0 <= ordinal < 1024 or not _id(target['outfit_id'])):
                raise ValueError('Invalid typed hair intent identity.')
            key = (category, ordinal)
            if (key in seen or original_index.get(key) != target['outfit_id'] or
                    returned_index.get(key) != target['outfit_id']):
                raise ValueError('Hair target is duplicate, replaced, reordered, or no longer present.')
            seen.add(key)
        result[lane] = copy.deepcopy(targets)
    return result


class RecoveryRequired(ValueError):
    """A failed transaction is retained and cannot be replayed by this instance."""


class CasCommitTransaction:
    """One receiver-owned CAS return; no arbitrary plan deserialization.

    journal_writer(document, expected_previous_sha256) must atomically compare
    its existing record to that exact hash (None means no existing record),
    durably fsync/replace, and return {'durable': True,
    'sha256': digest(document)}. journal_reader()
    must return that exact document. A callback returning an ACK before durable
    storage does not meet this contract.

    restore_lane(lane, typed_fields) must touch only existing appearance owners.
    commit_bank(receipt) must atomically compare the exact pending hash, update
    all desired bank lanes and enabled hair policy from those same fields, and
    consume pending once; it must perform no native serializer or appearance
    write. Its ACK is {'committed': True, 'plan_sha256': receipt['plan_sha256']}.
    Native membership, traits and future unreadable fields are outside this
    primitive's authority. Every pending/recovery state blocks further writes.
    """

    def __init__(self, backend, sim, pending_reader, identity_reader,
                 journal_reader, journal_writer, restore_lane, commit_bank):
        self.backend, self.sim = backend, sim
        self.pending_reader, self.identity_reader = pending_reader, identity_reader
        self.journal_reader, self.journal_writer = journal_reader, journal_writer
        self.restore_lane, self.commit_bank = restore_lane, commit_bank
        self.known = _known(backend)
        self.pending = copy.deepcopy(pending_reader())
        if (not isinstance(self.pending, dict) or self.pending.get('schema') != 2 or
                self.pending.get('state') != 'captured' or
                type(self.pending.get('runtime_pid')) is not int or self.pending['runtime_pid'] != os.getpid() or
                set(self.pending) != {'schema', 'state', 'runtime_pid', 'lane', 'identity', 'original_owners'}):
            raise ValueError('An exact durable schema-2 raw CAS checkpoint is required.')
        _validate_raw(self.pending['original_owners'], self.known)
        _consistent(self.pending['original_owners'])
        self.identity = _identity(self.pending['identity'])
        if (self.pending['original_owners']['identity'] != self.identity or
                self.pending['lane'] != self.pending['original_owners']['active']['lane'] or
                _identity(identity_reader()) != self.identity):
            raise ValueError('Raw CAS checkpoint identity differs from this runtime.')
        self.pending_sha256 = digest(self.pending)
        try:
            self.owner_refs = _forms(backend, sim, self.known)
        except (TypeError, ValueError):
            # Invalid returned owner maps still need a diagnostic raw journal.
            # They can never produce a desired plan or native write.
            self.owner_refs = None
        self.tracker = sim.occult_tracker
        if journal_reader() is not None:
            raise ValueError('An existing CAS journal requires inspection; automatic replay is blocked.')
        self.state, self.document, self.journal_sha256 = 'new', None, None
        self.retained_document = None
        self.plan, self.raw_return_sha256 = None, None
        self.native_write_attempted, self.bank_committed = False, False
        self.bank_commit_attempted = False
        self.recovery_recorded = False

    def _guard(self, check_owners=True):
        if digest(self.pending) != self.pending_sha256 or digest(self.pending_reader()) != self.pending_sha256:
            raise ValueError('CAS pending checkpoint changed; the prior state was retained.')
        if _identity(self.identity_reader()) != self.identity or self.sim.occult_tracker is not self.tracker:
            raise ValueError('CAS runtime ownership changed; no native write allowed.')
        resolver = getattr(self.backend, '_get_sim_info_by_id', None)
        if resolver is not None and resolver(self.sim.id) is not self.sim:
            raise ValueError('Selected native Sim is not the current manager-owned object.')
        if check_owners:
            current = _forms(self.backend, self.sim, self.known)
            if (self.owner_refs is None or set(current) != set(self.owner_refs) or
                    any(current[lane] is not owner for lane, owner in self.owner_refs.items())):
                raise ValueError('A stored CAS owner was replaced, missing, or added.')
        if self.journal_sha256 is not None:
            persisted = self.journal_reader()
            if (persisted is None or digest(persisted) != self.journal_sha256 or
                    self.document is None or digest(self.document) != self.journal_sha256):
                raise ValueError('Durable CAS journal changed; automatic replay is blocked.')

    def _write(self, document):
        self.retained_document = copy.deepcopy(document)
        receipt = self.journal_writer(copy.deepcopy(document), self.journal_sha256)
        expected = digest(document)
        if (not isinstance(receipt, dict) or set(receipt) != {'durable', 'sha256'} or
                receipt.get('durable') is not True or receipt.get('sha256') != expected):
            raise ValueError('CAS write-ahead journal was not durably acknowledged.')
        persisted = self.journal_reader()
        if persisted is None or digest(persisted) != expected:
            raise ValueError('CAS journal durable readback differs from its acknowledgment.')
        self.document, self.journal_sha256 = copy.deepcopy(document), expected

    def _failure(self, error, phase):
        self.state = 'recovery-required'
        document = copy.deepcopy(self.retained_document) if self.retained_document is not None else {
            'schema': 1, 'identity': self.identity, 'pending_sha256': self.pending_sha256,
            'original_owners': self.pending['original_owners']}
        # A writer can persist our exact document and then lose its ACK. Only
        # that byte-exact self-owned record permits the recovery CAS to advance;
        # an unrelated/tampered record is never overwritten during recovery.
        try:
            persisted = self.journal_reader()
            if self.retained_document is not None and persisted is not None and digest(persisted) == digest(self.retained_document):
                self.journal_sha256 = digest(persisted)
        except Exception:
            pass
        document.update(state='recovery-required', failed_phase=phase, error=str(error),
                        native_write_attempted=self.native_write_attempted,
                        bank_commit_attempted=self.bank_commit_attempted,
                        bank_committed=(self.bank_committed if self.bank_committed or not self.bank_commit_attempted else None),
                        bank_commit_acknowledged=self.bank_committed,
                        bank_commit_outcome=('acknowledged' if self.bank_committed else
                                             'unresolved' if self.bank_commit_attempted else 'not-attempted'),
                        automatic_replay_allowed=False)
        try:
            self._write(document)
            self.recovery_recorded = True
        except Exception:
            self.recovery_recorded = False
        raise RecoveryRequired('CAS ' + phase + ' failed; originals and returned state require inspection: ' + str(error))

    def observe_return(self, snapshot_reader=None):
        """Durably retain every raw owner BEFORE optional complete serialization.

        snapshot_reader is trusted native serialization code and may mutate
        hidden outfit buffers. Its output is appended separately; the pre-call
        raw return remains the sole appearance-choice source. Any serializer
        failure retains the raw return and blocks planning/replay.
        """
        if self.state != 'new':
            raise ValueError('This CAS return was already observed or interrupted.')
        self._guard(check_owners=False)
        try:
            raw = read_owners(self.backend, self.sim, self.identity_reader)
        except Exception as error:
            rejected = _rejected_owners(self.backend, self.sim, self.identity_reader, error)
            document = {'schema': 1, 'state': 'raw-observation-rejected',
                        'identity': self.identity, 'pending_sha256': self.pending_sha256,
                        'original_owners': copy.deepcopy(self.pending['original_owners']),
                        'rejected_owner_observation': rejected,
                        'native_write_attempted': False, 'bank_committed': False,
                        'automatic_replay_allowed': False}
            self.retained_document = copy.deepcopy(document)
            try:
                self._write(document)
            except Exception as journal_error:
                self._failure(journal_error, 'rejected raw-owner journal')
            self._failure(error, 'raw owner validation')
        self.raw_return_sha256 = digest(raw)
        document = {'schema': 1, 'state': 'raw-observed', 'identity': self.identity,
                    'pending_sha256': self.pending_sha256,
                    'original_owners': copy.deepcopy(self.pending['original_owners']),
                    'raw_return': raw, 'raw_return_sha256': self.raw_return_sha256,
                    'native_write_attempted': False, 'bank_committed': False,
                    'automatic_replay_allowed': False}
        try:
            self._write(document)
            self._guard()
            if set(raw['stored']) != set(self.pending['original_owners']['stored']):
                raise ValueError('The returned CAS owner set differs; no missing form generated.')
            if snapshot_reader is not None:
                serialized = _serialized_append(snapshot_reader(), self.identity)
                document['native_serialized_append'] = copy.deepcopy(serialized)
                document['native_serialized_sha256'] = digest(serialized)
                document['serializer_scope'] = 'Complete serializer append; not a replacement for pre-serializer raw appearance evidence.'
            current = read_owners(self.backend, self.sim, self.identity_reader)
            self._guard()
            document.update(state='observed', pre_write_owners=current,
                            pre_write_owners_sha256=digest(current),
                            complete_serializer_appended=snapshot_reader is not None)
            self._write(document)
            self.state = 'observed'
        except Exception as error:
            self._failure(error, 'raw observation or serializer append')
        return {'ok': True, 'pending_sha256': self.pending_sha256,
                'raw_return_sha256': self.raw_return_sha256,
                'journal_sha256': self.journal_sha256,
                'complete_serializer_appended': snapshot_reader is not None,
                'native_write_attempted': False}

    def prepare(self, expected_pending_sha256, expected_raw_return_sha256,
                dispositions, hair_targets=None):
        """Bind all changed owners to explicit decisions without native writes.

        Hair targets record independently supplied intent; this primitive does
        not infer propagation or transform the returned hair message. The
        embedding policy planner must implement any separate hair isolation.
        """
        if self.state != 'observed':
            raise ValueError('Only one complete observed CAS return can be planned.')
        self._guard()
        if (not _hash(expected_pending_sha256) or expected_pending_sha256 != self.pending_sha256 or
                not _hash(expected_raw_return_sha256) or expected_raw_return_sha256 != self.raw_return_sha256):
            raise ValueError('CAS plan hashes are stale or belong to another return.')
        raw, original = self.document['raw_return'], self.pending['original_owners']
        _consistent(raw)
        original_fields, returned_fields = original['stored'], raw['stored']
        changed = {lane for lane in original_fields if
                   appearance.fingerprint(original_fields[lane])['appearance_sha256'] !=
                   appearance.fingerprint(returned_fields[lane])['appearance_sha256']}
        if not isinstance(dispositions, list) or len(dispositions) != len(changed):
            raise ValueError('Every changed CAS lane requires one explicit disposition.')
        selected = {}
        for row in dispositions:
            if not isinstance(row, dict) or set(row) != {'lane', 'action'}:
                raise ValueError('CAS dispositions cannot contain external appearance bytes or navigation receipts.')
            lane = _lane(row['lane'], self.known)
            if (not isinstance(row['lane'], str) or lane not in changed or lane in selected or
                    not isinstance(row['action'], str) or row['action'] not in DECISIONS):
                raise ValueError('CAS disposition is duplicate, unchanged, unknown, or unsupported.')
            selected[lane] = row['action']
        if set(selected) != changed:
            raise ValueError('A changed CAS lane lacks explicit intent; no destination guessed.')
        accepted = {lane for lane, action in selected.items() if action == 'accept-returned'}
        desired = copy.deepcopy(original_fields)
        for lane in accepted:
            desired[lane] = copy.deepcopy(returned_fields[lane])
        targets = _hair_targets(hair_targets, accepted, original_fields, returned_fields, self.known)
        self.plan = {'schema': 1, 'identity': self.identity, 'pending_sha256': self.pending_sha256,
                     'raw_return_sha256': self.raw_return_sha256,
                     'pre_write_owners_sha256': self.document['pre_write_owners_sha256'],
                     'active_lane': raw['active']['lane'],
                     'dispositions': [{'lane': lane, 'action': selected[lane]} for lane in sorted(selected, key=int)],
                     'changed_lanes': sorted(changed, key=int), 'accepted_lanes': sorted(accepted, key=int),
                     'desired': desired, 'hair_targets': targets,
                     'automatic_intent_classification': False}
        plan_hash = digest(self.plan)
        document = copy.deepcopy(self.document)
        document.update(state='planned', plan=copy.deepcopy(self.plan), plan_sha256=plan_hash)
        try:
            self._write(document)
        except Exception as error:
            self._failure(error, 'plan journal')
        self.state = 'planned'
        return {'ok': True, 'plan_sha256': plan_hash,
                'changed_lanes': self.plan['changed_lanes'], 'accepted_lanes': self.plan['accepted_lanes'],
                'native_write_attempted': False, 'all_changed_lanes_have_explicit_intent': True}

    def _verify_desired(self):
        self._guard()
        observed = read_owners(self.backend, self.sim, self.identity_reader)
        if observed['active']['lane'] != self.plan['active_lane'] or set(observed['stored']) != set(self.plan['desired']):
            raise ValueError('Final CAS active lane or native owner set differs from the plan.')
        verified = {}
        for lane, desired in self.plan['desired'].items():
            expected = appearance.fingerprint(desired)['appearance_sha256']
            actual = appearance.fingerprint(observed['stored'][lane])['appearance_sha256']
            if expected != actual:
                raise ValueError('Final stored CAS appearance differs in lane ' + lane + '.')
            verified[lane] = actual
        active_hash = appearance.fingerprint(observed['active']['fields'])['appearance_sha256']
        if active_hash != verified[self.plan['active_lane']]:
            raise ValueError('Final active CAS appearance differs from its separately read stored owner.')
        return {'stored': verified, 'active_lane': self.plan['active_lane'],
                'active_appearance_sha256': active_hash, 'verified': True,
                'raw_final_owners_sha256': digest(observed)}

    def commit(self, expected_plan_sha256):
        """Journal first, restore all planned lanes, then verify and commit bank.

        Any failure after the write-ahead boundary is recovery-required. No
        original/returned bytes are discarded and this instance cannot retry.
        Completing this operation is appearance readback, not save/reload proof.
        """
        if self.state != 'planned':
            raise ValueError('CAS plan is unavailable, completed, or recovery-required; replay refused.')
        self._guard()
        if (not _hash(expected_plan_sha256) or digest(self.plan) != expected_plan_sha256 or
                self.document.get('plan_sha256') != expected_plan_sha256 or
                digest(self.document.get('plan')) != expected_plan_sha256):
            raise ValueError('CAS plan hash differs; no native write allowed.')
        current = read_owners(self.backend, self.sim, self.identity_reader)
        if digest(current) != self.plan['pre_write_owners_sha256']:
            raise ValueError('Native CAS return changed after observation; no native write allowed.')
        # Post-serializer ambiguity is not edit intent either. A serializer may
        # have changed both owners identically; raw desired fields still win.
        _consistent(current)
        document = copy.deepcopy(self.document)
        # A process can end inside a native setter before writing another ACK.
        # Durable intent therefore means a write is POSSIBLE, never falsely
        # proves that none happened. Same-process recovery can record its known
        # attempt flag; another process must retain the uncertainty/no replay.
        document.update(state='applying', native_write_attempted=None,
                        native_write_possible=True, bank_committed=False,
                        bank_commit_attempted=False, automatic_replay_allowed=False)
        try:
            self._write(document)  # Full originals/raw/desired must be durable.
            self.state = 'applying'
            self._guard()
            for lane in sorted(self.plan['desired'], key=int):
                self.native_write_attempted = True
                self.restore_lane(lane, copy.deepcopy(self.plan['desired'][lane]))
            final = self._verify_desired()
            document.update(state='verified', native_write_attempted=self.native_write_attempted,
                            final_native_appearance=final, bank_commit_possible=True,
                            bank_commit_attempted=None)
            self._write(document)
            self._guard()
            if self._verify_desired() != final:
                raise ValueError('Native CAS appearance changed before the metadata commit.')
            bank_receipt = {'plan_sha256': expected_plan_sha256,
                            'pending_sha256': self.pending_sha256, 'identity': self.identity,
                            'bank': copy.deepcopy(self.plan['desired']),
                            'active_lane': self.plan['active_lane'],
                            'hair_targets': copy.deepcopy(self.plan['hair_targets']),
                            'final_native_appearance': copy.deepcopy(final)}
            self.bank_commit_attempted = True
            acknowledgment = self.commit_bank(copy.deepcopy(bank_receipt))
            if (not isinstance(acknowledgment, dict) or set(acknowledgment) != {'committed', 'plan_sha256'} or
                    acknowledgment.get('committed') is not True or acknowledgment.get('plan_sha256') != expected_plan_sha256):
                raise ValueError('Atomic bank/hair-policy commit was not acknowledged.')
            self.bank_committed = True
            # The atomic callback consumes pending. Verify native readback again
            # without _guard's intentionally now-consumed checkpoint comparison.
            if _identity(self.identity_reader()) != self.identity:
                raise ValueError('Runtime changed during metadata commit.')
            owners = _forms(self.backend, self.sim, self.known)
            if (self.sim.occult_tracker is not self.tracker or set(owners) != set(self.owner_refs) or
                    any(owners[lane] is not owner for lane, owner in self.owner_refs.items())):
                raise ValueError('Native owner identity changed during metadata commit.')
            after = read_owners(self.backend, self.sim, self.identity_reader)
            if digest(after) != final['raw_final_owners_sha256']:
                raise ValueError('Metadata callback changed native appearance; completion refused.')
            document.update(state='completed', bank_committed=True,
                            save_reload_verified=False, final_native_appearance=final)
            self._write(document)
            self.state = 'completed'
        except Exception as error:
            self._failure(error, 'native reconcile or bank commit')
        return {'ok': True, 'plan_sha256': expected_plan_sha256,
                'accepted_lanes': list(self.plan['accepted_lanes']),
                'all_native_owners_verified': True, 'bank_committed': True,
                'save_reload_verified': False, 'journal_sha256': self.journal_sha256}
