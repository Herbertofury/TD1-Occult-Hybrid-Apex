"""Select one measured played-lot marker; ordinary Play is a separate operation."""
import json
from pathlib import Path
import re
import time

import cas_transition
import game_capture
import game_lifecycle
import reusable_profile
from game_load import normalized
from save_metadata import read as read_metadata
from source_manifest import sha256, write_json
from windows_ocr import recognize


AUTOSAVE_DRIFT_FILES = frozenset(['Slot_ffffffff.save'] +
                               ['Slot_ffffffff.save.ver{}'.format(index) for index in range(5)])


def _artifact_roster(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20000:
        raise ValueError('Current journal artifact roster is absent or exceeds its bound.')
    names = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name'] or
                not isinstance(row.get('sha256'), str) or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None):
            raise ValueError('Current journal artifact roster is untyped.')
        names.append(row.get('relative', row['name']))
    if any(not isinstance(name, str) or not name or len(name) > 1024 for name in names) or len(names) != len(set(names)):
        raise ValueError('Current journal artifact roster contains ambiguous identities.')
    return rows


def _save_inventory(rows):
    if (not isinstance(rows, dict) or not 1 <= len(rows) <= 1024 or
            any(not isinstance(name, str) or not name or Path(name).name != name or
                not isinstance(row, dict) or set(row) != {'bytes', 'mtime_ns', 'sha256'} or
                type(row['bytes']) is not int or not 0 <= row['bytes'] <= 512 * 1024 * 1024 or
                type(row['mtime_ns']) is not int or row['mtime_ns'] < 0 or
                not isinstance(row['sha256'], str) or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None
                for name, row in rows.items())):
        raise ValueError('Exact named save inventory is absent, untyped or exceeds its bound.')
    return rows


def save_delta(before, after):
    return [{'name': name, 'before': before.get(name), 'after': after.get(name)}
            for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]


def _save_boundary(before, after, allow_autosave_drift, profile, metadata_reader, target):
    delta = save_delta(before, after)
    _save_inventory(before); _save_inventory(after)
    if set(before) != set(after):
        raise ValueError('Exact save inventory names changed.')
    if delta and (not allow_autosave_drift or any(row['name'] not in AUTOSAVE_DRIFT_FILES for row in delta)):
        raise ValueError('Save inventory changed outside the explicitly permitted autosave files.')
    metadata = None; normal_metadata = None; autosave_identity = None
    if allow_autosave_drift:
        filename = 'Slot_ffffffff.save'
        if filename not in after:
            raise ValueError('Explicit autosave drift requires the existing indexed autosave file.')
        metadata = metadata_reader(profile / 'saves' / filename, after[filename]['sha256'])
        if (not isinstance(metadata, dict) or type(metadata.get('slot_id')) is not int or
                metadata.get('save_guid') != target['save_guid'] or
                metadata.get('active_household_id') != target['household_id'] or
                type(metadata.get('preferred_manual_slot_id')) is not int or
                metadata['preferred_manual_slot_id'] != target['slot_id'] or
                metadata.get('file_sha256') != after[filename]['sha256']):
            raise ValueError('Indexed current autosave metadata differs from the exact GUID/household/sentinel/preferred slot.')
        if metadata['slot_id'] == 0xffffffff:
            autosave_identity = 'native-autosave-sentinel'
        elif metadata['slot_id'] == target['slot_id']:
            # Current game builds can write the preferred manual slot ID into
            # the native Autosave proto while retaining the ffffffff filename.
            # This only admits that exact named file, with its untouched normal
            # save independently hash/metadata-bound; it never certifies Live.
            normal_name = 'Slot_{:08x}.save'.format(target['slot_id'])
            normal_hash = target.get('file_sha256', target.get('expected_save_sha256'))
            if (type(target.get('slot_id')) is not int or not 0 < target['slot_id'] < 0xffffffff or
                    metadata.get('slot_name') != 'Autosave' or normal_name not in before or normal_name not in after or
                    before[normal_name] != after[normal_name] or after[normal_name]['sha256'] != normal_hash):
                raise ValueError('Indexed autosave manual-slot identity lacks its named Autosave and unchanged normal-save anchor.')
            normal_metadata = metadata_reader(profile / 'saves' / normal_name, normal_hash)
            if (not isinstance(normal_metadata, dict) or type(normal_metadata.get('slot_id')) is not int or
                    normal_metadata['slot_id'] != target['slot_id'] or normal_metadata.get('save_guid') != target['save_guid'] or
                    normal_metadata.get('active_household_id') != target['household_id'] or
                    normal_metadata.get('file_sha256') != normal_hash or
                    not isinstance(normal_metadata.get('slot_name'), str) or not normal_metadata['slot_name'] or
                    normal_metadata['slot_name'] == 'Autosave' or
                    metadata.get('preferred_manual_slot_name') != normal_metadata['slot_name']):
                raise ValueError('Indexed autosave manual-slot identity differs from its exact normal-save metadata anchor.')
            autosave_identity = 'native-manual-slot-proto-in-named-autosave-file'
        else:
            raise ValueError('Indexed current autosave metadata differs from the exact native sentinel or preferred manual slot.')
    return {'save_files_unchanged': not delta, 'save_files_changed': bool(delta), 'delta': delta,
            'autosave_drift_allowed': allow_autosave_drift,
            'non_autosave_files_unchanged': not any(row['name'] not in AUTOSAVE_DRIFT_FILES for row in delta),
            'indexed_autosave_metadata': metadata, 'autosave_native_identity': autosave_identity,
            'indexed_normal_save_anchor': normal_metadata}


def marker_target(image, observation, expected_world):
    """Measure a unique paired green marker from the current native backbuffer."""
    width, height = image.size
    if (not 200 <= width <= 8192 or not 200 <= height <= 8192 or width * height > 16000000 or
            not isinstance(observation, dict) or observation.get('ok') is not True or
            type(observation.get('width')) is not int or type(observation.get('height')) is not int or
            (observation['width'], observation['height']) != (width, height) or
            not isinstance(expected_world, str) or not normalized(expected_world) or len(expected_world) > 64):
        raise ValueError('Map requires one fresh bounded native viewport and exact world label.')
    lines = observation.get('lines')
    if (not isinstance(lines, list) or not 0 < len(lines) <= 256 or
            any(not isinstance(row, dict) or not isinstance(row.get('text'), str) for row in lines)):
        raise ValueError('Native world OCR is absent or untyped.')
    labels = [normalized(row['text']) for row in lines]
    if (labels.count(normalized(expected_world)) != 1 or
            any(label in labels for label in ('save game?', 'leaving so soon?', 'buy now',
                                             'load game', 'reset current household'))):
        raise ValueError('Exact native world is absent, ambiguous or blocked by another menu.')
    green = set()
    rgb = image.convert('RGB')
    pixels = rgb.get_flattened_data() if hasattr(rgb, 'get_flattened_data') else rgb.getdata()
    for index, pixel in enumerate(pixels):
        red, channel, blue = pixel
        if channel >= 135 and red <= 65 and blue <= 100 and channel - max(red, blue) >= 65:
            green.add(index)
            if len(green) > 100000:
                raise ValueError('Green map observation exceeds its marker bound.')
    components = []
    while green:
        seed = green.pop()
        pending, points = [seed], []
        while pending:
            point = pending.pop(); points.append(point)
            x, y = point % width, point // width
            for adjacent in ((point - 1 if x else -1), (point + 1 if x + 1 < width else -1),
                             (point - width if y else -1), (point + width if y + 1 < height else -1)):
                if adjacent in green:
                    green.remove(adjacent); pending.append(adjacent)
        xs, ys = [point % width for point in points], [point // width for point in points]
        left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
        if len(points) >= 25 and right - left + 1 >= 7 and bottom - top + 1 >= 15:
            components.append({'area': len(points), 'bounds': [left, top, right, bottom]})
            if len(components) > 64:
                raise ValueError('Native played-lot marker components are ambiguous.')
    pairs = []
    components.sort(key=lambda row: row['bounds'][0])
    for index, left in enumerate(components):
        a = left['bounds']
        for right in components[index + 1:]:
            b = right['bounds']
            if (a[1] == b[1] and a[3] == b[3] and 1 <= b[0] - a[2] - 1 <= 8 and
                    14 <= b[2] - a[0] + 1 <= 28 and 15 <= a[3] - a[1] + 1 <= 30 and
                    min(left['area'], right['area']) / max(left['area'], right['area']) >= .5):
                if a[0] <= 0 or a[1] <= 0 or b[2] >= width - 1 or a[3] >= height - 1:
                    raise ValueError('Native played-lot marker is clipped by its viewport.')
                pairs.append((left, right))
    if len(pairs) != 1:
        raise ValueError('Native played-lot marker pair is absent or ambiguous.')
    left, right = pairs[0]
    a, b = left['bounds'], right['bounds']
    return {'command': 1, 'x': round((a[0] + b[2] + 1) / 2), 'y': round((a[1] + a[3] + 1) / 2),
            'width': width, 'height': height, 'bounds': [a[0], a[1], b[2] + 1, a[3] + 1],
            'bounds_convention': 'left-top-inclusive-right-bottom-exclusive',
            'components': [{'area': row['area'], 'bounds': [row['bounds'][0], row['bounds'][1],
                              row['bounds'][2] + 1, row['bounds'][3] + 1]} for row in (left, right)]}


def _native_click(result, pid, viewport=None, point=None):
    metrics = result.get('window_metrics') if isinstance(result, dict) else None
    cursor = result.get('cursor_client') if isinstance(result, dict) else None
    common = (isinstance(result, dict) and result.get('ok') is True and
            type(result.get('native_code')) is int and result['native_code'] == 0 and
            type(result.get('input_state')) is int and result['input_state'] == 4 and
            type(result.get('input_version')) is int and result['input_version'] == 2 and
            result.get('input_submitted') is True and
            result.get('execution') == 'fixed-native-control' and result.get('request_state') == 'completed' and
            isinstance(result.get('request_id'), str) and re.fullmatch('[0-9a-f]{32}', result['request_id']) is not None and
            isinstance(metrics, dict) and metrics.get('available') is True and
            type(metrics.get('overlay_pid')) is int and metrics['overlay_pid'] == pid and
            type(metrics.get('width')) is int and type(metrics.get('height')) is int and
            200 <= metrics['width'] <= 8192 and 200 <= metrics['height'] <= 8192 and
            (viewport is None or (metrics.get('width'), metrics.get('height')) == viewport))
    if not common:
        return False
    if result.get('foreground_required') is False:
        return (result.get('window_messages_accepted') is True and result.get('os_cursor_moved') is False and
                result.get('pointer_verified') is False and type(metrics.get('root_match')) is bool and
                type(metrics.get('foreground_pid')) is int and metrics['foreground_pid'] >= 0 and
                cursor == {'x': -1, 'y': -1})
    return (result.get('pointer_verified') is True and metrics.get('root_match') is True and
            type(metrics.get('foreground_pid')) is int and metrics['foreground_pid'] == pid and
            (point is None or (isinstance(cursor, dict) and set(cursor) == {'x', 'y'} and
                               type(cursor.get('x')) is int and type(cursor.get('y')) is int and
                               (cursor['x'], cursor['y']) == point)))


def _indexed_play_receipt(prior, recovered, pid):
    """Bind one retained completed Play to its ordered measured intent/UUID."""
    steps = prior.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 4096:
        raise ValueError('Indexed Play steps are absent or exceed their bound.')
    phases = ['home', 'play'] if prior.get('initial_surface') == 'native-home-menu' else ['play']
    if prior.get('initial_surface') not in ('native-home-menu', 'native-load-menu'):
        raise ValueError('Prior input was not the measured exact indexed save Play operation.')
    receipts = []
    previous = -1
    for phase in phases:
        recognized = [(i, row) for i, row in enumerate(steps) if isinstance(row, dict) and row.get('action') == 'recognize-' + phase]
        intents = [(i, row) for i, row in enumerate(steps) if isinstance(row, dict) and row.get('action') == 'input-' + phase + '-intent']
        if len(recognized) != 1 or len(intents) != 1:
            raise ValueError('Prior input was not the measured exact indexed save Play operation.')
        at, row = recognized[0]; intent_at, intent = intents[0]
        target = row.get('result', {}).get('target')
        if (not previous < at < intent_at or not isinstance(target, dict) or
                set(target) != {'command', 'x', 'y', 'width', 'height'} or
                any(type(value) is not int for value in target.values()) or target['command'] != 1 or
                not 200 <= target['width'] <= 8192 or not 200 <= target['height'] <= 8192 or
                not 0 <= target['x'] < target['width'] or not 0 <= target['y'] < target['height'] or
                intent.get('result', {}).get('submission_attempted') is not True or intent_at + 1 >= len(steps) or
                steps[intent_at + 1].get('action') != 'test_input'):
            raise ValueError('Prior input was not the measured exact indexed save Play operation.')
        submitted = steps[intent_at + 1]
        receipt = submitted.get('result')
        request_id = submitted.get('request_id', receipt.get('request_id') if isinstance(receipt, dict) else None)
        if (not isinstance(request_id, str) or re.fullmatch('[0-9a-f]{32}', request_id) is None or
                not isinstance(receipt, dict) or receipt.get('request_id') != request_id):
            raise ValueError('Indexed Play request UUID differs from its retained submission.')
        if _native_click(receipt, pid, (target['width'], target['height']), (target['x'], target['y'])):
            if submitted.get('request_id') != request_id:
                raise ValueError('Completed indexed Play lacks its retained pre-submission UUID.')
        else:
            if (phase != 'play' or recovered is None or receipt.get('request_state') not in (None, 'pending', 'unresolved') or
                    recovered.get('same_request_identity') is not True or
                    recovered.get('original_request_id') != request_id or
                    not isinstance(recovered.get('result'), dict) or recovered['result'].get('request_id') != request_id or
                    not _native_click(recovered['result'], pid, (target['width'], target['height']), (target['x'], target['y']))):
                raise ValueError('Recovered original indexed Play input lacks its exact native completed receipt.')
            receipt = recovered['result']
        receipts.append(receipt); previous = intent_at + 1
    all_inputs = [row for row in steps if isinstance(row, dict) and row.get('action') == 'test_input']
    if len(all_inputs) != len(phases) or len({row['request_id'] for row in receipts}) != len(phases):
        raise ValueError('Indexed Play contains extra or reused native input UUIDs.')
    return receipts[-1]


def _durable_native_input(state, sim_id, token, value, request, proof, output):
    row = {'action': 'test_input', 'request_id': None, 'target': value}
    proof['steps'].append(row); write_json(output, proof)
    def submitted(action, request_id):
        if (action != 'test_input' or row['request_id'] is not None or
                not isinstance(request_id, str) or re.fullmatch('[0-9a-f]{32}', request_id) is None):
            raise ValueError('Native map input UUID changed before submission.')
        row['request_id'] = request_id; write_json(output, proof)
    result = request(state, 'test_input', sim_id=sim_id,
        value=json.dumps({'test_token': token, 'value': value}), seconds=2, submission_observer=submitted)
    row['result'] = result; write_json(output, proof)
    if not row['request_id'] or not isinstance(result, dict) or result.get('request_id') != row['request_id']:
        raise ValueError('Native map input has no matching retained submission UUID; never replay.')
    return result


def select_marker(state, output, identity, request, sim_id, household_id, save_guid,
                  slot_id, expected_save_sha256, world, load_proof, load_proof_sha256,
                  recovered_input_proof=None, recovered_input_sha256=None, capture=game_capture.capture,
                  ocr=recognize, identity_provider=None, alive=cas_transition.process_alive,
                  pause=time.sleep, metadata_reader=read_metadata, image_reader=None,
                  allow_autosave_drift=False):
    """One marker click after an exact indexed load; retain the next frame for review."""
    state_path, journal, profile, original = reusable_profile.load(state)
    if (type(allow_autosave_drift) is not bool or type(slot_id) is not int or not 0 < slot_id < 0xffffffff or
            any(not isinstance(value, str) or re.fullmatch('[1-9][0-9]{0,19}', value) is None or
                not 0 < int(value) < 1 << 64 for value in (sim_id, household_id, save_guid)) or
            any(not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None
                for value in (expected_save_sha256, load_proof_sha256)) or
            ((recovered_input_proof is None) != (recovered_input_sha256 is None)) or
            (recovered_input_sha256 is not None and (not isinstance(recovered_input_sha256, str) or
                re.fullmatch('[0-9a-f]{64}', recovered_input_sha256) is None)) or
            not isinstance(world, str) or not normalized(world) or len(world) > 64):
        raise ValueError('Map selection requires exact indexed save, runtime and proof identities.')
    output = reusable_profile.writable(output)
    if (output.exists() or output == state_path or output.suffix.lower() != '.json' or
            not output.parent.is_dir() or any(output == base or base in output.parents for base in (profile, original))):
        raise ValueError('Use a new external map JSON proof outside both profiles and the journal.')
    def read_proof(path, digest):
        path = reusable_profile.writable(path)
        if (path == state_path or any(path == base or base in path.parents for base in (profile, original)) or
                path.suffix.lower() != '.json' or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024 or
                sha256(path) != digest):
            raise ValueError('Prior map prerequisite proof is absent, changed or inside a profile.')
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict): raise ValueError('Prior map prerequisite proof is untyped.')
        return value
    prior = read_proof(load_proof, load_proof_sha256)
    recovered = read_proof(recovered_input_proof, recovered_input_sha256) if recovered_input_proof is not None else None
    _artifact_roster(journal['artifacts'])
    expected_script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    keys = ('pid', 'test_token', 'script_sha256')
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or identity['pid'] <= 0 or
            identity.get('test_token') != journal['token'] or identity.get('script_sha256') != expected_script or
            prior.get('operation') != 'load-exact-existing-disposable-save' or
            not isinstance(prior.get('identity'), dict) or any(prior['identity'].get(key) != identity.get(key) for key in keys) or
            prior.get('inputs') != journal['artifacts'] or prior.get('save_files_unchanged') is not True or
            prior.get('before_saves') != prior.get('after_saves') or prior.get('input_replay_attempted') is not False):
        raise ValueError('Indexed load proof differs from the exact current runtime, artifacts or saves.')
    target = {'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid,
              'slot_id': slot_id, 'file_sha256': expected_save_sha256}
    if any(prior.get('target', {}).get(key) != value for key, value in target.items()):
        raise ValueError('Prior indexed load target differs from the requested original household.')
    receipt = _indexed_play_receipt(prior, recovered, identity['pid'])
    before = game_lifecycle.all_save_files(profile)
    filename = 'Slot_{:08x}.save'.format(slot_id)
    if (filename not in before or
            before[filename]['sha256'] != expected_save_sha256):
        raise ValueError('Exact indexed normal save changed after Play.')
    prerequisite_boundary = _save_boundary(prior['after_saves'], before, allow_autosave_drift,
                                          profile, metadata_reader, target)
    metadata = metadata_reader(profile / 'saves' / filename, expected_save_sha256)
    if (metadata.get('slot_id') != slot_id or metadata.get('save_guid') != save_guid or
            metadata.get('active_household_id') != household_id or metadata != prior.get('indexed_save_metadata')):
        raise ValueError('Indexed native save metadata changed after the verified Play input.')
    state_digest = sha256(state_path)
    if identity_provider is None:
        from apex_cli import verified_identity
        identity_provider = verified_identity
    if image_reader is None:
        from PIL import Image
        image_reader = Image.open
    proof = {'schema': 1, 'ok': False, 'operation': 'select-existing-played-lot-marker',
             'identity': identity, 'inputs': journal['artifacts'], 'target': dict(target, world=world),
             'prerequisites': {'load_proof': str(load_proof), 'load_proof_sha256': load_proof_sha256,
                               'recovered_input_proof': str(recovered_input_proof) if recovered_input_proof is not None else None,
                               'recovered_input_sha256': recovered_input_sha256},
             'indexed_save_metadata': metadata, 'indexed_play_receipt': receipt,
             'before_saves': before, 'steps': [], 'save_requested': False, 'save_file_written': False,
             'indexed_load_baseline_saves': prior['after_saves'],
             'save_comparison_scope': 'indexed-load-baseline-through-marker',
             'prerequisite_save_boundary': prerequisite_boundary, 'allow_autosave_drift': allow_autosave_drift,
             'play_input_accepted': False, 'native_live_verified': False, 'native_slot_verified': False,
             'input_replay_attempted': False, 'outcome': 'unresolved'}
    write_json(output, proof)
    def record(action, result):
        proof['steps'].append({'action': action, 'result': result}); write_json(output, proof)
        return result
    def bound():
        current = identity_provider(state)
        if (not isinstance(current, dict) or any(current.get(key) != identity.get(key) for key in keys) or
                sha256(state_path) != state_digest or not alive(identity['pid'])):
            raise ValueError('Exact game process/profile/source/journal changed; no further input.')
    def guarded_request(_state, action, **kwargs):
        bound(); return request(_state, action, **kwargs)
    def call(action, value=None):
        if action == 'test_input':
            return _durable_native_input(state, sim_id, journal['token'], value, guarded_request, proof, output)
        return record(action, guarded_request(state, action, sim_id=sim_id,
            value=json.dumps({'test_token': journal['token'], 'value': value}), seconds=2))
    def idle():
        if game_lifecycle.shutdown_cas_state(call('cas_ui_diagnostics')).get('safe') is not True:
            raise ValueError('Active or unknown CAS ownership blocks played-lot selection.')
    def frame(phase):
        bound(); idle()
        image = output.with_name(output.stem + '-' + phase + '.bmp')
        captured = record('capture-' + phase, capture(state, image, guarded_request))
        if (captured.get('ok') is not True or captured.get('capture_completed_verified') is not True or
                captured.get('test_token') != journal['token'] or captured.get('inputs') != journal['artifacts'] or
                not image.is_file() or sha256(image) != captured.get('sha256')):
            raise ValueError('Fresh native map capture identity/hash failed; no input replay.')
        observed = record('observe-' + phase, ocr(image))
        if (not isinstance(observed, dict) or observed.get('ok') is not True or
                (captured.get('width'), captured.get('height')) != (observed.get('width'), observed.get('height'))):
            raise ValueError('Fresh native map OCR/capture viewport is unresolved.')
        return image, captured, observed
    try:
        bound(); idle()
        hidden = call('overlay_hide')
        if hidden.get('ok') is not True or hidden.get('visible') is not False:
            raise ValueError('Overlay visibility is unresolved; no marker input.')
        image, captured, observed = frame('map')
        with image_reader(image) as pixels:
            selected = marker_target(pixels, observed, world)
        if (captured['width'], captured['height']) != (selected['width'], selected['height']):
            raise ValueError('Measured marker and native capture dimensions differ.')
        record('measured-played-lot-marker', selected)
        idle(); bound()
        current_saves = game_lifecycle.all_save_files(profile)
        record('pre-input-save-boundary', _save_boundary(before, current_saves, allow_autosave_drift,
                                                        profile, metadata_reader, target))
        if sha256(image) != captured['sha256']:
            raise ValueError('Measured frame changed before marker input; no input submitted.')
        value = {key: selected[key] for key in ('command', 'x', 'y', 'width', 'height')}
        record('input-marker-intent', {'submission_attempted': True, 'target': value})
        submitted = call('test_input', value)
        if not _native_click(submitted, identity['pid'], (selected['width'], selected['height']),
                             (selected['x'], selected['y'])):
            raise ValueError('Marker input refused or unresolved; the click is never replayed.')
        proof['marker_input_accepted'] = True; write_json(output, proof); pause(.5)
        _, _, selected_observation = frame('selected-household')
        proof.update(ok=True, post_click_capture_verified=True,
                     selected_household_observation=selected_observation,
                     post_click_capture=str(output.with_name(output.stem + '-selected-household.bmp')),
                     outcome='marker-click-captured-awaiting-household-inspection')
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    proof['after_saves'] = game_lifecycle.all_save_files(profile)
    proof['operation_save_files_unchanged'] = proof['after_saves'] == before
    proof['operation_save_delta'] = save_delta(before, proof['after_saves'])
    proof['save_files_unchanged'] = proof['after_saves'] == prior['after_saves']
    proof['save_files_changed'] = not proof['save_files_unchanged']
    proof['save_delta'] = save_delta(prior['after_saves'], proof['after_saves'])
    try:
        proof['final_save_boundary'] = _save_boundary(prior['after_saves'], proof['after_saves'], allow_autosave_drift,
                                                      profile, metadata_reader, target)
    except (OSError, ValueError, RuntimeError) as error:
        proof.update(ok=False, outcome='save-files-changed-unexpectedly')
        proof['save_boundary_error'] = str(error)
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
            'marker_input_accepted': proof.get('marker_input_accepted', False),
            'native_live_verified': False, 'native_slot_verified': False,
            'save_files_unchanged': proof['save_files_unchanged'], 'save_files_changed': proof['save_files_changed'],
            'allow_autosave_drift': allow_autosave_drift, 'outcome': proof['outcome'],
            'message': proof.get('error')}
