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
from . import cas_catalog, color_shift, outfit_snapshot, form_appearance as appearance, form_bank, sim_record, outfit_hair
from .change_journal import ChangeJournal, fingerprint, decoded
from .dresser_parts import DresserParts, read_rows, write_rows, uint

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
              'pending_preview': (pending or {}).get('id'), 'save_reload_verified': False}
    if observations:
        result['latest_native_observation'] = {'sha256': observations[-1]['sim_record']['sha256'], 'time': observations[-1]['time']}
        previous = observations[-2]['sim_record'] if len(observations) > 1 else journal.data['nodes'][0].get('sim_record')
        if previous: result['latest_native_observation']['delta'] = sim_record.delta(previous, observations[-1]['sim_record'])
    if pending:
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
    sim, before, journal, lane = _context(backend, sim_id, form, history=action != 'studio_items')
    primary, flags = journal.primary_sim, journal.form_flags
    if action == 'studio_items':
        return _items_response(backend, sim, before, journal, lane, value)
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
        restore = getattr(backend, '_studio_restore_appearance', backend._restore_siminfo_payload)
        native = journal.native_target if journal.inactive else sim
        native_prior = appearance.packed(backend, native) if native is not None else None
        try:
            if native is not None:
                restore(native, appearance.payload(desired))
                if fingerprint(_state_from_fields(backend, appearance.packed(backend, native))) != fingerprint(raw):
                    raise ValueError('Appearance owner rejected the accepted state.')
            if journal.inactive: sim._studio_fields = copy.deepcopy(desired)
            elif fingerprint(read()) != fingerprint(raw):
                raise ValueError('Live appearance owner rejected the accepted state.')
            form_bank.update(backend, primary, flags, _packed(backend, sim), create=True)
        except Exception:
            if native is not None: restore(native, appearance.payload(native_prior))
            if journal.inactive: sim._studio_fields = copy.deepcopy(prior)
            if fingerprint(read()) != fingerprint(_state_from_fields(backend, prior)):
                raise ValueError('Appearance rollback differs; retain the recovery journal.')
            raise
        if not journal.inactive: backend._resend_all_visuals(sim)
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
