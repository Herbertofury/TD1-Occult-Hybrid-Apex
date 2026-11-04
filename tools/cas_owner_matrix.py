"""Repeat every captured CAS form across a household, retaining exact receipts.

Navigates the existing disposable CAS session; optional unique physique edits
distinguish actual owners from identical templates. It never accepts CAS or
saves. A failed/ambiguous request stops the
run and retains its intent; running this command again is not a recovery step.
"""
import argparse
import copy
import hashlib
import json
import re
import struct
from pathlib import Path

class MatrixStopped(Exception):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf-8')).hexdigest()


def inventory(status):
    if status.get('ok') is not True or status.get('selection_enabled') is not True:
        raise ValueError('The native independent-owner engine is not ready.')
    members=status.get('members'); selected=status.get('selected_native',{})
    if not isinstance(members,list) or not 1<=len(members)<=8 or selected.get('available') is not True:
        raise ValueError('The complete native household/current member is unavailable.')
    ids=set(); result=[]
    for member in members:
        sid=member.get('sim_id'); mask=member.get('owned_mask'); owners=member.get('separate_owners')
        if (not isinstance(sid,str) or not sid.isascii() or not sid.isdecimal() or
                str(int(sid))!=sid or not 0<int(sid)<2**64 or sid in ids or
                type(mask) is not int or not 1<=mask<=127 or member.get('imported_mask')!=mask or
                not isinstance(owners,list) or not owners):
            raise ValueError('Native household identities or imported appearance owners are incomplete.')
        ids.add(sid); seen=set(); copied=[]
        for owner in owners:
            oid=owner.get('owner_id'); kind=owner.get('native_kind')
            if (not isinstance(oid,str) or not oid or oid in seen or
                    type(kind) is not int or kind not in (1,2,4,8,16,32,64) or not mask & kind):
                raise ValueError('Captured form identities are duplicated or have another rendering kind.')
            seen.add(oid); copied.append(dict(owner_id=oid,native_kind=kind))
        result.append(dict(sim_id=sid,owned_mask=mask,owners=copied))
    if selected.get('sim_id') not in ids:
        raise ValueError('The selected member is outside the captured household.')
    return result,selected['sim_id']


def appearance_view(client):
    """Compare every supplied Sim field/panel, including empty equipped panels."""
    rows=client.get('catalogs'); sim=client.get('sim')
    if not isinstance(rows,list) or not isinstance(sim,dict) or not sim:
        raise ValueError('CAS appearance inventory is incomplete.')
    panels={}
    for row in rows:
        name=row.get('panel')
        if not isinstance(name,str) or name in panels or type(row.get('supported')) is not bool:
            raise ValueError('CAS panel inventory is malformed or duplicated.')
        panels[name]=copy.deepcopy({key:row.get(key) for key in
            ('supported','items','preset','preset_query')})
    if not panels:raise ValueError('No equipped CAS panels were observed.')
    return copy.deepcopy(dict(sim=sim,panels=panels,outfit=client.get('outfit'),
        planned_outfits=client.get('planned_outfits'),hair_color=client.get('hair_color'),
        hair_selected_swatch_id=client.get('hair_selected_swatch_id')))


def visible_inventory(member, client):
    """Navigate player-visible forms; keep hidden preimages in the byte audit.

    Rendering kind alone is not a form identity. In particular, a canonical
    native/2 backup must not be visited when CAS exposes active/2 as Alien.
    Discover each member separately rather than assuming identical form menus.
    """
    if not isinstance(client,dict):raise ValueError('A native CAS client observation is required.')
    strip=client.get('form_strip',{})
    if (client.get('sim',{}).get('simId')!=member['sim_id'] or strip.get('sim_id')!=member['sim_id'] or
            strip.get('native_owner_state')!='bound' or strip.get('desired_owner_id') or
            strip.get('gesture_pending') is True):
        raise ValueError('Visible forms require the exact settled household member.')
    groups=strip.get('life_states');captured={o['owner_id']:o for o in member['owners']}
    if not isinstance(groups,list) or not 1<=len(groups)<=64:
        raise ValueError('The current member has no complete visible form catalog.')
    families=set();seen=set();primary=set();owners=[];human=None
    native_families={'human':1,'alien':2,'vampire':4,'mermaid':8,'witch':16,'spellcaster':16,'werewolf':32,'fairy':64}
    for group in groups:
        family=group.get('family') if isinstance(group,dict) else None
        variants=group.get('variants') if isinstance(group,dict) else None
        if (not isinstance(family,str) or not family or family in families or
                not isinstance(variants,list) or not 1<=len(variants)<=1024):
            raise ValueError('Visible form families are missing, duplicated or incomplete.')
        families.add(family)
        if family=='human' and len(variants)!=1:
            raise ValueError('CAS must expose exactly one shared Human form.')
        for variant in variants:
            oid=variant.get('owner_id') if isinstance(variant,dict) else None
            if not isinstance(oid,str) or oid not in captured or oid in seen:
                raise ValueError('A visible form is duplicated or outside this member\'s captured graph.')
            seen.add(oid);owner=captured[oid];kind=owner['native_kind']
            if oid.startswith(('native/','active/')):
                if oid not in ('native/'+str(kind),'active/'+str(kind)) or kind in primary or native_families.get(family)!=kind:
                    raise ValueError('A native backup alias or another family was exposed as a player form.')
                primary.add(kind)
            if family=='human':
                if kind!=1 or oid not in ('native/1','active/1'):
                    raise ValueError('The shared Human is not its exact native appearance.')
                human=oid
            owners.append(copy.deepcopy(owner))
    if human is None or any(member['owned_mask'] & kind and kind not in primary for kind in (2,4,8,16,32,64)):
        raise ValueError('The visible catalog omits the shared Human or an owned actual occult.')
    if strip.get('selected_owner_id') not in seen:
        raise ValueError('The current selected appearance is absent from its visible form catalog.')
    return dict(sim_id=member['sim_id'],owned_mask=member['owned_mask'],owners=owners)


def member_selection_context(client):
    """Use the actual native selector layer, not a rendering-layer alias."""
    if not isinstance(client,dict):raise ValueError('A native CAS client observation is required.')
    sid=client.get('sim',{}).get('simId');observation=client.get('owner_pair_observation',{})
    found=[]
    def walk(value):
        if isinstance(value,dict):
            if value.get('source')=='native-selector-retained-filtered-feed' and value.get('selected_sim_id')==sid:
                if value.get('complete') is not True or type(value.get('selected_layer')) is not int or value['selected_layer'] not in (0,1):
                    raise ValueError('Native member selector is incomplete; no selection sent.')
                found.append(value['selected_layer'])
            for child in value.values():walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    walk(observation)
    if not found or len(set(found))!=1 or type(observation.get('session')) is not int or observation['session']<=0:
        raise ValueError('One exact native member-selector capability is required.')
    return found[0],observation['session']


def physique_markers(members):
    # Observed native CAS readback quantizes the saved three-decimal muscle
    # coefficient, then maps it into the UI range (1/1500 increments).
    # Request representable points; never turn a mismatched edit into success.
    owners=[(m['sim_id'],o['owner_id']) for m in members for o in m['owners']]
    if not owners or len(owners)>1049:
        raise ValueError('This physique marker range cannot distinguish every owner; no edit submitted.')
    def point(n):
        value=(225+round(1050*(n+1)/(len(owners)+1)))/1500
        if value==0.5:return value
        # Native float conversion can land just inside the preceding truncated
        # coefficient. Stay four float ULPs inside the intended bin, away from
        # zero coefficient. This is below the existing 1e-6 readback tolerance;
        # that tolerance and the game's acknowledgement are not changed.
        bits=struct.unpack('<I',struct.pack('<f',value))[0]+(-4 if value<0.5 else 4)
        return struct.unpack('<f',struct.pack('<I',bits))[0]
    result={key:point(n) for n,key in enumerate(owners)}
    if len(set(result.values()))!=len(owners):raise ValueError('Physique markers are not unique.')
    return result


def native_bytes(value,sid,owner,generation):
    """Compare every serialized byte, including unknown future native fields."""
    exported=value.get('owner_export',{})
    if (value.get('ok') is not True or type(exported.get('schema')) is not int or exported['schema']!=1 or
            exported.get('sim_id')!=sid or exported.get('owner_id')!=owner['owner_id'] or
            type(exported.get('native_kind')) is not int or exported['native_kind']!=owner['native_kind'] or
            type(exported.get('generation')) is not int or exported['generation']!=generation or
            exported.get('appearance_written') is not False or exported.get('model_harvested') is not False or
            exported.get('source')!='committed-native-appearance' or
            type(exported.get('bytes')) is not int or not 0<exported['bytes']<=512*1024):
        raise ValueError('Complete native snapshot has another owner, generation or scope.')
    raw=exported.get('native_hex'); expected=exported.get('sha256')
    if (not isinstance(raw,str) or len(raw)!=2*exported['bytes'] or re.fullmatch('[0-9a-f]+',raw) is None or
            not isinstance(expected,str) or re.fullmatch('[0-9a-f]{64}',expected) is None):
        raise ValueError('Complete native snapshot is truncated or noncanonical.')
    decoded=bytes.fromhex(raw)
    if hashlib.sha256(decoded).hexdigest()!=expected:
        raise ValueError('Complete native snapshot bytes differ from their digest.')
    return decoded


def page_index(value,members):
    if (value.get('ok') is not True or value.get('appearance_written') is not False or
            value.get('model_harvested') is not False or value.get('save_submitted') is not False):
        raise ValueError('Complete read-only page export is required.')
    expected={(m['sim_id'],o['owner_id']):o['native_kind'] for m in members for o in m['owners']}
    result={}
    for member in value.get('members',[]):
        sid=member.get('identity',{}).get('sim_id')
        for row in member.get('owners',[]):
            key=(sid,row.get('owner_id'));sha=row.get('sha256')
            if (key not in expected or key in result or type(row.get('native_kind')) is not int or row['native_kind']!=expected[key] or
                    not isinstance(sha,str) or re.fullmatch('[0-9a-f]{64}',sha) is None):
                raise ValueError('Paged matrix snapshot changed or duplicated an exact owner.')
            result[key]=sha
    if set(result)!=set(expected):raise ValueError('Paged matrix snapshot omitted household appearances.')
    return result


def resume_prefix(path,native,members,cycles,edit_markers,verify_native,verify_pages):
    """Recover completed first-cycle evidence only after an explicit non-send.

    Never replay an unresolved request. The only admitted failure happened
    before the Source receiver created a CAS command. Every earlier edit and
    view must still have its exact successful receipt in this runtime/scope.
    """
    from source_manifest import sha256
    path=Path(path);prior=json.loads(path.read_text(encoding='utf-8'))
    refused='Native UI transport has no distributor client; no CAS request sent.'
    if (prior.get('ok') is not False or prior.get('cycles')!=cycles or
            prior.get('targets')!=members or prior.get('differences') or
            prior.get('cas_accept_submitted') is not False or prior.get('save_submitted') is not False or
            prior.get('edit_markers_requested')!=edit_markers or not edit_markers or
            prior.get('native_bytes_requested')!=verify_native or verify_native or
            prior.get('native_pages_requested')!=verify_pages or not verify_pages or
            prior.get('native_page_checkpoints') or not prior.get('error','').endswith(refused)):
        raise ValueError('Only a first-cycle, explicitly unsent transport refusal can resume.')
    receipts={};numbered=[]
    for receipt in path.parent.glob(path.stem+'-*.json'):
        if re.fullmatch(re.escape(path.stem)+r'-[0-9]{4}\.json',receipt.name):
            raw=receipt.read_bytes();receipts[hashlib.sha256(raw).hexdigest()]=json.loads(raw)
            numbered.append(receipt)
    numbered.sort()
    if not numbered:raise ValueError('No original matrix command evidence.')
    first=json.loads(numbered[0].read_text(encoding='utf-8'))
    last=json.loads(numbered[-1].read_text(encoding='utf-8'))
    if (first.get('ok') is not True or first.get('pid')!=native['pid'] or first.get('scope_id')!=native['scope_id'] or
            last.get('ok') is not False or last.get('message')!=refused or last.get('request_state')!='failed' or
            last.get('ui_transition_verified') is not False):
        raise ValueError('The stopped matrix has another runtime/scope or an uncertain last request.')
    expected=[(m['sim_id'],o['owner_id'],o['native_kind']) for m in members for o in m['owners']]
    steps=prior.get('steps');edits=prior.get('marker_edits')
    if (not isinstance(steps,list) or not 0<len(steps)<len(expected) or
            not isinstance(edits,list) or len(edits)!=len(steps)):
        raise ValueError('Only an exact completed first-cycle prefix can resume.')
    baselines={};markers=physique_markers(members)
    for index,(step,edit) in enumerate(zip(steps,edits)):
        sid,oid,kind=expected[index];key=(sid,oid)
        selected=receipts.get(step.get('receipt_sha256'),{})
        receipt=selected.get('native_owner_view_receipt',{})
        edited=receipts.get(edit.get('receipt_sha256'),{})
        if (step.get('cycle')!=0 or (step.get('sim_id'),step.get('owner_id'),step.get('native_kind'))!=(sid,oid,kind) or
                (edit.get('sim_id'),edit.get('owner_id'))!=key or edit.get('requested')!=markers[key] or
                selected.get('ok') is not True or receipt.get('sim_id')!=sid or receipt.get('owner_id')!=oid or
                receipt.get('native_kind')!=kind or receipt.get('independent_undo_bound') is not True or
                edited.get('ok') is not True):
            raise ValueError('A completed matrix step lacks its exact independent edit/view evidence.')
        view=appearance_view(edited['client'])
        observed=view['sim'].get('physiqueValues',[None])[0]
        if (view['sim'].get('simId')!=sid or observed!=edit.get('readback') or
                type(observed) not in (int,float) or abs(observed-markers[key])>0.000001 or
                digest(view)!=step.get('view_sha256')):
            raise ValueError('A retained matrix edit differs from its complete original readback.')
        baselines[key]=view
    return prior,baselines,dict(path=str(path.resolve()),sha256=sha256(path),completed_visits=len(steps),
        last_request_sent=False,runtime_pid=native['pid'],scope_id=native['scope_id'])


def run(state,output,cycles=2,member_ids=None,edit_markers=False,verify_native=False,verify_pages=False,resume=None):
    from apex_cli import execute,parser
    from cli_identity_cache import session
    from source_manifest import write_json,sha256
    state=Path(state); output=Path(output)
    if (type(cycles) is not int or not 2<=cycles<=10 or type(edit_markers) is not bool or
            type(verify_native) is not bool or type(verify_pages) is not bool or
            verify_native and verify_pages or output.exists()):
        raise ValueError('Use 2..10 cycles and one new external proof file.')
    # Existing command evidence validates its outputs against the test profile.
    # The matrix's aggregate proof belongs beside those individual receipts.
    import reusable_profile
    _,_,profile,original=reusable_profile.load(state)
    resolved=output.resolve()
    if any(resolved==p.resolve() or p.resolve() in resolved.parents for p in (profile,original)):
        raise ValueError('Matrix evidence must remain outside both game profiles.')
    proof=dict(schema=1,operation='native-household-all-owner-view-matrix',ok=False,
        cycles=cycles,targets=[],steps=[],differences=[],appearance_edits_submitted=False,
        edit_markers_requested=edit_markers,marker_edits=[],
        native_bytes_requested=verify_native,native_snapshot_count=0,
        native_pages_requested=verify_pages,native_page_checkpoints=[],
        cas_accept_submitted=False,save_submitted=False,complete_native_fields_verified=False,
        complete_native_snapshot_bytes_verified=False,
        production_ready=False)
    stop_file=output.with_suffix('.stop');proof.update(stopped=False,stop_file=str(stop_file))
    write_json(output,proof); sequence=0
    def command(args):
        nonlocal sequence
        if stop_file.exists():raise MatrixStopped('Stopped at a completed command boundary; no request replayed.')
        path=output.with_name(output.stem+'-'+format(sequence,'04d')+'.json');sequence+=1
        if path.exists():raise ValueError('A matrix receipt already exists; do not replay.')
        value=execute(parser().parse_args(args+['--state',str(state),'--output',str(path)]))
        if not path.exists():write_json(path,value)
        value=json.loads(path.read_text(encoding='utf-8'))
        if value.get('ok') is not True:
            raise ValueError('Matrix command failed; retain '+str(path)+': '+str(value.get('message',value.get('error'))))
        return value,path
    try:
        from cas_client import observation_batch
        with session(state),observation_batch(state):
            native,_=command(['game','native-cas-engine','--value',json.dumps(dict(operation='status'))])
            members,sid=inventory(native)
            all_members=copy.deepcopy(members);page_baseline=None
            if member_ids:
                requested=set(member_ids)
                if not requested<={m['sim_id'] for m in members}:raise ValueError('Requested member is absent from the native roster.')
                members=[m for m in members if m['sim_id'] in requested]
            current,_=command(['cas','status','--sim-id',sid,'--seconds','20'])
            household=current['client']['sim']['householdId']; baselines={}; native_baselines={}
            # Capture remains complete (including backup aliases), but the
            # navigation/edit matrix must match each actual CAS form menu.
            visible=[];proof['captured_owner_count']=sum(len(m['owners']) for m in all_members)
            for member in members:
                target=member['sim_id']
                if sid!=target:
                    layer,native_session=member_selection_context(current['client'])
                    current,_=command(['cas','member-select','--sim-id',sid,'--target-sim-id',target,
                        '--household-id',household,'--expected-layer',str(layer),
                        '--native-session',str(native_session),'--seconds','25'])
                    sid=target
                visible.append(visible_inventory(member,current['client']))
            members=visible;proof['targets']=copy.deepcopy(members)
            proof['selectable_owner_count']=sum(len(m['owners']) for m in members);write_json(output,proof)
            marker_values=physique_markers(members) if edit_markers else {}
            completed=0
            if resume is not None:
                previous,baselines,continuity=resume_prefix(resume,native,members,cycles,edit_markers,verify_native,verify_pages)
                for name in ('steps','marker_edits','appearance_edits_submitted'):
                    proof[name]=copy.deepcopy(previous[name])
                proof['resumed_from']=continuity;completed=len(previous['steps']);write_json(output,proof)
            position=0
            for cycle in range(cycles):
                for member in members:
                    pending=[]
                    for owner in member['owners']:
                        if position>=completed:pending.append(owner)
                        position+=1
                    if not pending:continue
                    target=member['sim_id']
                    if sid!=target:
                        layer,native_session=member_selection_context(current['client'])
                        current,_=command(['cas','member-select','--sim-id',sid,'--target-sim-id',target,
                            '--household-id',household,'--expected-layer',str(layer),
                            '--native-session',str(native_session),'--seconds','25'])
                        sid=target
                    for owner in pending:
                        c=current['client']
                        current,path=command(['cas','form-owner-select','--sim-id',sid,
                            '--owner-id',owner['owner_id'],'--native-kind',str(owner['native_kind']),
                            '--owned-mask',str(member['owned_mask']),'--household-id',household,
                            '--expected-layer',str(c['sim']['occultLayer']),
                            '--native-session',str(c['owner_pair_observation']['session']),'--seconds','25'])
                        receipt=current['native_owner_view_receipt']
                        if (receipt.get('sim_id')!=sid or receipt.get('owner_id')!=owner['owner_id'] or
                                receipt.get('native_kind')!=owner['native_kind'] or
                                receipt.get('independent_undo_bound') is not True or receipt.get('undo_owner_id')!=owner['owner_id']):
                            raise ValueError('Form selection lacks its exact independent owner/history receipt.')
                        export_path=None; raw=None
                        if edit_markers and cycle==0:
                            value=marker_values[(sid,owner['owner_id'])]
                            existing=current['client']['sim']['physiqueValues'][0]
                            edit_path=path; submitted=abs(existing-value)>0.000001
                            if submitted:
                                # Publish intent before any edit; interrupted
                                # outcomes remain potentially submitted.
                                proof['appearance_edits_submitted']=True;write_json(output,proof)
                                current,edit_path=command(['cas','physique','--sim-id',sid,
                                    '--physique-type','0','--value',str(value),'--seconds','25'])
                            proof['marker_edits'].append(dict(sim_id=sid,owner_id=owner['owner_id'],
                                requested=value,readback=current['client']['sim']['physiqueValues'][0],
                                edit_submitted=submitted,receipt_sha256=sha256(edit_path)))
                        if verify_native:
                            if edit_markers and cycle==0:
                                # Export reads the committed graph, never the
                                # live model. Flush the actual edit by selecting
                                # the same owner through its normal game-thread
                                # synchronizer before taking its baseline.
                                c=current['client']
                                current,_=command(['cas','form-owner-select','--sim-id',sid,
                                    '--owner-id',owner['owner_id'],'--native-kind',str(owner['native_kind']),
                                    '--owned-mask',str(member['owned_mask']),'--household-id',household,
                                    '--expected-layer',str(c['sim']['occultLayer']),
                                    '--native-session',str(c['owner_pair_observation']['session']),'--seconds','25'])
                            generation=current['native_owner_view_receipt']['generation']
                            exported,export_path=command(['game','native-cas-engine','--value',json.dumps(dict(
                                operation='export-owner',scope_id=native['scope_id'],sim_id=sid,
                                owner_id=owner['owner_id'],expected_generation=generation))])
                            raw=native_bytes(exported,sid,owner,generation)
                            proof['native_snapshot_count']+=1
                        view=appearance_view(current['client']); key=(sid,owner['owner_id'])
                        if cycle==0:baselines[key]=view
                        elif view!=baselines[key]:
                            prior=baselines[key]
                            proof['differences'].append(dict(sim_id=sid,owner_id=owner['owner_id'],
                                fields=[k for k in view if view[k]!=prior[k]],
                                panels=[p for p in view['panels'] if view['panels'][p]!=prior['panels'].get(p)]))
                        if verify_native:
                            if cycle==0:native_baselines[key]=raw
                            elif raw!=native_baselines[key]:
                                proof['differences'].append(dict(sim_id=sid,owner_id=owner['owner_id'],
                                    complete_native_bytes_changed=True,
                                    before_sha256=hashlib.sha256(native_baselines[key]).hexdigest(),
                                    after_sha256=hashlib.sha256(raw).hexdigest()))
                        step=dict(cycle=cycle,sim_id=sid,owner_id=owner['owner_id'],
                            native_kind=owner['native_kind'],receipt_sha256=sha256(path),view_sha256=digest(view))
                        if export_path is not None:
                            step.update(native_snapshot_receipt_sha256=sha256(export_path),
                                        native_bytes_sha256=hashlib.sha256(raw).hexdigest())
                        proof['steps'].append(step);write_json(output,proof)
                        print(json.dumps(dict(visits=len(proof['steps']),**step)),flush=True)
                        if proof['differences']:raise ValueError('CAS appearance changed across owner/member visits.')
                if verify_pages:
                    # All outgoing owners were committed by their normal
                    # switches. Flush only the final edited view once, then
                    # read the complete household through bounded native pages.
                    c=current['client'];last=member['owners'][-1]
                    current,_=command(['cas','form-owner-select','--sim-id',sid,'--owner-id',last['owner_id'],
                        '--native-kind',str(last['native_kind']),'--owned-mask',str(member['owned_mask']),
                        '--household-id',household,'--expected-layer',str(c['sim']['occultLayer']),
                        '--native-session',str(c['owner_pair_observation']['session']),'--seconds','25'])
                    from cas_owner_export import run as export_pages
                    checkpoint=output.with_name(output.stem+'-cycle-'+str(cycle)+'-pages.json')
                    exported=export_pages(state,checkpoint);index=page_index(exported,all_members)
                    proof['native_page_checkpoints'].append(dict(cycle=cycle,path=str(checkpoint),
                        sha256=sha256(checkpoint),owners=len(index)))
                    proof['native_snapshot_count']+=len(index)
                    if page_baseline is None:page_baseline=index
                    else:
                        for key,sha in index.items():
                            if page_baseline[key]!=sha:proof['differences'].append(dict(sim_id=key[0],owner_id=key[1],
                                complete_native_bytes_changed=True,before_sha256=page_baseline[key],after_sha256=sha))
                    write_json(output,proof)
                    if proof['differences']:raise ValueError('Complete household native bytes changed across cycle barriers.')
            proof['ok']=len(proof['steps'])==cycles*sum(len(m['owners']) for m in members)
            # The serialized DTO includes every captured byte. That does not
            # establish arbitrary field editing or a complete gameplay Sim.
            proof['complete_native_snapshot_bytes_verified']=(verify_native or verify_pages) and proof['ok']
    except MatrixStopped as error:
        proof.update(stopped=True,error=str(error))
    except Exception as error:
        proof['error']=str(error)
    finally:write_json(output,proof)
    return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--cycles',type=int,default=2);p.add_argument('--member-id',action='append')
    p.add_argument('--edit-physique-markers',action='store_true',help='Edit each disposable CAS owner to a unique physique value; never accept/save')
    p.add_argument('--verify-native-bytes',action='store_true',help='Flush actual edits and compare complete native protobuf bytes, including unknown fields')
    p.add_argument('--verify-native-pages',action='store_true',help='Compare complete household bytes at cycle barriers; avoids an export/flush per visit')
    p.add_argument('--resume-unsent-prefix',type=Path,help='Continue exact successful first-cycle receipts after a proven not-sent transport refusal; never replay an uncertain request')
    args=p.parse_args();result=run(args.state,args.output,args.cycles,args.member_id,args.edit_physique_markers,args.verify_native_bytes,args.verify_native_pages,args.resume_unsent_prefix)
    print(json.dumps({k:result.get(k) for k in ('ok','error','differences','production_ready')}))
    raise SystemExit(0 if result['ok'] else 1)
