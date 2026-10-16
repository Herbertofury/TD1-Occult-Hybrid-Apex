"""Complete native household records and disposable Tray round trips."""
import base64
import hashlib
import json
from pathlib import Path
import struct
import uuid
import zipfile
import math
import time
import reusable_profile
import tray_library
from live_color_probe import chunks
from source_manifest import write_json


def varint(value):
    if type(value) is not int or not 0 <= value < 1 << 64:
        raise ValueError('Native unsigned protobuf integer required.')
    raw=bytearray()
    while value>127:raw.append((value&127)|128);value>>=7
    raw.append(value);return bytes(raw)


def blob(number,value):return varint((number<<3)|2)+varint(len(value))+value
def integer(number,value):return varint(number<<3)+varint(value)


def replace(raw,changes,drop=()):
    result=[];done=set()
    for n,k,v,wire in chunks(raw):
        if n in drop:continue
        if n in changes:
            if n not in done:result.extend(changes[n]);done.add(n)
        else:result.append(wire)
    for n in sorted(set(changes)-done):result.extend(changes[n])
    return b''.join(result)


def build(template,metadata,records,item_id,name):
    if not isinstance(name,str) or not 1<=len(name)<=256 or type(item_id)is not int or not 0<item_id<1<<64:
        raise ValueError('Explicit native item identity/name required.')
    old=tray_library.sims(template)
    if old['version']!=2:raise ValueError('Current verified v2 native export template required.')
    sims=[];ids=[]
    for row in records:
        raw=base64.b64decode(row['native_sim'],validate=True)
        if hashlib.sha256(raw).hexdigest()!=row['native_sha256']:raise ValueError('Complete native Sim bytes differ.')
        identity=[w[-8:] for n,k,v,w in chunks(raw) if n==1 and k==1]
        if len(identity)!=1 or int.from_bytes(identity[0][-8:],'little')!=int(row['sim_id']):raise ValueError('Native Sim identity differs.')
        sims.append(raw);ids.append(int(row['sim_id']))
    if not 1<=len(sims)<=8 or len(set(ids))!=len(ids):raise ValueError('Bounded unique household roster required.')
    extent=struct.unpack_from('<I',template,12)[0];payload=template[16:16+extent];footer=template[16+extent:]
    if len(footer)!=5 or footer[-1:]!=b'\0' or struct.unpack_from('<I',footer)[0]!=len(old['sims']):
        raise ValueError('Native member-count footer differs; no guessed export generated.')
    body=[v for n,k,v,w in chunks(payload) if n==1 and k==2]
    if len(body)!=1:raise ValueError('Native household container differs.')
    household=replace(body[0],{2:[integer(2,item_id)],3:[blob(3,name.encode('utf-8'))],6:[blob(6,s) for s in sims]})
    payload=replace(payload,{1:[blob(1,household)],3:[integer(3,ids[0])]})
    raw=struct.pack('<IIII',2,16+len(payload)+5-4,0,len(payload))+payload+struct.pack('<I',len(sims))+b'\0'
    if tray_library.sims(raw)['sims']!=[base64.b64encode(s).decode('ascii') for s in sims]:raise ValueError('Native member export failed exact readback.')
    version,size=struct.unpack_from('<II',metadata)
    if version!=0 or size!=len(metadata)-8:raise ValueError('Current native metadata template required.')
    # Metadata remains local: no remote Gallery identity or copied portraits.
    specific=[v for n,k,v,w in chunks(metadata[8:]) if n==10 and k==2]
    if len(specific)!=1:raise ValueError('Native household metadata absent or ambiguous.')
    hh=[v for n,k,v,w in chunks(specific[0]) if n==2 and k==2]
    if len(hh)!=1:raise ValueError('Native household-specific metadata absent.')
    hh=replace(hh[0],{1:[integer(1,len(sims))]},drop=(2,))
    specific=replace(specific[0],{2:[blob(2,hh)]})
    meta=replace(metadata[8:],{1:[integer(1,item_id)],4:[blob(4,name.encode('utf-8'))],10:[blob(10,specific)]},drop=(3,20))
    meta=struct.pack('<II',0,len(meta))+meta
    return raw,meta


def execute(args):
    from apex_cli import owned_request,require_isolated
    require_isolated(args.state)
    settle=getattr(args,'settle_seconds',3)
    if not isinstance(settle,(int,float)) or not math.isfinite(settle) or not .1<=settle<=30:
        raise ValueError('Use .1 through 30 finite simulation seconds for queued spawns.')
    if args.operation=='export-tray':
        raise ValueError('Native Library metadata/portrait generation remains unverified. Use export-records for an external snapshot archive; no candidate can be installed into Tray.')
    _,journal,active,original=reusable_profile.load(args.state)
    if args.values is None or args.values.stat().st_size>4096:raise ValueError('Bounded explicit household JSON values required.')
    values=json.loads(args.values.read_text(encoding='utf-8'))
    if not isinstance(values,dict):raise ValueError('Typed household values required.')
    output=reusable_profile.writable(args.output) if args.output else None
    if output is not None and (output.exists() or output.suffix.lower()!='.json' or any(output==p or p in output.parents for p in (active,original))):
        raise ValueError('Use one new external household receipt outside both profiles.')
    action={'capabilities':'test_household_capabilities','records':'test_household_records','load-tray':'test_household_import','export-records':'test_household_records','recover-import':'test_household_recover_import','finish-import':'test_household_finish_import'}[args.operation]
    if args.operation=='export-records':
        if args.template is None or args.name is None or args.archive is None:raise ValueError('Select an explicit native template, new name and new external review ZIP. Generated candidates cannot be installed into Tray.')
        archive=reusable_profile.writable(args.archive)
        if archive.exists() or archive.suffix.lower()!='.zip' or any(archive==p or p in archive.parents for p in (active,original)):
            raise ValueError('Use a new external review ZIP outside both profiles; no generated files are staged into the game library.')
        template=reusable_profile.writable(args.template)
        if template.parent!=active/'Tray' or template.suffix.lower()!='.trayitem':raise ValueError('Use the marked profile\'s exact existing native Tray template.')
        group=tray_library.groups(template.parent).get(template.name)
        binaries=[p for p in group or () if p.suffix.lower()=='.householdbinary']
        if len(binaries)!=1:raise ValueError('Native template household group is ambiguous.')
        template_raw=tray_library.read(binaries[0]);metadata_raw=tray_library.read(template)
    if args.operation=='load-tray' and args.source_file is not None:
        source=Path(args.source_file).absolute()
        if source.name!=values.get('filename') or source.suffix.lower()!='.householdbinary':raise ValueError('Exact external native source filename required.')
        raw=tray_library.read(source)
        if hashlib.sha256(raw).hexdigest()!=values.get('sha256'):raise ValueError('External source hash differs; no load submitted.')
        values=dict(values,external_file=str(source))
    result=owned_request(args.state,action,args.sim_id,value=json.dumps(dict(test_token=journal['token'],value=values)))
    if args.operation=='load-tray' and result.get('ok') and result.get('pending'):
        # Creation is never repeated. Let the already queued native spawns run,
        # pause again, then submit one read-only completion with its exact WAL.
        pending=dict(result);pending['lifecycle_requests']=[]
        def event(action,argument):
            def intent(command,request_id):
                pending['lifecycle_requests'].append(dict(action=command,request_id=request_id))
                if output is not None:write_json(output,pending)
            return owned_request(args.state,action,args.sim_id,value=json.dumps(dict(test_token=journal['token'],value=argument)),submission_observer=intent)
        if output is not None:write_json(output,pending)
        try:
            played=event('test_play',None)
            if not played.get('ok'):raise ValueError('Queued spawn simulation did not start; retain the original import.')
            time.sleep(settle)
        finally:
            paused=event('test_pause',None)
            if not paused.get('ok'):raise ValueError('Queued spawn pause failed; retain its IDs and lifecycle receipt.')
        completion=dict(household_id=values['household_id'],save_guid=values['save_guid'],journal_sha256=pending['journal_sha256'])
        result=event('test_household_finish_import',completion)
        result['creation_receipt']=pending
    if result.get('ok') and args.operation=='export-records':
        identifier=int(uuid.uuid4().hex[:14],16)
        raw,meta=build(template_raw,metadata_raw,result['sims'],identifier,args.name)
        prefix='!0x'+format(identifier,'016x')
        names=['0x00000001'+prefix+'.trayitem','0x00000000'+prefix+'.householdbinary']
        # This is a native-record snapshot, not a generated Gallery item.
        # Incomplete metadata/portraits must never reach the game's reader.
        payloads={names[1]:raw}
        manifest=dict(schema=1,status='unverified-native-record-candidate',native_game_library_acceptance=False,
            files={n:hashlib.sha256(v).hexdigest() for n,v in payloads.items()})
        with archive.open('xb') as stream:
            with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
                for name,data in payloads.items():z.writestr(name,data)
                z.writestr('ApexHouseholdCandidate.json',json.dumps(manifest,sort_keys=True))
        result.update(trayitem=None,household_file=names[1],household_sha256=hashlib.sha256(raw).hexdigest(),
            archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            sims_written=len(result['sims']),images_written=0,existing_files_overwritten=False,
            game_library_files_written=False,native_game_library_acceptance=False)
    if output is not None:write_json(output,result)
    return result
