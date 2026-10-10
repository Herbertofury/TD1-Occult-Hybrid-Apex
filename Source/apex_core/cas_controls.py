"""Typed CAS capabilities from the installed native UI, never arbitrary services.

Pagination bounds each transport packet, not the complete catalog or history.
Native null, refusal and unresolved writes remain explicit outcomes.
"""
import math

READS = frozenset(('catalog', 'variants', 'swatches', 'layers', 'body-types', 'modifiers', 'hair-matching',
    'voices', 'walkstyles', 'detail-status', 'filters'))
OPERATIONS = READS | frozenset(('preset', 'select-layer', 'remove', 'layer-add',
    'layer-remove', 'layer-move', 'swatch', 'physique', 'body-type', 'color-sliders', 'hair-match',
    'voice-actor', 'voice-pitch', 'walkstyle', 'detail-mode', 'filter-clear'))
PANEL_OPERATIONS = frozenset(('catalog', 'variants', 'preset', 'select-layer',
    'remove', 'layers', 'layer-add', 'layer-remove', 'layer-move', 'body-types', 'body-type', 'modifiers', 'color-sliders',
    'filters', 'filter-clear'))
PART_PROFILE_PANELS = frozenset(('profile_hair_eyebrows', 'profile_pet_whiskers'))
SCHEMAS = {
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
        if selected != request['data_id']:
            raise ValueError('Native swatch did not read back its exact selected identity.')
    if op == 'physique':
        values = client['sim'].get('physiqueValues')
        if (not isinstance(values, list) or len(values) <= request['physique_type'] or
                type(values[request['physique_type']]) not in (int, float) or
                abs(values[request['physique_type']]-request['value']) > 0.000001):
            raise ValueError('Native physique slider did not read back its requested value.')
