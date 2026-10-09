"""Apex CLI: isolated profiles, bridge readiness, game-thread requests and proof.

This controls the real running game through its production bridge. It does not
claim that EA's graphical executable has a supported headless mode.
"""
import argparse
import json
from pathlib import Path, PureWindowsPath
import sys
import time
import uuid
import zipfile
import urllib.error
import urllib.parse
import urllib.request
from source_manifest import sha256, write_json
import test_profile
import game_launch
import reusable_profile
import candidate_install


class LocalRedirectGuard(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Local game bridge redirects are not allowed.')


def get(path, query=None, timeout=12):
    url = 'http://127.0.0.1:8017' + path
    if query:
        url += '?' + urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
    # No remote endpoint option: this command controls only the local game bridge.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), LocalRedirectGuard())
    with opener.open(url, timeout=timeout) as response:
        if response.headers.get_content_type() != 'application/json':
            raise ValueError('Bridge returned non-JSON content.')
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('Bridge response exceeds the bounded limit.')
    return json.loads(raw)


def require_isolated(state):
    result = test_profile.status(state)
    if not result['ready_to_launch']:
        raise ValueError('The session is not an exact isolated Apex profile; refusing game commands.')
    return result


def verified_identity(state, transport=get):
    require_isolated(state)
    _path, journal, _profile, _original = reusable_profile.load(state)
    expected = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if expected is None:
        raise ValueError('Install the complete candidate before in-game CLI testing.')
    identity = transport('/api/bridge')
    if identity.get('test_token') != journal['token'] or identity.get('script_sha256') != expected:
        raise ValueError('Running bridge does not match this test profile and exact installed script.')
    pid = identity.get('pid')
    if type(pid) is not int or not 0 < pid <= 0xffffffff:
        raise ValueError('Bridge PID must be an exact valid Windows process identity.')
    process = game_launch.observe_game_process(pid)
    if not process or process.get('Id') != pid or not process.get('Path') or PureWindowsPath(process['Path']).name.casefold() != 'ts4_x64.exe':
        raise ValueError('Bridge PID is not an observed Sims 4 DX11 process.')
    return identity


def owned_request(state, action, sim_id=None, occult=None, value=None, seconds=30, transport=get, submission_observer=None):
    identity = verified_identity(state, transport)
    if identity.get('native_cli_available') and action in (
            'test_capture', 'test_input', 'test_studio_ui', 'overlay_status', 'overlay_show', 'overlay_hide', 'overlay_start'):
        _path, journal, _profile, _original = reusable_profile.load(state)
        if value is None:
            value = json.dumps({'test_token': journal['token'], 'value': None})
        request_id = uuid.uuid4().hex
        query = {'action': action, 'value': value, 'request_id': request_id}
        if action == 'test_input':
            from game_focus import requires_elevated_input, native_input_once
            if requires_elevated_input(identity['pid']):
                return native_input_once(state, value, request_id)
            import game_window
            focused = game_window.focus(identity['pid'])
            if focused.get('ok') is False and focused.get('foreground_verified') is False:
                from game_focus import focus_for_input
                focused = focus_for_input(state, identity['pid'], focused)
            if not focused.get('ok') or not focused.get('foreground_verified'):
                return dict(focused, ok=False, input_submitted=False)
            fresh = verified_identity(state, transport)
            if any(fresh.get(key) != identity.get(key) for key in ('pid', 'test_token', 'script_sha256')):
                raise ValueError('Game identity changed after focus; no native input submitted.')
        if submission_observer is not None:
            submission_observer(action, request_id)
        try:
            result = transport('/api/native', query)
        except (OSError, urllib.error.URLError) as error:
            if action == 'test_input':
                # The native UUID cache belongs to this game process. A lost
                # response can follow a completed input or a process restart;
                # resending here cannot establish which one occurred.
                return {'ok': False, 'outcome': 'unresolved', 'request_id': request_id,
                        'input_submitted': None, 'transport_error': str(error),
                        'message': 'Native input completion was not observed. Retain this request ID; do not replay the input.'}
            # Existing non-input controls retain their exact request identity.
            result = transport('/api/native', query)
        if action == 'test_input' and result.get('ok'):
            # The game-owned handler releases its held button/key asynchronously.
            # Do not let the next CLI action move/focus a surface before release.
            time.sleep(0.25)
        return result
    if not identity.get('alarm_ready') and not (action in (
            'test_quit', 'test_capture', 'test_input', 'test_studio_ui', 'overlay_status', 'overlay_show', 'overlay_hide', 'overlay_start',
            'test_snapshot', 'test_status',
            'cas_ui_request', 'cas_ui_result', 'cas_ui_panels', 'cas_ui_diagnostics', 'cas_ui_socket_ack')
            and identity.get('core_tick_ready')):
        raise ValueError('Load the disposable household before in-game commands.')
    request_id = uuid.uuid4().hex
    query = {'action': action, 'sim_id': sim_id, 'occult': occult, 'value': value, 'request_id': request_id}
    if submission_observer is not None:
        submission_observer(action, request_id)
    try:
        result = transport('/api/command', query)
    except (OSError, urllib.error.URLError) as error:
        # An interrupted response does not prove the mutation failed. Poll the
        # predetermined ID; never submit the mutation a second time.
        result = {'request_id': request_id, 'request_state': 'running', 'transport_error': str(error)}
    if result.get('request_state') not in ('pending', 'running'):
        return result
    return poll_request(request_id, seconds, transport=transport)


def poll_request(request_id, seconds=30, transport=get, monotonic=time.monotonic, pause=time.sleep):
    if len(request_id) != 32 or any(char not in '0123456789abcdef' for char in request_id) or not 0 < seconds <= 300:
        raise ValueError('Use a returned request ID and a 0-300 second completion timeout.')
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        row = transport('/api/requests/status', {'request_id': request_id})
        if row['state'] in ('completed', 'failed', 'cancelled'):
            result = dict(row.get('result') or {'ok': False})
            return dict(result, request_id=request_id, request_state=row['state'])
        if row['state'] not in ('pending', 'running', 'unknown'):
            raise ValueError('Unsupported bridge request state.')
        pause(min(0.25, max(0, deadline - monotonic())))
    return {'ok': False, 'outcome': 'unresolved', 'request_id': request_id,
            'message': 'Completion was not observed. Poll this ID; do not repeat the mutation.'}


def wait_for_bridge(seconds, probe=get, monotonic=time.monotonic, pause=time.sleep):
    if not 0 < seconds <= 300:
        raise ValueError('Bridge wait must be between 0 and 300 seconds.')
    deadline = monotonic() + seconds
    last = {'ok': False, 'message': 'Bridge not observed.'}
    while monotonic() < deadline:
        try:
            last = probe('/api/bridge', timeout=min(2, max(0.1, deadline - monotonic())))
            if last.get('ok') and last.get('alarm_ready'):
                return last
        except (OSError, ValueError, urllib.error.URLError) as error:
            last = {'ok': False, 'message': str(error)}
        pause(min(1, max(0, deadline - monotonic())))
    return {'ok': False, 'message': 'Timed out waiting for the game-thread bridge. Load a disposable household.',
            'last_bridge_state': last}


def parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bridge')
    commands.add_parser('logs')
    capabilities = commands.add_parser('capabilities')
    capabilities.add_argument('--state', required=True, type=Path)
    launch = commands.add_parser('launch', help='Plan or execute an isolated launch through the installed EA client')
    launch.add_argument('--game-root', required=True, type=Path)
    launch.add_argument('--state', required=True, type=Path)
    launch.add_argument('--offer-id', help='Verified Sims 4 storefront identity from local EA metadata')
    launch.add_argument('--execute', action='store_true')
    launch.add_argument('--elevate-permission-once', action='store_true',
                        help='If exact EA consent is inaccessible, request normal UAC for one Sims-bound helper; approval remains manual')
    launch.add_argument('--headless', action='store_true', help='Fails explicitly until an actual headless runtime exists')
    ea_update = commands.add_parser('ea-update', help='Inspect or once restart a verified pending EA client update')
    ea_update.add_argument('--state', required=True, type=Path)
    ea_update.add_argument('--work', type=Path, help='External evidence directory; defaults to the profile journal directory')
    ea_update.add_argument('--restart-once', action='store_true', help='Invoke the exact native pending-update action through normal Windows elevation')
    ea_restart = commands.add_parser('ea-restart', help='Restart the exact installed EA client from normal user permissions, preserving account and saves')
    ea_restart.add_argument('operation', choices=('status', 'restart', 'restore'))
    ea_restart.add_argument('--state', required=True, type=Path)
    ea_restart.add_argument('--output', required=True, type=Path)
    ea_restart.add_argument('--seconds', type=float, default=45)
    ea_restart.add_argument('--normal-permissions', action='store_true', help='Reversibly remove only the exact EA HKCU RUNASADMIN token')
    ea_restart.add_argument('--force-if-tray', action='store_true', help='After normal close, explicitly stop only the exact remaining tray-only EA lifetime')
    ea_restart.add_argument('--elevate-close-once', action='store_true', help='Request normal Windows approval for one source-pinned close-only helper; never launches an elevated client')
    ea_restart.add_argument('--recovery', type=Path)
    ea_restart.add_argument('--expected-recovery-sha256')
    compatibility = commands.add_parser('launch-config', help='Inspect or reversibly remove forced game administrator compatibility')
    compatibility.add_argument('operation', choices=('status', 'prepare', 'restore'))
    compatibility.add_argument('--game-root', required=True, type=Path)
    compatibility.add_argument('--state', required=True, type=Path)
    compatibility.add_argument('--receipt', type=Path)
    profile = commands.add_parser('profile', help='Reversible isolated test profile management')
    profile_commands = profile.add_subparsers(dest='profile_command', required=True)
    activate = profile_commands.add_parser('activate')
    activate.add_argument('--profile', required=True, type=Path)
    activate.add_argument('--state', required=True, type=Path)
    activate.add_argument('--artifact', required=True, action='append', type=Path)
    activate.add_argument('--seed-state', type=Path)
    inspect = profile_commands.add_parser('status')
    inspect.add_argument('--state', required=True, type=Path)
    inspect.add_argument('--verify-original', action='store_true')
    restore = profile_commands.add_parser('restore')
    restore.add_argument('--state', required=True, type=Path)
    adopt = profile_commands.add_parser('adopt', help='Use one retained test profile; protected original stays read-only')
    adopt.add_argument('--previous-state', required=True, type=Path)
    adopt.add_argument('--profile', required=True, type=Path)
    adopt.add_argument('--protected-original', required=True, type=Path)
    adopt.add_argument('--state', required=True, type=Path)
    adopt.add_argument('--artifact', type=Path, action='append')
    install = profile_commands.add_parser('install', help='Replace only verified Apex test artifacts in the same test profile')
    install.add_argument('--state', required=True, type=Path)
    install.add_argument('--artifact', required=True, type=Path, action='append')
    bundle = profile_commands.add_parser('install-candidate', help='Install verified packages, script and matching F11 DLL together')
    bundle.add_argument('--state', required=True, type=Path)
    bundle.add_argument('--bundle', required=True, type=Path)
    bundle.add_argument('--experimental-ui', action='store_true')
    bundle.add_argument('--optional', action='store_true')
    backup = profile_commands.add_parser('backup', help='Preserve disposable saves/Tray externally and hash original saves read-only')
    backup.add_argument('--state', required=True, type=Path)
    autosaves = profile_commands.add_parser('recover-autosaves', help='Recover only six disposable autosaves after a verified normal unsaved exit')
    autosaves.add_argument('--state', required=True, type=Path)
    autosaves.add_argument('--backup-manifest', required=True, type=Path)
    autosaves.add_argument('--backup-sha256', required=True)
    autosaves.add_argument('--exit-proof', required=True, type=Path)
    autosaves.add_argument('--exit-sha256', required=True)
    autosaves.add_argument('--output', required=True, type=Path)
    addon = profile_commands.add_parser('mccc', help='Exact minimal MCCC CAS/Dresser interoperability recipe')
    addon.add_argument('operation', choices=('install', 'remove'))
    addon.add_argument('--state', required=True, type=Path)
    addon.add_argument('--archive', type=Path)
    autostart = profile_commands.add_parser('overlay-autostart', help='Toggle automatic native overlay load with the game closed')
    autostart.add_argument('operation', choices=('on', 'off'))
    autostart.add_argument('--state', required=True, type=Path)
    cleanup = profile_commands.add_parser('consolidate', help='Recover retired disposable profile contents then keep one test profile')
    cleanup.add_argument('--state', required=True, type=Path)
    cleanup.add_argument('--previous-state', required=True, type=Path, action='append')
    for name in ('recover', 'preserve-settings'):
        maintenance = profile_commands.add_parser(name)
        maintenance.add_argument('--state', required=True, type=Path)
    wait = commands.add_parser('wait', help='Wait for a loaded zone and production owner queue')
    wait.add_argument('--state', required=True, type=Path)
    wait.add_argument('--seconds', type=float, default=30)
    proof = commands.add_parser('probe', help='Record exact test inputs and read-only runtime evidence')
    proof.add_argument('--state', required=True, type=Path)
    proof.add_argument('--output', required=True, type=Path)
    proof.add_argument('--sim-id')
    request = commands.add_parser('request')
    request.add_argument('action')
    request.add_argument('--state', required=True, type=Path)
    request.add_argument('--sim-id')
    request.add_argument('--occult')
    request.add_argument('--value')
    poll = commands.add_parser('poll')
    poll.add_argument('request_id')
    poll.add_argument('--seconds', type=float, default=30)
    game = commands.add_parser('game', help='Real in-game test controls; requires the marked disposable profile')
    game.add_argument('operation', choices=('status', 'focus', 'capture', 'key', 'click', 'move', 'all-data', 'pause', 'play', 'speed2', 'speed3', 'create-sim', 'cas', 'outfit', 'save', 'snapshot', 'quit', 'shutdown', 'exit', 'resume', 'load', 'map-select', 'map-play', 'live-observe', 'main-menu', 'native-human'))
    game.add_argument('--state', required=True, type=Path)
    game.add_argument('--sim-id')
    game.add_argument('--value')
    game.add_argument('--output', type=Path)
    game.add_argument('--with-overlay', action='store_true')
    game.add_argument('--elevate-once', action='store_true', help='One normal Windows elevation for authenticated game focus only')
    game.add_argument('--key', choices=('F11', 'ESC', 'ENTER', 'TAB', 'SPACE'))
    game.add_argument('--x', type=int)
    game.add_argument('--y', type=int)
    game.add_argument('--width', type=int)
    game.add_argument('--height', type=int)
    game.add_argument('--seconds', type=float, default=60)
    game.add_argument('--slot-id', type=lambda value: int(value, 0), help='Existing normal slot only; required for typed save targeting')
    game.add_argument('--slot-name', help='Bounded explicit save name; required for typed save targeting')
    game.add_argument('--expected-save-sha256', help='Exact current existing target-file hash')
    game.add_argument('--save-guid', help='Exact original native save GUID for save targeting')
    game.add_argument('--household-id', help='Exact existing household identity for save targeting')
    game.add_argument('--world', help='Exact current native world label for one measured played-lot marker')
    game.add_argument('--load-proof', type=Path, help='Exact indexed-load proof preceding the current map')
    game.add_argument('--load-proof-sha256')
    game.add_argument('--recovered-input-proof', type=Path, help='Completed native acknowledgment for the original indexed Play request ID')
    game.add_argument('--recovered-input-sha256')
    game.add_argument('--allow-autosave-drift', action='store_true',
                      help='Record drift only in six existing disposable autosave files; normal saves remain exact')
    game.add_argument('--selection-proof', type=Path, help='Exact selected-household native capture and indexed-save evidence')
    game.add_argument('--selection-proof-sha256')
    game.add_argument('--map-play-proof', type=Path, help='Immutable prior native household Play evidence for read-only Live observation')
    game.add_argument('--map-play-proof-sha256')
    game.add_argument('--expected-current-form', type=int, choices=(1, 2, 4, 8, 16, 32, 64),
                      help='Exact currently observed native form for native-human')
    game.add_argument('--ensure-witch-owner', action='store_true',
                      help='Allow native-human to construct a missing tuned Witch owner without random generation')
    cas = commands.add_parser('cas', help='Semantic native CAS controls; no mouse input')
    cas.add_argument('operation', choices=('panels', 'status', 'panel', 'outfit', 'outfit-add', 'hair-swatch', 'select', 'form-select', 'undo', 'redo', 'result', 'diagnostics', 'return'))
    cas.add_argument('--state', required=True, type=Path)
    cas.add_argument('--sim-id')
    cas.add_argument('--household-id', help='Exact existing household identity required for semantic CAS return')
    cas.add_argument('--settle-ticks', type=int, default=30, help='Native simulation timeline ticks required before leaving Live paused')
    cas.add_argument('--form', dest='form_flags', type=int, choices=(1, 2, 4, 8, 16, 32, 64),
                     help='Exact form actually present in the observed native base/alternate pair')
    cas.add_argument('--expected-layer', type=int, choices=(0, 1), help='Exact currently observed native CAS layer')
    cas.add_argument('--native-session', type=int, help='Exact owner observation session from a fresh CAS status')
    cas.add_argument('--panel')
    cas.add_argument('--category', type=int)
    cas.add_argument('--index', type=int, help='Zero-based existing outfit number')
    cas.add_argument('--data-id', help='Exact decimal native CAS catalog data identity')
    cas.add_argument('--request-id')
    cas.add_argument('--seconds', type=float, help='Wait limit; defaults to 60 seconds for return and 10 for other CAS operations')
    cas.add_argument('--output', type=Path)
    cas_bank = commands.add_parser('cas-bank', help='Durable all-form CAS checkpoint, explicit edit decisions and verified commit')
    cas_bank.add_argument('operation', choices=('begin', 'status', 'observe', 'prepare', 'commit'))
    cas_bank.add_argument('--state', required=True, type=Path)
    cas_bank.add_argument('--sim-id', required=True)
    cas_bank.add_argument('--output', required=True, type=Path)
    cas_bank.add_argument('--seconds', type=float, default=30)
    cas_bank.add_argument('--expected-pending-sha256')
    cas_bank.add_argument('--expected-raw-return-sha256')
    cas_bank.add_argument('--expected-plan-sha256')
    cas_bank.add_argument('--dispositions-file', type=Path)
    cas_bank.add_argument('--dispositions-sha256')
    cas_bank.add_argument('--hair-targets-file', type=Path)
    cas_bank.add_argument('--hair-targets-sha256')
    cas_probe = commands.add_parser('cas-probe', help='Regression probe for already open native CAS; no entry or acceptance')
    cas_probe.add_argument('--state', required=True, type=Path)
    cas_probe.add_argument('--sim-id', required=True)
    cas_probe.add_argument('--output', required=True, type=Path)
    cas_probe.add_argument('--seconds', type=float, default=60)
    cas_probe.add_argument('--step-seconds', type=float, default=30)
    cas_probe.add_argument('--outfit-add', action='store_true', help='Explicitly allow an Everyday second-outfit probe')
    hair_audit = commands.add_parser('cas-hair-audit', help='Retain all outfit metadata and observe hair in verified existing clothing categories twice')
    hair_audit.add_argument('--state', required=True, type=Path)
    hair_audit.add_argument('--sim-id', required=True)
    hair_audit.add_argument('--output', required=True, type=Path)
    hair_audit.add_argument('--seconds', type=float, default=120)
    hair_audit.add_argument('--step-seconds', type=float, default=15)
    reload = commands.add_parser('cas-reload', help='Verify native stored appearances after normal save, exit and restart')
    reload.add_argument('--state', required=True, type=Path)
    reload.add_argument('--sim-id', required=True)
    reload.add_argument('--household-id', required=True)
    reload.add_argument('--save-guid', required=True)
    reload.add_argument('--save-exit-proof', required=True, type=Path)
    reload.add_argument('--expected-proof-sha256', required=True)
    reload.add_argument('--save-proof', type=Path, help='Exact earlier controlled save proof for a seal-preserving unsaved exit')
    reload.add_argument('--expected-save-proof-sha256', help='SHA-256 of the exact controlled save proof')
    reload.add_argument('--output', required=True, type=Path)
    reload.add_argument('--seconds', type=float, default=60)
    reload.add_argument('--settle-ticks', type=int, default=750)
    discard = commands.add_parser('game-discard', help='Normal exit without saving after an exact failed CAS return')
    discard.add_argument('--state', required=True, type=Path)
    discard.add_argument('--sim-id', required=True)
    discard.add_argument('--household-id', required=True)
    discard.add_argument('--save-guid', required=True)
    discard.add_argument('--failed-return-proof', required=True, type=Path)
    discard.add_argument('--expected-proof-sha256', required=True)
    discard.add_argument('--output', required=True, type=Path)
    discard.add_argument('--seconds', type=float, default=60)
    crash = commands.add_parser('cas-crash', help='Preserve a later native crash against an immutable completed CAS entry')
    crash.add_argument('--state', required=True, type=Path)
    crash.add_argument('--entry-proof', required=True, type=Path)
    crash.add_argument('--expected-proof-sha256', required=True)
    crash.add_argument('--output', required=True, type=Path)
    crash_archive = commands.add_parser('cas-crash-archive', help='Archive only never-observed CAS metadata while the crashed disposable game is closed')
    crash_archive.add_argument('--state', required=True, type=Path)
    crash_archive.add_argument('--crash-proof', required=True, type=Path)
    crash_archive.add_argument('--expected-proof-sha256', required=True)
    crash_archive.add_argument('--slot-id', required=True, type=int)
    crash_archive.add_argument('--expected-save-sha256', required=True)
    crash_archive.add_argument('--output', required=True, type=Path)
    captured_archive = commands.add_parser('cas-captured-archive', help='Closed disposable only: preserve and archive an exact never-observed CAS checkpoint; no return/reload claim')
    captured_archive.add_argument('--state', required=True, type=Path)
    captured_archive.add_argument('--entry-proof', required=True, type=Path)
    captured_archive.add_argument('--expected-proof-sha256', required=True)
    captured_archive.add_argument('--slot-id', required=True, type=int)
    captured_archive.add_argument('--expected-save-sha256', required=True)
    captured_archive.add_argument('--output', required=True, type=Path)
    abandon = commands.add_parser('cas-abandon', help='Archive retained failed CAS metadata after a verified restart of the unchanged save')
    abandon.add_argument('--state', required=True, type=Path)
    abandon.add_argument('--sim-id', required=True)
    abandon.add_argument('--household-id', required=True)
    abandon.add_argument('--save-guid', required=True)
    abandon.add_argument('--slot-id', required=True, type=lambda value: int(value, 0))
    abandon.add_argument('--failed-return-proof', required=True, type=Path)
    abandon.add_argument('--expected-proof-sha256', required=True)
    abandon.add_argument('--unsaved-exit-proof', type=Path)
    abandon.add_argument('--expected-unsaved-exit-proof-sha256')
    abandon.add_argument('--observer-failure-proof', type=Path)
    abandon.add_argument('--expected-observer-failure-sha256')
    abandon.add_argument('--expected-save-sha256', required=True)
    abandon.add_argument('--output', required=True, type=Path)
    abandon.add_argument('--seconds', type=float, default=30)
    abandon.add_argument('--allow-auto-save-slot-metadata-only', action='store_true',
                         help='Allow only the native autosave sentinel when archiving metadata; proves no loaded disk slot')
    catalog = commands.add_parser('cas-catalog-audit', help='Audit native CAS panel navigation and retain complete returned catalogs')
    catalog.add_argument('--state', required=True, type=Path)
    catalog.add_argument('--sim-id', required=True)
    catalog.add_argument('--output', required=True, type=Path)
    catalog.add_argument('--panel', dest='panels', action='append')
    catalog.add_argument('--seconds', type=float, default=120)
    catalog.add_argument('--step-seconds', type=float, default=5)
    catalog.add_argument('--step-budget', type=int, default=20)
    studio = commands.add_parser('studio', help='Live/stored-form CAS History and appearance editing on the real game thread')
    studio.add_argument('operation', choices=('status', 'items', 'inventory', 'history', 'record', 'checkpoint', 'recover', 'color-copy', 'color-preview', 'color-inspect', 'color-edit', 'part-inspect', 'part-preview', 'outfit-duplicate', 'open-history', 'open-parts', 'open-cas-history', 'open-cas-parts', 'cancel', 'undo', 'redo', 'jump', 'apply', 'hair-enable', 'hair-disable', 'hair-status'))
    studio.add_argument('--state', required=True, type=Path)
    studio.add_argument('--sim-id')
    studio.add_argument('--form', type=int, help='Explicit existing native/bank form owner; editing does not activate it')
    studio.add_argument('--value')
    studio.add_argument('--output', type=Path, help='New external JSON evidence file for complete native history records')
    studio.add_argument('--value-file', type=Path, help='UTF-8 JSON for numeric color edits')
    studio.add_argument('--all-forms', action='store_true', help='Read every existing observed form without activating it')
    studio.add_argument('--catalog-manifest', type=Path, help='Exact external CAS resource cache manifest for verified names/images/package provenance')
    studio.add_argument('--catalog-manifest-sha256')
    studio.add_argument('--jobs', type=int, default=4, help='Inventory read-only page concurrency, one through four')
    test = commands.add_parser('test', help='Run actual gameplay suites, unpause to settle, record proof and leave paused')
    test.add_argument('suite', choices=('color-cycle', 'hybrid-cycle'))
    test.add_argument('--state', required=True, type=Path)
    test.add_argument('--sim-id', required=True)
    test.add_argument('--output', required=True, type=Path)
    test.add_argument('--target', default='0:HAIR')
    test.add_argument('--occult', action='append', choices=('VAMPIRE', 'WITCH', 'WEREWOLF', 'ALIEN', 'MERMAID', 'FAIRY'))
    test.add_argument('--settle-seconds', type=float, default=3)
    return parser


def execute(args):
    if args.command == 'cas-captured-archive':
        from cas_crash_archive import archive
        return archive(args.state, args.entry_proof, args.expected_proof_sha256,
            args.slot_id, args.expected_save_sha256, args.output, entry_only=True)
    if args.command == 'cas-crash-archive':
        from cas_crash_archive import archive
        return archive(args.state, args.crash_proof, args.expected_proof_sha256,
            args.slot_id, args.expected_save_sha256, args.output)
    if args.command == 'cas-crash':
        from cas_crash import record
        return record(args.state, args.entry_proof, args.expected_proof_sha256, args.output)
    if args.command == 'ea-update':
        import ea_update
        work = args.work if args.work is not None else args.state.resolve().parent
        return (ea_update.restart_once if args.restart_once else ea_update.inspect)(work=work, state=args.state)
    if args.command == 'ea-restart':
        import ea_restart
        return ea_restart.run(args.state, args.operation, args.output,
            normal_permissions=args.normal_permissions, force_if_tray=args.force_if_tray,
            elevate_close_once=args.elevate_close_once, recovery=args.recovery,
            expected_recovery_sha256=args.expected_recovery_sha256, seconds=args.seconds)
    if args.command == 'launch-config':
        import launch_compatibility
        require_isolated(args.state)
        if args.operation == 'status':
            return dict(launch_compatibility.plan(args.game_root), ok=True)
        if args.receipt is None:
            raise ValueError('A recovery receipt is required for compatibility changes.')
        return launch_compatibility.configure(args.state, args.game_root, args.receipt, restore=args.operation == 'restore')
    if args.command == 'launch':
        return game_launch.launch(args.game_root, args.state, args.execute, args.headless, offer_id=args.offer_id,
                                 elevate_permission_once=args.elevate_permission_once)
    if args.command == 'profile':
        if args.profile_command == 'overlay-autostart':
            from overlay_configuration import configure
            return configure(args.state, args.operation == 'on')
        if args.profile_command == 'mccc':
            import test_addons
            return test_addons.configure(args.state, args.archive, remove=args.operation == 'remove')
        if args.profile_command == 'install-candidate':
            return candidate_install.install(args.state, args.bundle, args.experimental_ui, args.optional)
        if args.profile_command == 'backup':
            return candidate_install.backup(args.state)
        if args.profile_command == 'recover-autosaves':
            from test_autosave_recovery import recover
            return recover(args.state, args.backup_manifest, args.backup_sha256,
                           args.exit_proof, args.exit_sha256, args.output)
        if args.profile_command == 'adopt':
            return reusable_profile.adopt(args.previous_state, args.profile, args.state, args.protected_original, args.artifact)
        if args.profile_command == 'install':
            return reusable_profile.install(args.state, args.artifact)
        if args.profile_command == 'recover':
            return reusable_profile.recover(args.state)
        if args.profile_command == 'preserve-settings':
            return reusable_profile.preserve_settings(args.state)
        if args.profile_command == 'consolidate':
            return reusable_profile.consolidate(args.state, args.previous_state)
        if args.profile_command == 'activate':
            return test_profile.activate(args.profile, args.state, args.artifact, seed_state=args.seed_state)
        if args.profile_command == 'restore':
            return test_profile.restore(args.state)
        return test_profile.status(args.state, args.verify_original)
    if args.command == 'bridge':
        return get('/api/bridge')
    if args.command == 'logs':
        return get('/api/logs', {'count': 180})
    if args.command == 'poll':
        return poll_request(args.request_id, args.seconds)
    if args.command == 'capabilities':
        return owned_request(args.state, 'overlay_capabilities')
    profile = require_isolated(args.state)
    if args.command == 'cas-bank':
        from cas_bank_cli import run
        return run(args, owned_request)
    if args.command == 'game-discard':
        from game_discard import observe
        return observe(args.state, args.output, verified_identity(args.state), owned_request,
                       args.failed_return_proof, args.expected_proof_sha256, args.sim_id,
                       args.household_id, args.save_guid, seconds=args.seconds, transport=get)
    if args.command == 'cas-abandon':
        from cas_abandon import observe
        recovery_options = {}
        if args.observer_failure_proof is not None or args.expected_observer_failure_sha256 is not None:
            if args.observer_failure_proof is None or args.expected_observer_failure_sha256 is None:
                raise ValueError('Observer failure proof and its exact hash must be supplied together.')
            recovery_options.update(observer_failure_proof=args.observer_failure_proof,
                expected_observer_failure_sha256=args.expected_observer_failure_sha256)
            if args.unsaved_exit_proof is None or args.expected_unsaved_exit_proof_sha256 is None:
                raise ValueError('Observer failure recovery also requires the separate unsaved exit proof and hash.')
        if args.unsaved_exit_proof is not None or args.expected_unsaved_exit_proof_sha256 is not None:
            if args.unsaved_exit_proof is None or args.expected_unsaved_exit_proof_sha256 is None:
                raise ValueError('Unsaved exit proof and its exact hash must be supplied together.')
            recovery_options.update(unsaved_exit_proof=args.unsaved_exit_proof,
                expected_unsaved_exit_proof_sha256=args.expected_unsaved_exit_proof_sha256)
        return observe(args.state, args.output, verified_identity(args.state), owned_request,
                       args.failed_return_proof, args.expected_proof_sha256, args.expected_save_sha256,
                       args.sim_id, args.household_id, args.save_guid, args.slot_id,
                       seconds=args.seconds, transport=get,
                       allow_auto_save_slot_metadata_only=args.allow_auto_save_slot_metadata_only,
                       **recovery_options)
    if args.command == 'cas-reload':
        from cas_reload import observe
        if (args.save_proof is None) != (args.expected_save_proof_sha256 is None):
            raise ValueError('A controlled save proof and its exact SHA-256 must be supplied together.')
        return observe(args.state, args.output, verified_identity(args.state), owned_request,
                       args.save_exit_proof, args.expected_proof_sha256, args.sim_id,
                       args.household_id, args.save_guid, seconds=args.seconds,
                       settle_ticks=args.settle_ticks, transport=get,
                       save_proof=args.save_proof, expected_save_proof_sha256=args.expected_save_proof_sha256)
    if args.command == 'cas-catalog-audit':
        from cas_catalog_audit import run
        return run(args.state, args.output, verified_identity(args.state), owned_request,
                   args.sim_id, seconds=args.seconds, step_seconds=args.step_seconds,
                   panels=args.panels, step_budget=args.step_budget, transport=get)
    if args.command == 'test':
        from runtime_tests import RuntimeTest
        return RuntimeTest(args.state, args.sim_id, args.output, owned_request).run(
            args.suite, args.target, tuple(args.occult or ('VAMPIRE', 'WITCH')), args.settle_seconds)
    if args.command == 'wait':
        return wait_for_bridge(args.seconds)
    if args.command == 'probe':
        output = test_profile.unlinked(args.output)
        active = Path(profile['profile'])
        original = Path(profile['original'])
        if any(output == path or path in output.parents for path in (active, original)):
            raise ValueError('Proof output must be outside both game profiles.')
        bridge = get('/api/bridge')
        actions = {}
        if bridge.get('alarm_ready'):
            for action in ('bridge_status', 'bodytype_live_audit', 'status'):
                actions[action] = owned_request(args.state, action, sim_id=args.sim_id)
        result = {'schema': 1, 'ok': bool(bridge.get('alarm_ready')) and bool(actions) and all(row.get('ok') for row in actions.values()),
                  'proof_scope': 'Isolated packaged bridge and read-only actions only; gameplay/CAS/save/reload gates remain open.',
                  'headless_game_runtime': False, 'profile': profile, 'bridge': bridge, 'actions': actions}
        write_json(output, result)
        return result
    if args.command == 'studio':
        if args.operation == 'inventory':
            if args.output is None or args.value is not None or args.value_file is not None:
                raise ValueError('Inventory needs one new JSON output and uses typed paging automatically.')
            from studio_inventory import collect
            return collect(args.state, args.output, verified_identity(args.state), owned_request,
                           args.sim_id, form=args.form, all_forms=args.all_forms,
                           catalog_manifest=args.catalog_manifest,
                           catalog_manifest_sha256=args.catalog_manifest_sha256,
                           identity_provider=verified_identity, jobs=args.jobs)
        if args.all_forms or args.catalog_manifest is not None or args.catalog_manifest_sha256 is not None:
            raise ValueError('All-form/catalog options are specific to the inventory operation.')
        output = None
        if args.output is not None:
            _, _, active, original = reusable_profile.load(args.state)
            output = reusable_profile.writable(args.output)
            if (output.exists() or output.suffix.lower() != '.json' or output == Path(args.state).resolve() or
                    any(output == root or root in output.parents for root in (active, original))):
                raise ValueError('Studio receipts require one new external JSON filename before any command.')

        def studio_receipt(result):
            if output is None:
                return result
            write_json(output, result)
            return dict(result, proof=str(output), proof_sha256=sha256(output))

        if args.operation in ('open-history', 'open-parts', 'open-cas-history', 'open-cas-parts'):
            if not args.sim_id:
                raise ValueError('An explicit Sim ID is required for Studio UI selection.')
            _, data, _, _ = reusable_profile.load(args.state)
            return studio_receipt(owned_request(args.state, 'test_studio_ui', value=json.dumps({'test_token': data['token'],
                'value': {'sim_id': args.sim_id, 'tab': args.operation[5:].replace('-', '_')}})))
        value = args.value
        if args.value_file:
            if value is not None or args.value_file.stat().st_size > 2048:
                raise ValueError('Supply one bounded Studio value or value file.')
            value = args.value_file.read_text(encoding='utf-8')
        if args.form is not None:
            value = json.dumps({'form': args.form, 'value': value})
        result = owned_request(args.state, 'studio_' + args.operation.replace('-', '_'), args.sim_id, value=value)
        return studio_receipt(result)
    if args.command == 'cas':
        if args.seconds is None:
            args.seconds = 60 if args.operation == 'return' else 10
        if args.operation == 'return':
            if args.output is None:
                raise ValueError('Semantic CAS return requires a new external JSON proof filename.')
            from cas_return import observe
            return observe(args.state, args.output, verified_identity(args.state), owned_request,
                           args.sim_id, args.household_id, seconds=args.seconds,
                           settle_ticks=args.settle_ticks, transport=get)
        from cas_client import execute as cas_execute
        return cas_execute(args, owned_request)
    if args.command == 'cas-probe':
        from cas_runtime_probe import run
        return run(args.state, args.output, verified_identity(args.state), owned_request, args.sim_id,
                   seconds=args.seconds, step_seconds=args.step_seconds, everyday_second=args.outfit_add, transport=get)
    if args.command == 'cas-hair-audit':
        from cas_hair_audit import run
        return run(args.state, args.output, verified_identity(args.state), owned_request, args.sim_id,
                   seconds=args.seconds, step_seconds=args.step_seconds, transport=get)
    if args.command == 'game':
        if args.operation == 'live-observe':
            if args.output is None:
                raise ValueError('Read-only paused Live observation needs one new external proof.')
            from game_live_observe import observe
            return observe(args.state, args.output, verified_identity(args.state), owned_request,
                           args.sim_id, args.household_id, args.save_guid, args.slot_id,
                           args.expected_save_sha256, args.map_play_proof, args.map_play_proof_sha256,
                           identity_provider=verified_identity)
        if args.operation == 'map-play':
            if args.output is None or args.value is not None:
                raise ValueError('Map Play requires a new external proof and explicit selected-household parameters.')
            from game_map_play import observe
            return observe(args.state, args.output, verified_identity(args.state), owned_request,
                           args.sim_id, args.household_id, args.save_guid, args.slot_id,
                           args.expected_save_sha256, args.selection_proof,
                           args.selection_proof_sha256, seconds=args.seconds,
                           identity_provider=verified_identity)
        if args.operation == 'map-select':
            if args.output is None or args.value is not None:
                raise ValueError('Measured map selection requires a new external proof and explicit saved-household parameters.')
            from game_map import select_marker
            return select_marker(args.state, args.output, verified_identity(args.state), owned_request,
                                 args.sim_id, args.household_id, args.save_guid, args.slot_id,
                                 args.expected_save_sha256, args.world, args.load_proof,
                                 args.load_proof_sha256, args.recovered_input_proof,
                                 args.recovered_input_sha256, identity_provider=verified_identity,
                                 allow_autosave_drift=args.allow_autosave_drift)
        if args.operation == 'load':
            if args.output is None or args.value is not None:
                raise ValueError('Exact existing-save load requires a new external proof and named save parameters.')
            from game_load import observe
            return observe(args.state, args.output, verified_identity(args.state), owned_request,
                           args.sim_id, args.household_id, args.save_guid, args.slot_id,
                           args.slot_name, args.expected_save_sha256, seconds=args.seconds,
                           identity_provider=verified_identity)
        if args.operation == 'native-human':
            if not all((args.sim_id, args.household_id, args.save_guid)) or args.expected_current_form is None or args.value is not None:
                raise ValueError('Native Human selection requires exact Sim/household/save GUID and observed current form.')
            _path, journal, profile, original = reusable_profile.load(args.state)
            output = reusable_profile.writable(args.output) if args.output else None
            if output is not None and (output.exists() or output.suffix.casefold() != '.json' or
                    any(output == root or root in output.parents for root in (profile, original))):
                raise ValueError('Use a new external JSON native-selection proof outside both profiles.')
            result = owned_request(args.state, 'test_native_form_select', args.sim_id,
                value=json.dumps({'test_token': journal['token'], 'value': {
                    'form_flags': 1, 'expected_current_form_flags': args.expected_current_form,
                    'household_id': args.household_id, 'save_guid': args.save_guid,
                    'ensure_witch_owner': args.ensure_witch_owner}}), seconds=args.seconds)
            if output is not None:
                write_json(output, result)
                return {'ok': result.get('ok') is True, 'output': str(output), 'sha256': sha256(output),
                        'outcome': result.get('outcome'), 'request_id': result.get('request_id'),
                        'native_switch_attempted': result.get('native_switch_attempted'),
                        'witch_owner_created': result.get('witch_owner_created'),
                        'bank_appearance_restored': result.get('bank_appearance_restored'),
                        'unpaused_visual_verification_required': result.get('unpaused_visual_verification_required')}
            return result
        if args.operation == 'cas' and args.output is not None:
            from cas_transition import observe
            return observe(args.state, args.output, verified_identity(args.state), owned_request,
                           sim_id=args.sim_id, value=args.value, seconds=args.seconds, transport=get)
        if args.operation == 'resume':
            if args.output is None:
                raise ValueError('A new external JSON proof filename is required for Resume.')
            from game_lifecycle import resume
            return resume(args.state, args.output, verified_identity(args.state), owned_request,
                          sim_id=args.sim_id, seconds=args.seconds,
                          household_id=args.household_id, save_guid=args.save_guid)
        if args.operation == 'shutdown':
            if args.output is None:
                raise ValueError('A new external JSON proof filename is required for normal Save and Exit.')
            from game_lifecycle import shutdown
            return shutdown(args.state, args.output, verified_identity(args.state), owned_request)
        if args.operation == 'main-menu':
            if args.output is None or not all((args.sim_id, args.household_id, args.save_guid)):
                raise ValueError('Unsaved main-menu exit requires a new external proof and exact native identities.')
            from game_main_menu import observe
            return observe(args.state, args.output, verified_identity(args.state), owned_request,
                           args.sim_id, args.household_id, args.save_guid)
        if args.operation == 'exit':
            if args.output is None or not all((args.sim_id, args.household_id, args.save_guid)):
                raise ValueError('Unsaved normal exit requires a new external proof and exact Sim/household/save GUID.')
            from game_lifecycle import shutdown
            return shutdown(args.state, args.output, verified_identity(args.state), owned_request,
                            save=False, sim_id=args.sim_id, household_id=args.household_id,
                            save_guid=args.save_guid)
        if args.operation == 'focus':
            if args.elevate_once:
                if args.output is None:
                    raise ValueError('One-shot game focus requires a new external --output proof.')
                from game_focus import elevate_once
                return elevate_once(args.state, args.output)
            import game_window
            return game_window.focus(verified_identity(args.state)['pid'])
        _path, data, _profile, _original = reusable_profile.load(args.state)
        if args.operation == 'capture':
            if args.output is None:
                raise ValueError('An external proof image filename is required.')
            from game_capture import capture
            return capture(args.state, args.output, owned_request, overlay=args.with_overlay)
        direct_output = None
        if args.output is not None and args.operation not in ('all-data', 'save'):
            direct_output = reusable_profile.writable(args.output)
            if (direct_output.exists() or direct_output.suffix.casefold() != '.json' or
                    any(direct_output == root or root in direct_output.parents for root in (_profile, _original))):
                raise ValueError('Use a new external JSON command receipt outside both profiles.')
        def receipt(result):
            if direct_output is None:
                return result
            write_json(direct_output, result)
            return dict(result, proof=str(direct_output), proof_sha256=sha256(direct_output))
        if args.operation in ('key', 'click', 'move'):
            if args.width is None or args.height is None or not 1 <= args.width <= 8192 or not 1 <= args.height <= 8192:
                raise ValueError('Supply the observed client viewport width/height.')
            if args.operation == 'key':
                if args.key is None:
                    raise ValueError('A supported key is required.')
                x, y = {'F11': 122, 'ESC': 27, 'ENTER': 13, 'TAB': 9, 'SPACE': 32}[args.key], 0
            else:
                x, y = args.x, args.y
                if x is None or y is None or not 0 <= x < args.width or not 0 <= y < args.height:
                    raise ValueError('Click must be inside the observed game viewport.')
            argument = {'command': 2 if args.operation == 'key' else 3 if args.operation == 'move' else 1, 'x': x, 'y': y,
                        'width': args.width, 'height': args.height}
            return receipt(owned_request(args.state, 'test_input', value=json.dumps({'test_token': data['token'], 'value': argument})))
        value = json.dumps({'test_token': data['token'], 'value': args.value})
        if args.operation == 'all-data':
            if not args.sim_id:
                raise ValueError('An explicit Sim ID is required for complete data capture.')
            output = reusable_profile.writable(args.output) if args.output else None
            if output is not None and (output.exists() or any(output == root or root in output.parents for root in (_profile, _original))):
                raise ValueError('Use a new complete-data evidence file outside both profiles.')
            result = owned_request(args.state, 'test_all_data', args.sim_id, value=value)
            if output is not None and result.get('ok'):
                write_json(output, result)
                return {'ok': True, 'output': str(output), 'sha256': sha256(output), 'native_sha256': result['native_sha256'],
                        'native_bytes': result['native_bytes'], 'schema_messages': len(result['field_schemas']),
                        'runtime_only_fields_complete': False, 'all_edit_handlers_complete': False}
            return result
        if args.operation == 'save':
            if args.output is None or args.value is not None:
                raise ValueError('Typed existing-target save requires a new external proof and named save parameters.')
            from game_save import observe
            return observe(args.state, args.output, verified_identity(args.state), owned_request, args.sim_id,
                           args.slot_id, args.slot_name, args.expected_save_sha256, args.save_guid,
                           args.household_id, seconds=args.seconds, transport=get)
        quit_pid = get('/api/bridge')['pid'] if args.operation == 'quit' else None
        result = owned_request(args.state, 'test_' + args.operation.replace('-', '_'), args.sim_id, value=value)
        if args.operation == 'quit' and result.get('ok'):
            pid = quit_pid
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if not any(row['Id'] == pid for row in game_launch.running_game_processes()):
                    return receipt(dict(result, game_exit_verified=True, pid=pid))
                time.sleep(0.5)
            return receipt(dict(result, ok=False, outcome='unresolved', game_exit_verified=False,
                message='Normal quit was submitted once but process exit was not observed.'))
        return receipt(result)
    return owned_request(args.state, args.action, args.sim_id, args.occult, args.value)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get('ok') else 1
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, urllib.error.URLError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
