"""CLI for the running Apex bridge; requests exercise its production queue."""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def get(path, query=None, timeout=12):
    url = 'http://127.0.0.1:8017' + path
    if query:
        url += '?' + urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
    # No remote endpoint option: this command controls only the local game bridge.
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.headers.get_content_type() != 'application/json':
            raise ValueError('Bridge returned non-JSON content.')
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('Bridge response exceeds the bounded limit.')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bridge')
    commands.add_parser('logs')
    request = commands.add_parser('request')
    request.add_argument('action')
    request.add_argument('--sim-id')
    request.add_argument('--occult')
    request.add_argument('--value')
    poll = commands.add_parser('poll')
    poll.add_argument('request_id')
    args = parser.parse_args()
    try:
        if args.command == 'bridge':
            result = get('/api/bridge')
        elif args.command == 'logs':
            result = get('/api/logs', {'count': 180})
        elif args.command == 'poll':
            result = get('/api/requests/status', {'request_id': args.request_id})
        else:
            result = get('/api/command', {'action': args.action, 'sim_id': args.sim_id,
                                         'occult': args.occult, 'value': args.value})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get('ok') else 1
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
