"""Typed development controls for the native existing-owner selection patch."""
import os


def _identity(value):
    return (isinstance(value, str) and 1 <= len(value) <= 20 and value.isascii() and
            value.isdecimal() and value[0] != '0' and int(value) <= 0xffffffffffffffff)


def argument(value):
    if not isinstance(value, dict):
        raise ValueError('Use a typed native CAS engine operation.')
    operation = value.get('operation')
    if operation == 'status' and set(value) == {'operation'}:
        return
    scope = value.get('scope_id')
    if not isinstance(scope, str) or len(scope) != 32 or any(c not in '0123456789abcdef' for c in scope):
        raise ValueError('Use the exact native form scope identity.')
    if operation == 'activate' and set(value) == {'operation', 'scope_id'}:
        return
    if operation == 'entry-ready' and set(value) == {'operation', 'scope_id', 'sim_id'} and _identity(value['sim_id']):
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
    rows = value.get('members')
    if operation != 'arm' or set(value) != {'operation', 'scope_id', 'members'} or not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise ValueError('Use the complete captured household roster to arm native form selection.')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'sim_id', 'owned_mask'} or not _identity(row['sim_id']):
            raise ValueError('Native form scope has an invalid member identity.')
        mask = row['owned_mask']
        if type(mask) is not int or not 3 <= mask <= 127 or not mask & 1 or row['sim_id'] in ids:
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
        if (type(mask) is not int or not 3 <= mask <= 127 or not mask & 1 or
                type(imported) is not int or imported not in (0, mask) or
                not isinstance(kinds, list) or len(kinds) > 7 or
                any(type(k) is not int or k not in (1, 2, 4, 8, 16, 32, 64) for k in kinds) or len(set(kinds)) != len(kinds)):
            raise ValueError('Native form patch owner capture is incomplete or untyped.')
        if imported and sum(kinds) != imported:
            raise ValueError('Native form patch readiness does not cover all imported kinds.')
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
    from . import overlay_loader, sim_data, form_appearance as appearance
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
        receipts.append(dict(sim_id=row['sim_id'], native_sha256=capture['native_sha256'],
                             native_bytes=len(raw), native_message_type=capture['native_message_type'],
                             imported_mask=imported['imported_mask'], kinds=imported['kinds']))
    result = call(dict(operation='activate', scope_id=status['scope_id']))
    if result.get('ok') is not True or result.get('selection_enabled') is not True:
        raise ValueError('Complete native owner selection did not activate.')
    return dict(enabled=True, scope_id=status['scope_id'], members=receipts, existing_appearances_unchanged=True)
