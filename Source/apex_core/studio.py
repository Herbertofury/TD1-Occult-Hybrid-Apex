"""Explicit current-form outfit/color editor using the canonical game owner.

The native overlay sends commands; every snapshot/preview/apply happens here on
the Sims owner thread. Numeric color edits preserve unedited Q14 lanes and use
the selected effective CASP's actual bounds. No background Sim polling.
"""
import hashlib
import json
import os
import copy
import re
from . import cas_catalog, color_shift, outfit_snapshot, form_appearance as appearance, form_bank, sim_record, outfit_hair, morph_controls, human_werewolf
from .change_journal import ChangeJournal, fingerprint, decoded
from .dresser_parts import DresserParts, NEUTRAL_SHIFT, read_rows, write_rows, uint

_COLOR_CLIPBOARD = None
_ITEM_SHA = re.compile(r'[0-9a-f]{64}\Z')
_ITEM_TGI = re.compile(r'034AEECB:[0-9A-F]{8}:([0-9A-F]{16})\Z')


def _capture_native_record(backend, primary):
    # Native serialization can rebuild hidden wardrobes. History observers
    # must not call it while a raw CAS return awaits explicit decisions.
    form_bank.assert_idle(backend, primary)
    return sim_record.capture(backend, primary)


def _normalize(backend, raw):
    return getattr(backend, '_studio_normalize_snapshot', outfit_snapshot.normalize)(raw)


def _read_outfits(backend, sim):
    return appearance.decode(sim._studio_fields['__outfits__'])[1] if hasattr(sim, '_studio_fields') else backend._v8_read_outfit_blob(sim)


def _packed(backend, sim):
    return copy.deepcopy(sim._studio_fields) if hasattr(sim, '_studio_fields') else appearance.packed(backend, sim)


def _message(backend, sim):
    raw = _normalize(backend, _read_outfits(backend, sim))
    provider = getattr(backend, '_studio_parse_snapshot', None)
    if provider is not None:
        return provider(raw)
    message = backend._V8_Outfits_pb2.OutfitList()
    message.ParseFromString(raw)
    return message


def _state(backend, sim, outfits=None):
    fields = _packed(backend, sim)
    raw = _normalize(backend, _read_outfits(backend, sim) if outfits is None else outfits)
    fields['__outfits__'] = appearance.encode(('protobuf', raw))
    return json.dumps(fields, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('utf-8')


def _state_from_fields(backend, fields):
    result = dict(fields)
    result['__outfits__'] = appearance.encode(('protobuf', _normalize(backend, appearance.decode(result['__outfits__'])[1])))
    return json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('utf-8')


def _fields(raw):
    fields = json.loads(raw.decode('utf-8'))
    appearance.payload(fields)
    if '__outfits__' not in fields:
        raise ValueError('Complete appearance history requires outfits.')
    return fields


def _delta(before, after):
    left, right = _fields(before), _fields(after)
    changed = [name for name in sorted(set(left) | set(right)) if left.get(name) != right.get(name)]
    return {'changed_fields': changed, 'summary': ' + '.join('outfits' if name == '__outfits__' else name.replace('_', ' ') for name in changed) or 'No appearance differences'}


def _part_delta(backend, before, after):
    def wardrobe(raw):
        outfits = appearance.decode(_fields(raw)['__outfits__'])[1]
        provider = getattr(backend, '_studio_parse_snapshot', None)
        if provider is not None: message = provider(outfits)
        else:
            message = backend._V8_Outfits_pb2.OutfitList(); message.ParseFromString(outfits)
        result, ordinals = {}, {}
        for outfit in message.outfits:
            category = int(outfit.category); ordinal = ordinals.get(category, 0)
            ordinals[category] = ordinal + 1
            for index, row in enumerate(read_rows(outfit)):
                result[(category, ordinal, index)] = row
        return result
    a, b = wardrobe(before), wardrobe(after)
    changes = []
    for key in sorted(set(a) | set(b)):
        if a.get(key) == b.get(key): continue
        row = b.get(key, a.get(key)); body = row['body_type']
        _, meta, _ = backend._v8_resolve_body_type(str(body))
        changes.append({'category': key[0], 'outfit_ordinal': key[1], 'row': key[2],
                        'body_type': body, 'label': (meta or {}).get('label') or 'BodyType {}'.format(body),
                        'before': a.get(key), 'after': b.get(key)})
    return {'part_changes': changes[:256], 'part_change_count': len(changes), 'part_changes_truncated': len(changes) > 256}


def _context(backend, sim_id, form=None, history=True):
    sim = backend._get_sim_info_by_id(sim_id)
    if sim is None:
        raise ValueError('Select a live Sim first.')
    if not backend._v8_imports_ready():
        raise ValueError('This runtime does not expose the required outfit protobuf API.')
    persistence = backend.services.get_persistence_service()
    slot = persistence.get_save_slot_proto_buff()
    guid = persistence.get_save_slot_proto_guid()
    if slot is None or guid is None or not 0 < int(guid) < 1 << 64 or not 0 <= int(slot.slot_id) <= 0xffffffff:
        raise ValueError('Save this disposable game first so history has a stable save identity.')
    stable_slot = 0 < int(slot.slot_id) < 0xffffffff
    primary = sim
    flags = backend._get_current_flags(primary) if form is None else int(form)
    inactive = flags != backend._get_current_flags(primary)
    native_target = None
    source = 'Current live form'
    if inactive:
        path, key = form_bank.context(backend, primary)
        record = form_bank.load(path)['records'].get(key, {})
        stored = (record.get('bank', {}).get(str(flags))
                  if form_bank.current_runtime_authorized(backend, primary, record) else None)
        native_target = backend._form_map(primary.occult_tracker).get(backend._coerce_flags(flags))
        source = 'Accepted independent appearance bank' if stored is not None else 'Native stored form'
        if stored is None and native_target is not None: stored = appearance.packed(backend, native_target)
        if stored is None: raise ValueError('No existing appearance owner for this form; no new form generated.')
        class StoredOwner: pass
        sim = StoredOwner(); sim._studio_fields = copy.deepcopy(stored)
    base_lane = '{}:{}:{}:{}'.format(int(guid), int(slot.slot_id), backend._sim_id(primary), flags)
    if not stable_slot:
        # CAS and native Resume temporarily report slot zero/the autosave
        # sentinel. Keep their exact native GUID, Sim and form, with an
        # explicit runtime lane. Never guess a disk slot or replay this lane
        # after restart; the normal saved-slot history remains untouched.
        base_lane += ':runtime-{}'.format(os.getpid())
    # Prior outfit-only history remains intact. It cannot truthfully restore
    # face/skin/genetics it never captured, so full appearance gets its own lane.
    lane = base_lane + ':full-appearance-v1'
    filename = hashlib.sha256(lane.encode('ascii')).hexdigest() + '.json'
    if history:
        journal = ChangeJournal(os.path.join(backend._data_directory(), 'CASHistory', filename), lane,
                                capture_record=lambda: _capture_native_record(backend, primary))
        legacy = os.path.join(backend._data_directory(), 'CASHistory', hashlib.sha256(base_lane.encode('ascii')).hexdigest() + '.json')
        journal.legacy_available = os.path.isfile(legacy)
    else:
        # Metadata pages need the exact native owner, not a potentially large
        # persistent undo graph or full gameplay serialization on every chunk.
        class ReadContext: pass
        journal = ReadContext()
    journal.backend = backend
    journal.primary_sim, journal.form_flags, journal.inactive, journal.native_target = primary, flags, inactive, native_target
    journal.appearance_source = source
    journal.stable_save_slot_verified = stable_slot
    journal.history_runtime_only = not stable_slot
    return sim, _state(backend, sim), journal, lane


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
    message = _message(backend, sim)
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
    inventory, ordinals = [], {}
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
        try:
            from sims.outfits.outfit_enums import OutfitCategory
            category_name = OutfitCategory(int(outfit.category)).name.replace('_', ' ').title()
        except (ImportError, AttributeError, ValueError):
            category_name = 'Category {}'.format(int(outfit.category))
        category = int(outfit.category); ordinal = ordinals.get(category, 0); ordinals[category] = ordinal + 1
        inventory.append({'index': index, 'category': category, 'ordinal': ordinal, 'number': ordinal + 1, 'category_name': category_name,
                          'outfit_id': str(outfit.outfit_id), 'parts': parts})
    return inventory


def _category_catalog(backend):
    rows = {}
    for item in getattr(backend, '_V8_CAS_BODYTYPE_DEFS', ()):
        body, meta, reason = backend._v8_resolve_body_type(item['key'])
        number = body if body is not None else int(item['value'])
        rows[number] = dict(item, body_type=number, supported=body is not None, reason=reason)
    enum = getattr(backend, '_V8_EA_BODYTYPE', None)
    if enum is not None:
        for value in enum:
            number = int(value)
            if number not in rows:
                rows[number] = {'body_type': number, 'key': value.name, 'label': value.name.replace('_', ' ').title(),
                                'group': 'Runtime discovered', 'supported': True, 'reason': 'runtime enum'}
    return [rows[key] for key in sorted(rows)]


def _form_inventory(backend, sim):
    current = backend._get_current_flags(sim)
    fields = {}
    for kind, form in backend._form_map(sim.occult_tracker).items():
        fields[int(kind)] = (appearance.packed(backend, form), 'Native stored form')
    path, key = form_bank.context(backend, sim)
    record = form_bank.load(path)['records'].get(key, {})
    if form_bank.current_runtime_authorized(backend, sim, record):
        for kind, stored in record.get('bank', {}).items():
            fields[int(kind)] = (stored, 'Accepted independent appearance bank')
    fields[current] = (appearance.packed(backend, sim), 'Current live form')
    names = {1:'Human', 2:'Alien / disguise', 4:'Vampire', 8:'Mermaid', 16:'Spellcaster', 32:'Werewolf', 64:'Fairy'}
    result = []
    for kind in sorted(fields):
        stored, source = fields[kind]
        raw = _normalize(backend, appearance.decode(stored['__outfits__'])[1])
        parser = getattr(backend, '_studio_parse_snapshot', None)
        if parser is not None: message = parser(raw)
        else:
            message = backend._V8_Outfits_pb2.OutfitList(); message.ParseFromString(raw)
        result.append({'flags': kind, 'name': names.get(kind, 'Form {}'.format(kind)), 'current': kind == current,
                       'source': source, 'outfit_inventory': _outfit_inventory(backend, message),
                       'appearance_fields': [dict(name=name, kind=value['kind'], value=value['value']) for name,value in sorted(stored.items())]})
    return result


def _response(journal, message, **extras):
    timeline = journal.timeline()
    for node in timeline:
        current = journal._node(node['id'])
        node['delta'] = (_delta(decoded(journal._node(node['parent'])['state']), decoded(current['state']))
                         if node['parent'] else {'changed_fields': [], 'summary': 'Full appearance baseline'})
        if node['parent'] and '__outfits__' in node['delta']['changed_fields']:
            node['delta'].update(_part_delta(journal.backend, decoded(journal._node(node['parent'])['state']), decoded(current['state'])))
        node['complete_native_record_retained'] = 'sim_record' in current
        if node['parent'] and 'sim_record' in current and 'sim_record' in journal._node(node['parent']):
            node['native_delta'] = sim_record.delta(journal._node(node['parent'])['sim_record'], current['sim_record'])
        node['is_current'] = node['id'] == journal.data['cursor']
        node['child_count'] = sum(item['parent'] == node['id'] for item in timeline)
    pending = journal.data['pending']
    observations = [item for item in journal.data['operations'] if item['kind'] == 'observed-native-record']
    result = {'ok': True, 'native_observation_count': len(observations), 'message': message, 'history_nodes': timeline,
              'history_cursor': journal.data['cursor'], 'history_lane': journal.lane,
              'runtime_pid': os.getpid(), 'inspected_form_flags': journal.form_flags,
              'stable_save_slot_verified': journal.stable_save_slot_verified,
              'history_runtime_only': journal.history_runtime_only,
              'appearance_sha256': fingerprint(journal.appearance_reader()),
              'history_scope': 'Complete native Sim records tracked, including runtime-discovered schemas and unknown wire fields. Undo restores readable appearance fields/outfits; gameplay records are retained as evidence.',
              'legacy_outfit_history_retained': getattr(journal, 'legacy_available', False),
              'pending_preview': (pending or {}).get('id'), 'preview_outfit_inventory': None, 'save_reload_verified': False}
    if observations:
        result['latest_native_observation'] = {'sha256': observations[-1]['sim_record']['sha256'], 'time': observations[-1]['time']}
        previous = observations[-2]['sim_record'] if len(observations) > 1 else journal.data['nodes'][0].get('sim_record')
        if previous: result['latest_native_observation']['delta'] = sim_record.delta(previous, observations[-1]['sim_record'])
    if pending:
        # A whole-appearance try-on may contain new native outfit IDs. Expose
        # its detached wardrobe explicitly; accepted/equipped data stays real.
        class PreviewOwner: pass
        owner = PreviewOwner(); owner._studio_fields = _fields(decoded(pending['after']))
        result['preview_outfit_inventory'] = _outfit_inventory(journal.backend, _message(journal.backend, owner))
        result['preview_delta'] = _delta(decoded(pending['before']), decoded(pending['after']))
        if '__outfits__' in result['preview_delta']['changed_fields']:
            result['preview_delta'].update(_part_delta(journal.backend, decoded(pending['before']), decoded(pending['after'])))
        result['preview_diff'] = result['preview_delta']['summary']
    result.update(extras)
    return result


def _current_outfit(sim, inventory):
    try:
        category, ordinal = sim.get_current_outfit()
        matches = [row for row in inventory if row['category'] == int(category)]
        return matches[int(ordinal)]['index']
    except (AttributeError, IndexError, TypeError, ValueError):
        return None  # No fabricated current-outfit selection.


def _items_response(backend, sim, before, journal, lane, value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Use a bounded explicit equipped-item page request.')
    request = json.loads(value)
    fields = {'lane', 'appearance_sha256', 'runtime_pid', 'cursor', 'limit', 'outfit_index'}
    if not isinstance(request, dict) or set(request) != fields:
        raise ValueError('Equipped-item page protocol differs.')
    appearance_hash = fingerprint(before)
    if (request['lane'] != lane or request['appearance_sha256'] != appearance_hash or
            type(request['runtime_pid']) is not int or request['runtime_pid'] != os.getpid()):
        raise ValueError('Sim/form/save, process or appearance changed; inspect again.')
    cursor, limit, selected = request['cursor'], request['limit'], request['outfit_index']
    if (type(cursor) is not int or not 0 <= cursor <= 16384 or type(limit) is not int or not 1 <= limit <= 8 or
            selected is not None and (type(selected) is not int or not 0 <= selected < 128)):
        raise ValueError('Use an exact nonnegative page cursor, limit one through eight and existing outfit index.')
    # Parse the already captured, normalized state. Never call get_outfit(),
    # which generates absent outfits in the current game Python contract.
    raw = appearance.decode(_fields(before)['__outfits__'])[1]
    parser = getattr(backend, '_studio_parse_snapshot', None)
    if parser is not None: message = parser(raw)
    else:
        message = backend._V8_Outfits_pb2.OutfitList(); message.ParseFromString(raw)
    if len(message.outfits) > 128 or selected is not None and selected >= len(message.outfits):
        raise ValueError('Outfit inventory exceeds the bound or the requested owner is absent.')
    page, total, ordinals = [], 0, {}
    for outfit_index, outfit in enumerate(message.outfits):
        category = int(outfit.category); ordinal = ordinals.get(category, 0)
        ordinals[category] = ordinal + 1
        if selected is not None and selected != outfit_index: continue
        rows = read_rows(outfit)
        for index, row in enumerate(rows):
            if cursor <= total < cursor + limit:
                page.append(dict(row, index=index, outfit_index=outfit_index, category=category,
                    ordinal=ordinal, outfit_id=str(outfit.outfit_id),
                    target='{}:{}:{}'.format(outfit_index, row['body_type'], index)))
            total += 1
            if total > 16384:
                raise ValueError('Equipped-item inventory exceeds the bounded traversal; no rows were omitted.')
    if cursor > total:
        raise ValueError('Equipped-item page cursor exceeds the exact current inventory.')
    parts = lane.split(':')
    owner = {'runtime_pid': os.getpid(), 'sim_id': str(backend._sim_id(journal.primary_sim)),
             'save_guid': parts[0], 'slot_id': int(parts[1]), 'form_flags': journal.form_flags}
    items, resources = [], {}
    inspections = 0
    for row in page:
        part_id = row.pop('id')
        item = dict(row, cas_part_id=str(part_id), cas_part_hex='{:016X}'.format(part_id),
            status='unresolved', reason=None, display_name=None, name_status='unresolved',
            name_reason='Genuine CASP internal name is unavailable.', part_editor=None)
        if part_id not in resources:
            inspections += 1
            try:
                resources[part_id] = (cas_catalog.effective_metadata(backend, part_id), None)
            except Exception as error:
                resources[part_id] = (None, '{}: {}'.format(type(error).__name__, error)[:2048])
        metadata, error = resources[part_id]
        try:
            if error: raise ValueError(error)
            if type(metadata.get('body_type')) is not int or metadata['body_type'] != row['body_type']:
                raise ValueError('Effective CASP body type differs from this exact equipped row.')
            if not isinstance(metadata.get('resource_sha256'), str) or not _ITEM_SHA.fullmatch(metadata['resource_sha256']):
                raise ValueError('Effective CASP bytes have no exact resource hash.')
            name = metadata.get('part_name')
            if isinstance(name, str) and name and len(name) <= 4096:
                item.update(display_name=name, name_status='casp-internal-name', name_reason=None)
            editor = dict(metadata, target=row['target'], cas_part_id=str(part_id), appearance_sha256=appearance_hash)
            # Only primitive metadata crosses the transport/cache boundary.
            item['part_editor'] = json.loads(json.dumps(editor, ensure_ascii=True, allow_nan=False))
            tgi = metadata.get('resource_tgi')
            match = _ITEM_TGI.fullmatch(tgi) if isinstance(tgi, str) else None
            if metadata.get('resource_key_query') != 'native-key' or match is None or int(match.group(1), 16) != part_id:
                raise ValueError('Native effective CASP type/group/instance is unavailable or differs.')
            item['status'] = 'resolved'
        except Exception as error:
            item['reason'] = '{}: {}'.format(type(error).__name__, error)[:2048]
        editor = item['part_editor'] or {}
        binding = dict(owner, appearance_sha256=appearance_hash, outfit_index=row['outfit_index'],
            outfit_id=row['outfit_id'], target=row['target'], body_type=row['body_type'], cas_part_id=str(part_id),
            resource_tgi=editor.get('resource_tgi'), resource_sha256=editor.get('resource_sha256'))
        item['cache_key'] = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=True,
            allow_nan=False, separators=(',', ':')).encode('ascii')).hexdigest()
        items.append(item)
    next_cursor = cursor + len(items) if cursor + len(items) < total else None
    result = {'ok': True, 'message': 'Exact equipped-item metadata page read.', 'owner': owner,
        'runtime_pid': owner['runtime_pid'], 'history_lane': lane, 'appearance_sha256': appearance_hash,
        'stable_save_slot_verified': journal.stable_save_slot_verified,
        'history_runtime_only': journal.history_runtime_only,
        'inspected_form_flags': journal.form_flags, 'current_form_flags': backend._get_current_flags(journal.primary_sim),
        'appearance_source': journal.appearance_source, 'outfit_index': selected, 'cursor': cursor, 'limit': limit,
        'total': total, 'next_cursor': next_cursor, 'complete': next_cursor is None,
        'resource_inspection_count': inspections, 'items': items}
    if len(json.dumps(result, ensure_ascii=True, allow_nan=False).encode('ascii')) > 500 * 1024:
        raise ValueError('Equipped-item page exceeds the bounded transport response; no partial page returned.')
    return result


def dispatch(backend, action, sim_id, value):
    global _COLOR_CLIPBOARD
    form = None
    if isinstance(value, str) and value.startswith('{'):
        envelope = json.loads(value)
        if isinstance(envelope, dict) and set(envelope) == {'form', 'value'}:
            if type(envelope['form']) is not int or not 0 < envelope['form'] < 1 << 32:
                raise ValueError('Invalid explicit form owner.')
            form, value = envelope['form'], envelope['value']
    sim, before, journal, lane = _context(backend, sim_id, form,
        # Begin/chunks are transport-only. Finish returns a Studio document,
        # including the real destination history; it needs the full context.
        history=action not in ('studio_items', 'studio_preview_snapshot') and
            (not action.startswith('studio_clipboard_') or action == 'studio_clipboard_finish'))
    primary, flags = journal.primary_sim, journal.form_flags
    journal.appearance_reader = lambda: _state(backend, sim)
    if action == 'studio_items':
        return _items_response(backend, sim, before, journal, lane, value)
    if action == 'studio_copy_appearance':
        from . import appearance_transfer
        clip = appearance_transfer.capture(_fields(before), dict(kind='sim', sim_id=str(backend._sim_id(primary)), form=flags,
            label='Sim {} / form {}'.format(backend._sim_id(primary), flags)))
        return _response(journal, 'Appearance copied without changing any Sim or form.',
            appearance_clipboard={name: clip[name] for name in ('id', 'sha256', 'source')},
            clipboard_fields=sorted(clip['fields']), clipboard_outfits=_outfit_inventory(backend, _message(backend, sim)))
    if action.startswith('studio_clipboard_'):
        from . import appearance_transfer
        if not isinstance(value, str) or len(value) > 8192: raise ValueError('Bounded clipboard operation required.')
        request = json.loads(value)
        if action == 'studio_clipboard_export':
            if not isinstance(request, dict) or set(request) != {'id', 'sha256'}: raise ValueError('Exact clipboard identity required.')
            return dict(appearance_transfer.get(request['id'], request['sha256']), ok=True)
        operation = action[len('studio_clipboard_'):]
        result = appearance_transfer.upload(operation, request)
        if operation == 'finish':
            return _response(journal, 'Imported appearance retained in the clipboard; no Sim changed.',
                appearance_clipboard={name: result[name] for name in ('id', 'sha256', 'source')}, clipboard_fields=sorted(result['fields']),
                clipboard_outfits=_outfit_inventory(backend, appearance_transfer._parse(backend, result['fields'])))
        return dict(result, ok=True, sim_appearance_written=False)
    if action == 'studio_preview_snapshot':
        if not isinstance(value, str) or len(value) > 2048:
            raise ValueError('A bounded exact preview owner is required.')
        request = json.loads(value)
        expected = {'lane', 'appearance_sha256', 'outfit_index', 'outfit_id'}
        if not isinstance(request, dict) or set(request) not in (expected, expected | {'preview_id'}):
            raise ValueError('Preview snapshot fields differ.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Preview appearance owner changed; inspect again.')
        render_state, preview_id = before, request.get('preview_id')
        if preview_id is not None:
            if not isinstance(preview_id, str) or not re.fullmatch(r'[0-9a-f]{32}', preview_id):
                raise ValueError('An exact prepared preview identity is required.')
            filename = hashlib.sha256(lane.encode('ascii')).hexdigest() + '.json'
            retained = ChangeJournal(os.path.join(backend._data_directory(), 'CASHistory', filename), lane)
            pending = retained.data['pending']
            if (not pending or pending['id'] != preview_id or pending['stage'] != 'prepared' or
                    pending['before_sha256'] != fingerprint(before)):
                raise ValueError('Prepared preview changed; no appearance was applied.')
            render_state = decoded(pending['after'])
        render_fields = _fields(render_state)
        class PreviewOwner: pass
        preview_owner = PreviewOwner(); preview_owner._studio_fields = render_fields
        message = _message(backend, preview_owner)
        index = request['outfit_index']
        if type(index) is not int or not 0 <= index < len(message.outfits) or str(message.outfits[index].outfit_id) != request['outfit_id']:
            raise ValueError('Preview outfit identity changed; inspect again.')
        form_bank.assert_idle(backend, primary)
        owners = list(backend._form_map(primary.occult_tracker).values()) + [primary]
        originals = [(owner, _state(backend, owner)) for owner in owners]
        record = sim_record.restore(_capture_native_record(backend, primary))
        if any(_state(backend, owner) != raw for owner, raw in originals) or _state(backend, sim) != before:
            raise ValueError('Native metadata serialization changed an appearance; preview refused.')
        from .human_werewolf import preview_form
        return dict(request, ok=True, sim_id=str(backend._sim_id(primary)), form=flags,
                    visual_form=preview_form(backend, primary, flags),
                    preview_id=preview_id, render_sha256=fingerprint(render_state), fields=render_fields,
                    native_sim=record['native_base64'], native_sha256=record['native_sha256'],
                    appearance_source=journal.appearance_source, save_guid=str(backend.services.get_persistence_service().get_save_slot_proto_guid()),
                    runtime_pid=os.getpid(), save_file_written=False, history_written=False)
    read = lambda: _state(backend, sim)
    journal.appearance_reader = read
    def write(raw):
        form_bank.assert_idle(backend, primary)
        prior = _packed(backend, sim)
        desired = _fields(raw)
        # Keep unrequested field additions/removals from a different runtime
        # out of a restore. Every captured field must have a matching owner.
        if set(desired) != set(prior):
            raise ValueError('Native appearance field set changed; capture a new checkpoint.')
        restore_raw = getattr(backend, '_studio_restore_appearance', backend._restore_siminfo_payload)
        def restore(owner,values):
            # The primary's Live mask may exclude this stored Mermaid/Alien
            # kind. Use the existing, verified per-owner native context while
            # setters filter outfits; restore the exact mask before readback.
            from .native_occult_context import appearance_write
            return appearance_write(backend,primary,owner,lambda:restore_raw(owner,values))
        native = journal.native_target if journal.inactive else sim
        native_prior = appearance.packed(backend, native) if native is not None else None
        # A Live Sim and its stored current-form wrapper are distinct owners.
        # Keep this edit/Undo's requested fields on both; otherwise a later
        # switch can resurrect the stored pre-Undo shape or CAS part. Preserve
        # every unrelated field on the wrapper, including existing differences.
        companion = None if journal.inactive else backend._form_map(primary.occult_tracker).get(backend._coerce_flags(flags))
        if companion is native: companion = None
        companion_prior = appearance.packed(backend, companion) if companion is not None else None
        prior_hashes=appearance.fingerprint(prior)['field_sha256']
        desired_hashes=appearance.fingerprint(desired)['field_sha256']
        edited = {name: row for name, row in desired.items() if prior_hashes.get(name)!=desired_hashes[name]}
        companion_desired = dict(companion_prior, **edited) if companion_prior is not None else None
        def restore_edit(owner,expected,changes):
            if not changes:return
            restore(owner,appearance.payload(changes))
            # Native morph/outfit setters may reset an unrelated skin/coat or
            # genetics field. Restore only those unrequested side effects;
            # never replay a rejected requested edit or accept omitted data.
            observed=appearance.packed(backend,owner)
            observed_hashes=appearance.fingerprint(observed)['field_sha256']
            expected_hashes=appearance.fingerprint(expected)['field_sha256']
            side_effects={name:row for name,row in expected.items()
                          if name not in changes and observed_hashes.get(name)!=expected_hashes[name]}
            if side_effects:restore(owner,appearance.payload(side_effects))
        def check_companion(expected):
            if companion is None: return
            if backend._form_map(primary.occult_tracker).get(backend._coerce_flags(flags)) is not companion:
                raise ValueError('Stored current-form owner changed during appearance Apply; retain recovery.')
            if fingerprint(_state_from_fields(backend, appearance.packed(backend, companion))) != fingerprint(_state_from_fields(backend, expected)):
                raise ValueError('Stored current-form appearance rejected the accepted edit.')
        try:
            if native is not None:
                # Rebuilding identical outfits can rewrite unrelated genetics.
                # Apply only the requested differences, then verify ALL fields.
                native_hashes=appearance.fingerprint(native_prior)['field_sha256']
                changed = {name: row for name, row in desired.items() if native_hashes.get(name)!=desired_hashes[name]}
                restore_edit(native,desired,changed)
                observed = _state_from_fields(backend, appearance.packed(backend, native))
                if fingerprint(observed) != fingerprint(raw):
                    # Retain the rejected native bytes before rollback erases
                    # them. Exact row/unknown-field differences can then be
                    # diagnosed without replaying the destructive attempt.
                    from pathlib import Path
                    from .occult_add_guard import publish
                    from .overlay_loader import _unlinked
                    diagnostic = _unlinked(Path(backend._data_directory()) / 'CASHistory' /
                        ('rejected-' + hashlib.sha256(lane.encode('ascii')).hexdigest() + '.json'))
                    publish(diagnostic, dict(schema=1, lane=lane, sim_id=str(backend._sim_id(primary)), form=flags,
                        stage='rejected-before-rollback', original=native_prior, expected=desired,
                        observed=appearance.packed(backend, native), changed_fields=_delta(raw, observed)['changed_fields'],
                        assignment_diagnostics=getattr(backend,'_APEX_APPEARANCE_RESTORE_DIAGNOSTICS',{}).get(str(getattr(native,'id','unknown')))))
                    raise ValueError('Appearance owner rejected the accepted state. Changed fields: ' +
                                     ', '.join(_delta(raw, observed)['changed_fields']))
            if companion is not None:
                companion_before=appearance.fingerprint(companion_prior)['field_sha256']
                companion_after=appearance.fingerprint(companion_desired)['field_sha256']
                changed = {name: row for name, row in companion_desired.items() if companion_before.get(name)!=companion_after[name]}
                restore_edit(companion,companion_desired,changed)
                check_companion(companion_desired)
            if journal.inactive: sim._studio_fields = copy.deepcopy(desired)
            elif fingerprint(read()) != fingerprint(raw):
                raise ValueError('Live appearance owner rejected the accepted state.')
            if not journal.inactive:
                backend._resend_all_visuals(sim)
                if fingerprint(read()) != fingerprint(raw):
                    raise ValueError('Visual resend changed the accepted appearance.')
            check_companion(companion_desired)
            form_bank.update(backend, primary, flags, _packed(backend, sim), create=True)
        except Exception:
            if companion is not None:
                if backend._form_map(primary.occult_tracker).get(backend._coerce_flags(flags)) is not companion:
                    raise ValueError('Stored current-form identity changed; no removed owner rollback attempted.')
                failed = appearance.packed(backend, companion)
                rollback = {name: row for name, row in companion_prior.items() if failed.get(name) != row}
                if rollback: restore(companion, appearance.payload(rollback))
                check_companion(companion_prior)
            if native is not None:
                failed = appearance.packed(backend, native)
                rollback = {name: row for name, row in native_prior.items() if failed.get(name) != row}
                if rollback: restore(native, appearance.payload(rollback))
            if journal.inactive: sim._studio_fields = copy.deepcopy(prior)
            if fingerprint(read()) != fingerprint(_state_from_fields(backend, prior)):
                raise ValueError('Appearance rollback differs; retain the recovery journal.')
            raise
    if action == 'studio_werewolf_ea_preview':
        from . import werewolf_defaults
        if flags != 32 or human_werewolf.preview_form(backend, primary, flags) != 32:
            raise ValueError('Select the EA Werewolf appearance owner/style before preparing EA defaults.')
        if journal.data['pending']: raise ValueError('Apply or Cancel the pending preview first.')
        generated = werewolf_defaults.prepare(backend, primary)
        if set(generated) != set(_fields(before)): raise ValueError('EA generated appearance field set differs.')
        after = _state_from_fields(backend, generated)
        token = journal.prepare('EA default Werewolf / retained previous look', before, after)
        return _response(journal, 'EA-generated Werewolf try-on prepared. Apply replaces only this appearance; Undo retains the previous look.', preview_id=token)
    if action in ('studio_paste_preview', 'studio_paste_live'):
        from . import appearance_transfer
        if journal.data['pending']: raise ValueError('Apply or Cancel the pending preview before pasting.')
        if not isinstance(value, str) or len(value) > 8192: raise ValueError('Bounded selective appearance paste required.')
        request = json.loads(value)
        if not isinstance(request, dict) or set(request) != {'clipboard_id', 'clipboard_sha256', 'selection', 'lane', 'appearance_sha256'}:
            raise ValueError('Paste clipboard/target identity fields differ.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Paste destination changed; inspect again.')
        clip = appearance_transfer.get(request['clipboard_id'], request['clipboard_sha256'])
        after = _state_from_fields(backend, appearance_transfer.merge(backend, _fields(before), clip['fields'], request['selection']))
        if after == before: return _response(journal, 'Selected appearance fields already match; no Sim changed.')
        token = journal.prepare('Paste appearance / {} form {} → form {}'.format(clip['source']['kind'], clip['source']['form'], flags), before, after)
        if action == 'studio_paste_live':
            journal.apply(token, read, write)
            return _response(journal, 'Selected appearance fields pasted and read back; unpause to verify the visible result.', live_paste_applied=True)
        return _response(journal, 'Selective appearance try-on prepared; Apply keeps it, Cancel discards it.', preview_id=token)
    if action == 'studio_shape_inspect':
        return _response(journal, 'Observed face/body slider values read without changing any form.',
                         shape_editor=morph_controls.inspect(_fields(before)))
    if action in ('studio_shape_add_preview', 'studio_shape_add_live'):
        if journal.data['pending']: raise ValueError('Apply or Cancel the pending preview before adding a modifier.')
        if not isinstance(value, str) or len(value) > 2048: raise ValueError('Bounded new modifier request required.')
        request = json.loads(value)
        if not isinstance(request, dict) or set(request) != {'group','value','resource_tgi','resource_sha256','lane','appearance_sha256'}:
            raise ValueError('New modifier request identity fields differ.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Sim/form/save or appearance changed; inspect again.')
        key = morph_controls.effective_modifier(backend, request['resource_tgi'], request['resource_sha256'])
        after = _state_from_fields(backend, morph_controls.add(_fields(before), request['group'], key, request['value']))
        form_bank.assert_idle(backend, primary)
        token = journal.prepare('Add modifier {} / group {}'.format(key, request['group']), before, after)
        if action == 'studio_shape_add_live':
            journal.apply(token, read, write)
            return _response(journal, 'Resource-verified modifier applied to this form. Unpause to inspect rendering.',
                             live_shape_applied=True, rendered_result_verified=False,
                             shape_editor=morph_controls.inspect(_fields(read())))
        return _response(journal, 'Resource-verified modifier try-on prepared.', preview_id=token)
    if action in ('studio_shape_preview', 'studio_shape_live'):
        if journal.data['pending']: raise ValueError('Apply or Cancel the pending preview before another slider edit.')
        if not isinstance(value, str) or len(value) > 2048: raise ValueError('Bounded appearance slider request required.')
        request = json.loads(value)
        if not isinstance(request, dict) or set(request) != {'field','group','index','key','before','value','lane','appearance_sha256'}:
            raise ValueError('Appearance slider request fields differ.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Sim/form/save or appearance changed; inspect again.')
        controls = {name: request[name] for name in ('field','group','index','key','before','value')}
        after = _state_from_fields(backend, morph_controls.replace(_fields(before), controls))
        if after == before: return _response(journal, 'The exact appearance slider already matches.')
        form_bank.assert_idle(backend, primary)
        token = journal.prepare('Edit {} slider / group {} / row {}'.format(request['field'],request['group'],request['index']), before, after)
        if action == 'studio_shape_live':
            journal.apply(token, read, write)
            return _response(journal, 'Live appearance slider applied and read back. Unpause to check the rendered result.',
                live_shape_applied=True, rendered_result_verified=False,
                shape_editor=morph_controls.inspect(_fields(read())),form_inventory=_form_inventory(backend, primary),
                outfit_inventory=_outfit_inventory(backend, _message(backend, sim)))
        return _response(journal, 'Appearance slider try-on prepared. Apply keeps this form edit; Cancel discards it.',preview_id=token)
    if action in ('studio_status', 'studio_history'):
        if not journal.data['pending']:
            journal.observe(before, 'Observed Sim state / external CAS')
        message = _message(backend, sim)
        if message is None:
            raise ValueError('Cannot parse outfit data.')
        lines = []
        for index, outfit in enumerate(message.outfits):
            rows = read_rows(outfit)
            lines.append('Outfit {} | category {} | ID {} | {} parts'.format(index, outfit.category, outfit.outfit_id, len(rows)))
        return _response(journal, 'Current-form outfit/history data read.', outfit_text='\n'.join(lines),
            runtime_pid=os.getpid(),
            lane=lane, outfit_inventory=_outfit_inventory(backend, message),
            current_outfit_index=_current_outfit(primary, _outfit_inventory(backend, message)) if not journal.inactive else None,
            readable_appearance_fields=sorted(_fields(before)),
            current_form_flags=backend._get_current_flags(primary), inspected_form_flags=flags, stored_form_edit_supported=True,
            appearance_source=journal.appearance_source,
            werewolf_appearance_style=('human_cc' if human_werewolf.preview_form(backend, primary, flags) == 1 else 'ea') if flags == 32 else None,
            visual_form=human_werewolf.preview_form(backend, primary, flags),
            hair_policy=outfit_hair.status(backend, primary),
            form_inventory=_form_inventory(backend, primary) if hasattr(primary, 'occult_tracker') else [],
            category_catalog=_category_catalog(backend),
            appearance_sha256=fingerprint(before), color_clipboard_ready=_COLOR_CLIPBOARD is not None)
    if action in ('studio_hair_enable', 'studio_hair_disable', 'studio_hair_status'):
        policy = (outfit_hair.status(backend, primary) if action == 'studio_hair_status' else
                  outfit_hair.configure(backend, primary, action == 'studio_hair_enable'))
        return _response(journal, 'Independent hairstyles and exact colors are owned per outfit.' if policy['enabled'] else
                         'Independent outfit hairstyle protection is disabled; retained values remain available.', hair_policy=policy)
    if action == 'studio_record':
        if value == 'latest-native':
            records = [item['sim_record'] for item in journal.data['operations'] if item.get('sim_record')]
            if not records: raise ValueError('No complete native observation retained yet.')
            return dict(sim_record.restore(records[-1]), ok=True, history_node=journal.data['cursor'], history_lane=lane, evidence_only=True)
        node = journal._node(value or journal.data['cursor'])
        if 'sim_record' not in node:
            raise ValueError('This older checkpoint contains no full native record.')
        return dict(sim_record.restore(node['sim_record']), ok=True, history_node=node['id'],
                    history_lane=lane, evidence_only=True)
    if action == 'studio_checkpoint':
        journal.observe(before, value or 'Named checkpoint', force=True)
        return _response(journal, 'Checkpoint captured without changing the Sim.')
    if action == 'studio_outfit_duplicate':
        if not isinstance(value, str) or len(value) > 2048: raise ValueError('Use a bounded outfit-copy preview.')
        request = json.loads(value)
        if not isinstance(request, dict) or set(request) != {'source', 'category', 'lane', 'appearance_sha256'}:
            raise ValueError('Outfit-copy preview protocol differs.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Sim/form/save or appearance changed; inspect again.')
        message = _message(backend, sim)
        if type(request['source']) is not int or not 0 <= request['source'] < len(message.outfits) or type(request['category']) is not int:
            raise ValueError('Select an existing source outfit and destination category.')
        existing = [outfit for outfit in message.outfits if int(outfit.category) == request['category']]
        if not existing or len(existing) >= 5:
            raise ValueError('Use an existing category with fewer than five outfits; no unsupported category generated.')
        allocator = getattr(backend, '_studio_alloc_outfit_id', None)
        if allocator is None:
            import id_generator
            allocator = id_generator.generate_object_id
        new_id = uint(int(allocator()), 64)
        if not new_id or any(int(outfit.outfit_id) == new_id for outfit in message.outfits):
            raise ValueError('Native outfit allocator returned a duplicate/reserved identity.')
        source = message.outfits[request['source']]
        clone = message.outfits.add(); clone.CopyFrom(source)
        clone.outfit_id, clone.category = new_id, request['category']
        form_bank.assert_idle(backend, primary)
        token = journal.prepare('Duplicate outfit into category {} / outfit {}'.format(request['category'], len(existing) + 1),
                                before, _state(backend, sim, message.SerializeToString()))
        return _response(journal, 'New numbered outfit preview prepared; Apply explicitly.', preview_id=token,
                         new_outfit_id=str(new_id), destination_ordinal=len(existing))
    if action == 'studio_recover':
        return _response(journal, journal.recover(before))
    if action == 'studio_part_inspect':
        _, _, rows, index, _, body = _target(backend, sim, value)
        row = rows[index]
        metadata = cas_catalog.effective_metadata(backend, row['id'])
        if metadata['body_type'] != body:
            raise ValueError('Effective CASP does not match this equipped slot.')
        candidates = []
        for outfit in _outfit_inventory(backend, _message(backend, sim)):
            for part in outfit['parts']:
                if part['body_type'] == body and part['target'] != value and part['cas_part_id'] != str(row['id']):
                    candidates.append(dict(part, outfit_index=outfit['index'], category=outfit['category']))
        editor = dict(metadata, target=value, cas_part_id=str(row['id']),
                      appearance_sha256=fingerprint(before), candidates=candidates[:256])
        return _response(journal, 'Equipped part inspected. Replacements come from this Sim and form.', part_editor=editor)
    if action == 'studio_part_preview':
        if not isinstance(value, str) or len(value) > 2048:
            raise ValueError('Part preview exceeds its bound.')
        request = json.loads(value)
        if not isinstance(request, dict) or set(request) != {'target', 'source', 'lane', 'appearance_sha256'}:
            raise ValueError('Part preview protocol differs.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Sim/form/save or appearance changed; inspect again.')
        message, outfit, rows, index, _, body = _target(backend, sim, request['target'])
        _, _, source_rows, source_index, _, source_body = _target(backend, sim, request['source'])
        source, target = source_rows[source_index], rows[index]
        if source_body != body or source['layer_id'] != target['layer_id']:
            raise ValueError('Source body type/layer is incompatible with this equipped slot.')
        if (source['color_shift'] is None) != (target['color_shift'] is None):
            raise ValueError('Color-array presence differs; no conversion guessed.')
        source_meta = cas_catalog.effective_metadata(backend, source['id'])
        target_meta = cas_catalog.effective_metadata(backend, target['id'])
        if source_meta['body_type'] != body or target_meta['body_type'] != body:
            raise ValueError('Effective replacement CASP does not match this equipped slot.')
        old_id = target['id']
        # Source already exists on this very Sim/form. Preserve destination
        # object references, layer, all other rows and unknown protobuf fields.
        target['id'], target['color_shift'] = source['id'], source['color_shift']
        write_rows(outfit, rows)
        after = _state(backend, sim, message.SerializeToString())
        if fingerprint(before) == fingerprint(after):
            return _response(journal, 'This equipped part already matches; nothing changed.')
        form_bank.assert_idle(backend, primary)
        token = journal.prepare('Replace ' + target_meta['part_name'], before, after)
        return _response(journal, 'Equipped-part replacement preview prepared.', preview_id=token,
            preview_diff='{}: {:016X} -> {:016X}; destination references/layers preserved'.format(
                request['target'], old_id, source['id']))
    if action in ('studio_catalog_preview', 'studio_catalog_live'):
        if action == 'studio_catalog_live' and journal.data['pending']:
            raise ValueError('Resolve the existing preview before applying a live catalog edit.')
        if not isinstance(value, str) or len(value) > 2048:
            raise ValueError('Catalog selection exceeds its bound.')
        request = json.loads(value)
        expected = {'outfit_index', 'outfit_id', 'part_index', 'body_type', 'cas_part_id',
                    'resource_tgi', 'resource_sha256', 'lane', 'appearance_sha256'}
        if not isinstance(request, dict) or set(request) != expected:
            raise ValueError('Catalog selection fields differ.')
        if request['lane'] != lane or request['appearance_sha256'] != fingerprint(before):
            raise ValueError('Sim/form/save or appearance changed; inspect again.')
        if (not isinstance(request['cas_part_id'], str) or not request['cas_part_id'].isdigit() or
                not _ITEM_SHA.fullmatch(str(request['resource_sha256']))):
            raise ValueError('Use an exact CASP instance/hash.')
        part_id = uint(int(request['cas_part_id']), 64)
        match = _ITEM_TGI.fullmatch(str(request['resource_tgi']))
        if not part_id or match is None or int(match.group(1), 16) != part_id:
            raise ValueError('Catalog CASP instance and resource TGI differ.')
        message = _message(backend, sim)
        number, index, body = request['outfit_index'], request['part_index'], request['body_type']
        if type(number) is not int or not 0 <= number < len(message.outfits) or type(body) is not int:
            raise ValueError('Select an exact existing outfit and body type.')
        resolved, _, reason = backend._v8_resolve_body_type(str(body))
        if resolved != body:
            raise ValueError(reason or 'The runtime has not classified this body type.')
        outfit = message.outfits[number]
        if request['outfit_id'] != str(outfit.outfit_id):
            raise ValueError('Outfit identity changed.')
        rows = read_rows(outfit)
        if index is None:
            if any(row['body_type'] == body for row in rows):
                raise ValueError('Select the existing equipped row; layered append is not inferred.')
        elif type(index) is not int or not 0 <= index < len(rows) or rows[index]['body_type'] != body:
            raise ValueError('Equipped row changed; choose the exact layer again.')
        metadata = cas_catalog.effective_metadata(backend, part_id)
        if (metadata['resource_tgi'] != request['resource_tgi'] or
                metadata['resource_sha256'] != request['resource_sha256'] or metadata['body_type'] != body):
            raise ValueError('The loaded effective CASP differs from the catalog selection.')
        age, species, gender = int(primary.age), int(primary.species), int(primary.gender)
        if (age not in (1, 2, 4, 8, 16, 32, 64, 128) or species != metadata['species'] or
                not age & metadata['age_gender']):
            raise ValueError('This CASP does not support the selected Sim age/species.')
        if metadata['parameter_flags'] & 128 and not gender & metadata['age_gender']:
            raise ValueError('This effective CASP restricts the selected gender.')
        if metadata['parameter_flags2'] & 1:
            # Cross-frame mesh conversion requires a native fitting contract;
            # no global modifier, outfit generator or guessed morph is used.
            raise ValueError('Restricted-frame fitting needs a verified native fitting contract.')
        if index is not None and rows[index]['id'] == part_id:
            return _response(journal, 'This exact catalog part is already equipped; its color and layer are retained.',
                             effective_resource_verified=True, catalog_part_id=str(part_id))
        if index is None:
            row = {'id': part_id, 'body_type': body,
                   'layer_id': metadata['layer_id'] if rows and rows[0]['layer_id'] is not None else None,
                   'color_shift': NEUTRAL_SHIFT if rows and rows[0]['color_shift'] is not None else None,
                   'object_id': 0 if rows and rows[0]['object_id'] is not None else None}
            if rows and rows[0]['layer_id'] is not None and row['layer_id'] is None:
                # Pre-v50 CASP has no layer field. Layer zero is the exact
                # baseline Dresser default only for an empty category.
                row['layer_id'] = 0
            rows.append(row)
        else:
            row = rows[index]
            if row['object_id'] not in (None, 0):
                raise ValueError('Object-backed CASP replacement needs a native attachment contract.')
            row['id'] = part_id
            if row['color_shift'] is not None:
                row['color_shift'] = NEUTRAL_SHIFT
            if row['layer_id'] is not None and metadata['layer_id'] is not None:
                row['layer_id'] = metadata['layer_id']
        write_rows(outfit, rows)
        after = _state(backend, sim, message.SerializeToString())
        if fingerprint(before) == fingerprint(after):
            return _response(journal, 'This exact catalog part already matches; nothing changed.')
        form_bank.assert_idle(backend, primary)
        token = journal.prepare('Select catalog part: ' + metadata['part_name'], before, after)
        if action == 'studio_catalog_live':
            journal.apply(token, read, write)
            current = read()
            inventory = _outfit_inventory(backend, _message(backend, sim))
            return _response(journal, 'Live catalog item applied and read back. Unpause to check the rendered result.',
                live_catalog_applied=True, rendered_result_verified=False, effective_resource_verified=True,
                catalog_part_id=str(part_id), appearance_sha256=fingerprint(current), outfit_inventory=inventory,
                form_inventory=_form_inventory(backend, primary),
                current_outfit_index=_current_outfit(primary, inventory) if not journal.inactive else None,
                current_form_flags=backend._get_current_flags(primary), inspected_form_flags=flags,
                appearance_source=journal.appearance_source)
        return _response(journal, 'Catalog item preview prepared from verified loaded CASP bytes. Apply explicitly.',
                         preview_id=token, effective_resource_verified=True, catalog_part_id=str(part_id),
                         preview_diff='{} / outfit {} / BodyType {}: {:016X}'.format(flags, number, body, part_id))
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
            'resource_tgi': metadata['resource_tgi'], 'resource_key_query': metadata['resource_key_query'],
            'casp_version': metadata['version'], 'part_name': metadata['part_name'], 'channels': channels}
        return _response(journal, 'Read effective CASP slider bounds and exact Q14 values.', color_editor=editor)
    if action in ('studio_color_edit', 'studio_color_live'):
        if action == 'studio_color_live' and journal.data['pending']:
            raise ValueError('Resolve the existing preview before applying a live color edit.')
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
        after = _state(backend, sim, message.SerializeToString())
        if row['color_shift'] == old:
            return _response(journal, 'The requested values already match this exact Q14 color.',
                             live_color_applied=False)
        token = journal.prepare('Edit part color: ' + ', '.join(sorted(request['edits'])), before, after)
        if action == 'studio_color_live':
            # One owner-thread transaction, with the same durable history,
            # stale-state refusal and exact rollback as Preview + Apply.
            # Never send game input, activate a form or change clock speed.
            journal.apply(token, read, write)
            current = read()
            current_message = _message(backend, sim)
            _, _, current_rows, current_index, _, _ = _target(backend, sim, request['target'])
            accepted = current_rows[current_index]['color_shift']
            editor = dict(target=request['target'], cas_part_id=str(row['id']),
                color_hex='{:016X}'.format(accepted), appearance_sha256=fingerprint(current),
                resource_sha256=metadata['resource_sha256'], resource_tgi=metadata['resource_tgi'],
                resource_key_query=metadata['resource_key_query'], casp_version=metadata['version'],
                part_name=metadata['part_name'], channels={name: dict(bounds, value=color_shift.decode(accepted)[name])
                    for name, bounds in metadata['ranges'].items()})
            return _response(journal, 'Live part color applied and read back. Unpause to check the rendered result.',
                live_color_applied=True, rendered_result_verified=False, color_editor=editor,
                appearance_sha256=fingerprint(current), outfit_inventory=_outfit_inventory(backend, current_message),
                form_inventory=_form_inventory(backend, primary),
                current_outfit_index=_current_outfit(primary, _outfit_inventory(backend, current_message)) if not journal.inactive else None,
                current_form_flags=backend._get_current_flags(primary), inspected_form_flags=flags,
                appearance_source=journal.appearance_source)
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
        after = _state(backend, sim, message.SerializeToString())
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
        form_bank.assert_idle(backend, primary)
        journal.apply(value, read, write)
        return _response(journal, 'Appearance write matches the accepted preview. Stored form owner updated without activation.' if journal.inactive else 'Appearance write matches the accepted preview. Save/reload testing remains pending.')
    raise ValueError('Unknown Studio action.')
