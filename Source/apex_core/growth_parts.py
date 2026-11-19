"""Stage EA body-hair CAS parts without writing an existing appearance owner.

The inspected native appearance modifier calls set_caspart with distinct
source/destination bases. A staged result is accepted only when complete
genetics, including unknown bytes and both growth lists, match the source.
The preparation probe never applies to a real Sim. Transition repair uses one
native CASP transfer from an existing same-kind owner whose entire appearance
matches the desired source, with durable complete preimages and full readback.
Neither path softens the appearance comparison.
"""
import hashlib
import os
import uuid
from pathlib import Path
from . import form_appearance as appearance, genetics_snapshot as genetics


def missing_growth_parts(expected, observed):
    """Recognize deletion alone; different swatches are never duplicates."""
    expected = genetics.normalize(expected)
    observed = genetics.normalize(observed)
    if expected == observed:
        return []
    old, new = genetics._fields(expected), genetics._fields(observed)
    if (len([r for r in old if r[0] == 5]) != 1 or
            len([r for r in new if r[0] == 5]) != 1 or
            [r[3] for r in old if r[0] != 5] != [r[3] for r in new if r[0] != 5]):
        raise ValueError('Genetics changed outside its current parts list.')
    a = next(r for r in old if r[0] == 5)
    b = next(r for r in new if r[0] == 5)
    if a[1] != 2 or b[1] != 2:
        raise ValueError('Native genetics parts-list wire contract differs.')
    old_rows, new_rows = genetics._parts(a[2]), genetics._parts(b[2])
    remaining = list(new_rows)
    missing = []
    for row in old_rows:
        if remaining and row == remaining[0]:
            remaining.pop(0)
            continue
        n, wire, raw, chunk = row
        if n != 1 or wire != 2:
            raise ValueError('Genetics lost unknown container data.')
        values = {n: v for n, w, v, c in genetics._fields(raw) if n in (1, 2) and w == 0}
        if values.get(2) not in (78, 79, 80, 81):
            raise ValueError('Genetics deletion is not an inspected body-hair part.')
        missing.append(dict(part_id=values[1], body_type=values[2], raw_sha256=hashlib.sha256(raw).hexdigest()))
    if remaining or not 1 <= len(missing) <= 4 or len({r['body_type'] for r in missing}) != len(missing):
        raise ValueError('Genetics parts changed, reordered or have ambiguous body-hair owners.')
    return missing


def raw_genetics(owner):
    raw = owner.genetic_data
    if callable(getattr(raw, 'SerializeToString', None)):
        raw = raw.SerializeToString()
    if not isinstance(raw, bytes) or len(raw) > 8 * 1024 * 1024:
        raise ValueError('Bounded complete native genetics required.')
    return raw


def _restore_outfits(owner, fields):
    value = appearance.decode(fields['__outfits__'])
    if not isinstance(value, tuple) or len(value) != 2 or value[0] != 'protobuf':
        raise ValueError('Complete native outfit protobuf required for CASP side-effect repair.')
    # Use the inspected native blob setter, without a genetics assignment or
    # the Live mixin's additional outfit reconstruction. Keep every category,
    # color/layer, CC resource and unknown byte in the original message.
    owner._base.outfits = value[1]


def _detached(backend, sim, owner, fields):
    from sims.sim_info_base_wrapper import SimInfoBaseWrapper
    values = appearance.payload(fields)
    staged = SimInfoBaseWrapper(**{name: getattr(sim, name) for name in (
        'gender', 'age', 'species', 'first_name', 'last_name', 'breed_name', 'full_name_key', 'breed_name_key')})
    if any(staged._base is o._base for o in [sim] + list(backend._form_map(sim.occult_tracker).values())):
        raise ValueError('Detached native staging base aliases a real owner.')
    staged._base.current_occult_types = owner._base.current_occult_types
    staged._base.occult_types = owner._base.occult_types
    staged._base.base_trait_ids = list(owner._base.base_trait_ids)
    values['flags'] = owner.flags
    backend._restore_siminfo_payload(staged, values)
    return staged


def _stage(backend, sim, owner, fields, proof, path):
    from .occult_add_guard import publish
    from cas.cas import set_caspart, get_caspart_bodytype
    expected = appearance.decode(fields['genetic_data'])
    if isinstance(expected, tuple):expected = expected[1]
    # EA's existing stored target still owns the complete native genetics and
    # growth context after the active setter rejects its body-hair projection.
    # Prefer that exact same-kind source, not a different occult or old bank.
    kind = int(owner._base.current_occult_types)
    stored = backend._form_map(sim.occult_tracker).get(backend._coerce_flags(kind))
    source = None
    for candidate in (owner, stored):
        if (candidate is not None and int(candidate._base.current_occult_types) == kind and
                genetics.normalize(raw_genetics(candidate)) == genetics.normalize(expected)):
            source = candidate
            break
    template = source if source is not None else owner
    proof['complete_native_source_id'] = None if source is None else str(source.id)
    staged = _detached(backend, sim, template, fields)
    missing = missing_growth_parts(expected, raw_genetics(staged))
    for row in missing:
        if get_caspart_bodytype(row['part_id']) != row['body_type']:
            raise ValueError('Native CASP body type differs from the complete source.')
        proof['native_calls'].append(dict(row, attempted=True))
        publish(path, proof)
        # EA copies source genetics per call. Carry the accumulated repaired
        # source into a distinct detached destination, rather than restarting
        # every slot from the rejected real owner or aliasing the native bases.
        destination = _detached(backend, sim, template, fields)
        if destination._base is staged._base:
            raise ValueError('Native cumulative CASP staging bases alias.')
        source_base = source._base if source is not None else staged._base
        if set_caspart(source_base, destination._base, row['part_id'], False, False, True, 0, True) is not True:
            raise ValueError('Native detached CASP preparation rejected the source part.')
        staged = destination
        if genetics.normalize(raw_genetics(staged)) == genetics.normalize(expected):break
    actual = raw_genetics(staged)
    proof.update(expected_genetics=appearance.encode(expected), staged_genetics=appearance.encode(actual),
                 prepared_genetics_verified=genetics.normalize(actual) == genetics.normalize(expected))
    if not proof['prepared_genetics_verified']:
        raise ValueError('Detached complete genetics still differ; no real Sim Apply attempted.')
    proof.update(stage='detached-outfit-restore-intent', staged_fields_before_outfit_restore=appearance.packed(backend,staged))
    publish(path,proof)
    _restore_outfits(staged,fields)
    proof.update(staged_fields=appearance.packed(backend,staged))
    proof['prepared_appearance_verified'] = appearance.fingerprint(proof['staged_fields']) == appearance.fingerprint(fields)
    if not proof['prepared_appearance_verified']:
        raise ValueError('Detached outfit restoration failed complete appearance readback; no real Sim Apply attempted.')
    return staged, missing


def prepare(backend, sim, request):
    from . import household_io, occult_add_guard, native_occult_context
    if not isinstance(request, dict) or set(request) != {'household_id', 'save_guid', 'form_flags'}:
        raise ValueError('Exact household/save and existing form required.')
    household_io.context(backend, request)
    flag = request['form_flags']
    if type(flag) is not int or flag not in (1, 2, 4, 8, 16, 32, 64) or sim is None or str(sim.household_id) != request['household_id']:
        raise ValueError('One existing native appearance owner required.')
    mapping = backend._form_map(sim.occult_tracker)
    owner = mapping.get(backend._coerce_flags(flag))
    if owner is None:
        raise ValueError('Stored native owner is absent; no form created.')
    original_map = dict(mapping)
    owners = [sim] + list(mapping.values())
    before = [(o, appearance.packed(backend, o), o.flags) for o in owners]
    context = native_occult_context.read(backend, sim)
    fields = appearance.packed(backend, owner)
    path = Path(backend._data_directory()) / ('growth-probe-' + uuid.uuid4().hex + '.json')
    proof = dict(schema=1, stage='preparing', runtime_pid=os.getpid(), sim_id=str(sim.id),
                 form_flags=flag, fields=fields, original_context=context, original_owners=[
                     dict(id=str(o.id), fields=f, flags=flags) for o, f, flags in before], native_calls=[])
    occult_add_guard.publish(path, proof)
    try:
        staged, missing = _stage(backend, sim, owner, fields, proof, path)
        proof.update(stage='verified', real_sim_apply_attempted=False)
        return dict(ok=True, prepared_genetics_verified=True, missing_parts=missing,
                    real_sim_apply_attempted=False, save_file_written=False, form_created=False,
                    probe_journal=str(path))
    except Exception as error:
        proof.update(stage='rejected', error=str(error)[:2048], real_sim_apply_attempted=False)
        raise
    finally:
        unchanged = (backend._form_map(sim.occult_tracker) is mapping and set(mapping) == set(original_map) and
                     all(mapping[k] is o for k, o in original_map.items()) and
                     native_occult_context.read(backend, sim) == context and
                     all(appearance.packed(backend, o) == f and o.flags == flags for o, f, flags in before))
        proof['all_real_owners_unchanged'] = unchanged
        occult_add_guard.publish(path, proof)
        if not unchanged:
            raise ValueError('Native staging changed an existing owner; complete preimages retained, no replay authorized.')


def restore(backend, sim, owner, fields):
    """Restore captured genetics only after exact detached native preparation.

The raw setter can also modify the preferred-growth projection. Eligibility
comes from the immutable desired appearance and a complete detached readback,
not from assuming the rejected owner's remaining genetics are authoritative.
"""
    expected = appearance.fingerprint(fields)
    actual = appearance.evidence(backend, owner)
    changed = [name for name, value in expected['field_sha256'].items() if actual['field_sha256'].get(name) != value]
    diagnostic = dict(changed_fields=changed, status='inspecting', native_override_attempted=False)
    cache = getattr(backend, '_APEX_GROWTH_RESTORE_DIAGNOSTICS', None)
    if not isinstance(cache, dict):cache = {}; backend._APEX_GROWTH_RESTORE_DIAGNOSTICS = cache
    key = str(owner.id)
    if len(cache) >= 64 and key not in cache:cache.clear()
    if changed:cache.setdefault(key, []).append(diagnostic);cache[key] = cache[key][-8:]
    if changed != ['genetic_data']:
        diagnostic['status'] = 'declined-other-fields'
        return False
    from . import occult_add_guard, native_occult_context
    from cas.cas import set_caspart
    mapping = backend._form_map(sim.occult_tracker)
    original_map = dict(mapping)
    before = [(o, appearance.packed(backend, o), o.flags) for o in [sim] + list(mapping.values())]
    context = native_occult_context.read(backend, sim)
    path = Path(backend._data_directory()) / ('growth-restore-' + uuid.uuid4().hex + '.json')
    proof = dict(schema=1, stage='preparing', runtime_pid=os.getpid(), sim_id=str(sim.id), owner_id=str(owner.id),
                 expected_fields=fields, original_context=context, original_owners=[
                     dict(id=str(o.id), fields=f, flags=flags) for o, f, flags in before],
                 native_calls=[], real_sim_apply_attempted=False)
    occult_add_guard.publish(path, proof)
    try:
        staged, parts = _stage(backend, sim, owner, fields, proof, path)
        if (any(appearance.packed(backend, o) != f or o.flags != flags for o, f, flags in before) or
                native_occult_context.read(backend, sim) != context):
            raise ValueError('Detached preparation changed a real owner; no native override submitted.')
        # Detached CASP preparation copies the complete growth context. The
        # generic override API did not preserve it in either native trial.
        # Use the existing exact source directly, never the rejected owner or
        # a cached bank. A different outfit/voice/skin source cannot qualify.
        sources = [o for o in [sim] + list(mapping.values())
                   if str(o.id) == proof.get('complete_native_source_id')]
        if (len(sources) != 1 or sources[0] is owner or sources[0]._base is owner._base or
                int(sources[0]._base.current_occult_types) != int(owner._base.current_occult_types) or
                appearance.evidence(backend, sources[0]) != expected or not parts):
            raise ValueError('Complete distinct same-kind native CASP source is unavailable; no real Apply submitted.')
        source = sources[0]
        proof.update(stage='apply-intent', real_sim_apply_attempted=True, apply_method='set_caspart',
                     applied_part=parts[0])
        diagnostic.update(status='apply-intent', native_transfer_attempted=True, journal=str(path))
        occult_add_guard.publish(path, proof)
        if set_caspart(source._base, owner._base, parts[0]['part_id'], False, False, True, 0, True) is not True:
            proof['observed_fields'] = appearance.packed(backend, owner)
            raise ValueError('Native body-hair CASP transfer rejected; no replay authorized.')
        actual = appearance.evidence(backend,owner)
        changed = sorted(k for k,v in expected['field_sha256'].items() if actual['field_sha256'].get(k)!=v)
        if changed == ['__outfits__']:
            # Native CASP replaces the rendered part occupying its body type,
            # including CC eyelashes assigned to an arm-hair slot. Detached
            # full readback must prove the exact outfit setter preserves the
            # reconstructed genetics before this separate, one-shot write.
            if proof.get('prepared_appearance_verified') is not True:
                raise ValueError('Detached complete outfit-restoration proof is absent; no real outfit write.')
            proof.update(stage='outfit-restore-intent', fields_before_outfit_restore=appearance.packed(backend,owner))
            occult_add_guard.publish(path,proof)
            _restore_outfits(owner,fields)
        for name in ('resend_physical_attributes', 'resend_current_outfit', 'resend_outfits'):
            resend = getattr(owner, name, None)
            if callable(resend):
                resend()
        if appearance.evidence(backend, owner) != expected:
            proof['observed_fields'] = appearance.packed(backend, owner)
            raise ValueError('Native body-hair CASP transfer failed complete appearance readback; no replay authorized.')
        if (backend._form_map(sim.occult_tracker) is not mapping or set(mapping) != set(original_map) or
                any(mapping[k] is not o for k, o in original_map.items()) or
                native_occult_context.read(backend, sim) != context or
                any(o.flags != flags or o is not owner and appearance.packed(backend, o) != f for o, f, flags in before)):
            raise ValueError('Native body-hair CASP transfer changed another owner or context.')
        proof.update(stage='verified', all_unselected_owners_unchanged=True, missing_parts=parts)
        diagnostic['status'] = 'verified'
        return True
    except Exception as error:
        proof.update(stage='rejected', error=str(error)[:2048])
        try:
            proof['observed_owners'] = [dict(id=str(o.id),fields=appearance.packed(backend,o),flags=o.flags)
                                        for o, _, _ in before]
            proof['observed_context'] = native_occult_context.read(backend,sim)
        except Exception as observation_error:
            proof['observation_error'] = str(observation_error)[:2048]
        diagnostic.update(status='rejected', error=str(error)[:2048], journal=str(path))
        raise
    finally:
        occult_add_guard.publish(path, proof)
