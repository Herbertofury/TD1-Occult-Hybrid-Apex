"""Typed development controls for the native existing-owner selection patch."""
import os
import copy

_LAYOUT_SCOPE = None  # Fresh pre-entry representations, never prior appearance values.


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
    if operation in ('seed-active','seed-canonical') and set(value) == {'operation','scope_id','sim_id','native_kind','native_hex','sha256'}:
        if type(value['native_kind']) is not int or value['native_kind'] not in (1,2,4,8,16,32,64):
            raise ValueError('An active entry requires its exact native rendering kind.')
        argument({key:item for key,item in dict(value,operation='seed').items() if key!='native_kind'})
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
        validate(value, os.getpid() if pid is None else pid)
        for key in ('owner_appearances','owner_appearance_error'):value.pop(key,None)
        value['owner_appearance_query']='unavailable'
        value['bank_commit_authorized']=False
        scope=_LAYOUT_SCOPE
        if scope is not None and scope['pid']==value['pid'] and scope['scope_id']==value['scope_id']:
            try:
                from . import cas_owner_decode,form_appearance
                decoded=[]
                for row in value['owners']:
                    captured=scope['owners'][(value['sim_id'],row['owner_id'])]
                    if captured['native_kind']!=row['native_kind']:
                        raise ValueError('Native appearance changed its captured rendering kind.')
                    item=cas_owner_decode.read(bytes.fromhex(row['native_hex']),value['sim_id'],captured['layout'])
                    if item['native_sha256']!=row['sha256']:
                        raise ValueError('Decoded native appearance differs from its complete snapshot.')
                    decoded.append(dict(owner_id=row['owner_id'],native_kind=row['native_kind'],
                        native_sha256=item['native_sha256'],fields=item['fields'],
                        appearance_sha256=form_appearance.fingerprint(item['fields'])['appearance_sha256']))
                value['owner_appearances']=decoded
                value['owner_appearance_query']='returned-value'
                value['bank_commit_authorized']=False
            except Exception as error:
                value['owner_appearance_query']='failed'
                value['owner_appearance_error']=str(error)[:2048]
        return value
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


def _verify_imported_owners(call, status, expected):
    """Read every imported DTO before the native CAS entry can begin.

    This comparison uses the fresh pre-entry fields, not a post-import baseline.
    A stable but already damaged owner must never pass entry qualification.
    No appearance data is written by this bounded readback.
    """
    from .cas_owner_export_page import Collector
    from . import cas_owner_decode, form_appearance
    if status.get('ok') is not True or status.get('selection_enabled') is not True:
        raise ValueError('Cannot verify an incomplete native appearance import.')
    members = status.get('members', [])
    if {row['sim_id'] for row in members} != {sid for sid, _owner in expected}:
        raise ValueError('Native import readback has a different household roster.')
    verified = []
    for member in members:
        sid = member['sim_id']
        kinds = {owner: item['native_kind'] for (sim_id, owner), item in expected.items() if sim_id == sid}
        identity = dict(pid=status['pid'], scope_id=status['scope_id'], sim_id=sid,
            generation=member['graph_generation'], owned_mask=member['owned_mask'],
            selected_owner_id=member['graph_selected_owner_id'])
        collector = Collector(identity, kinds)
        cursor = ''
        while not collector.complete:
            page = call(dict(operation='export-owner-page', scope_id=identity['scope_id'], sim_id=sid,
                expected_generation=identity['generation'], after_owner_id=cursor))
            cursor = collector.append(page)['next_owner_id']
        for row in collector.document()['owners']:
            original = expected[(sid, row['owner_id'])]['fields']
            observed = cas_owner_decode.read(bytes.fromhex(row['native_hex']), sid, cas_owner_decode.layout(original))['fields']
            before = form_appearance.fingerprint(original); after = form_appearance.fingerprint(observed)
            changed = sorted(name for name in set(original) | set(observed)
                if before['field_sha256'].get(name) != after['field_sha256'].get(name))
            if changed:
                raise ValueError('Native import changed pre-entry appearance '+sid+'/'+row['owner_id']+': '+', '.join(changed))
            verified.append(dict(sim_id=sid, owner_id=row['owner_id'], native_kind=row['native_kind'],
                native_sha256=row['sha256'], appearance_sha256=after['appearance_sha256']))
    return dict(ok=True, owners=verified, appearance_written=False, pre_entry_fields_verified=True)


def seed_members(backend):
    """Extend CAS's native import with every pre-entry canonical owner.

    Run on the Live game thread, before native CAS disposes its producers.
    The client packet can narrow the occult tracker; the complete native save
    model supplies its otherwise omitted records without exporting a file.
    """
    global _LAYOUT_SCOPE
    from . import overlay_loader, sim_data, form_appearance as appearance, lifestate_forms, cas_owner_payload, cas_owner_decode
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
    receipts = [];layouts={}; expected={};epochs={}
    import base64
    for row in status['members']:
        sim = members[row['sim_id']]
        from . import cas_bank_transaction
        checkpoint=cas_bank_transaction.status(backend,sim)
        epoch=checkpoint.get('expected_pending_sha256')
        if checkpoint.get('phase')!='captured' or not cas_bank_transaction.primitive._hash(epoch):
            raise ValueError('Native owners require this member\'s fresh captured CAS transaction.')
        epochs[row['sim_id']]=epoch
        owners = dict(backend._form_map(sim.occult_tracker), active=sim)
        fields = {str(kind): appearance.packed(backend, owner) for kind, owner in owners.items()}
        before = {kind: appearance.fingerprint(payload) for kind,payload in fields.items()}
        for kind,owner in owners.items():
            native_kind=int(backend._get_current_flags(sim)) if kind=='active' else int(kind)
            owner_id='active/'+str(native_kind) if kind=='active' else 'native/'+str(native_kind)
            layouts[(row['sim_id'],owner_id)]=dict(native_kind=native_kind,layout=cas_owner_decode.layout(fields[str(kind)]))
            expected[(row['sim_id'],owner_id)]=dict(native_kind=native_kind,fields=fields[str(kind)])
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
        # EA's tracker record has no per-form pelt/custom-texture fields.
        # Import each exact complete owner separately, with its own root fields.
        for kind in sorted(backend._form_map(sim.occult_tracker),key=int):
            projected=cas_owner_payload.project_record(capture,fields[str(kind)],int(kind))
            canonical=call(dict(operation='seed-canonical',scope_id=status['scope_id'],sim_id=row['sim_id'],
                native_kind=int(kind),native_hex=projected['native_hex'],sha256=projected['sha256']))
            if canonical.get('ok') is not True:
                raise ValueError('Complete canonical appearance import failed.')
        canonical_row=next(item for item in canonical['members'] if item['sim_id']==row['sim_id'])
        if type(canonical_row.get('canonical_source_seeded_mask')) is not int or canonical_row['canonical_source_seeded_mask']!=row['owned_mask']:
            raise ValueError('Complete canonical appearance import omitted an existing form.')
        active_kind=int(backend._get_current_flags(sim))
        projected=cas_owner_payload.project_record(capture,fields['active'],active_kind)
        active=call(dict(operation='seed-active',scope_id=status['scope_id'],sim_id=row['sim_id'],
            native_kind=active_kind,native_hex=projected['native_hex'],sha256=projected['sha256']))
        active_row=next(item for item in active.get('members',()) if item['sim_id']==row['sim_id'])
        if active.get('ok') is not True or active_row.get('active_entry_source_seeded') is not True:
            raise ValueError('The exact active appearance did not import its complete genetic record.')
        named = []
        for variant in lifestate_forms.native_cas_owners(backend, sim):
            projected = cas_owner_payload.project_record(capture, variant['fields'],variant['native_kind'])
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
            layouts[(row['sim_id'],variant['owner_id'])]=dict(native_kind=variant['native_kind'],
                layout=cas_owner_decode.layout(variant['fields']))
            expected[(row['sim_id'],variant['owner_id'])]=dict(native_kind=variant['native_kind'],fields=variant['fields'])
        if any(appearance.fingerprint(appearance.packed(backend,owner)) != before[str(kind)] for kind,owner in owners.items()):
            raise ValueError('Independent full-record imports changed a pre-entry native Sim appearance.')
        receipts.append(dict(sim_id=row['sim_id'], native_sha256=capture['native_sha256'],
                             native_bytes=len(raw), native_message_type=capture['native_message_type'],
                             imported_mask=imported['imported_mask'], kinds=imported['kinds'], named_owners=named))
    result = call(dict(operation='activate', scope_id=status['scope_id']))
    if result.get('ok') is not True or result.get('selection_enabled') is not True:
        raise ValueError('Complete native owner selection did not activate.')
    verification = _verify_imported_owners(call,result,expected)
    _LAYOUT_SCOPE=dict(pid=os.getpid(),scope_id=status['scope_id'],owners=layouts,epochs=epochs,
        logical_owners={row['sim_id']:dict(logical_owner_ids=row['logical_owner_ids'],human_owner_id=row['human_owner_id'])
                        for row in result['members']})
    return dict(enabled=True, scope_id=status['scope_id'], members=receipts, existing_appearances_unchanged=True,
                import_verification=verification)


def owns_return(sim_id,epoch):
    scope=_LAYOUT_SCOPE
    if scope is None or not any(sid==sim_id for sid,_oid in scope['owners']):return False
    if scope['pid']!=os.getpid() or scope.get('epochs',{}).get(sim_id)!=epoch:
        raise ValueError('Native CAS return belongs to a different process or member checkpoint.')
    return True


def returned_owners(backend,sim,epoch):
    """Read the complete committed graph after receiver-owned Live return.

    No model is harvested on a Source worker. CAS must already have completed
    its native synchronization; this retains raw unknown bytes independently
    for every canonical, active and named owner. It never loads a gameplay DTO.
    """
    sid=str(sim.id)
    if not owns_return(sid,epoch):return None
    from . import overlay_loader,cas_owner_decode
    from .cas_owner_export_page import Collector
    import paths
    scope=_LAYOUT_SCOPE
    call=lambda value:overlay_loader.native_cas_engine_control(backend.__file__,paths.DLL_PATH,value)
    status=call(dict(operation='status'))
    rows=[row for row in status.get('members',[]) if row['sim_id']==sid]
    if (status.get('ok') is not True or status.get('pid')!=scope['pid'] or
            status.get('scope_id')!=scope['scope_id'] or len(rows)!=1 or
            rows[0].get('native_view_fault') is not False):
        raise ValueError('Native CAS return has another or unresolved owner graph.')
    member=rows[0];expected={oid:item for (owner_sid,oid),item in scope['owners'].items() if owner_sid==sid}
    binding=scope['logical_owners'].get(sid)
    if (not isinstance(binding,dict) or any(member.get(key)!=binding[key]
            for key in ('logical_owner_ids','human_owner_id'))):
        raise ValueError('Native CAS logical form bindings changed after their original capture.')
    identity=dict(pid=scope['pid'],scope_id=scope['scope_id'],sim_id=sid,generation=member['graph_generation'],
        owned_mask=member['owned_mask'],selected_owner_id=member['graph_selected_owner_id'])
    collector=Collector(identity,{oid:item['native_kind'] for oid,item in expected.items()});cursor=''
    while not collector.complete:
        page=call(dict(operation='export-owner-page',scope_id=scope['scope_id'],sim_id=sid,
            expected_generation=identity['generation'],after_owner_id=cursor))
        cursor=collector.append(page)['next_owner_id']
    document=collector.document()
    for row in document['owners']:
        row['fields']=cas_owner_decode.read(bytes.fromhex(row['native_hex']),sid,expected[row['owner_id']]['layout'])['fields']
    final=call(dict(operation='status'))
    fresh=[row for row in final.get('members',[]) if row['sim_id']==sid]
    if (final.get('ok') is not True or final.get('pid')!=scope['pid'] or final.get('scope_id')!=scope['scope_id'] or
            len(fresh)!=1 or fresh[0].get('graph_generation')!=identity['generation'] or
            fresh[0].get('graph_selected_owner_id')!=identity['selected_owner_id'] or
            fresh[0].get('native_view_fault') is not False or any(fresh[0].get(key)!=binding[key]
                for key in ('logical_owner_ids','human_owner_id'))):
        raise ValueError('Native CAS return changed during its complete appearance readback.')
    return dict(schema=1,ok=True,source='receiver-native-owner-return',identity=identity,
        checkpoint_epoch=epoch,owners=document['owners'],logical_owner_ids=copy.deepcopy(binding['logical_owner_ids']),
        human_owner_id=binding['human_owner_id'],appearance_written=False,save_reload_verified=False)
