"""Explicit granular Draw profiling; the original null-callback tail is exact."""
from pathlib import Path
import hashlib
import json
import os
import re

import cas_catalog_binding as binding
import cas_communication_index as comm
import cas_cell_attach as attach

ROOT=Path(__file__).resolve().parents[1]
SOURCES=('tools/cas_draw_phase.py','tools/CasDrawPhasePatch.java','tools/CasStructuralRolesPatch.java',
         'tools/CasCommunicationIndexPatch.java','Source/CASUi/catalog_trace_methods.as')
MAIN=binding.TARGET
CELL='widgets.CAS.controls.CASClothingPanelCellViewMain'
PHASES=('overlay','geometry','state','context','tooltip')
COUNTS={'overlay':3,'geometry':9,'state':15,'context':11,'tooltip':9}
OWNED=('ApexCatalogTraceConfigure','ApexCatalogTraceStep')
SEMANTICS={'ApexCatalogTraceConfigure':'f4cc380bea6e4ea55385cc22b9133deb9750307d70abf119da7b9664561148b2',
           'ApexCatalogTraceStep':'59ba48e2346931068847a55b9be674a08521fe015601d28d63f99a5c06d7d6d1'}


def digest(raw):return hashlib.sha256(raw).hexdigest()


def _qname(a,index):
    value=a.qname(index)
    if index and a.pool(6,index)['name']==0:
        kind=str(a.pool(6,index)['kind']);value=value.replace(kind+'::',kind+':null:',1)
    return value


def _semantic(a,row):
    b=row['value'];info=a.methods['rows'][b['method']]['value'];stack,regs,initial,maximum=b['frame']
    text=str(info['flags'])+'|'+_qname(a,info['ret'])+''.join('|'+_qname(a,p) for p in info['params'])+'|'+str(regs)+'|'+str(stack)+'|'+str(maximum-initial)
    for r in b['traits']['rows']:
        t=r['value']
        if t['flags']&15 not in (0,6):raise ValueError('Granular diagnostic activation has a non-slot trait.')
        text+='|local:'+_qname(a,t['name'])+':'+_qname(a,t['type'])+':'+str(t['slot'])+':'+str(t['value'])+':'+str(t.get('value_kind',0))
    code=a.instructions(b['code']);addresses={x[0]:i for i,x in enumerate(code)};addresses[len(b['code'])]=len(code)
    # FFDec debug(0xEF) extra operands contain absolute stub source lines.
    # Normalize only their common positive offset, keeping type/name/register,
    # zero extras and every relative line gap exact. These owned debug records
    # do not execute; native bodies and runtime QName operands stay untouched.
    debug_lines=[args[3] for _,_,op,args in code if op==0xef and len(args)==4 and args[0]==1 and args[3]>0]
    debug_base=min(debug_lines) if debug_lines else None
    names={0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2}
    for start,end,op,args in code:
        text+='\n'+str(op)
        for n,value in enumerate(args):
            if 0x0c<=op<=0x1a:
                if end+value not in addresses:raise ValueError('Granular diagnostic branch leaves instruction boundary.')
                token='@'+str(addresses[end+value])
            elif n==0 and op in names:token=_qname(a,value)
            elif n==1 and op==0xef:token=a.string(value)
            elif n==3 and op==0xef and args[0]==1 and value>0:token='owned-source+'+str(value-debug_base)
            elif n==0 and op==0xf1:token='owned-helper-source'
            elif n==0 and op==0x2c:token=a.string(value)
            elif n==0 and op in (0x2d,0x2e):
                number=a.pool(op-0x2d,value)
                if op==0x2d and number&0x80000000:number-=1<<32
                token=str(number)
            elif n==0 and op==0x2f:raise ValueError('Reviewed granular diagnostic has no double operands.')
            else:token=str(value)
            text+=':'+token
    for start,end,target,kind,name in b['exceptions']:
        if any(v not in addresses for v in (start,end,target)):raise ValueError('Granular diagnostic exception leaves instruction boundary.')
        text+='\ncatch:'+str(addresses[start])+':'+str(addresses[end])+':'+str(addresses[target])+':'+_qname(a,kind)+':'+_qname(a,name)
    return text


def _verify_timer_binding(a,row):
    bindings=[]
    for _,_,op,args in a.instructions(row['value']['code']):
        if op not in (0x5d,0x60,0x66,0x46,0x4f) or not args:continue
        q=a.pool(6,args[0]);name=a.string(q['name'])
        if name in ('flash','utils'):raise ValueError('Granular timer uses an unresolved runtime flash object.')
        if name=='getTimer':
            if a.qname(args[0])!='7:getTimer:22:flash.utils' or op not in (0x5d,0x46) or op==0x46 and args[1]!=0:
                raise ValueError('Granular timer must resolve the native flash.utils PackageNamespace function.')
            bindings.append(op)
    if bindings!=[0x5d,0x46]:raise ValueError('Granular diagnostic timer binding inventory differs.')


def trace_source():
    source=(ROOT/'Source/CASUi/catalog_trace_methods.as').read_text(encoding='utf-8')
    additions=','.join('"'+n+'"' for n in PHASES)
    changes=[('"icons","other"]','"icons","other",'+additions+']',2),
             ('swatches:0,icons:0,other:0}','swatches:0,icons:0,other:0,'+','.join(n+':0' for n in PHASES)+'}',1),
             ('swatches:0,icons:0,other:1}','swatches:0,icons:0,other:1,'+','.join(n+':0' for n in PHASES)+'}',1)]
    for before,after,count in changes:
        if source.count(before)!=count:raise ValueError('Exact granular trace source seam differs.')
        source=source.replace(before,after)
    source+='\nprivate function ApexLayoutTraceDispose():void {}\n'
    source+='private function ApexPhaseMarkerNames():Object {return ['+','.join('"'+n+'.'+edge+'"' for n in PHASES for edge in ('enter','leave'))+'];}\n'
    return source


def inject(original):
    if 'ApexCatalogTraceConfigure' in original:raise ValueError('Use the original EA Main compiler source.')
    # FFDec's retained EA stub has no flash.utils import. An unimported fully
    # qualified global function can compile as getlex("flash").utils.getTimer,
    # which fails with #1069 in the actual AVM2 application domain. Resolve the
    # imported PackageNamespace function directly; never manufacture a runtime
    # object named flash or alter the original class's other methods.
    anchor='package widgets.CAS.Customizer\n{'
    if original.count(anchor)!=1:raise ValueError('Original Main package/import seam differs.')
    if 'import flash.utils.getTimer;' not in original:
        original=original.replace(anchor,anchor+'\n   import flash.utils.getTimer;',1)
    at=original.rfind('\n   }')
    if at<0:raise ValueError('Original Main class boundary missing.')
    return original[:at]+trace_source().replace('flash.utils.getTimer()','getTimer()')+original[at:]


def _named(a,owner,name):
    space,leaf=owner.rsplit('.',1)
    instances=[r for r in a.instances if a.qname(r['name'])=='7:'+leaf+':22:'+space]
    if len(instances)!=1:raise ValueError('Exact phase owner class absent.')
    traits=[r for r in instances[0]['traits']['rows'] if a.string(a.pool(6,r['value']['name'])['name'])==name]
    if len(traits)!=1 or traits[0]['value']['flags']&15 not in (1,2,3):raise ValueError('Exact phase method absent.')
    rows=[r for r in a.bodies['rows'] if r['value']['method']==traits[0]['value']['method']]
    if len(rows)!=1:raise ValueError('Exact phase body absent.')
    return rows[0]


def _phase(a,op,args):
    if op not in (0x46,0x4f,0x61,0x68):return None
    n=a.string(a.pool(6,args[0])['name'])
    if op in (0x46,0x4f) and n=='gotoAndStop':return 'overlay'
    if op in (0x61,0x68) and n in ('enabled','Selected','visible'):return 'state'
    if op==0x61 and n in ('scaleX','scaleY','x','y','alpha'):return 'geometry'
    if op in (0x46,0x4f) and n in ('CallUIService','GetVariation','IsMTX','IsUnviewed','IsLocked','GetCASBrandedProduct','GetPackIcon'):return 'context'
    if op in (0x61,0x46,0x4f) and n in ('Text','Data','HorizontalAlignment','VerticalAlignment','SetText'):return 'tooltip'
    return None


def _s24(value):
    if not -8388608<=value<=8388607:raise ValueError('Phase marker branch overflow.')
    return (value&0xffffff).to_bytes(3,'little')


def _stamp(a,phase,edge):
    name=phase+'.'+edge;hits=[i+1 for i,r in enumerate(a.pools[3]['rows']) if r['value']==name]
    if len(hits)!=1:raise ValueError('Exact phase marker string absent.')
    # Callback local24 is the existing captured nullable Function. No borrowed
    # product/cell/renderer is passed or stored by a granular marker.
    rest=b'\x62\x18\x64\x2c'+attach._u30(hits[0])+b'\x20\x41\x02\x29'
    return b'\x62\x18\x12'+_s24(len(rest))+rest


def _expected_draw(final_a,old):
    code=final_a.instructions(old['code'])
    if len(code)!=1783 or code[6][2]!=0x11 or old['exceptions'] or old['traits']['count']:
        raise ValueError('Exact two-tail Draw authority differs.')
    profile=code[6][1]+code[6][3][0]
    if profile not in {r[0] for r in code}:raise ValueError('Draw profile entry is not an instruction boundary.')
    pieces=[];mapping={};counts={n:0 for n in PHASES};offset=0
    for start,end,op,args in code:
        mapping[start]=offset
        phase=_phase(final_a,op,args) if start>=profile else None
        before=_stamp(final_a,phase,'enter') if phase else b''
        after=_stamp(final_a,phase,'leave') if phase else b''
        part=before+old['code'][start:end]+after
        pieces.append((start,end,op,args,before,part));offset+=len(part)
        if phase:counts[phase]+=1
    mapping[len(old['code'])]=offset
    if counts!=COUNTS:raise ValueError('Granular phase instruction inventory differs.')
    out=bytearray()
    for start,end,op,args,before,part in pieces:
        if 0x0c<=op<=0x1a:
            if end+args[0] not in mapping:raise ValueError('Original Draw branch is not an instruction boundary.')
            at=len(out)+len(before);part=before+bytes([op])+_s24(mapping[end+args[0]]-at-4)+part[len(before)+4:]
        out+=part
    if out[:profile]!=old['code'][:profile]:raise ValueError('Disabled Draw prologue or fast tail changed.')
    return bytes(out)


def rollback_descriptor(baseline):
    _,raw=binding._abc_payload(baseline);a=binding._ABC(raw).parse()
    bodies={}
    for owner,name in ((CELL,'Draw'),*((MAIN,n) for n in OWNED)):
        row=_named(a,owner,name);bodies[owner+'.'+name]=raw[row['start']:row['end']].hex()
    return dict(pool_counts=[r['count'] for r in a.pools],bodies=bodies)


def reconstruct_previous(final,proof):
    from cas_ui_build import replace_payload
    prefix,raw=binding._abc_payload(final);a=binding._ABC(raw).parse();d=proof.get('rollback')
    if not isinstance(d,dict) or set(d)!={'pool_counts','bodies'} or not isinstance(d['bodies'],dict):raise ValueError('Draw phase rollback absent.')
    counts=d['pool_counts'];keys={CELL+'.Draw',*(MAIN+'.'+n for n in OWNED)}
    if not isinstance(counts,list) or len(counts)!=7 or set(d['bodies'])!=keys:raise ValueError('Draw phase rollback inventory differs.')
    patches=[];restored={};parsed={}
    for key,text in d['bodies'].items():
        if not isinstance(text,str) or len(text)>40000 or re.fullmatch('[0-9a-f]+',text) is None:raise ValueError('Draw phase old body is invalid or unbounded.')
        before=bytes.fromhex(text);reader=binding._ABC(before);old=reader.body();owner,name=key.rsplit('.',1);row=_named(a,owner,name)
        if reader.at!=len(before) or old['method']!=row['value']['method']:raise ValueError('Draw phase rollback targets another method.')
        restored[old['method']]=before;parsed[key]=old
    previous_draw=parsed[CELL+'.Draw'];actual=_named(a,CELL,'Draw')['value']
    if actual['code']!=_expected_draw(a,previous_draw) or actual['frame']!=(previous_draw['frame'][0]+5,)+previous_draw['frame'][1:] or actual['exceptions'] or actual['traits']['count']:
        raise ValueError('Granular Draw differs from the exact profiled-tail additions.')
    for n in OWNED:
        row=_named(a,MAIN,n)
        _verify_timer_binding(a,row)
        if row['value']['frame'][2]!=parsed[MAIN+'.'+n]['frame'][2] or digest(_semantic(a,row).encode())!=SEMANTICS.get(n):
            raise ValueError('Granular diagnostic helper semantic/lexical identity differs.')
    for pool,count in zip(a.pools,counts):
        if type(count) is not int or count<0 or count>pool['count']:raise ValueError('Draw phase pool prefix differs.')
        end=pool['head'] if count<=1 else pool['rows'][count-2]['end']
        patches.append((pool['start'],pool['end'],attach._u30(count)+raw[pool['head']:end]))
    table=a.bodies;body=attach._u30(table['count'])+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']]) for r in table['rows'])
    patches.append((table['start'],table['end'],body));prior=len(raw)
    for start,end,data in sorted(patches,reverse=True):
        if end>prior:raise ValueError('Overlapping Draw phase rollback spans.')
        raw=raw[:start]+data+raw[end:];prior=start
    return replace_payload(final,prefix+raw)


def adapt(previous,baseline,source,ffdec,work):
    from cas_ui_build import replace_payload
    if binding.verify_contract(previous,baseline) is not True:raise ValueError('Complete incoming binding chain did not verify.')
    ffdec=Path(ffdec);work=Path(work);work.mkdir(parents=True,exist_ok=True)
    pins={n:digest((ROOT/n).read_bytes()) for n in SOURCES}
    incoming=work/'baseline.swf';incoming.write_bytes(baseline);owned=work/'CASCustomizerMain.as';owned.write_text(inject(Path(source).read_text(encoding='utf-8-sig')),encoding='utf-8')
    compiled=work/'compiled.swf';comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,MAIN,owned],work/'ffdec.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasDrawPhasePatch.java'],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasDrawPhasePatch',incoming,compiled,output,report],work/'transplant.log')
    abc=output.read_bytes();post=json.loads(report.read_text())
    if post.get('ok') is not True or post.get('abc_sha256')!=digest(abc):raise ValueError('Granular Draw output differs.')
    if pins!={n:digest((ROOT/n).read_bytes()) for n in SOURCES}:raise ValueError('Granular Draw source changed during compilation.')
    post.update(source_sha256=pins,helper_source_sha256=digest(trace_source().encode()),previous_stage_sha256=comm.contract_digest(previous),rollback=rollback_descriptor(baseline))
    return replace_payload(baseline,binding._abc_payload(baseline)[0]+abc),post


def chain_contract(previous,proof,final):
    required=('disabled_fast_tail_exact','existing_profile_markers_retained','native_cfg_projection_verified','native_throw_propagation_retained',
              'whole_abc_rollback_verified','all_other_bodies_retained','no_borrowed_handles_retained','native_timer_namespace_verified')
    counts={'changed_draw_bodies':1,'replaced_owned_bodies':2,'appended_methods':0,'appended_fields':0,'disabled_added_instructions':0,'granular_sites':sum(COUNTS.values())}
    if(not isinstance(previous,dict) or not isinstance(proof,dict) or proof.get('ok') is not True or proof.get('phase')!='opt-in-granular-draw-profile' or
       any(proof.get(n) is not True for n in required) or any(type(proof.get(n)) is not int or proof[n]!=v for n,v in counts.items()) or
       proof.get('phase_sites')!=COUNTS or any(type(n) is not int for n in proof.get('phase_sites',{}).values()) or
       proof.get('baseline_swf_sha256')!=previous.get('final_swf_sha256') or proof.get('previous_stage_sha256')!=comm.contract_digest(previous) or
       proof.get('source_sha256')!={n:digest((ROOT/n).read_bytes()) for n in SOURCES} or proof.get('helper_source_sha256')!=digest(trace_source().encode()) or
       proof.get('runtime_qualified') is not False or proof.get('performance_gain_claimed') is not False):raise ValueError('Granular Draw contract differs.')
    if digest(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Granular Draw final ABC differs.')
    baseline=reconstruct_previous(final,proof)
    if digest(baseline)!=proof['baseline_swf_sha256'] or digest(binding._abc_payload(baseline)[1])!=proof.get('baseline_abc_sha256'):
        raise ValueError('Granular Draw does not reconstruct its exact previous Main.')
    if binding.verify_contract(previous,baseline) is not True:raise ValueError('Granular Draw previous full chain differs.')
    return dict(previous_stage_contract=json.loads(json.dumps(previous)),previous_stage_sha256=comm.contract_digest(previous),
                draw_phase_contract=json.loads(json.dumps(proof)),postproof_sha256=comm.contract_digest(proof),final_swf_sha256=digest(final))


def verify_contract(contract,final):
    if not isinstance(contract,dict) or chain_contract(contract.get('previous_stage_contract'),contract.get('draw_phase_contract'),final)!=contract:
        raise ValueError('Granular Draw continuation differs.')
    return True
