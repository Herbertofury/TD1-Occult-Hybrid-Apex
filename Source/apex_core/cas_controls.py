"""Typed CAS capabilities from the installed native UI, never arbitrary services.

Pagination bounds each transport packet, not the complete catalog or history.
Native null, refusal and unresolved writes remain explicit outcomes.
"""
import math


class PostconditionMismatch(ValueError):
    """A complete native readback differs from the requested target value."""


READS = frozenset(('catalog', 'variants', 'swatches', 'layers', 'body-types', 'modifiers', 'hair-matching', 'occults',
    'voices', 'walkstyles', 'detail-status', 'filters'))
OPERATIONS = READS | frozenset(('preset', 'select-layer', 'remove', 'layer-add',
    'layer-remove', 'layer-move', 'swatch', 'physique', 'body-type', 'color-sliders', 'hair-match',
    'voice-actor', 'voice-pitch', 'walkstyle', 'detail-mode', 'filter-clear', 'occult-view', 'occult-cache-view', 'occult-owner-view', 'form-owner-select', 'workspace', 'form-menu', 'pair-link', 'pair-copy'))
PANEL_OPERATIONS = frozenset(('catalog', 'variants', 'preset', 'select-layer',
    'remove', 'layers', 'layer-add', 'layer-remove', 'layer-move', 'body-types', 'body-type', 'modifiers', 'color-sliders',
    'filters', 'filter-clear'))
PART_PROFILE_PANELS = frozenset(('profile_hair_eyebrows', 'profile_pet_whiskers'))
SCHEMAS = {
    'pair-link': {'operation','owner_id','enabled'},
    'pair-copy': {'operation','source_owner_id','target_owner_id'},
    'form-menu': {'operation', 'family'},
    'form-owner-select': {'operation','owner_id','native_kind','owned_mask','household_id','native_session','expected_layer','test_token'},
    'workspace': {'operation', 'x', 'y', 'scale', 'locked', 'collapsed'},
    'occults': {'operation'},
    'occult-view': {'operation', 'occult_type', 'expected_all_occults', 'household_id', 'native_session', 'expected_layer'},
    'occult-cache-view': {'operation', 'occult_type', 'expected_all_occults', 'household_id', 'native_session', 'expected_layer', 'owned_mask', 'test_token'},
    'occult-owner-view': {'operation', 'occult_type', 'expected_all_occults', 'household_id', 'native_session', 'expected_layer', 'owned_mask', 'test_token'},
    'catalog': {'operation', 'panel', 'offset', 'limit'},
    'variants': {'operation', 'panel', 'data_id'},
    'preset': {'operation', 'panel', 'data_id'},
    'select-layer': {'operation', 'panel', 'data_id', 'body_type', 'layer_index', 'layer_id'},
    'remove': {'operation', 'panel', 'data_id'},
    'layers': {'operation', 'panel', 'body_type'},
    'layer-add': {'operation', 'panel', 'body_type'},
    'layer-remove': {'operation', 'panel', 'body_type', 'layer_index', 'layer_id'},
    'layer-move': {'operation', 'panel', 'body_type', 'layer_index', 'layer_id', 'target_index'},
    'swatches': {'operation', 'swatch_type', 'offset', 'limit'},
    'swatch': {'operation', 'swatch_type', 'data_id', 'color_index'},
    'physique': {'operation', 'physique_type', 'value'},
    'body-types': {'operation', 'panel'},
    'body-type': {'operation', 'panel', 'body_type'},
    'modifiers': {'operation', 'panel', 'data_id', 'layer_index', 'layer_id'},
    'color-sliders': {'operation', 'panel', 'data_id', 'layer_index', 'layer_id', 'hue', 'opacity', 'saturation', 'brightness'},
    'hair-matching': {'operation'},
    'hair-match': {'operation', 'flags'},
    'voices': {'operation'},
    'voice-actor': {'operation', 'actor_index'},
    'voice-pitch': {'operation', 'value'},
    'walkstyles': {'operation'},
    'walkstyle': {'operation', 'data_id'},
    'detail-status': {'operation'},
    'detail-mode': {'operation', 'enabled'},
    'filters': {'operation', 'panel'},
    'filter-clear': {'operation', 'panel'},
}


def identity(value):
    if (not isinstance(value, str) or not value.isascii() or not value.isdecimal() or
            not 0 < int(value) < 2**64 or str(int(value)) != value):
        raise ValueError('Use one canonical decimal native catalog identity.')
    return value


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid typed CAS ' + name + '.')
    return value


def wire(request, panel):
    op = request['operation']
    if set(request) != SCHEMAS[op]:
        raise ValueError('CAS control requires its complete typed fields.')
    state = panel(request['panel']) if op in PANEL_OPERATIONS else 0
    category, index, value = 0, 0, ''
    if op in ('pair-link','pair-copy'):
        import re
        names=('owner_id',) if op=='pair-link' else ('source_owner_id','target_owner_id')
        for name in names:
            if not isinstance(request[name],str) or re.fullmatch(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}',request[name]) is None:
                raise ValueError('Pair controls require exact independently owned form identities.')
        if op=='pair-link':
            if type(request['enabled']) is not bool:raise ValueError('Choose explicit link or unlink.')
            value=request['owner_id']+','+('1' if request['enabled'] else '0')
        else:
            if request['source_owner_id']==request['target_owner_id']:raise ValueError('Copy requires two distinct owners.')
            value=request['source_owner_id']+','+request['target_owner_id']
        return 0,0,0,value
    if op == 'form-menu':
        import re
        family = request['family']
        if not isinstance(family, str) or re.fullmatch(r'[a-z0-9_][a-z0-9_-]{0,63}', family) is None:
            raise ValueError('Choose all or one exact returned life-state family.')
        return 0, 0, 0, family
    if op == 'form-owner-select':
        import re
        owner = request['owner_id']
        if not isinstance(owner, str) or re.fullmatch(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}', owner) is None:
            raise ValueError('Use the exact existing independent form owner identity.')
        identity(request['household_id'])
        state = integer(request['native_kind'], 1, 64, 'rendering kind')
        if state & (state-1): raise ValueError('A form requires one native rendering kind.')
        category = integer(request['owned_mask'], 1, 127, 'owned membership mask')
        if not category & 1 or not category & state: raise ValueError('A form requires an existing rendering owner.')
        integer(request['native_session'], 1, 2**31-1, 'editor session')
        index = integer(request['expected_layer'], 0, 1, 'current native layer')
        if not isinstance(request['test_token'], str) or re.fullmatch(r'[0-9a-f]{32}', request['test_token']) is None:
            raise ValueError('Independent form qualification requires the disposable profile token.')
        return state, category, index, owner
    if op == 'workspace':
        values = []
        for name, low, high in (('x', 0, 1), ('y', 0, 1), ('scale', 0.7, 1.5)):
            number = request[name]
            if type(number) not in (int, float) or not math.isfinite(number) or not low <= number <= high:
                raise ValueError('CAS workspace requires finite bounded ' + name + '.')
            values.append(format(float(number) if number else 0.0, '.9f').rstrip('0').rstrip('.'))
        for name in ('locked', 'collapsed'):
            if type(request[name]) is not bool:
                raise ValueError('CAS workspace requires explicit typed ' + name + '.')
            values.append('1' if request[name] else '0')
        return 0, 0, 0, ','.join(values)
    if op == 'occults':
        return 0, 0, 0, ''
    if op in ('occult-view', 'occult-cache-view', 'occult-owner-view'):
        target = integer(request['occult_type'], 1 if op == 'occult-owner-view' else 2, 2**30, 'existing occult appearance')
        if target & (target - 1):
            raise ValueError('Choose one existing native occult appearance.')
        mask = integer(request['expected_all_occults'], 1, 2**31-1, 'complete observed membership mask')
        if op == 'occult-view' and mask & target != target:
            raise ValueError('Native CAS has no observed membership for this view; this operation cannot add or replace a life state.')
        session = integer(request['native_session'], 1, 2**31-1, 'current native session')
        layer = integer(request['expected_layer'], 0, 1, 'currently observed layer')
        value = identity(request['household_id']) + ',' + str(layer)
        if op in ('occult-cache-view', 'occult-owner-view'):
            owned = integer(request['owned_mask'], 1, 127, 'captured native membership mask')
            token = request['test_token']
            if (target not in ((1, 2, 4, 8, 16, 32, 64) if op == 'occult-owner-view' else (2, 4, 8, 16, 32, 64)) or owned & target != target or mask & ~owned or
                    not isinstance(token, str) or len(token) != 32 or any(c not in '0123456789abcdef' for c in token)):
                raise ValueError('Cache qualification requires a captured existing occult and exact disposable token.')
            value += ',' + str(owned)
        return session, mask, target, value
    if op == 'voice-actor':
        return 0, 0, integer(request['actor_index'], 0, 2**31-1, 'zero-based eligible voice index'), ''
    if op == 'voice-pitch':
        number = request['value']
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError('Voice pitch requires a finite value within the eligible native voice range.')
        return 0, 0, 0, str(float(number))
    if op == 'detail-mode':
        if type(request['enabled']) is not bool:
            raise ValueError('Detailed edit mode requires an explicit boolean.')
        return 0, 0, 0, '1' if request['enabled'] else '0'
    if op in ('modifiers', 'color-sliders'):
        category = integer(request['layer_id'], 0, 127, 'native layer identity')
        index = integer(request['layer_index'], -1, 2**31-1, 'layer index')
        if (index == -1) != (category == 0) or category == 127:
            raise ValueError('Use an ordinary slot (-1, 0) or one explicit non-medical native layer.')
        value = identity(request['data_id'])
        if op == 'color-sliders':
            for name in ('hue', 'opacity', 'saturation', 'brightness'):
                number = request[name]
                if type(number) not in (int, float) or not math.isfinite(number):
                    raise ValueError('Native color slider requires finite typed numbers.')
                value += ',' + str(float(number))
        return state, category, index, value
    if op == 'hair-match':
        return 0, 0, 0, str(integer(request['flags'], 0, 63, 'hair matching flags'))
    if 'data_id' in request:
        value = identity(request['data_id'])
    if op in ('catalog', 'swatches'):
        category = integer(request['offset'], 0, 2**31-1, 'page offset')
        index = integer(request['limit'], 1, 32, 'page size')
    if 'body_type' in request:
        category = integer(request['body_type'], 1, 2**16-1, 'body type')
    if 'layer_index' in request:
        index = integer(request['layer_index'], 0, 2**31-1, 'layer index')
        layer = integer(request['layer_id'], 1, 127, 'native layer identity')
        value = (value + ',' if op == 'select-layer' else '') + str(layer)
    if op == 'layer-move':
        value += ',' + str(integer(request['target_index'], 0, 2**31-1, 'target layer index'))
    if 'swatch_type' in request:
        state = integer(request['swatch_type'], 0, 16, 'swatch type')
        if state == 5:
            raise ValueError('Featured-look colors require the native look identity.')
    if op == 'swatch':
        index = integer(request['color_index'], 0, 2**16-1, 'fur color index')
        if state != 6 and index != 0:
            raise ValueError('Only fur palettes have indexed native colors.')
    if op == 'physique':
        state = integer(request['physique_type'], 0, 1, 'physique type')
        number = request['value']
        if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError('Native physique slider requires a finite value from 0 to 1.')
        value = str(float(number))
    return state, category, index, value


def validate(client, request):
    """Require operation-specific native postconditions, not panel visibility."""
    op = request['operation']
    control = client.get('control')
    if not isinstance(control, dict) or control.get('operation') != op:
        raise ValueError('Native CAS control has no exact typed result.')
    if op in ('pair-link','pair-copy'):
        import re
        pair=control.get('pair')
        if (control.get('acknowledged') is not True or control.get('scope')!='whole-appearance' or
            not isinstance(control.get('request_id'),str) or re.fullmatch('[0-9a-f]{32}',control['request_id']) is None or
            control.get('sim_id')!=client.get('sim',{}).get('simId') or not isinstance(pair,dict) or
            pair.get('sim_id')!=control['sim_id'] or pair.get('base_owner_id')==pair.get('alternate_owner_id') or
            pair.get('human_owner_id') not in (pair.get('base_owner_id'),pair.get('alternate_owner_id'))):
            raise PostconditionMismatch('Native pair action lacks its exact completed Sim and shared-Human pair.')
        if op=='pair-link':
            other=pair['alternate_owner_id'] if pair['base_owner_id']==pair['human_owner_id'] else pair['base_owner_id']
            if other!=request['owner_id'] or control.get('enabled') is not request['enabled'] or pair.get('linked') is not request['enabled']:
                raise PostconditionMismatch('The requested actual form link state did not read back.')
        elif (control.get('source_owner_id')!=request['source_owner_id'] or control.get('target_owner_id')!=request['target_owner_id'] or
              {request['source_owner_id'],request['target_owner_id']}!={pair['base_owner_id'],pair['alternate_owner_id']}):
            raise PostconditionMismatch('Copy did not acknowledge its exact source and destination.')
        return
    if op == 'form-menu':
        family = '' if request['family'] == 'all' else request['family']
        rows = control.get('life_states')
        if (control.get('appearance_written') is not False or control.get('variant_family') != family or
                not isinstance(rows, list) or not 1 <= len(rows) <= 2048 or
                any(not isinstance(row, dict) or not isinstance(row.get('family'), str) or
                    not isinstance(row.get('variants'), list) or not row['variants'] for row in rows) or
                len({row['family'] for row in rows}) != len(rows) or
                family and family not in {row['family'] for row in rows}):
            raise PostconditionMismatch('The exact life-state menu did not read back; no appearance selection is authorized.')
        return
    if op == 'form-owner-select':
        native = client.get('sim', {})
        context = client.get('native_context')
        rendered = context.get('rendered_form') if isinstance(context, dict) else None
        strip = client.get('form_strip')
        if (control.get('owner_id') != request['owner_id'] or native.get('householdId') != request['household_id'] or
                not isinstance(strip, dict) or strip.get('sim_id') != native.get('simId') or
                strip.get('selected_owner_id') != request['owner_id'] or
                strip.get('native_owner_state') != 'bound' or strip.get('desired_owner_id') != '' or
                not isinstance(rendered, dict) or rendered.get('query') != 'returned-value' or
                type(rendered.get('value')) is not int or rendered['value'] != request['native_kind'] or
                type(native.get('allOccultTypes')) is not int or
                native['allOccultTypes'] | 1 != request['owned_mask']):
            raise PostconditionMismatch('Native CAS did not show the exact independently selected form and membership.')
        return
    if op == 'workspace':
        layout = control.get('layout')
        if (not isinstance(layout, dict) or control.get('appearance_written') is not False or
                control.get('visible') is not True or layout.get('dragging') is not False):
            raise ValueError('CAS workspace did not return a visible settled layout.')
        for name in ('x', 'y', 'scale'):
            actual = layout.get(name)
            if type(actual) not in (int, float) or not math.isfinite(actual) or abs(actual-request[name]) > 0.000001:
                raise PostconditionMismatch('CAS workspace ' + name + ' did not read back.')
        for name in ('locked', 'collapsed'):
            if type(layout.get(name)) is not bool or layout[name] != request[name]:
                raise PostconditionMismatch('CAS workspace ' + name + ' did not read back.')
        return
    if op in ('occults', 'occult-view', 'occult-cache-view', 'occult-owner-view'):
        rows = control.get('occults')
        if (not isinstance(rows, list) or len(rows) > 32 or
                any(not isinstance(row, dict) or type(row.get('occult_type')) is not int or
                    not 0 < row['occult_type'] < 2**31 or row['occult_type'] & (row['occult_type']-1) for row in rows) or
                len({row['occult_type'] for row in rows}) != len(rows)):
            raise ValueError('The actual native occult catalog is unavailable or ambiguous.')
        if op == 'occult-view':
            native = client.get('sim', {})
            if (native.get('allOccultTypes') != request['expected_all_occults'] or
                    native.get('occultType') != request['occult_type'] or
                    native.get('householdId') != request['household_id']):
                raise PostconditionMismatch('Native CAS did not select the requested view with every previous occult membership intact.')
        if op == 'occult-cache-view':
            native = client.get('sim', {})
            mask = native.get('allOccultTypes')
            if (type(mask) is not int or mask not in (request['occult_type'], request['occult_type'] | 1) or
                    native.get('occultType') != request['occult_type'] or
                    native.get('householdId') != request['household_id']):
                raise PostconditionMismatch('Experimental native cache selection did not reach its requested pair projection.')
        if op == 'occult-owner-view':
            native = client.get('sim', {})
            if (type(native.get('allOccultTypes')) is not int or native['allOccultTypes'] not in (request['owned_mask'], request['owned_mask'] & ~1) or
                    type(native.get('occultType')) is not int or native['occultType'] != request['occult_type'] or
                    native.get('householdId') != request['household_id']):
                raise PostconditionMismatch('Native owner selection did not retain the requested form and every captured membership.')
    if op in ('voices', 'voice-actor', 'voice-pitch'):
        rows = control.get('voices')
        actor, pitch = client['sim'].get('voiceActor'), client['sim'].get('voicePitch')
        if (not isinstance(rows, list) or not rows or type(actor) is not int or not 1 <= actor <= len(rows) or
                type(pitch) not in (int, float) or not math.isfinite(pitch)):
            raise ValueError('Native voice inventory and current voice are incomplete.')
        for row in rows:
            if (not isinstance(row, dict) or any(type(row.get(k)) not in (int, float) or
                    not math.isfinite(row[k]) for k in ('minPitch', 'maxPitch')) or row['minPitch'] > row['maxPitch']):
                raise ValueError('Eligible native voice pitch bounds are incomplete.')
        if op == 'voice-actor' and actor != request['actor_index'] + 1:
            raise ValueError('Native voice actor did not retain its requested zero-based index.')
        if op == 'voice-pitch' and abs(pitch-request['value']) > 0.000001:
            raise ValueError('Native voice pitch did not retain the requested value.')
        if op != 'voices' and not rows[actor-1]['minPitch'] <= pitch <= rows[actor-1]['maxPitch']:
            raise ValueError('Edited voice pitch is outside the selected native voice range.')
    if op in ('walkstyles', 'walkstyle'):
        rows = control.get('walkstyles')
        if (not isinstance(rows, list) or any(not isinstance(row, dict) or
                not isinstance(row.get('id'), str) or type(row.get('equipped')) is not bool for row in rows) or
                len({row['id'] for row in rows}) != len(rows)):
            raise ValueError('Native walkstyle inventory is incomplete or ambiguous.')
        if op == 'walkstyle':
            selected = [row['id'] for row in rows if row['equipped']]
            if selected != [request['data_id']]:
                raise ValueError('Native walkstyle did not retain the requested trait identity.')
    if op in ('detail-status', 'detail-mode'):
        if type(control.get('active')) is not bool:
            raise ValueError('Native detailed edit mode lacks a boolean readback.')
        if op == 'detail-mode' and control['active'] is not request['enabled']:
            raise ValueError('Native detailed edit mode did not retain its requested state.')
    if op in ('filters', 'filter-clear'):
        filters = control.get('filters')
        if (not isinstance(filters, dict) or any(not isinstance(filters.get(key), list) for key in ('tags', 'excludeTags', 'packIds')) or
                any(type(filters.get(key)) is not bool for key in ('filterByGameplayUnlocks', 'filterLocked',
                    'filterPurchasedProducts', 'filterModdedContent'))):
            raise ValueError('Native catalog filters are incomplete.')
        if op == 'filter-clear' and control.get('selected_bubble_empty') is not True:
            raise ValueError('Native removable catalog filter selections did not clear completely.')
    if op in ('hair-matching', 'hair-match'):
        integer(control.get('flags'), 0, 63, 'hair matching readback')
        if op == 'hair-match' and control['flags'] != request['flags']:
            raise ValueError('Native hair matching flags did not retain the requested mask.')
    if op in ('modifiers', 'color-sliders'):
        observed = control.get('selected')
        if not isinstance(observed, dict) or observed.get('dataID') != request['data_id']:
            raise ValueError('Native modifiers belong to another equipped part.')
        if op == 'color-sliders':
            before = control.get('before')
            if not isinstance(before, dict) or before.get('dataID') != request['data_id']:
                raise ValueError('Native color edit lacks its complete original modifiers.')
            changed = {'hue_range_modifier', 'opacity_range_modifier', 'saturation_range_modifier', 'value_range_modifier'}
            if {k:v for k,v in before.items() if k not in changed} != {k:v for k,v in observed.items() if k not in changed}:
                raise ValueError('Native color edit changed other modifier fields.')
            for name, native in (('hue', 'hue'), ('opacity', 'opacity'), ('saturation', 'saturation'), ('brightness', 'value')):
                value = observed.get(native + '_range_modifier')
                if type(value) not in (int, float) or not math.isfinite(value) or abs(value-request[name]) > 0.000001:
                    raise ValueError('Native color slider did not read back its requested value.')
    if op in ('catalog', 'swatches'):
        rows = control.get('items')
        total = control.get('total')
        if (type(total) is not int or total < 0 or not isinstance(rows, list) or
                len(rows) != min(request['limit'], max(0, total-request['offset'])) or
                type(control.get('offset')) is not int or type(control.get('limit')) is not int or
                control['offset'] != request['offset'] or control['limit'] != request['limit'] or
                any(not isinstance(row, dict) for row in rows)):
            raise ValueError('Native catalog page is incomplete or has a different range.')
    if op == 'variants':
        if control.get('data_id') != request['data_id'] or not isinstance(control.get('family'), dict):
            raise ValueError('Native variant result lacks the requested product identity.')
    if op in ('body-types', 'body-type'):
        types = control.get('body_types')
        if (not isinstance(types, list) or not types or
                any(type(kind) is not int or kind <= 0 for kind in types) or len(types) != len(set(types)) or
                type(control.get('body_type')) is not int or control['body_type'] not in types):
            raise ValueError('Native body-region navigation lacks its complete eligible inventory.')
        if op == 'body-type' and control['body_type'] != request['body_type']:
            raise ValueError('Native body region did not read back the requested identity.')
    if op == 'preset':
        if (control.get('selected_data_id') != request['data_id'] or
                control.get('preset_query') != 'returned-value' or
                not isinstance(control.get('preset'), dict)):
            raise ValueError('Native preset selection did not read back its exact catalog identity.')
    if op in ('layers', 'layer-add', 'layer-remove', 'layer-move', 'select-layer'):
        layers = control.get('layers')
        if (type(control.get('body_type')) is not int or control['body_type'] != request['body_type'] or not isinstance(layers, list) or
                any(not isinstance(row, dict) or type(row.get('layerId')) is not int or
                    not 1 <= row['layerId'] <= 127 or 'partKey' not in row for row in layers)):
            raise ValueError('Native layer readback is incomplete or belongs to another body type.')
        if op == 'select-layer':
            at = request['layer_index']
            if (at >= len(layers) or layers[at]['layerId'] != request['layer_id'] or
                    str(layers[at]['partKey']) != request['data_id']):
                raise ValueError('Native layered item did not retain its exact part and layer identity.')
        elif op != 'layers':
            before = control.get('before')
            if not isinstance(before, list):
                raise ValueError('Native layer mutation lacks its complete original array.')
            if op == 'layer-add':
                if (len(layers) != len(before)+1 or layers[:-1] != before or
                        str(layers[-1]['partKey']) != '0' or
                        layers[-1]['layerId'] in [row['layerId'] for row in before]):
                    raise ValueError('Native layer append changed existing layers or did not append one empty layer.')
            else:
                at = request['layer_index']
                if at >= len(before) or before[at]['layerId'] != request['layer_id']:
                    raise ValueError('Native layer mutation original identity differs.')
                expected = list(before)
                row = expected.pop(at)
                if op == 'layer-move':
                    if request['target_index'] >= len(before):
                        raise ValueError('Native layer move target is outside the original array.')
                    expected.insert(request['target_index'], row)
                if layers != expected:
                    raise ValueError('Native layer mutation readback lost or changed another layer.')
    if op == 'remove':
        if control.get('removed_data_id') != request['data_id'] or any(
                str(row.get('dataID')) == request['data_id'] for row in client.get('selected') or []):
            raise ValueError('Native CAS removal did not remove the requested equipped identity.')
    if op == 'swatch':
        selected = control.get('selected')
        if request['swatch_type'] == 6:
            if not isinstance(selected, list) or request['color_index'] >= len(selected):
                raise ValueError('Native fur color array did not read back the requested slot.')
            selected = selected[request['color_index']]
        elif request['swatch_type'] == 0:
            if not isinstance(selected, dict):
                raise ValueError('Native skin tone did not return its complete modifier record.')
            selected = selected.get('dataID')
        if (not isinstance(selected, str) or not selected.isascii() or not selected.isdecimal() or
                str(int(selected)) != selected or not 0 < int(selected) < 2**64):
            raise ValueError('Native swatch lacks a canonical selected identity.')
        if selected != request['data_id']:
            raise PostconditionMismatch('Native swatch did not read back its exact selected identity.')
    if op == 'physique':
        values = client['sim'].get('physiqueValues')
        if (not isinstance(values, list) or len(values) <= request['physique_type'] or
                type(values[request['physique_type']]) not in (int, float) or
                abs(values[request['physique_type']]-request['value']) > 0.000001):
            raise ValueError('Native physique slider did not read back its requested value.')
