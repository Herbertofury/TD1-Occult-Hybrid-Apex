"""Focus-free, reversible live-color regression on an explicitly equipped part.

Uses the running game-thread bridge, never input, launching, CAS entry or saves.
An accepted color is verified after native simulation ticks, then Undo/Redo and
final Undo restore the original. Screenshots remain separate visual evidence.
"""
import base64
import json
import math
from pathlib import Path
import sys
import time

from source_manifest import write_json
import reusable_profile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.outfit_snapshot import field, normalize, varint


def chunks(raw):
    offset = 0
    while offset < len(raw):
        start = offset
        number, kind, offset, value = field(raw, offset)
        yield number, kind, value, raw[start:offset]


def color_array(outfit):
    arrays = [value for number, kind, value, _ in chunks(outfit) if number == 12 and kind == 2]
    if len(arrays) != 1:
        raise ValueError('Expected one native OutfitData.part_shifts message.')
    values = []
    for number, kind, value, _ in chunks(arrays[0]):
        if number != 1:
            raise ValueError('Unrecognized native color-array field; do not discard it.')
        if kind == 0:
            values.append(value)
        elif kind == 2:
            offset = 0
            while offset < len(value):
                item, offset = varint(value, offset)
                values.append(item)
        else:
            raise ValueError('Unsupported native color-array encoding.')
    return values


def color_scope(before, after, target, expected_hex):
    """Retain unknown fields too: only one exact outfit color entry may differ."""
    if set(before) != set(after):
        raise ValueError('Native appearance field inventory changed.')
    for name in before:
        if name != '__outfits__' and before[name] != after[name]:
            raise ValueError('Untargeted appearance field changed: ' + name)
    def outfits(fields):
        row = fields['__outfits__']
        if row['kind'] != 'protobuf':
            raise ValueError('Expected native outfit protobuf evidence.')
        return list(chunks(normalize(base64.b64decode(row['value'], validate=True))))
    old, new = outfits(before), outfits(after)
    if len(old) != len(new):
        raise ValueError('Native OutfitList field inventory changed.')
    outfit_index, _body, part_index = map(int, target.split(':'))
    # Studio indexes the native list. Normalization sorts categories, so find
    # that exact original child identity instead of reusing the sorted index.
    native = [value for number, kind, value, _ in chunks(base64.b64decode(before['__outfits__']['value']))
              if number == 1 and kind == 2]
    selected = native[outfit_index]
    matches = 0
    for a, b in zip(old, new):
        if a[:2] != b[:2]:
            raise ValueError('Native outfit protobuf field changed.')
        if a[0] != 1 or a[2] != selected:
            if a[3] != b[3]:
                raise ValueError('Untargeted outfit or unknown list field changed.')
            continue
        matches += 1
        # Every byte outside part_shifts, including unknown fields, stays exact.
        left = b''.join(raw for number, _, _, raw in chunks(a[2]) if number != 12)
        right = b''.join(raw for number, _, _, raw in chunks(b[2]) if number != 12)
        if left != right:
            raise ValueError('Untargeted field inside the selected outfit changed.')
        colors, actual = color_array(a[2]), color_array(b[2])
        colors[part_index] = int(expected_hex, 16)
        if colors != actual:
            raise ValueError('Color changed outside the exact selected part.')
    if matches != 1:
        raise ValueError('The original native outfit identity is ambiguous.')
    return True


def expected_color(editor, edits):
    result = int(editor['color_hex'], 16)
    names = ('brightness', 'saturation', 'hue', 'opacity')
    if not isinstance(edits, dict) or not edits or set(edits) - set(names):
        raise ValueError('Supply explicit numeric color channels.')
    for name, value in edits.items():
        bounds = editor['channels'][name]
        if (type(value) not in (int, float) or not math.isfinite(value) or not bounds['enabled']
                or not bounds['min'] <= value <= bounds['max']):
            raise ValueError('Value exceeds the equipped CASP channel bounds: ' + name)
        scaled = value * 16384
        integer = math.floor(scaled + .5) if scaled >= 0 else math.ceil(scaled - .5)
        shift = names.index(name) * 16
        result = (result & ~(65535 << shift)) | ((integer & 65535) << shift)
    return '{:016X}'.format(result)


def verify_color_owners(before, after, form, target, expected):
    """Native stored wrappers and the current Live Sim are distinct owners.

    An active edit writes Live plus the independent bank; the native stored
    wrapper is synchronized by a later explicit form switch. An inactive edit
    writes that exact stored wrapper without altering the distinct Live Sim.
    Do not infer either owner's contents from the other.
    """
    def owners(snapshot):
        return {str(row['flags']): row['appearance']['typed_payload']
                for row in snapshot['sim']['form_appearances']}
    original, current = owners(before), owners(after)
    active, lane = before['sim']['current_form'], str(form)
    if (set(original) != set(current) or before['sim']['id'] != after['sim']['id']
            or after['sim']['current_form'] != active):
        raise ValueError('Live color edit changed the native form inventory/active Sim or form.')
    for other in current:
        if other != lane and current[other] != original[other]:
            raise ValueError('Untargeted native stored owner changed: ' + other)
    old_live = before['sim']['full_appearance']['typed_payload']
    new_live = after['sim']['full_appearance']['typed_payload']
    if active == form:
        if current[lane] != original[lane]:
            raise ValueError('An active color edit unexpectedly changed the distinct native stored wrapper.')
        color_scope(old_live, new_live, target, expected)
    else:
        color_scope(original[lane], current[lane], target, expected)
        if old_live != new_live:
            raise ValueError('Editing an inactive form changed the distinct Live owner.')
    return True


def run(state, sim_id, form, target, edits, output, request, identity_provider,
        settle_ticks=30, seconds=60, pause=time.sleep, monotonic=time.monotonic):
    _, journal, profile, original = reusable_profile.load(state)
    output = reusable_profile.writable(output)
    if output.exists() or any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('Use a new evidence file outside both game profiles.')
    if not 30 <= settle_ticks <= 1500 or not 1 <= seconds <= 120:
        raise ValueError('Use bounded native-tick and observation limits.')
    identity = identity_provider(state)
    proof = dict(schema=1, ok=False, identity=identity, sim_id=sim_id, form=form,
                 target=target, edits=edits, steps=[], input_submitted=False,
                 focus_attempted=False, save_submitted=False, rendered_result_verified=False)
    write_json(output, proof)

    def call(action, value=None, allow_refusal=False):
        if action.startswith('test_'):
            value = json.dumps({'test_token': journal['token'], 'value': value})
        elif action.startswith('studio_'):
            value = json.dumps({'form': form, 'value': value})
        def submitted(_action, uuid):
            proof['steps'].append(dict(action=action, request_id=uuid, submitted_once=True))
            write_json(output, proof)
        result = request(state, action, sim_id=sim_id, value=value, seconds=seconds,
                         submission_observer=submitted)
        proof['steps'][-1]['result'] = result
        write_json(output, proof)
        if result.get('request_state') not in ('completed', 'failed') or result.get('outcome') == 'unresolved':
            raise ValueError('Unresolved request; retain UUID and do not replay: ' + action)
        if not allow_refusal and result.get('ok') is not True:
            raise ValueError('Runtime step refused: ' + action + ': ' + str(result.get('message', result.get('error', ''))))
        return result

    def owners(snapshot):
        return {str(row['flags']): row['appearance']['typed_payload']
                for row in snapshot['sim']['form_appearances']}

    def settle():
        start = call('test_snapshot', 'forms')
        call('test_play')
        try:
            deadline = monotonic() + seconds
            while monotonic() < deadline:
                pause(.25)
                last = call('test_snapshot')
                ticks = int(last['sim_now_ticks']) - int(start['sim_now_ticks'])
                if ticks >= settle_ticks:
                    break
            else:
                raise ValueError('Native simulation did not advance enough ticks.')
        finally:
            call('test_pause')
        return call('test_snapshot', 'forms'), ticks

    try:
        call('test_pause')
        initial = call('test_snapshot', 'forms')
        original_owners = owners(initial)
        lane = str(form)
        if lane not in original_owners or initial['sim']['id'] != sim_id:
            raise ValueError('Exact requested existing native form is unavailable.')
        active = initial['sim']['current_form']
        status = call('studio_status')
        if status['pending_preview']:
            raise ValueError('Resolve the existing preview before starting this regression.')
        editor = call('studio_color_inspect', target)['color_editor']
        expected = expected_color(editor, edits)
        if expected == editor['color_hex']:
            raise ValueError('Test values must actually change the selected part.')
        payload = {key: editor[key] for key in ('target', 'cas_part_id', 'color_hex', 'appearance_sha256', 'resource_sha256')}
        payload.update(lane=status['history_lane'], edits=edits)
        applied = call('studio_color_live', json.dumps(payload))
        if not applied.get('live_color_applied') or applied['color_editor']['color_hex'] != expected:
            raise ValueError('Atomic live edit did not read back the exact expected Q14.')
        accepted = call('studio_status')
        snapshot, ticks = settle()
        verify_color_owners(initial, snapshot, form, target, expected)
        reread = call('studio_color_inspect', target)
        if reread['color_editor']['color_hex'] != expected:
            raise ValueError('Accepted live color disappeared after unpause.')
        stale = call('studio_color_live', json.dumps(payload), allow_refusal=True)
        if stale.get('ok') is not False:
            raise ValueError('Stale appearance edit was not refused.')
        for action, cursor, expected_hash in (
                ('studio_undo', None, status['appearance_sha256']),
                ('studio_redo', accepted['history_cursor'], accepted['appearance_sha256']),
                ('studio_undo', None, status['appearance_sha256'])):
            preview = call(action, cursor)
            call('studio_apply', preview['preview_id'])
            settled, count = settle()
            observed = call('studio_status')
            if observed['appearance_sha256'] != expected_hash:
                raise ValueError('History restore differs after native ticks: ' + action)
        final = owners(settled)
        # Exact original bytes, including non-outfit native appearance fields.
        if final != original_owners:
            raise ValueError('Final Undo did not restore every native owner exactly.')
        if settled['sim']['full_appearance']['typed_payload'] != initial['sim']['full_appearance']['typed_payload']:
            raise ValueError('Final Undo did not restore the distinct Live owner exactly.')
        if identity_provider(state)['pid'] != identity['pid']:
            raise ValueError('Runtime process changed during regression.')
        proof.update(ok=True, simulation_progress_ticks=ticks, exact_q14_verified=True,
                     all_untargeted_fields_and_unknown_outfit_bytes_verified=True,
                     all_other_native_owners_unchanged=True, active_form_unchanged=True,
                     stale_edit_refused=True, undo_redo_after_ticks_verified=True,
                     final_original_state_restored=True, final_paused=settled['clock_speed'] == 0)
    except Exception as error:
        proof['error'] = str(error)
        # Never replay an unresolved edit or restore blindly after a failure.
        try:
            call('test_pause')
        except Exception as pause_error:
            proof['pause_error'] = str(pause_error)
    finally:
        write_json(output, proof)
    return {key: proof[key] for key in ('ok', 'error', 'exact_q14_verified',
            'all_untargeted_fields_and_unknown_outfit_bytes_verified',
            'undo_redo_after_ticks_verified', 'final_original_state_restored',
            'final_paused', 'rendered_result_verified') if key in proof}
