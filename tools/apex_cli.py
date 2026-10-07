"""Apex CLI: isolated profiles, bridge readiness, game-thread requests and proof.

This controls the real running game through its production bridge. It does not
claim that EA's graphical executable has a supported headless mode.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from source_manifest import write_json
import test_profile
import game_launch


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
    commands.add_parser('capabilities')
    launch = commands.add_parser('launch', help='Plan or execute an isolated launch through the installed EA client')
    launch.add_argument('--game-root', required=True, type=Path)
    launch.add_argument('--state', required=True, type=Path)
    launch.add_argument('--execute', action='store_true')
    launch.add_argument('--headless', action='store_true', help='Fails explicitly until an actual headless runtime exists')
    profile = commands.add_parser('profile', help='Reversible isolated test profile management')
    profile_commands = profile.add_subparsers(dest='profile_command', required=True)
    activate = profile_commands.add_parser('activate')
    activate.add_argument('--profile', required=True, type=Path)
    activate.add_argument('--state', required=True, type=Path)
    activate.add_argument('--artifact', required=True, action='append', type=Path)
    inspect = profile_commands.add_parser('status')
    inspect.add_argument('--state', required=True, type=Path)
    inspect.add_argument('--verify-original', action='store_true')
    restore = profile_commands.add_parser('restore')
    restore.add_argument('--state', required=True, type=Path)
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
    return parser


def execute(args):
    if args.command == 'launch':
        return game_launch.launch(args.game_root, args.state, args.execute, args.headless)
    if args.command == 'profile':
        if args.profile_command == 'activate':
            return test_profile.activate(args.profile, args.state, args.artifact)
        if args.profile_command == 'restore':
            return test_profile.restore(args.state)
        return test_profile.status(args.state, args.verify_original)
    if args.command == 'bridge':
        return get('/api/bridge')
    if args.command == 'logs':
        return get('/api/logs', {'count': 180})
    if args.command == 'poll':
        return get('/api/requests/status', {'request_id': args.request_id})
    if args.command == 'capabilities':
        return get('/api/command', {'action': 'overlay_capabilities'})
    profile = require_isolated(args.state)
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
                actions[action] = get('/api/command', {'action': action, 'sim_id': args.sim_id})
        result = {'schema': 1, 'ok': bool(bridge.get('alarm_ready')) and bool(actions) and all(row.get('ok') for row in actions.values()),
                  'proof_scope': 'Isolated packaged bridge and read-only actions only; gameplay/CAS/save/reload gates remain open.',
                  'headless_game_runtime': False, 'profile': profile, 'bridge': bridge, 'actions': actions}
        write_json(output, result)
        return result
    return get('/api/command', {'action': args.action, 'sim_id': args.sim_id,
                                 'occult': args.occult, 'value': args.value})


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get('ok') else 1
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
