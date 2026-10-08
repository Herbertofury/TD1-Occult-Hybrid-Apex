"""Apex CLI: isolated profiles, bridge readiness, game-thread requests and proof.

This controls the real running game through its production bridge. It does not
claim that EA's graphical executable has a supported headless mode.
"""
import argparse
import json
from pathlib import Path
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
    processes = game_launch.running_game_processes()
    process = next((row for row in processes if row['Id'] == identity.get('pid')), None)
    if not process or not process.get('Path') or Path(process['Path']).name.lower() != 'ts4_x64.exe':
        raise ValueError('Bridge PID is not an observed Sims 4 DX11 process.')
    return identity


def owned_request(state, action, sim_id=None, occult=None, value=None, seconds=30, transport=get):
    identity = verified_identity(state, transport)
    if identity.get('native_cli_available') and action in (
            'test_capture', 'test_input', 'test_studio_ui', 'overlay_status', 'overlay_show', 'overlay_hide', 'overlay_start'):
        _path, journal, _profile, _original = reusable_profile.load(state)
        if value is None:
            value = json.dumps({'test_token': journal['token'], 'value': None})
        request_id = uuid.uuid4().hex
        query = {'action': action, 'value': value, 'request_id': request_id}
        if action == 'test_input':
            import game_window
            focused = game_window.focus(identity['pid'])
            if not focused.get('ok') or not focused.get('foreground_verified'):
                return dict(focused, ok=False, input_submitted=False)
        try:
            result = transport('/api/native', query)
        except (OSError, urllib.error.URLError):
            # Reuse the exact identity so response loss cannot repeat a click.
            result = transport('/api/native', query)
        if action == 'test_input' and result.get('ok'):
            # The game-owned handler releases its held button/key asynchronously.
            # Do not let the next CLI action move/focus a surface before release.
            time.sleep(0.25)
        return result
    if not identity.get('alarm_ready') and not (action in (
            'test_quit', 'test_capture', 'test_input', 'test_studio_ui', 'overlay_status', 'overlay_show', 'overlay_hide', 'overlay_start',
            'cas_ui_request', 'cas_ui_result', 'cas_ui_panels', 'cas_ui_diagnostics', 'cas_ui_socket_ack')
            and identity.get('core_tick_ready')):
        raise ValueError('Load the disposable household before in-game commands.')
    request_id = uuid.uuid4().hex
    query = {'action': action, 'sim_id': sim_id, 'occult': occult, 'value': value, 'request_id': request_id}
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
    launch.add_argument('--headless', action='store_true', help='Fails explicitly until an actual headless runtime exists')
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
    addon = profile_commands.add_parser('mccc', help='Exact minimal MCCC CAS/Dresser interoperability recipe')
    addon.add_argument('operation', choices=('install', 'remove'))
    addon.add_argument('--state', required=True, type=Path)
    addon.add_argument('--archive', type=Path)
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
    game.add_argument('operation', choices=('status', 'focus', 'capture', 'key', 'click', 'move', 'all-data', 'pause', 'play', 'speed2', 'speed3', 'create-sim', 'cas', 'outfit', 'save', 'snapshot', 'quit', 'shutdown', 'resume'))
    game.add_argument('--state', required=True, type=Path)
    game.add_argument('--sim-id')
    game.add_argument('--value')
    game.add_argument('--output', type=Path)
    game.add_argument('--with-overlay', action='store_true')
    game.add_argument('--key', choices=('F11', 'ESC', 'ENTER', 'TAB', 'SPACE'))
    game.add_argument('--x', type=int)
    game.add_argument('--y', type=int)
    game.add_argument('--width', type=int)
    game.add_argument('--height', type=int)
    game.add_argument('--seconds', type=float, default=60)
    cas = commands.add_parser('cas', help='Semantic native CAS controls; no mouse input')
    cas.add_argument('operation', choices=('panels', 'status', 'panel', 'outfit', 'outfit-add', 'hair-swatch', 'select', 'undo', 'redo', 'result', 'diagnostics'))
    cas.add_argument('--state', required=True, type=Path)
    cas.add_argument('--sim-id')
    cas.add_argument('--panel')
    cas.add_argument('--category', type=int)
    cas.add_argument('--index', type=int, help='Zero-based existing outfit number')
    cas.add_argument('--data-id', help='Exact decimal native CAS catalog data identity')
    cas.add_argument('--request-id')
    cas.add_argument('--seconds', type=float, default=10)
    cas.add_argument('--output', type=Path)
    studio = commands.add_parser('studio', help='Live/stored-form CAS History and appearance editing on the real game thread')
    studio.add_argument('operation', choices=('status', 'history', 'record', 'checkpoint', 'recover', 'color-copy', 'color-preview', 'color-inspect', 'color-edit', 'part-inspect', 'part-preview', 'outfit-duplicate', 'open-history', 'open-parts', 'open-cas-history', 'open-cas-parts', 'cancel', 'undo', 'redo', 'jump', 'apply', 'hair-enable', 'hair-disable', 'hair-status'))
    studio.add_argument('--state', required=True, type=Path)
    studio.add_argument('--sim-id')
    studio.add_argument('--form', type=int, help='Explicit existing native/bank form owner; editing does not activate it')
    studio.add_argument('--value')
    studio.add_argument('--output', type=Path, help='New external JSON evidence file for complete native history records')
    studio.add_argument('--value-file', type=Path, help='UTF-8 JSON for numeric color edits')
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
    if args.command == 'launch-config':
        import launch_compatibility
        require_isolated(args.state)
        if args.operation == 'status':
            return dict(launch_compatibility.plan(args.game_root), ok=True)
        if args.receipt is None:
            raise ValueError('A recovery receipt is required for compatibility changes.')
        return launch_compatibility.configure(args.state, args.game_root, args.receipt, restore=args.operation == 'restore')
    if args.command == 'launch':
        return game_launch.launch(args.game_root, args.state, args.execute, args.headless, offer_id=args.offer_id)
    if args.command == 'profile':
        if args.profile_command == 'mccc':
            import test_addons
            return test_addons.configure(args.state, args.archive, remove=args.operation == 'remove')
        if args.profile_command == 'install-candidate':
            return candidate_install.install(args.state, args.bundle, args.experimental_ui, args.optional)
        if args.profile_command == 'backup':
            return candidate_install.backup(args.state)
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
        if args.operation in ('open-history', 'open-parts', 'open-cas-history', 'open-cas-parts'):
            if not args.sim_id:
                raise ValueError('An explicit Sim ID is required for Studio UI selection.')
            _, data, _, _ = reusable_profile.load(args.state)
            return owned_request(args.state, 'test_studio_ui', value=json.dumps({'test_token': data['token'],
                'value': {'sim_id': args.sim_id, 'tab': args.operation[5:].replace('-', '_')}}))
        value = args.value
        if args.value_file:
            if value is not None or args.value_file.stat().st_size > 2048:
                raise ValueError('Supply one bounded Studio value or value file.')
            value = args.value_file.read_text(encoding='utf-8')
        if args.form is not None:
            value = json.dumps({'form': args.form, 'value': value})
        result = owned_request(args.state, 'studio_' + args.operation.replace('-', '_'), args.sim_id, value=value)
        if args.output is not None:
            _, _, active, original = reusable_profile.load(args.state)
            output = reusable_profile.writable(args.output)
            if args.operation != 'record' or output.exists() or any(output == root or root in output.parents for root in (active, original)):
                raise ValueError('Complete history record output requires a new external filename.')
            if result.get('ok'):
                write_json(output, result)
                return {'ok': True, 'output': str(output), 'sha256': sha256(output), 'history_node': result['history_node'], 'evidence_only': True}
        return result
    if args.command == 'cas':
        from cas_client import execute as cas_execute
        return cas_execute(args, owned_request)
    if args.command == 'game':
        if args.operation == 'resume':
            if args.output is None:
                raise ValueError('A new external JSON proof filename is required for Resume.')
            from game_lifecycle import resume
            return resume(args.state, args.output, verified_identity(args.state), owned_request,
                          sim_id=args.sim_id, seconds=args.seconds)
        if args.operation == 'shutdown':
            if args.output is None:
                raise ValueError('A new external JSON proof filename is required for normal Save and Exit.')
            from game_lifecycle import shutdown
            return shutdown(args.state, args.output, verified_identity(args.state), owned_request)
        if args.operation == 'focus':
            import game_window
            return game_window.focus(verified_identity(args.state)['pid'])
        _path, data, _profile, _original = reusable_profile.load(args.state)
        if args.operation == 'capture':
            if args.output is None:
                raise ValueError('An external proof image filename is required.')
            from game_capture import capture
            return capture(args.state, args.output, owned_request, overlay=args.with_overlay)
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
            return owned_request(args.state, 'test_input', value=json.dumps({'test_token': data['token'], 'value': argument}))
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
            snapshot = owned_request(args.state, 'test_snapshot', args.sim_id, value=value)
            if not snapshot.get('ok'):
                return snapshot
            slot = snapshot['save_slot']
            if not 0 < slot < 0xffffffff:
                raise ValueError('Refusing the scratch/unsaved slot.')
            save = reusable_profile.writable(_profile / 'saves' / ('Slot_{:08x}.save'.format(slot)))
            prior_time = save.stat().st_mtime_ns if save.exists() else None
            result = owned_request(args.state, 'test_save', args.sim_id, value=value)
            if not result.get('ok'):
                return result
            deadline, previous = time.monotonic() + 15, None
            while time.monotonic() < deadline:
                if save.exists() and save.stat().st_size:
                    stat = save.stat()
                    observed = (stat.st_mtime_ns, stat.st_size, sha256(save))
                    if observed == previous and stat.st_mtime_ns != prior_time:
                        return dict(result, save_completed_file_verified=True, save_reload_verified=False,
                            save_file=str(save), save_sha256=observed[2], save_bytes=observed[1])
                    previous = observed
                time.sleep(0.25)
            return dict(result, ok=False, outcome='unresolved', save_completed_file_verified=False,
                message='Save was submitted once but a completed file rewrite was not observed; do not resubmit blindly.')
        quit_pid = get('/api/bridge')['pid'] if args.operation == 'quit' else None
        result = owned_request(args.state, 'test_' + args.operation.replace('-', '_'), args.sim_id, value=value)
        if args.operation == 'quit' and result.get('ok'):
            pid = quit_pid
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if not any(row['Id'] == pid for row in game_launch.running_game_processes()):
                    return dict(result, game_exit_verified=True, pid=pid)
                time.sleep(0.5)
            return dict(result, ok=False, outcome='unresolved', game_exit_verified=False,
                message='Normal quit was submitted once but process exit was not observed.')
        return result
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
