"""Authorized 1.13.7 persistence port with exception/unknown-data protection.

Retain the recognized-form load/save algorithm. Missing tuning never authorizes
deleting serialized forms. A current tuned Witch wrapper also receives its
omitted native core/outfit record. Pelt/custom texture are outside that record's
schema; historical banks never authorize this path. No hooks register on import.
"""
import hashlib
import sys
import threading


_SERIALIZERS = threading.local()
_WITCH = 16
_CORE_FIELDS = ('physique', 'facial_attributes', 'voice_pitch', 'voice_actor',
                'voice_effect', 'skin_tone', 'skin_tone_val_shift', 'genetic_data')


def _native_base_wrapper():
    from sims.sim_info_base_wrapper import SimInfoBaseWrapper
    return SimInfoBaseWrapper


def _tattoo_mapping(value):
    # Inspected native getter: body-type -> uint64 texture. No tuple/list or
    # alternate layout is inferred from a protobuf field with a similar name.
    if (not isinstance(value, dict) or len(value) > 1024 or
            any(type(key) is not int or not 0 <= key < 2 ** 32 or
                type(texture) is not int or not 0 <= texture < 2 ** 64
                for key, texture in value.items())):
        raise ValueError('Native custom tattoo mapping contract differs.')
    return value


def _tattoo_field(record):
    field = record.DESCRIPTOR.fields_by_name.get('parts_custom_tattoos')
    if field is None:
        return None
    message = getattr(field, 'message_type', None)
    fields = getattr(message, 'fields_by_name', {})
    body, texture = fields.get('body_type'), fields.get('texture_id')
    if (field.number != 23 or field.label != 3 or field.type != 11 or body is None or texture is None or
            (body.number, body.type, body.label) != (1, 13, 2) or
            (texture.number, texture.type, texture.label) != (2, 4, 2)):
        raise ValueError('Native custom tattoo protobuf schema differs.')
    return field


def _read_tattoos(record):
    if _tattoo_field(record) is None:
        return None
    values = {}
    rows = record.parts_custom_tattoos
    if len(rows) > 1024:
        raise ValueError('Native custom tattoos exceed their bound.')
    for row in rows:
        if not row.HasField('body_type') or not row.HasField('texture_id') or row.body_type in values:
            raise ValueError('Native custom tattoos are incomplete or ambiguous.')
        values[row.body_type] = row.texture_id
    return _tattoo_mapping(values)


def _write_tattoos(record, value):
    if _tattoo_field(record) is None:
        raise ValueError('Native custom tattoo field is unavailable.')
    values = _tattoo_mapping(value)
    _read_tattoos(record)
    originals = {}
    for row in record.parts_custom_tattoos:
        clone = type(row)(); clone.CopyFrom(row)
        originals[row.body_type] = clone
    # Copy matching rows first, so future/unknown row fields remain intact.
    order = [body for body in originals if body in values]
    order.extend(sorted(set(values) - set(originals)))
    del record.parts_custom_tattoos[:]
    for body in order:
        row = record.parts_custom_tattoos.add()
        if body in originals:
            row.CopyFrom(originals[body])
        row.body_type, row.texture_id = body, values[body]
    if _read_tattoos(record) != values:
        raise ValueError('Native custom tattoos failed exact protobuf readback.')


def _core_contract(record):
    expected = {'occult_type': (1, 13, 1), 'flags': (18, 13, 1),
                'physique': (11, 9, 1), 'facial_attributes': (12, 12, 1),
                'voice_pitch': (13, 2, 1), 'voice_actor': (14, 13, 1),
                'voice_effect': (15, 4, 1), 'skin_tone': (16, 4, 1),
                'skin_tone_val_shift': (22, 2, 1), 'genetic_data': (17, 11, 1),
                'outfits': (21, 11, 1)}
    fields = getattr(getattr(record, 'DESCRIPTOR', None), 'fields_by_name', {})
    if any(name not in fields or (fields[name].number, fields[name].type, fields[name].label) != contract
           for name, contract in expected.items()):
        raise ValueError('Native Witch appearance protobuf contract differs.')
    _tattoo_field(record)


def _record_payload(record, observed):
    from . import form_appearance as appearance
    expected = {}
    for name in _CORE_FIELDS:
        if record.HasField(name):
            value = getattr(record, name)
            if name == 'genetic_data':
                raw = value.SerializeToString()
                kind = observed.get(name, {}).get('kind')
                if kind not in ('bytes', 'protobuf'):
                    raise ValueError('Native stored genetic getter contract differs.')
                value = raw if kind == 'bytes' else ('protobuf', raw)
            expected[name] = appearance.encode(value)
    expected['__outfits__'] = appearance.encode(('protobuf', record.outfits.SerializeToString()))
    tattoos = _read_tattoos(record)
    if tattoos is not None:
        expected['parts_custom_tattoos'] = appearance.encode(tattoos)
    return expected


def _stored_core(backend, owner, record):
    from . import form_appearance as appearance
    observed = appearance.packed(backend, owner)
    expected = _record_payload(record, observed)
    actual = {name: observed.get(name) for name in expected}
    genetics_projection = None
    if 'genetic_data' in expected:
        # A native C++ getter may emit known protobuf fields in a different
        # wire order. Compare through the exact incoming message descriptor;
        # preserve presence, repeated order and every unknown field. This is
        # a read-only representation projection, never a field-drop filter.
        raw = appearance.decode(actual['genetic_data'])
        if isinstance(raw, tuple) and raw[0] == 'protobuf':
            raw = raw[1]
        if not isinstance(raw, bytes) or len(raw) > 8 * 1024 * 1024:
            raise ValueError('Native stored genetics is not bounded protobuf wire data.')
        parsed = type(record.genetic_data)()
        parsed.ParseFromString(raw)
        canonical = parsed.SerializeToString()
        wanted = record.genetic_data.SerializeToString()
        genetics_projection = {'native_sha256': hashlib.sha256(raw).hexdigest(),
            'native_bytes': len(raw), 'expected_sha256': hashlib.sha256(wanted).hexdigest(),
            'expected_bytes': len(wanted), 'canonical_sha256': hashlib.sha256(canonical).hexdigest(),
            'complete_message_equal': canonical == wanted, 'native_wire_equal': raw == wanted}
        from .genetics_snapshot import normalize as normalize_genetics
        genetics_projection['native_growth_projection_equal'] = normalize_genetics(canonical) == normalize_genetics(wanted)
        kind = actual['genetic_data']['kind']
        actual['genetic_data'] = appearance.encode(canonical if kind == 'bytes' else ('protobuf', canonical))
    if (any(value is None for value in actual.values()) or
            appearance.fingerprint(actual) != appearance.fingerprint(expected) or
            owner.flags != record.flags):
        changed = sorted(name for name in expected if actual[name] != expected[name])
        failure = ValueError('Stored native Witch core/outfits failed exact readback: '
                             + ', '.join(changed + (['flags'] if owner.flags != record.flags else [])))
        failure.appearance_diagnostics = {'changed_fields': changed,
            'expected_flags': record.flags, 'actual_flags': owner.flags,
            'expected_fingerprint': appearance.fingerprint(expected),
            'actual_fingerprint': appearance.fingerprint({k: v for k, v in actual.items() if v is not None})}
        if genetics_projection is not None:
            failure.appearance_diagnostics['genetics_projection'] = genetics_projection
            if genetics_projection['native_bytes'] <= 256 * 1024 and genetics_projection['expected_bytes'] <= 256 * 1024:
                failure.appearance_diagnostics['genetics_expected'] = expected['genetic_data']
                failure.appearance_diagnostics['genetics_observed'] = observed['genetic_data']
        raise failure
    return genetics_projection


def _append_witch(tracker, data, captured, active, map_before, tuning_before):
    if _WITCH not in captured or tuning_before is None:
        return
    owner, fields = captured[_WITCH]
    if (tracker.sim_info is not active[0] or tracker._sim_info is not active[0] or
            tracker._sim_info_map is not map_before or map_before.get(_WITCH) is not owner or
            tracker.OCCULT_DATA.get(_WITCH) is not tuning_before or owner is active[0]):
        raise ValueError('Native Witch owner changed during serialization.')
    record = data.occult_sim_infos.add()
    cached = getattr(tracker, '_apex_native_witch_record', None)
    if isinstance(cached, tuple) and len(cached) == 2 and cached[0] is owner:
        record.CopyFrom(cached[1])
    _core_contract(record)
    record.occult_type = _WITCH
    # Match the inspected native construction direction: proto <- wrapper.
    _native_base_wrapper().copy_physical_attributes(record, owner)
    _record_appearance(record, fields)
    if record.occult_type != _WITCH or record.flags != owner.flags:
        raise ValueError('Native Witch record identity/flags failed readback.')


def _load_witch(tracker, record, base_wrapper, sim_before, map_before, tuning_before):
    if record is None or tuning_before is None:
        return
    from . import form_appearance as appearance
    from .outfit_snapshot import normalize
    _core_contract(record)
    if record.occult_type != _WITCH or not record.HasField('outfits'):
        raise ValueError('Saved native Witch identity/outfits are unavailable.')
    outfits = record.outfits.SerializeToString()
    if not outfits:
        raise ValueError('Saved native Witch outfits are empty.')
    normalize(outfits)
    for name in _CORE_FIELDS:
        if record.HasField(name):
            appearance.encode(getattr(record, name))
    tattoos = _read_tattoos(record)
    backend = _appearance_backend()
    if backend is None:
        raise ValueError('Native Witch readback backend is unavailable.')
    if (tracker.sim_info is not sim_before or tracker._sim_info is not sim_before or
            tracker._sim_info_map is not map_before or tracker.OCCULT_DATA.get(_WITCH) is not tuning_before):
        raise ValueError('Native Witch load ownership changed.')
    owner = map_before.get(_WITCH)
    created = owner is None
    if created:
        owner = tracker._generate_sim_info(_WITCH, generate_new=False)
    if (owner is None or map_before.get(_WITCH) is not owner or owner is sim_before or
            getattr(owner, '_base', owner) is getattr(sim_before, '_base', sim_before)):
        raise ValueError('Native Witch stored wrapper identity is unavailable or aliases the active Sim.')
    before = appearance.packed(backend, owner)
    active = appearance.packed(backend, sim_before)
    owner_flags, active_flags = owner.flags, sim_before.flags
    try:
        # Read the immutable incoming clone after native load. The native
        # active branch writes proto <- main Sim; it cannot serve as our stored
        # Witch source, and the main Sim remains its separately loaded owner.
        owner.load_outfits(record.outfits)
        # The native outfit rebuild may regenerate genetics/physical fields.
        # Apply the immutable physical source AFTER that rebuild, exactly as
        # the appearance restorer does; retain the final exact readback gate.
        base_wrapper.copy_physical_attributes(owner._base, record)
        if record.HasField('genetic_data'):
            # Installed copy_genetic_data uses MergeFromString when the
            # destination is a message. That retains stale repeated/unknown
            # entries. Replace the complete immutable wire value instead.
            genetics = record.genetic_data.SerializeToString()
            target = owner.genetic_data
            if callable(getattr(target, 'ParseFromString', None)):
                target.ParseFromString(genetics)
            elif callable(getattr(target, 'Clear', None)) and callable(getattr(target, 'MergeFromString', None)):
                target.Clear()
                target.MergeFromString(genetics)
            elif isinstance(target, bytes):
                owner.genetic_data = genetics
            else:
                raise ValueError('Stored Witch genetics lacks the exact replacement contract.')
        if tattoos is not None:
            owner.parts_custom_tattoos = dict(tattoos)
        if (tracker._sim_info_map is not map_before or map_before.get(_WITCH) is not owner or
                tracker.sim_info is not sim_before or tracker._sim_info is not sim_before or
                tracker.OCCULT_DATA.get(_WITCH) is not tuning_before):
            raise ValueError('Native Witch stored owner changed during load readback.')
        tracker._apex_native_witch_genetics_projection = _stored_core(backend, owner, record)
        if (appearance.fingerprint(appearance.packed(backend, sim_before)) != appearance.fingerprint(active) or
                sim_before.flags != active_flags):
            raise ValueError('Stored Witch load changed the canonical active Sim.')
        tracker._apex_native_witch_record = (owner, record)
    except Exception as error:
        diagnostic = {'phase': 'native-witch-load', 'error': str(error)[:2048],
                      'created_wrapper': created, 'rollback_verified': False}
        if hasattr(error, 'appearance_diagnostics'):
            diagnostic['readback'] = error.appearance_diagnostics
        try:
            if (tracker._sim_info_map is not map_before or map_before.get(_WITCH) is not owner or
                    tracker.sim_info is not sim_before or tracker._sim_info is not sim_before):
                raise ValueError('Native Witch rollback owner continuity is unavailable.')
            owner.flags, sim_before.flags = owner_flags, active_flags
            _restore_owners(backend, {_WITCH: (owner, before)}, (sim_before, active))
            diagnostic['rollback_verified'] = not created
            diagnostic['original_payloads_restored_verified'] = True
        except Exception as rollback_error:
            diagnostic['rollback_error'] = str(rollback_error)[:2048]
        tracker._apex_native_witch_appearance_failure = diagnostic
        # Retain the latest bounded failure even when EA removes the failed
        # Sim from its manager. Disposable snapshot reads may inspect it;
        # this does not make the failed Sim usable or authorize a Save.
        backend._apex_native_load_failure = {'sim_id': str(sim_before.id), 'diagnostic': diagnostic}
        raise


def install_shared_guard(tracker):
    """Avoid irreversible native hidden-clothing generation during save only.

    The current native helper copies physique/trait IDs and then generates
    merged hidden outfits. Preserve its trait copy, but let the captured exact
    appearance populate the serialization records without mutating its owners.
    All calls outside the exact tracker/thread serialization scope stay native.
    """
    cls = type(tracker)
    original = getattr(cls, '_copy_shared_attributes', None)
    if not callable(original):
        return False
    if getattr(original, '_apex_serialization_appearance_guard', False):
        return True
    copy_traits = getattr(cls, '_copy_trait_ids', None)
    if not callable(copy_traits):
        raise ValueError('Native shared-attribute trait-copy contract is unavailable.')
    def guarded(self, destination, destination_kind, source, source_kind):
        contexts = getattr(_SERIALIZERS, 'contexts', ())
        for owner, captured, active in reversed(contexts):
            if owner is not self:
                continue
            row = captured.get(int(destination_kind))
            if row is None or row[0] is not destination or active[0] is not source:
                raise ValueError('Native serialization shared-attribute owner differs; appearance not guessed.')
            copy_traits(destination, source)
            return None
        return original(self, destination, destination_kind, source, source_kind)
    guarded._apex_serialization_appearance_guard = True
    guarded._apex_original = original
    cls._copy_shared_attributes = guarded
    return True


def _appearance_backend():
    return sys.modules.get('td1_occult_hybrid_apex')


def _load_authority(tracker, captured, active):
    saved = getattr(tracker, '_apex_native_load_owners', None)
    if saved is None:
        return captured  # Owned fixtures or a tracker not loaded by this hook.
    forms, sim, expected = saved
    if (tracker._sim_info_map is not forms or tracker.sim_info is not sim or active[0] is not sim or
            set(expected) != set(captured) or any(expected[key][0] is not captured[key][0] for key in expected)):
        raise ValueError('Immutable native load appearance ownership changed.')
    return expected


def _remember_load_owners(tracker, records):
    backend, captured, active = _capture_owners(tracker)
    if backend is None or not captured:
        return
    expected = {key: (owner, dict(fields)) for key, (owner, fields) in captured.items()}
    for key, record in records.items():
        if key not in expected:
            continue  # Unknown/missing native owners are not reconstructed.
        _core_contract(record)
        if int(record.occult_type) != key or not record.HasField('outfits'):
            raise ValueError('Immutable native load record identity/outfits are missing.')
        expected[key][1].update(_record_payload(record, expected[key][1]))
    tracker._apex_native_load_owners = (tracker._sim_info_map, active[0], expected)


def install_transition_guard(tracker):
    """Retain fresh native hybrid appearances during native form transitions.

    This covers internal trait-load and deferred post-load calls as well as
    explicit selections. No bank is read and a missing target is never
    reconstructed. Native traits, outfit selection and gameplay still run.
    """
    cls = type(tracker)
    original = getattr(cls, '_switch_to_occult_type_internal', None)
    if not callable(original):
        return False
    if getattr(original, '_apex_native_transition_guard', False):
        return True

    def guarded(self, target):
        forms = getattr(self, '_sim_info_map', None)
        sim = getattr(self, '_sim_info', None)
        source = getattr(sim, 'current_occult_types', None)
        # Single native pairs and construction of absent forms stay native.
        if (not isinstance(forms, dict) or len(forms) < 3 or source not in forms or
                target not in forms or any(owner is sim for owner in forms.values())):
            return original(self, target)
        if _appearance_backend() is None:
            return original(self, target)
        backend, captured, active = _capture_owners(self)
        if backend is None or not captured:
            return original(self, target)
        identities = {kind: owner for kind, (owner, _fields) in captured.items()}
        wanted = {kind: (owner, dict(fields)) for kind, (owner, fields) in captured.items()}
        # A current Live edit is newer than the stored source. Same-form
        # initialization also retains the full current native appearance.
        loading = getattr(self, '_apex_native_load_pending', False) is True
        if loading:
            wanted = _load_authority(self, captured, active)
        else:
            wanted[int(source)] = (captured[int(source)][0], dict(active[1]))
        # Trait initialization may filter the current Live genetics before
        # the first simulation. That projection is not a user's newer edit
        # and must not replace the complete stored native load record.
        desired_active = (active[0], dict(active[1] if loading and int(source) == int(target)
                                         else wanted[int(target)][1]))
        if not install_shared_guard(self):
            raise ValueError('Hybrid native transition lacks its shared-attribute contract.')
        contexts = getattr(_SERIALIZERS, 'contexts', None)
        if contexts is None:
            contexts = _SERIALIZERS.contexts = []
        context = (self, captured, active)
        contexts.append(context)
        native_completed, ownership_verified = False, False
        try:
            result = original(self, target)  # Exactly one native invocation.
            native_completed = True
            if (self._sim_info_map is not forms or self.sim_info is not sim or self._sim_info is not sim or
                    set(forms) != set(identities) or any(forms[key] is not owner for key, owner in identities.items()) or
                    int(sim.current_occult_types) != int(target)):
                raise ValueError('Native hybrid transition changed ownership or did not reach its target.')
            ownership_verified = True
            _restore_owners(backend, wanted, desired_active)
            resend = getattr(backend, '_resend_all_visuals', None)
            if callable(resend):
                resend(sim)
            from . import form_appearance as appearance
            if (any(appearance.fingerprint(appearance.packed(backend, owner)) != appearance.fingerprint(fields)
                    for owner, fields in wanted.values()) or
                    appearance.fingerprint(appearance.packed(backend, sim)) != appearance.fingerprint(desired_active[1])):
                raise ValueError('Hybrid native transition failed complete final appearance readback.')
            self._apex_native_transition_retention = {
                'source': int(source), 'target': int(target), 'stored_owners': sorted(captured),
                'all_stored_and_active_verified': True, 'bank_read': False, 'save_file_written': False}
            return result
        except Exception as error:
            self._apex_native_transition_failure = {
                'source': int(source), 'target': int(target), 'error': str(error)[:2048],
                'original_stored': {str(kind): fields for kind, (_owner, fields) in captured.items()},
                'original_active': active[1],
                'appearance_authority': 'immutable-native-load-records' if loading else 'fresh-native-before-transition',
                'desired_stored': {str(kind): fields for kind, (_owner, fields) in wanted.items()},
                'deferred_until_native_ready': loading and native_completed and ownership_verified,
                'retry_safe': False, 'bank_read': False}
            if loading and native_completed and ownership_verified:
                # Native trait initialization can reject saved genetic parts
                # until gender/trait setup completes. Preserve the immutable
                # records for the later ready boundary; a failed appearance
                # readback here must not make EA discard the household Sim.
                # Never swallow an original native exception or owner change.
                return result
            raise
        finally:
            if not contexts or contexts[-1] is not context:
                raise ValueError('Native transition scope changed; no repeated native call authorized.')
            contexts.pop()

    guarded._apex_native_transition_guard = True
    guarded._apex_original = original
    cls._switch_to_occult_type_internal = guarded
    ready = getattr(cls, 'on_sim_ready_to_simulate', None)
    if callable(ready) and not getattr(ready, '_apex_native_load_voice_guard', False):
        def ready_guarded(self, *args, **kwargs):
            loading = (getattr(self, '_apex_native_load_pending', False) is True and
                       isinstance(getattr(self, '_sim_info_map', None), dict) and len(self._sim_info_map) >= 3)
            captured, backend, active = {}, None, None
            forms = getattr(self, '_sim_info_map', None)
            capture_error = None
            if loading:
                try:
                    backend, captured, active = _capture_owners(self)
                    captured = _load_authority(self, captured, active)
                    if any(owner is active[0] or getattr(owner, '_base', owner) is getattr(active[0], '_base', active[0])
                           for owner, _fields in captured.values()):
                        raise ValueError('Loaded native appearance owner is aliased.')
                except Exception as error:
                    capture_error = error
            try:
                result = ready(self, *args, **kwargs)
                if loading:
                    try:
                        if capture_error is not None:
                            raise capture_error
                        sim = self.sim_info
                        if (backend is None or sim is not active[0] or self._sim_info is not sim or
                                self._sim_info_map is not forms or set(forms) != set(captured) or
                                any(forms[key] is not owner for key, (owner, _fields) in captured.items()) or
                                int(sim.current_occult_types) not in captured):
                            raise ValueError('Loaded native appearance ownership changed.')
                        expected = captured[int(sim.current_occult_types)][1]
                        # Trait initialization can filter the current genetics
                        # and apply voice effects after the native load/switch.
                        # At completion use the complete loaded native owners,
                        # never a prior bank or that transient Live projection.
                        _restore_owners(backend, captured, (sim, expected))
                        resend = getattr(backend, '_resend_all_visuals', None)
                        if callable(resend):
                            resend(sim)
                        from . import form_appearance as appearance
                        if (any(appearance.fingerprint(appearance.packed(backend, owner)) != appearance.fingerprint(fields)
                                for owner, fields in captured.values()) or
                                appearance.fingerprint(appearance.packed(backend, sim)) != appearance.fingerprint(expected)):
                            raise ValueError('Loaded native appearance failed complete final readback.')
                        self._apex_native_load_appearance_retention = {'form_flags': int(sim.current_occult_types),
                            'stored_owners': sorted(captured), 'verified': True, 'bank_read': False}
                    except Exception as error:
                        # A retention failure must be observable without making
                        # EA discard an otherwise loaded Sim. Keep its original
                        # complete native data and report no retention success.
                        self._apex_native_load_appearance_failure = {'error': str(error)[:2048],
                            'original_stored': {str(kind): fields for kind, (_owner, fields) in captured.items()},
                            'verified': False, 'retry_safe': False, 'bank_read': False}
                return result
            finally:
                self._apex_native_load_pending = False
        ready_guarded._apex_native_load_voice_guard = True
        ready_guarded._apex_original = ready
        cls.on_sim_ready_to_simulate = ready_guarded
    return True


def _capture_owners(tracker):
    """Native save merges hidden clothing; capture separate owners first."""
    forms = getattr(tracker, '_sim_info_map', {})
    if not isinstance(forms, dict) or len(forms) > 64:
        raise ValueError('Native form ownership is unavailable before serialization.')
    if not forms:
        return None, {}, None
    backend = _appearance_backend()
    if backend is None:
        raise ValueError('Appearance preservation backend is unavailable; serialization not started.')
    from . import form_appearance as appearance
    captured = {int(kind): (owner, appearance.packed(backend, owner)) for kind, owner in forms.items()}
    active = (tracker.sim_info, appearance.packed(backend, tracker.sim_info))
    return backend, captured, active


def _record_appearance(record, fields):
    """Preserve declared appearance fields without replacing the whole proto."""
    from . import form_appearance as appearance
    descriptors = record.DESCRIPTOR.fields_by_name
    for name, row in fields.items():
        target_name = 'outfits' if name == '__outfits__' else name
        descriptor = descriptors.get(target_name)
        # Pelt/custom texture are absent from the inspected occult schema.
        if descriptor is None:
            continue
        value = appearance.decode(row)
        if value is None:
            continue  # A None getter does not authorize substituting native zero.
        if descriptor.label == 3:
            if name == 'parts_custom_tattoos':
                _write_tattoos(record, value)
            continue
        if descriptor.type in (11, 12):
            raw = value[1] if isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf' else value
            if not isinstance(raw, bytes):
                raise ValueError('Native appearance message/bytes field requires exact bytes.')
            if descriptor.type == 11:
                target = getattr(record, target_name)
                target.Clear()
                target.MergeFromString(raw)
                observed = target.SerializeToString()
            else:
                setattr(record, target_name, raw)
                observed = getattr(record, target_name)
            if observed != raw:
                raise ValueError('Native appearance message/bytes field failed exact byte readback.')
        else:
            setattr(record, target_name, value)
            if getattr(record, target_name) != value:
                raise ValueError('Native appearance scalar failed exact readback.')


class _AppearancePreservationError(ValueError):
    def __init__(self, diagnostics):
        self.appearance_diagnostics = diagnostics
        changed = ','.join(diagnostics[0].get('changed_fields', [])) if diagnostics else ''
        super().__init__('Native serialization changed an appearance owner; preservation readback failed.' +
                         (' Changed fields: ' + changed if changed else ''))


def _restore_owners(backend, captured, active):
    if backend is None:
        return
    from . import form_appearance as appearance
    failed = []
    rows = [(kind, owner, fields) for kind, (owner, fields) in captured.items()]
    rows.append((None, active[0], active[1]))
    for kind, owner, fields in rows:
        expected = appearance.fingerprint(fields)
        detail = {'role': 'active-live' if kind is None else 'stored-form', 'form_flags': kind,
                  'sim_id': str(getattr(owner, 'id', ''))[:20], 'expected': expected,
                  'restore_attempted': False}
        try:
            observed = appearance.evidence(backend, owner)
            detail['after_serialization'] = observed
        except Exception as error:
            observed = None
            detail['serialized_read_error'] = str(error)[:2048]
        if observed is None or observed['appearance_sha256'] != expected['appearance_sha256']:
            detail['restore_attempted'] = True
            try:
                backend._restore_siminfo_payload(owner, appearance.payload(fields))
            except Exception as error:
                detail['restore_error'] = str(error)[:2048]
        try:
            restored = appearance.evidence(backend, owner)
            detail['after_restoration'] = restored
            detail['changed_fields'] = [name for name in sorted(set(expected['field_sha256']) | set(restored['field_sha256']))
                                       if expected['field_sha256'].get(name) != restored['field_sha256'].get(name)]
            if 'restore_error' not in detail and restored['appearance_sha256'] == expected['appearance_sha256']:
                continue
        except Exception as error:
            detail['restored_read_error'] = str(error)[:2048]
        failed.append(detail)
        # An independently failed owner must not leave the remaining captured
        # owners/active appearance in the native serializer's mutated state.
    if failed:
        raise _AppearancePreservationError(failed)


def _known_mask(tracker):
    mask = 1
    for kind in tracker.OCCULT_DATA:
        mask |= int(kind)
    return mask


def _native_record_bytes(record):
    serializer = getattr(record, 'SerializeToString', None)
    if not callable(serializer):
        return None
    try:
        raw = serializer()
    except Exception as error:
        raise ValueError('Native occult record is incomplete or ambiguous; exact bytes unavailable.') from error
    if not isinstance(raw, bytes):
        raise ValueError('Native occult record serializer did not return exact bytes.')
    return raw


def _retain_record_failure(tracker, items, phase, duplicate, raw):
    """Keep independent complete sources; never select a conflicting owner."""
    retained = []
    retained_all = True
    for item in items:
        try:
            clone = type(item)()
            clone.CopyFrom(item)
            retained.append(clone)
        except Exception:
            retained_all = False
    tracker._apex_conflicting_occult_records = tuple(retained)
    tracker._apex_occult_record_failure = {
        'phase': phase, 'occult_type': duplicate['occult_type'],
        'first_index': duplicate['first_index'], 'duplicate_index': duplicate['duplicate_index'],
        'exact_duplicate_verified': False, 'conflict_resolved': False,
        'complete_sources_retained': retained_all and len(retained) == len(items),
        'records': [{'index': index, 'occult_type': int(item.occult_type),
                     'native_bytes': None if value is None else len(value),
                     'native_sha256': None if value is None else hashlib.sha256(value).hexdigest()}
                    for index, (item, value) in enumerate(zip(items, raw))]}


def _unique_native_records(tracker, items, phase):
    """Only byte-identical full protobufs share one native load/save owner.

    Appearance-field equality is insufficient: outfits, creator metadata and
    unknown fields can differ. Retain every conflicting source and fail before
    selecting a record or performing appearance writes.
    """
    items = list(items)
    raw = [_native_record_bytes(item) for item in items]
    unique, indices, duplicate_rows = {}, {}, []
    for index, item in enumerate(items):
        key = int(item.occult_type)
        if key in unique:
            row = {'occult_type': key, 'first_index': indices[key], 'duplicate_index': index}
            previous = raw[indices[key]]
            if previous is None or raw[index] is None or previous != raw[index]:
                _retain_record_failure(tracker, items, phase, row, raw)
                prefix = 'Duplicate saved' if phase == 'load' else 'Duplicate serialized'
                retained = ('complete sources retained' if
                            tracker._apex_occult_record_failure['complete_sources_retained'] else
                            'available record diagnostics retained')
                raise ValueError(prefix + ' occult identities differ or lack exact native bytes; '
                                 + retained + ', refusing ambiguous owner selection.')
            duplicate_rows.append(row)
        else:
            unique[key], indices[key] = item, index
    return unique, duplicate_rows


def _unique_data_view(tracker, data, phase):
    records, duplicates = _unique_native_records(tracker, data.occult_sim_infos, phase)
    if not duplicates:
        return data, records
    # Work on a complete clone rather than rewriting the incoming persistence
    # buffer. CopyFrom retains its top-level and nested unknown protobuf data.
    view = type(data)()
    view.CopyFrom(data)
    del view.occult_sim_infos[:]
    for item in records.values():
        view.occult_sim_infos.add().CopyFrom(item)
    observed, repeated = _unique_native_records(tracker, view.occult_sim_infos, phase)
    if (repeated or list(observed) != list(records) or
            any(_native_record_bytes(observed[key]) != _native_record_bytes(item)
                for key, item in records.items())):
        raise ValueError('Exact duplicate occult view failed native byte readback.')
    retained = []
    for item in data.occult_sim_infos:
        clone = type(item)()
        clone.CopyFrom(item)
        retained.append(clone)
    tracker._apex_identical_duplicate_occult_records = tuple(retained)
    tracker._apex_occult_duplicate_diagnostics = {
        'phase': phase, 'exact_duplicate_verified': True,
        'original_record_count': len(data.occult_sim_infos), 'unique_record_count': len(records),
        'duplicates': duplicates, 'incoming_buffer_rewritten': False,
        'complete_sources_retained': True}
    return view, observed


def _native_pair_first(tracker, data):
    """Keep the projected native CAS pair ahead of retained secondary owners.

    The observed CAS round trip replaced the second owner with its projected
    alternate, leaving our appended Spellcaster last and displacing Alien.
    Pair-first ordering is a candidate mitigation requiring runtime proof.
    This is an exact protobuf permutation, never an incoming conflict merge.
    A custom projection can omit the Human bit even while its actual Human
    owner is present. Preserve that mask verbatim; only use its single known
    nonhuman kind to select the two existing records. Unknown/composite
    projections and missing pair records are left untouched.
    """
    mask = int(data.occult_types)
    alternate = mask & ~1
    if alternate not in (2, 4, 8, 16, 32, 64):
        return data
    records, duplicates = _unique_native_records(tracker, data.occult_sim_infos, 'save-pair')
    if duplicates or 1 not in records or alternate not in records:
        return data
    order = [1, alternate] + [key for key in records if key not in (1, alternate)]
    if order == list(records):
        return data
    raw = {key: _native_record_bytes(item) for key, item in records.items()}
    if any(value is None for value in raw.values()):
        raise ValueError('Native CAS pair ordering requires exact complete owner protobuf bytes.')
    view = type(data)()
    view.CopyFrom(data)
    del view.occult_sim_infos[:]
    for key in order:
        view.occult_sim_infos.add().CopyFrom(records[key])
    observed, duplicates = _unique_native_records(tracker, view.occult_sim_infos, 'save-pair')
    if (duplicates or list(observed) != order or set(observed) != set(records)
            or any(_native_record_bytes(observed[key]) != raw[key] for key in records)):
        raise ValueError('Native CAS pair permutation failed exact record byte readback.')
    tracker._apex_native_pair_order = {'projected_mask': mask, 'alternate': alternate,
        'before_order': list(records), 'after_order': order,
        'record_bytes_unchanged': True, 'incoming_conflict_resolved': False}
    return view


def save_with_retention(original, tracker, occult_utils, *args, **kwargs):
    sim = tracker.sim_info
    membership, available = sim.occult_types, tracker._occult_form_available
    backend, captured, active = _capture_owners(tracker)
    map_before = getattr(tracker, '_sim_info_map', None)
    tuning_before = tracker.OCCULT_DATA.get(_WITCH)
    if captured:
        install_shared_guard(tracker)
    contexts = getattr(_SERIALIZERS, 'contexts', None)
    if contexts is None:
        contexts = _SERIALIZERS.contexts = []
    context = (tracker, captured, active)
    contexts.append(context)
    serializer_error = None
    try:
        unknown = int(membership) & ~_known_mask(tracker)
        sim.occult_types = int(occult_utils.get_occult_types_for_save(tracker)) | unknown
        occult_utils.recalc_occult_form_availability(tracker, saving=True)
        data, records = _unique_data_view(tracker, original(tracker, *args, **kwargs), 'save')
        present = set(records)
        if _WITCH in captured and tuning_before is not None:
            present.add(_WITCH)  # The fresh tuned owner will be serialized below.
        missing = [item for item in getattr(tracker, '_apex_unresolved_occult_records', ())
                   if int(item.occult_type) not in present]
        unresolved, _duplicates = _unique_native_records(tracker, missing, 'save-unresolved')
        for kind, (_owner, fields) in captured.items():
            record = records.get(kind)
            if record is not None:
                _record_appearance(record, fields)
        if _WITCH not in records:
            _append_witch(tracker, data, captured, active, map_before, tuning_before)
        present = {int(item.occult_type) for item in data.occult_sim_infos}
        # An already emitted current native owner remains authoritative over a
        # stale unresolved copy. Validate all missing retained owners together
        # before appending any, and advance the emitted identity set per append.
        for key, item in unresolved.items():
            if key not in present:
                data.occult_sim_infos.add().CopyFrom(item)
                present.add(key)
        data.occult_types = int(data.occult_types) | unknown
        return _native_pair_first(tracker, data)
    except Exception as error:
        serializer_error = error
        raise
    finally:
        if not contexts or contexts[-1] is not context:
            raise ValueError('Native serialization scope changed; no appearance restoration guessed.')
        contexts.pop()
        sim.occult_types = membership
        tracker._occult_form_available = available
        try:
            _restore_owners(backend, captured, active)
        except Exception as error:
            tracker._apex_serialization_appearance_failure = {
                'ok': False, 'serializer_error': None if serializer_error is None else str(serializer_error)[:2048],
                'appearance_retention_error': str(error)[:2048],
                'owners': getattr(error, 'appearance_diagnostics', [])}
            if serializer_error is None:
                raise
            # The original failure remains the propagated exception. Its
            # independent appearance rollback failure is retained on the owner.


def load_with_retention(original, tracker, data, occult_cache, occult_utils, occult_enum, base_wrapper):
    data, incoming = _unique_data_view(tracker, data, 'load')
    occult_cache.OccultDataCache.process_custom_occults()
    sim_before = tracker.sim_info
    map_before = getattr(tracker, '_sim_info_map', None)
    tuning_before = tracker.OCCULT_DATA.get(_WITCH)
    records, unresolved = {}, []
    known = {int(occult_enum.HUMAN)} | {int(kind) for kind in tracker.OCCULT_DATA}
    for key, item in incoming.items():
        # Native active-form loading mutates incoming records. Retain exact
        # independent sources, including unknown protobuf fields, beforehand.
        clone = type(item)()
        clone.CopyFrom(item)
        records[key] = clone
        if key not in known:
            unresolved.append(clone)
    tracker._apex_unresolved_occult_records = tuple(unresolved)
    tracker._sim_info.occult_types = data.occult_types or occult_enum.HUMAN
    tracker._sim_info.current_occult_types = data.current_occult_types or occult_enum.HUMAN
    tracker._pending_occult_type = data.pending_occult_type
    tracker._occult_form_available = data.occult_form_available
    for kind in occult_enum:
        if int(kind) == _WITCH:
            continue  # The original loader owns creation; restore after it.
        if kind != occult_enum.HUMAN and kind not in tracker.OCCULT_DATA:
            continue
        item = records.get(int(kind))
        if item is not None:
            form = tracker._generate_sim_info(item.occult_type, generate_new=False)
            if kind == tracker._sim_info.current_occult_types:
                base_wrapper.copy_physical_attributes(item, tracker._sim_info._base)
            else:
                form.load_outfits(item.outfits)
                base_wrapper.copy_physical_attributes(form._base, item)
        if kind != occult_enum.HUMAN and tracker.has_occult_type(kind) and kind == tracker._sim_info.current_occult_types:
            tracker._generate_sim_info(kind, generate_new=False)
    result = original(tracker, data)
    tracker._sim_info.occult_types = int(tracker._sim_info.occult_types) | (int(data.occult_types) & ~_known_mask(tracker))
    _load_witch(tracker, records.get(_WITCH), base_wrapper, sim_before, map_before, tuning_before)
    if install_transition_guard(tracker) and isinstance(tracker._sim_info_map, dict) and len(tracker._sim_info_map) >= 3:
        _remember_load_owners(tracker, records)
        tracker._apex_native_load_pending = True
    from .form_bank_seal import note_loaded
    note_loaded(tracker)
    return result
