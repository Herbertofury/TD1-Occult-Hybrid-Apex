"""Submit one explicit existing disposable save target and observe its file.

No slot creation, pointer input, profile repair, quit/relaunch or blind replay.
The native scheduling receipt, changed stable file and reload are separate facts.
"""
import json
import math
from pathlib import Path
import sys
import time

import apex_cli
import cas_transition
import reusable_profile
from source_manifest import sha256, write_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.test_driver import _save_target, _save_file_evidence, _save_live_context


def uuid_id(value):
    return isinstance(value, str) and len(value) == 32 and all(char in '0123456789abcdef' for char in value)


def observe(state, output, identity, request, sim_id, slot_id, slot_name, expected_save_sha256,
            save_guid, household_id, seconds=60, transport=None,
            alive=cas_transition.process_alive, monotonic=time.monotonic, pause=time.sleep):
    target = _save_target({'slot_id': slot_id, 'slot_name': slot_name, 'expected_save_sha256': expected_save_sha256,
                           'save_guid': save_guid, 'household_id': household_id, 'sim_id': sim_id})
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 120:
        raise ValueError('Save observation wait must be finite and bounded to 120 seconds.')
    started, deadline = monotonic(), monotonic() + seconds
    journal_path, journal, profile, original = reusable_profile.load(state)
    expected_script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff
            or identity.get('test_token') != journal['token'] or expected_script is None
            or identity.get('script_sha256') != expected_script
            or (identity.get('profile') is not None and Path(identity['profile']).resolve() != profile)):
        raise ValueError('Save observer identity differs from the exact disposable profile/script/PID.')
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or not output.parent.is_dir() or output == journal_path
            or any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use one new external JSON save proof outside both profiles and the journal.')
    before = _save_file_evidence(profile, slot_id)
    if before['sha256'] != expected_save_sha256:
        raise ValueError('Existing target file hash differs from the explicit expectation; no save submitted.')
    if transport is None:
        transport = apex_cli.get
    crash_before, _ = cas_transition.read_crash(profile)
    if not isinstance(crash_before, dict) or crash_before.get('state') not in ('absent', 'read'):
        raise ValueError('Native crash baseline is unavailable or exceeds its bound; no save requests were sent.')
    proof = {'schema': 1, 'operation': 'explicit-existing-disposable-save', 'ok': False, 'outcome': 'unresolved',
             'identity': identity, 'journal': str(journal_path), 'inputs': journal['artifacts'],
             'target': target, 'seconds': seconds, 'target_before': before,
             'steps': [], 'owner_requests': [], 'file_observations': [], 'save_request_id': None,
             'save_command_attempted': False, 'save_submitted': False, 'save_completed_file_verified': False,
             'native_target_slot_verified': False, 'save_reload_verified': False, 'retry_safe': False,
             'process_exit_verified': False, 'crash_before': crash_before, 'crash_clear_verified': False, 'finalized': False,
             'scope': 'One native scheduling request and stable changed existing file; no reload or appearance-persistence claim.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2, ensure_ascii=False, allow_nan=False)

    def record():
        if len(json.dumps(proof, ensure_ascii=False, allow_nan=False).encode('utf-8')) > 4 * 1024 * 1024:
            raise ValueError('Save proof exceeded its bounded evidence budget.')
        write_json(output, proof)

    def remaining():
        value = deadline - monotonic()
        if value <= 0:
            raise TimeoutError('Save observation deadline expired; do not submit the save again.')
        return value

    def running():
        if not alive(identity['pid']):
            proof['process_exit_verified'] = True
            raise ProcessLookupError('Verified game process exited during save observation.')

    def pinned_transport(path, query=None, timeout=12):
        timeout = min(timeout, 2, remaining())
        if path == '/api/command' and isinstance(query, dict):
            rid = query.get('request_id')
            if not uuid_id(rid):
                raise ValueError('Save owner request UUID was not typed before submission.')
            proof['owner_requests'].append({'action': query.get('action'), 'request_id': rid})
            if query.get('action') == 'test_save':
                if proof['save_request_id'] is not None:
                    raise RuntimeError('Save command was already submitted; no replay permitted.')
                proof['save_request_id'] = rid
            record()  # Own the exact UUID even when submission loses its response.
        result = transport(path, query, timeout=timeout)
        if path == '/api/bridge' and (not isinstance(result, dict) or any(
                result.get(field) != identity.get(field) for field in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('Save bridge changed PID/token/script; no further command permitted.')
        return result

    def call(action, value):
        running()
        result = request(state, action, sim_id=sim_id, value=json.dumps({'test_token': journal['token'], 'value': value}),
                         seconds=min(2, remaining()), transport=pinned_transport)
        proof['steps'].append({'action': action, 'result': result, 'elapsed_seconds': max(0, monotonic() - started)})
        record()
        if not isinstance(result, dict):
            raise ValueError('Save observer requires typed game-owned results.')
        if (result.get('outcome') == 'unresolved' and uuid_id(result.get('request_id'))
                and result.get('request_state') not in ('completed', 'failed', 'cancelled')):
            # Poll the original owner UUID, including a save scheduling response
            # delayed past the short request timeout. Never resubmit its command.
            result = apex_cli.poll_request(result['request_id'], seconds=min(2, remaining()),
                        transport=pinned_transport, monotonic=monotonic, pause=lambda value: pause(min(value, remaining())))
            proof['steps'].append({'action': 'observe-owner:' + action, 'result': result})
            record()
        return result

    def profile_same():
        _, current, current_profile, _ = reusable_profile.load(state)
        if current_profile != profile or current['token'] != journal['token'] or current['artifacts'] != journal['artifacts']:
            raise ValueError('Disposable profile identity changed during save observation.')

    try:
        running()
        preflight = call('test_snapshot', None)
        _save_live_context(preflight, target)
        proof['native_before'] = preflight
        profile_same()
        if _save_file_evidence(profile, slot_id)['sha256'] != expected_save_sha256:
            raise ValueError('Existing target changed after native preflight; no save submitted.')
        proof['save_command_attempted'] = True
        record()
        submitted = call('test_save', target)
        if not uuid_id(proof['save_request_id']):
            raise RuntimeError('Save owner UUID was not retained; no completion or replay permitted.')
        if submitted.get('request_id') is not None and submitted['request_id'] != proof['save_request_id']:
            raise ValueError('Save scheduling receipt belongs to another owner UUID.')
        if (submitted.get('ok') is not True or submitted.get('save_submitted') is not True or
                submitted.get('slot_id') != slot_id or submitted.get('save_guid') != save_guid or
                submitted.get('household_id') != household_id or submitted.get('sim_id') != sim_id):
            raise RuntimeError('Native save scheduling was rejected or unresolved; preserve its UUID without replay.')
        proof['save_submitted'] = True
        record()
        previous = None
        while True:
            running(); remaining(); profile_same()
            try:
                observed = _save_file_evidence(profile, slot_id)
            except FileNotFoundError:
                # Native atomic replacement may briefly remove the path. Only
                # this passive file observation repeats, never the save request.
                previous = None
                pause(min(.25, remaining()))
                continue
            if not proof['file_observations'] or proof['file_observations'][-1] != observed:
                if len(proof['file_observations']) >= 128:
                    raise ValueError('Save file observation bound reached; no mutation replay permitted.')
                proof['file_observations'].append(observed)
                record()
            if observed == previous and observed['sha256'] != expected_save_sha256:
                proof['save_completed_file_verified'] = True
                proof['target_after'] = observed
                record()
                break
            previous = observed
            pause(min(.25, remaining()))
        after = call('test_snapshot', None)
        _save_live_context(after, target)
        if after.get('save_slot') != slot_id:
            raise ValueError('Changed file observed, but native runtime slot did not read back the explicit target.')
        proof.update(native_after=after, native_target_slot_verified=True)
        if _save_file_evidence(profile, slot_id) != proof['target_after']:
            raise ValueError('Target file changed after convergence; file completion is no longer stable.')
        intent = submitted.get('form_bank_seal')
        proof['form_bank_seal_verified'] = False
        if isinstance(intent, dict) and intent.get('state') == 'save-intent' and uuid_id(intent.get('intent_id')):
            sealed = call('test_form_seal_complete', {'intent_id': intent['intent_id'],
                          'expected_save_sha256': proof['target_after']['sha256']})
            proof['form_bank_seal'] = sealed; record()
            if (sealed.get('ok') is not True or sealed.get('state') != 'sealed' or sealed.get('intent_id') != intent['intent_id'] or
                    sealed.get('file_sha256') != proof['target_after']['sha256'] or
                    not isinstance(sealed.get('seal_sha256'), str) or len(sealed['seal_sha256']) != 64 or
                    any(char not in '0123456789abcdef' for char in sealed['seal_sha256'])):
                raise RuntimeError('Save file changed but appearance seal is rejected or unresolved; retain its UUID without replay.')
            proof['form_bank_seal_verified'] = True
        elif intent is None or isinstance(intent, dict) and intent.get('state') == 'not-applicable':
            proof['form_bank_seal'] = {'state': 'unavailable' if intent is None else 'not-applicable', 'sealed': False}
        else:
            raise ValueError('Native save seal intent is untyped or unknown; no appearance certification inferred.')
        proof.update(ok=True, outcome='existing-target-save-file-observed')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
        try:
            running()
        except ProcessLookupError:
            proof['outcome'] = 'process-exited'
        except (OSError, ValueError) as observation_error:
            proof['process_observation_error'] = str(observation_error)
    try:
        proof['crash'] = cas_transition.preserve_crash(profile, output, crash_before)
    except (OSError, ValueError, RuntimeError) as error:
        proof['crash'] = {'preserved': False, 'outcome': 'refused', 'error': str(error)}
    crash = proof['crash']; after_crash = crash.get('after', {})
    changed_crash = (isinstance(after_crash, dict) and
                     ((after_crash.get('state') == 'read' and
                       after_crash.get('sha256') != crash_before.get('sha256')) or
                      after_crash.get('state') == 'oversized'))
    proof['crash_clear_verified'] = (crash.get('preserved') is False and
                                    crash.get('outcome') in ('absent', 'unchanged') and
                                    after_crash.get('state') in ('absent', 'read') and not changed_crash)
    if changed_crash or crash.get('preserved') is True:
        proof.update(ok=False, outcome='crash' if crash.get('preserved') is True else 'changed-crash-report-refused',
                     message='A changed crash report was observed; save success is not verified. Inspect retained evidence before any retry.')
    elif not proof['crash_clear_verified']:
        proof.update(ok=False, outcome='crash-observation-unresolved',
                     message='Final crash evidence is unavailable or refused; save success is not verified. Inspect retained evidence before any retry.')
    proof.update(elapsed_seconds=max(0, monotonic() - started), finalized=True)
    record()
    return {'ok': proof['ok'], 'outcome': proof['outcome'], 'proof': str(output), 'proof_sha256': sha256(output),
            'save_request_id': proof['save_request_id'], 'save_submitted': proof['save_submitted'],
            'save_completed_file_verified': proof['save_completed_file_verified'],
            'native_target_slot_verified': proof['native_target_slot_verified'], 'save_reload_verified': False,
            'form_bank_seal_verified': proof.get('form_bank_seal_verified', False),
            'form_bank_seal': proof.get('form_bank_seal'),
            'retry_safe': False, 'message': proof.get('message', proof.get('error',
                'One existing-target save and stable changed file observed; reload remains separate.'))}
