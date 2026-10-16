"""Typed development controls for the native existing-owner selection patch."""
import os


def _identity(value):
    return (isinstance(value, str) and 1 <= len(value) <= 20 and value.isascii() and
            value.isdecimal() and value[0] != '0' and int(value) <= 0xffffffffffffffff)


def argument(value):
    if not isinstance(value, dict):
        raise ValueError('Use a typed native CAS engine operation.')
    operation = value.get('operation')
    if operation in ('status', 'view-status') and set(value) == {'operation'}:
        return
    scope = value.get('scope_id')
    if not isinstance(scope, str) or len(scope) != 32 or any(c not in '0123456789abcdef' for c in scope):
        raise ValueError('Use the exact native form scope identity.')
    if operation == 'activate' and set(value) == {'operation', 'scope_id'}:
        return
    if operation == 'entry-ready' and set(value) == {'operation', 'scope_id', 'sim_id'} and _identity(value['sim_id']):
        return
    if operation == 'export-owner-page' and set(value) == {'operation','scope_id','sim_id','expected_generation','after_owner_id'}:
        from .cas_owner_export_page import OWNER
        if (not _identity(value['sim_id']) or type(value['expected_generation']) is not int or
                not 0<value['expected_generation']<2**64 or not isinstance(value['after_owner_id'],str) or
                value['after_owner_id'] and OWNER.fullmatch(value['after_owner_id']) is None):
            raise ValueError('Export one bounded page of the exact committed owner graph.')
        return
    if operation == 'export-owner' and set(value) == {'operation','scope_id','sim_id','owner_id','expected_generation'}:
        import re
        if (not _identity(value['sim_id']) or not isinstance(value['owner_id'],str) or
                re.fullmatch(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}',value['owner_id']) is None or
                type(value['expected_generation']) is not int or not 0<value['expected_generation']<2**64):
            raise ValueError('Snapshot one existing exact appearance owner and graph generation.')
        return
    if operation == 'stage-view' and set(value) == {'operation', 'scope_id', 'sim_id', 'request_id',
            'expected_owner_id', 'owner_id', 'expected_generation', 'expected_layer'}:
        import re
        pattern = r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}'
        if (not _identity(value['sim_id']) or not isinstance(value['request_id'], str) or
                re.fullmatch(r'[0-9a-f]{32}', value['request_id']) is None or
                any(not isinstance(value[name], str) or re.fullmatch(pattern, value[name]) is None
                    for name in ('expected_owner_id', 'owner_id')) or
                type(value['expected_generation']) is not int or not 0 < value['expected_generation'] < 2**64 or
                type(value['expected_layer']) is not int or value['expected_layer'] not in (0, 1)):
            raise ValueError('Use an exact existing form owner, generation and one-shot view identity.')
        return
    if operation == 'seed' and set(value) == {'operation', 'scope_id', 'sim_id', 'native_hex', 'sha256'}:
        encoded, digest = value['native_hex'], value['sha256']
        if (not _identity(value['sim_id']) or not isinstance(encoded, str) or not 0 < len(encoded) <= 8*1024*1024 or
                len(encoded) % 2 or any(c not in '0123456789abcdef' for c in encoded) or
                not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('Native full-owner import requires exact bounded serialized bytes.')
        import hashlib
        if hashlib.sha256(bytes.fromhex(encoded)).hexdigest() != digest:
            raise ValueError('Native full-owner bytes differ from their captured SHA-256.')
        return
    if operation == 'seed-appearance' and set(value) == {
            'operation', 'scope_id', 'sim_id', 'owner_id', 'native_kind', 'native_hex', 'sha256'}:
        import re
        if (not isinstance(value['owner_id'], str) or
                re.fullmatch(r'[a-z][a-z0-9_]{0,63}/[a-z][a-z0-9_]{0,63}', value['owner_id']) is None or
                value['owner_id'].startswith('native/') or type(value['native_kind']) is not int or
                value['native_kind'] not in (1, 2, 4, 8, 16, 32, 64)):
            raise ValueError('Use an independent named form identity and existing native rendering kind.')
        argument({key: item for key, item in dict(value, operation='seed').items()
                  if key not in ('owner_id', 'native_kind')})
        return
    rows = value.get('members')
    if operation != 'arm' or set(value) != {'operation', 'scope_id', 'members'} or not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise ValueError('Use the complete captured household roster to arm native form selection.')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'sim_id', 'owned_mask'} or not _identity(row['sim_id']):
            raise ValueError('Native form scope has an invalid member identity.')
        mask = row['owned_mask']
        if type(mask) is not int or not 1 <= mask <= 127 or not mask & 1 or row['sim_id'] in ids:
            raise ValueError('Native form scope has an invalid or duplicated existing owner.')
        ids.add(row['sim_id'])


def reply(value, pid=None):
    if (not isinstance(value, dict) or type(value.get('ok')) is not bool or
            value.get('game_files_written') is not False or value.get('native_patch_qualified') is not False or
            value.get('production_ready') is not False):
        raise ValueError('Native form patch returned invalid qualification evidence.')
    if not value['ok']:
        return value
    if type(value.get('pid')) is not int or value['pid'] != (os.getpid() if pid is None else pid):
        raise ValueError('Native form patch belongs to a different game process.')
    if value.get('scope') == 'native-owner-export-page':
        from .cas_owner_export_page import validate
        return validate(value, os.getpid() if pid is None else pid)
    if value.get('scope') == 'native-form-view-status':
        if type(value.get('available')) is not bool:
            raise ValueError('Native form view availability is untyped.')
        if value['available']:
            import re
            if (not _identity(value.get('sim_id')) or not isinstance(value.get('owner_id'), str) or
                    re.fullmatch(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}', value['owner_id']) is None or
                    type(value.get('native_kind')) is not int or value['native_kind'] not in (1,2,4,8,16,32,64) or
                    type(value.get('layer')) is not int or value['layer'] not in (0,1) or
                    value.get('state') not in ('bound','unbound','unresolved')):
                raise ValueError('Native form view identity is incomplete.')
        return value
    if any(type(value.get(key)) is not bool for key in ('installed', 'armed', 'selection_enabled')):
        raise ValueError('Native form patch readiness is untyped.')
    rows = value.get('members')
    if not isinstance(rows, list) or len(rows) > 8:
        raise ValueError('Native form patch roster is out of bounds.')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not _identity(row.get('sim_id')) or row['sim_id'] in ids:
            raise ValueError('Native form patch member identity is invalid or duplicated.')
        ids.add(row['sim_id'])
        mask, imported = row.get('owned_mask'), row.get('imported_mask')
        kinds = row.get('kinds')
        if (type(mask) is not int or not 1 <= mask <= 127 or not mask & 1 or
                type(imported) is not int or imported not in (0, mask) or
                not isinstance(kinds, list) or len(kinds) > 7 or
                any(type(k) is not int or k not in (1, 2, 4, 8, 16, 32, 64) for k in kinds) or len(set(kinds)) != len(kinds)):
            raise ValueError('Native form patch owner capture is incomplete or untyped.')
        if imported and sum(kinds) != imported:
            raise ValueError('Native form patch readiness does not cover all imported kinds.')
    exported = value.get('owner_export')
    if exported is not None:
        import hashlib
        import re
        if (not isinstance(exported,dict) or type(exported.get('schema')) is not int or exported['schema']!=1 or
                not _identity(exported.get('sim_id')) or not isinstance(exported.get('owner_id'),str) or
                re.fullmatch(r'[a-z0-9_][a-z0-9_-]{0,63}/[a-z0-9_][a-z0-9_-]{0,63}',exported['owner_id']) is None or
                type(exported.get('generation')) is not int or not 0<exported['generation']<2**64 or
                type(exported.get('native_kind')) is not int or exported['native_kind'] not in (1,2,4,8,16,32,64) or
                type(exported.get('bytes')) is not int or not 0<exported['bytes']<=512*1024 or
                exported.get('appearance_written') is not False or exported.get('model_harvested') is not False or
                exported.get('source')!='committed-native-appearance'):
            raise ValueError('Native appearance snapshot identity or read-only scope differs.')
        encoded=exported.get('native_hex');digest=exported.get('sha256')
        if (not isinstance(encoded,str) or len(encoded)!=2*exported['bytes'] or
                re.fullmatch(r'[0-9a-f]+',encoded) is None or not isinstance(digest,str) or
                re.fullmatch(r'[0-9a-f]{64}',digest) is None):
            raise ValueError('Native appearance snapshot is truncated or noncanonical.')
        raw=bytes.fromhex(encoded)
        if hashlib.sha256(raw).hexdigest()!=digest:
            raise ValueError('Native appearance snapshot bytes differ from their SHA-256.')
        members=[row for row in rows if row['sim_id']==exported['sim_id']]
        if (len(members)!=1 or members[0].get('graph_generation')!=exported['generation'] or
                not any(owner.get('owner_id')==exported['owner_id'] and owner.get('native_kind')==exported['native_kind']
                        for owner in members[0].get('separate_owners',()))):
            raise ValueError('Native appearance snapshot belongs to a different owner/generation.')
        # Parsing is a detached schema read; it never reloads or writes a Sim.
        # Keep the complete raw snapshot even if this game's Python descriptor
        # is unavailable, rather than replacing it with partial inferred fields.
        try:
            from protocolbuffers import FileSerialization_pb2
        except ImportError as error:
            value['owner_export_catalog_query']='unavailable'
            value['owner_export_catalog_error']=str(error)[:2048]
        else:
            message=FileSerialization_pb2.SimData();message.ParseFromString(raw)
            if str(message.sim_id)!=exported['sim_id']:
                raise ValueError('Parsed native appearance has another Sim identity.')
            try:
                from . import sim_data
                catalog=sim_data.catalog(message)
                catalog['scope']='Committed CAS appearance DTO; nonappearance fields can have construction defaults.'
                value['owner_export_catalog']=catalog
                value['owner_export_catalog_query']='returned-value'
            except Exception as error:
                value['owner_export_catalog_query']='failed'
                value['owner_export_catalog_error']=str(error)[:2048]
    return value


def selection_ready(backend, sim_id, mask, kind):
    if backend is None:
        return False
    from . import overlay_loader
    import paths
    status = overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH, {'operation': 'status'})
    if (status.get('ok') is not True or status.get('selection_enabled') is not True or
            status.get('selection_route') != 'independent-owner-binding' or
            status.get('independent_owner_view_ready') is not True):
        return False
    selected = status.get('selected_native', {})
    if selected.get('available') is not True or selected.get('sim_id') != sim_id:
        return False
    rows = [row for row in status['members'] if row['sim_id'] == sim_id]
    return len(rows) == 1 and rows[0]['owned_mask'] == mask == rows[0]['imported_mask'] and kind in rows[0]['kinds']


def stage_view(backend, sim_id, request_id, request):
    from . import overlay_loader
    import paths
    call = lambda value: overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH, value)
    status = call({'operation': 'status'})
    rows = [row for row in status.get('members', ()) if row['sim_id'] == sim_id]
    selected = status.get('selected_native', {})
    if (status.get('owner_view_adapter_available') is not True or status.get('selection_enabled') is not True or
            len(rows) != 1 or selected.get('available') is not True or selected.get('sim_id') != sim_id or
            selected.get('layer') != request['expected_layer'] or
            rows[0]['owned_mask'] != request['owned_mask'] or rows[0]['imported_mask'] != request['owned_mask']):
        raise ValueError('Independent native view lacks its exact complete Sim/layer scope.')
    row = rows[0]
    owners = [owner for owner in row.get('separate_owners', ()) if owner.get('owner_id') == request['owner_id']]
    if len(owners) != 1 or owners[0].get('native_kind') != request['native_kind']:
        raise ValueError('The exact independent form owner is absent or has a different rendering kind.')
    result = call(dict(operation='stage-view', scope_id=status['scope_id'], sim_id=sim_id,
        request_id=request_id, expected_owner_id=row['graph_selected_owner_id'], owner_id=request['owner_id'],
        expected_generation=row['graph_generation'], expected_layer=request['expected_layer']))
    stage = result.get('view_stage', {})
    if (stage.get('request_id') != request_id or stage.get('sim_id') != sim_id or
            stage.get('owner_id') != request['owner_id'] or stage.get('staged_only') is not True or
            type(stage.get('token')) is not int or not 0x10000000 <= stage['token'] <= 0x1fffffff):
        raise ValueError('Independent native view staging was not acknowledged exactly; do not replay.')
    return stage['token']


def view_result(backend, sim_id, request_id, request):
    from . import overlay_loader
    import paths
    status = overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH, {'operation': 'status'})
    result = status.get('owner_view_result', {})
    selected = status.get('selected_native', {})
    if (not isinstance(result, dict) or result.get('request_id') != request_id or
            result.get('sim_id') != sim_id or result.get('owner_id') != request['owner_id'] or
            result.get('state') != 'applied' or result.get('conversion_called') is not False or
            result.get('independent_undo_bound') is not True or result.get('undo_owner_id') != request['owner_id'] or
            result.get('native_kind') != request['native_kind'] or result.get('owned_mask') != request['owned_mask'] or
            selected.get('available') is not True or selected.get('sim_id') != sim_id or
            selected.get('occult_type') != request['native_kind'] or
            selected.get('model_occult_type') != request['native_kind']):
        raise ValueError('Independent native form view lacks its exact completed binding receipt.')
    return result


def entry_ready(backend, sim_id):
    from . import overlay_loader
    if not overlay_loader._CALLS:
        return
    import paths
    status=overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH, {'operation':'status'})
    if status.get('ok') is True and status.get('selection_enabled') is True:
        result=overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH,
            dict(operation='entry-ready',scope_id=status['scope_id'],sim_id=sim_id))
        if result.get('ok') is not True:
            raise ValueError('Native CAS initial-import lifetime was not closed at its actual client handshake.')


def seed_members(backend):
    """Extend CAS's native import with every pre-entry canonical owner.

    Run on the Live game thread, before native CAS disposes its producers.
    The client packet can narrow the occult tracker; the complete native save
    model supplies its otherwise omitted records without exporting a file.
    """
    from . import overlay_loader, sim_data, form_appearance as appearance, lifestate_forms, cas_owner_payload
    if not overlay_loader._CALLS:
        return {'enabled': False}
    import paths
    call = lambda value: overlay_loader.native_cas_engine_control(backend.__file__, paths.DLL_PATH, value)
    status = call({'operation': 'status'})
    if status.get('ok') is not True or status.get('armed') is not True:
        return {'enabled': False}
    household = backend.services.active_household()
    if household is None:
        raise ValueError('Native form import requires the exact loaded household.')
    members = {str(sim.id): sim for sim in household.sim_info_gen()}
    if not set(row['sim_id'] for row in status['members']) <= set(members):
        raise ValueError('Native form scope does not belong to the current household.')
    receipts = []
    import base64
    for row in status['members']:
        sim = members[row['sim_id']]
        owners = dict(backend._form_map(sim.occult_tracker), active=sim)
        before = {str(kind): appearance.fingerprint(appearance.packed(backend, owner)) for kind, owner in owners.items()}
        capture = sim_data.snapshot(backend, sim)
        raw = base64.b64decode(capture['native_base64'], validate=True)
        result = call(dict(operation='seed', scope_id=status['scope_id'], sim_id=row['sim_id'],
                           native_hex=raw.hex(), sha256=capture['native_sha256']))
        if result.get('ok') is not True:
            raise ValueError('Native full-owner import failed: ' + str(result.get('message')))
        imported = next(item for item in result['members'] if item['sim_id'] == row['sim_id'])
        if imported['imported_mask'] != row['owned_mask']:
            raise ValueError('Native full-owner import did not retain every captured kind.')
        if any(appearance.fingerprint(appearance.packed(backend, owner)) != before[str(kind)] for kind, owner in owners.items()):
            raise ValueError('Full native serialization changed a pre-entry appearance.')
        named = []
        for variant in lifestate_forms.native_cas_owners(backend, sim):
            projected = cas_owner_payload.project(capture, variant['fields'])
            result = call(dict(operation='seed-appearance', scope_id=status['scope_id'], sim_id=row['sim_id'],
                owner_id=variant['owner_id'], native_kind=variant['native_kind'],
                native_hex=projected['native_hex'], sha256=projected['sha256']))
            if result.get('ok') is not True:
                raise ValueError('Independent named native appearance import failed.')
            member = next(item for item in result['members'] if item['sim_id'] == row['sim_id'])
            matches = [item for item in member.get('separate_owners', ()) if item.get('owner_id') == variant['owner_id']]
            if len(matches) != 1 or matches[0].get('native_kind') != variant['native_kind']:
                raise ValueError('Native import did not retain the exact named owner identity.')
            named.append(dict(owner_id=variant['owner_id'], native_kind=variant['native_kind'],
                              appearance_sha256=variant['appearance_sha256'], native_sha256=projected['sha256']))
        receipts.append(dict(sim_id=row['sim_id'], native_sha256=capture['native_sha256'],
                             native_bytes=len(raw), native_message_type=capture['native_message_type'],
                             imported_mask=imported['imported_mask'], kinds=imported['kinds'], named_owners=named))
    result = call(dict(operation='activate', scope_id=status['scope_id']))
    if result.get('ok') is not True or result.get('selection_enabled') is not True:
        raise ValueError('Complete native owner selection did not activate.')
    return dict(enabled=True, scope_id=status['scope_id'], members=receipts, existing_appearances_unchanged=True)
