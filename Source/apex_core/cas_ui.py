"""Typed native CAS client requests; UI acknowledgements prove client state.

EA SendUIMessage has only a message name. A short printable ASCII envelope is
delivered as one ordered batch using registered character messages. This avoids
mouse input, process offsets, arbitrary services/evaluation, and network loaders.
"""
from collections import OrderedDict
import copy
import hashlib
import json
import os
import threading
import time
import uuid
from .cas_panels import PANELS, ALIASES
from . import cas_controls

_RECORDS = OrderedDict()
_LOCK = threading.RLock()
_CAPACITY = 64
_CONNECTION = None
_READY = None
_LAST_REPLY = None
_PEERS = {}
_OWNER_BASELINES = OrderedDict()


def _owner_id(value, allow_zero=False, producer=False):
    if producer and type(value) is int:
        value = str(value)
    if (not isinstance(value, str) or not 1 <= len(value) <= 20 or not value.isascii() or not value.isdecimal() or
            str(int(value)) != value or not (0 if allow_zero else 1) <= int(value) < 2 ** 64):
        raise ValueError('Owner observation requires a canonical uint64 identity.')
    return value


def _owner_context(backend, sim):
    """Read producer identities only; never create, restore or ensure wrappers."""
    sim_id = _owner_id(sim.id, producer=True)
    if backend._get_sim_info_by_id(sim_id) is not sim:
        raise ValueError('Original producer Sim is no longer the manager owner.')
    tracker = sim.occult_tracker
    if tracker is None or tracker.sim_info is not sim:
        raise ValueError('Original producer tracker no longer owns this Sim.')
    forms = backend._form_map(tracker)
    if not isinstance(forms, dict) or len(forms) > 32:
        raise ValueError('Original native wrapper inventory is unavailable or exceeds its bound.')
    wrappers, references = [], {}
    for flags, wrapper in forms.items():
        if not isinstance(flags, int) or isinstance(flags, bool) or not 0 < flags < 2 ** 31 or wrapper is None:
            raise ValueError('Original native wrapper lane is untyped or unavailable.')
        wrapper_id = _owner_id(wrapper.id, producer=True)
        wrappers.append({'form_flags': int(flags), 'sim_id': wrapper_id})
        references[int(flags)] = wrapper
    wrappers.sort(key=lambda row: row['form_flags'])
    return ({'runtime_pid': os.getpid(), 'original_sim_id': sim_id,
             'household_id': _owner_id(sim.household_id, producer=True),
             'save_guid': _owner_id(backend.services.get_persistence_service().get_save_slot_proto_guid(), producer=True),
             'wrappers': wrappers}, tracker, references, forms)


def _baseline_hash(baseline):
    return hashlib.sha256(json.dumps(baseline, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode('ascii')).hexdigest()


def capture_original_owner(backend, sim):
    """Capture the actual form-bank producer before native CAS entry.

    The private object references allow later continuity checks. Exported IDs
    are read-only diagnostic evidence, never authority to accept an alternate.
    """
    try:
        context, tracker, wrappers, form_map = _owner_context(backend, sim)
        ids = [row['sim_id'] for row in context['wrappers']]
        complete = len(ids) == len(set(ids)) and context['original_sim_id'] not in ids
        baseline = dict(context, capture_id=uuid.uuid4().hex, complete=complete,
                        error='' if complete else 'Native wrapper identities are ambiguous.')
        key = (context['runtime_pid'], context['save_guid'], context['original_sim_id'])
        with _LOCK:
            _OWNER_BASELINES[key] = {'baseline': baseline, 'sim': sim, 'tracker': tracker,
                                     'wrappers': wrappers, 'form_map': form_map,
                                     'baseline_sha256': _baseline_hash(baseline)}
            _OWNER_BASELINES.move_to_end(key)
            while len(_OWNER_BASELINES) > _CAPACITY:
                _OWNER_BASELINES.popitem(last=False)
    except Exception as exc:
        baseline = {'complete': False, 'error': str(exc)[:256]}
    return {'ok': True, 'original_owner': copy.deepcopy(baseline),
            'mapping_verified': False, 'alternate_accept_authorized': False}


def _owner_record(record, feed=False):
    fields = {'sim_id', 'occult_type', 'all_occult_types', 'occult_layer'}
    fields |= {'index', 'selected'} if feed else {'household_id'}
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError('Native owner record is not a bounded primitive copy.')
    _owner_id(record['sim_id'], allow_zero=feed)
    if not feed:
        _owner_id(record['household_id'])
    for field in ('occult_type', 'all_occult_types', 'occult_layer') + (('index',) if feed else ()):
        if type(record[field]) is not int or not -2 ** 31 <= record[field] < 2 ** 31:
            raise ValueError('Native owner context must retain exact typed integers.')
    if feed and type(record['selected']) is not bool:
        raise ValueError('Native paired selection must retain its boolean type.')
    return record


def owner_pair_diagnostic(client, backend=None):
    """Compare typed native delivery with a privately stored original producer.

    This is observational only. Even a complete exact pair never authorizes
    alternate acceptance or proves durable edits/return to the original owner.
    """
    diagnostic = {'state': 'incomplete', 'pair_relationship_observed': False,
                  'mapping_verified': False, 'alternate_accept_authorized': False}
    try:
        observation = client.get('owner_pair_observation') if isinstance(client, dict) else None
        if observation is None:
            raise ValueError('No owned paired-feed observation was delivered by this native client.')
        if (not isinstance(observation, dict) or observation.get('protocol') != 1 or
                type(observation.get('protocol')) is not int or
                observation.get('scope') != 'native-cas-paired-feed-read-only' or
                type(observation.get('session')) is not int or not 0 < observation['session'] < 2 ** 31):
            raise ValueError('Native paired-feed observation has an invalid session/protocol.')
        for name in ('listener_registered', 'stable', 'complete'):
            if type(observation.get(name)) is not bool:
                raise ValueError('Native paired-feed completeness is untyped.')
        diagnostic.update(native_session=observation['session'], listener_registered=observation['listener_registered'])
        feed = observation.get('feed')
        if not isinstance(feed, dict):
            raise ValueError('Native paired feed is unavailable.')
        if (type(feed.get('sequence')) is not int or not 0 <= feed['sequence'] < 2 ** 31 or
                type(feed.get('delivered')) is not bool or type(feed.get('complete')) is not bool):
            raise ValueError('Native paired feed delivery/sequence is untyped.')
        diagnostic.update(feed_sequence=feed['sequence'], feed_delivered=feed['delivered'])
        if not feed['delivered']:
            raise ValueError('No paired feed delivered after owned listener registration; no refresh was forced.')
        pairs = feed.get('pairs')
        if not isinstance(pairs, list) or not 0 < len(pairs) <= 32:
            raise ValueError('Native paired feed lacks bounded parallel rows.')
        ids = []
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict) or set(pair) != {'index', 'base', 'alternate'} or type(pair['index']) is not int or pair['index'] != index:
                raise ValueError('Native paired feed row position is invalid.')
            for side in ('base', 'alternate'):
                record = _owner_record(pair[side], feed=True)
                if record['sim_id'] != '0': ids.append(record['sim_id'])
        if len(ids) != len(set(ids)):
            raise ValueError('Native paired feed contains ambiguous duplicate Sim identities.')
        index, layer = feed.get('selected_index'), feed.get('selected_layer')
        if type(index) is not int or not 0 <= index < len(pairs) or type(layer) is not int or layer not in (0, 1):
            raise ValueError('Native paired feed selection is missing or unsupported.')
        selected = _owner_record(observation.get('selected'))
        native_sim = client.get('sim', {})
        if (native_sim.get('simId') != selected['sim_id'] or native_sim.get('householdId') != selected['household_id'] or
                any(type(native_sim.get(native)) is not int or native_sim[native] != selected[field]
                    for native, field in (('occultType', 'occult_type'), ('allOccultTypes', 'all_occult_types'), ('occultLayer', 'occult_layer')))):
            raise ValueError('Snapshot and fresh owner observation selected contexts differ.')
        pair = pairs[index]
        chosen = pair['base' if layer == 0 else 'alternate']
        if (chosen['sim_id'] != selected['sim_id'] or chosen['sim_id'] == '0' or
                selected['occult_layer'] != layer or chosen['occult_layer'] != layer or
                any(chosen[field] != selected[field] for field in ('occult_type', 'all_occult_types'))):
            raise ValueError('Fresh selected Sim is not the paired-feed selected identity/context.')
        household = observation.get('household')
        if not isinstance(household, list) or not 0 < len(household) <= 32:
            raise ValueError('Native household getter lacks bounded records.')
        household_ids = []
        for record in household:
            _owner_record(record)
            if record['household_id'] != selected['household_id']:
                raise ValueError('Native household getter belongs to a different household.')
            household_ids.append(record['sim_id'])
        if len(household_ids) != len(set(household_ids)):
            raise ValueError('Native household getter contains duplicate Sim identities.')
        diagnostic.update(selected=copy.deepcopy(selected), selected_index=index, selected_layer=layer,
                          paired_base_id=pair['base']['sim_id'], paired_alternate_id=pair['alternate']['sim_id'],
                          base_in_household=pair['base']['sim_id'] in household_ids,
                          alternate_in_household=pair['alternate']['sim_id'] in household_ids,
                          selected_in_household=selected['sim_id'] in household_ids)
        if (not observation['listener_registered'] or not observation['stable'] or not observation['complete'] or
                not feed['complete'] or observation.get('selected_query') != 'returned-value' or
                observation.get('household_query') != 'returned-value'):
            raise ValueError('Native feed/getter delivery or selection continuity is incomplete.')
        if backend is None:
            raise ValueError('Original producer continuity requires an owner-thread backend read.')
        key = (os.getpid(), _owner_id(backend.services.get_persistence_service().get_save_slot_proto_guid(), producer=True), pair['base']['sim_id'])
        with _LOCK:
            stored = _OWNER_BASELINES.get(key)
            if stored is None:
                raise ValueError('No exact original producer baseline matches this native paired base.')
            baseline = stored['baseline']
            diagnostic['original_owner'] = copy.deepcopy(baseline)
            current, tracker, wrappers, form_map = _owner_context(backend, stored['sim'])
            expected = {name: baseline[name] for name in current}
            if (not baseline['complete'] or current != expected or tracker is not stored['tracker'] or form_map is not stored['form_map'] or
                    set(wrappers) != set(stored['wrappers']) or any(wrappers[flags] is not stored['wrappers'][flags] for flags in wrappers)):
                raise ValueError('Original producer/tracker/wrapper identities changed after baseline capture.')
            if selected['household_id'] != baseline['household_id'] or not diagnostic['base_in_household']:
                raise ValueError('Native paired base lacks original household membership.')
            matching = [row['form_flags'] for row in baseline['wrappers'] if row['sim_id'] == pair['alternate']['sim_id']]
            diagnostic['alternate_wrapper_flags'] = matching
            if len(matching) != 1:
                raise ValueError('Native paired alternate does not identify exactly one original native wrapper.')
        diagnostic.update(state='observed-pair-only', pair_relationship_observed=True, error='')
    except Exception as exc:
        diagnostic['error'] = str(exc)[:256]
    return diagnostic



def _form_select_original(backend, sim_id, household_id):
    """Bind navigation to the original producer without asserting wrapper mapping."""
    if backend is None:
        raise ValueError('CAS form selection requires the owner-thread original producer context.')
    current_zone = getattr(backend.services, 'current_zone', None)
    unloaded = (backend._get_sim_info_by_id(sim_id) is None and callable(current_zone)
                and current_zone() is None)
    if unloaded:
        # The Live C++ producer can be disposed even while its Python object
        # remains strongly held. Never dereference it during native CAS.
        # This is a captured identity capability plus fresh native CAS pair
        # binding, for navigation only; not current producer or write proof.
        candidates = [(key, value) for key, value in _OWNER_BASELINES.items()
            if key[0] == os.getpid() and key[2] == sim_id and
            value['baseline'].get('household_id') == household_id]
        if len(candidates) != 1:
            raise ValueError('Detached CAS navigation requires one unambiguous original capture.')
        key, stored = candidates[0]
        baseline = stored['baseline']
        if (baseline.get('complete') is not True or
                baseline.get('runtime_pid') != key[0] or baseline.get('save_guid') != key[1] or
                baseline.get('original_sim_id') != key[2] or
                stored.get('baseline_sha256') != _baseline_hash(baseline)):
            raise ValueError('Captured CAS navigation identity changed; no selection authorized.')
        return copy.deepcopy(baseline)
    else:
        guid = _owner_id(backend.services.get_persistence_service().get_save_slot_proto_guid(), producer=True)
        stored = _OWNER_BASELINES.get((os.getpid(), guid, sim_id))
    if stored is None:
        raise ValueError('CAS form selection lacks an exact original producer baseline; no selection sent.')
    baseline = stored['baseline']
    current, tracker, wrappers, form_map = _owner_context(backend, stored['sim'])
    if (not baseline['complete'] or current != {name: baseline[name] for name in current} or
            tracker is not stored['tracker'] or form_map is not stored['form_map'] or
            set(wrappers) != set(stored['wrappers']) or
            any(wrappers[flags] is not stored['wrappers'][flags] for flags in wrappers) or
            current['household_id'] != household_id):
        raise ValueError('CAS form selection original producer/household continuity changed; no selection authorized.')
    return copy.deepcopy(baseline)


def form_selection_binding(client, sim_id, request, resulting=False):
    """Validate a same-original-ID native pair for selection only, never acceptance.

    The household getter may lack household/layer fields. Its primitive rows are
    not filled or used as authority; the fresh selected Sim and original producer
    provide the exact household binding. Raw and retained selector rows must agree.
    """
    native = client.get('sim') if isinstance(client, dict) else None
    observation = client.get('owner_pair_observation') if isinstance(client, dict) else None
    if not isinstance(native, dict) or not isinstance(observation, dict):
        raise ValueError('CAS form selection requires a fresh selected Sim and owned selector feed.')
    if (type(observation.get('protocol')) is not int or observation['protocol'] != 1 or
            observation.get('scope') != 'native-cas-paired-feed-read-only' or
            type(observation.get('session')) is not int or observation['session'] != request['native_session'] or
            observation.get('stable') is not True or observation.get('selected_query') != 'returned-value'):
        raise ValueError('CAS form selection native session/selected observation is stale or incomplete.')
    selected = _owner_record(observation.get('selected'))
    expected_layer = selected['occult_layer'] if resulting else request['expected_layer']
    if (selected['sim_id'] != sim_id or selected['household_id'] != request['household_id'] or
            expected_layer not in (0, 1) or
            selected['occult_layer'] != expected_layer or
            native.get('simId') != sim_id or native.get('householdId') != request['household_id'] or
            any(type(native.get(key)) is not int or native[key] != selected[field] for key, field in
                (('occultType', 'occult_type'), ('allOccultTypes', 'all_occult_types'), ('occultLayer', 'occult_layer')))):
        raise ValueError('CAS form selection selected Sim/household/current layer differs from the bound request.')
    context = client.get('native_context')
    if (not isinstance(context, dict) or any(not isinstance(context.get(name), dict) or
            context[name].get('query') != 'returned-value' for name in
            ('edit_mode', 'new_family', 'entered_from_play_area')) or
            type(context['edit_mode'].get('value')) is not int or context['edit_mode']['value'] not in (0, 7) or
            context['new_family'].get('value') is not False or
            not isinstance(context['entered_from_play_area'].get('value'), dict) or
            context['entered_from_play_area']['value'].get('result') is not True):
        raise ValueError('CAS form selection requires existing-household mode 0 or single-Sim mode 7, an existing family and explicit entry from Live.')
    selector = observation.get('selector_feed')
    if (observation.get('selector_query') != 'returned-value' or not isinstance(selector, dict) or
            type(selector.get('protocol')) is not int or selector['protocol'] != 1 or
            selector.get('scope') != 'native-selector-owner-pair-view' or
            selector.get('service_registered') is not True or selector.get('reset_listener_registered') is not True or
            selector.get('mapping_verified') is not False or selector.get('alternate_accept_authorized') is not False):
        raise ValueError('CAS form selection requires the registered read-only selector service.')
    raw, retained = selector.get('raw_feed'), selector.get('retained')
    if (not isinstance(raw, dict) or raw.get('source') != 'native-selector-raw-entry-observer' or
            raw.get('before_native_handler') is not True or raw.get('delivered') is not True or
            raw.get('complete') is not True or type(raw.get('sequence')) is not int or not 0 < raw['sequence'] < 2**31 or
            not isinstance(retained, dict) or retained.get('source') != 'native-selector-retained-filtered-feed' or
            retained.get('available') is not True or retained.get('complete') is not True):
        raise ValueError('CAS form selection raw/retained paired delivery is unavailable or incomplete.')
    raw_pairs, pairs = raw.get('pairs'), retained.get('pairs')
    if (not isinstance(raw_pairs, list) or not isinstance(pairs, list) or not 0 < len(pairs) <= 32 or
            len(raw_pairs) != len(pairs) or type(raw.get('base_row_count')) is not int or
            type(raw.get('alternate_row_count')) is not int or raw['base_row_count'] != len(pairs) or
            raw['alternate_row_count'] != len(pairs)):
        raise ValueError('CAS form selection requires exact bounded parallel rows.')
    index = retained.get('selected_index')
    if (type(index) is not int or not 0 <= index < len(pairs) or raw.get('selected_index') != index or
            type(raw.get('selected_index')) is not int or type(raw.get('selected_layer')) is not int or
            raw['selected_layer'] not in (0, 1) or type(retained.get('selected_layer')) is not int or
            retained['selected_layer'] != expected_layer or retained.get('selected_sim_id') != sim_id):
        raise ValueError('CAS form selection retained index/current layer differs; no other Sim may be selected.')
    projections, original_indexes = [], []
    for position, (raw_pair, pair) in enumerate(zip(raw_pairs, pairs)):
        if any(not isinstance(row, dict) or set(row) != {'index', 'base', 'alternate'} or
                type(row['index']) is not int or row['index'] != position for row in (raw_pair, pair)):
            raise ValueError('CAS form selection paired positions are invalid.')
        copied = {'index': position}
        for side, layer in (('base', 0), ('alternate', 1)):
            row, original = _owner_record(pair[side], feed=True), _owner_record(raw_pair[side], feed=True)
            if (row['sim_id'] == '0' or row['index'] != position or row['occult_layer'] != layer or
                    any(row[key] != original[key] for key in row if key != 'selected')):
                raise ValueError('CAS form selection raw/retained identity or layer changed.')
            copied[side] = {key: row[key] for key in row if key != 'selected'}
        projections.append(copied)
        if any(pair[side]['sim_id'] == sim_id for side in ('base', 'alternate')):
            original_indexes.append(position)
    pair = pairs[index]
    base, alternate = pair['base'], pair['alternate']
    pair_kinds = {base['occult_type'], alternate['occult_type']}
    nonhuman = pair_kinds - {1}
    if (original_indexes != [index] or base['sim_id'] != sim_id or alternate['sim_id'] != sim_id or
            len(pair_kinds) != 2 or 1 not in pair_kinds or not nonhuman.issubset({2, 4, 8, 16, 32, 64}) or
            base['all_occult_types'] != alternate['all_occult_types'] or base['all_occult_types'] < 0 or
            any(not base['all_occult_types'] & kind for kind in pair_kinds)):
        raise ValueError('CAS form selection requires one observed same-original-ID base/alternate pair; wrapper ownership is unproved.')
    chosen = pair['base' if expected_layer == 0 else 'alternate']
    if (chosen['selected'] is not True or pair['alternate' if expected_layer == 0 else 'base']['selected'] is not False or
            any(chosen[field] != selected[field] for field in ('occult_type', 'all_occult_types', 'occult_layer'))):
        raise ValueError('CAS form selection fresh native selection does not match its retained pair.')
    targets = [layer for layer, side in ((0, 'base'), (1, 'alternate'))
               if pair[side]['occult_type'] == request['form_flags']]
    if len(targets) != 1:
        raise ValueError('Requested form is not the actual observed base/alternate; no selection authorized.')
    target_layer = targets[0]
    if resulting and expected_layer != target_layer:
        raise ValueError('CAS form selection did not reach the actual observed target layer.')
    return {'native_session': observation['session'], 'sim_id': sim_id, 'household_id': selected['household_id'],
            'selected_index': index, 'selected_layer': expected_layer, 'target_layer': target_layer,
            'form_flags': request['form_flags'], 'feed_sequence': raw['sequence'],
            'pair': projections[index]}

def attach_client(sim_id, clock=time.monotonic):
    global _READY
    if not isinstance(sim_id, str) or not sim_id.isdigit() or not 0 < int(sim_id) < 2 ** 64:
        raise ValueError('Native CAS must identify its exact selected Sim.')
    token = uuid.uuid4().hex + uuid.uuid4().hex
    with _LOCK:
        if len(_PEERS) >= 4:
            raise ValueError('Native CAS peer limit reached.')
        _PEERS[token] = {'sim_id': sim_id, 'observed_at': clock()}
        _READY = {'protocol': 1, 'transport': 'loopback-socket', 'sim_id': sim_id,
                  'observed_at': clock()}
    return token


def detach_client(token):
    with _LOCK:
        _PEERS.pop(token, None)


def poll_client(token, clock=time.monotonic):
    with _LOCK:
        peer = _PEERS.get(token)
        if peer is None:
            raise ValueError('Native CAS peer is not bound.')
        peer['observed_at'] = clock()
        for row in _RECORDS.values():
            if row['state'] == 'pending' and row.get('transport') == 'loopback-socket' and row['sim_id'] == peer['sim_id'] and row.get('delivery') == 'queued':
                row.update(delivery='claimed', peer=token)
                return row['wire']
    return None


def receive_socket(token, request_id, payload, clock=time.monotonic, backend=None):
    with _LOCK:
        peer, row = _PEERS.get(token), _RECORDS.get(request_id)
        if peer is None or row is None or row.get('peer') != token or peer['sim_id'] != row['sim_id']:
            raise ValueError('CAS acknowledgement does not match its claimed peer/Sim/request.')
        prior_state = row['state']
        receive(request_id, payload, backend=backend)
        if prior_state == 'pending' and row['state'] == 'completed':
            row['acknowledged_at'] = clock()
        # A complete validated ACK is fresh traffic from the exact claimed
        # peer, even when its native readback took longer than an idle poll.
        # Refused payloads must not renew a peer's authority/freshness.
        peer['observed_at'] = clock()
    return {'ok': True, 'acknowledgement_accepted': True, 'cas_request_id': request_id,
            'ui_transition_verified': row['request']['operation'] != 'accept' and bool(row['result'].get('ok'))}


def observe_connection(connection):
    global _CONNECTION
    if connection is not None: _CONNECTION = connection


def connection_matches(connection):
    return _CONNECTION is not None and connection == _CONNECTION


def observe_ready(protocol, connection, clock=time.monotonic):
    """Read-only startup signal, separate from a request/state acknowledgement."""
    global _READY
    if type(protocol) is not int or protocol != 1:
        raise ValueError('Unsupported native CAS startup protocol.')
    _READY = {'protocol': protocol, 'connection': None if connection is None else str(connection),
              'observed_at': clock()}


def reply_connection_allowed(request_id, connection):
    # PostServerCommand can originate from the native client without a server
    # connection argument. Only an existing unpredictable request can use that
    # path; receive still validates the complete selected-Sim client readback.
    with _LOCK:
        return (connection_matches(connection) or
                (connection is None and request_id in _RECORDS))


def observe_reply(request_id, connection, accepted):
    global _LAST_REPLY
    _LAST_REPLY = {'cas_request_id': request_id, 'connection': None if connection is None else str(connection),
                   'connection_accepted': bool(accepted)}


def diagnostics():
    with _LOCK:
        rows = [{'cas_request_id': key, 'state': row['state'], 'operation': row['request']['operation'],
                 'age_seconds': max(0, time.monotonic() - row['created'])} for key, row in _RECORDS.items()]
        result = {'ok': True, 'native_initializer_observed': _READY is not None,
                  'ready': copy.deepcopy(_READY), 'last_reply': copy.deepcopy(_LAST_REPLY),
                  'observed_connection': None if _CONNECTION is None else str(_CONNECTION), 'requests': rows,
                  'ui_transition_verified': False}
        result['native_peers'] = [{'sim_id': peer['sim_id'], 'age_seconds': max(0, time.monotonic() - peer['observed_at'])} for peer in _PEERS.values()]
    from .cas_socket import status as socket_status
    result['socket_transport'] = socket_status()
    result['socket_transport']['native_connection_verified'] = any(peer['age_seconds'] <= 3 for peer in result['native_peers'])
    try:
        from distributor.system import Distributor
        distributor = Distributor.instance()
        result.update(distributor_client_available=distributor.client is not None,
                      queued_operations=len(distributor.journal.entries))
    except Exception as exc:
        result['transport_diagnostic_error'] = str(exc)
    return result


def history_state(client):
    """Compare native data rather than incidental CAS navigation changes.

    Raw snapshots are retained in full. This projection only defines what can
    count as evidence for a history mutation, not which fields are captured.
    Selected outfit, visibility, query status and menu state do not prove an
    appearance edit. Slot existence can prove native outfit creation/removal.
    """
    catalogs = {row['panel']: {'items': row['items'], 'preset': row['preset']}
                for row in client['catalogs']}
    slots = []
    planned = client.get('planned_outfits')
    if isinstance(planned, list):
        for row in planned:
            if not isinstance(row, dict) or type(row.get('category')) is not int:
                continue
            data = row.get('data')
            if not isinstance(data, dict) or not isinstance(data.get('outfit_list'), list):
                continue
            entries = data['outfit_list']
            if any(not isinstance(item, dict) or type(item.get('outfit_type')) is not int or
                   type(item.get('outfit_index')) is not int for item in entries):
                continue
            slots.append({'category': row['category'], 'slots': sorted(
                (item['outfit_type'], item['outfit_index']) for item in entries)})
    projection = {'sim': client['sim'], 'catalogs': catalogs,
                  'hair_selected_swatch_id': client.get('hair_selected_swatch_id'),
                  'slot_inventory': sorted(slots, key=lambda row: row['category'])}
    return json.dumps(projection, sort_keys=True, separators=(',', ':'), allow_nan=False)


def validate_client(client, sim_id, request):
    if not isinstance(client, dict) or client.get('scope') != 'native-cas-client' or not isinstance(client.get('sim'), dict) or str(client['sim'].get('simId')) != sim_id:
        raise ValueError('CAS response belongs to another selected Sim.')
    slot = client.get('outfit')
    if (type(client.get('menu_state')) is not int or not -2 ** 31 <= client['menu_state'] < 2 ** 31 or
            type(client.get('panel_visible')) is not bool or not isinstance(slot, dict) or
            type(slot.get('outfit_type')) is not int or not 0 <= slot['outfit_type'] <= 255 or
            type(slot.get('outfit_index')) is not int or not 0 <= slot['outfit_index'] < 5):
        raise ValueError('CAS snapshot lacks its typed menu visibility and outfit identity.')
    catalogs = client.get('catalogs')
    if not isinstance(catalogs, list) or len(catalogs) != len(PANELS):
        raise ValueError('CAS inventory must include every mapped panel, including empty/unsupported panels.')
    names = set()
    for catalog in catalogs:
        if not isinstance(catalog, dict) or catalog.get('panel') not in PANELS or catalog['panel'] in names or type(catalog.get('menu_state')) is not int or catalog['menu_state'] != PANELS[catalog['panel']]:
            raise ValueError('CAS inventory panel identity differs.')
        names.add(catalog['panel'])
        supported, items = catalog.get('supported'), catalog.get('items')
        if type(supported) is not bool or (supported and (not isinstance(items, list) or len(items) > 1024 or any(not isinstance(item, dict) for item in items))) or (not supported and items is not None):
            raise ValueError('CAS inventory must distinguish unknown panels from empty panels.')
        preset_query, preset = catalog.get('preset_query'), catalog.get('preset')
        if preset_query not in ('returned-value', 'returned-null', 'failed', 'not-applicable') or (
                (preset_query == 'returned-value' and not isinstance(preset, dict)) or
                (preset_query != 'returned-value' and preset is not None)):
            raise ValueError('CAS preset query must distinguish a returned record from null or failed discovery.')
    validate_catalog_metadata(client)
    operation = request['operation']
    if operation in ({'panel', 'select'} | cas_controls.PANEL_OPERATIONS) and (type(client.get('menu_state')) is not int or client['menu_state'] != panel(request['panel']) or client.get('panel_visible') is not True):
        raise ValueError('Native panel visibility/state did not match the request.')
    if operation == 'outfit':
        slot = client.get('outfit')
        if not isinstance(slot, dict) or any(type(slot.get(key)) is not int or slot[key] != request[value] for key, value in (('outfit_type', 'category'), ('outfit_index', 'index'))):
            raise ValueError('Native outfit readback did not match the request.')
    if operation == 'outfit-add':
        created = client.get('outfit_created')
        if (not isinstance(created, dict) or type(created.get('before_count')) is not int or
                type(created.get('after_count')) is not int or not 0 <= created['before_count'] < 5 or
                created['after_count'] != created['before_count'] + 1 or
                slot['outfit_type'] != request['category'] or slot['outfit_index'] != created['before_count']):
            raise ValueError('Native CAS outfit creation did not verify exactly one appended slot.')
    if operation == 'hair-swatch' and client.get('hair_selected_swatch_id') != request['data_id']:
        raise ValueError('Native hair swatch did not match the exact selected identity.')
    if operation == 'select' and not any(isinstance(item, dict) and str(item.get('dataID')) == request['data_id'] for item in client.get('selected') or []):
        raise ValueError('Native selected item did not match the request.')
    if operation == 'form-select':
        form_selection_binding(client, sim_id, request, resulting=True)
    if operation in cas_controls.OPERATIONS:
        cas_controls.validate(client, request)
    if operation == 'accept':
        validate_accept_context(client)
        if client['sim']['householdId'] != request.get('household_id'):
            raise ValueError('CAS accept household differs from its bound original request.')


def validate_catalog_metadata(client):
    """Optional native catalog annotations never replace raw equipped records."""
    if 'catalog_metadata' not in client:
        return
    rows = client['catalog_metadata']
    if (not isinstance(rows, list) or len(rows) > 128 or
            type(client.get('catalog_metadata_complete')) is not bool or
            client.get('catalog_metadata_scope') != 'native-catalog-identities-only'):
        raise ValueError('Native catalog annotations lack bounded typed coverage.')
    equipped = {item.get('dataID') for catalog in client['catalogs'] for item in catalog['items'] or []
                if isinstance(item.get('dataID'), str)}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Native catalog annotation is not a record.')
        identity = row.get('data_id')
        if (not isinstance(identity, str) or identity not in equipped or identity in seen or
                not identity.isascii() or not identity.isdecimal() or
                not 0 < int(identity) < 2**64 or str(int(identity)) != identity or
                row.get('source') != 'native:GetCatalogItem' or row.get('name_source') != 'native:LocKey' or
                row.get('image_source') != 'native:GetCatalogItem.image'):
            raise ValueError('Native catalog annotation does not bind an exact equipped identity/source.')
        seen.add(identity)
        query, name_query, name = row.get('query'), row.get('name_query'), row.get('name')
        if query not in ('returned-value', 'returned-null', 'failed') or name_query not in (
                'localized-title', 'empty-title', 'failed', 'unavailable'):
            raise ValueError('Native catalog annotation lacks explicit query state.')
        if name_query == 'localized-title':
            if query != 'returned-value' or not isinstance(name, str) or not 0 < len(name) <= 2048:
                raise ValueError('A resolved catalog name must be genuine bounded localized text.')
        elif name is not None:
            raise ValueError('Unresolved native catalog names cannot masquerade as resolved text.')
        image, image_query = row.get('native_image_uri'), row.get('image_query')
        if image_query == 'native-uri':
            if query != 'returned-value' or not isinstance(image, str) or not 0 < len(image) <= 512:
                raise ValueError('Native catalog image URI is unavailable or unbounded.')
        elif image_query != 'not-returned' or image is not None:
            raise ValueError('Native image annotations must distinguish virtual URI from unavailable pixels.')
        raw = row.get('raw_json')
        if query == 'returned-value':
            if not isinstance(raw, str) or len(raw) > 65536:
                raise ValueError('Native product raw metadata exceeds its bound.')
            try:
                decoded = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            except (ValueError, TypeError) as exc:
                raise ValueError('Native product metadata is not complete JSON.') from exc
            if not isinstance(decoded, dict):
                raise ValueError('Native product metadata is not a complete record.')
        elif raw is not None:
            raise ValueError('Failed native product queries cannot retain a partial raw record.')


def validate_accept_context(client):
    """Only the observed existing-Sim editor entered from Live may commit.

    Native service values retain their real shapes. In particular a raw Sim's
    isNew field is not the household's CasIsNewFamily result, and an Object is
    not itself evidence that its result field is true.
    """
    context = client.get('native_context')
    if not isinstance(context, dict):
        raise ValueError('CAS accept lacks native edit context.')
    for name in ('edit_mode', 'new_family', 'entered_from_play_area'):
        record = context.get(name)
        if not isinstance(record, dict) or record.get('query') != 'returned-value':
            raise ValueError('CAS accept context query was not returned: ' + name)
    mode = context['edit_mode'].get('value')
    family = context['new_family'].get('value')
    area = context['entered_from_play_area'].get('value')
    if (type(mode) is not int or mode not in (0, 7) or family is not False or
            not isinstance(area, dict) or area.get('result') is not True):
        raise ValueError('CAS accept requires existing-household mode 0 or single-Sim mode 7, an existing family, and explicit entry from Live.')
    sim = client.get('sim')
    if not isinstance(sim, dict) or type(sim.get('occultLayer')) is not int or sim['occultLayer'] != 0:
        raise ValueError('CAS accept requires exact primary occult layer 0.')
    household_id = client['sim'].get('householdId')
    if (not isinstance(household_id, str) or not household_id.isascii() or not household_id.isdecimal() or
            not 0 < int(household_id) < 1 << 64 or str(int(household_id)) != household_id):
        raise ValueError('CAS accept lacks the exact original native household identity.')


def panel(value):
    name = ALIASES.get(value, value)
    if name not in PANELS: raise ValueError('Use a named installed CAS panel; run cas panels.')
    return PANELS[name]


def envelope(sim_id, request):
    if not isinstance(sim_id, str) or not sim_id.isdigit() or not 0 < int(sim_id) < 2 ** 64:
        raise ValueError('Choose an explicit CAS Sim identity.')
    if not isinstance(request, dict): raise ValueError('Use a typed CAS request.')
    op = request.get('operation')
    if op in cas_controls.OPERATIONS:
        state, category, index, value = cas_controls.wire(request, panel)
        request_id = uuid.uuid4().hex
        wire = '|'.join(map(str, (request_id, sim_id, op, state, category, index, value)))
        if len(wire) > 512 or any(not 32 <= ord(c) <= 126 for c in wire):
            raise ValueError('CAS envelope exceeds its printable transport bound.')
        return request_id, wire
    allowed = {'status': {'operation'}, 'panel': {'operation', 'panel'},
        'outfit': {'operation', 'category', 'index'},
        'outfit-add': {'operation', 'category'}, 'hair-swatch': {'operation', 'data_id'},
        'select': {'operation', 'panel', 'data_id'}, 'undo': {'operation'}, 'redo': {'operation'},
        'accept': {'operation', 'household_id'},
        'form-select': {'operation', 'household_id', 'expected_layer', 'form_flags', 'native_session'}}
    if op not in allowed or set(request) != allowed[op]: raise ValueError('Unsupported or incomplete CAS request.')
    state = panel(request['panel']) if 'panel' in request else 0
    if op == 'select':
        name = ALIASES.get(request['panel'], request['panel'])
        if (name.startswith('profile_') and name not in cas_controls.PART_PROFILE_PANELS or name in ('clothing_looks', 'clothing_head_tattoos', 'clothing_body_tattoos')):
            raise ValueError('Use the typed preset, swatch or select-layer command for this panel.')
    if op == 'form-select':
        _owner_id(sim_id)
        _owner_id(request['household_id'])
        if (type(request['expected_layer']) is not int or request['expected_layer'] not in (0, 1) or
                type(request['form_flags']) is not int or request['form_flags'] not in (1, 2, 4, 8, 16, 32, 64) or
                type(request['native_session']) is not int or not 0 < request['native_session'] < 2**31):
            raise ValueError('CAS form selection requires an exact current layer, requested form and native session.')
        request_id = uuid.uuid4().hex
        wire = '|'.join(map(str, (request_id, sim_id, op, request['form_flags'],
                                 request['expected_layer'], request['native_session'], request['household_id'])))
        return request_id, wire
    category, index = request.get('category', 0), request.get('index', 0)
    if type(category) is not int or not 0 <= category <= 255 or type(index) is not int or not 0 <= index < 5:
        raise ValueError('CAS outfit category/index is out of range.')
    value = request.get('data_id', '')
    if op == 'accept':
        value = request['household_id']
        if (not isinstance(value, str) or not value.isascii() or not value.isdecimal() or
                not 0 < int(value) < 1 << 64 or str(int(value)) != value):
            raise ValueError('CAS accept requires the exact original household identity before delivery.')
    if op == 'outfit-add' and category > 13:
        raise ValueError('Only installed native CAS outfit categories may be appended.')
    if op in ('select', 'hair-swatch') and (not isinstance(value, str) or not value.isdigit() or not 0 < int(value) < 2 ** 64):
        raise ValueError('Native CAS data_id must be an exact decimal resource identity.')
    request_id = uuid.uuid4().hex
    wire = '|'.join(map(str, (request_id, sim_id, op, state, category, index, value)))
    if len(wire) > 512 or any(not 32 <= ord(c) <= 126 for c in wire): raise ValueError('CAS envelope exceeds its limit.')
    return request_id, wire


def submit(sim_id, request, send=None, clock=time.monotonic, backend=None):
    request_id, wire = envelope(sim_id, request)
    with _LOCK:
        socket_ready = send is None and any(peer['sim_id'] == sim_id and clock() - peer['observed_at'] <= 3 for peer in _PEERS.values())
    form_select_context = None
    if request['operation'] == 'form-select':
        if not socket_ready:
            raise ValueError('CAS form selection requires a fresh exact-Sim socket peer; no request sent.')
        with _LOCK:
            original = _form_select_original(backend, sim_id, request['household_id'])
            fresh_peers = {token for token, peer in _PEERS.items()
                           if peer['sim_id'] == sim_id and 0 <= clock() - peer['observed_at'] <= 3}
            prior = next((row for row in reversed(list(_RECORDS.values())) if
                          row['state'] == 'completed' and row.get('peer') in fresh_peers and
                          row['sim_id'] == sim_id and row.get('acknowledged_at') is not None and
                          0 <= clock() - row['acknowledged_at'] <= 3 and row['result'].get('ok')), None)
            if prior is None:
                raise ValueError('CAS form selection requires a fresh owned native acknowledgement; request status first.')
            form_select_context = {'original': original,
                                   'before': form_selection_binding(prior['result'].get('client'), sim_id, request)}
    if request['operation'] == 'accept' and not socket_ready:
        raise ValueError('CAS accept requires a fresh exact-Sim socket peer; no request sent.')
    if send is None and not socket_ready:
        from distributor.ops import SendUIMessage
        from distributor.system import Distributor
        distributor = Distributor.instance()
        # The installed method silently drops operations when client is None.
        # Refuse before creating a pending record or sending part of an envelope.
        if distributor.client is None:
            raise ValueError('Native UI transport has no distributor client; no CAS request sent.')
        send = lambda name: distributor.add_op_with_no_owner(SendUIMessage(name))
    with _LOCK:
        # A lost client acknowledgement cannot permit another mutation.
        pending = [row for row in _RECORDS.values() if row['state'] in ('pending', 'accept-intent', 'accept-unresolved', 'form-select-unresolved')]
        if pending and request['operation'] == 'status' and all(
                row['request']['operation'] == 'status' and clock() - row['created'] >= 10 for row in pending):
            # Reading again cannot replay a mutation. Retain the prior identity
            # and allow a late reply to resolve that old read independently.
            for row in pending: row['state'] = 'superseded-read'
            pending = []
        if pending:
            raise ValueError('A CAS client request is unresolved; inspect its request ID before another operation.')
        _RECORDS[request_id] = {'state': 'pending', 'sim_id': sim_id, 'request': copy.deepcopy(request),
                              'created': clock(), 'result': None, 'wire': wire,
                              'transport': 'loopback-socket' if socket_ready else 'game-ui-message', 'delivery': 'queued'}
        if form_select_context is not None:
            _RECORDS[request_id]['form_select_context'] = form_select_context
        while len(_RECORDS) > _CAPACITY: _RECORDS.popitem(last=False)
    try:
        if not socket_ready:
            for name in ['ApexCAS.Begin'] + ['ApexCAS.Char.' + str(ord(c)) for c in wire] + ['ApexCAS.End']:
                send(name)
    except Exception:
        # Partial delivery is unresolved, never silently replayed.
        raise
    return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': request_id,
            'ui_transition_verified': False, 'input_submitted': False,
            'message': 'Semantic request submitted. Await the native CAS client acknowledgement; do not repeat.'}


def receive(request_id, payload, backend=None):
    """Retain every rejected native success while keeping its claim blocked."""
    try:
        return _receive(request_id, payload, backend)
    except (ValueError, KeyError, TypeError) as error:
        if isinstance(payload, str) and len(payload.encode('utf-8')) <= 131072:
            try:
                data = json.loads(payload)
            except (ValueError, TypeError):
                data = None
            if (isinstance(data, dict) and type(data.get('protocol')) is int and data['protocol'] == 1 and
                    data.get('cas_request_id') == request_id and data.get('ok') is True):
                with _LOCK:
                    row = _RECORDS.get(request_id)
                    if row and row['state'] == 'pending' and row['request']['operation'] != 'accept':
                        row['rejected_acknowledgement'] = copy.deepcopy(data)
                        row['acknowledgement_validation_error'] = str(error)
        raise


def _receive(request_id, payload, backend=None):
    if not isinstance(payload, str) or len(payload.encode('utf-8')) > 131072:
        raise ValueError('CAS client response exceeds its UTF-8 byte bound.')
    data = json.loads(payload)
    if not isinstance(data, dict) or type(data.get('protocol')) is not int or data['protocol'] != 1 or type(data.get('ok')) is not bool or data.get('cas_request_id') != request_id:
        raise ValueError('CAS client response identity/protocol differs.')
    with _LOCK:
        row = _RECORDS.get(request_id)
        if row is None: raise ValueError('Unsolicited CAS client response.')
        if row['request']['operation'] == 'accept':
            if row['result'] == data or row.get('accept_intent') == data:
                return  # A duplicate same-nonce intent cannot submit again.
            if row['state'] not in ('pending', 'accept-intent', 'accept-unresolved'):
                raise ValueError('CAS accept acknowledgement changed after its terminal result.')
            if data.get('ok'):
                if row['state'] != 'pending':
                    raise ValueError('CAS accept intent acknowledgement changed.')
                if data.get('lifecycle_stage') != 'accept-intent' or data.get('commit_submitted') is not False:
                    raise ValueError('CAS accept may acknowledge only a precommit intent, not Live success.')
                validate_client(data.get('client'), row['sim_id'], row['request'])
                row['owner_pair_diagnostic'] = owner_pair_diagnostic(data.get('client'), backend)
                row.update(state='accept-intent', result=copy.deepcopy(data))
                return
            unresolved = (data.get('commit_attempted') is True and 'commit_accepted' in data and
                          data['commit_accepted'] is None and data.get('commit_outcome') == 'unresolved')
            if (data.get('lifecycle_stage') != 'accept-result' or data.get('commit_submitted') is not False or
                    type(data.get('commit_attempted')) is not bool or
                    (data['commit_attempted'] and data.get('commit_accepted') is not False and not unresolved)):
                raise ValueError('CAS accept failure lacks an explicit native commit outcome.')
            if row['state'] == 'accept-unresolved':
                raise ValueError('An unresolved native commit cannot be replaced by a different acknowledgement.')
            if unresolved and row['state'] != 'accept-intent':
                raise ValueError('An unresolved native commit requires its original prepared intent.')
            # Preserve the original precommit receipt when native preconditions
            # change or SaveAndExitCAS explicitly refuses the one attempt.
            if row['state'] == 'accept-intent':
                row['accept_intent'] = copy.deepcopy(row['result'])
            row.update(state='accept-unresolved' if unresolved else 'failed', result=copy.deepcopy(data))
            return
        if row['state'] not in ('pending', 'superseded-read'):
            if row['result'] != data: raise ValueError('CAS request acknowledgement changed.')
            return
        if data.get('ok'):
            client = data.get('client')
            validate_client(client, row['sim_id'], row['request'])
            if row['request']['operation'] in ('undo', 'redo'):
                before_json = data.get('history_before_json')
                if not isinstance(before_json, str) or not 0 < len(before_json.encode('utf-8')) <= 131072:
                    raise ValueError('Native history acknowledgement lacks its complete pre-state.')
                before = json.loads(before_json)
                validate_client(before, row['sim_id'], {'operation': 'status'})
                if history_state(before) == history_state(client):
                    raise ValueError('Native history changed only navigation/metadata; no Sim or equipped data change verified.')
            if row['request']['operation'] == 'form-select':
                stored = row['form_select_context']
                if _form_select_original(backend, row['sim_id'], row['request']['household_id']) != stored['original']:
                    raise ValueError('CAS form selection original capture changed before readback.')
                after = form_selection_binding(client, row['sim_id'], row['request'], resulting=True)
                before = stored['before']
                if (any(after[key] != before[key] for key in ('native_session', 'sim_id', 'household_id', 'selected_index', 'target_layer', 'form_flags', 'pair')) or
                        after['feed_sequence'] < before['feed_sequence']):
                    raise ValueError('CAS form selection pair/session changed before readback.')
                receipt = data.get('form_selection')
                if (not isinstance(receipt, dict) or receipt.get('selection_verified') is not True or
                        receipt.get('mapping_verified') is not False or receipt.get('alternate_accept_authorized') is not False or
                        receipt.get('expected_layer') != before['selected_layer'] or type(receipt.get('expected_layer')) is not int or
                        receipt.get('selection_changed') is not (before['selected_layer'] != after['selected_layer']) or
                        any(type(receipt.get(key)) is not type(after[key]) or receipt[key] != after[key]
                            for key in ('native_session', 'sim_id', 'household_id', 'selected_index', 'target_layer', 'form_flags'))):
                    raise ValueError('CAS form selection lacks its exact typed native postcondition receipt.')
            row['owner_pair_diagnostic'] = owner_pair_diagnostic(client, backend)
            try:
                from .cas_room import inventory
                baseline = _form_select_original(backend, row['sim_id'], client['sim']['householdId'])
                row['cas_room'] = inventory(baseline, client)
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                row['cas_room'] = {'schema': 1, 'available': False, 'error': str(error)[:256]}
        unresolved_selection = (row['request']['operation'] == 'form-select' and not data.get('ok') and
                                data.get('mutation_started') is True)
        row.update(state='completed' if data.get('ok') else 'form-select-unresolved' if unresolved_selection else 'failed',
                   result=copy.deepcopy(data))


def result(request_id):
    with _LOCK:
        row = _RECORDS.get(request_id)
        if row is None: return {'ok': False, 'outcome': 'unknown', 'cas_request_id': request_id}
        if row['state'] == 'pending':
            if 'rejected_acknowledgement' in row:
                return {'ok': False, 'outcome': 'invalid-native-acknowledgement', 'cas_request_id': request_id,
                        'cas_request_state': 'pending', 'ui_transition_verified': False, 'input_submitted': False,
                        'message': row['acknowledgement_validation_error'],
                        'native_acknowledgement': copy.deepcopy(row['rejected_acknowledgement']),
                        'mutation_started': row['rejected_acknowledgement'].get('mutation_started') is True}
            return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': request_id}
        if row['state'] == 'superseded-read':
            return {'ok': False, 'outcome': 'superseded-read', 'cas_request_id': request_id,
                    'ui_transition_verified': False, 'input_submitted': False}
        if row['request']['operation'] == 'accept':
            response = dict(copy.deepcopy(row['result']), ui_transition_verified=row['state'] == 'completed',
                            input_submitted=False, cas_request_state=row['state'],
                            outcome='live-return' if row['state'] == 'completed' else
                                    'accept-intent' if row['state'] == 'accept-intent' else
                                    'accept-unresolved' if row['state'] == 'accept-unresolved' else 'accept-rejected',
                            live_return_verified=row['state'] == 'completed')
            if row['state'] == 'completed':
                response['ok'] = True  # Observed Live metadata, not a native commit ACK.
                response.update(lifecycle_stage='observed-live-return',
                                result_scope='game-owned-live-observation',
                                commit_submission_verified=False, appearance_persistence_verified=False)
            if 'return_observation' in row:
                response['return_observation'] = copy.deepcopy(row['return_observation'])
            if 'accept_intent' in row:
                response['accept_intent'] = copy.deepcopy(row['accept_intent'])
            if 'owner_pair_diagnostic' in row:
                response['owner_pair_diagnostic'] = copy.deepcopy(row['owner_pair_diagnostic'])
            return response
        response = dict(copy.deepcopy(row['result']), ui_transition_verified=bool(row['result'].get('ok')),
                        input_submitted=False, cas_request_state=row['state'])
        if 'cas_room' in row:
            response['cas_room'] = copy.deepcopy(row['cas_room'])
        if 'owner_pair_diagnostic' in row:
            response['owner_pair_diagnostic'] = copy.deepcopy(row['owner_pair_diagnostic'])
        if row['request']['operation'] == 'form-select':
            response.update(outcome='form-selected' if row['state'] == 'completed' else row['state'],
                            selection_only_verified=row['state'] == 'completed', mapping_verified=False,
                            alternate_accept_authorized=False, appearance_persistence_verified=False)
        if row['request']['operation'] in ('undo', 'redo'):
            response.update(history_data_change_verified=bool(row['result'].get('ok')),
                            history_expected_target_verified=False)
        return response


def observe_return(request_id, snapshot, phase, household_id, minimum_ticks):
    """Record game-thread Live evidence, without committing or changing a Sim.

    Both observations are freshly produced by test_driver. Caller assertions
    cannot replace the stored producer baseline, elapsed simulation ticks or current
    native connection/zone identity. The original native intent is retained.
    """
    if (not isinstance(request_id, str) or len(request_id) != 32 or
            any(char not in '0123456789abcdef' for char in request_id) or
            phase not in ('baseline', 'complete') or type(minimum_ticks) is not int or
            not 1 <= minimum_ticks <= 6000):
        raise ValueError('Use one existing CAS return UUID and a bounded typed observation phase.')
    with _LOCK:
        row = _RECORDS.get(request_id)
        if row is None or row['request']['operation'] != 'accept' or row['state'] not in ('accept-intent', 'accept-unresolved', 'completed'):
            raise ValueError('CAS return requires its retained native accept intent.')
        if _PEERS:
            raise ValueError('CAS peers remain attached; Live return is not verified.')
        if not isinstance(snapshot, dict):
            raise ValueError('CAS return requires a native producer snapshot.')
        if snapshot.get('sim_time_source') != 'services.time_service().sim_now':
            raise ValueError('CAS return requires the exact native simulation timeline origin; game-clock ticks are not progress proof.')
        intent = row.get('accept_intent', row['result'])
        original_household = intent['client']['sim']['householdId']
        if household_id != original_household:
            raise ValueError('CAS return household differs from its retained original native intent.')
        sim = snapshot.get('sim')
        ticks = snapshot.get('sim_now_ticks')
        query = snapshot.get('runtime_queries')
        if (snapshot.get('ok') is not True or not isinstance(sim, dict) or sim.get('id') != row['sim_id'] or
                sim.get('instanced') is not True or snapshot.get('household_id') != household_id or
                snapshot.get('in_build_buy') is not False or snapshot.get('zone_running') is not True or
                not isinstance(query, dict) or any(query.get(key) != 'returned-value'
                    for key in ('client_id', 'zone_running', 'sim_now_ticks'))):
            raise ValueError('CAS return lacks the exact instanced Sim and native running Live context.')
        for field in ('client_id', 'zone_id', 'save_guid', 'household_id'):
            value = snapshot.get(field)
            if (not isinstance(value, str) or not value.isascii() or not value.isdecimal() or
                    not 0 < int(value) < 1 << 64 or str(int(value)) != value):
                raise ValueError('CAS return lacks an exact native ' + field + ' identity.')
        if (not isinstance(ticks, str) or not ticks.isascii() or not ticks.isdecimal() or
                not 0 <= int(ticks) < 1 << 64 or str(int(ticks)) != ticks):
            raise ValueError('CAS return lacks exact native simulation timeline ticks.')
        observed = {key: snapshot[key] for key in
                    ('household_id', 'client_id', 'zone_id', 'save_guid', 'sim_now_ticks', 'sim_time_source')}
        observed.update(sim_id=row['sim_id'], minimum_ticks=minimum_ticks)
        stored = row.get('return_observation')
        if stored is not None and (not isinstance(stored, dict) or not isinstance(stored.get('baseline'), dict) or
                stored['baseline'].get('sim_time_source') != 'services.time_service().sim_now'):
            raise ValueError('Retained CAS baseline lacks the exact native simulation timeline origin; old clock proof cannot be reused.')
        if phase == 'baseline':
            if stored is not None:
                if any(stored['baseline'][key] != observed[key] for key in
                       ('sim_id', 'household_id', 'client_id', 'zone_id', 'save_guid', 'minimum_ticks', 'sim_time_source')):
                    raise ValueError('CAS return baseline identity cannot be replaced.')
            else:
                row['return_observation'] = {'baseline': copy.deepcopy(observed), 'live_return_verified': False}
            return dict(copy.deepcopy(row['return_observation']), ok=True, cas_request_id=request_id,
                        outcome='live-baseline', ui_transition_verified=False)
        if stored is None:
            raise ValueError('CAS return completion requires its stored producer baseline.')
        baseline = stored['baseline']
        if any(baseline[key] != observed[key] for key in
               ('sim_id', 'household_id', 'client_id', 'zone_id', 'save_guid', 'minimum_ticks', 'sim_time_source')):
            raise ValueError('Native Live identity changed after the CAS return baseline.')
        if type(snapshot.get('clock_speed')) is not int or snapshot['clock_speed'] != 0 or (
                int(ticks) - int(baseline['sim_now_ticks']) < baseline['minimum_ticks']):
            raise ValueError('CAS return requires simulation timeline progress and a final native paused readback.')
        if row['state'] != 'completed':
            stored.update(final=copy.deepcopy(observed), live_return_verified=True,
                          advanced_ticks=int(ticks) - int(baseline['sim_now_ticks']),
                          commit_submission_verified=False, appearance_persistence_verified=False)
            row.setdefault('accept_intent', copy.deepcopy(row['result']))
            row['state'] = 'completed'
        return dict(copy.deepcopy(stored), ok=True, outcome='live-return', cas_request_id=request_id,
                    ui_transition_verified=True)


def dispatch(action, sim_id, value, backend=None):
    if action == 'cas_ui_result': return result(value)
    if action == 'cas_ui_panels':
        return {'ok': True, 'panels': sorted(PANELS), 'aliases': dict(ALIASES),
                'typed_controls': {name: sorted(fields) for name, fields in cas_controls.SCHEMAS.items()},
                'swatch_types': {'skin': 0, 'eyes': 1, 'hair': 2, 'eyebrows': 3,
                    'facial_hair': 4, 'fur': 6, 'secondary_eyes': 7, 'nose': 8,
                    'arm_hair': 9, 'leg_hair': 10, 'front_hair': 11, 'back_hair': 12,
                    'mane': 13, 'forelock': 14, 'horse_feather': 15, 'horse_tail': 16},
                'native_refusal_is_success': False, 'catalog_pagination_discards_items': False}
    if action == 'cas_ui_diagnostics': return diagnostics()
    if action == 'cas_ui_socket_ack':
        # Internal socket callbacks carry typed values through the owner queue,
        # avoiding a second JSON string escaping every Unicode/raw field.
        if isinstance(value, str):
            if len(value.encode('utf-8')) > 262656:
                raise ValueError('Use a bounded native CAS acknowledgement.')
            data = json.loads(value)
        else:
            data = value
        if not isinstance(data, dict) or set(data) != {'peer', 'request_id', 'payload'}:
            raise ValueError('Invalid native CAS acknowledgement envelope.')
        for name, size in (('peer', 64), ('request_id', 32)):
            if not isinstance(data[name], str) or len(data[name]) != size or any(c not in '0123456789abcdef' for c in data[name]):
                raise ValueError('Invalid native CAS acknowledgement identity.')
        return receive_socket(data['peer'], data['request_id'], data['payload'], backend=backend)
    if action != 'cas_ui_request': raise ValueError('Unknown CAS UI operation.')
    if not isinstance(value, str) or len(value) > 2048: raise ValueError('Use a bounded typed CAS request.')
    return submit(str(sim_id), json.loads(value), backend=backend)
