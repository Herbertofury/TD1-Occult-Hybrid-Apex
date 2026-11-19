"""Control the F11 CAS-review model and its existing Source queue without input."""
import argparse
import copy
import json
from pathlib import Path
import re
import time

import reusable_profile
from cas_client import IntentEvidence
from cli_identity_cache import session
from source_manifest import sha256


def native_roster(receipt):
    """Python decodes native JSON uint64 IDs exactly, without a JS number hop."""
    if not isinstance(receipt, dict) or receipt.get('ok') is not True or not isinstance(receipt.get('sims'), list):
        raise ValueError('A fresh typed Source Sim roster is unavailable.')
    result = copy.deepcopy(receipt); seen = set()
    for row in result['sims']:
        if not isinstance(row, dict):
            raise ValueError('Source roster row is not typed.')
        value = row.get('id')
        if type(value) is int and 0 < value < 1 << 64:
            value = str(value)
        if not isinstance(value, str) or re.fullmatch('[1-9][0-9]{0,19}', value) is None or int(value) >= 1 << 64 or value in seen:
            raise ValueError('Source roster has a malformed or duplicate native uint64 identity.')
        seen.add(value); row['id'] = value
    return result


def document(path, expected, state, limit):
    journal, _data, active, original = reusable_profile.load(state)
    path = reusable_profile.writable(path)
    if (path == journal or any(path == root or root in path.parents for root in (active, original)) or
            path.suffix.lower() != '.json' or not path.is_file() or
            not isinstance(expected, str) or re.fullmatch('[0-9a-f]{64}', expected) is None):
        raise ValueError('Use an exact hashed external JSON document outside both profiles.')
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit or sha256(path) != expected:
        raise ValueError('Review document changed or exceeds its complete bound.')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate review intent key.')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('Nonfinite review intent.')))


def execute(args, request, monotonic=time.monotonic, pause=time.sleep):
    if not 0 < args.seconds <= 60:
        raise ValueError('Use a 0-60 second bounded Source-owner observation.')
    value = {'operation': 'cas-review', 'action': args.operation}
    if args.operation != 'status':
        previous = document(args.view_proof, args.view_sha256, args.state, 4 * 1024 * 1024)
        if (not isinstance(previous, dict) or previous.get('ok') is not True or
                previous.get('operation') != 'cas-review' or not isinstance(previous.get('view'), dict)):
            raise ValueError('Review action requires a successful exact preceding native view.')
        value['expected'] = previous['view']
    elif args.view_proof is not None or args.view_sha256 is not None:
        raise ValueError('Read-only status accepts no previous mutation intent.')
    allowed = {'select': {'sim_id'}, 'choice': {'lane', 'choice'}, 'hair': {'lane', 'outfit', 'selected'},
               'hair-none': {'lane'}}.get(args.operation, set())
    if allowed:
        options = document(args.values, args.values_sha256, args.state, 4096)
        if not isinstance(options, dict) or set(options) != allowed:
            raise ValueError('Supply only the exact named review action fields.')
        value.update(options)
    elif args.values is not None or args.values_sha256 is not None:
        raise ValueError('This review action accepts no external choices.')
    if args.operation == 'select' and (not isinstance(value['sim_id'], str) or
            re.fullmatch('[1-9][0-9]{0,19}', value['sim_id']) is None or int(value['sim_id']) >= 1 << 64):
        raise ValueError('Select an exact native uint64 Sim identity.')
    with session(args.state):
        evidence = IntentEvidence(args)
        call = evidence.wrap(request)
        _, journal, _, _ = reusable_profile.load(args.state)
        def native(argument):
            result = call(args.state, 'test_preview', value=json.dumps(
                {'test_token': journal['token'], 'value': argument}, ensure_ascii=True, allow_nan=False))
            if (not isinstance(result, dict) or result.get('ok') is not True or
                    result.get('operation') != 'cas-review' or not isinstance(result.get('view'), dict)):
                raise ValueError('Native review action refused or unresolved; inspect retained UUID and raw reply.')
            return result
        try:
            if args.operation == 'select':
                roster = call(args.state, 'list_sims')
                if roster.get('ok') is not True:
                    raise ValueError('A fresh Source Sim roster is unavailable.')
                value['roster'] = native_roster(roster)
            result = native(value)  # Exactly one submission of the requested action.
            deadline = monotonic() + args.seconds
            if result['view'].get('busy') is True:
                # Let the existing Source request reach a game-thread turn
                # before acquiring the render/model locks for another read.
                pause(min(2, args.seconds))
            while result['view'].get('busy') is True and monotonic() < deadline:
                pause(.5)
                result = native({'operation': 'cas-review', 'action': 'status'})
            result['requested_action'] = args.operation
            result['source_owner_pending'] = result['view'].get('busy') is True or result['view'].get('unresolved') is True
            result['source_model_failed'] = result['view'].get('failed') is True
            result['physical_imgui_click_proven'] = False
            result['appearance_mutation_queued'] = args.operation == 'commit'
            if args.operation != 'status' and (result['source_owner_pending'] or result['source_model_failed']):
                result.update(ok=False, outcome='source-owner-unresolved-or-failed')
            return evidence.finish(result)
        except BaseException as error:
            evidence.fail(error)
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('status', 'select', 'refresh', 'observe', 'choice', 'hair', 'hair-none', 'prepare', 'commit'))
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--view-proof', type=Path)
    parser.add_argument('--view-sha256')
    parser.add_argument('--values', type=Path)
    parser.add_argument('--values-sha256')
    parser.add_argument('--seconds', type=float, default=15)
    args = parser.parse_args(argv)
    from apex_cli import owned_request
    try:
        result = execute(args, owned_request)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result.get('ok') is True else 1
    except (OSError, ValueError, RuntimeError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error), 'automatic_replay_allowed': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
