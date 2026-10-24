"""Typed native Tray household loading in the marked disposable profile.

Native Sim protobufs stay complete. New identities are allocated before clone
loading; original household members are never removed or used as destinations.
"""
import base64
import hashlib
import inspect
import json
import re
import os
from pathlib import Path
from . import form_appearance as appearance, occult_add_guard, outfit_snapshot, sim_record, studio, hybrid_persistence, native_occult_context
from .overlay_loader import _unlinked


def chunks(raw):
    offset=0
    while offset<len(raw):
        number,kind,end,value=outfit_snapshot.field(raw,offset)
        yield number,kind,value
        offset=end


def tray_sims(raw):
    import struct
    if not 8<=len(raw)<=16*1024*1024:raise ValueError('Bounded native Tray household required.')
    version,size=struct.unpack_from('<II',raw)
    if version not in (1,2) or size!=len(raw)-4:raise ValueError('Verified native Tray household envelope required.')
    payload=raw[8:]
    if version==2:
        if len(raw)<16:raise ValueError('Truncated native Tray household.')
        reserved,length=struct.unpack_from('<II',raw,8)
        if reserved or length>len(raw)-16 or len(raw)-16-length>4096:raise ValueError('Native household extent differs.')
        payload=raw[16:16+length]
    bodies=[v for n,k,v in chunks(payload) if n==1 and k==2]
    if len(bodies)!=1:raise ValueError('Native Tray household absent or ambiguous.')
    sims=[v for n,k,v in chunks(bodies[0]) if n==6 and k==2]
    if not 1<=len(sims)<=8 or sum(map(len,sims))>8*1024*1024:raise ValueError('Native household member count/extent exceeds its bound.')
    return sims


def context(backend,request):
    if not isinstance(request,dict) or not all(k in request for k in ('household_id','save_guid')):
        raise ValueError('Exact household/save identity required.')
    household=backend.services.active_household()
    guid=str(backend.services.get_persistence_service().get_save_slot_proto_guid())
    if household is None or str(household.id)!=request['household_id'] or guid!=request['save_guid']:
        raise ValueError('Household/save changed; no household operation submitted.')
    return household


def capabilities(backend,request):
    household=context(backend,request)
    from sims.sim_info import SimInfo
    from sims.sim_spawner import SimSpawner
    names={}
    for name,method in [('constructor',SimInfo),('clone_load',SimInfo.load_sim_info),
            ('household_add',household.add_sim_info),('manager_add',backend.services.sim_info_manager().add),
            ('spawn',SimSpawner.spawn_sim)]:
        try:names[name]=str(inspect.signature(method))
        except (TypeError,ValueError):names[name]=None
    return dict(ok=True,household_id=str(household.id),members=[str(s.id) for s in household.sim_info_gen()],
                native_api=names,game_appearance_written=False)


def records(backend,request):
    if set(request)!={'household_id','save_guid','sim_ids'}:raise ValueError('Exact household/member inventory required.')
    household=context(backend,request);members=list(household.sim_info_gen())
    if sorted(request['sim_ids'])!=sorted(str(s.id) for s in members) or len(set(request['sim_ids']))!=len(members):
        raise ValueError('Household member inventory changed; no incomplete export accepted.')
    before=[(s,appearance.packed(backend,s),dict(backend._form_map(s.occult_tracker)),
        [(o,appearance.packed(backend,o)) for o in backend._form_map(s.occult_tracker).values()]) for s in members]
    rows=[]
    for sim in members:
        record=sim_record.restore(studio._capture_native_record(backend,sim))
        rows.append(dict(sim_id=str(sim.id),native_sim=record['native_base64'],native_sha256=record['native_sha256']))
    for sim,fields,mapping,owners in before:
        current=backend._form_map(sim.occult_tracker)
        if (appearance.packed(backend,sim)!=fields or set(current)!=set(mapping) or
                any(current[k] is not v for k,v in mapping.items()) or
                any(appearance.packed(backend,o)!=old for o,old in owners)):
            raise ValueError('Native household serialization changed an appearance; no export accepted.')
    return dict(ok=True,household_id=str(household.id),save_guid=request['save_guid'],sims=rows,
                game_appearance_written=False,save_file_written=False)


def recover_import(backend,request):
    """Retire a failed import only after its allocations are absent natively.

    Recovery archives the journal. It never removes a Sim, edits an existing
    appearance, restores a save, or retries a partially registered import.
    """
    if not isinstance(request,dict) or set(request)!={'household_id','save_guid','journal_sha256'} or not re.fullmatch(r'[0-9a-f]{64}',str(request['journal_sha256'])):
        raise ValueError('Exact failed-import journal/hash and save identity required.')
    household=context(backend,request)
    path=_unlinked(Path(backend._data_directory())/'household_tray_import.json')
    if not path.is_file() or path.stat().st_size>32*1024*1024:raise ValueError('Bounded failed-import journal required.')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=request['journal_sha256']:raise ValueError('Failed-import journal changed; no recovery acknowledged.')
    proof=json.loads(raw.decode('utf-8'))
    if proof.get('stage')!='recovery-required' or any(proof.get(n)!=request[n] for n in ('household_id','save_guid')):
        raise ValueError('Failed import belongs to another save or has no unresolved recovery.')
    members=sorted(str(s.id) for s in household.sim_info_gen())
    if members!=sorted(proof['original_members']):raise ValueError('Household still differs from its original roster; no recovery acknowledged.')
    manager=backend.services.sim_info_manager();persistence=backend.services.get_persistence_service()
    allocated=list(proof['identity_map'].values())
    if any(manager.get(int(i)) is not None or persistence.get_sim_proto_buff(int(i)) is not None for i in allocated):
        raise ValueError('Failed import allocations still exist; normal unsaved reload is required before recovery.')
    archive=_unlinked(path.with_name('household_tray_import.'+request['journal_sha256']+'.recovered.json'))
    if archive.exists():
        if archive.read_bytes()!=raw:raise ValueError('Recovery archive differs; no journal overwritten.')
    else:
        with archive.open('xb') as stream:
            stream.write(raw);stream.flush()
            import os
            os.fsync(stream.fileno())
    occult_add_guard.publish(path,dict(schema=1,stage='recovered-original-members-only',household_id=request['household_id'],
        save_guid=request['save_guid'],original_members=members,archived_journal=str(archive),archived_sha256=request['journal_sha256']))
    return dict(ok=True,allocated_sim_ids_absent=allocated,original_members=members,archived_sha256=request['journal_sha256'],
        sim_removed=False,appearance_written=False,save_file_written=False,import_replayed=False)


def _remap(message,mapping,path=()):
    # Limit remapping to schema-declared Sim references. A matching CASP,
    # outfit, resource or object ID must never be rewritten by coincidence.
    for field,value in message.ListFields():
        child_path=path+(field.name,)
        if field.type==11:
            for child in value if field.label==3 else (value,):_remap(child,mapping,child_path)
        elif field.type in (4,6) and (field.name in ('sim_id','sim_id_a','sim_id_b','sim_ids','spouse','significant_other','fiance','mother','father','previous_sim_id') or
                field.name=='ids' and any('genealogy' in p or 'sim_ids'==p for p in path) or
                field.name=='target_id' and any('relationship' in p for p in path)):
            if field.label==3:
                for i,v in enumerate(value):
                    if int(v) in mapping:value[i]=mapping[int(v)]
            elif int(value) in mapping:setattr(message,field.name,mapping[int(value)])


def validate_loaded(backend,sim,proto):
    observed=appearance.packed(backend,sim);expected={}
    descriptors=proto.DESCRIPTOR.fields_by_name
    for name in appearance.FIELDS:
        source='facial_attr' if name=='facial_attributes' and 'facial_attr' in descriptors else name
        if source not in descriptors or name not in observed:continue
        value=getattr(proto,source)
        if name=='parts_custom_tattoos':
            if any(not row.HasField('body_type') or not row.HasField('texture_id') for row in value):
                raise ValueError('Incomplete native custom tattoo record.')
            mapping={int(row.body_type):int(row.texture_id) for row in value}
            if len(mapping)!=len(value):raise ValueError('Ambiguous native custom tattoo record.')
            value=mapping
        elif hasattr(value,'SerializeToString'):
            raw=value.SerializeToString()
            if observed[name]['kind']=='bytes':value=raw
            elif observed[name]['kind']=='protobuf':value=('protobuf',raw)
            else:raise ValueError('Native appearance protobuf getter contract differs: '+name)
        expected[name]=appearance.encode(value)
    expected['__outfits__']=appearance.encode(('protobuf',proto.outfits.SerializeToString()))
    actual={name:observed.get(name) for name in expected}
    if appearance.fingerprint(actual)!=appearance.fingerprint(expected) or sim.flags!=proto.flags:
        error=ValueError('Native clone changed base appearance: '+', '.join(name for name in expected if actual[name]!=expected[name]))
        error.appearance_diagnostics=dict(expected=expected,observed=actual)
        raise error
    tracker_record=proto.attributes.occult_tracker
    wanted=list(tracker_record.occult_sim_infos);form_map=backend._form_map(sim.occult_tracker)
    if set(int(k) for k in form_map)!=set(int(row.occult_type) for row in wanted):
        raise ValueError('Native clone changed the stored occult owner inventory.')
    for row in wanted:
        try:hybrid_persistence._stored_core(backend,form_map[backend._coerce_flags(row.occult_type)],row)
        except ValueError as error:
            detail=getattr(error,'appearance_diagnostics',{})
            detail.update(form=int(row.occult_type),sim_id=str(sim.id))
            error.appearance_diagnostics=detail
            raise
    if (backend._get_occult_flags(sim)!=int(tracker_record.occult_types) or
            backend._get_current_flags(sim)!=int(tracker_record.current_occult_types)):
        raise ValueError('Native clone changed occult membership or active form.')


def restore_clone_appearance(backend,sim,proto):
    """The immutable source owns this newly allocated clone only.

    Native load can regenerate stored genetics while loading outfits. Restore
    the source after load, then require complete represented-field readback.
    This path never restores an existing destination or consults old banks.
    """
    mapping=backend._form_map(sim.occult_tracker)
    records=list(proto.attributes.occult_tracker.occult_sim_infos)
    if set(int(k) for k in mapping)!=set(int(r.occult_type) for r in records):
        raise ValueError('Native clone owner inventory differs; no source appearance guessed.')
    wrappers=[sim]+list(mapping.values())
    bases=[getattr(o,'_base',o) for o in wrappers]
    if any(a is b for i,a in enumerate(bases) for b in bases[i+1:]):
        raise ValueError('Native clone appearances alias; no source fields written.')
    # Base SimData uses facial_attr; the stored occult schema uses
    # facial_attributes. Preserve the actual descriptor contract for both.
    active={}
    descriptors=proto.DESCRIPTOR.fields_by_name
    for name in appearance.FIELDS:
        source='facial_attr' if name=='facial_attributes' and 'facial_attr' in descriptors else name
        if source not in descriptors:continue
        value=getattr(proto,source)
        if name=='parts_custom_tattoos':value={int(r.body_type):int(r.texture_id) for r in value}
        elif hasattr(value,'SerializeToString'):
            kind=appearance.packed(backend,sim).get(name,{}).get('kind')
            raw=value.SerializeToString();value=('protobuf',raw) if kind=='protobuf' else raw
        active[name]=appearance.encode(value)
    active['__outfits__']=appearance.encode(('protobuf',proto.outfits.SerializeToString()))
    targets=[(sim,active,proto.flags)]
    for record in records:
        owner=mapping[backend._coerce_flags(record.occult_type)]
        targets.append((owner,hybrid_persistence._record_payload(record,appearance.packed(backend,owner)),record.flags))
    for _ in range(2):
        for owner,expected,flags in targets:
            observed=appearance.packed(backend,owner)
            wanted_hashes=appearance.fingerprint(expected)['field_sha256']
            observed_hashes=appearance.fingerprint(observed)['field_sha256']
            changes={n:v for n,v in expected.items() if observed_hashes.get(n)!=wanted_hashes[n]}
            if owner.flags!=flags:changes['flags']=appearance.encode(int(flags))
            if changes:
                values={n:appearance.decode(v) for n,v in changes.items()}
                from .native_occult_context import appearance_write
                appearance_write(backend,sim,owner,lambda:backend._restore_siminfo_payload(owner,values))
        tracker=proto.attributes.occult_tracker
        if backend._get_occult_flags(sim)!=int(tracker.occult_types):
            backend._set_flags(sim,'occult_types',int(tracker.occult_types))
        if backend._get_current_flags(sim)!=int(tracker.current_occult_types):
            backend._set_flags(sim,'current_occult_types',int(tracker.current_occult_types))
        try:validate_loaded(backend,sim,proto);return
        except ValueError:
            if _==1:raise


def register_clone(manager,sim):
    # EA's native Ghost/load path can register the exact clone during load.
    # Admit that identity once; a different object at the allocated ID remains
    # an error. Never substitute an existing Sim or call add twice.
    existing=manager.get(sim.id)
    if existing is None:manager.add(sim)
    elif existing is not sim:raise ValueError('Allocated clone ID belongs to another object; no member added.')
    if manager.get(sim.id) is not sim:raise ValueError('Native clone registration did not retain its exact object.')


def finish_import(backend,request):
    """Finish queued spawns and retain captured availability; no recreation."""
    if not isinstance(request,dict) or set(request)!={'household_id','save_guid','journal_sha256'}:
        raise ValueError('Exact pending import journal and save identity required.')
    household=context(backend,request)
    path=_unlinked(Path(backend._data_directory())/'household_tray_import.json')
    if not path.is_file() or path.stat().st_size>32*1024*1024:raise ValueError('Bounded pending import required.')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=request['journal_sha256']:raise ValueError('Pending import changed; no completion submitted.')
    proof=json.loads(raw.decode('utf-8'))
    if proof.get('stage')!='awaiting-spawn' or proof.get('runtime_pid')!=os.getpid() or any(proof.get(k)!=request[k] for k in ('household_id','save_guid')):
        raise ValueError('Import has no current-runtime pending spawn; do not recreate members.')
    manager=backend.services.sim_info_manager()
    expected=proof['original_members']+proof['created']
    if sorted(str(s.id) for s in household.sim_info_gen())!=sorted(expected):raise ValueError('Pending household membership changed.')
    from .test_driver import persistence_evidence
    from protocolbuffers import FileSerialization_pb2
    observed=[]
    for blob in proof['source_sims']:
        proto=FileSerialization_pb2.SimData();proto.ParseFromString(base64.b64decode(blob,validate=True))
        mapping={int(k):int(v) for k,v in proof['identity_map'].items()}
        _remap(proto,mapping);proto.household_id=household.id
        if hasattr(proto,'account_id'):proto.account_id=household.account.id
        sim=manager.get(proto.sim_id)
        if sim is None or str(sim.id) not in proof['created']:raise ValueError('An allocated clone is absent; no spawn replayed.')
        evidence=persistence_evidence(backend,sim,household)
        ready=sim.get_sim_instance() is not None and evidence['persistence_verified_before_save']
        observed.append(dict(sim_id=str(sim.id),instanced=sim.get_sim_instance() is not None,persistence=evidence))
        if not ready:
            return dict(ok=True,pending=True,stage='awaiting-spawn',journal_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                created_sim_ids=proof['created'],spawn_observations=observed,unpause_required=True,creation_replayed=False)
        checkpoint=proof.get('native_contexts',{}).get(str(sim.id))
        if checkpoint is None:raise ValueError('No complete pre-startup native form context; availability is not guessed.')
        current=native_occult_context.capture(backend,sim)
        if current!=checkpoint:
            # EA startup can narrow availability to Witch even while retaining
            # every trait and stored appearance. Restore only this immutable
            # same-runtime native context, with a durable mutation intent.
            proof.update(stage='restoring-startup-context',context_owner=str(sim.id),context_before=current)
            occult_add_guard.publish(path,proof)
            restored=native_occult_context.restore(backend,sim,checkpoint)
            native_occult_context.verify(checkpoint,restored['after'],str(proto.attributes.occult_tracker.current_occult_types))
            proof.setdefault('context_restores',[]).append(dict(sim_id=str(sim.id),receipt=restored))
            proof['stage']='awaiting-spawn';occult_add_guard.publish(path,proof)
        try:validate_loaded(backend,sim,proto)
        except Exception as error:
            proof.update(stage='recovery-required',error=str(error)[:2048],readback=getattr(error,'appearance_diagnostics',None))
            occult_add_guard.publish(path,proof);raise
    proof.update(stage='verified',spawn_observations=observed);occult_add_guard.publish(path,proof)
    return dict(ok=True,pending=False,household_id=str(household.id),identity_map=proof['identity_map'],
        created_sim_ids=proof['created'],native_instances_verified=True,spawn_observations=observed,
        save_file_written=False,save_reload_verified=False,source_file_written=False,creation_replayed=False)


def import_tray(backend,request,profile):
    required={'household_id','save_guid','filename','sha256','source_sim_ids'}
    if not isinstance(request,dict) or set(request) not in (required,required|{'external_file'}) or not isinstance(request['filename'],str) or not re.fullmatch(r'0x[0-9a-fA-F]{8}!0x[0-9a-fA-F]{16}\.householdbinary',request['filename']):
        raise ValueError('One exact native Tray household and source inventory required.')
    if not isinstance(request['sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',request['sha256']):raise ValueError('Exact Tray source hash required.')
    if not isinstance(request['source_sim_ids'],list) or not 1<=len(request['source_sim_ids'])<=8 or any(not isinstance(i,str) or not re.fullmatch(r'[1-9][0-9]{0,19}',i) or int(i)>=1<<64 for i in request['source_sim_ids']):
        raise ValueError('Bounded explicit source Sim identities required.')
    household=context(backend,request)
    if 'external_file' in request:
        value=request['external_file']
        if not isinstance(value,str) or len(value)>1024 or not Path(value).is_absolute():raise ValueError('One exact absolute external native household source required.')
        path=_unlinked(Path(value))
        if path.name!=request['filename']:raise ValueError('External native source identity differs.')
    else:path=_unlinked(Path(profile)/'Tray'/request['filename'])
    if not path.is_file() or not 16<=path.stat().st_size<=16*1024*1024:raise ValueError('Bounded native Tray file required.')
    before=path.stat();raw=path.read_bytes();after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino) or hashlib.sha256(raw).hexdigest()!=request['sha256']:
        raise ValueError('Tray source changed; no import submitted.')
    from protocolbuffers import FileSerialization_pb2
    from sims.sim_info import SimInfo
    from sims.sim_info_types import Age,Gender,SpeciesExtended
    from sims.sim_info_lod import SimInfoLODLevel
    from sims.sim_spawner import SimSpawner
    import id_generator
    protos=[]
    for blob in tray_sims(raw):
        proto=FileSerialization_pb2.SimData();proto.ParseFromString(blob)
        if not proto.sim_id:raise ValueError('Native source Sim has no identity.')
        protos.append(proto)
    source_ids=[str(p.sim_id) for p in protos]
    if len(set(source_ids))!=len(source_ids) or sorted(source_ids)!=sorted(request['source_sim_ids']):raise ValueError('Source Sim inventory differs; no import submitted.')
    members=list(household.sim_info_gen());manager=backend.services.sim_info_manager()
    if len(members)+len(protos)>8:raise ValueError('Native household has insufficient free slots; no existing Sim removed.')
    mapping={}
    for proto in protos:
        allocated=int(id_generator.generate_object_id())
        if not 0<allocated<1<<64 or allocated in mapping.values() or manager.get(allocated) is not None:raise ValueError('Native allocator returned an existing/reserved identity.')
        mapping[int(proto.sim_id)]=allocated
        inspect.signature(SimInfo).bind(sim_id=allocated,age=Age(proto.age),gender=Gender(proto.gender),species=SpeciesExtended.get_species(proto.extended_species),account=household.account)
        inspect.signature(SimInfo.load_sim_info).bind(None,proto,is_clone=True,default_lod=SimInfoLODLevel.FULL)
    # Durable source bytes and intent are published before any member creation.
    journal=_unlinked(Path(backend._data_directory())/'household_tray_import.json')
    if journal.exists():
        old=json.loads(journal.read_text(encoding='utf-8'))
        if old.get('stage') not in ('verified','preflight-refused','recovered-original-members-only'):raise ValueError('Previous household import is unresolved; retain its allocated identities, do not repeat.')
    proof=dict(schema=1,stage='creating',runtime_pid=os.getpid(),household_id=str(household.id),save_guid=request['save_guid'],source_sha256=request['sha256'],
        identity_map={str(k):str(v) for k,v in mapping.items()},original_members=[str(s.id) for s in members],created=[],
        source_sims=[base64.b64encode(p.SerializeToString()).decode('ascii') for p in protos],native_contexts={})
    occult_add_guard.publish(journal,proof)
    originals=[occult_add_guard.Preservation(backend,s,0) for s in members]
    try:
        for proto in protos:
            source_id=int(proto.sim_id)
            _remap(proto,mapping);proto.sim_id=mapping[source_id]
            proto.household_id=household.id
            if hasattr(proto,'account_id'):proto.account_id=household.account.id
            sim=SimInfo(sim_id=proto.sim_id,age=Age(proto.age),gender=Gender(proto.gender),species=SpeciesExtended.get_species(proto.extended_species),account=household.account)
            proof['created'].append(str(sim.id));occult_add_guard.publish(journal,proof)
            if int(sim.id)!=int(proto.sim_id):raise ValueError('Native constructor allocated a different identity; no clone load submitted.')
            immutable=type(proto)();immutable.CopyFrom(proto)
            sim.load_sim_info(proto,is_clone=True,default_lod=SimInfoLODLevel.FULL)
            restore_clone_appearance(backend,sim,immutable)
            # Validate every represented stored owner before registration and
            # spawning. A loader that silently collapses hybrids is rejected.
            validate_loaded(backend,sim,immutable)
            proof['native_contexts'][str(sim.id)]=native_occult_context.capture(backend,sim)
            occult_add_guard.publish(journal,proof)
            register_clone(manager,sim);household.add_sim_info(sim)
            SimSpawner.spawn_sim(sim)
            client=backend.services.client_manager().get_first_client()
            client.add_selectable_sim_info(sim)
            sim.save_sim();household.save_data()
            validate_loaded(backend,sim,immutable)
        for preservation in originals:preservation.restore(preservation.flags[0],accepted=True)
        observed=[str(s.id) for s in household.sim_info_gen()]
        expected=proof['original_members']+proof['created']
        if sorted(observed)!=sorted(expected) or any(manager.get(int(i)) is None for i in proof['created']):raise ValueError('Created household membership differs; no import completion claimed.')
        proof['stage']='awaiting-spawn';occult_add_guard.publish(journal,proof)
        completion=dict(household_id=str(household.id),save_guid=request['save_guid'],journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest())
        return finish_import(backend,completion)
    except Exception as error:
        proof.update(stage='recovery-required',error=str(error)[:2048],
            readback=getattr(error,'appearance_diagnostics',None))
        occult_add_guard.publish(journal,proof)
        for preservation in originals:preservation.restore(preservation.flags[0],accepted=False)
        raise
