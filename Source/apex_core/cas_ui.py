"""Typed native CAS client requests; UI acknowledgements prove client state.

EA SendUIMessage has only a message name. A short printable ASCII envelope is
delivered as one ordered batch using registered character messages. This avoids
mouse input, process offsets, arbitrary services/evaluation, and network loaders.
"""
from collections import OrderedDict
import copy
import json
import threading
import time
import uuid
from .cas_panels import PANELS, ALIASES

_RECORDS = OrderedDict()
_LOCK = threading.RLock()
_CAPACITY = 64
_CONNECTION = None
_READY = None
_LAST_REPLY = None
_PEERS = {}


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


def receive_socket(token, request_id, payload):
    with _LOCK:
        peer, row = _PEERS.get(token), _RECORDS.get(request_id)
        if peer is None or row is None or row.get('peer') != token or peer['sim_id'] != row['sim_id']:
            raise ValueError('CAS acknowledgement does not match its claimed peer/Sim/request.')
        receive(request_id, payload)
    return {'ok': True, 'acknowledgement_accepted': True, 'cas_request_id': request_id,
            'ui_transition_verified': bool(row['result'].get('ok'))}


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
        if preset_query not in ('returned-value', 'returned-null', 'failed') or (
                (preset_query == 'returned-value' and not isinstance(preset, dict)) or
                (preset_query != 'returned-value' and preset is not None)):
            raise ValueError('CAS preset query must distinguish a returned record from null or failed discovery.')
    operation = request['operation']
    if operation in ('panel', 'select') and (type(client.get('menu_state')) is not int or client['menu_state'] != panel(request['panel']) or client.get('panel_visible') is not True):
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


def panel(value):
    name = ALIASES.get(value, value)
    if name not in PANELS: raise ValueError('Use a named installed CAS panel; run cas panels.')
    return PANELS[name]


def envelope(sim_id, request):
    if not isinstance(sim_id, str) or not sim_id.isdigit() or not 0 < int(sim_id) < 2 ** 64:
        raise ValueError('Choose an explicit CAS Sim identity.')
    if not isinstance(request, dict): raise ValueError('Use a typed CAS request.')
    op = request.get('operation')
    allowed = {'status': {'operation'}, 'panel': {'operation', 'panel'},
        'outfit': {'operation', 'category', 'index'},
        'outfit-add': {'operation', 'category'}, 'hair-swatch': {'operation', 'data_id'},
        'select': {'operation', 'panel', 'data_id'}, 'undo': {'operation'}, 'redo': {'operation'}}
    if op not in allowed or set(request) != allowed[op]: raise ValueError('Unsupported or incomplete CAS request.')
    state = panel(request['panel']) if 'panel' in request else 0
    if op == 'select' and state not in {PANELS[name] for name in (
            'clothing_hair', 'clothing_tops', 'clothing_bottoms', 'clothing_fullbody', 'clothing_shoes')}:
        raise ValueError('Native selection for this panel requires its typed preset/layer contract; no request sent.')
    category, index = request.get('category', 0), request.get('index', 0)
    if type(category) is not int or not 0 <= category <= 255 or type(index) is not int or not 0 <= index < 5:
        raise ValueError('CAS outfit category/index is out of range.')
    value = request.get('data_id', '')
    if op == 'outfit-add' and category > 13:
        raise ValueError('Only installed native CAS outfit categories may be appended.')
    if op in ('select', 'hair-swatch') and (not isinstance(value, str) or not value.isdigit() or not 0 < int(value) < 2 ** 64):
        raise ValueError('Native CAS data_id must be an exact decimal resource identity.')
    request_id = uuid.uuid4().hex
    wire = '|'.join(map(str, (request_id, sim_id, op, state, category, index, value)))
    if len(wire) > 512 or any(not 32 <= ord(c) <= 126 for c in wire): raise ValueError('CAS envelope exceeds its limit.')
    return request_id, wire


def submit(sim_id, request, send=None, clock=time.monotonic):
    request_id, wire = envelope(sim_id, request)
    with _LOCK:
        socket_ready = send is None and any(peer['sim_id'] == sim_id and clock() - peer['observed_at'] <= 3 for peer in _PEERS.values())
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
        pending = [row for row in _RECORDS.values() if row['state'] == 'pending']
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


def receive(request_id, payload):
    if not isinstance(payload, str) or len(payload.encode('utf-8')) > 131072:
        raise ValueError('CAS client response exceeds its UTF-8 byte bound.')
    data = json.loads(payload)
    if not isinstance(data, dict) or data.get('protocol') != 1 or type(data.get('ok')) is not bool or data.get('cas_request_id') != request_id:
        raise ValueError('CAS client response identity/protocol differs.')
    with _LOCK:
        row = _RECORDS.get(request_id)
        if row is None: raise ValueError('Unsolicited CAS client response.')
        if row['state'] not in ('pending', 'superseded-read'):
            if row['result'] != data: raise ValueError('CAS request acknowledgement changed.')
            return
        if data.get('ok'):
            client = data.get('client')
            validate_client(client, row['sim_id'], row['request'])
        row.update(state='completed' if data.get('ok') else 'failed', result=copy.deepcopy(data))


def result(request_id):
    with _LOCK:
        row = _RECORDS.get(request_id)
        if row is None: return {'ok': False, 'outcome': 'unknown', 'cas_request_id': request_id}
        if row['state'] == 'pending': return {'ok': False, 'outcome': 'pending-client', 'cas_request_id': request_id}
        if row['state'] == 'superseded-read':
            return {'ok': False, 'outcome': 'superseded-read', 'cas_request_id': request_id,
                    'ui_transition_verified': False, 'input_submitted': False}
        return dict(copy.deepcopy(row['result']), ui_transition_verified=bool(row['result'].get('ok')),
                    input_submitted=False, cas_request_state=row['state'])


def dispatch(action, sim_id, value):
    if action == 'cas_ui_result': return result(value)
    if action == 'cas_ui_panels': return {'ok': True, 'panels': sorted(PANELS), 'aliases': dict(ALIASES)}
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
        return receive_socket(data['peer'], data['request_id'], data['payload'])
    if action != 'cas_ui_request': raise ValueError('Unknown CAS UI operation.')
    if not isinstance(value, str) or len(value) > 2048: raise ValueError('Use a bounded typed CAS request.')
    return submit(str(sim_id), json.loads(value))
