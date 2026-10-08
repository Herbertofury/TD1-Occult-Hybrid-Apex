"""Typed real-game test operations, restricted to a marked disposable profile.

No arbitrary Python/console evaluation, no external UI input, no worker-thread
Sim access. Transition submission and completed gameplay proof are distinct.
"""
import base64
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


def snapshot(backend, sim, export_outfits=False):
    persistence = backend.services.get_persistence_service()
    slot = persistence.get_save_slot_proto_buff()
    game_clock = backend.services.game_clock_service()
    household = backend.services.active_household()
    zone = backend.services.current_zone()
    result = {'ok': True, 'zone_id': str(zone.id), 'save_slot': int(slot.slot_id),
              'save_guid': str(persistence.get_save_slot_proto_guid()),
              'household_id': str(household.id) if household is not None else None,
              'clock_speed': int(game_clock.clock_speed), 'sim_now': str(game_clock.now()),
              'in_build_buy': bool(zone.is_in_build_buy)}
    if sim is not None:
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
        if export_outfits:
            from .outfit_snapshot import normalize
            result['sim']['outfit_base64'] = base64.b64encode(blob).decode('ascii')
            result['sim']['appearance_sha256'] = hashlib.sha256(normalize(blob)).hexdigest()
    return result


def dispatch(backend, action, sim_id, value):
    global _LAST_CLIENT_ID
    argument = guard(backend, value)
    if action == 'test_quit':
        from sims4.commands import client_cheat
        manager = backend.services.client_manager()
        client = manager.get_first_client() if manager is not None else None
        connection = client.id if client is not None else _LAST_CLIENT_ID
        if connection is None:
            raise ValueError('No observed native game-client connection for normal quit.')
        client_cheat('quit', connection)
        return {'ok': True, 'transition': 'quit-confirmation-requested', 'game_exit_verified': False,
                'confirmation_required': True, 'message': 'Native Save Game confirmation requested; process exit is not yet verified.'}
    sim = backend._get_sim_info_by_id(sim_id)
    if action in ('test_status', 'test_snapshot'):
        return snapshot(backend, sim, export_outfits=argument == 'outfits')
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
            return {'ok': False, 'outcome': 'unresolved', 'message': 'Creation was submitted but one new Sim was not observed; do not repeat blindly.'}
        created[0].first_name, created[0].last_name = 'Apex', 'Test'
        result = snapshot(backend, created[0])
        result.update({'created_sim_id': str(created[0].id), 'message': 'One disposable test Sim was created and observed in the active household.'})
        return result
    if action == 'test_cas':
        if sim is None or sim.get_sim_instance() is None:
            raise ValueError('CAS entry requires an instanced selected Sim.')
        from server_commands.cas_commands import modify_in_cas
        from server_commands.argument_helpers import OptionalTargetParam
        before = snapshot(backend, sim)
        submitted = modify_in_cas(OptionalTargetParam(str(sim.id)), _connection=client.id)
        return {'ok': bool(submitted), 'transition': 'cas-entry-submitted', 'before': before,
                'cas_visible_verified': False, 'message': 'CAS entry submitted to the real game client; UI completion must be observed separately.'}
    if action == 'test_save':
        persistence = backend.services.get_persistence_service()
        slot = persistence.get_save_slot_proto_buff()
        if slot is None or not int(slot.slot_id) or int(slot.slot_id) == 0xffffffff:
            raise ValueError('Load a real disposable save slot before saving.')
        from server_commands.persistence_commands import override_save_slot
        override_save_slot(int(slot.slot_id), slot.slot_name, auto_save_slot_id=None,
                           ignore_callback=False, _connection=client.id)
        return {'ok': True, 'transition': 'save-submitted', 'slot_id': int(slot.slot_id),
                'save_completed_verified': False, 'message': 'Save submitted; verify the save file and reload before claiming persistence.'}
    raise ValueError('Unknown typed test operation.')
