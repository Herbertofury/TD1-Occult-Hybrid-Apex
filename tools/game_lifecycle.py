"""Normal Save and Exit through recognized, game-owned native menu buttons."""
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
