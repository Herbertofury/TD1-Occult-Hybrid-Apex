"""Explicit current-form outfit/color editor using the canonical game owner.

The native overlay sends commands; every snapshot/preview/apply happens here on
the Sims owner thread. Numeric color edits preserve unedited Q14 lanes and use
the selected effective CASP's actual bounds. No background Sim polling.
"""
import hashlib
import json
import os
from . import cas_catalog, color_shift
from .change_journal import ChangeJournal, fingerprint
from .dresser_parts import DresserParts, read_rows, write_rows

_COLOR_CLIPBOARD = None


def _context(backend, sim_id):
    sim = backend._get_sim_info_by_id(sim_id)
    if sim is None:
        raise ValueError('Select a live Sim first.')
    if not backend._v8_imports_ready():
        raise ValueError('This runtime does not expose the required outfit protobuf API.')
    blob = backend._v8_read_outfit_blob(sim)
    if not blob:
        raise ValueError('The current form has no readable outfit snapshot.')
    # Bind history to the actual save slot as well as Sim/current form. Reusing
    # IDs in another save must never grant access to a different recovery lane.
    persistence = backend.services.get_persistence_service()
    slot = persistence.get_save_slot_proto_buff()
    guid = persistence.get_save_slot_proto_guid()
    if slot is None or guid is None or not int(guid) or not int(slot.slot_id):
        raise ValueError('Save this disposable game first so history has a stable save identity.')
    save_id = int(slot.slot_id)
    lane = '{}:{}:{}:{}'.format(int(guid), save_id, backend._sim_id(sim), backend._get_current_flags(sim))
    filename = hashlib.sha256(lane.encode('ascii')).hexdigest() + '.json'
    journal = ChangeJournal(os.path.join(backend._data_directory(), 'CASHistory', filename), lane)
    return sim, blob, journal, lane


def _target(backend, sim, value):
    text = str(value or '')
    pieces = text.split(':')
    if len(pieces) not in (2, 3) or not pieces[0].isdigit() or (len(pieces) == 3 and not pieces[2].isdigit()):
        raise ValueError('Use outfit:BodyType, or outfit:BodyType:part-index for an explicit layered part.')
    index, body_type = pieces[:2]
    number = int(index)
    body, _, reason = backend._v8_resolve_body_type(body_type)
    if body is None:
        raise ValueError(reason)
    message = backend._v8_parse_outfits(sim)
    if message is None or number >= len(message.outfits):
        raise ValueError('Outfit index does not exist in this form.')
    outfit = message.outfits[number]
    rows = read_rows(outfit)
    matches = [offset for offset, row in enumerate(rows) if row['body_type'] == body]
    if len(pieces) == 3:
        selected = int(pieces[2])
        if selected not in matches:
            raise ValueError('Explicit part index does not match the selected BodyType in this outfit.')
    elif len(matches) != 1:
        raise ValueError('Choose a single existing part; missing/layered slots are not guessed.')
    else:
        selected = matches[0]
    return message, outfit, rows, selected, number, body


def _part_model(row):
    # The authorized helper owns this explicitly targeted row. Other layered
    # slots never become an ambiguous whole-outfit Dresser dictionary.
    return DresserParts([row['body_type']], [row['id']], [row['color_shift']])


def _outfit_inventory(backend, message):
    inventory = []
    for index, outfit in enumerate(message.outfits):
        parts = []
        for offset, row in enumerate(read_rows(outfit)):
            body = row['body_type']
            resolved, meta, reason = backend._v8_resolve_body_type(str(body))
            parts.append({'index': offset, 'body_type': body,
                'label': (meta or {}).get('label') or 'BodyType {}'.format(body),
                'target': '{}:{}:{}'.format(index, body, offset),
                'cas_part_id': str(row['id']), 'cas_part_hex': '{:016X}'.format(row['id']),
                'color_hex': None if row['color_shift'] is None else '{:016X}'.format(row['color_shift']),
                'color_values': None if row['color_shift'] is None else color_shift.decode(row['color_shift']),
                'object_id': None if row['object_id'] is None else str(row['object_id']),
                'layer_id': row['layer_id'], 'target_supported': resolved == body,
                'target_reason': reason})
        inventory.append({'index': index, 'category': int(outfit.category),
                          'outfit_id': str(outfit.outfit_id), 'parts': parts})
    return inventory


def _response(journal, message, **extras):
    timeline = journal.timeline()
    lines = ['{}{} | {} | {}'.format('* ' if node['id'] == journal.data['cursor'] else '  ',
        node['id'], node['label'], node['sha256'][:12]) for node in timeline]
    return dict({'ok': True, 'message': message, 'history_text': '\n'.join(lines),
                 'history_nodes': timeline, 'history_cursor': journal.data['cursor'],
                 'history_lane': journal.lane,
                 'pending_preview': (journal.data['pending'] or {}).get('id'),
                 'save_reload_verified': False}, **extras)


def dispatch(backend, action, sim_id, value):
    global _COLOR_CLIPBOARD
    sim, before, journal, lane = _context(backend, sim_id)
    read = lambda: backend._v8_read_outfit_blob(sim)
    def write(raw):
        if not backend._v8_write_outfit_blob(sim, raw):
            raise ValueError('The runtime rejected the outfit write.')
        backend._resend_all_visuals(sim)
    if action in ('studio_status', 'studio_history'):
        message = backend._v8_parse_outfits(sim)
        if message is None:
            raise ValueError('Cannot parse outfit data.')
        lines = []
        for index, outfit in enumerate(message.outfits):
            rows = read_rows(outfit)
            lines.append('Outfit {} | category {} | ID {} | {} parts'.format(index, outfit.category, outfit.outfit_id, len(rows)))
        return _response(journal, 'Current-form outfit/history data read.', outfit_text='\n'.join(lines),
            lane=lane, outfit_inventory=_outfit_inventory(backend, message),
            appearance_sha256=fingerprint(before), color_clipboard_ready=_COLOR_CLIPBOARD is not None)
    if action == 'studio_checkpoint':
        journal.observe(before, value or 'Named checkpoint', force=True)
        return _response(journal, 'Checkpoint captured without changing the Sim.')
    if action == 'studio_recover':
        return _response(journal, journal.recover(before))
    if action == 'studio_color_inspect':
        _, _, rows, index, _, body = _target(backend, sim, value)
        row = rows[index]
        if row['color_shift'] is None:
            raise ValueError('This part has no explicit color state; no conversion is guessed.')
        metadata = cas_catalog.effective_metadata(backend, row['id'])
        if metadata['body_type'] != body:
            raise ValueError('The effective CASP body type differs from this outfit row.')
        values = color_shift.decode(row['color_shift'])
        channels = {name: dict(bounds, value=values[name]) for name, bounds in metadata['ranges'].items()}
        editor = {'target': value, 'cas_part_id': str(row['id']), 'color_hex': '{:016X}'.format(row['color_shift']),
            'appearance_sha256': fingerprint(before), 'resource_sha256': metadata['resource_sha256'],
            'casp_version': metadata['version'], 'part_name': metadata['part_name'], 'channels': channels}
        return _response(journal, 'Read effective CASP slider bounds and exact Q14 values.', color_editor=editor)
    if action == 'studio_color_edit':
        if not isinstance(value, str) or len(value) > 2048:
            raise ValueError('Numeric color request exceeds its bound.')
        request = json.loads(value)
        expected = {'target', 'lane', 'cas_part_id', 'color_hex', 'appearance_sha256', 'resource_sha256', 'edits'}
        if not isinstance(request, dict) or set(request) != expected:
            raise ValueError('Numeric color request does not match the editor protocol.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Sim/form/save or appearance changed; inspect this part again before editing.')
        message, outfit, rows, index, _, body = _target(backend, sim, request['target'])
        row = rows[index]
        if row['color_shift'] is None or request['cas_part_id'] != str(row['id']) or request['color_hex'] != '{:016X}'.format(row['color_shift']):
            raise ValueError('The selected CAS part/color changed; inspect again.')
        metadata = cas_catalog.effective_metadata(backend, row['id'])
        if metadata['body_type'] != body or metadata['resource_sha256'] != request['resource_sha256']:
            raise ValueError('The effective CASP resource changed; inspect again.')
        old = row['color_shift']
        row['color_shift'] = color_shift.replace(old, request['edits'], metadata['ranges'])
        write_rows(outfit, rows)
        after = message.SerializeToString()
        if row['color_shift'] == old:
            return _response(journal, 'The requested values already match this exact Q14 color.')
        token = journal.prepare('Edit part color: ' + ', '.join(sorted(request['edits'])), before, after)
        return _response(journal, 'Numeric color preview prepared. Apply explicitly to change this form.',
            preview_id=token, preview_diff='{}: {:016X} -> {:016X}; quantized values {}'.format(
                metadata['part_name'], old, row['color_shift'], color_shift.decode(row['color_shift'])))
    if action == 'studio_color_copy':
        _, _, rows, index, outfit_index, body = _target(backend, sim, value)
        row = rows[index]
        if row['color_shift'] is None:
            raise ValueError('This part has no explicit slider state; absence is preserved rather than guessed.')
        model = _part_model(row)
        _COLOR_CLIPBOARD = {'id': model.get_part_id(body), 'body_type': body,
            'color_shift': model.get_color_shift(body), 'source_lane': lane, 'outfit_index': outfit_index}
        return _response(journal, 'Exact part color copied.', raw_color_hex='{:016X}'.format(_COLOR_CLIPBOARD['color_shift']),
            color_part_id=str(_COLOR_CLIPBOARD['id']))
    if action == 'studio_color_preview':
        if _COLOR_CLIPBOARD is None:
            raise ValueError('Copy an exact part color first.')
        message, outfit, rows, index, _, body = _target(backend, sim, value)
        row = rows[index]
        if row['id'] != _COLOR_CLIPBOARD['id'] or body != _COLOR_CLIPBOARD['body_type']:
            raise ValueError('Color-only copy requires the identical CAS part and body type; no incompatible substitution.')
        if row['color_shift'] is None:
            raise ValueError('Destination slider state is absent; conversion compatibility must be resolved first.')
        model = _part_model(row)
        model.add_part_shift(body, row['id'], _COLOR_CLIPBOARD['color_shift'])
        old_shift = row['color_shift']
        rows[index]['color_shift'] = model.get_color_shift(body)
        write_rows(outfit, rows)
        after = message.SerializeToString()
        if fingerprint(before) == fingerprint(after):
            return _response(journal, 'Destination already has the exact copied color; nothing changed.')
        token = journal.prepare('Paste exact part color', before, after)
        return _response(journal, 'Preview prepared. Apply explicitly to change this form.', preview_id=token,
            preview_diff='BodyType {}: {:016X} -> {:016X}; identical CAS part {}'.format(body, old_shift, rows[index]['color_shift'], row['id']))
    if action == 'studio_cancel':
        journal.cancel(value)
        return _response(journal, 'Preview cancelled; Sim appearance was unchanged.')
    if action in ('studio_undo', 'studio_redo', 'studio_jump'):
        kind = {'studio_undo': 'Undo', 'studio_redo': 'Redo', 'studio_jump': 'Jump'}[action]
        token = journal.restore(kind, before, value or None)
        return _response(journal, '{} preview prepared. Apply explicitly.'.format(kind), preview_id=token)
    if action == 'studio_apply':
        journal.apply(value, read, write)
        return _response(journal, 'Appearance write matches the accepted preview. Save/reload testing remains pending.')
    raise ValueError('Unknown Studio action.')
