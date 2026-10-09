"""Play one selected disposable household through its measured native control.

The household, save and capture are hash-bound before one input. Actual Live
membership, final pause and the native normal slot are separate readbacks.
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
from game_load import _save_live_context, normalized
from game_map import _native_click, save_delta
from save_household import read as read_household
from source_manifest import sha256, write_json
from windows_ocr import recognize


CAPTION = 'Bright Cliff Apartments'


def _bounds(row, width, height):
    words = row.get('words')
    if not isinstance(words, list) or not 0 < len(words) <= 64:
        raise ValueError('Selected household OCR has no measured bounds.')
    rectangles = []
    for word in words:
        if not isinstance(word, dict):
            raise ValueError('Selected household OCR word is untyped.')
        values = [word.get(key) for key in ('x', 'y', 'width', 'height')]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
            raise ValueError('Selected household OCR bounds are nonfinite or untyped.')
        x, y, w, h = values
        if not 0 <= x < x + w <= width or not 0 <= y < y + h <= height:
            raise ValueError('Selected household OCR bounds exceed their viewport.')
        rectangles.append((x, y, x + w, y + h))
    return [min(row[0] for row in rectangles), min(row[1] for row in rectangles),
            max(row[2] for row in rectangles), max(row[3] for row in rectangles)]


def _white(pixel, minimum=225):
    return min(pixel[:3]) >= minimum and max(pixel[:3]) - min(pixel[:3]) <= 20


def play_target(image, observation, household_name, expected_caption=CAPTION):
    """Require the household panel and measure its unique filled Play triangle."""
    width, height = image.size
    if (not 200 <= width <= 8192 or not 200 <= height <= 8192 or width * height > 16000000 or
            not isinstance(observation, dict) or observation.get('ok') is not True or
            type(observation.get('width')) is not int or type(observation.get('height')) is not int or
            (observation['width'], observation['height']) != (width, height) or
            not isinstance(household_name, str) or not normalized(household_name) or len(household_name) > 256):
        raise ValueError('Play requires a fresh bounded native viewport and indexed household name.')
    lines = observation.get('lines')
    if (not isinstance(lines, list) or not 0 < len(lines) <= 256 or
            any(not isinstance(row, dict) or not isinstance(row.get('text'), str) for row in lines)):
        raise ValueError('Selected household OCR is absent or untyped.')
    labels = [normalized(row['text']) for row in lines]
    if any(label in labels for label in ('save game?', 'leaving so soon?', 'buy now', 'load game',
            'this game requires permissions', "you don't have access", 'you don’t have access')):
        raise ValueError('Another native dialog blocks selected household Play.')
    captions = [row for row in lines if normalized(row['text']) == normalized(expected_caption)]
    if len(captions) != 1 or _bounds(captions[0], width, height)[3] > height * .12:
        raise ValueError('Exact apartment caption is absent, ambiguous or outside its native header.')
    names = []
    for row in lines:
        if normalized(row['text']) == normalized(household_name):
            box = _bounds(row, width, height)
            if box[2] < width * .55 and box[1] > height * .6:
                names.append(box)
    if len(names) != 1:
        raise ValueError('Exact indexed household name is absent or ambiguous in its detail panel.')
    funds = []
    for row in lines:
        match = re.fullmatch(r'funds\s*:\s*[$§s]?\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)', normalized(row['text']))
        if not match:
            continue
        box = _bounds(row, width, height)
        if (box[2] < width * .55 and names[0][3] <= box[1] <= names[0][3] + height * .08 and
                abs((box[0] + box[2] - names[0][0] - names[0][2]) / 2) <= width * .08):
            funds.append((box, int(match[1].replace(',', ''))))
    if len(funds) != 1 or not 0 <= funds[0][1] <= 0x7fffffff:
        raise ValueError('Selected household Funds panel is absent or ambiguous.')
    rgb = image.convert('RGB'); pixels = rgb.load()
    # Empty description text is too pale for OCR. Measure its white rectangle
    # below the authenticated name/Funds rows instead of inventing that label.
    scan_y = round(funds[0][0][3] + height * .04)
    runs, start = [], None
    for x in range(round(width * .55)):
        white = 0 <= scan_y < height and _white(pixels[x, scan_y])
        if white and start is None: start = x
        if start is not None and (not white or x == round(width * .55) - 1):
            right = x if not white else x + 1
            if width * .18 <= right - start <= width * .48:
                runs.append((start, right))
            start = None
    fund_x = (funds[0][0][0] + funds[0][0][2]) / 2
    descriptions = []
    for left, right in runs:
        if not left < fund_x < right or scan_y + height * .1 >= height:
            continue
        probes = [round(scan_y + height * fraction) for fraction in (0, .05, .1)]
        if all(sum(_white(pixels[x, y]) for x in range(left + 3, right - 3)) /
               (right - left - 6) >= .98 for y in probes):
            descriptions.append([left, scan_y, right, probes[-1] + 1])
    if len(descriptions) != 1:
        raise ValueError('Selected household description panel is absent or ambiguous.')
    blue = set()
    for y in range(round(height * .75), height):
        for x in range(round(width * .7), width):
            red, green, channel = pixels[x, y]
            if channel >= 130 and channel - red >= 65 and channel - green >= 40 and red <= 80 and 30 <= green <= 150:
                blue.add((x, y))
                if len(blue) > 100000:
                    raise ValueError('Native Play blue components exceed their bound.')
    triangles = []
    while blue:
        seed = blue.pop(); pending, points = [seed], []
        while pending:
            x, y = pending.pop(); points.append((x, y))
            for adjacent in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if adjacent in blue:
                    blue.remove(adjacent); pending.append(adjacent)
        if len(points) < 100:
            continue
        xs, ys = zip(*points); left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
        w, h = right - left + 1, bottom - top + 1
        if not (20 <= w <= 100 and 24 <= h <= 120 and .65 <= w / h <= 1.05 and .38 <= len(points) / (w * h) <= .62):
            continue
        rows = {}
        for x, y in points: rows.setdefault(y, []).append(x)
        widths = [max(rows[y]) - min(rows[y]) + 1 for y in range(top, bottom + 1)] if len(rows) == h else []
        if (not widths or sum(abs(min(row) - left) <= 1 for row in rows.values()) / h < .9 or
                any(len(row) / (max(row) - min(row) + 1) < .9 for row in rows.values()) or
                not .3 * h <= widths.index(max(widths)) <= .7 * h or
                max(widths[:max(1, h // 10)] + widths[-max(1, h // 10):]) > w * .3):
            continue
        center_x, center_y = left + w * .35, (top + bottom) / 2
        def sample(dx, dy):
            x, y = round(center_x + dx * h), round(center_y + dy * h)
            # The native white button has a shaded lower half; its measured
            # normal frame reaches 222 while the surrounding panel is <150.
            return _white(pixels[x, y], 210) if 1 <= x < width - 1 and 1 <= y < height - 1 else None
        inner = [sample(dx, dy) for dx, dy in ((-.65, 0), (.65, 0), (0, -.65), (0, .65))]
        outer = [sample(dx, dy) for dx, dy in ((-.7, -.7), (.7, -.7), (-.7, .7), (.7, .7))]
        if not all(value is True for value in inner) or any(value is None for value in outer) or sum(value is False for value in outer) < 3:
            continue
        centroid = (sum(xs) / len(points), sum(ys) / len(points))
        chosen = min(points, key=lambda point: (point[0] - centroid[0]) ** 2 + (point[1] - centroid[1]) ** 2)
        triangles.append({'command': 1, 'x': chosen[0], 'y': chosen[1], 'width': width, 'height': height,
            'bounds': [left, top, right + 1, bottom + 1], 'component_area': len(points),
            'bounds_convention': 'left-top-inclusive-right-bottom-exclusive',
            'household_name': household_name, 'funds': funds[0][1],
            'description_bounds': descriptions[0], 'caption': expected_caption})
    if len(triangles) != 1:
        raise ValueError('Native filled Play triangle and white circle are absent or ambiguous.')
    return triangles[0]


def observe(state, output, identity, request, sim_id, household_id, save_guid,
            slot_id, expected_save_sha256, selection_proof, selection_proof_sha256,
            seconds=60, capture=game_capture.capture, ocr=recognize,
            identity_provider=None, alive=cas_transition.process_alive,
            monotonic=time.monotonic, pause=time.sleep, metadata_reader=read_household, image_reader=None):
    state_path, journal, profile, original = reusable_profile.load(state)
    if (type(slot_id) is not int or not 0 < slot_id < 0xffffffff or
            any(not isinstance(value, str) or re.fullmatch('[1-9][0-9]{0,19}', value) is None or
                not 0 < int(value) < 1 << 64 for value in (sim_id, household_id, save_guid)) or
            any(not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None
                for value in (expected_save_sha256, selection_proof_sha256)) or
            type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60):
        raise ValueError('Play requires exact existing save/Sim/proof identities and a bounded timeout.')
    output = reusable_profile.writable(output)
    if (output.exists() or output == state_path or output.suffix.lower() != '.json' or
            not output.parent.is_dir() or any(output == base or base in output.parents for base in (profile, original))):
        raise ValueError('Use a new external Play JSON proof outside both profiles and the journal.')
    def read_proof(path, digest):
        path = reusable_profile.writable(path)
        if (path == state_path or any(path == base or base in path.parents for base in (profile, original)) or
                path.suffix.lower() != '.json' or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024 or
                sha256(path) != digest):
            raise ValueError('Selected household prerequisite proof is absent, changed or inside a profile.')
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict): raise ValueError('Selected household prerequisite is untyped.')
        return value
    prior = read_proof(selection_proof, selection_proof_sha256)
    expected_script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    keys = ('pid', 'test_token', 'script_sha256')
    target = {'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid,
              'slot_id': slot_id, 'file_sha256': expected_save_sha256}
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or identity.get('script_sha256') != expected_script or
            len(journal['artifacts']) != 14 or prior.get('operation') != 'select-existing-disposable-household-unit' or
            prior.get('ok') is not True or prior.get('schema') != 1 or
            not isinstance(prior.get('identity'), dict) or any(prior['identity'].get(key) != identity.get(key) for key in keys) or
            prior.get('inputs') != journal['artifacts'] or prior.get('save_files_unchanged') is not True or
            prior.get('before_saves') != prior.get('after_saves') or prior.get('input_replay_attempted') is not False or
            prior.get('save_requested') is not False or
            any(prior.get('target', {}).get(key) != value for key, value in target.items())):
        raise ValueError('Selected household proof differs from the exact current runtime, artifacts or target.')
    before = game_lifecycle.all_save_files(profile)
    filename = 'Slot_{:08x}.save'.format(slot_id)
    if len(before) != 18 or before != prior.get('after_saves') or before.get(filename, {}).get('sha256') != expected_save_sha256:
        raise ValueError('Exact eighteen-file save baseline changed after household selection.')
    metadata = metadata_reader(profile / 'saves' / filename, expected_save_sha256, household_id, sim_id)
    if (not isinstance(metadata, dict) or metadata != prior.get('indexed_household') or
            not isinstance(prior.get('indexed_save_metadata'), dict) or
            any(metadata.get(key) != value for key, value in prior['indexed_save_metadata'].items()) or
            metadata.get('slot_id') != slot_id or metadata.get('save_guid') != save_guid or
            metadata.get('file_sha256') != expected_save_sha256 or metadata.get('active_household_id') != household_id or
            metadata.get('selected_membership_verified') is not True or metadata.get('selected_household_is_active') is not True or
            metadata.get('household', {}).get('id') != household_id or metadata.get('sim', {}).get('id') != sim_id or
            metadata.get('sim', {}).get('household_id') != household_id or
            sim_id not in metadata.get('household', {}).get('member_ids', [])):
        raise ValueError('Indexed selected household metadata or native identity changed.')
    household_name = metadata.get('household', {}).get('name')
    selected_capture = prior.get('capture')
    if not isinstance(selected_capture, dict) or not isinstance(selected_capture.get('result'), dict):
        raise ValueError('Selected household proof has no typed native capture.')
    previous_capture = read_proof(selected_capture.get('proof', ''), selected_capture.get('proof_sha256', ''))
    if previous_capture != selected_capture['result']:
        raise ValueError('Selected native capture receipt changed.')
    viewport = (previous_capture.get('width'), previous_capture.get('height'))
    previous_image = reusable_profile.writable(previous_capture.get('output', ''))
    if (any(previous_image == base or base in previous_image.parents for base in (profile, original)) or
            not previous_image.is_file() or sha256(previous_image) != previous_capture.get('sha256') or
            previous_capture.get('ok') is not True or previous_capture.get('capture_completed_verified') is not True or
            previous_capture.get('test_token') != journal['token'] or previous_capture.get('inputs') != journal['artifacts']):
        raise ValueError('Selected native capture pixels, token or artifacts changed.')
    clicks = prior.get('native_inputs')
    if not isinstance(clicks, list) or len(clicks) != 3:
        raise ValueError('Selected household proof requires its three retained native input receipts.')
    for click in clicks:
        if (not isinstance(click, dict) or read_proof(click.get('proof', ''), click.get('sha256', '')) != click.get('result') or
                not _native_click(click.get('result'), identity['pid'], viewport)):
            raise ValueError('A selected household native input receipt changed or did not complete.')
    if len({click['result']['request_id'] for click in clicks}) != 3:
        raise ValueError('Selected household native input receipts do not represent three distinct requests.')
    if image_reader is None:
        from PIL import Image
        image_reader = Image.open
    with image_reader(previous_image) as pixels:
        prior_target = play_target(pixels, prior.get('selected_household_observation'), household_name)
    if identity_provider is None:
        from apex_cli import verified_identity
        identity_provider = verified_identity
    state_digest = sha256(state_path)
    proof = {'schema': 1, 'ok': False, 'operation': 'play-existing-selected-disposable-household',
        'identity': identity, 'inputs': journal['artifacts'], 'target': target,
        'selection_proof': str(selection_proof), 'selection_proof_sha256': selection_proof_sha256,
        'indexed_household': metadata, 'before_saves': before, 'steps': [],
        'household_verified': False, 'native_live_verified': False, 'native_slot_verified': False,
        'play_input_accepted': False, 'save_requested': False, 'save_file_written': False,
        'input_replay_attempted': False, 'outcome': 'unresolved',
        'scope': 'One native Play input and readbacks; save_file_written=False means no host save request, while save_delta records actual files.'}
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
        return record(action, guarded_request(state, action, sim_id=sim_id,
            value=json.dumps({'test_token': journal['token'], 'value': value}), seconds=2))
    def idle():
        if game_lifecycle.shutdown_cas_state(call('cas_ui_diagnostics')).get('safe') is not True:
            raise ValueError('Active or unknown CAS ownership blocks selected household Play.')
    def context(snapshot):
        _save_live_context(snapshot, target)
        if type(snapshot.get('clock_speed')) is not int or snapshot['clock_speed'] not in (0, 1, 2, 3):
            raise ValueError('Native loaded clock is untyped.')
        return snapshot
    try:
        bound(); idle()
        hidden = call('overlay_hide')
        if hidden.get('ok') is not True or hidden.get('visible') is not False:
            raise ValueError('Overlay visibility is unresolved; no household Play input.')
        image = output.with_name(output.stem + '-selected-household.bmp')
        captured = record('capture-selected-household', capture(state, image, guarded_request))
        if (captured.get('ok') is not True or captured.get('capture_completed_verified') is not True or
                captured.get('test_token') != journal['token'] or captured.get('inputs') != journal['artifacts'] or
                not image.is_file() or sha256(image) != captured.get('sha256')):
            raise ValueError('Fresh selected household capture identity/hash failed.')
        observation = record('observe-selected-household', ocr(image))
        with image_reader(image) as pixels:
            selected = play_target(pixels, observation, household_name)
        if ((captured.get('width'), captured.get('height')) != (selected['width'], selected['height']) or
                selected['funds'] != prior_target['funds']):
            raise ValueError('Selected household native viewport or Funds changed before Play.')
        record('measured-native-play', selected); idle(); bound()
        if game_lifecycle.all_save_files(profile) != before or sha256(image) != captured['sha256']:
            raise ValueError('Measured native frame or save baseline changed before Play.')
        value = {key: selected[key] for key in ('command', 'x', 'y', 'width', 'height')}
        record('input-play-intent', {'submission_attempted': True, 'target': value})
        submitted = call('test_input', value)
        if not _native_click(submitted, identity['pid'], (selected['width'], selected['height']), (selected['x'], selected['y'])):
            raise ValueError('Native Play input refused or unresolved; it is never replayed.')
        proof['play_input_accepted'] = True; write_json(output, proof)
        deadline = monotonic() + seconds
        while monotonic() < deadline:
            bound()
            try:
                snapshot = call('test_snapshot')
            except (OSError, ValueError, RuntimeError) as error:
                snapshot = record('snapshot-unavailable', {'ok': False, 'error': str(error)})
            proof['last_live_readback'] = snapshot; write_json(output, proof)
            selected_sim = snapshot.get('sim') if isinstance(snapshot, dict) else None
            if isinstance(snapshot, dict) and snapshot.get('zone_running') is True and (
                    snapshot.get('household_id') != household_id or snapshot.get('save_guid') != save_guid or
                    isinstance(selected_sim, dict) and selected_sim.get('id') != sim_id):
                raise ValueError('Running zone differs from the original GUID/household/Sim; no pause requested.')
            if (isinstance(snapshot, dict) and snapshot.get('zone_running') is True and
                    isinstance(selected_sim, dict) and selected_sim.get('instanced') is True):
                context(snapshot)
                proof['loaded_before_pause'] = snapshot; write_json(output, proof)
                if snapshot['save_slot'] not in (slot_id, 0xffffffff):
                    raise ValueError('Running native slot differs from the target or observed autosave sentinel; no pause requested.')
                idle(); bound()
                if snapshot['clock_speed'] != 0:
                    paused = call('test_pause')
                    proof['pause_readback'] = paused; write_json(output, proof)
                    context(paused)
                    if paused['clock_speed'] != 0:
                        raise ValueError('Safe household pause did not read back; no input replay.')
                final = call('test_snapshot')
                proof['loaded'] = final; write_json(output, proof)
                context(final); idle()
                if final['clock_speed'] != 0:
                    raise ValueError('Final selected household Live context is not paused.')
                proof.update(household_verified=True, native_live_verified=True)
                proof['native_slot_verified'] = final['save_slot'] == slot_id
                proof['ok'] = proof['native_slot_verified']
                proof['outcome'] = ('exact-selected-household-normal-slot-live-paused' if proof['ok'] else
                                    'selected-household-live-paused-native-slot-unverified')
                if not proof['native_slot_verified']:
                    proof['message'] = 'Original household is safely paused in Live, but its actual native slot differs; autosave metadata cannot certify the normal slot.'
                break
            pause(min(.5, max(0, deadline - monotonic())))
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    proof['after_saves'] = game_lifecycle.all_save_files(profile)
    proof['save_files_unchanged'] = proof['after_saves'] == before
    proof['save_delta'] = save_delta(before, proof['after_saves'])
    if not proof['save_files_unchanged']:
        proof.update(ok=False, outcome='save-files-changed-unexpectedly')
    write_json(output, proof)
    return {'ok': proof['ok'], 'proof': str(output), 'proof_sha256': sha256(output),
        'household_verified': proof['household_verified'], 'native_live_verified': proof['native_live_verified'],
        'native_slot_verified': proof['native_slot_verified'], 'play_input_accepted': proof['play_input_accepted'],
        'save_files_unchanged': proof['save_files_unchanged'], 'outcome': proof['outcome'],
        'message': proof.get('error', proof.get('message'))}
