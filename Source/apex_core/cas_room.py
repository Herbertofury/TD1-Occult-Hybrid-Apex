"""Retained form rail for Apex's CAS workspace; no native objects or writes.

Every captured owner stays visible even when EA exposes only two layers.
Visibility never authorizes selection, owner mapping, or appearance acceptance.
Only the exact observed Human-base pair supports the current native transport.
Alien's creature-base/disguise ordering is retained without guessing a layer.
"""
import copy
import os

NAMES = {1: 'Human', 2: 'Alien', 4: 'Vampire', 8: 'Mermaid',
         16: 'Spellcaster', 32: 'Werewolf', 64: 'Fairy'}


def _id(value):
    return (isinstance(value, str) and 0 < len(value) <= 20 and value.isascii()
        and value.isdecimal() and str(int(value)) == value and 0 < int(value) < 2**64)


def inventory(baseline, client):
    """Build only from a privately authenticated capture and fresh typed client."""
    native, obs = client.get('sim'), client.get('owner_pair_observation')
    if (not isinstance(baseline, dict) or baseline.get('complete') is not True or
            type(baseline.get('runtime_pid')) is not int or baseline['runtime_pid'] != os.getpid() or
            not all(_id(baseline.get(k)) for k in ('original_sim_id', 'household_id', 'save_guid')) or
            not isinstance(native, dict) or native.get('simId') != baseline['original_sim_id'] or
            native.get('householdId') != baseline['household_id'] or not isinstance(obs, dict) or
            type(obs.get('session')) is not int or not 0 < obs['session'] < 2**31 or
            obs.get('stable') is not True or obs.get('selected_query') != 'returned-value'):
        raise ValueError('CAS room requires the exact captured original and fresh native selection.')
    owners, ids = {}, set()
    wrappers = baseline.get('wrappers')
    if not isinstance(wrappers, list) or not 0 < len(wrappers) <= 32:
        raise ValueError('CAS room captured form inventory is unavailable.')
    for row in wrappers:
        if (not isinstance(row, dict) or set(row) != {'form_flags', 'sim_id'} or
                type(row['form_flags']) is not int or not 0 < row['form_flags'] < 2**31 or
                row['form_flags'] & (row['form_flags']-1) or row['form_flags'] in owners or
                not _id(row['sim_id']) or row['sim_id'] in ids or row['sim_id'] == baseline['original_sim_id']):
            raise ValueError('CAS room refuses ambiguous or invalid captured owners.')
        owners[row['form_flags']] = row['sim_id']; ids.add(row['sim_id'])
    selector = obs.get('selector_feed', {})
    raw, retained = selector.get('raw_feed', {}), selector.get('retained', {})
    if (selector.get('protocol') != 1 or selector.get('scope') != 'native-selector-owner-pair-view' or
            selector.get('service_registered') is not True or obs.get('selector_query') != 'returned-value' or
            raw.get('complete') is not True or raw.get('delivered') is not True or
            raw.get('before_native_handler') is not True or type(raw.get('sequence')) is not int or raw['sequence'] <= 0 or
            retained.get('complete') is not True or retained.get('available') is not True or
            retained.get('selected_sim_id') != baseline['original_sim_id']):
        raise ValueError('CAS room requires both actual raw and retained native pair feeds.')
    pairs, original_pairs = retained.get('pairs'), raw.get('pairs')
    index, layer = retained.get('selected_index'), retained.get('selected_layer')
    if (not isinstance(pairs, list) or not isinstance(original_pairs, list) or not 0 < len(pairs) <= 32 or
            len(pairs) != len(original_pairs) or type(index) is not int or not 0 <= index < len(pairs) or
            type(layer) is not int or layer not in (0, 1) or raw.get('selected_index') != index or
            raw.get('base_row_count') != len(pairs) or raw.get('alternate_row_count') != len(pairs)):
        raise ValueError('CAS room refuses changed native pair positions.')
    pair, original = pairs[index], original_pairs[index]
    if pair.get('index') != index or original.get('index') != index:
        raise ValueError('CAS room selected pair index changed.')
    available = {}
    for side, side_layer in (('base', 0), ('alternate', 1)):
        row, before = pair.get(side), original.get(side)
        if (not isinstance(row, dict) or not isinstance(before, dict) or
                set(row) != {'sim_id','index','occult_type','all_occult_types','occult_layer','selected'} or
                set(before) != set(row) or any(row[k] != before[k] for k in row if k != 'selected') or
                row['sim_id'] != baseline['original_sim_id'] or type(row['index']) is not int or row['index'] != index or
                type(row['occult_layer']) is not int or row['occult_layer'] != side_layer or
                type(row['occult_type']) is not int or row['occult_type'] not in owners or
                type(row['all_occult_types']) is not int or row['all_occult_types'] < 0 or
                type(row['selected']) is not bool or row['selected'] != (layer == side_layer) or
                type(before['selected']) is not bool or row['occult_type'] in available):
            raise ValueError('CAS room pair identity, selected layer or captured form changed.')
        available[row['occult_type']] = side_layer
    selected = pair['base' if layer == 0 else 'alternate']
    if (type(native.get('occultLayer')) is not int or native['occultLayer'] != layer or
            type(native.get('occultType')) is not int or native['occultType'] != selected['occult_type'] or
            native.get('allOccultTypes') != selected['all_occult_types'] or
            pair['base']['all_occult_types'] != pair['alternate']['all_occult_types']):
        raise ValueError('CAS room fresh selected form differs from native pair.')
    human_base = pair['base']['occult_type'] == 1
    rows = []
    for form in sorted(owners):
        native_layer = available.get(form)
        rows.append({'form_flags': form, 'label': NAMES.get(form, 'Native form '+str(form)),
            'captured_owner_id': owners[form], 'native_layer': native_layer,
            'selected': form == native['occultType'], 'visible': True,
            'navigation_supported': native_layer is not None and human_base,
            'state': 'native-pair' if native_layer is not None else 'retained-outside-native-pair'})
    return copy.deepcopy({'schema': 1, 'scope': 'captured-cas-room-inventory',
        'runtime_pid': baseline['runtime_pid'], 'sim_id': baseline['original_sim_id'],
        'household_id': baseline['household_id'], 'save_guid': baseline['save_guid'],
        'native_session': obs['session'], 'selected_layer': layer, 'selected_form': native['occultType'],
        'rows': rows, 'all_captured_forms_visible': True, 'all_forms_editable_this_visit': False,
        'membership_modified': False, 'mapping_verified': False, 'alternate_accept_authorized': False,
        'appearance_persistence_verified': False})
