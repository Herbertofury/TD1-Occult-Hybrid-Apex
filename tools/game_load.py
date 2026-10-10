"""Load one existing disposable save through its ordinary native menu.

No direct persistence call, save, guessed slot, pack dismissal or input replay.
An observed map without the exact requested Live household remains unresolved.
"""
import json
import math
from pathlib import Path
import re
import time

import cas_transition
import game_capture
import game_lifecycle
import reusable_profile
from game_save import _save_live_context
from source_manifest import sha256, write_json
from windows_ocr import recognize
from save_metadata import read as read_metadata


def normalized(text):
    return ' '.join(str(text).split()).casefold()


def menu_target(observation, phase, slot_name):
    if (not isinstance(observation, dict) or observation.get('ok') is not True or
            type(observation.get('width')) is not int or type(observation.get('height')) is not int or
            not 200 <= observation['width'] <= 8192 or not 200 <= observation['height'] <= 8192):
        raise ValueError('Load requires a fresh typed native game viewport.')
    lines = observation.get('lines')
    if not isinstance(lines, list) or not 0 < len(lines) <= 256:
        raise ValueError('Load menu text is absent or exceeds its bound.')
    if any(not isinstance(row, dict) or not isinstance(row.get('text'), str) for row in lines):
        raise ValueError('Load menu text is untyped.')
    labels = [normalized(row['text']) for row in lines]
    forbidden = ('save game?', 'buy now', 'this game requires permissions', "you don't have access",
                 'you don’t have access', 'leaving so soon?', 'reset current household')
    if any(label in labels for label in forbidden):
        raise ValueError('Another native dialog blocks load; no input submitted.')
    if phase == 'home':
        # The current WinRT/font observation merges the Resume plumbob into
        # "IRESUME GAME" and can omit the selected Home tab. Require the full
        # four-control Home surface and one exact known header spelling.
        resume_count = sum(labels.count(label) for label in ('resume game', 'iresume game'))
        header = labels.count('home') == 1 or resume_count == 1
        # At the observed 2560x1385 viewport, OCR returns both exact Home and
        # Resume labels plus every gameplay control but misses Marketplace.
        # Require both independent headers in that specific missing-label case;
        # a lone Load Game or partial Home surface still cannot authorize input.
        marketplace = labels.count('marketplace')
        marketplace_verified = marketplace == 1 or (marketplace == 0 and
            labels.count('home') == 1 and resume_count == 1)
        if (not header or not marketplace_verified or
                any(labels.count(label) != 1 for label in ('load game', 'new game', 'gallery')) or
                any(label in labels for label in ('autosave', 'play'))):
            raise ValueError('Complete native Home menu is not recognized.')
        label = 'load game'
    elif phase in ('row', 'play'):
        name = normalized(slot_name)
        # WinRT reads the installed font's trailing numeral 1 as uppercase I.
        # This sole alias is allowed only for the exact indexed save name;
        # native slot/GUID/household readback must still establish the load.
        aliases = [name] + ([name[:-1] + 'i'] if name.endswith('1') else [])
        matches = [row for row in lines if normalized(row['text']) in aliases]
        if labels.count('load game') != 1 or len(matches) != 1:
            raise ValueError('Native load menu lacks one exact requested save name.')
        # Play is the installed English SAVE_LOAD_LOAD_BUTTON, not an invented
        # generic Load button. Only the currently selected save may be played.
        label = normalized(matches[0]['text'])
        name_target = measured_target(observation, label)
        if phase == 'play':
            candidates = []
            for row in lines:
                if normalized(row['text']) != 'play': continue
                measured = measured_target(dict(observation, lines=[row]), 'play')
                # Each native slot's Play belongs to that row's parent control.
                # Select exactly one measured Play to the right on the same row,
                # never a global first Play (which can be Autosave).
                if measured['x'] > name_target['x'] and abs(measured['y'] - name_target['y']) <= 16:
                    candidates.append(measured)
            if len(candidates) != 1:
                raise ValueError('Requested save row has no unique measured native Play button.')
            return candidates[0]
    else:
        raise ValueError('Unknown native load phase.')
    return measured_target(observation, label)


def measured_target(observation, label):
    if (type(observation.get('width')) is not int or type(observation.get('height')) is not int or
            not 200 <= observation['width'] <= 8192 or not 200 <= observation['height'] <= 8192):
        raise ValueError('Native menu target requires a bounded typed viewport.')
    matches = [row for row in observation.get('lines', []) if normalized(row.get('text', '')) == label]
    if len(matches) != 1:
        raise ValueError('Native load target is absent or ambiguous.')
    words = matches[0].get('words')
    if not isinstance(words, list) or not 0 < len(words) <= 64:
        raise ValueError('Native load target has no bounded measured rectangle.')
    rectangles = []
    for word in words:
        if not isinstance(word, dict):
            raise ValueError('Native load target word is untyped.')
        bounds = [word.get(field) for field in ('x', 'y', 'width', 'height')]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in bounds):
            raise ValueError('Native load target requires finite measured bounds.')
        x, y, width, height = bounds
        if not 0 <= x < x + width <= observation['width'] or not 0 <= y < y + height <= observation['height']:
            raise ValueError('Native load target is outside its current viewport.')
        rectangles.append((x, y, x + width, y + height))
    return {'command': 1, 'x': round((min(row[0] for row in rectangles) + max(row[2] for row in rectangles)) / 2),
            'y': round((min(row[1] for row in rectangles) + max(row[3] for row in rectangles)) / 2),
            'width': observation['width'], 'height': observation['height']}


def cold_menu_guard(identity, observed, phase, slot_name):
    """Admit only a measured cold Home/indexed-load menu, never a CAS view.

    Before the first household loads there is no TimeService/game-thread CAS
    dispatcher. The fixed native input route is independent of that dispatcher.
    An empty cold bridge plus the complete freshly captured ordinary menu is
    required; this exception cannot finish a load or authorize Sim mutations.
    """
    queue = identity.get('queue') if isinstance(identity, dict) else None
    if (not isinstance(identity, dict) or identity.get('native_cli_available') is not True or
            identity.get('core_tick_ready') is not False or identity.get('alarm_ready') is not False or
            type(identity.get('core_ticks')) is not int or identity['core_ticks'] != 0 or
            not isinstance(queue, dict) or queue.get('closed') is not False or
            any(type(queue.get(name)) is not int or queue[name] != 0 for name in ('pending', 'retained')) or
            phase not in ('home', 'play')):
        raise ValueError('Native cold-menu admission requires an empty never-ticked bridge and a measured ordinary menu.')
    menu_target(observed, phase, slot_name)
    return {'safe': True, 'outcome': 'measured-cold-native-menu', 'phase': phase,
            'game_thread_unavailable': True, 'sim_mutation_authorized': False,
            'live_completion_established': False}


def observe(state, output, identity, request, sim_id, household_id, save_guid,
            slot_id, slot_name, expected_save_sha256, seconds=60, capture=game_capture.capture,
            ocr=recognize, identity_provider=None, alive=cas_transition.process_alive,
            monotonic=time.monotonic, pause=time.sleep, metadata_reader=read_metadata):
    state_path, journal, profile, original = reusable_profile.load(state)
    if (type(slot_id) is not int or not 0 < slot_id < 0xffffffff or
            not isinstance(slot_name, str) or not 0 < len(slot_name) <= 64 or
            any(ord(char) < 32 for char in slot_name) or slot_name != slot_name.strip() or
            any(not isinstance(value, str) or re.fullmatch(r'[1-9][0-9]{0,19}', value) is None or
                not 0 < int(value) < 1 << 64 for value in (sim_id, household_id, save_guid)) or
            not isinstance(expected_save_sha256, str) or re.fullmatch('[0-9a-f]{64}', expected_save_sha256) is None or
            type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60):
        raise ValueError('Load requires exact existing save/Sim identities, file hash and bounded timeout.')
    output = reusable_profile.writable(output)
    if (output.exists() or output == state_path or output.suffix.lower() != '.json' or
            not output.parent.is_dir() or any(output == base or base in output.parents for base in (profile, original))):
        raise ValueError('Use a new external JSON load proof outside both profiles and the journal.')
    before = game_lifecycle.all_save_files(profile)
    filename = 'Slot_{:08x}.save'.format(slot_id)
    if filename not in before or before[filename]['sha256'] != expected_save_sha256:
        raise ValueError('The exact requested existing save changed; no game input submitted.')
    metadata = metadata_reader(profile / 'saves' / filename, expected_save_sha256)
    if (metadata.get('save_guid') != save_guid or metadata.get('slot_id') != slot_id or
            metadata.get('active_household_id') != household_id or metadata.get('slot_name') != slot_name):
        raise ValueError('Indexed native save metadata differs from the requested slot/name/GUID/household.')
    if identity_provider is None:
        from apex_cli import verified_identity
        identity_provider = verified_identity
    expected_script = next((row['sha256'] for row in journal['artifacts']
                            if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    proof = {'schema': 1, 'ok': False, 'operation': 'load-exact-existing-disposable-save',
             'identity': identity, 'inputs': journal['artifacts'], 'before_saves': before, 'steps': [],
             'target': {'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid,
                        'slot_id': slot_id, 'slot_name': slot_name, 'file_sha256': expected_save_sha256},
             'save_file_written': False, 'indexed_save_metadata': metadata,
             'native_slot_verified': False, 'native_live_verified': False,
             'outcome': 'unresolved', 'input_replay_attempted': False}
    write_json(output, proof)
    envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})
    def record(action, result):
        proof['steps'].append({'action': action, 'result': result}); write_json(output, proof)
        return result
    def bound():
        current = identity_provider(state)
        if (not isinstance(current, dict) or current.get('pid') != identity.get('pid') or
                current.get('test_token') != journal['token'] or current.get('script_sha256') != expected_script or
                not alive(identity['pid'])):
            raise ValueError('The exact game process/profile/source changed; no further input submitted.')
        return current
    def call(action, value=None):
        bound()
        return record(action, request(state, action, sim_id=sim_id, value=envelope(value), seconds=2))
    def idle(observed=None, phase=None):
        current = bound()
        if current.get('core_tick_ready') is False:
            return record('cold-native-menu-admission', cold_menu_guard(current, observed, phase, slot_name))
        guard = game_lifecycle.shutdown_cas_state(call('cas_ui_diagnostics'))
        if guard.get('safe') is not True:
            raise ValueError('Active or unknown CAS ownership blocks load.')
    def read_live():
        try:
            result = call('test_snapshot')
        except (OSError, ValueError, RuntimeError) as error:
            return record('snapshot-unavailable', {'ok': False, 'error': str(error)})
        return result
    def exact_live(snapshot):
        _save_live_context(snapshot, proof['target'])
        if snapshot.get('save_slot') != slot_id:
            raise ValueError('Actual native save slot differs; autosave metadata cannot prove this load.')
        if type(snapshot.get('clock_speed')) is not int or snapshot['clock_speed'] not in (0, 1, 2, 3):
            raise ValueError('Native loaded clock is untyped.')
        return snapshot
    try:
        current = bound()
        if current.get('core_tick_ready') is not False:
            idle()
        game_capture.prepare_window(state, request, proof.setdefault('renderer', {}),
                                    lambda: write_json(output, proof), identity, identity_provider)
        hidden = call('overlay_hide')
        if hidden.get('ok') is not True or hidden.get('visible') is not False:
            raise ValueError('Overlay visibility is unresolved; no load input submitted.')
        pre = read_live()
        if pre.get('zone_running') is True or pre.get('sim', {}).get('instanced') is True:
            exact_live(pre)
            proof['already_loaded'] = True
        else:
            for phase in ('home', 'play'):
                if phase == 'play' and proof.get('play_input_accepted') is True:
                    break
                current = bound()
                if current.get('core_tick_ready') is not False:
                    idle()
                image = output.with_name(output.stem + '-' + phase + '.bmp')
                frame = record('capture-' + phase, capture(state, image, request))
                if frame.get('ok') is not True:
                    raise ValueError('Fresh native load capture failed; no input submitted.')
                observed = ocr(image)
                record('observe-' + phase, observed)  # Keep an unrecognized surface as evidence too.
                if phase == 'home':
                    try:
                        selected = menu_target(observed, 'play', slot_name)
                        proof['initial_surface'] = 'native-load-menu'
                    except ValueError:
                        selected = menu_target(observed, 'home', slot_name)
                        proof['initial_surface'] = 'native-home-menu'
                else:
                    selected = menu_target(observed, phase, slot_name)
                if (frame['width'], frame['height']) != (selected['width'], selected['height']):
                    raise ValueError('Load OCR/capture viewport changed; no input submitted.')
                submitted_phase = 'play' if phase == 'home' and proof['initial_surface'] == 'native-load-menu' else phase
                record('recognize-' + submitted_phase, {'observation': observed, 'target': selected})
                idle(observed, submitted_phase); bound()
                record('input-' + submitted_phase + '-intent', {'submission_attempted': True})
                result = call('test_input', selected)
                if result.get('ok') is not True:
                    raise ValueError('Native load input refused or unresolved; never repeat this proof.')
                proof[submitted_phase + '_input_accepted'] = True; write_json(output, proof)
                pause(0.5)
        deadline = monotonic() + seconds
        while monotonic() < deadline:
            bound()
            snapshot = read_live()
            if snapshot.get('zone_running') is True or snapshot.get('sim', {}).get('instanced') is True:
                exact_live(snapshot); idle()
                if snapshot['clock_speed'] != 0:
                    paused = call('test_pause'); exact_live(paused)
                    if paused.get('clock_speed') != 0:
                        raise ValueError('Loaded Live pause did not read back; no input replay.')
                final = exact_live(call('test_snapshot')); idle()
                if final.get('clock_speed') != 0:
                    raise ValueError('Final loaded Live context is not paused.')
                proof.update(ok=True, native_slot_verified=True, native_live_verified=True,
                             loaded=final, outcome='exact-existing-slot-live-verified')
                break
            pause(0.5)
        if not proof['ok']:
            proof['message'] = 'Load was submitted once; the exact native slot and Live household were not verified. A neighborhood map remains unresolved.'
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    proof['after_saves'] = game_lifecycle.all_save_files(profile)
    proof['save_files_unchanged'] = proof['after_saves'] == before
    if not proof['save_files_unchanged']:
        proof.update(ok=False, outcome='save-files-changed-unexpectedly')
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
            'native_slot_verified': proof['native_slot_verified'], 'native_live_verified': proof['native_live_verified'],
            'outcome': proof['outcome'], 'message': proof.get('error', proof.get('message'))}
