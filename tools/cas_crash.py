"""Bind a later native crash to an immutable successful disposable CAS entry.

This preserves evidence only. It neither launches, saves nor restores a Sim.
The crash report has no PID field; attribution and causality remain unverified.
"""
import json
from pathlib import Path

import cas_transition
import reusable_profile
from cas_return import native_live_context
from source_manifest import sha256, write_json


def external_json(path, profile, original, expected_hash):
    path = reusable_profile.writable(path)
    if (not path.is_file() or path.stat().st_size > 12 * 1024 * 1024 or
            any(path == root or root in path.parents for root in (profile, original)) or
            sha256(path) != expected_hash):
        raise ValueError('CAS entry proof is unsafe, missing or changed.')
    return path, json.loads(path.read_text(encoding='utf-8'))


def entry_receipt(entry):
    """Read the one submitted entry, including its exact later UUID completion."""
    steps = entry.get('steps')
    if not isinstance(steps, list) or len(steps) > 1024:
        raise ValueError('CAS entry observations are missing or oversized.')
    rows = [row.get('result') for row in steps if isinstance(row, dict) and row.get('action') == 'test_cas']
    completions = [row.get('result') for row in steps if isinstance(row, dict)
                   and row.get('action') == 'test_cas_completion']
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError('CAS entry must have been acknowledged exactly once.')
    if rows[0].get('ok') is True:
        if completions:
            raise ValueError('CAS entry must have been acknowledged exactly once.')
        return rows[0]
    request_id = entry.get('entry_request_id')
    statuses = [row.get('result') for row in steps if isinstance(row, dict)
                and row.get('action') == 'test_cas_status']
    terminal = [row for row in statuses if isinstance(row, dict) and row.get('state') == 'completed']
    if (not isinstance(request_id, str) or len(request_id) != 32 or
            any(c not in '0123456789abcdef' for c in request_id) or
            rows[0].get('ok') is not False or rows[0].get('outcome') != 'unresolved' or
            rows[0].get('request_id') != request_id or len(completions) != 1 or len(terminal) != 1 or
            any(not isinstance(row, dict) or row.get('ok') is not True or
                row.get('request_id') != request_id or row.get('state') not in ('pending', 'running', 'completed')
                for row in statuses) or
            set(terminal[0]) != {'ok', 'request_id', 'state', 'result'} or
            not isinstance(terminal[0]['result'], dict) or terminal[0]['result'].get('ok') is not True):
        raise ValueError('CAS entry lacks its one original UUID terminal completion.')
    completed = completions[0]
    if (not isinstance(completed, dict) or completed.get('request_id') != request_id or
            completed.get('request_state') != 'completed' or
            {key: value for key, value in completed.items() if key not in ('request_id', 'request_state')}
            != terminal[0]['result']):
        raise ValueError('CAS entry completion differs from the retained original UUID result.')
    return completed


def entry_context(entry, identity, sim_id, household_id, save_guid, slot_id):
    if (not isinstance(entry, dict) or entry.get('schema') != 1 or
            entry.get('operation') != 'observe-native-cas-entry' or
            entry.get('ok') is not True or entry.get('outcome') != 'inventory' or
            any(entry.get(field) is not True for field in
                ('entry_submitted', 'entry_accepted', 'handshake_verified', 'inventory_verified', 'no_input_replay')) or
            entry.get('requested_sim_id') != sim_id or not isinstance(entry.get('identity'), dict) or
            any(entry['identity'].get(field) != identity.get(field)
                for field in ('pid', 'test_token', 'script_sha256', 'profile'))):
        raise ValueError('Post-entry crash requires the exact completed native CAS entry.')
    before = entry_receipt(entry).get('before')
    # Preserve the original receipt without pretending its old clock producer
    # can establish fresh simulation progress or a successful CAS return.
    if (not native_live_context(before, sim_id, household_id) or before.get('save_guid') != save_guid or
            before.get('save_slot') != slot_id or before.get('clock_speed') != 0):
        raise ValueError('CAS entry lacks its exact paused native Sim, household and save slot.')
    return before


def validate(proof, identity, sim_id, household_id, save_guid, slot_id, profile, original):
    if (proof.get('schema') != 1 or proof.get('operation') != 'observe-native-cas-post-entry-crash' or
            proof.get('ok') is not False or proof.get('outcome') != 'native-crash' or
            proof.get('process_absent_observed') is not True or proof.get('identity') != identity):
        raise ValueError('A later native crash needs its exact retained runtime evidence.')
    _, entry = external_json(proof.get('entry_proof', ''), profile, original, proof.get('entry_proof_sha256'))
    before = entry_context(entry, identity, sim_id, household_id, save_guid, slot_id)
    crash = proof.get('crash')
    if (not isinstance(crash, dict) or crash.get('outcome') != 'preserved' or crash.get('preserved') is not True or
            crash.get('before') != entry.get('crash_before') or
            not isinstance(crash.get('after'), dict) or
            crash.get('after', {}).get('sha256') == crash.get('before', {}).get('sha256')):
        raise ValueError('A changed crash report was not preserved after this CAS entry.')
    path = reusable_profile.writable(crash.get('path', ''))
    if (any(path == root or root in path.parents for root in (profile, original)) or
            not path.is_file() or not 1 <= path.stat().st_size <= cas_transition.MAX_CRASH_BYTES or
            sha256(path) != crash['after'].get('sha256')):
        raise ValueError('Preserved later crash bytes are missing, changed or unsafe.')
    return before


def record(state, entry_proof, expected_hash, output):
    journal_path, journal, profile, original = reusable_profile.load(state)
    path, entry = external_json(entry_proof, profile, original, expected_hash)
    identity = entry.get('identity', {})
    expected_script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or identity.get('script_sha256') != expected_script or
            Path(identity.get('profile', '')).resolve() != profile or cas_transition.process_alive(identity['pid']) is not False):
        raise ValueError('Crash observation requires an absent exact disposable runtime and unchanged script.')
    before = entry_receipt(entry).get('before', {})
    sim_id = entry.get('requested_sim_id')
    entry_context(entry, identity, sim_id, before.get('household_id'), before.get('save_guid'), before.get('save_slot'))
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.lower() != '.json' or not output.parent.is_dir() or output in (journal_path, path) or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use a new external JSON crash proof outside the profiles and journal.')
    proof = {'schema': 1, 'operation': 'observe-native-cas-post-entry-crash', 'ok': False, 'outcome': 'native-crash',
             'identity': identity, 'entry_proof': str(path), 'entry_proof_sha256': expected_hash,
             'process_absent_observed': True, 'sim_id': sim_id, 'household_id': before['household_id'],
             'save_guid': before['save_guid'], 'slot_id': before['save_slot'],
             'crash': cas_transition.preserve_crash(profile, output, entry['crash_before']),
             'causality_verified': False, 'report_pid_attribution_verified': False,
             'game_mutated': False, 'appearance_restored': False, 'save_written': False}
    validate(proof, identity, sim_id, before['household_id'], before['save_guid'], before['save_slot'], profile, original)
    write_json(output, proof)
    return {'ok': True, 'crash_evidence_preserved': True, 'game_test_passed': False,
            'proof': str(output), 'proof_sha256': sha256(output), 'causality_verified': False}
