"""Retain exact native availability separately from appearance and traits.

The installed native constructor gives every stored wrapper its own current
kind and the primary Sim's availability mask. CAS can narrow that mask without
removing its stored wrappers or occult traits. Only a fresh receiver checkpoint
authorizes restoring the captured masks; existing forms are never generated.
"""


def _integer(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < int(value) < 1 << 32:
        raise ValueError('Native occult context is not a bounded positive integer.')
    return int(value)


def owners(backend, sim):
    forms = backend._form_map(sim.occult_tracker)
    if not isinstance(forms, dict) or not forms or len(forms) > 32:
        raise ValueError('Native occult context requires exact existing stored owners.')
    mapped = {str(int(kind)): owner for kind, owner in forms.items()}
    if len(mapped) != len(forms) or any(int(kind) <= 0 or int(kind) & (int(kind)-1) for kind in mapped):
        raise ValueError('Native occult context owner kinds are ambiguous.')
    rows = dict(mapped, active=sim)
    bases = {kind: getattr(owner, '_base', None) for kind, owner in rows.items()}
    if all(base is None for base in bases.values()):
        return None  # Pure synthetic appearance fixtures have no native bases.
    if any(base is None for base in bases.values()) or len({id(base) for base in bases.values()}) != len(bases):
        raise ValueError('Native occult context has missing or aliased base owners.')
    return bases


def read(backend, sim):
    bases = owners(backend, sim)
    if bases is None:
        return None
    return {kind: {'available': _integer(base.occult_types),
                   'current': _integer(base.current_occult_types)} for kind, base in bases.items()}


def validate(value):
    if (not isinstance(value, dict) or 'active' not in value or not 2 <= len(value) <= 33 or
            any(kind != 'active' and (not isinstance(kind, str) or not kind.isascii() or not kind.isdecimal() or
                str(int(kind)) != kind or not 0 < int(kind) < 1 << 32 or int(kind) & (int(kind)-1)) for kind in value)):
        raise ValueError('Captured native occult context has an invalid owner set.')
    for kind, row in value.items():
        if not isinstance(row, dict) or set(row) != {'available', 'current'}:
            raise ValueError('Captured native occult context is incomplete.')
        available, current = _integer(row['available']), _integer(row['current'])
        if current & (current-1) or kind != 'active' and current != int(kind):
            raise ValueError('Captured native occult context does not identify its actual stored kind.')
    active = value['active']
    # Availability is a native context, not a trait-membership union. A real
    # all-six hybrid can report 65 while retaining all seven stored owners.
    # Restore what the fresh native checkpoint actually reports; never invent
    # 127 from its stored owner keys or use an older bank to infer membership.
    if str(active['current']) not in value:
        raise ValueError('Captured active kind has no existing native owner.')
    if any(row['available'] != active['available'] for row in value.values()):
        raise ValueError('Captured native availability differs between existing owners.')
    return value


def capture(backend, sim):
    value = read(backend, sim)
    return None if value is None else validate(value)


def verify(checkpoint, observed, active_lane):
    """Verify captured availability with the explicitly returned active kind."""
    validate(checkpoint)
    validate(observed)
    expected = {kind: dict(row) for kind, row in checkpoint.items()}
    if not isinstance(active_lane, str) or active_lane not in expected or active_lane == 'active':
        raise ValueError('Native availability requires an explicit existing active owner.')
    expected['active']['current'] = int(active_lane)
    if observed != expected:
        raise ValueError('Native availability/current context differs from its captured owners and returned active kind.')
    return observed


def verify_receipt(checkpoint, receipt, active_lane):
    if (not isinstance(receipt, dict) or set(receipt) != {'verified', 'restored_owners', 'before', 'after',
            'current_kinds_unchanged', 'traits_modified', 'forms_created'} or
            receipt['verified'] is not True or receipt['current_kinds_unchanged'] is not True or
            receipt['traits_modified'] is not False or receipt['forms_created'] is not False):
        raise ValueError('Native availability restore receipt is incomplete.')
    after = verify(checkpoint, receipt['after'], active_lane)
    before = receipt['before']
    if not isinstance(before, dict) or set(before) != set(after):
        raise ValueError('Native availability before/after owner sets differ.')
    for kind, row in before.items():
        if (not isinstance(row, dict) or set(row) != {'available', 'current'} or
                _integer(row['available']) != row['available'] or
                _integer(row['current']) != after[kind]['current']):
            raise ValueError('Native availability receipt changed current kind or omitted its original context.')
    changed = sorted((kind for kind in before if before[kind]['available'] != after[kind]['available']),
                     key=lambda kind: (kind == 'active', 0 if kind == 'active' else int(kind)))
    if receipt['restored_owners'] != changed:
        raise ValueError('Native availability receipt does not identify its exact restored owners.')
    return receipt


def restore(backend, sim, checkpoint):
    """Restore only exact captured availability, never current kind or traits.

    Caller must already have durable native-write intent and the receiver's
    exact current-runtime identity. All owners are preflighted before setters.
    A partial/failed setter remains a failed native transaction, never retried.
    """
    validate(checkpoint)
    before = read(backend, sim)
    if before is None or set(before) != set(checkpoint):
        raise ValueError('Native occult context owner set changed; no availability restored.')
    for kind, row in before.items():
        if kind != 'active' and row['current'] != checkpoint[kind]['current']:
            raise ValueError('Native stored current kind changed; it cannot be repaired by availability restoration.')
    # The returned active kind is owned by the raw CAS return and explicit plan.
    # Availability restoration must preserve that observed current selection.
    if str(before['active']['current']) not in checkpoint:
        raise ValueError('Returned native active kind has no original owner.')
    bases = owners(backend, sim)
    written = []
    final_context = {kind: {'available': checkpoint[kind]['available'], 'current': before[kind]['current']}
                     for kind in before}
    for kind in sorted(bases, key=lambda kind: (kind == 'active', 0 if kind == 'active' else int(kind))):
        desired = checkpoint[kind]['available']
        if before[kind]['available'] != desired:
            bases[kind].occult_types = desired
            written.append(kind)
        observed = read(backend, sim)
        # Distinct native appearance buffers may share availability. Admit
        # only an exact complete captured-context readback, never a partial
        # propagation or any stored/active current-kind change.
        if observed == final_context:
            written = sorted((key for key in before if before[key]['available'] != observed[key]['available']),
                             key=lambda key: (key == 'active', 0 if key == 'active' else int(key)))
            break
        if (set(observed) != set(before) or any(observed[key]['current'] != before[key]['current'] for key in before) or
                any(observed[key]['available'] != (checkpoint[key]['available'] if key in written else before[key]['available'])
                    for key in before)):
            raise ValueError('Native availability setter changed another owner/current kind or failed exact readback.')
    after = read(backend, sim)
    if any(after[kind]['available'] != checkpoint[kind]['available'] for kind in checkpoint):
        raise ValueError('Native availability restoration failed complete final readback.')
    return {'verified': True, 'restored_owners': written, 'before': before, 'after': after,
            'current_kinds_unchanged': True, 'traits_modified': False, 'forms_created': False}


def appearance_write(backend, sim, owner, apply):
    """Use an existing owner's kind while native appearance setters filter parts.

    A Live switch can already have narrowed availability before CAS begins.
    Restoring that captured mask cannot admit another stored form's parts. The
    temporary mask uses this distinct owner's existing current kind when the
    preceding context excludes it; it is restored before complete appearance
    readback. No traits, current kind,
    stored appearance payloads are changed here. Native availability may be
    shared only when complete readback establishes that exact scope. The caller
    must retain its
    appearance transaction's durable native-write intent before invoking this.
    """
    before = read(backend, sim)
    if before is None:
        return apply()  # Synthetic fixtures have no native part filtering.
    validate(before)
    forms = backend._form_map(sim.occult_tracker)
    matches = [str(int(kind)) for kind, candidate in forms.items() if candidate is owner]
    if owner is sim:
        matches.append('active')
    if len(matches) != 1:
        raise ValueError('Appearance write requires one exact existing native owner.')
    selected = matches[0]
    base = owners(backend, sim)[selected]
    original = before[selected]['available']
    # The observed Vampire pair uses availability 4 for both native layers.
    # Human is an existing appearance owner, not an extra occult capability:
    # its native setter leaves 4 unchanged when offered 5. Earlier complete
    # Human reconciliation works under the original mask. Do not require an
    # invented Human bit before an ordinary Human appearance write.
    current = before[selected]['current']
    # Actual Mermaid admission of 4|8 succeeds, but assignment still filters
    # the tail. Test only this existing owner's kind when the preceding mask
    # excludes it. A context already containing its kind remains authoritative.
    # This does not alter trait membership or the current kind, and the exact
    # preceding context must read back before appearance completion can pass.
    temporary = original if current == 1 or original & current else current
    expected = {kind: dict(row) for kind, row in before.items()}
    expected[selected]['available'] = temporary
    shared = {kind: {'available': temporary, 'current': row['current']} for kind, row in before.items()}
    diagnostic = {'owner': selected, 'before': before, 'temporary_available': temporary,
                  'scope': None, 'payload_attempted': False, 'payload_completed': False,
                  'observations': [], 'verified': False}
    cache = getattr(backend, '_APEX_NATIVE_OCCULT_WRITE_DIAGNOSTICS', None)
    if not isinstance(cache, dict):
        cache = {}; backend._APEX_NATIVE_OCCULT_WRITE_DIAGNOSTICS = cache
    if len(cache) >= 64: cache.clear()
    cache[str(getattr(owner, 'id', selected))] = diagnostic
    def unchanged(value, stage):
        observed = read(backend, sim)
        diagnostic['observations'].append({'stage': stage, 'observed': observed})
        if observed != value:
            differences = [(kind, value.get(kind), observed.get(kind)) for kind in sorted(set(value) | set(observed))
                           if value.get(kind) != observed.get(kind)]
            raise ValueError('Appearance write changed native context on another owner or current kind; ' +
                             stage + ': ' + repr(differences))
    def apply_once():
        diagnostic['payload_attempted'] = True
        result = apply()
        diagnostic['payload_completed'] = True
        return result
    if temporary == original:
        diagnostic['scope'] = 'unchanged'
        result = apply_once()
        unchanged(before, 'payload')
        diagnostic['verified'] = True
        return result
    try:
        base.occult_types = temporary
        observed = read(backend, sim)
        diagnostic['observations'].append({'stage': 'admission', 'observed': observed})
        if observed == shared:
            expected = shared; diagnostic['scope'] = 'complete-shared-availability'
        else:
            diagnostic['scope'] = 'selected-owner'
        unchanged(expected, 'admission')
        result = apply_once()  # Once only; a failed payload is never replayed.
        unchanged(expected, 'payload')
    finally:
        base.occult_types = original
        unchanged(before, 'restore')
    diagnostic['verified'] = True
    return result
