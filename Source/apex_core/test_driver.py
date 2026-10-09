"""Typed real-game test operations, restricted to a marked disposable profile.

No arbitrary Python/console evaluation, no external UI input, no worker-thread
Sim access. Transition submission and completed gameplay proof are distinct.
"""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path

_IDENTITY = None
_LAST_CLIENT_ID = None


def runtime_identity(module_file):
    global _IDENTITY
    if _IDENTITY is not None:
        return dict(_IDENTITY)
    result = {'pid': os.getpid(), 'test_token': None, 'script_sha256': None}
    try:
        from .overlay_loader import sidecar_paths, _unlinked
        native, _manifest = sidecar_paths(module_file)
        archive = native.parent.parent / 'ApexOccultHybrid.ts4script'
        profile = archive.parent.parent.parent
        if profile.name != 'The Sims 4' or archive.parent.name != 'Apex' or archive.parent.parent.name != 'Mods':
            raise ValueError('Test bridge is not in the one supported disposable layout.')
        marker_path = _unlinked(profile / '.apex-disposable-profile.json')
        if marker_path.stat().st_size > 4096:
            raise ValueError('Oversize disposable marker.')
        marker = json.loads(marker_path.read_text(encoding='utf-8'))
        token = marker.get('token', '')
        if marker.get('disposable') is not True or len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
            raise ValueError('Invalid disposable identity.')
        result.update({'test_token': token, 'script_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'profile': str(profile)})
    except Exception as error:
        result['identity_error'] = str(error)
    _IDENTITY = dict(result)
    return result


def guard(backend, value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('A bounded typed test request is required.')
    payload = json.loads(value)
    identity = runtime_identity(backend.__file__)
    if not identity['test_token'] or payload.get('test_token') != identity['test_token']:
        raise ValueError('Real-game test controls require the exact disposable profile token.')
    # Recheck the disk marker each mutation: owner swaps invalidate the session.
    from .overlay_loader import _unlinked
    marker_path = _unlinked(Path(identity['profile']) / '.apex-disposable-profile.json')
    if marker_path.stat().st_size > 4096:
        raise ValueError('Oversize disposable marker.')
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    if marker.get('token') != identity['test_token'] or marker.get('disposable') is not True:
        raise ValueError('Disposable profile identity changed.')
    return payload.get('value')


def persistence_evidence(backend, sim, household):
    """Read current native save buffers; disk save/reload remains a separate gate."""
    checks = {}
    result = {'checks': checks, 'household_sim_ids': [],
              'persisted_household_sim_ids': [], 'errors': [],
              'persistence_verified_before_save': False, 'save_reload_verified': False}
    if sim is None or household is None:
        result['errors'].append('A selected Sim and active household are required.')
        return result
    try:
        result['household_sim_ids'] = [str(item.id) for item in household.sim_info_gen()]
        checks['active_household_membership'] = str(sim.id) in result['household_sim_ids']
        checks['runtime_household_identity'] = sim.household_id == household.id
        checks['manager_identity'] = backend.services.sim_info_manager().get(sim.id) is sim
        checks['account_save_eligible'] = sim.account_id is not None
        persistence = backend.services.get_persistence_service()
        native_sim = persistence.get_sim_proto_buff(sim.id)
        checks['sim_proto_exists'] = native_sim is not None
        checks['sim_proto_identity'] = native_sim is not None and native_sim.sim_id == sim.id
        checks['sim_proto_household_identity'] = native_sim is not None and native_sim.household_id == household.id
        native_household = persistence.get_household_proto_buff(household.id)
        checks['household_proto_exists'] = native_household is not None
        checks['household_proto_identity'] = native_household is not None and native_household.household_id == household.id
        if native_household is not None:
            result['persisted_household_sim_ids'] = [str(item) for item in native_household.sims.ids]
        checks['household_proto_membership'] = str(sim.id) in result['persisted_household_sim_ids']
        result['persistence_verified_before_save'] = all(checks.values())
    except Exception as error:
        # Never save or repair here: preserve evidence of the original state.
        result['errors'].append(str(error))
    return result


def snapshot(backend, sim, export_outfits=False, export_forms=False):
    persistence = backend.services.get_persistence_service()
    slot = persistence.get_save_slot_proto_buff()
    game_clock = backend.services.game_clock_service()
    household = backend.services.active_household()
    zone = backend.services.current_zone()
    result = {'ok': True, 'zone_id': str(zone.id), 'save_slot': int(slot.slot_id),
              'save_guid': str(persistence.get_save_slot_proto_guid()),
              'household_id': str(household.id) if household is not None else None,
              'clock_speed': int(game_clock.clock_speed),
              'in_build_buy': bool(zone.is_in_build_buy),
              'sim_time_source': 'services.time_service().sim_now',
              'game_time_source': 'services.game_clock_service().now()'}
    # The game clock can advance while the simulation timeline is frozen.
    # Keep both native observations, and never infer sim progress from it.
    result.update(client_id=None, zone_running=None, sim_now=None, sim_now_ticks=None,
                  game_now=None, game_now_ticks=None, runtime_queries={}, runtime_errors={})
    for field, query in (
            ('client_id', lambda: backend.services.client_manager().get_first_client()),
            ('zone_running', lambda: zone.is_zone_running)):
        try:
            native = query()
            if field == 'client_id':
                native = native.id if native is not None else None
            if native is None:
                result['runtime_queries'][field] = 'returned-null'
                continue
            if (field == 'zone_running' and type(native) is not bool) or (
                    field == 'client_id' and (type(native) is not int or not 1 <= native < 1 << 64)):
                raise ValueError('Native runtime value has an unexpected type or bound.')
            result[field] = native if field == 'zone_running' else str(native)
            result['runtime_queries'][field] = 'returned-value'
        except Exception as error:
            result['runtime_queries'][field] = 'failed'
            result['runtime_errors'][field] = str(error)

    def sim_timeline():
        service = backend.services.time_service()
        return service.sim_now if service is not None else None

    for field, query in (('sim_now', sim_timeline), ('game_now', lambda: game_clock.now())):
        ticks_field = field + '_ticks'
        try:
            native = query()
            if native is None:
                result['runtime_queries'][field] = result['runtime_queries'][ticks_field] = 'returned-null'
                continue
            ticks = native.absolute_ticks()
            if type(ticks) is not int or not 0 <= ticks < 1 << 64:
                raise ValueError('Native ' + field + ' tick value has an unexpected type or bound.')
            text = str(native)
            result[field], result[ticks_field] = text, str(ticks)
            result['runtime_queries'][field] = result['runtime_queries'][ticks_field] = 'returned-value'
        except Exception as error:
            result['runtime_queries'][field] = result['runtime_queries'][ticks_field] = 'failed'
            result['runtime_errors'][field] = result['runtime_errors'][ticks_field] = str(error)
    if sim is not None:
        result['persistence'] = persistence_evidence(backend, sim, household)
        linked = []
        tracker = sim.occult_tracker
        membership = []
        for kind in backend._all_occults():
            if backend._has_occult(tracker, kind):
                membership.append({'occult': backend._safe_name(kind), 'flags': int(kind)})
            other = tracker.get_occult_sim_info(kind)
            if other is not None:
                blob = backend._v8_read_outfit_blob(other)
                linked.append({'occult': str(kind), 'flags': int(kind), 'sim_id': str(other.id),
                               'outfit_sha256': hashlib.sha256(blob).hexdigest() if blob else None})
        blob = backend._v8_read_outfit_blob(sim)
        result['sim'] = {'id': str(sim.id), 'name': '{} {}'.format(sim.first_name, sim.last_name),
                         'occult_flags': backend._get_occult_flags(sim), 'current_form': backend._get_current_flags(sim),
                         'membership': membership,
                         'outfit_sha256': hashlib.sha256(blob).hexdigest() if blob else None,
                         'linked_forms': linked, 'instanced': sim.get_sim_instance() is not None,
                         'current_outfit': list(sim.get_current_outfit())}
        if export_forms:
            from .form_appearance import evidence
            result['sim']['full_appearance'] = evidence(backend, sim, export=True)
            forms = []
            for kind, form in sorted(backend._form_map(tracker).items(), key=lambda pair: int(pair[0])):
                forms.append({'flags': int(kind), 'occult': backend._safe_name(kind),
                              'sim_id': str(form.id), 'appearance': evidence(backend, form, export=True)})
            result['sim']['form_appearances'] = forms
        if export_outfits:
            from .outfit_snapshot import normalize
            result['sim']['outfit_base64'] = base64.b64encode(blob).decode('ascii')
            result['sim']['appearance_sha256'] = hashlib.sha256(normalize(blob)).hexdigest()
    if sim is None and isinstance(getattr(backend, '_apex_native_load_failure', None), dict):
        result['native_load_failure'] = copy.deepcopy(backend._apex_native_load_failure)
    elif sim is not None:
        projection = getattr(sim.occult_tracker, '_apex_native_witch_genetics_projection', None)
        if isinstance(projection, dict):
            result['native_genetics_projection'] = copy.deepcopy(projection)
        retention = getattr(sim.occult_tracker, '_apex_native_transition_retention', None)
        if isinstance(retention, dict):
            result['native_transition_retention'] = copy.deepcopy(retention)
        load_appearance = getattr(sim.occult_tracker, '_apex_native_load_appearance_retention', None)
        if isinstance(load_appearance, dict):
            result['native_load_appearance_retention'] = copy.deepcopy(load_appearance)
        load_failure = getattr(sim.occult_tracker, '_apex_native_load_appearance_failure', None)
        if isinstance(load_failure, dict):
            result['native_load_appearance_failure'] = {name: copy.deepcopy(load_failure.get(name))
                for name in ('error', 'verified', 'retry_safe', 'bank_read')}
        failure = getattr(sim.occult_tracker, '_apex_native_transition_failure', None)
        if isinstance(failure, dict):
            result['native_transition_failure'] = {name: copy.deepcopy(failure.get(name))
                for name in ('source', 'target', 'error', 'appearance_authority', 'retry_safe', 'bank_read')}
    return result


def native_identity_inventory(backend, sim_id, argument):
    """Read exact manager/household/save identities even when the Sim is absent.

    No fallback Sim, manager insertion/removal, persistence serialization of a
    runtime Sim, form-bank access or repair occurs. Native persistence bytes
    are read only from an existing buffer, with their actual identities kept.
    """
    fields = {'save_guid', 'household_id', 'include_native_record'}
    if (not isinstance(argument, dict) or set(argument) != fields or
            type(argument.get('include_native_record')) is not bool or
            not all(_save_id(value) for value in (sim_id, argument.get('save_guid'), argument.get('household_id')))):
        raise ValueError('Use an exact selected Sim, native household/save GUID and typed record option.')
    household_id, save_guid = argument['household_id'], argument['save_guid']
    before = snapshot(backend, None)
    def context_matches(live):
        return (isinstance(live, dict) and live.get('ok') is True and
                live.get('household_id') == household_id and live.get('save_guid') == save_guid and
                live.get('zone_running') is True and live.get('in_build_buy') is False and
                _save_id(live.get('client_id')) and _save_id(live.get('zone_id')) and
                isinstance(live.get('runtime_queries'), dict) and
                all(live['runtime_queries'].get(key) == 'returned-value' for key in ('client_id', 'zone_running')))
    if not context_matches(before):
        raise ValueError('Native household/save/Live identity differs; no identity inventory read.')
    result = {'ok': False, 'scope': 'native-sim-identity-inventory', 'sim_id': sim_id,
              'household_id': household_id, 'save_guid': save_guid, 'live_context_before': before,
              'manager_selected': {'query': 'failed', 'present': None},
              'manager_inventory': {'query': 'failed', 'selected_present': None},
              'active_household': {'query': 'failed', 'selected_member': None},
              'persisted_household': {'query': 'failed', 'selected_member': None},
              'persisted_selected': {'query': 'failed', 'present': None},
              'native_record_query': 'not-requested', 'native_record': None,
              'selected_native_absence_verified': False, 'identity_deletion_verified': False,
              'replacement_mapping_verified': False, 'sim_mutated': False,
              'manager_mutated': False, 'persistence_mutated': False, 'bank_read': False}
    def identifier(value, allow_zero=False):
        value = str(value)
        if not _save_id(value) and not (allow_zero and value == '0'):
            raise ValueError('Native identity is not an exact uint64 decimal value.')
        return value
    def ids(values):
        rows, seen = [], set()
        for item in values:
            if len(rows) >= 20000:
                raise ValueError('Native identity inventory exceeds its bound.')
            value = identifier(item)
            if value in seen:
                raise ValueError('Native identity inventory contains duplicate IDs.')
            rows.append(value); seen.add(value)
        return rows
    def failure(key, error):
        result[key].update(query='failed', error=str(error)[:1024])
    manager = backend.services.sim_info_manager()
    try:
        selected = manager.get(int(sim_id))
        row = result['manager_selected']
        row.update(query='returned-null' if selected is None else 'returned-value', present=selected is not None)
        if selected is not None:
            row.update(sim_id=identifier(selected.id), household_id=identifier(selected.household_id, allow_zero=True),
                       instanced=selected.get_sim_instance() is not None)
            if row['sim_id'] != sim_id:
                raise ValueError('Manager selected lookup returned a different Sim ID.')
    except Exception as error:
        failure('manager_selected', error)
    try:
        manager_ids, members, seen = [], [], set()
        for info in manager.get_all():
            if len(manager_ids) >= 20000:
                raise ValueError('Native manager inventory exceeds its bound.')
            current_id, current_household = identifier(info.id), identifier(info.household_id, allow_zero=True)
            if current_id in seen:
                raise ValueError('Native manager inventory contains duplicate Sim IDs.')
            manager_ids.append(current_id); seen.add(current_id)
            if current_household == household_id:
                members.append({'sim_id': current_id, 'household_id': current_household,
                                'instanced': info.get_sim_instance() is not None})
        result['manager_inventory'].update(query='returned-value', count=len(manager_ids),
            sim_ids=manager_ids, selected_present=sim_id in manager_ids,
            household_sim_ids=[row['sim_id'] for row in members], household_records=members)
    except Exception as error:
        failure('manager_inventory', error)
    try:
        household = backend.services.active_household()
        if household is None or identifier(household.id) != household_id:
            raise ValueError('Active household identity changed during inventory.')
        household_ids = ids(info.id for info in household.sim_info_gen())
        result['active_household'].update(query='returned-value', household_id=household_id,
                                         sim_ids=household_ids, selected_member=sim_id in household_ids)
    except Exception as error:
        failure('active_household', error)
    persistence = backend.services.get_persistence_service()
    try:
        native_household = persistence.get_household_proto_buff(int(household_id))
        row = result['persisted_household']
        row.update(query='returned-null' if native_household is None else 'returned-value',
                   present=native_household is not None)
        if native_household is not None:
            if identifier(native_household.household_id) != household_id:
                raise ValueError('Native household buffer has a different household ID.')
            household_ids = ids(native_household.sims.ids)
            row.update(household_id=household_id, sim_ids=household_ids, selected_member=sim_id in household_ids)
    except Exception as error:
        failure('persisted_household', error)
    try:
        native_selected = persistence.get_sim_proto_buff(int(sim_id))
        row = result['persisted_selected']
        row.update(query='returned-null' if native_selected is None else 'returned-value', present=native_selected is not None)
        if native_selected is not None:
            row.update(sim_id=identifier(native_selected.sim_id), household_id=identifier(native_selected.household_id, allow_zero=True))
            if row['sim_id'] != sim_id:
                raise ValueError('Native selected buffer has a different Sim ID.')
            if argument['include_native_record']:
                result['native_record_query'] = 'failed'
                from .sim_data import catalog
                result['native_record'] = dict(catalog(native_selected), source='native-existing-save-buffer',
                    sim_id=sim_id, household_id=row['household_id'], save_guid=save_guid)
                result['native_record_query'] = 'returned-value'
        elif argument['include_native_record']:
            result['native_record_query'] = 'returned-null'
    except Exception as error:
        failure('persisted_selected', error)
    after = snapshot(backend, None)
    if (not context_matches(after) or any(after.get(key) != before.get(key)
            for key in ('client_id', 'zone_id', 'save_guid', 'household_id'))):
        raise ValueError('Native household/save/client/zone identity changed during inventory.')
    result['live_context_after'] = after
    result['ok'] = all(result[key]['query'] != 'failed' for key in
                       ('manager_selected', 'manager_inventory', 'active_household', 'persisted_household', 'persisted_selected'))
    result['selected_native_absence_verified'] = (result['ok'] and
        result['manager_selected']['present'] is False and result['manager_inventory']['selected_present'] is False and
        result['active_household']['selected_member'] is False and
        result['persisted_household'].get('selected_member') is False and result['persisted_selected']['present'] is False)
    return result


def native_form_snapshot(backend, sim, sim_id, argument):
    """Read an explicit native appearance owner without bank/history fallback."""
    fields = {'form_flags', 'save_guid', 'household_id', 'include_native_record'}
    if (not isinstance(argument, dict) or set(argument) != fields or
            type(argument.get('form_flags')) is not int or argument['form_flags'] not in (1, 2, 4, 8, 16, 32, 64) or
            type(argument.get('include_native_record')) is not bool or
            not all(_save_id(value) for value in (sim_id, argument.get('save_guid'), argument.get('household_id')))):
        raise ValueError('Use an explicit native form and exact save/household/Sim identities.')
    if sim is None or str(sim.id) != sim_id or str(sim.household_id) != argument['household_id']:
        raise ValueError('Selected native Sim/household differs; no appearance owner read.')
    live = snapshot(backend, sim)
    if (live.get('ok') is not True or live.get('save_guid') != argument['save_guid'] or
            live.get('household_id') != argument['household_id'] or
            not isinstance(live.get('sim'), dict) or live['sim'].get('id') != sim_id):
        raise ValueError('Native save/household/Sim context differs; no appearance owner read.')
    flags = argument['form_flags']
    tracker = sim.occult_tracker
    # A failed membership API is retained as failed, never replaced by a mask.
    membership = []
    for kind in backend._all_occults():
        row = {'occult': backend._safe_name(kind), 'flags': int(kind), 'query': 'failed', 'has_occult': None}
        try:
            present = tracker.has_occult_type(kind)
            if type(present) is not bool:
                raise ValueError('Native membership getter returned an unexpected type.')
            row.update(query='returned-value', has_occult=present)
        except Exception as error:
            row['error'] = str(error)[:1024]
        membership.append(row)
    native_map = backend._form_map(tracker)
    if not isinstance(native_map, dict):
        raise ValueError('Native stored form map is unavailable.')
    target = native_map.get(backend._coerce_flags(flags))
    current = backend._get_current_flags(sim)
    if type(current) is not int:
        raise ValueError('Native active form identity is unavailable.')
    source = 'native-form-map'
    stored_present = target is not None
    if target is None and current == flags:
        target, source = sim, 'current-live-only'
    result = {'ok': target is not None, 'form_flags': flags, 'sim_id': sim_id,
              'native_wrapper_id': None if target is None else str(target.id), 'source': source,
              'stored_form_present': stored_present, 'current_form_flags': current,
              'native_membership': membership, 'live_context': live,
              'appearance': None, 'active_live_appearance': None, 'native_record': None,
              'bank_read': False, 'form_created': False, 'appearance_mutated': False,
              'save_reload_verified': False}
    if target is None:
        result.update(outcome='missing-native-form', message='The explicit native stored form is absent; no bank fallback or form creation occurred.')
        return result
    if not _save_id(result['native_wrapper_id']):
        raise ValueError('Native wrapper has no exact Sim identity.')
    from .form_appearance import evidence
    result['appearance'] = evidence(backend, target, export=True)
    result['last_restore_diagnostics'] = getattr(backend, '_APEX_APPEARANCE_RESTORE_DIAGNOSTICS', {}).get(str(target.id))
    result['last_serializer_failure'] = getattr(tracker, '_apex_serialization_appearance_failure', None)
    if current == flags:
        result['active_live_appearance'] = evidence(backend, sim, export=True)
    if argument['include_native_record']:
        persistence = backend.services.get_persistence_service()
        message = persistence.get_sim_proto_buff(sim.id)
        if message is None or str(message.sim_id) != sim_id or str(message.household_id) != argument['household_id']:
            raise ValueError('Existing native Sim persistence buffer identity differs.')
        from .sim_data import catalog
        result['native_record'] = dict(catalog(message), source='native-existing-save-buffer',
                                       sim_id=sim_id, household_id=argument['household_id'], save_guid=argument['save_guid'])
    return result


def _save_id(value):
    return (isinstance(value, str) and value.isascii() and value.isdecimal()
            and 0 < int(value) < 1 << 64 and str(int(value)) == value)


def _save_target(argument):
    fields = {'slot_id', 'slot_name', 'expected_save_sha256', 'save_guid', 'household_id', 'sim_id'}
    if (not isinstance(argument, dict) or set(argument) != fields
            or type(argument.get('slot_id')) is not int or not 0 < argument['slot_id'] < 0xffffffff
            or not isinstance(argument.get('slot_name'), str) or not 0 < len(argument['slot_name']) <= 128
            or len(argument['slot_name'].encode('utf-8')) > 512
            or not argument['slot_name'].strip() or any(ord(char) < 32 or ord(char) == 127 for char in argument['slot_name'])
            or not isinstance(argument.get('expected_save_sha256'), str)
            or len(argument['expected_save_sha256']) != 64
            or any(char not in '0123456789abcdef' for char in argument['expected_save_sha256'])
            or not all(_save_id(argument.get(name)) for name in ('save_guid', 'household_id', 'sim_id'))):
        raise ValueError('Save requires one typed existing slot/name, original file SHA-256 and exact save/household/Sim identities.')
    return argument


def _save_file_evidence(profile, slot_id):
    """Passive regular-file evidence; a caller never supplies a destination path."""
    import stat
    from .overlay_loader import _unlinked
    profile = _unlinked(profile)
    if profile.name != 'The Sims 4':
        raise ValueError('Save target must be beneath the marked disposable profile.')
    target = _unlinked(profile / 'saves' / ('Slot_{:08x}.save'.format(slot_id)))
    if target.parent.parent != profile:
        raise ValueError('Save target escaped the disposable profile.')
    before = target.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= 256 * 1024 * 1024:
        raise ValueError('Save target must be an existing nonempty, unlinked regular file within its bound.')
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    after = target.lstat()
    signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)
    if signature(before) != signature(after):
        raise ValueError('Save target changed during its hash read; no stable file identity was observed.')
    return {'path': str(target), 'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns,
            'ctime_ns': after.st_ctime_ns, 'device': after.st_dev, 'inode': after.st_ino,
            'sha256': digest.hexdigest()}


def _save_live_context(result, argument):
    """Require fresh native membership/buffers, not a cached household label."""
    required = ('active_household_membership', 'runtime_household_identity', 'manager_identity', 'account_save_eligible',
                'sim_proto_exists', 'sim_proto_identity', 'sim_proto_household_identity',
                'household_proto_exists', 'household_proto_identity', 'household_proto_membership')
    if (not isinstance(result, dict) or result.get('ok') is not True
            or result.get('save_guid') != argument['save_guid']
            or result.get('household_id') != argument['household_id']
            or result.get('in_build_buy') is not False or result.get('zone_running') is not True
            or not isinstance(result.get('sim'), dict) or result['sim'].get('id') != argument['sim_id']
            or result['sim'].get('instanced') is not True
            or type(result.get('save_slot')) is not int or not 0 <= result['save_slot'] <= 0xffffffff
            or not isinstance(result.get('runtime_queries'), dict)
            or any(result['runtime_queries'].get(name) != 'returned-value' for name in ('client_id', 'zone_running'))
            or not _save_id(result.get('client_id')) or not _save_id(result.get('zone_id'))
            or not isinstance(result.get('persistence'), dict)
            or result['persistence'].get('persistence_verified_before_save') is not True
            or not isinstance(result['persistence'].get('checks'), dict)
            or any(result['persistence']['checks'].get(name) is not True for name in required)
            or any(value is not True for value in result['persistence']['checks'].values())):
        raise ValueError('Save target differs from fresh native GUID/household/Sim persistence or live-client context.')
    return result


def _submit_existing_save(backend, sim, client, argument):
    argument = _save_target(argument)
    if sim is None or str(sim.id) != argument['sim_id']:
        raise ValueError('Save requires the exact selected disposable Sim.')
    from . import cas_ui
    with cas_ui._LOCK:
        if cas_ui._PEERS or any(row.get('state') not in ('completed', 'failed', 'superseded-read')
                                for row in cas_ui._RECORDS.values()):
            raise ValueError('CAS is active or unresolved; no save target may be submitted.')
    before = _save_live_context(snapshot(backend, sim), argument)
    if before['client_id'] != str(client.id):
        raise ValueError('Native save-client identity changed before submission.')
    identity = runtime_identity(backend.__file__)
    if not identity.get('test_token') or not identity.get('profile'):
        raise ValueError('No marked disposable save profile is available.')
    file_before = _save_file_evidence(Path(identity['profile']), argument['slot_id'])
    if file_before['sha256'] != argument['expected_save_sha256']:
        raise ValueError('Existing save target SHA-256 differs; no save was submitted.')
    from . import form_bank_seal
    seal_intent = form_bank_seal.begin_save(backend, sim, argument, before, file_before)
    from server_commands.persistence_commands import override_save_slot
    result = {'ok': False, 'transition': 'existing-save-target-submission', 'slot_id': argument['slot_id'],
              'slot_name': argument['slot_name'], 'save_guid': argument['save_guid'],
              'household_id': argument['household_id'], 'sim_id': argument['sim_id'],
              'runtime_slot_before': before['save_slot'], 'native_before': before, 'target_before': file_before,
              'form_bank_seal': seal_intent,
              'save_submission_attempted': True, 'save_submitted': None, 'retry_safe': False,
              'save_completed_verified': False, 'save_completed_file_verified': False, 'save_reload_verified': False}
    try:
        # Current installed bytecode schedules save_game_gen and returns None.
        # No direct slot/protobuf patch or scratch-save command is substituted.
        native_return = override_save_slot(argument['slot_id'], argument['slot_name'], auto_save_slot_id=None,
                                          ignore_callback=False, _connection=client.id)
    except Exception as error:
        form_bank_seal.submitted(backend, sim, seal_intent, None)
        result.update(outcome='unresolved', message='Native save scheduling raised; retain its request UUID and do not replay.',
                      native_error=str(error))
        return result
    if native_return is False:
        form_bank_seal.submitted(backend, sim, seal_intent, False)
        result.update(outcome='save-rejected', save_submitted=False,
                      message='Native save command explicitly returned false; submission was not verified.')
        return result
    if native_return is not None:
        form_bank_seal.submitted(backend, sim, seal_intent, None)
        result.update(outcome='unresolved', native_return_type=type(native_return).__name__,
                      message='Native save return differs from the inspected None contract; do not replay.')
        return result
    form_bank_seal.submitted(backend, sim, seal_intent, True)
    result.update(ok=True, outcome='save-submitted', save_submitted=True,
                  message='One existing-target save was scheduled; stable target-file change and reload are separate proof.')
    return result


def dispatch(backend, action, sim_id, value):
    global _LAST_CLIENT_ID
    argument = guard(backend, value)
    if action in ('test_capture', 'test_input'):
        from . import overlay_loader
        if action == 'test_capture':
            return overlay_loader.capture(overlay=argument == 'overlay')
        import paths
        return overlay_loader.input_event(backend.__file__, paths.DLL_PATH, argument)
    if action == 'test_quit':
        from sims4.commands import client_cheat
        try:
            manager = backend.services.client_manager()
        except AttributeError:
            manager = None  # CAS may unload gameplay services.
        client = manager.get_first_client() if manager is not None else None
        connection = client.id if client is not None else _LAST_CLIENT_ID
        if connection is None:
            raise ValueError('No observed native game-client connection for normal quit.')
        client_cheat('quit', connection)
        return {'ok': True, 'transition': 'quit-menu-requested', 'game_exit_verified': False,
                'confirmation_required': True, 'message': 'Native quit menu requested; select Exit Game, then Save and Exit. Process exit is not yet verified.'}
    sim = backend._get_sim_info_by_id(sim_id)
    if action == 'test_identity_inventory':
        return native_identity_inventory(backend, sim_id, argument)
    if action == 'test_form_snapshot':
        return native_form_snapshot(backend, sim, sim_id, argument)
    if action == 'test_native_form_select':
        from .native_form_select import select
        return select(backend, sim, sim_id, argument)
    if action == 'test_cas_return_observed':
        if not isinstance(argument, dict) or set(argument) != {'cas_request_id', 'phase', 'household_id', 'minimum_ticks'}:
            raise ValueError('Use a typed CAS return observation with the original request UUID.')
        from .cas_ui import observe_return
        # No caller-provided snapshot, ticks or verified flags are accepted.
        return observe_return(argument['cas_request_id'], snapshot(backend, sim), argument['phase'],
                              argument['household_id'], argument['minimum_ticks'])
    if action == 'test_all_data':
        from .form_bank import assert_idle
        assert_idle(backend, sim)
        from .sim_data import snapshot as all_data_snapshot
        return dict(all_data_snapshot(backend, sim), ok=True)
    if action in ('test_form_seal_complete', 'test_form_reconcile'):
        from . import form_bank_seal
        return (form_bank_seal.complete_save if action == 'test_form_seal_complete' else form_bank_seal.reconcile)(backend, sim, argument)
    if action == 'test_cas_abandon_unsaved':
        from .form_bank import abandon_unsaved
        return abandon_unsaved(backend, sim, argument)
    if action in ('test_status', 'test_snapshot'):
        return snapshot(backend, sim, export_outfits=argument == 'outfits', export_forms=argument == 'forms')
    if action == 'test_outfit':
        request = json.loads(argument) if isinstance(argument, str) else argument
        if not isinstance(request, dict) or set(request) != {'category', 'index'} or any(type(request[key]) is not int or not 0 <= request[key] < 1024 for key in request):
            raise ValueError('Use one existing outfit category/index.')
        if sim is None: raise ValueError('Select the explicit disposable Sim.')
        from .form_bank import assert_idle
        assert_idle(backend, sim)
        from sims.outfits.outfit_enums import OutfitCategory
        target = (OutfitCategory(request['category']), request['index'])
        if not sim.has_outfit(target): raise ValueError('That outfit does not exist; no outfit generated.')
        submitted = sim.set_current_outfit(target)
        backend._resend_all_visuals(sim)
        result = snapshot(backend, sim)
        result.update(ok=bool(submitted) and tuple(sim.get_current_outfit()) == target,
                      transition='existing-outfit-selected', unpaused_visual_verification_required=True)
        return result
    manager = backend.services.client_manager()
    client = manager.get_first_client()
    if client is None:
        raise ValueError('No active game client is available.')
    _LAST_CLIENT_ID = client.id
    if action in ('test_pause', 'test_play', 'test_speed2', 'test_speed3'):
        from server_commands.clock_commands import set_speed
        speed = {'test_pause': 'paused', 'test_play': 'one', 'test_speed2': 'two', 'test_speed3': 'three'}[action]
        set_speed(speed, 'apex.cli', _connection=client.id)
        result = snapshot(backend, sim)
        result['ok'] = result['clock_speed'] == {'paused': 0, 'one': 1, 'two': 2, 'three': 3}[speed]
        return result
    if action == 'test_create_sim':
        household = backend.services.active_household()
        if household is None or len(tuple(household.sim_info_gen())) >= 8:
            raise ValueError('Test creation requires a loaded household with a free slot.')
        before = {item.id for item in household.sim_info_gen()}
        from server_commands.sim_commands import spawn_client_sims_simple
        from sims.sim_info_types import Age, Gender, Species
        spawn_client_sims_simple(num=1, x=None, y=None, z=None, age=Age.YOUNGADULT,
                                 gender=Gender.FEMALE, species=Species.HUMAN,
                                 household_id='active', instantiate=True, _connection=client.id)
        created = [item for item in household.sim_info_gen() if item.id not in before]
        if len(created) != 1:
            return {'ok': False, 'outcome': 'unresolved',
                    'created_sim_ids': [str(item.id) for item in created],
                    'persistence_verified_before_save': False, 'save_reload_verified': False,
                    'creation_submitted': True, 'retry_safe': False,
                    'message': 'Creation was submitted but one new Sim was not observed; do not repeat blindly.'}
        created[0].first_name, created[0].last_name = 'Apex', 'Test'
        result = snapshot(backend, created[0])
        evidence = result.get('persistence') or persistence_evidence(backend, created[0], household)
        verified = evidence['persistence_verified_before_save']
        result.update({'ok': verified, 'created_sim_id': str(created[0].id),
                       'created_sim_ids': [str(created[0].id)], 'persistence': evidence,
                       'persistence_verified_before_save': verified, 'save_reload_verified': False,
                       'creation_submitted': True, 'retry_safe': False,
                       'outcome': 'native-save-buffers-verified' if verified else 'persistence-unresolved',
                       'message': ('Created Sim identity and household membership verified in the native save buffers; disk save/reload is still required.'
                                   if verified else 'One test Sim was observed, but native persistence postconditions failed; retain its ID and do not repeat creation blindly.')})
        return result
    if action == 'test_cas':
        if sim is None or sim.get_sim_instance() is None:
            raise ValueError('CAS entry requires an instanced selected Sim.')
        from server_commands.cas_commands import modify_in_cas
        from server_commands.argument_helpers import OptionalTargetParam
        if argument not in (None, 'full'):
            raise ValueError('CAS mode must be default or full.')
        # Keep every form before the native client can propagate CAS edits.
        # A retained/interrupted transaction is deliberately not replaced.
        from . import cas_bank_transaction
        protection = cas_bank_transaction.begin(backend, sim)
        if not isinstance(protection, dict) or protection.get('ok') is not True:
            raise ValueError('Complete CAS form checkpoint was not acknowledged; no entry submitted.')
        before = snapshot(backend, sim)
        from .cas_ui import capture_original_owner
        owner_observation = capture_original_owner(backend, sim)
        if argument == 'full':
            from sims4.commands import client_cheat
            client_cheat('cas.fulleditmode', client.id)
        submitted = modify_in_cas(OptionalTargetParam(str(sim.id)), _connection=client.id)
        return {'ok': bool(submitted), 'transition': 'cas-entry-submitted', 'before': before,
                'form_checkpoint': protection,
                'original_owner': owner_observation,
                'cas_visible_verified': False, 'message': 'CAS entry submitted to the real game client; UI completion must be observed separately.'}
    if action == 'test_save':
        return _submit_existing_save(backend, sim, client, argument)
    raise ValueError('Unknown typed test operation.')
