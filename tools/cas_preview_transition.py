"""Exact bytecode continuation avoiding redundant native preview rebuilds.

Only an already-active preview can remain active between the same eight EA
preview categories. Native leave/enter callbacks and every real preview exit
remain intact. This module operates on build artifacts, never game objects.
"""
from pathlib import Path
import hashlib
import json
import re

import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as comm

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('tools/cas_preview_transition.py','tools/cas_catalog_binding.py',
         'tools/cas_cell_attach.py','tools/cas_swatch_geometry.py')
PIN='75101c574cd90ac3382025094731585f61c23328a6a1b7e0f9eefb86554c6f42'
NATIVE_CONTEXT={
    'SetState':'c3b749ce1c296eed48b060c0bb5e47c3476c1ab0d1d9690bfb8a4eeaabe95264',
    'OnEnterState':'559d934abd5bf2a8473722625a3d212688421b3505a21f151f9015c21502a8fd',
}
GENERIC_ROUTE='da076e680ec48e887e8e086ac36c8ce0d7316499e7f5b195f6fdfe024905d89b'
CATEGORIES=('CLOTHING_BODYSCAR','CLOTHING_BODYDETAILS','CLOTHING_BODY_TATTOOS','CLOTHING_BODY_MEDICAL',
 'CLOTHING_BODY_BODYHAIR_ARM','CLOTHING_BODY_BODYHAIR_LEG','CLOTHING_BODY_BODYHAIR_TORSOFRONT','CLOTHING_BODY_BODYHAIR_TORSOBACK')

def digest(raw):return hashlib.sha256(raw).hexdigest()

def instructions(raw):
    """Decode only the pinned native method's reviewed instruction inventory."""
    r=attach._ABCReader(raw);rows=[]
    single={0x08,0x2c,0x55,0x60,0x61,0x62,0x63,0x66}
    none={0x09,0x26,0x27,0x29,0x2a,0x30,0x47,0x73,0x76,0x96,0xd0,0xd1,0xd2,0xd3,0xd7}
    def signed():
        n=int.from_bytes(r.raw(3),'little');return n-(1<<24) if n&(1<<23) else n
    while r.at<len(raw):
        start=r.at;op=r.byte();args=[]
        if op in (0x10,0x11,0x12,0x13,0x14,0x1a):args=[signed()]
        elif op==0x1b:
            default=signed();count=r.u30()
            if count>9:raise ValueError('Native preview switch inventory differs.')
            args=[default,count]+[signed() for _ in range(count+1)]
        elif op in single:args=[r.u30()]
        elif op in (0x46,0x4f):args=[r.u30(),r.u30()]
        elif op==0x24:
            n=r.byte();args=[n-256 if n&128 else n]
        elif op not in none:raise ValueError('Unreviewed native preview opcode: '+hex(op))
        rows.append((start,r.at,op,args))
    return rows

def _s24(value):
    if not -8388608<=value<=8388607:raise ValueError('Native preview branch overflow.')
    return (value&0xffffff).to_bytes(3,'little')

def _instruction(op,value):return bytes([op])+attach._u30(value)

def expected_code(a,before):
    for name,pin in NATIVE_CONTEXT.items():
        if digest(a.named(name)[2]['value']['code'])!=pin:
            raise ValueError('Native preview caller/enter semantics changed: '+name)
    classes=[i for i,r in enumerate(a.instances) if a.qname(r['name'])=='7:MenuState:22:widgets.CAS.constants']
    if len(classes)!=1:raise ValueError('Exact native preview menu class absent.')
    traits=[r['value'] for r in a.classes[classes[0]]['traits']['rows']
        if a.string(a.pool(6,r['value']['name'])['name'])=='GetGenericPanelType']
    if len(traits)!=1 or traits[0]['flags']&15!=1:raise ValueError('Native generic route method differs.')
    bodies=[r['value'] for r in a.bodies['rows'] if r['value']['method']==traits[0]['method']]
    if len(bodies)!=1 or digest(bodies[0]['code'])!=GENERIC_ROUTE:
        raise ValueError('Native generic route could bypass the preview-category entry.')
    if (digest(before['code'])!=PIN or before['frame']!=(6,6,12,13) or
            before['exceptions'] or before['traits']['count']):
        raise ValueError('Exact native preview leave body/metadata differs.')
    code=instructions(before['code'])
    def prop(name,op):
        hits={args[0] for _,_,kind,args in code if kind==op and a.string(a.pool(6,args[0])['name'])==name}
        if len(hits)!=1:raise ValueError('Native preview QName differs: '+name)
        return hits.pop()
    setter=prop('TattooMode',0x61);state=prop('mNextState',0x66);menu=prop('MenuState',0x60)
    hits=[n for n,(_,_,op,args) in enumerate(code) if op==0x61 and args==[setter]]
    if len(hits)!=1:raise ValueError('Native preview setter inventory differs.')
    index=hits[0]-2;start=code[index][0];end=code[index+2][1]
    if (code[index][2]!=0x60 or code[index+1][2]!=0x27 or
            a.string(a.pool(6,code[index][3][0])['name'])!='CASStateData'):
        raise ValueError('Native preview false setter seam differs.')
    query=[i+1 for i,r in enumerate(a.pools[3]['rows']) if r['value']=='GetIsTattooModeEnabled']
    if len(query)!=1:raise ValueError('Native tattoo-preview query string differs.')
    communication=prop('CommunicationManager',0x60);game_service=prop('CallGameService',0x4f)
    pieces=[_instruction(0x60,code[index][3][0])+_instruction(0x66,setter)+b'\x12\0\0\0',
        _instruction(0x60,communication)+_instruction(0x2c,query[0])+_instruction(0x46,game_service)+b'\x01\x26\x1a\0\0\0']
    for category in CATEGORIES:
        pieces.append(b'\xd0'+_instruction(0x66,state)+_instruction(0x60,menu)+
            _instruction(0x66,prop(category,0x66))+b'\x13\0\0\0')
    size=sum(map(len,pieces));insert=bytearray(b''.join(pieces))
    first_end=len(pieces[0]);insert[first_end-3:first_end]=_s24(size-first_end)
    offset=first_end+len(pieces[1]);insert[offset-3:offset]=_s24(size-offset)
    for piece in pieces[2:]:
        offset+=len(piece);insert[offset-3:offset]=_s24(size+end-start-offset)
    mapping={at:at+(size if at>start else 0) for at,_,_,_ in code}
    mapping[len(before['code'])]=len(before['code'])+size
    result=bytearray()
    for at,stop,op,args in code:
        if at==start:result+=insert
        raw=before['code'][at:stop]
        if op in (0x10,0x11,0x12,0x13,0x14,0x1a):
            target=stop+args[0]
            if target not in mapping or start<target<end:raise ValueError('Native branch enters an invalid setter boundary.')
            raw=bytes([op])+_s24(mapping[target]-mapping[stop])
        elif op==0x1b:
            targets=[at+args[0]]+[at+x for x in args[2:]]
            if any(t not in mapping or start<t<end for t in targets):raise ValueError('Native switch enters an invalid setter boundary.')
            offsets=[_s24(mapping[t]-mapping[at]) for t in targets]
            raw=b'\x1b'+offsets[0]+attach._u30(args[1])+b''.join(offsets[1:])
        result+=raw
    return bytes(result)

def _old_body(final,proof):
    from cas_ui_build import replace_payload
    text=proof.get('native_body')
    if not isinstance(text,str) or len(text)>8192 or re.fullmatch('[0-9a-f]+',text) is None:
        raise ValueError('Native preview rollback body absent or unbounded.')
    raw=bytes.fromhex(text);reader=binding._ABC(raw);old=reader.body()
    if reader.at!=len(raw):raise ValueError('Native preview rollback body has trailing bytes.')
    prefix,data=binding._abc_payload(final);a=binding._ABC(data).parse();row=a.named('OnLeaveState')[2];current=row['value']
    if (current['method']!=old['method'] or current['frame']!=old['frame'] or current['exceptions'] or
            current['traits']['count'] or current['code']!=expected_code(a,old)):
        raise ValueError('Native preview transition does not preserve its exact original method.')
    prior=data[:row['start']]+raw+data[row['end']:]
    return replace_payload(final,prefix+prior)

def reconstruct_previous(final,proof):
    prior=_old_body(final,proof)
    if (digest(prior)!=proof.get('baseline_swf_sha256') or
            digest(binding._abc_payload(prior)[1])!=proof.get('baseline_abc_sha256')):
        raise ValueError('Native preview full rollback differs from its authenticated previous Main.')
    return prior

def chain_contract(previous,proof,final):
    import cas_swatch_geometry as swatch
    required=('native_cfg_projection_verified','whole_abc_rollback_verified','constant_pools_unchanged',
        'requires_already_active_preview','requires_native_preview_true','normal_preview_exit_retained')
    counts={'changed_native_bodies':1,'appended_methods':0,'appended_fields':0,'same_preview_next_categories':8}
    if (not isinstance(previous,dict) or not isinstance(proof,dict) or proof.get('phase')!='same-native-preview-category-transition' or
            proof.get('ok') is not True or any(proof.get(n) is not True for n in required) or
            any(type(proof.get(n)) is not int or proof[n]!=v for n,v in counts.items()) or
            proof.get('source_sha256')!={n:digest((ROOT/n).read_bytes()) for n in SOURCES} or
            proof.get('previous_stage_sha256')!=comm.contract_digest(previous) or
            proof.get('baseline_swf_sha256')!=previous.get('final_swf_sha256') or
            proof.get('abc_sha256')!=digest(binding._abc_payload(final)[1]) or
            proof.get('runtime_qualified') is not False or proof.get('performance_gain_claimed') is not False):
        raise ValueError('Native preview transition contract differs.')
    prior=reconstruct_previous(final,proof)
    if swatch.verify_contract(previous,prior) is not True:raise ValueError('Native preview previous complete chain differs.')
    return dict(previous_stage_contract=json.loads(json.dumps(previous)),previous_stage_sha256=comm.contract_digest(previous),
        preview_transition_contract=json.loads(json.dumps(proof)),postproof_sha256=comm.contract_digest(proof),final_swf_sha256=digest(final))

def verify_contract(contract,final):
    if (not isinstance(contract,dict) or
            chain_contract(contract.get('previous_stage_contract'),contract.get('preview_transition_contract'),final)!=contract):
        raise ValueError('Native preview transition continuation differs.')
    return True

def adapt(previous,baseline):
    from cas_ui_build import replace_payload
    import cas_swatch_geometry as swatch
    if swatch.verify_contract(previous,baseline) is not True:raise ValueError('Native preview incoming chain did not verify.')
    pins={n:digest((ROOT/n).read_bytes()) for n in SOURCES}
    prefix,data=binding._abc_payload(baseline);a=binding._ABC(data).parse();row=a.named('OnLeaveState')[2];body=row['value']
    code=expected_code(a,body);header=b''.join(attach._u30(x) for x in (body['method'],*body['frame'],len(code)))
    made=data[:row['start']]+header+code+b'\0\0'+data[row['end']:]
    final=replace_payload(baseline,prefix+made)
    proof=dict(ok=True,phase='same-native-preview-category-transition',native_body=data[row['start']:row['end']].hex(),
        baseline_swf_sha256=digest(baseline),baseline_abc_sha256=digest(data),abc_sha256=digest(made),
        source_sha256=pins,previous_stage_sha256=comm.contract_digest(previous),changed_native_bodies=1,appended_methods=0,
        appended_fields=0,same_preview_next_categories=8,native_cfg_projection_verified=True,whole_abc_rollback_verified=True,
        constant_pools_unchanged=True,requires_already_active_preview=True,requires_native_preview_true=True,normal_preview_exit_retained=True,
        runtime_qualified=False,performance_gain_claimed=False)
    if pins!={n:digest((ROOT/n).read_bytes()) for n in SOURCES}:raise ValueError('Native preview source changed during build.')
    chain_contract(previous,proof,final)
    return final,proof
