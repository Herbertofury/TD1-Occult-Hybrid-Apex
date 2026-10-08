"""Bounded Resume and normal Save and Exit through game-owned menu buttons."""
import json
from pathlib import Path
import re
import time

import game_capture
import game_launch
import reusable_profile
from source_manifest import sha256, write_json
from windows_ocr import recognize


def button(observation, phase):
    lines = observation.get('lines', [])
    normalized = lambda text: ' '.join(str(text).split()).casefold()
    text = [normalized(row.get('text')) for row in lines]
    if phase == 'menu':
        if 'menu' not in text or 'save' not in text or not any(label in text for label in ('save as', 'save as...', 'save as…')) or 'save game?' in text:
            raise ValueError('Native main menu is not recognized; no Exit click submitted.')
        label = 'exit game'
    elif phase == 'confirmation':
        if not all(item in text for item in ('save game?', 'are you sure you want to exit the game?', 'cancel', 'exit game')):
            raise ValueError('Native Save Game confirmation is not recognized; no Save and Exit click submitted.')
        label = 'save and exit'
    elif phase == 'resume':
        required = ('home', 'marketplace', 'load game', 'new game', 'gallery')
        forbidden = ('save game?', 'buy now', 'expansion pack', 'game pack', 'stuff pack',
                     'this game requires permissions', 'you don’t have access',
                     "you don't have access", 'cancel')
        if observation.get('ok') is not True or not all(text.count(item) == 1 for item in required) or any(item in text for item in forbidden):
            raise ValueError('Complete Sims 4 Home menu is not recognized; no Resume click submitted.')
        labels = [item for item in ('resume game', 'resume') if item in text]
        if len(labels) != 1:
            raise ValueError('Native Resume button is absent or ambiguous.')
        label = labels[0]
    else:
        raise ValueError('Unknown lifecycle phase.')
    matches = [row for row in lines if normalized(row.get('text')) == label]
    if len(matches) != 1 or not matches[0].get('words'):
        raise ValueError('Native lifecycle button is absent or ambiguous.')
    words = matches[0]['words']
    left, top = min(row['x'] for row in words), min(row['y'] for row in words)
    right = max(row['x'] + row['width'] for row in words)
    bottom = max(row['y'] + row['height'] for row in words)
    x, y = round((left + right) / 2), round((top + bottom) / 2)
    if not 0 <= left < right <= observation['width'] or not 0 <= top < bottom <= observation['height']:
        raise ValueError('Lifecycle button is outside the observed game viewport.')
    return {'command': 1, 'x': x, 'y': y, 'width': observation['width'], 'height': observation['height']}


def loaded_household(snapshot, prior_saves, sim_id=None):
    """Require a real saved Live household; no menu/loading submission is proof."""
    if not snapshot.get('ok') or snapshot.get('in_build_buy') is not False:
        return False
    try:
        slot = snapshot['save_slot']
        if type(slot) is not int or not 0 < slot < 0xffffffff:
            return False
        if 'Slot_{:08x}.save'.format(slot) not in prior_saves:
            return False
        if any(not 0 < int(str(snapshot[field]), 10) < 1 << 64
               for field in ('zone_id', 'save_guid', 'household_id')):
            return False
        sim = snapshot['sim']
        if sim.get('instanced') is not True or not 0 < int(sim['id'], 10) < 1 << 64:
            return False
        return sim_id is None or sim['id'] == sim_id
    except (KeyError, TypeError, ValueError):
        return False


def resume(state, output, identity, request, sim_id=None, seconds=60,
           capture=game_capture.capture, ocr=recognize,
           processes=game_launch.running_game_processes, monotonic=time.monotonic, pause=time.sleep):
    """Recognize Resume once, then observe a saved household through the owned bridge."""
    _, journal, profile, original = reusable_profile.load(state)
    if sim_id is not None:
        if not isinstance(sim_id, str) or not sim_id.isascii() or not sim_id.isdecimal() or not 0 < int(sim_id) < 1 << 64:
            raise ValueError('Use an exact decimal existing Sim ID.')
        sim_id = str(int(sim_id))
    if not 0 < seconds <= 60:
        raise ValueError('Resume completion wait must be between 0 and 60 seconds.')
    output = reusable_profile.writable(output)
    if output.exists() or output.suffix.lower() != '.json' or any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('Use one new external JSON lifecycle proof filename.')
    if not output.parent.is_dir():
        raise ValueError('Use an existing evidence directory.')
    proof = {'schema': 1, 'ok': False, 'operation': 'resume-existing-disposable-household',
             'identity': identity, 'inputs': journal['artifacts'], 'requested_sim_id': sim_id,
             'before_saves': save_files(profile), 'steps': [], 'resume_input_accepted': False,
             'household_loaded_verified': False, 'save_reload_verified': False}
    write_json(output, proof)
    def record(action, result):
        proof['steps'].append({'action': action, 'result': result})
        write_json(output, proof)
        return result
    def still_running():
        return any(row['Id'] == identity['pid'] for row in processes())
    envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})
    try:
        if not proof['before_saves']:
            raise ValueError('No existing normal disposable save was found; Resume was not submitted.')
        if not still_running():
            raise ValueError('Verified game process exited before Resume.')
        hidden = record('overlay_hide', request(state, 'overlay_hide'))
        if not hidden.get('ok'):
            raise ValueError('Could not hide Apex overlay before recognizing native Resume.')
        for attempt in range(3):
            if not still_running():
                raise ValueError('Verified game process changed before Resume.')
            image = output.with_name(output.stem + '-resume-' + str(attempt + 1) + '.bmp')
            frame = record('capture-resume', capture(state, image, request))
            if not frame.get('ok'):
                raise ValueError('Native Resume capture was unresolved; no input submitted.')
            observed = ocr(image)
            try:
                selected = button(observed, 'resume')
            except ValueError as error:
                record('recognize-resume', {'observation': observed, 'error': str(error)})
                # Only observations repeat: never dismiss a card or choose a different menu action.
                pause(0.5)
                continue
            if (selected['width'], selected['height']) != (frame['width'], frame['height']):
                raise ValueError('OCR/capture viewport differs; no Resume click submitted.')
            record('recognize-resume', {'observation': observed, 'selected': selected})
            if not still_running():
                raise ValueError('Verified game process changed before Resume input.')
            result = record('click-resume', request(state, 'test_input', value=envelope(selected)))
            if not result.get('ok'):
                if result.get('input_version') == 2 and result.get('input_submitted') is False and result.get('native_code') == -2:
                    pause(0.5)
                    continue  # Explicit pre-input refusal; reobserve all menu labels and dimensions.
                raise ValueError('Resume input unresolved; no successful or ambiguous press is repeated.')
            proof['resume_input_accepted'] = True
            write_json(output, proof)
            break
        if not proof['resume_input_accepted']:
            raise ValueError('Native Resume surface did not converge; no Resume completion claimed.')
        deadline = monotonic() + seconds
        while monotonic() < deadline and still_running():
            try:
                snapshot = record('test_snapshot', request(state, 'test_snapshot', sim_id=sim_id,
                                                           value=envelope(None), seconds=2))
            except (OSError, ValueError, RuntimeError) as error:
                snapshot = record('test_snapshot', {'ok': False, 'error': str(error)})
            if loaded_household(snapshot, proof['before_saves'], sim_id):
                proof['household_loaded_verified'] = True
                proof['loaded_household'] = snapshot
                break
            pause(min(0.5, max(0, deadline - monotonic())))
        proof['ok'] = proof['household_loaded_verified']
        proof['message'] = ('Existing disposable household loaded; native saved slot, Live Sim and optional requested Sim identity verified.'
                            if proof['ok'] else 'Resume was submitted once; the saved household was not verified. Inspect retained proof before another action.')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
            'resume_input_accepted': proof['resume_input_accepted'],
            'household_loaded_verified': proof['household_loaded_verified'], 'save_reload_verified': False,
            'message': proof.get('message', proof.get('error'))}


def save_files(profile):
    files = {}
    for path in (profile / 'saves').glob('Slot_*.save'):
        matched = re.fullmatch(r'Slot_([0-9a-fA-F]{8})\.save', path.name)
        if matched and 0 < int(matched[1], 16) < 0xffffffff:
            path = reusable_profile.writable(path)
            files[path.name] = {'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns, 'sha256': sha256(path)}
    return files


def refused_before_input(result):
    # These version-2 paths return before button-down. All other failures,
    # timeouts and response loss can have submitted input and must not repeat.
    return (result.get('input_version') == 2 and result.get('input_submitted') is False and
            (result.get('input_state') == -7 or result.get('native_code') == -2))


def shutdown(state, output, identity, request, capture=game_capture.capture, ocr=recognize,
             processes=game_launch.running_game_processes, monotonic=time.monotonic, pause=time.sleep):
    _, journal, profile, original = reusable_profile.load(state)
    output = reusable_profile.writable(output)
    if output.exists() or output.suffix.lower() != '.json' or any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('Use one new external JSON lifecycle proof filename.')
    if not output.parent.is_dir():
        raise ValueError('Use an existing evidence directory.')
    proof = {'schema': 1, 'ok': False, 'operation': 'normal-save-and-exit',
             'identity': identity, 'inputs': journal['artifacts'], 'steps': [],
             'before_saves': save_files(profile), 'game_exit_verified': False,
             'save_completed_file_verified': False, 'save_reload_verified': False}
    write_json(output, proof)
    def record(action, result, require_ok=True):
        proof['steps'].append({'action': action, 'result': result})
        write_json(output, proof)
        if require_ok and not result.get('ok'):
            raise ValueError('Lifecycle step failed; retained proof: ' + action)
        return result
    try:
        record('overlay_hide', request(state, 'overlay_hide'))
        envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})
        image = output.with_name(output.stem + '-initial.bmp')
        frame = record('capture-initial', capture(state, image, request)); observed = ocr(image)
        initial = None
        for phase in ('confirmation', 'menu'):
            try:
                button(observed, phase); initial = (phase, frame, observed); break
            except ValueError: pass
        if initial is None:
            record('quit-menu-request', request(state, 'test_quit', value=envelope(None)))
        phases = ('confirmation',) if initial and initial[0] == 'confirmation' else ('menu', 'confirmation')
        for phase in phases:
            selected, clicked = None, False
            for attempt in range(3):
                if attempt == 0 and initial and initial[0] == phase:
                    _, frame, observed = initial
                else:
                    image = output.with_name(output.stem + '-' + phase + '-' + str(attempt + 1) + '.bmp')
                    frame = record('capture-' + phase, capture(state, image, request)); observed = ocr(image)
                try: selected = button(observed, phase)
                except ValueError as error:
                    proof['steps'].append({'action': 'recognize-' + phase, 'observation': observed, 'error': str(error)})
                    write_json(output, proof)
                    pause(0.5)
                    continue
                if (selected['width'], selected['height']) != (frame['width'], frame['height']):
                    raise ValueError('OCR/capture viewport identity differs; no click submitted.')
                # The accepted label, pixels and native dimensions are recorded
                # before the single identity-protected click is submitted.
                proof['steps'].append({'action': 'recognize-' + phase, 'observation': observed, 'selected': selected})
                write_json(output, proof)
                result = record('click-' + phase, request(state, 'test_input', value=envelope(selected)), require_ok=False)
                if not result.get('ok'):
                    if refused_before_input(result):
                        pause(0.5); continue  # Reobserve the complete native surface before another attempt.
                    raise ValueError('Unresolved lifecycle input; no button press repeated: ' + phase)
                clicked = True
                pause(0.5)
                break
            if not clicked:
                raise ValueError('Native lifecycle surface did not converge; do not repeat quit blindly.')
        deadline = monotonic() + 30
        while monotonic() < deadline:
            if not any(row['Id'] == identity['pid'] for row in processes()):
                proof['game_exit_verified'] = True
                break
            pause(0.5)
        if proof['game_exit_verified']:
            proof['after_saves'] = save_files(profile)
            changed = {name: row for name, row in proof['after_saves'].items() if row != proof['before_saves'].get(name)}
            proof['rewritten_normal_slots'] = changed
            proof['save_completed_file_verified'] = bool(changed)
        proof['ok'] = proof['game_exit_verified'] and proof['save_completed_file_verified']
        proof['message'] = ('Normal Save and Exit completed; disposable save rewrite and game-process exit verified. Reload verification remains separate.'
                            if proof['ok'] else 'Save and Exit was submitted once; save rewrite/process exit were not both verified. Retained proof must be inspected before retrying.')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
            'game_exit_verified': proof['game_exit_verified'], 'save_completed_file_verified': proof['save_completed_file_verified'],
            'save_reload_verified': False, 'message': proof.get('message', proof.get('error'))}
