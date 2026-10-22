"""Explicit, paged equipped references; no appearance/mesh export files.

A changed graph or roster invalidates the complete job. Capture never selects
a household member, switches an occult, equips a part or accepts/saves CAS.
"""
import json
import time
from pathlib import Path

KINDS = {1:'Human',2:'Alien',4:'Vampire',8:'Mermaid',16:'Spellcaster',32:'Werewolf',64:'Fairy'}
SPECIAL = {'imaginary_friend':'Imaginary Friend','plantsim':'PlantSim','servo':'Servo',
           'ghost':'Ghost','reaper':'Reaper','skeleton':'Skeleton','scarecrow':'Scarecrow'}


def form_label(owner_id, kind):
    return SPECIAL.get(owner_id.split('/',1)[0], KINDS[kind])


def collect(state, output, save_guid, household_id, catalog_sha256, request=None):
    from apex_cli import owned_request, verified_identity
    from cas_owner_matrix import inventory
    from cli_identity_cache import session
    from source_manifest import write_json, sha256
    request = request or owned_request
    output = Path(output)
    if output.exists() or output.suffix.lower() != '.json':
        raise ValueError('Publish the compact capture to a new JSON file.')
    if len(catalog_sha256) != 64 or any(c not in '0123456789abcdef' for c in catalog_sha256):
        raise ValueError('The exact catalogue SHA-256 is required.')
    def call(action, value):
        result = request(state, action, value=json.dumps(value, separators=(',',':')))
        if result.get('ok') is not True:
            raise ValueError(result.get('message', 'Equipped reference capture failed.'))
        return result
    with session(Path(state)):
        identity = verified_identity(state)
        token = identity['test_token']
        def native(value): return call('test_native_cas_engine', {'test_token':token,'value':value})
        argument = {'save_guid':save_guid,'household_id':household_id}
        roster = call('catalog_actor_roster', argument)
        status = native({'operation':'status'})
        members, _ = inventory(status)
        expected = {row['sim_id']:row for row in status['members']}
        labels = {row['sim_id']:row['name'] for row in roster['members']}
        if roster['pid'] != status['pid'] or set(labels) != set(expected):
            raise ValueError('The persisted roster and current CAS household differ; no capture published.')
        actors = []
        for member in members:
            sid = member['sim_id']; generation = expected[sid]['graph_generation']
            ids = sorted(owner['owner_id'] for owner in member['owners'])
            kinds = {owner['owner_id']:owner['native_kind'] for owner in member['owners']}
            owners = []; after = ''; start = 0
            while start < len(ids):
                page = native(dict(operation='usage-owner-page',scope_id=status['scope_id'],sim_id=sid,
                                   expected_generation=generation,after_owner_id=after))
                if (page.get('source') != 'committed-equipped-references' or page.get('pid') != status['pid'] or
                        page.get('scope_id') != status['scope_id'] or page.get('sim_id') != sid or
                        page.get('generation') != generation or page.get('total_owners') != len(ids) or
                        page.get('start_index') != start or page.get('after_owner_id') != after or
                        page.get('appearance_written') is not False or page.get('model_harvested') is not False or
                        page.get('game_files_written') is not False or len(page.get('owners',[])) != 1):
                    raise ValueError('The compact page differs from its exact read-only owner scope.')
                row = page['owners'][0]; oid = ids[start]
                if (set(row) != {'owner_id','native_kind','revision','outfits'} or row['owner_id'] != oid or
                        row['native_kind'] != kinds[oid]):
                    raise ValueError('Compact page skipped, replayed or changed a form owner.')
                owners.append(dict(owner_id=oid,form=form_label(oid,kinds[oid]),outfits=row['outfits']))
                start += 1; after = oid
                complete = start == len(ids)
                if page.get('complete') is not complete or page.get('next_owner_id') != (None if complete else oid):
                    raise ValueError('Compact page continuation is incomplete or inconsistent.')
            actors.append(dict(sim_id=sid,name=labels[sid],generation=generation,owners=owners))
        final = native({'operation':'status'})
        observed = {row['sim_id']:row for row in final['members']}
        if (final['pid'] != status['pid'] or final['scope_id'] != status['scope_id'] or set(observed) != set(expected) or
                any(observed[sid]['graph_generation'] != expected[sid]['graph_generation'] for sid in expected) or
                call('catalog_actor_roster', argument) != roster):
            raise ValueError('The household changed during capture; no stale snapshot published.')
        value = dict(schema=1,catalog_sha256=catalog_sha256,save_guid=save_guid,
            captured_at=int(time.time()*1000),source='native-cas-committed',source_epoch=status['scope_id'],
            complete=True,households=[dict(household_id=household_id,name=roster['name'],members=actors)])
        write_json(output, value)
    return dict(ok=True,output=str(output),sha256=sha256(output),sims=len(actors),
                bytes=output.stat().st_size,appearance_written=False,assets_exported=False,
                freshness='Explicit committed CAS snapshot; refresh after edits. Names are persisted metadata.')
