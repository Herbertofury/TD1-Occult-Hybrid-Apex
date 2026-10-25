"""Fresh metadata for the visible overlay, without appearance/library audits.

Only the canonical game owner calls this module.  HTTP/render workers receive
copied primitives; the result is display data, never authority for a mutation.
Full status, Health, Drift Guard and library actions keep their original paths.
"""
import json
import threading


def _identity(value, allow_zero=False):
    if type(value) is not int or not (0 if allow_zero else 1) <= value < 2**64:
        raise ValueError('Overlay metadata identity is unavailable or outside uint64.')
    return str(value)


def _selected(backend, manager, requested):
    if requested not in (None, ''):
        if (not isinstance(requested, str) or not 1 <= len(requested) <= 32 or
                not requested.isascii() or requested != requested.strip()):
            raise ValueError('Select an exact decimal or hexadecimal Sim identity.')
        try:
            sid = int(requested, 16 if requested.lower().startswith('0x') else 10)
        except ValueError:
            raise ValueError('Select an exact decimal or hexadecimal Sim identity.')
        _identity(sid)
        sim = manager.get(sid)
        if sim is None or int(sim.id) != sid:
            raise ValueError('The selected Sim is unavailable; another Sim was not substituted.')
        return sim
    sim = backend._get_active_sim_info()
    if sim is not None and manager.get(int(sim.id)) is not sim:
        raise ValueError('The active Sim is no longer owned by the current manager.')
    return sim


def _label(backend, sim):
    # The existing label helper reads names/identity only, never appearance.
    label = backend._sim_label(sim)
    if not isinstance(label, str):
        raise ValueError('The selected Sim has no display label.')
    return label


def _household(backend, sim, manager):
    hid = _identity(int(sim.household_id), allow_zero=True)
    household = getattr(sim, 'household', None)
    if household is None:
        if hid != '0':
            raise ValueError('The selected household is unavailable; no partial roster returned.')
        return {'household_id': hid, 'members': [], 'complete': True}, None, ()
    generator = next((getattr(household, name, None) for name in
                      ('sim_info_gen', 'get_all_sim_infos', 'get_all_sims_sim_info_gen')
                      if callable(getattr(household, name, None))), None)
    if generator is None:
        raise ValueError('The native household roster is unavailable.')
    members = tuple(generator())
    rows, ids = [], set()
    for member in members:
        if member is None:
            raise ValueError('The native household roster has an unavailable member.')
        sid = _identity(int(member.id))
        if sid in ids or str(int(member.household_id)) != hid or manager.get(int(sid)) is not member:
            raise ValueError('The native household roster changed or contains a foreign member.')
        ids.add(sid)
        rows.append({'id': sid, 'name': _label(backend, member),
                     'occult_types_value': int(backend._get_occult_flags(member)),
                     'current_occult_types_value': int(backend._get_current_flags(member))})
    if str(int(sim.id)) not in ids:
        raise ValueError('The selected Sim is absent from its native household roster.')
    return {'household_id': hid, 'members': rows, 'complete': True}, generator, members


def _known_warning_count(backend, sid):
    # These are existing in-memory notifications, not a new drift scan.  Do not
    # copy baselines/payloads, call the layered warning helper or inspect Sims.
    warnings = getattr(backend, '_APEX7_WARNINGS', {})
    if not isinstance(warnings, dict):
        return None
    prefix = sid + ':'
    return sum(1 for key in warnings if isinstance(key, str) and key.startswith(prefix))


def dispatch(backend, requested=None, value=None):
    if (backend.services is None or threading.current_thread().ident !=
            backend._APEX_GAME_THREAD_IDENT):
        raise ValueError('Overlay metadata requires the canonical Sims game-thread owner.')
    if isinstance(value, str):
        if len(value) > 128:
            raise ValueError('Overlay metadata accepts only a bounded log-count object.')
        def unique(items):
            result = {}
            for key, item in items:
                if key in result:
                    raise ValueError('Overlay metadata repeats an option.')
                result[key] = item
            return result
        options = json.loads(value, object_pairs_hook=unique)
    else:
        options = value
    options = {'count': 220} if options is None else options
    if (not isinstance(options, dict) or set(options) != {'count'} or
            type(options['count']) is not int or not 0 <= options['count'] <= 260):
        raise ValueError('Overlay metadata accepts only a log count from zero to 260.')
    manager = backend.services.sim_info_manager()
    if manager is None:
        raise ValueError('The native Sim manager is unavailable.')
    sim = _selected(backend, manager, requested)
    persistence = backend.services.get_persistence_service()
    save_guid = _identity(int(persistence.get_save_slot_proto_guid()), allow_zero=True)
    status = {'ok': sim is not None, 'message': 'No active Sim' if sim is None else 'Fresh overlay metadata',
              'sim': None, 'sim_id': None, 'save_guid': save_guid,
              'health': None, 'health_observation': 'not-scanned',
              'drift_warning_count': None, 'drift_observation': 'cached-notifications-only',
              'drift_scan_performed': False, 'occults': [], 'form_map_keys': [],
              'display_metadata_only': True, 'mutation_authority': False}
    household = {'household_id': None, 'members': [], 'complete': sim is None}
    if sim is not None:
        sid = _identity(int(sim.id))
        flags, current = int(backend._get_occult_flags(sim)), int(backend._get_current_flags(sim))
        tracker = sim.occult_tracker
        forms = backend._form_map(tracker)
        if not hasattr(forms, 'items'):
            raise ValueError('The selected native form map is unavailable.')
        form_keys = tuple((key, owner is not None) for key, owner in forms.items())
        membership = []
        for occult in backend._all_occults(include_human=True):
            number = int(occult)
            membership.append({'name': str(backend._safe_name(occult)), 'value': number,
                               'has_occult': bool(flags & number),
                               'has_form_data': any(int(key) == number and present for key, present in form_keys),
                               'has_memory_trait': None, 'has_tuning': None})
        household, generator, members = _household(backend, sim, manager)
        status.update(sim=_label(backend, sim), sim_id=sid, household_id=household['household_id'],
                      occult_types_value=flags, current_occult_types_value=current,
                      occult_form_available=bool(getattr(tracker, '_occult_form_available', False)),
                      form_map_keys=[str(backend._safe_name(key)) for key, present in form_keys if present],
                      form_membership=membership,
                      occults=[row for row in membership if row['name'].upper() != 'HUMAN'],
                      drift_warning_count=_known_warning_count(backend, sid))
        # A display packet cannot silently mix a replacement Sim/household/save.
        # These checks read metadata only; native appearance getters are absent.
        returned_members = tuple(generator()) if generator is not None else ()
        if (manager.get(int(sid)) is not sim or int(sim.household_id) != int(household['household_id']) or
                persistence.get_save_slot_proto_guid() != int(save_guid) or
                len(returned_members) != len(members) or
                any(now is not before for now, before in zip(returned_members, members))):
            raise ValueError('The selected native display context changed during observation.')
    with backend._LOCK:
        count = options['count']
        history = backend._HISTORY[-count:] if count else ()
        logs = [line[:4096] for line in history if isinstance(line, str)]
    return {'ok': True, 'schema': 1, 'message': 'Overlay display metadata ready',
            'build_version': str(backend._BUILD_VERSION), 'status': status,
            'household': household, 'sims': household['members'], 'logs': logs,
            'alarm_ready': bool(backend._ALARM_READY), 'server_running': bool(backend._SERVER_RUNNING),
            'auto_repair': bool(backend._AUTO_REPAIR), 'native_status': str(backend._NATIVE_STATUS),
            'appearance_read': False, 'appearance_written': False, 'library_scan_performed': False,
            'display_metadata_only': True, 'mutation_authority': False}
