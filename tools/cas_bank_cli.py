"""Typed CLI for receiver-owned CAS appearance transactions.

Requests contain exact receipt hashes and lane/outfit decisions only. Native
appearance bytes stay inside the game-owned checkpoint and journal.
"""
import hashlib
import json
from pathlib import Path

import reusable_profile
from source_manifest import sha256, write_json


FORMS = {'1', '2', '4', '8', '16', '32', '64'}


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate CAS intent JSON key.')
        result[key] = value
    return result


def _intent_file(path, expected, active, original):
    if path is None or not _hash(expected):
        raise ValueError('Intent files require their exact SHA-256.')
    path = reusable_profile.legacy.unlinked(path)
    if path.suffix.lower() != '.json' or any(path == root or root in path.parents for root in (active, original)):
        raise ValueError('Use an external JSON intent file.')
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= 128 * 1024:
        raise ValueError('CAS intent file exceeds its bound.')
    with path.open('rb') as stream:
        raw = stream.read(128 * 1024 + 1)
    after = path.stat()
    if (len(raw) > 128 * 1024 or hashlib.sha256(raw).hexdigest() != expected or
            (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)):
        raise ValueError('CAS intent file changed or differs from its exact hash.')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs)


def _dispositions(value):
    if not isinstance(value, list) or len(value) > 7:
        raise ValueError('Use at most seven explicit changed-form decisions.')
    seen = set()
    for row in value:
        if (not isinstance(row, dict) or set(row) != {'lane', 'action'} or
                not isinstance(row['lane'], str) or row['lane'] not in FORMS or row['lane'] in seen or
                row['action'] not in ('accept-returned', 'restore-original')):
            raise ValueError('Each form decision needs a unique lane and supported action; external fields are forbidden.')
        seen.add(row['lane'])
    return value


def _hair_targets(value, accepted):
    if not isinstance(value, dict) or set(value) - accepted:
        raise ValueError('Hair intent must belong to an explicitly accepted form.')
    for lane, targets in value.items():
        if not isinstance(targets, list) or not 0 < len(targets) <= 1024:
            raise ValueError('Hair intent needs bounded outfit targets.')
        seen = set()
        for row in targets:
            if (not isinstance(row, dict) or set(row) != {'category', 'ordinal', 'outfit_id'} or
                    type(row['category']) is not int or not 0 <= row['category'] < 2 ** 32 or
                    type(row['ordinal']) is not int or not 0 <= row['ordinal'] < 1024 or
                    not isinstance(row['outfit_id'], str) or not row['outfit_id'].isascii() or
                    not row['outfit_id'].isdigit() or str(int(row['outfit_id'])) != row['outfit_id'] or
                    not 0 < int(row['outfit_id']) < 2 ** 64 or
                    (row['category'], row['ordinal']) in seen):
                raise ValueError('Hair intent requires exact category/ordinal/uint64 outfit identity; external fields are forbidden.')
            seen.add((row['category'], row['ordinal']))
    return value


def run(args, request):
    _, journal, active, original = reusable_profile.load(args.state)
    output = reusable_profile.writable(args.output)
    if (output.exists() or output.suffix.lower() != '.json' or
            output == Path(args.state).resolve() or
            any(output == root or root in output.parents for root in (active, original))):
        raise ValueError('CAS bank receipts require one new external JSON filename.')
    if (not isinstance(args.sim_id, str) or not args.sim_id.isascii() or not args.sim_id.isdigit() or
            str(int(args.sim_id)) != args.sim_id or not 0 < int(args.sim_id) < 2 ** 64):
        raise ValueError('Use an exact native uint64 Sim identity.')
    supplied = {key: getattr(args, key) for key in ('expected_pending_sha256', 'expected_raw_return_sha256',
        'expected_plan_sha256', 'dispositions_file', 'dispositions_sha256', 'hair_targets_file', 'hair_targets_sha256')}
    allowed = {'begin': set(), 'status': set(), 'observe': {'expected_pending_sha256'},
               'prepare': {'expected_pending_sha256', 'expected_raw_return_sha256', 'dispositions_file',
                           'dispositions_sha256', 'hair_targets_file', 'hair_targets_sha256'},
               'commit': {'expected_pending_sha256', 'expected_plan_sha256'}}[args.operation]
    if any(value is not None and key not in allowed for key, value in supplied.items()):
        raise ValueError('CAS bank options belong to a different operation; no request submitted.')
    value = {}
    for name in ('expected_pending_sha256', 'expected_raw_return_sha256', 'expected_plan_sha256'):
        if name in allowed and (name != 'expected_raw_return_sha256' or args.operation == 'prepare'):
            if not _hash(supplied[name]):
                raise ValueError('Use the exact prior CAS receipt hashes.')
            value[name] = supplied[name]
    if args.operation == 'prepare':
        value['dispositions'] = _dispositions(_intent_file(args.dispositions_file, args.dispositions_sha256, active, original))
        if args.hair_targets_file is not None or args.hair_targets_sha256 is not None:
            accepted = {row['lane'] for row in value['dispositions'] if row['action'] == 'accept-returned'}
            value['hair_targets'] = _hair_targets(_intent_file(args.hair_targets_file, args.hair_targets_sha256, active, original), accepted)
    if not 0 < args.seconds <= 300:
        raise ValueError('Use a bounded CAS bank command completion timeout.')
    action = 'cas_bank_' + args.operation
    receipt = {'schema': 1, 'ok': False, 'outcome': 'prepared-not-submitted',
               'action': action, 'sim_id': args.sim_id, 'request_id': None,
               'request_submitted': False, 'automatic_replay_allowed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, sort_keys=True)

    def submitting(submitted_action, request_id):
        if submitted_action != action or receipt['request_id'] is not None:
            raise ValueError('CAS bank submission identity is duplicate or belongs to another action.')
        receipt.update(outcome='submission-possible', request_id=request_id, request_submitted=None)
        write_json(output, receipt)  # Native UUID must be durable BEFORE HTTP.

    try:
        result = request(args.state, action, sim_id=args.sim_id,
                         value=(None if args.operation in ('begin', 'status') else json.dumps(value, sort_keys=True, allow_nan=False)), seconds=args.seconds,
                         submission_observer=submitting)
        if not isinstance(result, dict):
            raise ValueError('The CAS bank command returned no typed receipt.')
        if receipt['request_id'] is not None:
            if 'request_id' in result and result['request_id'] != receipt['request_id']:
                returned = result
                result = dict(receipt, outcome='unresolved', returned_request_id=returned.get('request_id'),
                    returned_receipt=returned,
                    message='Returned request identity differs. Retain the submitted UUID; no command was replayed.')
            result = dict(result, request_id=receipt['request_id'], submitted_request_id=receipt['request_id'])
    except (OSError, ValueError, RuntimeError) as error:
        result = dict(receipt, outcome='unresolved' if receipt['request_id'] is not None else 'not-submitted',
                      error=str(error), message='Retain this exact request identity; no command was replayed.')
    write_json(output, result)
    return dict(result, proof=str(output), proof_sha256=sha256(output))
