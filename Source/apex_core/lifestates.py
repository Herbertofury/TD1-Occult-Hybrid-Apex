"""Life-state identities are independent of EA's seven-bit occult enum.

Registry entries describe gameplay producers, not invented native flag values.
Only owner-thread inspection runs here; opening a catalog adds/removes nothing.
Appearance variants use the same complete field codec as native occult owners.
"""
import copy
import threading

NATIVE = {'HUMAN': 1, 'ALIEN': 2, 'VAMPIRE': 4, 'MERMAID': 8,
          'WITCH': 16, 'WEREWOLF': 32, 'FAIRY': 64}
ALIASES = {'SPELLCASTER': 'WITCH', 'PLANT_SIM': 'PLANTSIM', 'GRIM_REAPER': 'REAPER',
           'GRIM': 'REAPER', 'IMAGINARYFRIEND': 'IMAGINARY_FRIEND', 'ROBOT': 'SERVO',
           'PATCHY': 'SCARECROW', 'BONEHILDA': 'SKELETON'}
SPECIAL = {
    'PLANTSIM': {'traits': (162668,), 'buffs': (162844,), 'variants': ('plant', 'human'),
                'label': 'PlantSim', 'producer': 'trait-and-buff'},
    'SERVO': {'traits': (218444, 17914856899346771710), 'buffs': (219638,),
              'variants': ('robot', 'human_cc'), 'label': 'Servo / Robot', 'producer': 'trait-and-buff'},
    'GHOST': {'traits': (), 'buffs': (), 'variants': ('ghost', 'living'),
              'label': 'Ghost', 'producer': 'death-tracker'},
    'REAPER': {'traits': (16851,), 'buffs': (), 'variants': ('reaper', 'unrobed'),
               'label': 'Grim Reaper', 'producer': 'trait'},
    'SKELETON': {'traits': (175972, 2104933071391606333), 'buffs': (175971,),
                 'variants': ('skeleton', 'human_cc'), 'label': 'Skeleton / Bonehilda', 'producer': 'trait-and-buff'},
    'SCARECROW': {'traits': (187088,), 'buffs': (190165,), 'variants': ('scarecrow', 'human_cc'),
                  'label': 'Scarecrow / Patchy', 'producer': 'trait-and-buff'},
    'IMAGINARY_FRIEND': {'traits': (453528,), 'buffs': (456067,),
        'variants': ('lil_monster', 'pegacorn', 'spooky_kid', 'wild_child', 'real'),
        'label': 'Imaginary Friend', 'producer': 'imaginary-friend-service'},
}


def name(value):
    if not isinstance(value, str):
        raise ValueError('A life state requires its named identity, not a native flag.')
    result = value.strip().upper().replace(' ', '_').replace('-', '_')
    result = ALIASES.get(result, result)
    if result not in NATIVE and result not in SPECIAL:
        raise ValueError('Unknown life-state identity.')
    return result


def owner_thread(backend, sim):
    expected = getattr(backend, '_APEX_GAME_THREAD_IDENT', None)
    if type(expected) is not int or expected != threading.current_thread().ident:
        raise ValueError('Life-state operations require the canonical game thread.')
    if sim is None or backend._get_sim_info_by_id(str(sim.id)) is not sim:
        raise ValueError('Select the exact existing manager-owned Sim.')


def _trait(backend, sim, identity):
    tuning = backend._get_trait(identity)
    return tuning is not None and sim.trait_tracker.has_trait(tuning)


def _buff(backend, sim, identity):
    manager = backend.services.get_instance_manager(backend.sims4.resources.Types.BUFF)
    tuning = manager.get(identity)
    return tuning is not None and sim.has_buff(tuning)


def _imaginary(backend, sim):
    getter = getattr(backend.services, 'get_imaginary_friend_service', None)
    service = getter() if callable(getter) else None
    if service is None:
        return {'supported': False, 'member': None, 'reason': 'Native Imaginary Friend service unavailable.'}
    member = bool(service.is_imaginary_friend(sim.id))
    result = {'supported': True, 'member': member}
    if member:
        status = service.get_imaginary_friend_status(sim.id)
        child = service.get_child_sim(sim.id)
        doll = service.get_imaginary_friend_doll(sim.id)
        result.update(status=None if status is None else str(status),
                      child_sim_id=None if child is None else str(getattr(child, 'id', child)),
                      doll_object_id=None if doll is None else str(doll))
    return result


def catalog(backend, sim):
    owner_thread(backend, sim)
    tracker, rows = sim.occult_tracker, []
    forms = backend._form_map(tracker)
    for key, flags in NATIVE.items():
        kind = backend._coerce_flags(flags)
        rows.append({'id': key, 'label': 'Spellcaster' if key == 'WITCH' else key.title(),
            'producer': 'native-occult', 'native_flags': flags,
            'member': flags == 1 or bool(backend._has_occult(tracker, kind)),
            'existing_appearance': kind in forms, 'current': flags == backend._get_current_flags(sim),
            'native_membership_switch_supported': True})
    for key, spec in SPECIAL.items():
        observed = {'trait_ids': [str(i) for i in spec['traits'] if _trait(backend, sim, i)],
                    'buff_ids': [str(i) for i in spec['buffs'] if _buff(backend, sim, i)]}
        member = bool(observed['trait_ids'] or observed['buff_ids'])
        if key == 'GHOST':
            observed['death_tracker_is_ghost'] = bool(sim.is_ghost)
            member = observed['death_tracker_is_ghost']
        elif key == 'IMAGINARY_FRIEND':
            observed['service'] = _imaginary(backend, sim)
            # A costume/reward trait alone is not the native service identity.
            member = observed['service']['member']
        rows.append({'id': key, 'label': spec['label'], 'producer': spec['producer'],
                     'native_flags': None, 'member': member, 'observed': observed,
                     'variants': list(spec['variants']),
                     'native_membership_switch_supported': False})
    return {'ok': True, 'sim_id': str(sim.id), 'rows': copy.deepcopy(rows),
            'appearance_modified': False, 'gameplay_modified': False,
            'scope': 'Installed native identities; custom appearance variants are separate owners.'}
