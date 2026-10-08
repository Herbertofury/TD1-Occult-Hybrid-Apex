"""Human-looking active Werewolf appearance, with a durable original receipt.

Only explicit user actions copy appearance. No trait, statistic, perk, fury,
membership or current-form mutation; no polling that overwrites later CAS edits.
"""
import json
import os
from pathlib import Path
from . import form_appearance as appearance
from .overlay_loader import _unlinked


def storage(backend):
    return _unlinked(Path(backend._data_directory()) / 'human_werewolf.json')


def load(path):
    if not path.exists():
        return {'schema': 1, 'records': {}}
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Human Werewolf recovery receipt exceeds its bound.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if (data.get('schema') != 1 or not isinstance(data.get('records'), dict) or len(data['records']) > 256
            or not isinstance(data.get('retired', {}), dict) or len(data.get('retired', {})) > 256):
        raise ValueError('Invalid Human Werewolf recovery receipt.')
    return data


def save(path, data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False).encode('utf-8')
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError('Human Werewolf receipt exceeds its bound.')
    temporary = _unlinked(path.with_suffix('.pending'))
    with temporary.open('wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def dispatch(backend, sim, action):
    if sim is None:
        raise ValueError('Select a Sim with Werewolf membership.')
    werewolf, human = backend._occult_by_name('WEREWOLF'), backend.OccultType.HUMAN
    if werewolf is None or not backend._has_occult(sim.occult_tracker, werewolf):
        raise ValueError('The selected Sim has no Werewolf membership.')
    tracker = sim.occult_tracker
    target = tracker.get_occult_sim_info(werewolf)
    source = sim if backend._get_current_flags(sim) == int(human) else tracker.get_occult_sim_info(human)
    if target is None or source is None:
        raise ValueError('Existing Human and Werewolf appearance records are required; no forms were generated.')
    guid = str(backend.services.get_persistence_service().get_save_slot_proto_guid())
    key = guid + ':' + str(sim.id)
    path, data = storage(backend), None
    data = load(path)
    record = data['records'].get(key)
    if action == 'werewolf_human_status':
        return {'ok': True, 'enabled': bool(record and record.get('state') == 'enabled'),
                'receipt_state': record.get('state') if record else 'disabled',
                'active_werewolf': backend._get_current_flags(sim) == int(werewolf),
                'message': 'Human-looking Werewolf changes appearance only; all Werewolf gameplay remains owned by the game.'}
    active = backend._get_current_flags(sim) == int(werewolf)
    from . import form_bank
    form_bank.assert_idle(backend, sim)
    live_before = appearance.packed(backend, sim) if active else None
    before = appearance.packed(backend, target)
    before_sha = appearance.fingerprint(before)['appearance_sha256']
    if len(data['records']) >= 256 and not record:
        raise ValueError('Human Werewolf receipt capacity reached; all prior recovery records were retained.')
    if action == 'werewolf_human_on':
        if record:
            if record.get('state') == 'enabled':
                return {'ok': True, 'enabled': True, 'message': 'Human-looking Werewolf is already enabled; later CAS edits were retained.'}
            raise ValueError('An interrupted Werewolf appearance change has a recovery receipt; inspect it before another change.')
        desired = appearance.packed(backend, source)
        record = {'state': 'enabling', 'save_guid': guid, 'sim_id': str(sim.id),
                  'original': before, 'original_sha256': before_sha,
                  'enabled_sha256': appearance.fingerprint(desired)['appearance_sha256']}
        data['records'][key] = record
    elif action == 'werewolf_human_off':
        if not record:
            return {'ok': True, 'enabled': False, 'message': 'Human-looking Werewolf is already disabled.'}
        if record.get('state') != 'enabled' or before_sha != record.get('enabled_sha256'):
            raise ValueError('Werewolf appearance has newer edits or an interrupted change. Original and edited states are retained; automatic restore was refused.')
        desired = record['original']
        if appearance.fingerprint(desired)['appearance_sha256'] != record['original_sha256']:
            raise ValueError('Original Werewolf receipt failed its appearance identity check.')
        if len(data.get('retired', {})) >= 256 and key not in data.get('retired', {}):
            raise ValueError('Retired receipt capacity reached; no recovery records were discarded.')
        record['state'] = 'disabling'
    else:
        raise ValueError('Unsupported Human Werewolf action.')
    save(path, data)  # Durable preimage precedes any mutation.
    try:
        expected = appearance.fingerprint(desired)['appearance_sha256']
        backend._restore_siminfo_payload(target, appearance.payload(desired))
        if active:
            backend._restore_siminfo_payload(sim, appearance.payload(desired))
        if appearance.evidence(backend, target)['appearance_sha256'] != expected or active and appearance.evidence(backend, sim)['appearance_sha256'] != expected:
            raise ValueError('Exact appearance readback failed.')
        form_bank.update(backend, sim, int(werewolf), desired)
    except Exception:
        backend._restore_siminfo_payload(target, appearance.payload(before))
        if active:
            backend._restore_siminfo_payload(sim, appearance.payload(live_before))
        record['state'] = 'recovery-required'
        save(path, data)
        raise
    enabled = action == 'werewolf_human_on'
    if enabled:
        record['state'] = 'enabled'
    else:
        # Keep the old appearance receipt even after a successful disable.
        record['state'] = 'disabled'
        data.setdefault('retired', {})[key] = data['records'].pop(key)
    save(path, data)
    return {'ok': True, 'enabled': enabled, 'active_werewolf': active,
            'appearance_sha256': expected, 'gameplay_mutated': False, 'save_reload_verified': False,
            'message': ('Human appearance applied to the Werewolf form.' if enabled else 'Original Werewolf appearance restored.') + ' Unpause briefly, then verify the visible form and gameplay.'}
