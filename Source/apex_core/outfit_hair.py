"""Event-driven, opt-in hair ownership per form/category/outfit number.

The installed SimInfoBaseWrapper exposes an outfit-change CallableList. No
per-frame scan, CAS-client guessing, whole-Sim reload or global genetic edits.
"""
import copy
import functools
import threading
from . import form_appearance as appearance, form_bank
from .dresser_parts import read_rows, write_rows

_BACKEND = None
_BUSY = set()
_ERRORS = {}


def _message(backend, fields):
    raw = appearance.decode(fields['__outfits__'])[1]
    parser = getattr(backend, '_studio_parse_snapshot', None)
    if parser is not None: return parser(raw)
    message = backend._V8_Outfits_pb2.OutfitList()
    message.ParseFromString(raw)
    return message


def _types(backend):
    hair, _, reason = backend._v8_resolve_body_type('HAIR')
    if hair is None: raise ValueError('Hair BodyType unresolved: ' + reason)
    result = {hair}
    override, _, _ = backend._v8_resolve_body_type('HAIRCOLOR_OVERRIDE')
    if override is not None: result.add(override)
    return result


def _style_message(backend, fields):
    message = _message(backend, fields)
    descriptor = getattr(message, 'DESCRIPTOR', None)
    outfits = getattr(descriptor, 'fields_by_name', {}).get('outfits')
    native = getattr(outfits, 'message_type', None)
    flag = getattr(native, 'fields_by_name', {}).get('match_hair_style')
    if (getattr(native, 'full_name', None) != 'EA.Sims4.Persistence.OutfitData'
            or getattr(flag, 'number', None) != 9 or getattr(flag, 'type', None) != 8
            or getattr(flag, 'label', None) != 1):
        raise ValueError('Native OutfitData.match_hair_style boolean field 9 is unavailable.')
    for outfit in message.outfits:
        if getattr(outfit, 'DESCRIPTOR', None) is not native or type(getattr(outfit, 'match_hair_style', None)) is not bool:
            raise ValueError('Native outfit hair-match API is unavailable.')
    return message


def style_match_status(backend, fields):
    """Inspect the native per-outfit match flag without changing a Sim."""
    message = _style_message(backend, fields)
    return {'outfit_count': len(message.outfits),
            'matching_outfit_count': sum(outfit.match_hair_style for outfit in message.outfits)}


def independent_style_fields(backend, fields):
    """Plan native match-flag clearing, preserving the complete outfit message.

    Parts, exact uint64 colors, other flags and unknown protobuf fields remain
    owned by the existing native parser. This is pure preparation; native CAS
    propagation behavior requires a separate in-game probe.
    """
    message = _style_message(backend, fields)
    try:
        for outfit in message.outfits:
            outfit.match_hair_style = False
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError('Native outfit hair-match API cannot set its boolean flag: ' + str(error))
    desired = copy.deepcopy(fields)
    desired['__outfits__'] = appearance.encode(('protobuf', message.SerializeToString()))
    status = style_match_status(backend, desired)
    if status['matching_outfit_count'] or status['outfit_count'] != len(message.outfits):
        raise ValueError('Native outfit hair-match preparation failed serialized readback.')
    return desired


def capture(backend, fields):
    types, ordinals, result = _types(backend), {}, []
    for outfit in _message(backend, fields).outfits:
        category = int(outfit.category); ordinal = ordinals.get(category, 0)
        ordinals[category] = ordinal + 1
        result.append({'category': category, 'ordinal': ordinal, 'outfit_id': str(outfit.outfit_id),
            'hair': [{'index': i, 'row': row} for i, row in enumerate(read_rows(outfit)) if row['body_type'] in types]})
    return result


def _outfit_uid(value):
    if (not isinstance(value, str) or not value.isascii() or not value.isdecimal()
            or not 0 < int(value) < 1 << 64 or str(int(value)) != value):
        raise ValueError('Hair ownership requires an exact original native outfit UID.')
    return value


def _slot(category, ordinal):
    if (type(category) is not int or not 0 <= category < 1 << 32
            or type(ordinal) is not int or not 0 <= ordinal < 4096):
        raise ValueError('Hair target category/ordinal must be typed existing outfit identities.')
    return category, ordinal


def _held_index(held):
    if not isinstance(held, list) or len(held) > 4096:
        raise ValueError('Held hair wardrobe is unavailable or exceeds its bound.')
    originals = {}
    for item in held:
        if not isinstance(item, dict) or any(name not in item for name in ('category', 'ordinal', 'outfit_id', 'hair')):
            raise ValueError('Held hair wardrobe lacks a complete outfit identity.')
        key = _slot(item['category'], item['ordinal'])
        if key in originals:
            raise ValueError('Held hair wardrobe duplicates an outfit identity; no target guessed.')
        _outfit_uid(item['outfit_id'])
        if not isinstance(item['hair'], list) or len(item['hair']) > 4096:
            raise ValueError('Held native hair rows are unavailable or exceed their bound.')
        originals[key] = item
    return originals


def _preserved_targets(originals, preserve, lane):
    """Validate caller-owned intent, never classify native propagation as intent.

    Legacy single-slot records bind to their already held original UID. A
    multiple-target record must supply its independently established lane and
    original UIDs. Producing/durably capturing native edit intent is a separate,
    currently unsupported integration; post-CAS diffs cannot fill that role.
    """
    if preserve is None:
        return {}
    if isinstance(preserve, (tuple, list)) and len(preserve) == 2 and all(type(value) is int for value in preserve):
        key = _slot(*preserve)
        if key not in originals:
            raise ValueError('Explicit CAS hair target has no held original outfit; identity cannot be guessed.')
        return {key: originals[key]['outfit_id']}
    if (not isinstance(preserve, dict) or set(preserve) != {'schema', 'lane', 'targets'}
            or type(preserve.get('schema')) is not int or preserve['schema'] != 1
            or not isinstance(preserve.get('lane'), str) or not preserve['lane'].isascii()
            or not preserve['lane'].isdecimal() or not 0 < int(preserve['lane']) < 1 << 32
            or str(int(preserve['lane'])) != preserve['lane']
            or not isinstance(lane, str) or preserve['lane'] != lane
            or not isinstance(preserve.get('targets'), list) or not 0 < len(preserve['targets']) <= 4096):
        raise ValueError('Multiple CAS hair targets require a typed set bound to the exact selected occult lane.')
    targets = {}
    for item in preserve['targets']:
        if not isinstance(item, dict) or set(item) != {'category', 'ordinal', 'outfit_id'}:
            raise ValueError('Multiple CAS hair targets require category, ordinal and original native UID.')
        key = _slot(item['category'], item['ordinal'])
        uid = _outfit_uid(item['outfit_id'])
        if key in targets:
            raise ValueError('Multiple CAS hair targets duplicate a slot; intent must be explicitly deduplicated.')
        if key not in originals or originals[key]['outfit_id'] != uid:
            raise ValueError('CAS hair target differs from its held original outfit identity.')
        targets[key] = uid
    return targets


def reconcile(backend, fields, held, preserve=None, lane=None):
    """Restore held hair outside explicitly bound targets; retain full messages.

    A preserved target cannot bypass replacement/reorder detection. Planning is
    pure and accepts no target inferred from native propagated appearance diffs.
    """
    types, ordinals = _types(backend), {}
    originals = _held_index(held)
    targets = _preserved_targets(originals, preserve, lane)
    observed_targets = set()
    message = _message(backend, fields)
    for outfit in message.outfits:
        category = int(outfit.category); ordinal = ordinals.get(category, 0)
        ordinals[category] = ordinal + 1; key = (category, ordinal)
        original = originals.get(key)
        if original is None: continue
        # A replaced/reordered outfit needs explicit acceptance; its old hair
        # cannot truthfully be assigned just because the numeric index matches.
        if original['outfit_id'] != str(outfit.outfit_id):
            raise ValueError('Outfit identity changed; accept the new wardrobe before hair repair.')
        if key in targets:
            observed_targets.add(key)
            continue
        rows = read_rows(outfit)
        current = [{'index': i, 'row': row} for i, row in enumerate(rows) if row['body_type'] in types]
        if current == original['hair']: continue
        revised = [row for row in rows if row['body_type'] not in types]
        for item in original['hair']:
            revised.insert(min(item['index'], len(revised)), copy.deepcopy(item['row']))
        write_rows(outfit, revised)
    if set(targets) != observed_targets:
        raise ValueError('Explicit CAS hair target outfit disappeared; originals and returned state must be retained.')
    desired = copy.deepcopy(fields)
    desired['__outfits__'] = appearance.encode(('protobuf', message.SerializeToString()))
    return desired


def sync(backend, record, lane, fields):
    policy = record.get('hair_policy')
    if policy and policy.get('enabled'):
        policy['forms'][str(int(lane))] = capture(backend, fields)


def configure(backend, sim, enabled):
    form_bank.assert_idle(backend, sim)
    if enabled:
        # Explicitly enabling this option captures the whole current native
        # bank before any callback can treat held prior-runtime rows as current.
        form_bank.update(backend, sim, backend._get_current_flags(sim),
                         appearance.packed(backend, sim), create=True)
    path, key = form_bank.context(backend, sim); data = form_bank.load(path)
    record = data['records'].setdefault(key, {'bank': form_bank.capture(backend, sim), 'history': []})
    if enabled:
        fields = form_bank.capture(backend, sim)
        fields.update(record.get('bank', {}))
        fields[str(backend._get_current_flags(sim))] = appearance.packed(backend, sim)
        record['hair_policy'] = {'enabled': True, 'forms': {lane: capture(backend, stored) for lane, stored in fields.items()}}
    else:
        record.setdefault('hair_policy', {'forms': {}})['enabled'] = False
    if enabled: register(backend, sim)  # Prove the callback API before enabling persistently.
    form_bank.save(path, data)
    return status(backend, sim)


def status(backend, sim):
    path, key = form_bank.context(backend, sim)
    policy = form_bank.load(path)['records'].get(key, {}).get('hair_policy', {})
    return {'enabled': bool(policy.get('enabled')), 'form_count': len(policy.get('forms', {})),
            'outfit_count': sum(len(rows) for rows in policy.get('forms', {}).values()),
            'last_error': _ERRORS.get(key), 'typed_multiple_targets_supported': True,
            'automatic_cas_intent_classification_supported': False,
            'durable_native_cas_intent_capture_supported': False,
            'scope': 'Live repair retains exact serialized hair rows per form/category/number; native CAS propagation unverified. Explicit target intent required.'}


def cas_target(backend, sim, value=None):
    if not status(backend, sim)['enabled']: return None
    category, ordinal = sim.get_current_outfit() if value is None else value
    key = (int(category), int(ordinal))
    if key not in {(item['category'], item['ordinal']) for item in capture(backend, appearance.packed(backend, sim))}:
        raise ValueError('The selected CAS hair target outfit does not exist.')
    return list(key)


def accept_cas(backend, record, lane, chosen, target):
    policy = record.get('hair_policy', {})
    held = policy.get('forms', {}).get(str(lane))
    if policy.get('enabled'):
        if held is None:
            raise ValueError('Selected occult lane has no held hair wardrobe; native propagation cannot be classified as intent.')
        if target is None: raise ValueError('Choose an explicit CAS hair target before accepting propagated changes.')
        return reconcile(backend, chosen, held, preserve=target, lane=str(lane))
    return chosen


def enforce(backend, sim):
    path, key = form_bank.context(backend, sim)
    if key in _BUSY: return False
    try:
        form_bank.assert_idle(backend, sim)
    except ValueError as error:
        if len(_ERRORS) < 256 or key in _ERRORS: _ERRORS[key] = str(error)
        return False
    record = form_bank.load(path)['records'].get(key, {})
    policy = record.get('hair_policy', {})
    if not policy.get('enabled') or record.get('pending') or record.get('switch_pending'): return False
    if not form_bank.current_runtime_authorized(backend, sim, record):
        return False  # A prior-runtime held wardrobe cannot overwrite fresh native hair.
    held = policy.get('forms', {}).get(str(backend._get_current_flags(sim)))
    if held is None: return False
    from . import studio
    from .change_journal import fingerprint
    owner, before, journal, _ = studio._context(backend, sim.id)
    desired = reconcile(backend, studio._fields(before), held)
    after = studio._state_from_fields(backend, desired)
    if fingerprint(before) == fingerprint(after): return False
    if journal.data['pending']: return False  # Stale Apply will fail; never replace an accepted preview in flight.
    _BUSY.add(key)
    try:
        journal.observe(before, 'Before outfit hair isolation repair')
        token = journal.prepare('Keep independent outfit hairstyle and exact color', before, after)
        reply = studio.dispatch(backend, 'studio_apply', sim.id, token)
        if not reply.get('ok'): raise ValueError(reply.get('message', 'Hair repair not accepted'))
    finally: _BUSY.remove(key)
    _ERRORS.pop(key, None)
    return True


def _event(info, category_and_index, old_category_and_index):
    backend = _BACKEND
    if backend is None or threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT: return
    # An inactive SimInfoBaseWrapper can share the main Sim ID. Only the actual
    # live owner handles a Live outfit-change callback.
    if backend._get_sim_info_by_id(info.id) is not info: return
    try: enforce(backend, info)
    except Exception as error:
        _, key = form_bank.context(backend, info)
        if len(_ERRORS) < 256 or key in _ERRORS: _ERRORS[key] = str(error)
        backend._log('Outfit hair isolation retained state: ' + str(error))


def register(backend, sim):
    global _BACKEND
    _BACKEND = backend
    callbacks = sim.on_outfit_changed
    if _event not in callbacks: sim.register_for_outfit_changed_callback(_event)


def install(backend, wrapper_type=None):
    """Register opted-in loaded Sims on their first real outfit-change event."""
    global _BACKEND
    _BACKEND = backend
    if wrapper_type is None:
        from sims.sim_info_base_wrapper import SimInfoBaseWrapper
        wrapper_type = SimInfoBaseWrapper
    original = wrapper_type.set_current_outfit
    if getattr(original, '_apex_outfit_hair_hook', False): return
    @functools.wraps(original)
    def changed(info, *args, **kwargs):
        if threading.current_thread().ident == backend._APEX_GAME_THREAD_IDENT:
            try:
                if backend._get_sim_info_by_id(info.id) is info and status(backend, info)['enabled']:
                    register(backend, info); enforce(backend, info)
            except Exception as error:
                backend._log('Outfit hair registration retained state: ' + str(error))
        return original(info, *args, **kwargs)
    changed._apex_outfit_hair_hook = True
    wrapper_type.set_current_outfit = changed
