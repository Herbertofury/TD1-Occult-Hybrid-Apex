"""Independent full appearance lanes with durable CAS originals and edits.

No whole-Sim loading or gameplay replacement. Ambiguous CAS destinations and
interrupted switches retain both states and refuse further destructive changes.
"""
import json
import os
from pathlib import Path
from . import form_appearance as appearance
from .overlay_loader import _unlinked


def context(backend, sim):
    if sim is None:
        raise ValueError('Select a Sim for independent form ownership.')
    guid = str(backend.services.get_persistence_service().get_save_slot_proto_guid())
    return _unlinked(Path(backend._data_directory()) / 'form_bank.json'), guid + ':' + str(sim.id)


def load(path):
    if not path.exists():
        return {'schema': 1, 'records': {}}
    if path.stat().st_size > 48 * 1024 * 1024:
        raise ValueError('Form bank exceeds its bound; prior records retained.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('records'), dict) or len(data['records']) > 256:
        raise ValueError('Invalid form bank.')
    return data


def save(path, data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False).encode('utf-8')
    if len(raw) > 48 * 1024 * 1024 or len(data['records']) > 256:
        raise ValueError('Form bank capacity reached; no original discarded.')
    temporary = _unlinked(path.with_suffix('.pending'))
    with temporary.open('wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


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
    backend._restore_siminfo_payload(target, appearance.payload(fields))
    expected = appearance.fingerprint(fields)['appearance_sha256']
    if appearance.evidence(backend, target)['appearance_sha256'] != expected:
        raise ValueError('Stored form failed exact appearance readback.')
    if backend._get_current_flags(sim) == int(lane):
        backend._restore_siminfo_payload(sim, appearance.payload(fields))
        backend._resend_all_visuals(sim)
        if appearance.evidence(backend, sim)['appearance_sha256'] != expected:
            raise ValueError('Live form failed exact appearance readback.')


def begin(backend, sim, hair_target=None):
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
    if len(record.get('history', [])) >= 32:
        raise ValueError('CAS recovery history full; no original discarded.')
    record['pending'] = {'state': 'captured', 'lane': lane, 'originals': originals,
                         'membership': members, 'traits': backend._disk_trait_snapshot(sim),
                         'native_original': snapshot(backend, sim)}
    from . import outfit_hair
    record['pending']['hair_target'] = outfit_hair.cas_target(backend, sim, hair_target)
    data['records'][key] = record
    save(path, data)
    return {'ok': True, 'lane': lane, 'message': 'Complete CAS originals retained. Enter native or MCCC CAS, then explicitly finish this transaction.'}


def update(backend, sim, lane, fields, create=False):
    """Synchronize an explicit accepted appearance change with an existing bank."""
    path, key = context(backend, sim)
    data = load(path)
    record = data['records'].get(key)
    if record is None:
        if not create: return
        record = {'bank': capture(backend, sim), 'history': []}
        data['records'][key] = record
    if record.get('pending') or record.get('switch_pending'):
        raise ValueError('Resolve the pending form transaction before changing appearance.')
    appearance.fingerprint(fields)
    record['bank'][str(int(lane))] = fields
    from . import outfit_hair
    outfit_hair.sync(backend, record, lane, fields)
    record['runtime_pid'] = os.getpid()
    save(path, data)


def assert_idle(backend, sim):
    path, key = context(backend, sim)
    record = load(path)['records'].get(key)
    if record and (record.get('pending') or record.get('switch_pending')):
        raise ValueError('Resolve the pending form transaction before changing appearance.')


def finish(backend, sim):
    path, key = context(backend, sim)
    data = load(path)
    record = data['records'].get(key)
    pending = record.get('pending') if record else None
    if not pending or pending.get('state') not in ('captured', 'returned'):
        raise ValueError('No recoverable CAS transaction; interrupted states retained for inspection.')
    from .sim_data import snapshot
    returned = capture(backend, sim)
    pending.update(state='returned', returned=returned, native_returned=snapshot(backend, sim))
    save(path, data)  # Returned edits preserved before any reconciliation.
    lane, current = pending['lane'], str(backend._get_current_flags(sim))
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
        record['bank'].update(pending['originals'])
        record['bank'][lane] = chosen
        outfit_hair.sync(backend, record, lane, chosen)
        record['active_lane'] = current
        record['runtime_pid'] = os.getpid()
        pending['native_after'] = snapshot(backend, sim)
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
    return {'ok': True, 'captured': True, 'active_lane': record.get('active_lane'),
            'bank_lanes': sorted(record.get('bank', {})), 'history_count': len(record.get('history', [])),
            'pending_state': pending.get('state') if pending else None,
            'pending_lane': pending.get('lane') if pending else None,
            'switch_pending': bool(record.get('switch_pending')),
            'message': 'CAS originals, returned edits and native Sim records are retained; save/reload verification is separate.'}


def switch(backend, sim, target, operation):
    path, key = context(backend, sim)
    data = load(path)
    record = data['records'].get(key)
    if record and (record.get('pending') or record.get('switch_pending')):
        raise ValueError('Pending CAS/form transition retained; resolve it before switching.')
    if not record or not record.get('bank'):
        return operation()
    source, target = str(backend._get_current_flags(sim)), str(int(target))
    before = appearance.packed(backend, sim)
    # A newly loaded EA form may diverge from the accepted bank (including
    # Spellcaster's unsaved native appearance record). Retain that observation;
    # never overwrite the accepted lane merely because the game restarted.
    if record.get('runtime_pid') != os.getpid() and source in record['bank']:
        observed = record.setdefault('restart_observations', [])
        if len(observed) >= 32:
            raise ValueError('Restart observations full; no prior appearance discarded.')
        observed.append({'lane': source, 'fields': before})
    else:
        record['bank'][source] = before
    record['switch_pending'] = {'source': source, 'target': target, 'original': before}
    save(path, data)
    result = operation()
    if not result.get('ok') or backend._get_current_flags(sim) != int(target):
        return dict(result, ok=False, message='Form did not converge; original and target bank states retained.')
    if target in record['bank']:
        restore(backend, sim, target, record['bank'][target])
    else:
        record['bank'][target] = appearance.packed(backend, sim)
    record['active_lane'] = target
    record['runtime_pid'] = os.getpid()
    record['switch_pending'] = None
    save(path, data)
    return dict(result, independent_appearance_verified=True, appearance=appearance.evidence(backend, sim))
