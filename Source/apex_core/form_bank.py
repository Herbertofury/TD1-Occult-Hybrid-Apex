"""Independent full appearance lanes with durable CAS originals and edits.

No whole-Sim loading or gameplay replacement. Ambiguous CAS destinations and
interrupted switches retain both states and refuse further destructive changes.
"""
import json
import hashlib
import os
import copy
import uuid
from pathlib import Path
from . import form_appearance as appearance
from .overlay_loader import _unlinked


def context(backend, sim):
    if sim is None:
        raise ValueError('Select a Sim for independent form ownership.')
    guid = str(backend.services.get_persistence_service().get_save_slot_proto_guid())
    return _unlinked(Path(backend._data_directory()) / 'form_bank.json'), guid + ':' + str(sim.id)


def load(path):
    from .cas_bank_transaction import load_for_write
    return load_for_write(path)


def save(path, data):
    from .cas_bank_transaction import save_from_read
    return save_from_read(path, data)


def capture(backend, sim):
    result = {str(int(kind)): appearance.packed(backend, form)
              for kind, form in backend._form_map(sim.occult_tracker).items()}
    result[str(backend._get_current_flags(sim))] = appearance.packed(backend, sim)
    return result


def restore(backend, sim, lane, fields):
    kind = backend._coerce_flags(int(lane))
    target = backend._ensure_human_form(sim.occult_tracker) if int(lane) == 1 else backend._ensure_form(sim.occult_tracker, kind, generate_new=False)
    if target is None:
        raise ValueError('Required form missing; no replacement generated.')
    expected_fields = appearance.fingerprint(fields)
    expected = expected_fields['appearance_sha256']
    def restore_changed(owner):
        observed = appearance.evidence(backend, owner)
        changed = {name: value for name, value in fields.items()
                   if observed['field_sha256'].get(name) != expected_fields['field_sha256'][name]}
        # Rebuilding matching outfits can filter unrelated genetic CAS parts.
        # Restore only fields which actually differ; complete readback still
        # checks every original field, including any setter side effects.
        from .native_occult_context import appearance_write
        appearance_write(backend, sim, owner,
            lambda: backend._restore_siminfo_payload(owner, appearance.payload(changed)))
    # Native outfit loading and visual resends are unnecessary when every
    # appearance field and normalized outfit byte already matches the bank.
    if appearance.evidence(backend, target)['appearance_sha256'] != expected:
        restore_changed(target)
        if appearance.evidence(backend, target)['appearance_sha256'] != expected:
            observed = appearance.evidence(backend, target)
            changed = sorted(name for name in expected_fields['field_sha256']
                             if observed['field_sha256'].get(name) != expected_fields['field_sha256'][name])
            raise ValueError('Stored form failed exact appearance readback. Lane ' + lane + '; fields: ' + ', '.join(changed))
    if backend._get_current_flags(sim) == int(lane):
        # The active Sim and stored wrapper can diverge independently. Inspect
        # the Sim after any wrapper write rather than inferring its state.
        if appearance.evidence(backend, sim)['appearance_sha256'] != expected:
            restore_changed(sim)
            backend._resend_all_visuals(sim)
            if appearance.evidence(backend, sim)['appearance_sha256'] != expected:
                raise ValueError('Live form failed exact appearance readback.')


def current_runtime_authorized(backend, sim, record):
    """Current native ownership or an exact consumed certified reload only."""
    if not isinstance(record, dict):
        return False
    if type(record.get('runtime_pid')) is int and record['runtime_pid'] == os.getpid():
        return True
    from .form_bank_seal import current_runtime_bank_verified
    try:
        return current_runtime_bank_verified(backend, sim, record)
    except Exception:
        return False  # Unknown/changed/unmarked sidecars never approve a replay.


def begin(backend, sim, hair_target=None):
    assert_idle(backend, sim)
    if (getattr(sim.occult_tracker, '_apex_seal_recovery_required', False) or
            getattr(sim.occult_tracker, '_apex_cas_bank_recovery_required', False)):
        raise ValueError('Sealed reload recovery is unresolved; native appearance edits are blocked.')
    path, key = context(backend, sim)
    data = load(path)
    record = data['records'].get(key)
    if record and (record.get('pending') or record.get('switch_pending')):
        raise ValueError('CAS transaction retained; finish or inspect it first.')
    from .sim_data import snapshot
    originals = capture(backend, sim)
    lane = str(backend._get_current_flags(sim))
    members = [int(kind) for kind in backend._all_occults() if backend._has_occult(sim.occult_tracker, kind)]
    record = record or {'bank': {}, 'history': []}
    if not isinstance(record.get('history', []), list):
        raise ValueError('CAS recovery history must retain its typed index.')
    record['pending'] = {'state': 'captured', 'lane': lane, 'originals': originals,
                         'runtime_pid': os.getpid(),
                         'membership': members, 'traits': backend._disk_trait_snapshot(sim),
                         'native_original': snapshot(backend, sim)}
    from . import outfit_hair
    fresh_runtime = bool(record.get('bank')) and not current_runtime_authorized(backend, sim, record)
    if fresh_runtime:
        # A new checkpoint is the current native state, not permission to replay
        # an uncertified prior-runtime lane omitted from its owner map.
        record['pending']['fresh_runtime_checkpoint'] = True
        record['pending']['prior_bank'] = copy.deepcopy(record['bank'])
        record['pending']['prior_runtime_pid'] = record.get('runtime_pid')
        record['pending']['prior_hair_policy'] = copy.deepcopy(record.get('hair_policy'))
        if record.get('hair_policy', {}).get('enabled'):
            record['hair_policy']['forms'] = {owner: outfit_hair.capture(backend, fields)
                                            for owner, fields in originals.items()}
    record['pending']['hair_target'] = outfit_hair.cas_target(backend, sim, hair_target)
    data['records'][key] = record
    save(path, data)
    preparation = None
    if record.get('hair_policy', {}).get('enabled'):
        pending = record['pending']
        pending['hair_preparation'] = {'state': 'preparing', 'lane': lane}
        save(path, data)  # Originals and preparation intent precede native writes.
        try:
            before = outfit_hair.style_match_status(backend, originals[lane])
            desired = outfit_hair.independent_style_fields(backend, originals[lane])
            restore(backend, sim, lane, desired)
            readback = appearance.packed(backend, sim)
            after = outfit_hair.style_match_status(backend, readback)
            if after['matching_outfit_count'] or after['outfit_count'] != before['outfit_count']:
                raise ValueError('Pre-CAS independent hair flags failed native readback.')
            preparation = dict(state='prepared', lane=lane, outfit_count=after['outfit_count'],
                               matching_before=before['matching_outfit_count'],
                               matching_after=after['matching_outfit_count'],
                               appearance_sha256=appearance.fingerprint(readback)['appearance_sha256'],
                               native_cas_propagation_verified=False)
            pending['hair_preparation'] = preparation
            save(path, data)
        except Exception as error:
            pending['state'] = 'recovery-required'
            pending['hair_preparation'].update(state='failed', error=str(error))
            save(path, data)
            raise
    result = {'ok': True, 'lane': lane, 'message': 'Complete CAS originals retained. Enter native or MCCC CAS, then explicitly finish this transaction.'}
    if preparation is not None: result['hair_preparation'] = preparation
    return result


def update(backend, sim, lane, fields, create=False):
    """Synchronize an explicit accepted appearance change with an existing bank."""
    assert_idle(backend, sim)
    path, key = context(backend, sim)
    data = load(path)
    record = data['records'].get(key)
    if record is None:
        if not create: return
        record = {'bank': capture(backend, sim), 'history': [], 'runtime_pid': os.getpid()}
        data['records'][key] = record
    if record.get('pending') or record.get('switch_pending'):
        raise ValueError('Resolve the pending form transaction before changing appearance.')
    appearance.fingerprint(fields)
    if not current_runtime_authorized(backend, sim, record):
        history = record.setdefault('bank_rebase_history', [])
        if not isinstance(history, list):
            raise ValueError('Native bank rebase history must retain its typed index.')
        native = capture(backend, sim)
        history.append({'state': 'current-native-rebase', 'prior_runtime_pid': record.get('runtime_pid'),
                        'runtime_pid': os.getpid(), 'prior_bank': copy.deepcopy(record['bank']),
                        'prior_hair_policy': copy.deepcopy(record.get('hair_policy')),
                        'native_originals': copy.deepcopy(native), 'accepted_lane': str(int(lane)),
                        'save_reload_verified': False, 'old_bank_restored': False})
        record['bank'] = native
        record['native_rebase_requires_cas_completion'] = True
        if record.get('hair_policy', {}).get('enabled'):
            from . import outfit_hair
            record['hair_policy']['forms'] = {owner: outfit_hair.capture(backend, current)
                                            for owner, current in native.items()}
    record['bank'][str(int(lane))] = fields
    from . import outfit_hair
    outfit_hair.sync(backend, record, lane, fields)
    record['runtime_pid'] = os.getpid()
    save(path, data)


def assert_idle(backend, sim):
    if (getattr(sim.occult_tracker, '_apex_seal_recovery_required', False) or
            getattr(sim.occult_tracker, '_apex_cas_bank_recovery_required', False)):
        raise ValueError('Sealed reload recovery is unresolved; native appearance edits are blocked.')
    path, key = context(backend, sim)
    record = load(path)['records'].get(key)
    from .cas_bank_transaction import _blocked, _lease_path
    if _blocked(record, key) or _lease_path(path).exists():
        raise ValueError('Pending form transaction, CAS journal or writer lease retained. Resolve it before changing appearance.')


def _old_process_absent(pid):
    """Query one exact PID through fixed Win32 functions; never send a signal."""
    if type(pid) is not int or not 0 < pid <= 0xffffffff or pid == os.getpid():
        raise ValueError('Use one valid different prior Windows PID.')
    import paths
    from .overlay_loader import _game_ctypes
    native = _game_ctypes(paths.DLL_PATH)
    class Dword(native._SimpleCData):
        _type_ = 'I'
    class Handle(native._SimpleCData):
        _type_ = 'P'
    class Library:
        _handle = native.LoadLibrary('kernel32.dll')
    def bind(name, result, arguments):
        call = type(name + 'Call', (native.CFuncPtr,), {'_flags_': native.FUNCFLAG_STDCALL,
                    '_restype_': result, '_argtypes_': arguments})
        return call((name, Library()))
    handle = None
    try:
        opened = bind('OpenProcess', Handle, (Dword, Dword, Dword))(0x1000, 0, pid)
        handle = getattr(opened, 'value', opened)
        if not handle:
            result = bind('GetLastError', Dword, ())()
            error = int(getattr(result, 'value', result))
            if error == 87:
                return True
            raise ValueError('Prior PID absence is not verified; Win32 error ' + str(error))
        code = Dword()
        result = bind('GetExitCodeProcess', Dword, (Handle, native.POINTER(Dword)))(handle, native.byref(code))
        if not int(getattr(result, 'value', result)):
            raise ValueError('Prior PID exit observation failed.')
        return code.value != 259
    finally:
        try:
            if handle:
                result = bind('CloseHandle', Dword, (Handle,))(handle)
                if not int(getattr(result, 'value', result)):
                    raise ValueError('Prior PID query handle closure failed.')
        finally:
            native.FreeLibrary(Library._handle)


def _captured_schema2_archive(record, argument, sim_id):
    """Validate old raw originals for metadata archival, never native replay.

    Only a captured transaction which never began observation/serialization or
    native writes may use this narrow path. Unknown or interrupted states stay
    gated; every retained byte is copied into failed history unchanged.
    """
    from . import cas_commit_plan as primitive, cas_bank_transaction as receiver
    from .form_bank_seal import _hash
    pending, transaction = record.get('pending'), record.get('cas_transaction')
    checkpoint_keys = {'schema', 'state', 'runtime_pid', 'lane', 'identity', 'original_owners'}
    transaction_keys = {'schema', 'transaction_id', 'owner_key', 'identity',
        'checkpoint_sha256', 'transaction_sha256', 'record_guard_sha256',
        'hair_checkpoint', 'hair_checkpoint_sha256', 'prior_bank', 'prior_hair_policy',
        'phase', 'journal', 'full_native_original_appended'}
    old_identity = {'runtime_pid': argument['prior_pid'], 'sim_id': sim_id,
                    'household_id': argument['household_id'], 'save_guid': argument['save_guid']}
    if (not isinstance(pending, dict) or set(pending) != checkpoint_keys or
            type(pending.get('schema')) is not int or pending['schema'] != 2 or
            pending.get('state') != 'captured' or type(pending.get('runtime_pid')) is not int or
            pending['runtime_pid'] != argument['prior_pid'] or pending.get('identity') != old_identity or
            type(pending['identity'].get('runtime_pid')) is not int or
            not isinstance(transaction, dict) or set(transaction) != transaction_keys or
            type(transaction.get('schema')) is not int or transaction['schema'] != 1 or
            not receiver._token(transaction.get('transaction_id')) or
            transaction.get('identity') != old_identity or
            type(transaction['identity'].get('runtime_pid')) is not int or transaction.get('owner_key') !=
                argument['save_guid'] + ':' + sim_id or
            transaction.get('phase') != 'captured' or transaction.get('journal') is not None or
            transaction.get('full_native_original_appended') is not False or
            _hash(transaction) != argument['expected_cas_transaction_sha256'] or
            transaction.get('checkpoint_sha256') != primitive.digest(pending) or
            transaction.get('record_guard_sha256') != receiver._record_guard(record) or
            not isinstance(transaction.get('hair_checkpoint'), dict) or
            transaction.get('hair_checkpoint_sha256') != primitive.digest(transaction['hair_checkpoint']) or
            transaction.get('prior_bank') != record.get('bank', {}) or
            transaction.get('prior_hair_policy') != record.get('hair_policy')):
        raise ValueError('Only exact never-observed schema2 CAS originals may be archived; journal retained.')
    envelope = {name: transaction[name] for name in ('transaction_id', 'identity',
        'checkpoint_sha256', 'record_guard_sha256', 'hair_checkpoint_sha256')}
    if transaction.get('transaction_sha256') != primitive.digest(envelope):
        raise ValueError('Captured CAS transaction envelope changed; no metadata archived.')
    raw = pending['original_owners']
    if (not isinstance(raw, dict) or set(raw) != {'identity', 'stored', 'active'} or
            raw.get('identity') != old_identity or type(raw['identity'].get('runtime_pid')) is not int or
            not isinstance(raw.get('stored'), dict) or
            not 1 <= len(raw['stored']) <= 32 or not isinstance(raw.get('active'), dict) or
            set(raw['active']) != {'lane', 'fields'} or raw['active'].get('lane') != pending['lane'] or
            pending['lane'] not in raw['stored']):
        raise ValueError('Captured separate raw owner identities are unavailable; originals retained.')
    for lane, fields in raw['stored'].items():
        if (not isinstance(lane, str) or not lane.isascii() or not lane.isdecimal() or
                str(int(lane)) != lane or not 0 < int(lane) < 1 << 32 or
                int(lane) & (int(lane) - 1)):
            raise ValueError('Captured raw owner lane is not exact; originals retained.')
        appearance.fingerprint(fields)
    primitive._consistent(raw)
    return copy.deepcopy(transaction)


def abandon_unsaved(backend, sim, argument):
    """Archive an exact abandoned CAS intent; no native appearance restoration."""
    fields = {'expected_pending_sha256', 'prior_pid', 'expected_save_sha256', 'slot_id',
              'save_guid', 'household_id', 'failed_return_proof_sha256'}
    optional = 'allow_auto_save_slot_metadata_only'
    schema2_fields = {'expected_cas_transaction_sha256', 'unsaved_exit_proof_sha256'}
    from .form_bank_seal import _identity, _idle, _live, _sha, _hash
    from .test_driver import _save_id, _save_file_evidence
    if (not isinstance(argument, dict) or set(argument) not in (fields, fields | {optional}, fields | schema2_fields, fields | schema2_fields | {optional}) or
            optional in argument and type(argument[optional]) is not bool or type(argument['slot_id']) is not int or
            not 0 < argument['slot_id'] < 0xffffffff or type(argument['prior_pid']) is not int or
            not 0 < argument['prior_pid'] <= 0xffffffff or
            not all(_sha(argument[name]) for name in ('expected_pending_sha256', 'expected_save_sha256', 'failed_return_proof_sha256')) or
            not all(_save_id(argument[name]) for name in ('save_guid', 'household_id')) or
            any(not _sha(argument[name]) for name in schema2_fields if name in argument)):
        raise ValueError('Use exact pending/proof/file hashes and typed prior runtime/save identities.')
    identity, profile, path, key, _seals = _identity(backend, sim)
    _idle()
    target = dict(argument, sim_id=str(sim.id))
    live = _live(backend, sim, target, paused=True)
    data = load(path); record = data['records'].get(key)
    pending = record.get('pending') if isinstance(record, dict) else None
    schema2 = isinstance(pending, dict) and type(pending.get('schema')) is int and pending['schema'] == 2
    if schema2 != schema2_fields.issubset(argument):
        raise ValueError('Schema2 archival requires exact transaction and unsaved-exit proof hashes.')
    if schema2:
        _captured_schema2_archive(record, argument, str(sim.id))
    elif record and record.get('cas_transaction') is not None:
        raise ValueError('A retained modern CAS journal cannot be discarded through legacy archival.')
    disk_slot_verified = live['save_slot'] == argument['slot_id']
    metadata_only_auto = argument.get(optional) is True and live['save_slot'] == 0xffffffff
    metadata_only_zero = (schema2 and argument.get(optional) is True and live['save_slot'] == 0)
    if not (disk_slot_verified or metadata_only_auto or metadata_only_zero) or not _old_process_absent(argument['prior_pid']):
        raise ValueError('Prior process is still live or the reloaded native slot differs; pending was retained.')
    file_row = _save_file_evidence(profile, argument['slot_id'])
    if file_row['sha256'] != argument['expected_save_sha256']:
        raise ValueError('Reloaded save hash differs; pending was retained.')
    pending_hash = hashlib.sha256(json.dumps(pending, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    if (not isinstance(pending, dict) or pending_hash != argument['expected_pending_sha256'] or
            pending.get('state') not in ('captured', 'returned', 'reconciling', 'recovery-required') or
            pending.get('runtime_pid') is not None and (type(pending['runtime_pid']) is not int or pending['runtime_pid'] != argument['prior_pid']) or
            record.get('switch_pending') is not None or not isinstance(record.get('failed_history', []), list)):
        raise ValueError('Exact abandoned CAS pending ownership is unavailable; no metadata changed.')
    if not schema2:
        original = pending.get('native_original')
        if (not isinstance(original, dict) or original.get('sim_id') != str(sim.id) or
                original.get('save_guid') != argument['save_guid']):
            raise ValueError('Pending originals belong to another native Sim/save; no metadata changed.')
        native_fields = original.get('data', {}).get('fields', [])
        household = [row for row in native_fields if isinstance(row, dict) and row.get('name') == 'household_id']
        if len(household) != 1 or household[0].get('present') is not True or household[0].get('value') != argument['household_id']:
            raise ValueError('Pending native household identity differs; no metadata changed.')
    bank_before = _hash(record['bank'])
    failed = {'pending': pending, 'pending_sha256': pending_hash, 'state': 'abandoned-unsaved-exit',
        'prior_pid': argument['prior_pid'], 'new_pid': identity['pid'],
        'failed_return_proof_sha256': argument['failed_return_proof_sha256'], 'reloaded_file': file_row,
        'sim_id': str(sim.id), 'household_id': argument['household_id'], 'save_guid': argument['save_guid'],
        'appearance_restored': False, 'seal_created': False, 'actual_native_slot_id': live['save_slot'],
        'disk_slot_verified': disk_slot_verified, 'metadata_archive_only': True,
        'loaded_file_verified': False, 'save_reload_verified': False}
    if schema2:
        from . import cas_bank_transaction as receiver
        retained_record = copy.deepcopy(record)
        failed.update(cas_transaction=copy.deepcopy(record['cas_transaction']),
            cas_transaction_sha256=argument['expected_cas_transaction_sha256'],
            unsaved_exit_proof_sha256=argument['unsaved_exit_proof_sha256'],
            checkpoint_schema=2, native_write_attempted=False, native_serializer_called=False)
        def archive(data_now, selected, fresh_identity):
            expected_identity = {'runtime_pid': identity['pid'], 'sim_id': str(sim.id),
                'household_id': argument['household_id'], 'save_guid': argument['save_guid']}
            if selected != retained_record or fresh_identity != expected_identity:
                raise ValueError('Captured CAS metadata changed before archival; no replacement.')
            _captured_schema2_archive(selected, argument, str(sim.id))
            _idle()
            fresh_live = _live(backend, sim, target, paused=True)
            if (any(fresh_live.get(name) != live.get(name) for name in
                    ('save_guid', 'household_id', 'client_id', 'zone_id', 'save_slot')) or
                    not _old_process_absent(argument['prior_pid']) or
                    _save_file_evidence(profile, argument['slot_id'])['sha256'] != argument['expected_save_sha256']):
                raise ValueError('Native/file/prior-process identity changed before metadata archival.')
            selected.setdefault('failed_history', []).append(copy.deepcopy(failed))
            selected['pending'] = None
            selected['cas_transaction'] = None
        receiver._mutate(backend, sim, archive)
        record = load(path)['records'][key]
    else:
        record.setdefault('failed_history', []).append(failed); record['pending'] = None
        save(path, data)
    return {'ok': True, 'state': 'abandoned-unsaved-exit', 'prior_pid': argument['prior_pid'],
            'abandoned': True, 'appearance_mutated': False, 'save_written': False,
            'pending_sha256': argument['expected_pending_sha256'], 'failed_return_proof_sha256': argument['failed_return_proof_sha256'],
            'bank_sha256': bank_before, 'bank_appearances_changed': False, 'appearance_restored': False,
            'save_file_written': False, 'seal_created': False, 'failed_history_count': len(record['failed_history']),
            'actual_native_slot_id': live['save_slot'], 'disk_slot_verified': disk_slot_verified,
            'metadata_archive_only': True, 'loaded_file_verified': False, 'save_reload_verified': False,
            'cas_transaction_archived': schema2, 'native_serializer_called': False,
            'native_write_attempted': False}


def finish(backend, sim):
    path, key = context(backend, sim)
    data = load(path)
    record = data['records'].get(key)
    pending = record.get('pending') if record else None
    if record and (record.get('cas_transaction') is not None or isinstance(pending, dict) and pending.get('schema') == 2):
        return {'ok': False, 'outcome': 'explicit-owner-decisions-required',
                'native_appearance_written': False, 'save_reload_verified': False,
                'message': 'Use cas-bank observe, prepare and commit with explicit decisions for every changed form. No edits were guessed or restored.'}
    if not pending or pending.get('state') not in ('captured', 'returned'):
        raise ValueError('No recoverable CAS transaction; interrupted states retained for inspection.')
    if type(pending.get('runtime_pid')) is not int or pending['runtime_pid'] != os.getpid():
        raise ValueError('CAS originals belong to another or unknown runtime; retain them for verified metadata abandonment.')
    from .sim_data import snapshot
    returned = capture(backend, sim)
    pending.update(state='returned', returned=returned)
    save(path, data)  # Raw returned edits are durable BEFORE native serialization.
    lane, current = pending['lane'], str(backend._get_current_flags(sim))
    changed_other = [other for other, fields in returned.items() if other != lane and
        (other not in pending['originals'] or appearance.fingerprint(fields)['appearance_sha256'] !=
         appearance.fingerprint(pending['originals'][other])['appearance_sha256'])]
    if changed_other or set(returned) != set(pending['originals']):
        raise ValueError('Legacy CAS edited another form or changed ownership outside its entry lane; every returned state was retained, no other-form edits discarded.')
    pending['native_returned'] = snapshot(backend, sim)
    save(path, data)
    chosen = returned.get(lane)
    if chosen is None:
        raise ValueError('CAS returned no selected form; both states retained.')
    before = pending['originals'].get(lane)
    from . import outfit_hair
    chosen = outfit_hair.accept_cas(backend, record, lane, chosen, pending.get('hair_target'))
    changed = before is None or appearance.fingerprint(chosen)['appearance_sha256'] != appearance.fingerprint(before)['appearance_sha256']
    if current != lane and not changed and current in returned and current in pending['originals']:
        wrong_changed = appearance.fingerprint(returned[current])['appearance_sha256'] != appearance.fingerprint(pending['originals'][current])['appearance_sha256']
        if wrong_changed:
            raise ValueError('CAS edited another form; destination not guessed. Both states retained.')
    pending.update(state='reconciling', accepted=chosen)
    save(path, data)
    try:
        for flags in pending['membership']:
            kind = backend._coerce_flags(flags)
            if not backend._has_occult(sim.occult_tracker, kind):
                backend._add_occult(sim, kind, generate=True, add_traits=False, add_memory=False, use_gameplay_loot=False)
        backend._restore_disk_trait_snapshot(sim, pending['traits'])
        required_traits = {str(row['trait_id']) for row in pending['traits']}
        restored_traits = {str(row['trait_id']) for row in backend._disk_trait_snapshot(sim)}
        if not required_traits.issubset(restored_traits):
            raise ValueError('CAS occult trait recovery failed readback; all returned states retained.')
        if any(not backend._has_occult(sim.occult_tracker, backend._coerce_flags(flags))
               for flags in pending['membership']):
            raise ValueError('CAS membership recovery failed readback; all returned states retained.')
        for other, fields in pending['originals'].items():
            if other != lane:
                restore(backend, sim, other, fields)
        restore(backend, sim, lane, chosen)
        # Prior bank lanes absent from this native checkpoint remain historical
        # evidence only. They cannot create/overwrite a missing native owner.
        record['bank'] = dict(pending['originals'])
        record['bank'][lane] = chosen
        outfit_hair.sync(backend, record, lane, chosen)
        record['active_lane'] = current
        record['runtime_pid'] = os.getpid()
        pending['native_after'] = snapshot(backend, sim)
        pending['native_after_scope'] = 'Native serializer buffer before final native appearance readback; not final appearance proof.'
        # The real native serializer regenerates hidden outfits as shared
        # clothing. Completion is verified after this call, never before it.
        for verified_lane, verified_fields in record['bank'].items():
            restore(backend, sim, verified_lane, verified_fields)
        native_forms = backend._form_map(sim.occult_tracker)
        verified_owners = {}
        for verified_lane, verified_fields in record['bank'].items():
            native_owner = native_forms.get(backend._coerce_flags(int(verified_lane)))
            if native_owner is None:
                raise ValueError('Final stored native appearance owner missing after serialization.')
            observed = appearance.evidence(backend, native_owner)
            if observed['appearance_sha256'] != appearance.fingerprint(verified_fields)['appearance_sha256']:
                raise ValueError('Final stored native appearance differs after serialization.')
            verified_owners[verified_lane] = observed
        live_final = appearance.evidence(backend, sim)
        if live_final['appearance_sha256'] != appearance.fingerprint(record['bank'][current])['appearance_sha256']:
            raise ValueError('Final active native appearance differs after serialization.')
        pending['final_native_appearance'] = {'stored': verified_owners, 'active_lane': current,
                                            'active_live': live_final, 'verified': True}
        record['native_rebase_requires_cas_completion'] = False
        pending['state'] = 'completed'
        record.setdefault('history', []).append(pending)
        record['pending'] = None
        save(path, data)
    except Exception:
        pending['state'] = 'recovery-required'
        save(path, data)
        raise
    return {'ok': True, 'lane': lane, 'edited': changed, 'message': 'CAS edit accepted in selected lane; other appearances restored and verified. Save/reload proof remains separate.'}


def status(backend, sim):
    path, key = context(backend, sim)
    record = load(path)['records'].get(key)
    if record is None:
        return {'ok': True, 'captured': False, 'message': 'No CAS form transaction captured for this Sim.'}
    pending = record.get('pending')
    result = {'ok': True, 'captured': True, 'active_lane': record.get('active_lane'),
            'bank_lanes': sorted(record.get('bank', {})), 'history_count': len(record.get('history', [])),
            'pending_state': pending.get('state') if pending else None,
            'pending_lane': pending.get('lane') if pending else None,
            'switch_pending': bool(record.get('switch_pending')),
            'pending_schema': pending.get('schema') if isinstance(pending, dict) else None,
            'message': 'CAS originals, returned edits and native Sim records are retained; save/reload verification is separate.'}
    if record.get('cas_transaction') is not None:
        from .cas_bank_transaction import status as transaction_status
        result['cas_transaction'] = transaction_status(backend, sim)
    return result


def _switch_lane(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a native owner identity.')
    result = int(value)
    if result <= 0 or result & (result - 1):
        raise ValueError('One exact native appearance owner is required.')
    return str(result)


def _switch_owner_id(owner, require_positive=False):
    try:
        value = owner.id
    except AttributeError:
        return {'query': 'unavailable', 'value': None}
    if isinstance(value, bool):
        raise ValueError('Native Sim identity is untyped.')
    minimum = 1 if require_positive else 0
    if not isinstance(value, int) or not minimum <= value < (1 << 64):
        raise ValueError('Native Sim identity is invalid.')
    return {'query': 'returned-value', 'value': str(value)}


def _switch_owners(backend, tracker):
    source = backend._form_map(tracker)
    if not isinstance(source, dict) or not source:
        raise ValueError('Complete existing native owner map is unavailable.')
    owners = {}
    for kind, owner in source.items():
        lane = _switch_lane(kind)
        if owner is None or lane in owners:
            raise ValueError('Native appearance owner is missing or duplicated.')
        owners[lane] = owner
    if len({id(owner) for owner in owners.values()}) != len(owners):
        raise ValueError('Stored owners alias; independent reconciliation is unsupported.')
    return owners


def _switch_manager_sim(backend, sim):
    accessor = getattr(backend.services, 'sim_info_manager', None)
    if accessor is None:
        return False  # Explicitly unavailable, not an invented identity proof.
    manager = accessor()
    if manager is None or manager.get(sim.id) is not sim:
        raise ValueError('Original Sim is not the exact native manager object.')
    return True


def _switch_check_identity(backend, sim, tracker, owners, owner_ids, location, manager):
    if sim.occult_tracker is not tracker or context(backend, sim) != location:
        raise ValueError('Native Sim/tracker/save context changed; no reconciliation authorized.')
    if manager and not _switch_manager_sim(backend, sim):
        raise ValueError('Native manager identity disappeared.')
    current = _switch_owners(backend, tracker)
    if set(current) != set(owners):
        raise ValueError('Native owner set changed; no missing or new owner is reconstructed.')
    for lane, owner in owners.items():
        if current[lane] is not owner or _switch_owner_id(owner) != owner_ids[lane]:
            raise ValueError('Native owner identity changed; replacement mapping is unproved.')


def _switch_snapshots(backend, owners):
    return {lane: appearance.packed(backend, owner) for lane, owner in owners.items()}


def _switch_hashes(fields):
    return {lane: appearance.fingerprint(value)['appearance_sha256']
            for lane, value in fields.items()}


def _switch_bank_differences(bank, native):
    differences = {}
    for lane, fields in native.items():
        current = appearance.fingerprint(fields)
        cached = appearance.fingerprint(bank[lane]) if lane in bank else None
        if cached == current:
            continue
        fields_before = cached['field_sha256'] if cached else {}
        differences[lane] = {
            'bank_present': cached is not None,
            'bank_appearance_sha256': cached['appearance_sha256'] if cached else None,
            'native_appearance_sha256': current['appearance_sha256'],
            'changed_fields': sorted(name for name in set(fields_before) | set(current['field_sha256'])
                                    if fields_before.get(name) != current['field_sha256'].get(name))}
    return differences


def _switch_hair_policy(backend, prior, desired):
    if not isinstance(prior, dict) or not prior.get('enabled'):
        return None
    from . import outfit_hair
    prepared = copy.deepcopy(prior)
    forms = {}
    for lane, fields in desired.items():
        held = outfit_hair.capture(backend, fields)
        index = outfit_hair._held_index(held)
        slots, ordinals = {}, {}
        for outfit in outfit_hair._message(backend, fields).outfits:
            category = int(outfit.category)
            ordinal = ordinals.get(category, 0)
            ordinals[category] = ordinal + 1
            slots[(category, ordinal)] = str(outfit.outfit_id)
        if ({slot: row['outfit_id'] for slot, row in index.items()} != slots or
                appearance.fingerprint(outfit_hair.reconcile(backend, fields, held)) !=
                appearance.fingerprint(fields)):
            raise ValueError('Hair policy capture differs from the complete intended native owner wardrobe.')
        forms[lane] = held
    prepared['forms'] = forms
    return prepared


def switch(backend, sim, target, operation):
    """Preserve all current owners around one native form switch.

    Fresh inactive native appearances, including the selected target, retain
    unsaved CAS/MCCC edits. The latest active source wins over its stored copy.
    Prior bank fields are evidence only; completion proves immediate readback,
    not stability after simulation progression or a later save/reload.
    """
    assert_idle(backend, sim)
    location = context(backend, sim)
    path, key = location
    data = load(path)
    record = data['records'].get(key)
    if record and (record.get('pending') or record.get('switch_pending')):
        raise ValueError('Unresolved native transaction retained; switching is blocked.')
    if record and record.get('bank') and not current_runtime_authorized(backend, sim, record):
        raise ValueError('Prior-runtime bank is uncertified; no old appearance replay authorized.')
    prior_history = record.get('switch_history', []) if record else []
    if not isinstance(prior_history, list):
        raise ValueError('Switch recovery history must retain its typed index.')

    source, target = _switch_lane(backend._get_current_flags(sim)), _switch_lane(target)
    tracker = sim.occult_tracker
    owners = _switch_owners(backend, tracker)
    if source not in owners or target not in owners:
        raise ValueError('Existing source and target owners are required; none is generated.')
    if any(owner is sim for owner in owners.values()):
        raise ValueError('Active Sim aliases stored appearance; distinct ownership is unproved.')
    manager = _switch_manager_sim(backend, sim)
    owner_ids = {lane: _switch_owner_id(owner) for lane, owner in owners.items()}
    stored_originals = _switch_snapshots(backend, owners)
    active_original = appearance.packed(backend, sim)
    previous_bank = copy.deepcopy(record.get('bank', {})) if record else {}
    prior_hair_policy = copy.deepcopy(record.get('hair_policy')) if record else None
    if set(previous_bank) - set(owners):
        raise ValueError('Bank contains an absent native owner; no reconstruction or prior replay authorized.')
    expected = copy.deepcopy(stored_originals)
    # A cached target is not authority over a newer inactive native edit. Keep
    # the complete cache and its differences as evidence, never replay it.
    native_vs_bank = _switch_bank_differences(previous_bank, stored_originals)
    active_vs_bank = _switch_bank_differences(previous_bank, {source: active_original})
    expected[source] = copy.deepcopy(active_original)  # Latest Live source also wins for a same-owner selection.
    desired_active = copy.deepcopy(expected[target])
    _switch_check_identity(backend, sim, tracker, owners, owner_ids, location, manager)

    record = record or {'bank': {}, 'history': []}
    data['records'][key] = record
    from .bank_history import externalize
    externalize(path, record)
    record['bank'][source] = copy.deepcopy(active_original)
    pending = {'schema': 2, 'state': 'captured', 'request_id': uuid.uuid4().hex,
               'source': source, 'target': target, 'runtime_pid': os.getpid(),
               'original': copy.deepcopy(active_original),  # Existing recovery field remains useful.
               'stored_originals': stored_originals, 'active_original': active_original,
               'owner_ids': owner_ids, 'sim_id': _switch_owner_id(sim, require_positive=True),
               'manager_identity_verified': manager,
               'previous_bank': previous_bank,
               'prior_hair_policy': prior_hair_policy,
               'appearance_authority': 'fresh-native-before-switch',
               'native_vs_bank_differences': native_vs_bank,
               'active_source_vs_bank_differences': active_vs_bank,
               'desired_stored': expected,
               'desired_active': desired_active,
               'native_operation_attempted': False,
               'all_stored_owners_verified': False, 'active_owner_verified': False,
               'simulation_settled_verified': False, 'save_reload_verified': False}
    record['switch_pending'] = pending
    save(path, data)  # Complete originals precede every native write.

    def retain_failure(error, state):
        pending['state'], pending['error'] = state, str(error)[:8192]
        try:
            _switch_check_identity(backend, sim, tracker, owners, owner_ids, location, manager)
            pending['returned_stored'] = _switch_snapshots(backend, owners)
            pending['returned_active'] = appearance.packed(backend, sim)
            pending['returned_scope'] = 'Exact original owner identities; partial native result retained.'
            pending['returned_identity_verified'] = True
        except Exception as capture_error:
            pending['returned_capture_error'] = str(capture_error)[:8192]
            pending['returned_identity_verified'] = False
            # Retain a replacement/new map only as unverified observed data.
            # Never dereference old removed wrappers or use new ones to repair.
            try:
                if sim.occult_tracker is not tracker or context(backend, sim) != location:
                    raise ValueError('Context changed; no cross-context return read authorized.')
                current = _switch_owners(backend, tracker)
                pending['unverified_returned_owner_ids'] = {lane: _switch_owner_id(owner) for lane, owner in current.items()}
                pending['unverified_returned_stored'] = _switch_snapshots(backend, current)
                pending['unverified_returned_scope'] = 'Read-only changed native owner map; no replacement/restore authority.'
            except Exception as observed_error:
                pending['unverified_return_capture_error'] = str(observed_error)[:8192]
        # If storage itself fails, the last successful durable captured/issued
        # record still contains every original/desired owner. Never clear it.
        save(path, data)

    try:
        # Hair callbacks are blocked by the durable pending record while the
        # complete new wardrobe is planned. Partial/ambiguous capture must not
        # leave the older enabled policy able to undo a fresh native edit.
        pending['state'] = 'hair-policy-planning'
        desired_hair_policy = _switch_hair_policy(backend, prior_hair_policy, expected)
        pending['hair_policy_plan'] = copy.deepcopy(desired_hair_policy)
        pending['hair_policy_synchronized'] = False
        _switch_check_identity(backend, sim, tracker, owners, owner_ids, location, manager)
        pending['state'] = 'native-operation-armed'
        save(path, data)
        pending['state'] = 'native-operation-issued'
        pending['native_operation_attempted'] = True
        save(path, data)  # Durable submission intent; a crash cannot report an unarmed/no-attempt state.
        result = operation()  # Exactly one call. Subsequent calls encounter WAL.
        if not isinstance(result, dict) or type(result.get('ok')) is not bool:
            raise ValueError('Native switch outcome is untyped; retain unresolved original request.')
        pending['native_operation_result'] = {'ok': result['ok'], 'message': str(result.get('message', ''))[:8192]}
        _switch_check_identity(backend, sim, tracker, owners, owner_ids, location, manager)
        if not result['ok'] or _switch_lane(backend._get_current_flags(sim)) != target:
            retain_failure('Native form did not converge to the exact existing target.', 'native-did-not-converge')
            return dict(result, ok=False, independent_appearance_verified=False,
                        message='Form did not converge; every original owner and latest source retained.',
                        switch_request_id=pending['request_id'])
        pending['state'] = 'reconciling-existing-owners'
        pending['native_returned_stored'] = _switch_snapshots(backend, owners)
        pending['native_returned_active'] = appearance.packed(backend, sim)
        save(path, data)

        def write_if_changed(owner, fields, active=False):
            _switch_check_identity(backend, sim, tracker, owners, owner_ids, location, manager)
            expected_hash = appearance.fingerprint(fields)['appearance_sha256']
            if appearance.evidence(backend, owner)['appearance_sha256'] != expected_hash:
                from .native_occult_context import appearance_write
                appearance_write(backend, sim, owner,
                    lambda: backend._restore_siminfo_payload(owner, appearance.payload(fields)))
                if active:
                    backend._resend_all_visuals(sim)
                if appearance.evidence(backend, owner)['appearance_sha256'] != expected_hash:
                    raise ValueError('Native owner failed exact immediate appearance readback.')

        for lane, owner in owners.items():
            write_if_changed(owner, expected[lane])
        write_if_changed(sim, desired_active, active=True)
        # A later setter/resend may have changed an earlier wrapper. Every
        # owner must be read again after the last native write, including Live.
        _switch_check_identity(backend, sim, tracker, owners, owner_ids, location, manager)
        final_stored = _switch_snapshots(backend, owners)
        final_active = appearance.packed(backend, sim)
        if _switch_hashes(final_stored) != _switch_hashes(expected):
            raise ValueError('All stored owners failed final readback after the last native write.')
        if appearance.fingerprint(final_active) != appearance.fingerprint(desired_active):
            raise ValueError('Distinct active owner failed final appearance readback.')
        if _switch_lane(backend._get_current_flags(sim)) != target:
            raise ValueError('Target owner changed during native reconciliation.')
        pending['all_stored_owners_verified'] = pending['active_owner_verified'] = True
        pending['verified_stored_hashes'] = _switch_hashes(final_stored)
        pending['verified_active_hash'] = appearance.fingerprint(final_active)['appearance_sha256']
        pending['state'] = 'immediate-native-readback-verified'
        save(path, data)
        record['bank'] = copy.deepcopy(expected)
        if desired_hair_policy is not None:
            record['hair_policy'] = copy.deepcopy(desired_hair_policy)
            pending['hair_policy_synchronized'] = True
        record['active_lane'] = target
        record['runtime_pid'] = os.getpid()
        # Retain full before/after evidence even after clearing the write block.
        history = record.setdefault('switch_history', [])
        if not isinstance(history, list):
            raise ValueError('Switch recovery history must retain its typed index.')
        history.append(copy.deepcopy(pending))
        record['switch_pending'] = None
        save(path, data)
        return dict(result, independent_appearance_verified=True,
                    all_stored_owners_verified=True, active_owner_verified=True,
                    simulation_settled_verified=False, save_reload_verified=False,
                    hair_policy_synchronized=desired_hair_policy is not None,
                    switch_request_id=pending['request_id'],
                    stored_owner_hashes=_switch_hashes(final_stored),
                    appearance=appearance.fingerprint(final_active))
    except Exception as error:
        record['switch_pending'] = pending
        try:
            retain_failure(error, 'recovery-required')
        except Exception as storage_error:
            # The last successful WAL still blocks replay and retains every
            # original. Surface the native failure that led here rather than
            # replacing it with a secondary failure to persist its diagnosis.
            pending['retention_storage_error'] = str(storage_error)[:8192]
            logger = getattr(backend, '_log', None)
            if logger is not None:
                try:
                    logger('Switch failure retained by prior WAL; diagnostic storage failed: ' +
                           str(storage_error)[:8192])
                except Exception:
                    pass
        raise
