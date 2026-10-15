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
    def full_check():
        result = test_profile.status(state)
        if not result['ready_to_launch']:
            raise ValueError('The session is not an exact isolated Apex profile; refusing game commands.')
        return result
    from cli_identity_cache import validate
    return validate(state, full_check)


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
            'test_capture', 'test_input', 'test_studio_ui', 'test_preview', 'test_native_cas_probe', 'overlay_status', 'overlay_show', 'overlay_hide', 'overlay_start'):
        _path, journal, _profile, _original = reusable_profile.load(state)
        if value is None:
            value = json.dumps({'test_token': journal['token'], 'value': None})
        request_id = uuid.uuid4().hex
        query = {'action': action, 'value': value, 'request_id': request_id}
        background_click = False
        if action == 'test_input':
            try:
                argument = json.loads(value)['value']
                background_click = (isinstance(argument, dict) and
                    set(argument) == {'command', 'x', 'y', 'width', 'height'} and
                    type(argument.get('command')) is int and argument['command'] == 4)
            except (ValueError, TypeError, KeyError):
                pass
        if action == 'test_input' and not background_click:
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
        if action == 'test_preview':
            raw = json.dumps(query, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('utf-8')
            if len(raw) > 4 * 1024 * 1024: raise ValueError('Native preview request exceeds bound.')
            request = urllib.request.Request('http://127.0.0.1:8017/api/native', data=raw,
                                             headers={'Content-Type': 'application/json'}, method='POST')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), LocalRedirectGuard())
            with opener.open(request, timeout=12) as response:
                try:
                    review = json.loads(value).get('value', {}).get('operation') == 'cas-review'
                except (ValueError, TypeError, AttributeError):
                    review = False
                limit = 4 * 1024 * 1024 if review else 32768
                reply = response.read(limit + 1)
                if len(reply) > limit: raise ValueError('Native preview response exceeds bound.')
                return json.loads(reply)
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
    launch.add_argument('--verified-launch-proof', type=Path, help='Retain the exact earlier successful account launch before EA rotates its logs')
    launch.add_argument('--expected-launch-proof-sha256')
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
    sliders = profile_commands.add_parser('sliders-presets', help='Read/copy owner slider and preset packages into this test profile')
    sliders.add_argument('--state', required=True, type=Path)
    sliders.add_argument('--install', action='store_true')
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
    life = commands.add_parser('lifestate', help='Named independent life-state appearances; game-thread CLI, no screen input')
    life.add_argument('operation', choices=('catalog','list','capture','bind','select'))
    life.add_argument('--state', required=True, type=Path)
    life.add_argument('--sim-id', required=True)
    life.add_argument('--output', required=True, type=Path)
    life.add_argument('--id')
    life.add_argument('--lifestate')
    life.add_argument('--label')
    life.add_argument('--base-form', type=int, choices=(1,2,4,8,16,32,64))
    life.add_argument('--expected-sha256')
    qol = commands.add_parser('qol', help='Game-thread autonomy and occult safety readback; no screen input')
    qol.add_argument('operation', choices=('status', 'autonomy-pause', 'autonomy-resume',
                     'death-prevent', 'death-restore', 'sunlight-on', 'sunlight-off',
                     'umbrella-on', 'umbrella-off', 'arm-test-safety', 'disarm-test-safety'))
    qol.add_argument('--state', required=True, type=Path)
    qol.add_argument('--sim-id')
    save_archive = commands.add_parser('save-intent-archive', help='Retain an old save intent after verified normal unsaved closure')
    save_archive.add_argument('--state', required=True, type=Path)
    save_archive.add_argument('--sim-id', required=True)
    save_archive.add_argument('--failure-proof', required=True, type=Path)
    save_archive.add_argument('--failure-sha256', required=True)
    save_archive.add_argument('--closure-proof', required=True, type=Path)
    save_archive.add_argument('--closure-sha256', required=True)
    save_archive.add_argument('--output', required=True, type=Path)
    entry_observe = commands.add_parser('cas-entry-observe', help='Verify an already accepted CAS entry without submitting it again')
    entry_observe.add_argument('--state', required=True, type=Path)
    entry_observe.add_argument('--sim-id', required=True)
    entry_observe.add_argument('--entry-proof', required=True, type=Path)
    entry_observe.add_argument('--entry-sha256', required=True)
    entry_observe.add_argument('--output', required=True, type=Path)
    poll = commands.add_parser('poll')
    poll.add_argument('request_id')
    poll.add_argument('--seconds', type=float, default=30)
    game = commands.add_parser('game', help='Real in-game test controls; requires the marked disposable profile')
    game.add_argument('operation', choices=('status', 'focus', 'capture', 'key', 'click', 'move', 'all-data', 'pause', 'play', 'speed2', 'speed3', 'create-sim', 'cas', 'outfit', 'save', 'snapshot', 'quit', 'shutdown', 'exit', 'resume', 'load', 'map-select', 'map-play', 'live-observe', 'main-menu', 'native-human', 'growth-probe', 'native-cas-probe'))
    game.add_argument('--state', required=True, type=Path)
    game.add_argument('--sim-id')
    game.add_argument('--value')
    game.add_argument('--output', type=Path)
    game.add_argument('--with-overlay', action='store_true')
    game.add_argument('--elevate-once', action='store_true', help='One normal Windows elevation for authenticated game focus only')
    game.add_argument('--key', choices=('F11', 'ESC', 'ENTER', 'TAB', 'SPACE'))
    game.add_argument('--background', action='store_true',
                      help='Capture, Resume, normal exit and clicks without foreground handoffs or OS cursor movement')
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
    cas.add_argument('operation', choices=('panels', 'status', 'panel', 'outfit', 'outfit-add', 'hair-swatch', 'select', 'form-select', 'layer-select', 'member-select', 'undo', 'redo', 'result', 'diagnostics', 'return',
        'catalog', 'variants', 'preset', 'select-layer', 'remove', 'layers', 'layer-add', 'layer-remove', 'layer-move', 'swatches', 'swatch', 'physique', 'body-types', 'body-type',
        'modifiers', 'color-sliders', 'hair-matching', 'hair-match', 'voices', 'voice-actor', 'voice-pitch',
        'walkstyles', 'walkstyle', 'detail-status', 'detail-mode', 'filters', 'filter-clear', 'occults', 'occult-view', 'occult-cache-view'))
    cas.add_argument('--state', required=True, type=Path)
    cas.add_argument('--sim-id')
    cas.add_argument('--target-sim-id', help='Existing household member identity for semantic member-select')
    cas.add_argument('--household-id', help='Exact existing household identity required for semantic CAS return')
    cas.add_argument('--settle-ticks', type=int, default=30, help='Native simulation timeline ticks required before leaving Live paused')
    cas.add_argument('--form', dest='form_flags', type=int, choices=(1, 2, 4, 8, 16, 32, 64),
                     help='Exact form actually present in the observed native base/alternate pair')
    cas.add_argument('--expected-layer', type=int, choices=(0, 1), help='Exact currently observed native CAS layer')
    cas.add_argument('--target-layer', type=int, choices=(0, 1), help='Explicit native primary/alternate layer; supports Vampire pairs with the same occult type')
    cas.add_argument('--occult-type', type=int, help='Exact existing native membership for an occult-view request')
    cas.add_argument('--expected-all-occults', type=int, help='Complete membership mask from the fresh native CAS status')
    cas.add_argument('--owned-mask', type=int, help='Research-only: actual pre-entry membership mask; requires marked disposable profile')
    cas.add_argument('--native-session', type=int, help='Exact owner observation session from a fresh CAS status')
    cas.add_argument('--panel')
    cas.add_argument('--category', type=int)
    cas.add_argument('--index', type=int, help='Zero-based existing outfit number')
    cas.add_argument('--data-id', help='Exact decimal native CAS catalog data identity')
    cas.add_argument('--base-data-id', help='Exact returned wing base bound to its selected color data ID')
    cas.add_argument('--offset', type=int, default=0, help='Catalog page offset; every page remains accessible')
    cas.add_argument('--limit', type=int, default=8, help='Items per transport packet, 1-32')
    cas.add_argument('--body-type', type=int, help='Exact body type returned by the native catalog')
    cas.add_argument('--layer-index', type=int, default=-1, help='Exact native layer index; -1 for ordinary color modifiers')
    cas.add_argument('--layer-id', type=int, default=0, help='Exact native layer identity; 0 for ordinary modifiers, medical 127 protected')
    for name in ('hue', 'opacity', 'saturation', 'brightness'):
        cas.add_argument('--' + name, type=float, help='Finite value within this equipped part\'s returned native range')
    cas.add_argument('--flags', type=int, help='Exact native human hair matching bitmask, 0-63')
    cas.add_argument('--actor-index', type=int, help='Zero-based index in the complete eligible native voice inventory')
    cas.add_argument('--enabled', action=argparse.BooleanOptionalAction, default=None,
                     help='Explicit desired detailed edit mode state; use --no-enabled to leave it')
    cas.add_argument('--target-index', type=int, help='Destination index for a layer move')
    cas.add_argument('--swatch-type', type=int, help='Native palette type from cas panels')
    cas.add_argument('--color-index', type=int, default=0, help='Existing fur palette slot')
    cas.add_argument('--physique-type', type=int, choices=(0, 1), help='0 weight, 1 muscle')
    cas.add_argument('--value', type=float, help='Finite slider value; voice uses its returned min/max, physique uses 0-1')
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
    household_cas = commands.add_parser('cas-household-commit', help='Commit each fresh household CAS checkpoint with explicit Sim/form edit intent')
    household_cas.add_argument('--state', required=True, type=Path)
    household_cas.add_argument('--entry-proof', required=True, type=Path)
    household_cas.add_argument('--entry-sha256', required=True)
    household_cas.add_argument('--accept', action='append', help='Keep a returned edit only for this exact SIM_ID:FORM; restore other changed forms')
    household_cas.add_argument('--output', required=True, type=Path)
    household_cas.add_argument('--seconds', type=float, default=60)
    household_cas.add_argument('--resume-proof', type=Path, help='Resume a retained batch stopped before sending its final request')
    household_cas.add_argument('--resume-sha256', help='Exact hash of that retained household proof; unresolved UUIDs are never replayed')
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
    failed_archive = commands.add_parser('cas-failed-commit-archive', help='Preserve a closed disposable native-readback failure after normal unsaved exit; no replay or save writes')
    failed_archive.add_argument('--state', required=True, type=Path)
    failed_archive.add_argument('--commit-proof', required=True, type=Path)
    failed_archive.add_argument('--expected-proof-sha256', required=True)
    failed_archive.add_argument('--unsaved-exit-proof', required=True, type=Path)
    failed_archive.add_argument('--expected-unsaved-exit-proof-sha256', required=True)
    failed_archive.add_argument('--expected-bank-sha256', required=True)
    failed_archive.add_argument('--slot-id', required=True, type=int)
    failed_archive.add_argument('--expected-save-sha256', required=True)
    failed_archive.add_argument('--output', required=True, type=Path)
    journal_archive = commands.add_parser('cas-journal-archive', help='Preserve a closed disposable raw-observed capacity failure without replay or save writes')
    journal_archive.add_argument('--state', required=True, type=Path)
    journal_archive.add_argument('--failed-return-proof', required=True, type=Path)
    journal_archive.add_argument('--expected-proof-sha256', required=True)
    journal_archive.add_argument('--closure-proof', required=True, type=Path)
    journal_archive.add_argument('--closure-proof-sha256', required=True)
    journal_archive.add_argument('--slot-id', required=True, type=int)
    journal_archive.add_argument('--expected-save-sha256', required=True)
    journal_archive.add_argument('--output', required=True, type=Path)
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
    captured_archive.add_argument('--before-proof', type=Path, help='Exact earlier same-runtime native appearances for older MCCC receipts without before context')
    captured_archive.add_argument('--expected-before-sha256')
    frontdoor_archive = commands.add_parser('cas-frontdoor-archive', help='Closed disposable only: preserve a Source entry after an exact later cold appearance comparison')
    for name in ('state', 'entry-path', 'cold-path', 'output'):
        frontdoor_archive.add_argument('--' + name, type=Path, required=True)
    for name in ('entry-hash', 'cold-hash', 'save-hash'):
        frontdoor_archive.add_argument('--' + name, required=True)
    frontdoor_archive.add_argument('--slot-id', type=int, required=True)
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
    workbench = commands.add_parser('cas-workbench', help='Discover every native CAS panel and optionally exercise exact returned items without clicks')
    workbench.add_argument('--state', required=True, type=Path)
    workbench.add_argument('--sim-id', required=True)
    workbench.add_argument('--output', required=True, type=Path)
    workbench.add_argument('--panel', dest='panels', action='append', help='Omit to visit the complete installed panel registry')
    workbench.add_argument('--edit', action='store_true', help='Exercise different exact returned native items; separate Live retention testing is required')
    workbench.add_argument('--step-seconds', type=float, default=12)
    catalog = commands.add_parser('cas-catalog-audit', help='Audit native CAS panel navigation and retain complete returned catalogs')
    catalog.add_argument('--state', required=True, type=Path)
    catalog.add_argument('--sim-id', required=True)
    catalog.add_argument('--output', required=True, type=Path)
    catalog.add_argument('--panel', dest='panels', action='append')
    catalog.add_argument('--seconds', type=float, default=120)
    catalog.add_argument('--step-seconds', type=float, default=5)
    catalog.add_argument('--step-budget', type=int, default=20)
    library = commands.add_parser('live-cas-catalog', help='Search all CASPs in explicit source packages without a CAS room or game input')
    library.add_argument('operation', choices=('build', 'query', 'resolve', 'serve'))
    library.add_argument('--index', required=True, type=Path)
    library.add_argument('--input', type=Path, help='JSON array of exact path/origin package sources')
    library.add_argument('--expected-index-sha256')
    library.add_argument('--query', default='')
    library.add_argument('--body-type', type=int)
    library.add_argument('--origin', choices=('mod', 'ea'))
    library.add_argument('--name-mode', choices=('preferred', 'package', 'code'), default='preferred')
    library.add_argument('--author', default='', help='Exact creator filename tag; inferred CC tags are unverified')
    library.add_argument('--sort', choices=('name', 'package', 'creator', 'id'), default='name')
    library.add_argument('--grouped', action='store_true', help='One CAS item card per native swatch family (schema 3 index)')
    library.add_argument('--offset', type=int, default=0)
    library.add_argument('--limit', type=int, default=60)
    library.add_argument('--part-id')
    library.add_argument('--tray-root', type=Path, help='Explicit read-only Tray folder for the F11 gallery')
    switch_archive = commands.add_parser('switch-archive-unsaved',help='Archive a failed switch after exact unsaved closure; no native replay')
    switch_archive.add_argument('--state',required=True,type=Path)
    switch_archive.add_argument('--bank',required=True,type=Path)
    switch_archive.add_argument('--expected-bank-sha256',required=True)
    switch_archive.add_argument('--closure-proof',required=True,type=Path)
    switch_archive.add_argument('--closure-sha256',required=True)
    switch_archive.add_argument('--sim-id',required=True)
    switch_archive.add_argument('--household-id',required=True)
    switch_archive.add_argument('--save-guid',required=True)
    switch_archive.add_argument('--slot-id',required=True,type=int)
    switch_archive.add_argument('--expected-save-sha256',required=True)
    switch_archive.add_argument('--output',required=True,type=Path)
    studio = commands.add_parser('studio', help='Live/stored-form CAS History and appearance editing on the real game thread')
    studio.add_argument('operation', choices=('status', 'items', 'inventory', 'preview-snapshot', 'history', 'record', 'checkpoint', 'recover', 'color-copy', 'color-preview', 'color-inspect', 'color-edit', 'color-live', 'part-inspect', 'part-preview', 'catalog-preview', 'catalog-live', 'shape-inspect', 'shape-preview', 'shape-live', 'shape-add-preview', 'shape-add-live', 'outfit-duplicate', 'copy-appearance', 'paste-preview', 'paste-live', 'werewolf-ea-preview', 'clipboard-export', 'open-library', 'open-history', 'open-parts', 'open-cas-history', 'open-cas-parts', 'cancel', 'undo', 'redo', 'jump', 'apply', 'hair-enable', 'hair-disable', 'hair-status'))
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
    preview = commands.add_parser('preview', help='Memory-only independent F11 3D Sim and animation controls without game input')
    preview.add_argument('operation', choices=('start', 'health', 'sliders', 'render', 'status', 'view', 'mode', 'workspace', 'clear', 'library-select', 'thumbnail', 'gallery-query', 'gallery-select', 'gallery-view'))
    preview.add_argument('--apply-mode', choices=('live', 'preview'), help='F11 edit policy; selecting a mode does not change the Sim')
    preview.add_argument('--state', required=True, type=Path)
    preview.add_argument('--slider-catalog', type=Path, help='External read-only slider/preset resource catalog')
    preview.add_argument('--slider-catalog-sha256')
    preview.add_argument('--game-root', type=Path, default=Path(r'C:\Games\The Sims 4'))
    preview.add_argument('--sim-id')
    preview.add_argument('--form', type=int, help='Exact observed Studio appearance owner, including named life-state handles')
    preview.add_argument('--outfit-index', type=int)
    preview.add_argument('--preview-id', help='Exact prepared CC/color try-on; does not apply it')
    preview.add_argument('--scene-id', help='Exact scene identity for stale-safe camera/animation controls')
    preview.add_argument('--values', type=Path, help='JSON camera/animation values, or workspace layout/columns/tab/catalog query')
    preview.add_argument('--output', type=Path, help='New external JSON proof; no assets are exported')
    stress = commands.add_parser('household-stress', help='Whole-roster native retention and complete CAS coverage gates')
    stress.add_argument('operation', choices=('plan', 'capture', 'verify', 'cycle'))
    stress.add_argument('--state', required=True, type=Path)
    stress.add_argument('--sim-id', dest='sim_ids', action='append', required=True)
    stress.add_argument('--household-id', required=True)
    stress.add_argument('--save-guid', required=True)
    stress.add_argument('--output', required=True, type=Path)
    stress.add_argument('--baseline', type=Path)
    stress.add_argument('--baseline-sha256')
    stress.add_argument('--settle-seconds', type=float, default=2)
    household = commands.add_parser('household',help='Typed native multi-Sim household and disposable Tray round trips')
    household.add_argument('operation',choices=('capabilities','records','export-records','export-tray','load-tray','recover-import','finish-import'))
    household.add_argument('--state',required=True,type=Path)
    household.add_argument('--sim-id',required=True)
    household.add_argument('--values',required=True,type=Path)
    household.add_argument('--template',type=Path)
    household.add_argument('--name')
    household.add_argument('--archive',type=Path,help='New external review ZIP; unverified generated entries are never installed into Tray')
    household.add_argument('--source-file',type=Path,help='Exact external native household record file, read only')
    household.add_argument('--output',type=Path)
    household.add_argument('--settle-seconds',type=float,default=3,help='Simulation time for queued native spawns; leaves the disposable game paused')
    tray = commands.add_parser('tray', help='Exact native Tray groups, represented appearances and cross-form selective paste')
    tray.add_argument('operation', choices=('list', 'inspect', 'export', 'import', 'clipboard', 'paste', 'preview'))
    tray.add_argument('--folder', type=Path)
    tray.add_argument('--household', type=Path)
    tray.add_argument('--expected-sha256')
    tray.add_argument('--item', help='Exact native .trayitem filename')
    tray.add_argument('--archive', type=Path)
    tray.add_argument('--inspection', type=Path)
    tray.add_argument('--state', type=Path)
    tray.add_argument('--source-sim-id')
    tray.add_argument('--form', type=int, choices=(1,2,4,8,16,32,64))
    tray.add_argument('--target-sim-id')
    tray.add_argument('--target-form', type=int, choices=(1,2,4,8,16,32,64))
    tray.add_argument('--selection', type=Path, help='Explicit fields/outfits/source_outfit/target_outfit/body_types JSON')
    tray.add_argument('--outfit-index', type=int, help='Exact existing source Tray outfit for independent preview')
    tray.add_argument('--apply-immediately', action='store_true', help='Paste commits immediately; default is reviewable try-on')
    tray.add_argument('--output', type=Path)
    test = commands.add_parser('test', help='Run actual gameplay suites, unpause to settle, record proof and leave paused')
    test.add_argument('suite', choices=('color-cycle', 'live-color', 'hybrid-cycle'))
    test.add_argument('--state', required=True, type=Path)
    test.add_argument('--sim-id', required=True)
    test.add_argument('--output', required=True, type=Path)
    test.add_argument('--target', default='0:HAIR')
    test.add_argument('--occult', action='append', choices=('VAMPIRE', 'WITCH', 'WEREWOLF', 'ALIEN', 'MERMAID', 'FAIRY'))
    test.add_argument('--settle-seconds', type=float, default=3)
    test.add_argument('--form', type=int, choices=(1, 2, 4, 8, 16, 32, 64),
                      help='Explicit existing native owner for the focus-free live-color regression')
    test.add_argument('--edits-file', type=Path, help='Bounded JSON map of numeric channel values for live-color')
    test.add_argument('--settle-ticks', type=int, default=30)
    test.add_argument('--seconds', type=float, default=60)
    return parser


def execute(args):
    if args.command == 'lifestate':
        from lifestate_cli import run
        return run(args, owned_request)
    if args.command == 'cas-entry-observe':
        from cas_entry_observe import observe as observe_accepted_entry
        return observe_accepted_entry(args.state, args.entry_proof, args.entry_sha256,
            args.sim_id, args.output, owned_request, verified_identity)
    if args.command == 'save-intent-archive':
        from save_intent_archive import archive as archive_save_intent
        return archive_save_intent(args.state, args.failure_proof, args.failure_sha256,
            args.closure_proof, args.closure_sha256, args.sim_id, args.output,
            owned_request, verified_identity)
    if args.command == 'qol':
        if args.operation in ('arm-test-safety', 'disarm-test-safety'):
            _, journal, profile, _ = reusable_profile.load(args.state)
            from test_profile import require_closed as qol_require_closed
            qol_require_closed()
            marker_path = reusable_profile.writable(profile / '.apex-disposable-profile.json')
            marker = json.loads(marker_path.read_text(encoding='utf-8'))
            if marker.get('token') != journal['token'] or marker.get('disposable') is not True:
                raise ValueError('Disposable profile identity changed.')
            marker['validation_safety'] = args.operation == 'arm-test-safety'
            write_json(marker_path, marker)
            return {'ok': True, 'validation_safety': marker['validation_safety'],
                    'normal_save_modified': False, 'scope': 'one-marked-test-profile-next-load'}
        return owned_request(args.state, 'qol_' + args.operation.replace('-', '_'), args.sim_id)
    if args.command == 'household-stress':
        from household_stress import run
        return run(args)
    if args.command=='switch-archive-unsaved':
        from switch_archive import archive
        return archive(args.state,args.bank,args.expected_bank_sha256,args.closure_proof,args.closure_sha256,
            args.sim_id,args.household_id,args.save_guid,args.slot_id,args.expected_save_sha256,args.output)
    if args.command=='household':
        from household_cli import execute as household_execute
        return household_execute(args)
    if args.command == 'tray':
        from tray_cli import execute as tray_execute
        return tray_execute(args)
    if args.command == 'preview':
        from preview_cli import execute as preview_execute
        return preview_execute(args)
    if args.command == 'live-cas-catalog':
        from live_cas_catalog import build, query, resolve
        if args.operation == 'build':
            if args.input is None or args.input.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('Provide a bounded explicit package-source JSON array.')
            return build(json.loads(args.input.read_text(encoding='utf-8')), args.index)
        if args.expected_index_sha256 is None:
            raise ValueError('Use the exact SHA256 returned by catalog build.')
        if args.operation == 'serve':
            from live_cas_browser import serve
            return serve(args.index, args.expected_index_sha256, args.tray_root)
        if args.operation == 'resolve':
            return resolve(args.index, args.expected_index_sha256, args.part_id)
        return query(args.index, args.expected_index_sha256, args.query, args.body_type,
            args.origin, args.name_mode, args.offset, args.limit, author=args.author, sort=args.sort, grouped=args.grouped)
    if args.command == 'cas-failed-commit-archive':
        from cas_failed_commit_archive import archive
        return archive(args.state, args.commit_proof, args.expected_proof_sha256,
            args.unsaved_exit_proof, args.expected_unsaved_exit_proof_sha256, args.expected_bank_sha256,
            args.slot_id, args.expected_save_sha256, args.output)
    if args.command == 'cas-journal-archive':
        from cas_journal_archive import archive
        return archive(args.state, args.failed_return_proof, args.expected_proof_sha256,
            args.closure_proof, args.closure_proof_sha256, args.slot_id, args.expected_save_sha256, args.output)
    if args.command == 'cas-frontdoor-archive':
        from cas_frontdoor_archive import archive
        return archive(args.state, args.entry_path, args.entry_hash, args.cold_path, args.cold_hash,
                       args.slot_id, args.save_hash, args.output)
    if args.command == 'cas-captured-archive':
        from cas_crash_archive import archive
        return archive(args.state, args.entry_proof, args.expected_proof_sha256,
            args.slot_id, args.expected_save_sha256, args.output, entry_only=True,
            before_proof=args.before_proof, expected_before_sha256=args.expected_before_sha256)
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
        options = {}
        if args.verified_launch_proof is not None or args.expected_launch_proof_sha256 is not None:
            options.update(verified_launch_proof=args.verified_launch_proof, expected_launch_proof_sha256=args.expected_launch_proof_sha256)
        return game_launch.launch(args.game_root, args.state, args.execute, args.headless, offer_id=args.offer_id,
                                  elevate_permission_once=args.elevate_permission_once, **options)
    if args.command == 'profile':
        if args.profile_command == 'sliders-presets':
            import owner_slider_addons
            return (owner_slider_addons.install if args.install else owner_slider_addons.plan)(args.state)
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
    if args.command == 'cas-household-commit':
        from cas_household_commit import run
        return run(args, verified_identity(args.state), owned_request)
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
    if args.command == 'cas-workbench':
        from cas_workbench import run
        return run(args.state, args.output, verified_identity(args.state), owned_request, args.sim_id,
                   edit=args.edit, panels=args.panels, step_seconds=args.step_seconds)
    if args.command == 'cas-catalog-audit':
        from cas_catalog_audit import run
        return run(args.state, args.output, verified_identity(args.state), owned_request,
                   args.sim_id, seconds=args.seconds, step_seconds=args.step_seconds,
                   panels=args.panels, step_budget=args.step_budget, transport=get)
    if args.command == 'test':
        if args.suite == 'live-color':
            if args.form is None or args.edits_file is None:
                raise ValueError('Live-color testing requires an explicit --form and --edits-file.')
            raw = args.edits_file.read_bytes()
            if len(raw) > 2048:
                raise ValueError('Color test values exceed their bound.')
            from live_color_probe import run
            return run(args.state, args.sim_id, args.form, args.target, json.loads(raw),
                       args.output, owned_request, verified_identity,
                       settle_ticks=args.settle_ticks, seconds=args.seconds)
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

        if args.operation in ('open-library', 'open-history', 'open-parts', 'open-cas-history', 'open-cas-parts'):
            if not args.sim_id:
                raise ValueError('An explicit Sim ID is required for Studio UI selection.')
            _, data, _, _ = reusable_profile.load(args.state)
            return studio_receipt(owned_request(args.state, 'test_studio_ui', value=json.dumps({'test_token': data['token'],
                'value': {'sim_id': args.sim_id, 'tab': args.operation[5:].replace('-', '_')}})))
        value = args.value
        if args.value_file:
            if value is not None or args.value_file.stat().st_size > (8192 if args.operation in ('paste-preview', 'paste-live') else 2048):
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
        if args.operation == 'native-cas-probe':
            from native_cas_probe_cli import run
            return run(args.state,args.output,owned_request)
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
            map_request, map_options = owned_request, {}
            if args.background:
                from functools import partial
                import game_capture
                from game_lifecycle import background_request
                map_request = background_request(owned_request)
                map_options['capture'] = partial(game_capture.capture, background=True)
            return observe(args.state, args.output, verified_identity(args.state), map_request,
                           args.sim_id, args.household_id, args.save_guid, args.slot_id,
                           args.expected_save_sha256, args.selection_proof,
                           args.selection_proof_sha256, seconds=args.seconds,
                           identity_provider=verified_identity, **map_options)
        if args.operation == 'map-select':
            if args.output is None or args.value is not None:
                raise ValueError('Measured map selection requires a new external proof and explicit saved-household parameters.')
            from game_map import select_marker
            map_request, map_options = owned_request, {}
            if args.background:
                from functools import partial
                import game_capture
                from game_lifecycle import background_request
                map_request = background_request(owned_request)
                map_options['capture'] = partial(game_capture.capture, background=True)
            return select_marker(args.state, args.output, verified_identity(args.state), map_request,
                                 args.sim_id, args.household_id, args.save_guid, args.slot_id,
                                 args.expected_save_sha256, args.world, args.load_proof,
                                 args.load_proof_sha256, args.recovered_input_proof,
                                 args.recovered_input_sha256, identity_provider=verified_identity,
                                 allow_autosave_drift=args.allow_autosave_drift, **map_options)
        if args.operation == 'load':
            if args.output is None or args.value is not None:
                raise ValueError('Exact existing-save load requires a new external proof and named save parameters.')
            from game_load import observe
            load_request, load_options = owned_request, {}
            if args.background:
                from functools import partial
                import game_capture
                from game_lifecycle import background_request
                load_request = background_request(owned_request)
                load_options['capture'] = partial(game_capture.capture, background=True)
            return observe(args.state, args.output, verified_identity(args.state), load_request,
                           args.sim_id, args.household_id, args.save_guid, args.slot_id,
                           args.slot_name, args.expected_save_sha256, seconds=args.seconds,
                           identity_provider=verified_identity, **load_options)
        if args.operation == 'growth-probe':
            if not all((args.sim_id, args.household_id, args.save_guid)) or args.value not in ('1','2','4','8','16','32','64'):
                raise ValueError('Native detached growth preparation requires exact Sim/household/save and one stored form value.')
            _, session, active, original = reusable_profile.load(args.state)
            output = reusable_profile.writable(args.output) if args.output else None
            if output is not None and (output.exists() or output.suffix.lower() != '.json' or
                    any(output == p or p in output.parents for p in (active, original))):
                raise ValueError('Use one new external growth-probe receipt.')
            result = owned_request(args.state, 'test_growth_probe', args.sim_id, value=json.dumps({
                'test_token': session['token'], 'value': dict(household_id=args.household_id,
                    save_guid=args.save_guid, form_flags=int(args.value))}))
            if output is not None:write_json(output,result)
            return result
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
            options = {}
            request = owned_request
            if args.background:
                from game_lifecycle import background_request
                from game_capture import capture
                from functools import partial
                request = background_request(owned_request)
                options = dict(background=True, capture=partial(capture, background=True))
            return resume(args.state, args.output, verified_identity(args.state), request,
                          sim_id=args.sim_id, seconds=args.seconds,
                          household_id=args.household_id, save_guid=args.save_guid, **options)
        if args.operation == 'shutdown':
            if args.output is None:
                raise ValueError('A new external JSON proof filename is required for normal Save and Exit.')
            from game_lifecycle import shutdown
            options = {}
            request = owned_request
            if args.background:
                from game_lifecycle import background_request
                from game_capture import capture
                from functools import partial
                request = background_request(owned_request)
                options = dict(capture=partial(capture, background=True))
            return shutdown(args.state, args.output, verified_identity(args.state), request, **options)
        if args.operation == 'main-menu':
            if args.output is None or not all((args.sim_id, args.household_id, args.save_guid)):
                raise ValueError('Unsaved main-menu exit requires a new external proof and exact native identities.')
            from game_main_menu import observe
            request, options = owned_request, {}
            if args.background:
                from game_lifecycle import background_request
                from game_capture import capture
                from functools import partial
                request = background_request(owned_request)
                options = dict(capture=partial(capture, background=True))
            return observe(args.state, args.output, verified_identity(args.state), request,
                           args.sim_id, args.household_id, args.save_guid, **options)
        if args.operation == 'exit':
            if args.output is None or not all((args.sim_id, args.household_id, args.save_guid)):
                raise ValueError('Unsaved normal exit requires a new external proof and exact Sim/household/save GUID.')
            from game_lifecycle import shutdown
            options = {}
            request = owned_request
            if args.background:
                from game_lifecycle import background_request
                from game_capture import capture
                from functools import partial
                request = background_request(owned_request)
                options = dict(capture=partial(capture, background=True))
            return shutdown(args.state, args.output, verified_identity(args.state), request,
                            save=False, sim_id=args.sim_id, household_id=args.household_id,
                            save_guid=args.save_guid, **options)
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
            return capture(args.state, args.output, owned_request, overlay=args.with_overlay, background=args.background)
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
            if args.background and args.operation != 'click':
                raise ValueError('Background input currently supports window-addressed clicks only.')
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
            argument = {'command': 4 if args.background else 2 if args.operation == 'key' else 3 if args.operation == 'move' else 1, 'x': x, 'y': y,
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
        # JSON escapes preserve Unicode filenames on legacy Windows consoles.
        # Encoding a successful mutation receipt must never fail afterwards.
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0 if result.get('ok') else 1
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, urllib.error.URLError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
