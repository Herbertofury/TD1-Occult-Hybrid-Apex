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
import struct
from pathlib import Path


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


def run(state,output,cycles=2,member_ids=None,edit_markers=False):
    from apex_cli import execute,parser
    from cli_identity_cache import session
    from source_manifest import write_json,sha256
    state=Path(state); output=Path(output)
    if type(cycles) is not int or not 2<=cycles<=10 or type(edit_markers) is not bool or output.exists():
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
        cas_accept_submitted=False,save_submitted=False,complete_native_fields_verified=False,
        production_ready=False)
    write_json(output,proof); sequence=0
    def command(args):
        nonlocal sequence
        path=output.with_name(output.stem+'-'+format(sequence,'04d')+'.json');sequence+=1
        if path.exists():raise ValueError('A matrix receipt already exists; do not replay.')
        value=execute(parser().parse_args(args+['--state',str(state),'--output',str(path)]))
        if not path.exists():write_json(path,value)
        value=json.loads(path.read_text(encoding='utf-8'))
        if value.get('ok') is not True:
            raise ValueError('Matrix command failed; retain '+str(path)+': '+str(value.get('message',value.get('error'))))
        return value,path
    try:
        with session(state):
            native,_=command(['game','native-cas-engine','--value',json.dumps(dict(operation='status'))])
            members,sid=inventory(native)
            if member_ids:
                requested=set(member_ids)
                if not requested<={m['sim_id'] for m in members}:raise ValueError('Requested member is absent from the native roster.')
                members=[m for m in members if m['sim_id'] in requested]
            proof['targets']=copy.deepcopy(members);write_json(output,proof)
            marker_values=physique_markers(members) if edit_markers else {}
            current,_=command(['cas','status','--sim-id',sid,'--seconds','20'])
            household=current['client']['sim']['householdId']; baselines={}
            for cycle in range(cycles):
                for member in members:
                    target=member['sim_id']
                    if sid!=target:
                        c=current['client']
                        current,_=command(['cas','member-select','--sim-id',sid,'--target-sim-id',target,
                            '--household-id',household,'--expected-layer',str(c['sim']['occultLayer']),
                            '--native-session',str(c['owner_pair_observation']['session']),'--seconds','25'])
                        sid=target
                    for owner in member['owners']:
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
                        view=appearance_view(current['client']); key=(sid,owner['owner_id'])
                        if cycle==0:baselines[key]=view
                        elif view!=baselines[key]:
                            prior=baselines[key]
                            proof['differences'].append(dict(sim_id=sid,owner_id=owner['owner_id'],
                                fields=[k for k in view if view[k]!=prior[k]],
                                panels=[p for p in view['panels'] if view['panels'][p]!=prior['panels'].get(p)]))
                        step=dict(cycle=cycle,sim_id=sid,owner_id=owner['owner_id'],
                            native_kind=owner['native_kind'],receipt_sha256=sha256(path),view_sha256=digest(view))
                        proof['steps'].append(step);write_json(output,proof)
                        print(json.dumps(dict(visits=len(proof['steps']),**step)),flush=True)
                        if proof['differences']:raise ValueError('CAS appearance changed across owner/member visits.')
            proof['ok']=len(proof['steps'])==cycles*sum(len(m['owners']) for m in members)
    except Exception as error:
        proof['error']=str(error)
    finally:write_json(output,proof)
    return proof


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--cycles',type=int,default=2);p.add_argument('--member-id',action='append')
    p.add_argument('--edit-physique-markers',action='store_true',help='Edit each disposable CAS owner to a unique physique value; never accept/save')
    args=p.parse_args();result=run(args.state,args.output,args.cycles,args.member_id,args.edit_physique_markers)
    print(json.dumps({k:result.get(k) for k in ('ok','error','differences','production_ready')}))
    raise SystemExit(0 if result['ok'] else 1)
