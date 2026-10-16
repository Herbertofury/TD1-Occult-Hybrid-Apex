"""Protect Python-to-native CAS entry, including cached MCCC client aliases.

No private third-party hooks, scanning timer or guessed return decisions. Every
hybrid household member gets fresh raw originals before the native command.
The existing explicit all-owner review remains authoritative on return.
"""
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
from types import FunctionType
import uuid
import zipfile

from . import cas_bank_transaction as bank, cas_entry_context, cas_ui
from .occult_add_guard import publish
from .overlay_loader import _unlinked

_LOCAL = threading.local()
_COMMANDS = ('sims.exit2cas', 'sims.exit2caswithhouseholdid')
_MCCC_ARCHIVE_SHA256 = 'f5a26bc40c645db9958fb4735a11480fd831540875b17402ff71e46ae62baa50'
_MCCC_MEMBER_SHA256 = '7c4f61dd26554734c53044a25424fdb8b1ef2c330a53c76ceadfdfcd246f7e50'
_MCCC_ALIAS = '\u062e\u062c\u0636\u0637\u062f\u062e\u062f'
_MCCC_CALLBACK = {
    'sha256': '838cdfb519bdcb3b8600cf8ce3e1f8cc2ae95437e94c769799bbc18fd1e361d7',
    'module': 'mc_cmd_center_dlg', 'qualname': 'SimMenuNavigation._modify_household_in_cas',
    'args': ('self', 'source_dialog'), 'flags': 67,
    'constants': (None, 'sims.exit2caswithhouseholdid {} {}'),
    'names': (_MCCC_ALIAS, 'format', '_sim_info', 'id', 'household_id', '_client')}
_MCCC_CLIENT = {
    'sha256': '943a6ba4722c3324f4687ec3d99c8636abc1b547ab2fea291aba82d3738f2254',
    'module': 'sims4.commands', 'qualname': 'client_cheat', 'args': ('s', 'context'), 'flags': 67,
    'constants': (None, 'Invoking client command with invalid context. command: {}, context: {}',
                  'tingyul', ('owner',)),
    'names': ('logger', 'assert_log', '__enable_native_commands', '_commands', 'client_cheat')}


def _function_contract(function, expected, namespace):
    """Pin semantics as well as instructions; never execute uninspected code."""
    if (not isinstance(function, FunctionType) or function.__globals__ is not namespace or
            function.__module__ != expected['module'] or function.__qualname__ != expected['qualname'] or
            function.__defaults__ is not None or function.__kwdefaults__ is not None):
        raise ValueError('Installed MCCC/game callback identity or defaults are unsupported.')
    code = function.__code__
    if (hashlib.sha256(code.co_code).hexdigest() != expected['sha256'] or
            code.co_argcount != len(expected['args']) or code.co_kwonlyargcount != 0 or
            getattr(code, 'co_posonlyargcount', 0) != 0 or code.co_varnames != expected['args'] or
            code.co_flags != expected['flags'] or code.co_consts != expected['constants'] or
            code.co_names != expected['names'] or code.co_freevars or code.co_cellvars):
        raise ValueError('Installed MCCC/game callback bytecode, constants or signature are unsupported.')


def _mccc_callback(profile, backend):
    """Read the pinned installed archive; use already-loaded real functions only."""
    profile = _unlinked(Path(profile))
    if profile.name != 'The Sims 4':
        raise ValueError('MCCC qualification requires the marked disposable profile layout.')
    path = _unlinked(profile / 'Mods' / 'MCCC' / 'mc_cmd_center.ts4script')
    if not path.is_file() or not 0 < path.stat().st_size <= 16 * 1024 * 1024:
        raise ValueError('Installed MCCC qualification archive is unavailable or oversized.')
    with path.open('rb') as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != _MCCC_ARCHIVE_SHA256:
        raise ValueError('Installed MCCC archive differs from the inspected 2026.5.0 contract.')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = [row for row in archive.infolist() if row.filename == 'mc_cmd_center_dlg.pyc']
        if len(rows) != 1 or not 16 < rows[0].file_size <= 4 * 1024 * 1024:
            raise ValueError('Installed MCCC callback member is missing, duplicate or oversized.')
        member = archive.read(rows[0])
    if member[:4] != b'B\r\r\n' or hashlib.sha256(member).hexdigest() != _MCCC_MEMBER_SHA256:
        raise ValueError('Installed MCCC callback member differs from its inspected Python 3.7 bytes.')
    module, version = sys.modules.get('mc_cmd_center_dlg'), sys.modules.get('mc_cmd_version')
    commands, native = sys.modules.get('sims4.commands'), sys.modules.get('_commands')
    if (module is None or version is None or getattr(version, 'VERSION', None) != '2026.5.0' or
            commands is None or native is None):
        raise ValueError('The inspected MCCC and game command modules are not already loaded.')
    navigation = vars(module).get('SimMenuNavigation')
    if not isinstance(navigation, type) or navigation.__module__ != 'mc_cmd_center_dlg':
        raise ValueError('Installed MCCC navigation class is unsupported.')
    function = vars(navigation).get('_modify_household_in_cas')
    _function_contract(function, _MCCC_CALLBACK, vars(module))
    alias = vars(module).get(_MCCC_ALIAS)
    _function_contract(alias, _MCCC_CLIENT, vars(commands))
    if (alias is not getattr(commands, 'client_cheat', None) or
            alias.__globals__.get('_commands') is not native or
            alias.__globals__.get('__enable_native_commands') is not True):
        raise ValueError('MCCC cached game-command alias no longer reaches the inspected native boundary.')
    probe = getattr(native, 'client_cheat', None)
    for _ in range(32):
        if getattr(probe, '_apex_cas_frontdoor', None) is backend:
            break
        probe = getattr(probe, '_apex_original', None)
        if probe is None:
            raise ValueError('The MCCC native-command boundary is not protected by this frontdoor.')
    else:
        raise ValueError('The MCCC command wrapper chain exceeds its supported bound.')
    return function, alias


def mccc_full_entry(backend, sim, client, profile):
    """Invoke the inspected real MCCC callback once, without constructing a dialog.

    This qualifies its full-household command callback, not MCCC's visible
    menus, all MCCC routes, CAS completion or appearance persistence.
    """
    if not getattr(backend, '_APEX_CAS_FRONTDOOR_READY', False):
        raise ValueError('Native CAS entry protection is not installed.')
    parsed = {'sim_id': sim.id, 'household_id': sim.household_id, 'full': True, 'active_id': None}
    selected, hybrids = _live(backend, parsed, client.id)
    if selected is not sim or sim not in hybrids:
        raise ValueError('MCCC qualification requires the exact selected hybrid Sim.')
    pending = getattr(backend, '_APEX_MCCC_CAS_TEST_ATTEMPT', None)
    if isinstance(pending, dict) and pending.get('stage') != 'frontdoor-receipt-verified':
        raise ValueError('An earlier MCCC callback submission is unresolved; do not replay it.')
    for member in hybrids:
        bank.assert_idle(backend, member)
    callback, client_cheat = _mccc_callback(profile, backend)
    roster = [str(member.id) for member in backend.services.active_household().sim_info_gen()]
    prior = getattr(backend, '_APEX_CAS_FRONTDOOR_RECEIPT', None)
    prior_id = prior.get('id') if isinstance(prior, dict) else None
    # Full-edit permission is explicit test setup. The actual CAS command
    # comes only from the real installed MCCC callback and its cached alias.
    client_cheat('cas.fulleditmode', client.id)
    attempt = {'id': uuid.uuid4().hex, 'stage': 'callback-invoked', 'sim_id': str(sim.id),
               'household_id': str(sim.household_id), 'retry_safe': False}
    backend._APEX_MCCC_CAS_TEST_ATTEMPT = attempt
    class Context:
        pass
    context = Context()
    context._sim_info, context._client = sim, client
    result = callback(context, None)
    receipt = getattr(backend, '_APEX_CAS_FRONTDOOR_RECEIPT', None)
    if (result is not None or not isinstance(receipt, dict) or receipt is prior or
            receipt.get('id') == prior_id or not isinstance(receipt.get('id'), str) or
            len(receipt['id']) != 32 or any(c not in '0123456789abcdef' for c in receipt['id']) or
            receipt.get('stage') != 'native-command-returned' or receipt.get('full_household') is not True or
            receipt.get('sim_id') != str(sim.id) or receipt.get('household_id') != str(sim.household_id) or
            receipt.get('roster_sim_ids') != roster):
        raise ValueError('Real MCCC callback lacks a fresh acknowledged normal frontdoor receipt; do not replay.')
    members = receipt.get('members')
    expected = {str(member.id) for member in hybrids}
    if (not isinstance(members, list) or len(members) != len(expected) or
            any(not isinstance(row, dict) or row.get('sim_id') not in expected for row in members) or
            {row['sim_id'] for row in members} != expected or
            any(not isinstance(row.get('checkpoint'), dict) or row['checkpoint'].get('ok') is not True or
                not isinstance(row.get('owner_observation'), dict) or
                row['owner_observation'].get('original_owner', {}).get('complete') is not True for row in members)):
        raise ValueError('MCCC callback did not capture every actual hybrid member; do not replay.')
    path = _unlinked(Path(backend._data_directory()) / ('cas_frontdoor_' + receipt['id'] + '.json'))
    if not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024 * 1024:
        raise ValueError('MCCC normal frontdoor receipt is not durably available; do not replay.')
    with path.open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024 or json.loads(raw.decode('utf-8'), object_pairs_hook=bank._pairs) != receipt:
        raise ValueError('MCCC normal frontdoor receipt differs from its durable evidence; do not replay.')
    rows = [{'sim_id': row['sim_id'], 'form_checkpoint': row['checkpoint'],
             'owner_observation': row['owner_observation']} for row in members]
    selected = next(row for row in rows if row['sim_id'] == str(sim.id))
    attempt['stage'] = 'frontdoor-receipt-verified'
    attempt['frontdoor_id'] = receipt['id']
    return {'ok': True, 'transition': 'cas-entry-submitted',
            'form_checkpoint': selected['form_checkpoint'],
            'household_form_checkpoints': {'ok': True, 'members': rows,
                'household_id': receipt['household_id'], 'roster_sim_ids': roster},
            'native_pair_preparation': receipt['preparation'],
            'original_owner': selected['owner_observation'], 'native_frontdoor': receipt,
            'requested_editor': 'existing-household-full', 'cas_visible_verified': False,
            'mccc_callback': {'version': '2026.5.0', 'method': _MCCC_CALLBACK['qualname'],
                'bytecode_sha256': _MCCC_CALLBACK['sha256'], 'archive_sha256': _MCCC_ARCHIVE_SHA256,
                'member_sha256': _MCCC_MEMBER_SHA256, 'frontdoor_receipt_sha256': hashlib.sha256(raw).hexdigest(),
                'attempt_id': attempt['id'], 'actual_callback_invoked': True,
                'dialog_constructor_invoked': False, 'visible_menu_exercised': False,
                'all_mccc_routes_verified': False, 'appearance_persistence_verified': False,
                'retry_safe': False}}


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
    from .cas_save_boundary import require_installed
    require_installed(backend)
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
