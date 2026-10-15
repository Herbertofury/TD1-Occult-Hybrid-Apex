"""Protect Python-to-native CAS entry, including cached MCCC client aliases.

No private third-party hooks, scanning timer or guessed return decisions. Every
hybrid household member gets fresh raw originals before the native command.
The existing explicit all-owner review remains authoritative on return.
"""
from contextlib import contextmanager
from pathlib import Path
import threading
import uuid

from . import cas_bank_transaction as bank, cas_entry_context, cas_ui
from .occult_add_guard import publish
from .overlay_loader import _unlinked

_LOCAL = threading.local()
_COMMANDS = ('sims.exit2cas', 'sims.exit2caswithhouseholdid')


def _uint(value):
    if (not value.isascii() or not value.isdecimal() or str(int(value)) != value or
            not 0 < int(value) < 1 << 64):
        raise ValueError('CAS entry requires canonical native unsigned identities.')
    return int(value)


def route(command):
    if not isinstance(command, str):
        return None
    parts = command.split()
    if not parts or parts[0].lower() not in _COMMANDS:
        return None
    name = parts[0].lower()
    if len(parts) not in (3, 4):
        raise ValueError('Unrecognized native CAS entry arguments; no entry submitted.')
    sim_id, household_id = _uint(parts[1]), _uint(parts[2])
    full = name == _COMMANDS[1]
    active_id = None
    if len(parts) == 4:
        if full:
            if parts[3] != 'career':
                raise ValueError('Unrecognized native household CAS mode.')
        else:
            active_id = _uint(parts[3])
    return {'sim_id': sim_id, 'household_id': household_id, 'full': full, 'active_id': active_id}


def _live(backend, parsed, connection):
    if threading.current_thread().ident != backend._APEX_GAME_THREAD_IDENT:
        raise ValueError('CAS entry requires the canonical game thread.')
    services = backend.services
    zone, household = services.current_zone(), services.active_household()
    client = services.client_manager().get_first_client()
    sim = backend._get_sim_info_by_id(str(parsed['sim_id']))
    if (zone is None or zone.is_zone_running is not True or zone.is_in_build_buy is not False or
            client is None or type(connection) is not int or connection != client.id or
            household is None or household.id != parsed['household_id'] or sim is None or
            sim.id != parsed['sim_id'] or sim.household_id != household.id or sim.get_sim_instance() is None):
        raise ValueError('CAS command does not belong to the exact running Live household/client.')
    if parsed['active_id'] is not None and services.get_active_sim().id != parsed['active_id']:
        raise ValueError('CAS command active Sim changed before native entry.')
    members = list(household.sim_info_gen())
    if not 1 <= len(members) <= 8 or sim not in members or len({member.id for member in members}) != len(members):
        raise ValueError('CAS entry household roster is ambiguous.')
    hybrids = []
    for member in members:
        if (member.household_id != household.id or
                backend._get_sim_info_by_id(str(member.id)) is not member):
            raise ValueError('CAS entry member is no longer the native manager owner.')
        forms = backend._form_map(member.occult_tracker)
        if isinstance(forms, dict) and len(forms) >= 3:
            hybrids.append(member)
    return sim, hybrids


@contextmanager
def prepared(backend, sim, full, preparation):
    """One synchronous CLI call, after its own complete capture/projection."""
    if getattr(_LOCAL, 'prepared', None) is not None:
        raise ValueError('Nested native CAS entry is forbidden.')
    capability = {'backend': backend, 'sim': sim, 'full': full, 'preparation': preparation, 'used': False}
    _LOCAL.prepared = capability
    try:
        yield
    finally:
        _LOCAL.prepared = None


def before_entry(backend, parsed, connection):
    sim, hybrids = _live(backend, parsed, connection)
    if not hybrids:
        return None
    capability = getattr(_LOCAL, 'prepared', None)
    projected = capability is not None
    if projected and (capability['backend'] is not backend or capability['sim'] is not sim or
            capability['full'] is not parsed['full'] or capability['used'] or
            capability['preparation'].get('ok') is not True):
        raise ValueError('Native CAS entry scope does not match its prepared receiver capability.')
    # Preflight every member before creating any new checkpoint. An existing
    # phone/CLI capture is reusable only if every native appearance is exact.
    captures, missing = [], []
    for member in hybrids:
        status = bank.status(backend, member)
        if status.get('blocked'):
            held = bank.fresh_entry_checkpoint(backend, member, projected=projected)
            captures.append({'sim_id': str(member.id), 'checkpoint': held})
        else:
            if projected:
                raise ValueError('Prepared CLI entry is missing a household checkpoint.')
            bank.assert_idle(backend, member)
            missing.append(member)
    for member in missing:
        held = bank.begin(backend, member)
        if held.get('ok') is not True:
            raise ValueError('CAS raw household checkpoint was not acknowledged.')
        captures.append({'sim_id': str(member.id), 'checkpoint': held})
    for member in hybrids:
        owner = cas_ui.capture_original_owner(backend, member)
        if owner.get('original_owner', {}).get('complete') is not True:
            raise ValueError('CAS original navigation owner is incomplete; entry blocked.')
        next(row for row in captures if row['sim_id'] == str(member.id))['owner_observation'] = owner
    preparation = capability['preparation'] if projected else cas_entry_context.prepare(backend, sim, parsed['full'])
    if projected:
        capability['used'] = True
    receipt = {'schema': 1, 'id': uuid.uuid4().hex, 'stage': 'native-submit-intent',
               'sim_id': str(sim.id), 'household_id': str(sim.household_id),
               'roster_sim_ids': [str(member.id) for member in backend.services.active_household().sim_info_gen()],
               'full_household': parsed['full'], 'members': captures, 'preparation': preparation,
               'native_appearance_written': False, 'return_requires_independent_member_decisions': True,
               'retry_safe': False}
    path = _unlinked(Path(backend._data_directory()) / ('cas_frontdoor_' + receipt['id'] + '.json'))
    publish(path, receipt)
    backend._APEX_CAS_FRONTDOOR_RECEIPT = receipt
    for row in captures:
        member = backend._get_sim_info_by_id(row['sim_id'])
        bank.mark_entry_submitted(backend, member, row['checkpoint']['expected_pending_sha256'], receipt['id'])
    return path, receipt


def install(backend, commands=None):
    if commands is None:
        import _commands as commands
    previous = commands.client_cheat
    probe = previous
    for _ in range(32):
        if getattr(probe, '_apex_cas_frontdoor', None) is backend:
            return True
        probe = getattr(probe, '_apex_original', None)
        if probe is None:
            break
    def client_cheat(command, connection):
        parsed = route(command)
        if parsed is None:
            return previous(command, connection)
        retained = before_entry(backend, parsed, connection)
        try:
            result = previous(command, connection)
        except BaseException:
            # The command may already have reached native CAS. Keep its intent
            # and originals; neither this wrapper nor a caller may repeat it.
            raise
        if retained is not None:
            path, receipt = retained
            receipt['stage'] = 'native-command-returned'
            publish(path, receipt)
        return result
    client_cheat._apex_cas_frontdoor = backend
    client_cheat._apex_original = previous
    commands.client_cheat = client_cheat
    return True
