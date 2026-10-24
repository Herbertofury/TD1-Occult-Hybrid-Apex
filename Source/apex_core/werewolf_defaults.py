"""Prepare an EA-generated Werewolf appearance without adopting its owners.

The installed 1.128 generator replaces the map entry and shares pelt data with
Human. Every pre-existing owner and map identity is restored before returning
the detached result. The normal Studio journal owns later Apply/Undo.
"""
import inspect
import json
import os
from pathlib import Path
from . import form_appearance as appearance, form_bank
from .overlay_loader import _unlinked


def _record(path, data):
    raw = json.dumps(data, ensure_ascii=True, sort_keys=True, allow_nan=False).encode('utf-8')
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError('Werewolf generation recovery exceeds its bound.')
    pending = _unlinked(path.with_suffix('.pending'))
    with pending.open('wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(pending), str(path))


def prepare(backend, sim):
    form_bank.assert_idle(backend, sim)
    tracker = sim.occult_tracker
    mapping = getattr(tracker, '_sim_info_map', None)
    kind = backend._occult_by_name('WEREWOLF')
    generator = getattr(tracker, '_generate_sim_info', None)
    if (kind is None or not backend._has_occult(tracker, kind) or not isinstance(mapping, dict)
            or kind not in mapping or not callable(generator)):
        raise ValueError('An existing native Werewolf owner and exact generator are required.')
    inspect.signature(generator).bind(kind, generate_new=True)
    original_map = dict(mapping)
    owners = []
    for owner in list(original_map.values()) + [sim]:
        if not any(owner is row[0] for row in owners):
            owners.append((owner, appearance.packed(backend, owner)))
    flags = (backend._get_occult_flags(sim), backend._get_current_flags(sim))
    path = _unlinked(Path(backend._data_directory()) / 'werewolf_default_generation.json')
    if path.exists():
        if path.stat().st_size > 32 * 1024 * 1024: raise ValueError('EA generation recovery receipt exceeds its bound.')
        prior = json.loads(path.read_text(encoding='utf-8'))
        if prior.get('stage') != 'restored':
            raise ValueError('Interrupted EA Werewolf generation retained; inspect its recovery first.')
    proof = {'schema': 1, 'stage': 'generating', 'sim_id': str(sim.id),
             'save_guid': str(backend.services.get_persistence_service().get_save_slot_proto_guid()),
             'owners': [{'form': next((int(k) for k, v in original_map.items() if v is owner), None),
                         'active': owner is sim, 'fields': fields} for owner, fields in owners]}
    _record(path, proof)
    result, failed = None, None
    try:
        generated = generator(kind, generate_new=True)
        if (tracker._sim_info_map is not mapping or generated is None
                or mapping.get(kind) is not generated or any(generated is owner for owner, _ in owners)):
            raise ValueError('EA generator did not return a distinct expected Werewolf owner.')
        result = appearance.packed(backend, generated)
        appearance.payload(result)
    except Exception as error:
        failed = error
    finally:
        if tracker._sim_info_map is not mapping:
            tracker._sim_info_map = mapping
        mapping.clear(); mapping.update(original_map)
        if backend._get_occult_flags(sim) != flags[0]: backend._set_flags(sim, 'occult_types', flags[0])
        if backend._get_current_flags(sim) != flags[1]: backend._set_flags(sim, 'current_occult_types', flags[1])
        for owner, fields in owners:
            current = appearance.packed(backend, owner)
            changed = {name: row for name, row in fields.items() if current.get(name) != row}
            if changed: backend._restore_siminfo_payload(owner, appearance.payload(changed))
        if ((backend._get_occult_flags(sim), backend._get_current_flags(sim)) != flags
                or any(appearance.packed(backend, owner) != fields for owner, fields in owners)
                or any(mapping.get(k) is not v for k, v in original_map.items()) or set(mapping) != set(original_map)):
            raise ValueError('EA generation rollback differs; retain its durable recovery receipt.')
        proof['stage'] = 'restored'; proof['accepted_preview'] = failed is None
        _record(path, proof)
    if failed is not None: raise failed
    return result
