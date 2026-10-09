"""Leave the exact paused disposable household through its normal menu, unsaved."""
import json
from pathlib import Path
import re
import time

import game_capture
import game_lifecycle
import reusable_profile
from game_load import normalized
from game_save import _save_live_context
from source_manifest import sha256, write_json
from windows_ocr import recognize


def target(observation, phase):
    labels = [normalized(row.get('text', '')) for row in observation.get('lines', [])]
    if observation.get('ok') is not True:
        raise ValueError('Fresh native menu observation is unavailable.')
    if phase == 'menu':
        if (labels.count('menu') != 1 or labels.count('save') != 1 or
                not any(label in labels for label in ('save as', 'save as...', 'save as…')) or
                'save game?' in labels):
            raise ValueError('Complete native Live menu is not recognized.')
        label = 'exit to main menu'
    elif phase == 'confirmation':
        question = ('would you like to save your game before exiting to the' in labels and 'main menu?' in labels)
        if (labels.count('save game?') != 1 or labels.count('cancel') != 1 or
                not (question or any(label in labels for label in ('are you sure you want to exit to the main menu?',
                                                                  'are you sure you want to exit to main menu?'))) or
                labels.count('save and exit') != 1):
            raise ValueError('Complete native main-menu confirmation is not recognized.')
        label = 'exit to main menu'
    else:
        raise ValueError('Unknown main-menu phase.')
    matches = [row for row in observation['lines'] if normalized(row['text']) == label]
    if len(matches) != 1 or not matches[0].get('words'):
        raise ValueError('Exact unsaved main-menu target is absent or ambiguous.')
    from game_load import measured_target
    return measured_target(observation, label)


def observe(state, output, identity, request, sim_id, household_id, save_guid,
            capture=game_capture.capture, ocr=recognize, identity_provider=None,
            pause=time.sleep):
    state_path, journal, profile, original = reusable_profile.load(state)
    if any(not isinstance(value, str) or not re.fullmatch('[1-9][0-9]{0,19}', value) or
           not 0 < int(value) < 1 << 64 for value in (sim_id, household_id, save_guid)):
        raise ValueError('Main-menu exit requires exact Sim, household and save GUID identities.')
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix != '.json' or not output.parent.is_dir() or output == state_path or
            any(output == base or base in output.parents for base in (profile, original))):
        raise ValueError('Use a new external JSON main-menu proof.')
    if identity_provider is None:
        from apex_cli import verified_identity
        identity_provider = verified_identity
    expected_script = next(row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script')
    before = game_lifecycle.all_save_files(profile)
    proof = {'schema': 1, 'ok': False, 'operation': 'normal-unsaved-return-to-main-menu',
             'identity': identity, 'target': {'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid},
             'before_saves': before, 'steps': [], 'save_requested': False, 'input_replayed': False}
    write_json(output, proof)
    def record(action, result):
        proof['steps'].append({'action': action, 'result': result}); write_json(output, proof)
        return result
    def bound():
        observed = identity_provider(state)
        if (observed.get('pid') != identity.get('pid') or observed.get('test_token') != journal['token'] or
                observed.get('script_sha256') != expected_script):
            raise ValueError('Exact bridge/runtime changed; no further native input.')
    def call(action, value=None):
        bound()
        return record(action, request(state, action, sim_id=sim_id,
            value=json.dumps({'test_token': journal['token'], 'value': value}), seconds=2))
    def live_guard():
        bound()
        if game_lifecycle.shutdown_cas_state(call('cas_ui_diagnostics')).get('safe') is not True:
            raise ValueError('Active or unresolved CAS blocks unsaved main-menu exit.')
        observed = call('test_snapshot'); _save_live_context(observed, proof['target'])
        if type(observed.get('clock_speed')) is not int or observed['clock_speed'] != 0:
            raise ValueError('Exact disposable Live household must be paused before main-menu exit.')
    def frame(phase):
        image = output.with_name(output.stem + '-' + phase + '.bmp')
        captured = record('capture-' + phase, capture(state, image, request))
        if captured.get('ok') is not True:
            raise ValueError('Native main-menu capture failed; no input.')
        observed = ocr(image)
        if (captured['width'], captured['height']) != (observed['width'], observed['height']):
            raise ValueError('Fresh main-menu viewport changed.')
        record('observe-' + phase, observed)
        return captured, observed
    def submit(value, phase):
        record('input-' + phase + '-intent', value)
        result = call('test_input', value)
        if result.get('ok') is not True:
            raise ValueError('Native input refused or unresolved; no replay.')
        proof[phase + '_input_accepted'] = True; write_json(output, proof); pause(.5)
    try:
        live_guard()
        hidden = call('overlay_hide')
        if hidden.get('ok') is not True or hidden.get('visible') is not False:
            raise ValueError('Overlay visibility is unresolved.')
        captured, observed = frame('initial')
        labels = [normalized(row['text']) for row in observed['lines']]
        initial_confirmation = 'save game?' in labels
        if initial_confirmation:
            target(observed, 'confirmation')  # Complete normal confirmation, never a generic dialog.
        elif 'menu' not in labels:
            # Only the exact paused Live HUD may receive one Escape.
            if labels.count('paused') != 1 or any(label in labels for label in ('save game?', 'cancel', 'buy now')):
                raise ValueError('Exact paused Live HUD is not recognized; no Escape input.')
            live_guard()
            submit({'command': 2, 'x': 27, 'y': 0, 'width': captured['width'], 'height': captured['height']}, 'escape')
            _, observed = frame('menu')
        if not initial_confirmation:
            live_guard(); submit(target(observed, 'menu'), 'menu')
            _, observed = frame('confirmation')
        live_guard(); submit(target(observed, 'confirmation'), 'confirmation')
        for attempt in range(6):
            pause(.5); _, observed = frame('home-' + str(attempt))
            labels = [normalized(row['text']) for row in observed['lines']]
            if all(labels.count(label) == 1 for label in ('home', 'marketplace', 'load game', 'new game', 'gallery')):
                bound(); proof['home_menu_verified'] = True; proof['ok'] = True; break
        if proof['ok'] is not True:
            raise ValueError('Native Home menu was not verified after the single unsaved exit.')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    proof['after_saves'] = game_lifecycle.all_save_files(profile)
    proof['save_files_unchanged'] = proof['after_saves'] == before
    proof['ok'] = proof['ok'] and proof['save_files_unchanged']
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
            'save_files_unchanged': proof['save_files_unchanged'], 'message': proof.get('error')}
