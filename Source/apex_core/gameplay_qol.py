"""Explicit game-thread autonomy and occult safety controls.

World autonomy/death overrides last for this session and restore the exact
previous setting. Per-Sim sunlight/umbrella preferences are scoped to save GUID
and Sim ID. Hooks delegate unchanged when no relevant preference is enabled;
there is no timer, filesystem access in callbacks, or appearance mutation.
"""
import inspect
import json
import os
from pathlib import Path

_AUTONOMY = None
_DEATH = None
_PREFERENCES = {}
_SAVE = None
_SUN = set()
_UMBRELLA = set()


def _path(backend):
    from .overlay_loader import _unlinked
    return _unlinked(Path(backend._data_directory()) / 'gameplay_qol.json')


def _load(backend):
    global _SAVE, _PREFERENCES, _SUN, _UMBRELLA
    guid = str(backend.services.get_persistence_service().get_save_slot_proto_guid())
    if _SAVE == guid:
        return
    path = _path(backend)
    data = {'schema': 1, 'saves': {}}
    if path.exists():
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('Occult safety preferences exceed their size bound.')
        data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('saves'), dict) or len(data['saves']) > 128:
        raise ValueError('Invalid occult safety preferences.')
    for saved, members in data['saves'].items():
        if not str(saved).isdigit() or not isinstance(members, dict) or len(members) > 4096:
            raise ValueError('Invalid save/member safety preferences.')
        for sid, options in members.items():
            if (not str(sid).isdigit() or not isinstance(options, dict) or
                    set(options) != {'sunlight', 'umbrella'} or
                    any(type(v) is not bool for v in options.values())):
                raise ValueError('Invalid per-Sim safety preference.')
    _PREFERENCES, _SAVE = data, guid
    members = data['saves'].get(guid, {})
    _SUN = {sid for sid, row in members.items() if row['sunlight']}
    _UMBRELLA = {sid for sid, row in members.items() if row['umbrella']}


def _persist(backend, sim, option, enabled):
    global _PREFERENCES
    from .overlay_loader import _unlinked
    import copy
    data = copy.deepcopy(_PREFERENCES)
    row = data['saves'].setdefault(_SAVE, {}).setdefault(str(sim.id), {'sunlight': False, 'umbrella': False})
    row[option] = enabled
    raw = json.dumps(data, sort_keys=True, allow_nan=False).encode('utf-8')
    if len(raw) > 1024 * 1024:
        raise ValueError('Occult safety preferences exceed their size bound.')
    path = _path(backend)
    temporary = _unlinked(path.with_suffix('.pending'))
    with temporary.open('wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))
    _PREFERENCES = data
    target = _SUN if option == 'sunlight' else _UMBRELLA
    target.add(str(sim.id)) if enabled else target.discard(str(sim.id))


def _autonomy(backend, enabled=None):
    global _AUTONOMY
    from autonomy.settings import AutonomyState, AutonomySettingsGroup
    service = backend.services.autonomy_service()
    if service is None:
        raise ValueError('Autonomy service is unavailable.')
    settings, group = service.global_autonomy_settings, AutonomySettingsGroup.DEFAULT
    if _AUTONOMY and _AUTONOMY['service'] is not service:
        _AUTONOMY = None
    current = settings.get_setting(AutonomyState, group)
    if enabled is True and _AUTONOMY is None:
        prior = current
        settings.set_setting(AutonomyState.DISABLED, group)
        if settings.get_setting(AutonomyState, group) != AutonomyState.DISABLED:
            settings.set_setting(prior, group)
            raise ValueError('Native autonomy override was not acknowledged.')
        _AUTONOMY = {'service': service, 'prior': prior}
    elif enabled is False and _AUTONOMY is not None:
        if current != AutonomyState.DISABLED:
            raise ValueError('Another mod changed autonomy; its setting was retained.')
        prior = _AUTONOMY['prior']
        settings.set_setting(prior, group)
        if settings.get_setting(AutonomyState, group) != prior:
            raise ValueError('Prior autonomy setting was not restored; retain this override.')
        _AUTONOMY = None
    current = settings.get_setting(AutonomyState, group)
    return {'paused_by_apex': _AUTONOMY is not None and current == AutonomyState.DISABLED,
            'native_global_state': int(current), 'scope': 'world-default-group',
            'session_only': True, 'running_interactions_cancelled': False}


def _death(enabled=None):
    global _DEATH
    from interactions.utils import death
    current = death._is_death_enabled
    if type(current) is not bool:
        raise ValueError('Native death-enable setting changed type.')
    if enabled is True and _DEATH is None:
        death.toggle_death(enabled=False)
        if death._is_death_enabled is not False:
            raise ValueError('Native death prevention was not acknowledged.')
        _DEATH = {'prior': current}
    elif enabled is False and _DEATH is not None:
        if death._is_death_enabled is not False:
            raise ValueError('Another mod changed death prevention; its setting was retained.')
        death.toggle_death(enabled=_DEATH['prior'])
        if death._is_death_enabled != _DEATH['prior']:
            raise ValueError('Prior death setting was not restored.')
        _DEATH = None
    return {'prevented_by_apex': _DEATH is not None and death._is_death_enabled is False,
            'native_death_enabled': death._is_death_enabled, 'session_only': True,
            'already_dying_sims_recovered': False}


def _sun_buffs(backend, sim):
    # Exact buff objects from installed vampire trait tuning; no global shade
    # spoofing and no change to PlantSim/day/night effects.
    known = set(backend._tuning_traits(backend.OccultType.VAMPIRE))
    known.update(trait for trait in sim.trait_tracker if 'vampire' in getattr(trait, '__name__', '').lower())
    result = set()
    for trait in known:
        tracking = getattr(trait, 'day_night_tracking', None)
        if tracking is not None:
            result.update(row.buff_type for row in tracking.sunlight_buffs if row.buff_type is not None)
    return result


def install(backend):
    """Install event-based, narrowly scoped delegating wrappers once."""
    _load(backend)
    from traits.trait_tracker import TraitTracker
    from weather.weather_aware_component import WeatherAwareComponent
    from time_service import TimeService
    exposure_original = TimeService.is_in_sunlight
    if not getattr(exposure_original, '_apex_sunlight_exposure_qol', False):
        exposure_signature = inspect.signature(exposure_original)
        if tuple(exposure_signature.parameters) != ('self', 'sim'):
            raise ValueError('Native sunlight exposure signature changed; wrapper refused.')
        vampire_traits = frozenset(backend._tuning_traits(backend.OccultType.VAMPIRE))
        def exposure(self, sim):
            info = getattr(sim, 'sim_info', None)
            if info is not None and str(info.id) in _SUN:
                # DayWalkers' inspected behavior uses this native exposure
                # predicate. Scope it to explicit preferences and actual
                # tuned vampire traits, including hybrids in other forms.
                traits = info.get_traits()
                if any(trait in vampire_traits for trait in traits):
                    return False
            return exposure_original(self, sim)
        exposure._apex_sunlight_exposure_qol = True
        exposure._apex_original = exposure_original
        TimeService.is_in_sunlight = exposure
    original = TraitTracker._add_remove_day_night_buffs
    if not getattr(original, '_apex_sunlight_qol', False):
        inspect.signature(original).bind(None, (), True)
        def sunlight(self, buffs, add):
            if add and _SUN and str(self._sim_info.id) in _SUN:
                blocked = _sun_buffs(backend, self._sim_info)
                buffs = tuple(row for row in buffs if row.buff_type not in blocked)
            return original(self, buffs, add)
        sunlight._apex_sunlight_qol = True
        TraitTracker._add_remove_day_night_buffs = sunlight
    route_original = WeatherAwareComponent.provide_route_events
    if not getattr(route_original, '_apex_umbrella_qol', False):
        signature = inspect.signature(route_original)
        signature.bind(None, None, None, None, 0, 0)
        if not {'sim', 'route_event_context'}.issubset(signature.parameters):
            raise ValueError('Native umbrella routing signature changed; wrapper refused.')
        class Context:
            def __init__(self, native, enter):
                self.native, self.enter = native, enter
            def __getattr__(self, name):
                return getattr(self.native, name)
            def route_event_already_scheduled(self, event, *args, **kwargs):
                if event is self.enter:
                    return True
                return self.native.route_event_already_scheduled(event, *args, **kwargs)
        def umbrella(self, *args, **kwargs):
            if not _UMBRELLA:
                return route_original(self, *args, **kwargs)
            bound = signature.bind(self, *args, **kwargs)
            sim = bound.arguments['sim']
            if str(sim.sim_info.id) not in _UMBRELLA:
                return route_original(self, *args, **kwargs)
            bound.arguments['route_event_context'] = Context(
                bound.arguments['route_event_context'], self.umbrella_route_events.enter_carry_event)
            return route_original(*bound.args, **bound.kwargs)
        umbrella._apex_umbrella_qol = True
        WeatherAwareComponent.provide_route_events = umbrella


def _exposure_status(backend, sim):
    """Explicit read proof; no timer or change to the sun, clock or Sim."""
    query = getattr(backend.services, 'time_service', None)
    instance = sim.get_sim_instance() if sim is not None else None
    if not callable(query) or instance is None:
        return {'query': 'unavailable'}
    try:
        time = query()
        callback = type(time).is_in_sunlight
        result = {'query': 'returned', 'apex_exposure_hook_installed':
                  getattr(callback, '_apex_sunlight_exposure_qol', False),
                  'effective_in_sunlight': callback(time, instance)}
        previous = getattr(callback, '_apex_original', None)
        if callable(previous):
            result['previous_callback_in_sunlight'] = previous(time, instance)
        return result
    except (ValueError, AttributeError, TypeError) as error:
        return {'query': 'failed', 'reason': str(error)}


def status(backend, sim):
    _load(backend)
    members = backend.services.active_household()
    safety = []
    if members:
        for member in members.sim_info_gen():
            instance = member.get_sim_instance()
            safety.append({'sim_id': str(member.id), 'instanced': instance is not None,
                           'is_dying': bool(instance.is_dying) if instance is not None else None,
                           'is_dead': bool(member.is_dead),
                           'death_type': str(member.death_type),
                           'effective_autonomy_state': int(instance.get_autonomy_state_setting()) if instance is not None else None})
    return {'schema': 1, 'sim_id': str(sim.id) if sim else None, 'save_guid': _SAVE,
            'autonomy': _autonomy(backend), 'death': _death(), 'household_safety': safety,
            'sunlight_blocked': bool(sim and str(sim.id) in _SUN),
            'sunlight_exposure': _exposure_status(backend, sim),
            'automatic_umbrellas_blocked': bool(sim and str(sim.id) in _UMBRELLA),
            'appearance_modified': False}


def initialize(backend):
    """Reload per-Sim hooks; optional explicit safety on marked test profiles."""
    install(backend)
    from .test_driver import runtime_identity
    identity = runtime_identity(backend.__file__)
    if not identity.get('test_token'):
        return
    from .overlay_loader import _unlinked
    marker = json.loads(_unlinked(Path(identity['profile']) / '.apex-disposable-profile.json').read_text(encoding='utf-8'))
    if marker.get('validation_safety') is not True or marker.get('token') != identity['test_token']:
        return
    _autonomy(backend, True)
    _death(True)
    from server_commands.clock_commands import set_speed
    client = backend.services.client_manager().get_first_client()
    if client is None:
        raise ValueError('Validation safety needs the loaded native game client.')
    set_speed('paused', 'apex.validation', _connection=client.id)


def dispatch(backend, sim, action, value=None):
    if value not in (None, ''):
        raise ValueError('QoL controls accept no external data payload.')
    _load(backend)
    if action in ('qol_autonomy_pause', 'qol_autonomy_resume'):
        _autonomy(backend, action.endswith('pause'))
    elif action in ('qol_death_prevent', 'qol_death_restore'):
        _death(action.endswith('prevent'))
    elif action in ('qol_sunlight_on', 'qol_sunlight_off', 'qol_umbrella_on', 'qol_umbrella_off'):
        if sim is None or sim.get_sim_instance() is None:
            raise ValueError('Choose an instanced Sim before changing occult safety.')
        install(backend)
        option = 'sunlight' if 'sunlight' in action else 'umbrella'
        enabled = action.endswith('_on')
        if option == 'sunlight' and enabled:
            buffs = _sun_buffs(backend, sim)
            if not buffs:
                raise ValueError('No installed vampire sunlight buff tuning was identified; nothing changed.')
        _persist(backend, sim, option, enabled)
        if option == 'sunlight':
            if enabled:
                for buff in buffs:
                    sim.remove_buff_by_type(buff)
                if any(sim.has_buff(buff) for buff in buffs):
                    raise ValueError('A vampire sunlight buff remained; do not advance simulation.')
            sim.trait_tracker.update_day_night_tracking_state(force_update=True)
    elif action != 'qol_status':
        raise ValueError('Unknown occult QoL control.')
    return {'ok': True, 'message': 'Native autonomy and occult safety settings read back.',
            'qol': status(backend, sim)}
