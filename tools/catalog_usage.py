"""Explicit, paged equipped references; no appearance/mesh export files.

A changed graph or roster invalidates the complete job. Capture never selects
a household member, switches an occult, equips a part or accepts/saves CAS.
"""
import json
import time
from pathlib import Path

KINDS = {1:'Human',2:'Alien',4:'Vampire',8:'Mermaid',16:'Spellcaster',32:'Werewolf',64:'Fairy'}
SPECIAL = {'imaginary_friend':'Imaginary Friend','plantsim':'PlantSim','servo':'Servo',
           'ghost':'Ghost','reaper':'Reaper','skeleton':'Skeleton','scarecrow':'Scarecrow',
           'human':'Human','alien':'Alien','vampire':'Vampire','mermaid':'Mermaid',
           'witch':'Spellcaster','werewolf':'Werewolf','fairy':'Fairy'}


def form_label(owner_id, kind):
    return SPECIAL.get(owner_id.split('/',1)[0], KINDS[kind])


def roster_identity(value):
    # Request UUID/state are transport acknowledgements, not roster freshness.
    keys=('schema','pid','save_guid','household_id','name','members','names_source',
          'appearance_written','save_submitted')
    return {key:value[key] for key in keys}


def equipped_outfits(fields):
    """Project existing detached outfit bytes, never call a game getter.

    Full DTOs are transient transport data only. The output contains IDs and
    labels, with no appearance payloads, meshes or textures written to disk.
    """
    import struct
    import sys
    source=str(Path(__file__).resolve().parents[1]/'Source')
    if source not in sys.path:sys.path.insert(0,source)
    from apex_core.form_appearance import decode
    from apex_core.outfit_snapshot import field, varint
    raw=decode(fields['__outfits__'])[1]
    def walk(data):
        at=0
        while at<len(data):
            start=at;n,k,at,value=field(data,at)
            if k==1:
                _,offset=varint(data,start);value=struct.unpack_from('<Q',data,offset)[0]
            yield n,k,value
    def array(data,fixed=False):
        rows=[]
        for n,k,v in walk(data):
            if n!=1:continue
            if k==(1 if fixed else 0):rows.append(v)
            elif k==2:
                if fixed:
                    if len(v)%8:raise ValueError('Misaligned equipped CASP identities.')
                    rows.extend(x[0] for x in struct.iter_unpack('<Q',v))
                else:
                    at=0
                    while at<len(v):x,at=varint(v,at);rows.append(x)
            else:raise ValueError('Unsupported equipped parallel array encoding.')
            if len(rows)>4096:raise ValueError('Equipped array exceeds its bound.')
        return rows
    outfits=[];ordinals={};count=0
    for n,k,v in walk(raw):
        if n!=1:continue
        if k!=2 or len(outfits)>=128:raise ValueError('Equipped outfit inventory differs.')
        values={};seen=set()
        for number,kind,value in walk(v):
            if number not in (1,2,5,7,15):continue
            if number in seen or kind!=(0 if number in (1,2) else 2):raise ValueError('Ambiguous equipped outfit field.')
            seen.add(number);values[number]=value
        category=values.get(2,0);ordinal=ordinals.get(category,0);ordinals[category]=ordinal+1
        ids=array(values.get(5,b''),True);bodies=array(values.get(7,b''));layers=array(values.get(15,b''))
        if category>255 or len(ids)!=len(bodies) or len(layers) not in (0,len(ids)):
            raise ValueError('Equipped part/body/layer arrays differ.')
        parts=[]
        for i,ident in enumerate(ids):
            if ident==0 or bodies[i]>=2**32 or layers and layers[i]>=2**32:raise ValueError('Invalid equipped CASP row.')
            parts.append(dict(instance=str(ident),body_type=bodies[i],layer=layers[i] if layers else None))
        count+=len(parts)
        if count>16384:raise ValueError('Equipped owner exceeds its reference bound.')
        outfits.append(dict(category=category,ordinal=ordinal,outfit_id=str(values.get(1,0)),parts=parts))
    return outfits


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
                page = native(dict(operation='export-owner-page',scope_id=status['scope_id'],sim_id=sid,
                                   expected_generation=generation,after_owner_id=after))
                if (page.get('source') != 'committed-native-appearance' or page.get('pid') != status['pid'] or
                        page.get('scope_id') != status['scope_id'] or page.get('sim_id') != sid or
                        page.get('generation') != generation or page.get('total_owners') != len(ids) or
                        page.get('start_index') != start or page.get('after_owner_id') != after or
                        page.get('appearance_written') is not False or page.get('model_harvested') is not False or
                        page.get('game_files_written') is not False or not 1<=len(page.get('owners',[]))<=8 or
                        page.get('owner_appearance_query')!='returned-value'):
                    raise ValueError('The compact page differs from its exact read-only owner scope.')
                decoded={o['owner_id']:o for o in page['owner_appearances']}
                if len(decoded)!=len(page['owners']):raise ValueError('Detached equipped owner inventory differs.')
                for row in page['owners']:
                    if start>=len(ids):raise ValueError('Equipped page exceeds its complete owner inventory.')
                    oid=ids[start];dto=decoded.get(oid)
                    if (row['owner_id']!=oid or row['native_kind']!=kinds[oid] or dto is None or
                            dto['native_kind']!=kinds[oid] or dto['native_sha256']!=row['sha256']):
                        raise ValueError('Equipped page skipped, replayed or changed a form owner.')
                    owners.append(dict(owner_id=oid,form=form_label(oid,kinds[oid]),outfits=equipped_outfits(dto['fields'])))
                    start+=1;after=oid
                complete = start == len(ids)
                if page.get('complete') is not complete or page.get('next_owner_id') != (None if complete else after):
                    raise ValueError('Compact page continuation is incomplete or inconsistent.')
            actors.append(dict(sim_id=sid,name=labels[sid],generation=generation,owners=owners))
        final = native({'operation':'status'})
        observed = {row['sim_id']:row for row in final['members']}
        if (final['pid'] != status['pid'] or final['scope_id'] != status['scope_id'] or set(observed) != set(expected) or
                any(observed[sid]['graph_generation'] != expected[sid]['graph_generation'] for sid in expected) or
                roster_identity(call('catalog_actor_roster', argument)) != roster_identity(roster)):
            raise ValueError('The household changed during capture; no stale snapshot published.')
        value = dict(schema=1,catalog_sha256=catalog_sha256,save_guid=save_guid,
            captured_at=int(time.time()*1000),source='native-cas-committed',source_epoch=status['scope_id'],
            complete=True,households=[dict(household_id=household_id,name=roster['name'],members=actors)])
        with output.open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    return dict(ok=True,output=str(output),sha256=sha256(output),sims=len(actors),
                bytes=output.stat().st_size,appearance_written=False,assets_exported=False,
                freshness='Explicit committed CAS snapshot; refresh after edits. Names are persisted metadata.')
