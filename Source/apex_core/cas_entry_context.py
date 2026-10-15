"""Expose every verified existing hybrid membership to native household CAS.

The legacy trait-based availability calculation can advertise Fairy while the
active appearance is Alien. Native CAS must receive the selected kind AND
every other actual membership, rather than Apex removing those memberships
itself before the native room has opened.
This preparation changes only native availability, preserving every existing
appearance owner, trait and current kind. Every hybrid member has its own raw
CAS transaction before household projection, including unselected members.
"""
import hashlib
import json
import os
from pathlib import Path
import uuid
from . import form_appearance as appearance, native_occult_context as context
from .occult_add_guard import publish
from .overlay_loader import _unlinked
from .hybrid_persistence import _export_memberships


def checkpoint_members(backend, selected, selected_checkpoint):
    """Checkpoint companions before any household availability projection.

    Preflight the whole scope first. A partial disk/checkpoint failure retains
    completed originals and prevents native CAS entry; it never replays them.
    Each member later uses the existing explicit observe/prepare/commit API,
    which restores that member's captured native availability as well as its
    independently decided appearance owners.
    """
    from . import cas_bank_transaction as bank
    from . import cas_ui
    if not isinstance(selected_checkpoint, dict) or selected_checkpoint.get('ok') is not True:
        raise ValueError('Selected CAS member has no acknowledged raw checkpoint.')
    household = backend.services.active_household()
    if household is None or household.id != selected.household_id:
        raise ValueError('CAS checkpoints require the exact loaded household.')
    members = list(household.sim_info_gen())
    if not 1 <= len(members) <= 8 or selected not in members or len({sim.id for sim in members}) != len(members):
        raise ValueError('CAS checkpoint roster is incomplete or ambiguous.')
    companions = []
    for sim in members:
        if backend._get_sim_info_by_id(str(sim.id)) is not sim or sim.household_id != household.id:
            raise ValueError('CAS checkpoint member is no longer the native manager owner.')
        forms = backend._form_map(sim.occult_tracker)
        if sim is not selected and isinstance(forms, dict) and len(forms) >= 3:
            if context.capture(backend, sim) is None:
                raise ValueError('CAS companion lacks complete distinct native owners.')
            bank.assert_idle(backend, sim)
            companions.append(sim)
    rows = [{'sim_id': str(selected.id), 'form_checkpoint': selected_checkpoint}]
    for sim in companions:
        result = bank.begin(backend, sim)
        if not isinstance(result, dict) or result.get('ok') is not True:
            raise ValueError('Companion raw CAS checkpoint was not acknowledged; entry blocked.')
        # CAS disposes the Live producers. Capture each companion's actual
        # navigation identity here, alongside its raw form checkpoint, while
        # the manager/tracker/wrappers are still readable and before projection.
        owner = cas_ui.capture_original_owner(backend, sim)
        if owner.get('original_owner', {}).get('complete') is not True:
            raise ValueError('Companion original CAS navigation identity is incomplete; entry blocked.')
        rows.append({'sim_id': str(sim.id), 'form_checkpoint': result, 'owner_observation': owner})
    return {'ok': True, 'household_id': str(household.id),
            'roster_sim_ids': [str(sim.id) for sim in members], 'members': rows,
            'native_appearance_written': False, 'native_availability_written': False,
            'return_requires_independent_member_decisions': True}


def prepare(backend, selected, full_household):
    if type(full_household) is not bool:
        raise ValueError('CAS entry requires a typed household scope.')
    household = backend.services.active_household()
    if household is None or household.id != selected.household_id:
        raise ValueError('CAS entry requires the exact loaded existing household.')
    members = list(household.sim_info_gen()) if full_household else [selected]
    if not 1 <= len(members) <= 8 or selected not in members or len({sim.id for sim in members}) != len(members):
        raise ValueError('CAS household inventory is incomplete or ambiguous.')
    rows = []
    for sim in members:
        if backend._get_sim_info_by_id(str(sim.id)) is not sim or sim.household_id != household.id:
            raise ValueError('CAS household member is no longer the exact native manager owner.')
        tracker = sim.occult_tracker
        forms = backend._form_map(tracker)
        current = backend._get_current_flags(sim)
        # Ordinary single-form Sims keep native behavior.
        if not isinstance(forms, dict) or len(forms) < 3:
            continue
        if current not in (1, 2, 4, 8, 16, 32, 64) or current not in forms or 1 not in forms:
            raise ValueError('CAS pair requires existing Human and selected native appearance owners.')
        if current != 1 and not tracker.has_occult_type(backend._coerce_flags(current)):
            raise ValueError('CAS selected kind has no actual occult membership.')
        before = context.capture(backend, sim)
        if before is None:
            raise ValueError('CAS pair preparation requires complete distinct native base owners.')
        owners = dict(forms, active=sim)
        packed = {str(kind): appearance.packed(backend, owner) for kind, owner in owners.items()}
        traits = backend._disk_trait_snapshot(sim)
        available = _export_memberships(tracker, before['active']['available'] | current | 1)
        # Actual membership and appearance storage are separate authorities.
        # Never generate a missing owner just to advertise it to native CAS.
        missing = [int(kind) for kind in tracker.OCCULT_DATA
                   if available & int(kind) and int(kind) not in forms]
        if missing:
            raise ValueError('CAS membership has no captured native appearance owner; entry blocked.')
        rows.append((sim, forms, dict(forms), owners, before, packed, traits, available))
    if not rows:
        return {'ok': True, 'prepared_members': [], 'native_availability_written': False}
    path = _unlinked(Path(backend._data_directory()) / 'household_cas_entry.json')
    if path.exists():
        raw = path.read_bytes()
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError('Prior CAS preparation exceeds its recovery bound.')
        previous = json.loads(raw.decode('utf-8'))
        if previous.get('stage') not in ('verified',):
            raise ValueError('A prior CAS pair preparation is unresolved; no replay authorized.')
        archive = _unlinked(path.with_name('household_cas_entry.' + hashlib.sha256(raw).hexdigest() + '.json'))
        if archive.exists():
            if archive.read_bytes() != raw:
                raise ValueError('CAS preparation archive differs from its exact preimage.')
        else:
            with archive.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    proof = {'schema': 1, 'id': uuid.uuid4().hex, 'stage': 'intent', 'runtime_pid': os.getpid(),
             'household_id': str(household.id), 'selected_sim_id': str(selected.id),
             'save_guid': str(backend.services.get_persistence_service().get_save_slot_proto_guid()),
             'members': [{'sim_id': str(sim.id), 'before_context': before,
                          'original_appearances': packed, 'original_traits': traits,
                          'requested_available': pair, 'write_attempted': False}
                         for sim, forms, identities, owners, before, packed, traits, pair in rows],
             'current_kind_written': False, 'trait_written': False, 'appearance_written': False,
             'forms_created': False, 'save_written': False, 'crash_fix_verified': False}
    publish(path, proof)  # Every complete preimage precedes all native setters.
    try:
        for row, held in zip(proof['members'], rows):
            sim, forms, identities, owners, before, packed, traits, pair = held
            if before['active']['available'] != pair:
                row['write_attempted'] = True; proof['stage'] = 'native-write-intent'; publish(path, proof)
                backend._set_flags(sim, 'occult_types', pair)
            after = context.read(backend, sim)
            if (sim.occult_tracker._sim_info_map is not forms or set(forms) != set(identities) or
                    any(forms[kind] is not owner for kind, owner in identities.items()) or set(after) != set(before) or
                    any(after[kind]['current'] != before[kind]['current'] for kind in before)):
                raise ValueError('CAS pair preparation changed native owner identities or current kind.')
            available = after['active']['available']
            # Native Vampire/Witch normalization may omit the Human bit.
            # Every verified non-Human membership must survive the setter.
            # A pair-only normalization must stop entry, never silently pass.
            current = before['active']['current']
            if (available & current != current or available & ~pair or
                    available & ~1 != pair & ~1 or
                    any(value['available'] != available for value in after.values())):
                raise ValueError('Native CAS availability did not retain every verified existing membership.')
            if backend._disk_trait_snapshot(sim) != traits:
                raise ValueError('CAS pair preparation changed occult/gameplay traits.')
            if any(appearance.fingerprint(appearance.packed(backend, owner)) != appearance.fingerprint(packed[str(kind)])
                   for kind, owner in owners.items()):
                raise ValueError('CAS pair preparation changed a native appearance; originals retained.')
            row.update(after_context=after, verified=True); proof['stage'] = 'verifying'; publish(path, proof)
        proof['stage'] = 'verified'; publish(path, proof)
    except Exception as error:
        proof.update(stage='unresolved', error=str(error)[:2048], retry_safe=False); publish(path, proof)
        raise
    return {'ok': True, 'prepared_members': [{'sim_id': row['sim_id'], 'available': row['after_context']['active']['available'],
                                            'current': row['after_context']['active']['current']} for row in proof['members']],
            'native_availability_written': any(row['write_attempted'] for row in proof['members']),
            'all_appearances_and_traits_unchanged': True, 'recovery_id': proof['id'], 'crash_fix_verified': False,
            'complete_existing_membership_required': True}
