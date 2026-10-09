"""Normal, unsaved exit of a quarantined disposable CAS identity failure.

This is deliberately narrower than normal shutdown. It pins a failed return
proof, reobserves the same paused Live context and missing Sim, and permits only
the retained acceptance intent after its native peer has disappeared. It never
marks acceptance successful, repairs a Sim, saves, or repeats ambiguous input.
"""
import copy
import json
import math
from pathlib import Path
import time

import apex_cli
import cas_transition
import game_capture
import game_lifecycle
import reusable_profile
from cas_return import decimal_id, uuid_id
from source_manifest import sha256, write_json
from windows_ocr import recognize


def missing_sim_live(value, household_id, save_guid):
    return (isinstance(value, dict) and value.get('ok') is True and 'sim' not in value
        and value.get('household_id') == household_id and value.get('save_guid') == save_guid
        and value.get('zone_running') is True and value.get('in_build_buy') is False
        and type(value.get('clock_speed')) is int and value['clock_speed'] == 0
        and all(decimal_id(value.get(field)) for field in ('client_id', 'zone_id'))
        and decimal_id(value.get('sim_now_ticks'), zero=True)
        and isinstance(value.get('runtime_queries'), dict)
        and all(value['runtime_queries'].get(field) == 'returned-value'
            for field in ('client_id', 'zone_running', 'sim_now_ticks')))


def failed_context(proof, identity, sim_id, household_id, save_guid):
    if (not isinstance(proof, dict) or proof.get('schema') != 1
            or proof.get('operation') != 'semantic-cas-return-to-live'
            or proof.get('ok') is not False or proof.get('outcome') != 'unresolved'
            or proof.get('accept_submitted') is not True
            or proof.get('accept_intent_observed') is not True
            or proof.get('cas_peer_disappearance_verified') is not True
            or proof.get('process_exit_verified') is not False
            or proof.get('input_submitted') is not False
            or proof.get('sim_id') != sim_id or proof.get('household_id') != household_id
            or not uuid_id(proof.get('cas_request_id'))
            or not isinstance(proof.get('identity'), dict)
            or any(proof['identity'].get(field) != identity.get(field)
                for field in ('pid', 'test_token', 'script_sha256'))):
        raise ValueError('Discard requires the exact failed return from this runtime, not an active or successful CAS session.')
    crash = proof.get('crash')
    if not isinstance(crash, dict) or crash.get('outcome') not in ('absent', 'unchanged'):
        raise ValueError('Failed return crash evidence is not clear; no discard input permitted.')
    steps = proof.get('steps')
    if not isinstance(steps, list) or len(steps) > 1024:
        raise ValueError('Failed return observations are unavailable or exceed their bound.')
    rows = [row.get('result') for row in steps if isinstance(row, dict) and row.get('action') == 'test_snapshot']
    if not rows or not missing_sim_live(rows[-1], household_id, save_guid):
        raise ValueError('Failed return does not retain the exact paused Live context with the selected Sim absent.')
    return rows[-1]


def discard_cas_state(diagnostic, intent_id):
    """Validate all native slots without changing their actual retained state."""
    if not uuid_id(intent_id) or not isinstance(diagnostic, dict):
        raise ValueError('An exact retained acceptance identity is required.')
    rows = diagnostic.get('requests')
    if not isinstance(rows, list):
        raise ValueError('Native request inventory is unavailable.')
    matching = [row for row in rows if isinstance(row, dict) and row.get('cas_request_id') == intent_id]
    if (len(matching) != 1 or matching[0].get('operation') != 'accept'
            or matching[0].get('state') != 'accept-intent'):
        raise ValueError('Retained native acceptance intent changed; no discard input permitted.')
    # The normal validator still checks every field, peer and other slot. Only
    # this exact known intent is exempted for unsaved exit, never for save/tests.
    validation = copy.deepcopy(diagnostic)
    selected = next(row for row in validation['requests'] if row.get('cas_request_id') == intent_id)
    selected.update(state='failed')
    for field in ('outcome', 'lifecycle_stage', 'commit_outcome'):
        selected.pop(field, None)
    guard = game_lifecycle.shutdown_cas_state(validation)
    if guard.get('safe') is not True:
        raise ValueError('Native CAS peer or another unresolved request remains; no discard input permitted.')
    return {'safe_for_unsaved_exit_only': True, 'native_peer_absence_verified': True,
            'retained_accept_intent': copy.deepcopy(matching[0]),
            'acceptance_marked_successful': False, 'other_slots_idle_verified': True}


def observe(state, output, identity, request, failed_return_proof, expected_proof_sha256,
            sim_id, household_id, save_guid, seconds=60, transport=None,
            capture=game_capture.capture, ocr=recognize, alive=cas_transition.process_alive,
            monotonic=time.monotonic, pause=time.sleep):
    started = monotonic()
    if (type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 90
            or not all(decimal_id(value) for value in (sim_id, household_id, save_guid))
            or not isinstance(expected_proof_sha256, str) or len(expected_proof_sha256) != 64
            or any(char not in '0123456789abcdef' for char in expected_proof_sha256)):
        raise ValueError('Use exact Sim/household/save identities, pinned proof hash and a bounded discard wait.')
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff
            or identity.get('test_token') != journal['token'] or script is None or identity.get('script_sha256') != script
            or Path(identity.get('profile', '')).resolve() != profile):
        raise ValueError('Discard identity differs from the exact disposable journal/profile/script.')
    output, failed_path = reusable_profile.writable(output), reusable_profile.writable(failed_return_proof)
    if (output.exists() or output.suffix.lower() != '.json' or not output.parent.is_dir()
            or output == journal_path or any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use a new external discard proof outside both profiles and the journal.')
    if (any(failed_path == root or root in failed_path.parents for root in (profile, original))
            or not failed_path.is_file() or failed_path.stat().st_size > 12 * 1024 * 1024
            or sha256(failed_path) != expected_proof_sha256):
        raise ValueError('Failed return proof is unsafe, missing, oversized or changed.')
    failed = json.loads(failed_path.read_text(encoding='utf-8'))
    context = failed_context(failed, identity, sim_id, household_id, save_guid)
    intent_id, deadline = failed['cas_request_id'], started + seconds
    transport = apex_cli.get if transport is None else transport
    proof = {'schema': 1, 'operation': 'normal-discard-failed-cas-session', 'ok': False,
        'outcome': 'unresolved', 'identity': identity, 'inputs': journal['artifacts'],
        'failed_return_proof': {'path': str(failed_path), 'sha256': expected_proof_sha256},
        'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid,
        'retained_cas_request_id': intent_id, 'steps': [], 'owner_requests': [],
        'before_saves': game_lifecycle.save_files(profile), 'save_submitted': False,
        'appearance_mutated': False, 'cas_accept_repeated': False, 'input_submitted': False,
        'quit_menu_submitted': False, 'discard_input_accepted': False,
        'game_exit_verified': False, 'normal_exit_verified': False, 'save_files_unchanged_verified': False}
    before_crash = None
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)

    def record(action, result):
        proof['steps'].append({'action': action, 'result': result})
        write_json(output, proof)
        return result

    def running():
        if monotonic() >= deadline:
            raise TimeoutError('Discard observation deadline expired; no request replay permitted.')
        present = alive(identity['pid'])
        if type(present) is not bool:
            raise ValueError('Game process observation is untyped.')
        if not present:
            raise ProcessLookupError('Verified game exited before the normal discard confirmation.')

    def pinned(path, query=None, timeout=12):
        running()
        if path in ('/api/command', '/api/native') and isinstance(query, dict):
            if not uuid_id(query.get('request_id')):
                raise ValueError('Retain the owner UUID before any discard transport.')
            proof['owner_requests'].append({'action': query.get('action'), 'request_id': query['request_id']})
            write_json(output, proof)
        result = transport(path, query, timeout=min(timeout, 2, max(.01, deadline - monotonic())))
        if path == '/api/bridge' and (not isinstance(result, dict) or any(result.get(field) != identity.get(field)
                for field in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('Discard bridge identity changed; no further input permitted.')
        return result

    envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})

    def call(action, value=None, selected_sim=None):
        running()
        result = record(action, request(state, action, sim_id=selected_sim, value=value,
                        seconds=min(2, max(.01, deadline - monotonic())), transport=pinned))
        if (not isinstance(result, dict) or result.get('ok') is not True
                or result.get('request_state') in ('pending', 'running', 'unknown')):
            raise ValueError('Discard control failed or remains unresolved; no replay: ' + action)
        return result

    def guard():
        diagnostic = call('cas_ui_diagnostics')
        record('discard-only-cas-guard', discard_cas_state(diagnostic, intent_id))
        current = call('test_snapshot', envelope(None), sim_id)
        if (not missing_sim_live(current, household_id, save_guid)
                or any(current.get(field) != context.get(field) for field in ('client_id', 'zone_id', 'sim_now_ticks'))):
            raise ValueError('Fresh paused Live identity/clock changed or selected Sim returned; no discard input permitted.')
        if game_lifecycle.save_files(profile) != proof['before_saves']:
            raise ValueError('Save files changed before discard input; no further input permitted.')

    def capture_request(_state, action, sim_id=None, value=None, **_kwargs):
        return call(action, value, sim_id)

    try:
        before_crash, _ = cas_transition.read_crash(profile)
        proof['crash_before'] = before_crash
        write_json(output, proof)
        if before_crash.get('state') not in ('absent', 'read'):
            raise ValueError('Crash baseline is unavailable; no discard input permitted.')
        guard()
        hidden = call('overlay_hide')
        if hidden.get('visible') is not False:
            raise ValueError('F11 visibility is not confirmed hidden.')
        initial = None
        for index, phase in enumerate(('initial', 'menu', 'confirmation-discard')):
            running()
            image = output.with_name(output.stem + '-' + phase + '.bmp')
            frame = record('capture-' + phase, capture(state, image, capture_request))
            if frame.get('ok') is not True or frame.get('capture_completed_verified') is not True:
                raise ValueError('Native discard capture did not complete; no input permitted.')
            observed = ocr(image)
            if observed.get('ok') is not True:
                raise ValueError('Native discard OCR failed; no input permitted.')
            if index == 0:
                for candidate in ('confirmation-discard', 'menu'):
                    try:
                        initial = candidate, game_lifecycle.button(observed, candidate)
                        break
                    except ValueError:
                        pass
                if initial is None:
                    guard()
                    proof['quit_menu_submitted'] = True
                    write_json(output, proof)
                    call('test_quit', envelope(None))
                    pause(.5)
                    continue
                phase, selected = initial
            else:
                if initial and initial[0] == 'confirmation-discard':
                    break
                if initial and initial[0] == 'menu' and index == 1:
                    continue
                selected = game_lifecycle.button(observed, phase)
            if (selected['width'], selected['height']) != (frame['width'], frame['height']):
                raise ValueError('Discard OCR/capture viewport identity differs.')
            record('recognized-' + phase, {'observation': observed, 'selected': selected})
            guard()
            proof['input_submitted'] = True  # Intent survives a lost native response.
            write_json(output, proof)
            result = call('test_input', envelope(selected))
            if result.get('input_version') != 2 or result.get('input_submitted') is not True or result.get('input_state') != 4:
                raise ValueError('Native discard input was not fully acknowledged; no replay permitted.')
            if phase == 'confirmation-discard':
                proof['discard_input_accepted'] = True
                write_json(output, proof)
                break
            pause(.5)
        while monotonic() < deadline and alive(identity['pid']):
            pause(min(.5, max(0, deadline - monotonic())))
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        proof['error'] = str(error)
    try:
        proof['final_process_alive'] = alive(identity['pid'])
        if type(proof['final_process_alive']) is not bool:
            raise ValueError('Final process observation is untyped.')
        proof['game_exit_verified'] = proof['final_process_alive'] is False
    except (OSError, ValueError, RuntimeError) as error:
        proof['process_observation_error'] = str(error)
    try:
        proof['after_saves'] = game_lifecycle.save_files(profile)
        proof['save_files_unchanged_verified'] = proof['after_saves'] == proof['before_saves']
    except (OSError, ValueError, RuntimeError) as error:
        proof['save_observation_error'] = str(error)
    try:
        proof['crash'] = cas_transition.preserve_crash(profile, output, before_crash) if before_crash is not None else {'outcome': 'baseline-unavailable'}
    except (OSError, ValueError, RuntimeError) as error:
        proof['crash'] = {'outcome': 'observation-failed', 'error': str(error)}
    proof['normal_exit_verified'] = (proof['game_exit_verified'] and proof['discard_input_accepted']
        and proof['crash'].get('outcome') in ('absent', 'unchanged') and 'error' not in proof)
    proof['ok'] = proof['normal_exit_verified'] and proof['save_files_unchanged_verified']
    proof['outcome'] = 'normal-exit-without-saving' if proof['ok'] else 'discard-unverified'
    proof.update(elapsed_seconds=monotonic() - started, finalized=True)
    write_json(output, proof)
    return {key: proof[key] for key in ('ok', 'outcome', 'normal_exit_verified', 'game_exit_verified',
            'discard_input_accepted', 'save_files_unchanged_verified')} | {
        'proof': str(output), 'proof_sha256': sha256(output),
        'message': 'Failed disposable session exited normally without changing save files.' if proof['ok'] else proof.get('error', 'Inspect retained discard proof before any retry.')}
