"""Main-only complete same-peer pre-consumption navigation failures.

Restore the exact Width Main before checking its complete recursive authority.
No original native method, constructor, field or provider is changed here.
"""
from pathlib import Path
import copy,hashlib,json,re,os
ROOT=Path(__file__).resolve().parents[1]
import cas_unconsumed_stage as stage
import cas_grid_width as previous
import cas_grid_budget as mechanics
import cas_grid_presentation as presentation
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as comm
MAIN=previous.MAIN
SOURCES=('tools/cas_catalog_unconsumed.py','tools/cas_unconsumed_stage.py','tools/CasCatalogUnconsumedPatch.java','Source/CASUi/catalog_unconsumed_methods.as','Source/CASUi/catalog_unconsumed_consumer_methods.as')
CONTRACT='catalog_unconsumed_contract'
MANIFEST='catalog_unconsumed_main_native_bytecode_contract'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def pins():return {n:sha((ROOT/n).read_bytes())for n in SOURCES}

def inventory(owner):
    if owner!=MAIN:raise ValueError('Exact Main-only unconsumed navigation owner required')
    return stage.REPLACED,stage.ADDED

def semantic_pins(owner):
    rows=re.findall(r'Map.entry\("([^"\n]+)","([0-9a-f]{64})"\)',(ROOT/SOURCES[2]).read_text())
    out={n.rsplit('/',1)[1]:v for n,v in rows if n.rsplit('/',1)[0]==owner}
    if len(out)!=len(sum(inventory(owner),()))or set(out)!=set(sum(inventory(owner),())):raise ValueError('Complete unconsumed navigation semantic inventory missing')
    return out

def semantic(a,row):
    b=row['value'];info=a.methods['rows'][b['method']]['value'];stack,regs,initial,maximum=b['frame']
    q=lambda n:presentation.draw._qname(a,n)
    text=str(info['flags'])+'|'+q(info['ret'])+''.join('|'+q(p) for p in info['params'])+'|'+str(regs)+'|'+str(stack)+'|'+str(maximum-initial)
    for r in b['traits']['rows']:
        t=r['value']
        if t['flags']&15 not in (0,6):raise ValueError('Presentation activation has non-slot trait.')
        text+='|local:'+q(t['name'])+':'+q(t['type'])+':'+str(t['slot'])+':'+str(t['value'])+':'+str(t.get('value_kind',0))
    code=a.instructions(b['code']);addresses={x[0]:i for i,x in enumerate(code)};addresses[len(b['code'])]=len(code)
    lines=[args[3] for _,_,op,args in code if op==0xef and len(args)==4 and args[0]==1 and args[3]>0];base=min(lines) if lines else None
    names={0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2}
    for start,end,op,args in code:
        text+='\n'+str(op)
        for n,value in enumerate(args):
            target=None
            if 0x0c<=op<=0x1a:target=end+value
            elif op==0x1b and n!=1:target=start+value
            if target is not None:
                if target not in addresses:raise ValueError('Presentation branch leaves instruction boundary.')
                token='@'+str(addresses[target])
            elif n==0 and op in names:token=q(value)
            elif n==1 and op==0xef:token=a.string(value)
            elif n==3 and op==0xef and args[0]==1 and value>0:token='owned-source+'+str(value-base)
            elif n==0 and op==0xf1:token='owned-helper-source'
            elif n==0 and op==0x2c:token=a.string(value)
            elif n==0 and op in (0x2d,0x2e):
                number=a.pool(op-0x2d,value)
                if op==0x2d and number&0x80000000:number-=1<<32
                token=str(number)
            elif n==0 and op==0x2f:
                number=a.pool(2,value)
                tokens={}
                if number not in tokens:raise ValueError('Unreviewed scheduling double constant: '+repr(number))
                token=tokens[number]
            else:token=str(value)
            text+=':'+token
    for start,end,target,kind,name in b['exceptions']:
        if any(v not in addresses for v in (start,end,target)):raise ValueError('Presentation exception leaves instruction boundary.')
        text+='\ncatch:'+str(addresses[start])+':'+str(addresses[end])+':'+str(addresses[target])+':'+q(kind)+':'+q(name)
    return text

def reconstruct(final,d,owner):
    from cas_ui_build import replace_payload
    replaced,added=inventory(owner);prefix,raw=binding._abc_payload(final);a=mechanics.ABC(raw).parse()
    if not isinstance(d,dict)or set(d)!={'pool_counts','bodies'}or set(d['bodies'])!=set(replaced):raise ValueError('Exact rollback body inventory missing')
    if not isinstance(d['pool_counts'],list)or len(d['pool_counts'])!=7:raise ValueError('Exact constant prefix missing')
    frozen=semantic_pins(owner);restored={};patches=[]
    for name,text in d['bodies'].items():
        if not isinstance(text,str)or re.fullmatch('[0-9a-f]{2,200000}',text)is None:raise ValueError('Original body malformed or unbounded')
        value=bytes.fromhex(text);r=mechanics.ABC(value);old=r.body();row=presentation.named(a,owner,name)[1]
        if r.at!=len(value)or old['method']!=row['value']['method']or old['frame'][2]!=row['value']['frame'][2]:raise ValueError('Original method/scope target differs')
        restored[old['method']]=value
    namespace,leaf=owner.rsplit('.',1);instance=next(i for i in a.instances if a.qname(i['name'])=='7:'+leaf+':22:'+namespace)
    traits=instance['traits'];count=len(added)
    if count:
        first=a.methods['count']-count;normal=presentation.named(a,owner,'ApexCatalogGridRequest')[1]['value']['frame'][2]
        for i,name in enumerate(added):
            t,b=presentation.named(a,owner,name);v=t['value'];info=a.methods['rows'][b['value']['method']]['value']
            if(t!=traits['rows'][-count+i]or v['flags']!=1 or v['dispatch']!=0 or 'metadata'in v or v['method']!=first+i or
               a.qname(v['name'])!='7:'+name+':5:'+namespace+':'+leaf or b!=a.bodies['rows'][-count+i]or
               b['value']['frame'][2]!=normal+(1 if info['flags']&2 else 0)or info['optional']or info['param_names']):raise ValueError('Appended private helper ABI/ownership differs')
        patches.append((traits['start'],traits['end'],attach._u30(traits['count']-count)+raw[traits['head']:traits['rows'][-count]['start']]))
    runtime_class=False
    for name in replaced+added:
        t,b=presentation.named(a,owner,name)
        if sha(semantic(a,b).encode())!=frozen[name]:raise ValueError('Reviewed unconsumed navigation semantic/CFG differs: '+name)
        for _,_,op,args in a.instructions(b['value']['code']):
            if op in(0x40,0x43,0x44,0x67):raise ValueError('Foreign nested/outer linkage')
            if op in(0x60,0x46,0x4f)and a.string(a.pool(6,args[0])['name'])=='getQualifiedClassName':
                if a.qname(args[0])!='7:getQualifiedClassName:22:flash.utils':raise ValueError('Runtime class namespace differs')
                runtime_class=True
    for p,count0 in zip(a.pools,d['pool_counts']):
        if type(count0)is not int or not 0<=count0<=p['count']:raise ValueError('Constant prefix malformed')
        end=p['head']if count0<=1 else p['rows'][count0-2]['end'];patches.append((p['start'],p['end'],attach._u30(count0)+raw[p['head']:end]))
    if count:
        table=a.methods;patches.append((table['start'],table['end'],attach._u30(table['count']-count)+raw[table['head']:table['rows'][-count]['start']]))
    table=a.bodies;rows=table['rows'][:-count]if count else table['rows']
    patches.append((table['start'],table['end'],attach._u30(table['count']-count)+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']])for r in rows)))
    limit=len(raw)
    for start,end,value in sorted(patches,reverse=True):
        if end>limit or start>end:raise ValueError('Rollback spans overlap')
        raw=raw[:start]+value+raw[end:];limit=start
    return replace_payload(final,prefix+raw)
def chain(prior,proof,final):
    required=('whole_abc_rollback_verified','all_unowned_bodies_retained','serialized_owned_bodies_verified','native_protected_bindings_verified')
    counts={'replaced_owned_bodies':len(stage.REPLACED),'appended_methods':len(stage.ADDED),'appended_fields':0,'changed_original_native_bodies':0}
    if(not isinstance(prior,dict)or previous.CONTRACT not in prior or not isinstance(proof,dict)or proof.get('ok')is not True or proof.get('mode')!='main'or
       any(proof.get(k)is not True for k in required)or proof.get('runtime_class_QName_verified')is not False or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in counts.items())or
       proof.get('source_sha256')!=pins()or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or
       proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False):raise ValueError('Complete unconsumed navigation proof differs')
    if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Final scheduling SWF/ABC identity differs')
    base=reconstruct(final,proof.get('rollback'),MAIN)
    if sha(base)!=proof.get('baseline_swf_sha256')or sha(base)!=prior.get('final_swf_sha256')or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256'):raise ValueError('Original complete Width predecessor bytes differ')
    if previous.verify_main(prior,base)is not True:raise ValueError('Full recursive preceding Main chain differs')
    return {'previous_stage_contract':copy.deepcopy(prior),'previous_stage_sha256':comm.contract_digest(prior),
            CONTRACT:copy.deepcopy(proof),'postproof_sha256':comm.contract_digest(proof),'final_swf_sha256':sha(final)}

def verify_main(contract,final):
    if not isinstance(contract,dict)or chain(contract.get('previous_stage_contract'),contract.get(CONTRACT),final)!=contract:raise ValueError('Complete unconsumed navigation Main contract differs')
    return True

def historical(contract,final):
    verify_main(contract,final)
    return contract['previous_stage_contract'],reconstruct(final,contract[CONTRACT]['rollback'],MAIN)

def inject_main(source):return stage.inject_main(previous.inject_main(source))

def adapt_main(prior,base,source,ffdec,work):
    from cas_ui_build import replace_payload
    if not isinstance(prior,dict)or previous.CONTRACT not in prior or previous.verify_main(prior,base)is not True:raise ValueError('Unconsumed navigation requires complete current Width Main')
    work=Path(work);ffdec=Path(ffdec);work.mkdir(parents=True,exist_ok=True);start=pins();(work/'baseline.swf').write_bytes(base)
    owned=work/'CASCustomizerMain.as';owned.write_text(inject_main(Path(source).read_text(encoding='utf-8-sig')),encoding='utf-8');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',work/'baseline.swf',compiled,MAIN,owned],work/'compile.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=presentation.ROOT
    comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',project/'tools/CasGridPoolPatch.java',ROOT/SOURCES[2]],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasCatalogUnconsumedPatch','main',work/'baseline.swf',compiled,output,report],work/'transplant.log')
    if start!=pins():raise ValueError('Unconsumed navigation source changed during compilation')
    final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
    proof.update(source_sha256=start,previous_stage_sha256=comm.contract_digest(prior),
                 rollback=mechanics.build_descriptor(base,MAIN,stage.REPLACED),final_swf_sha256=sha(final))
    return final,chain(prior,proof,final)

def unwrap_manifest(info,resources):
    import dbpf_build,maru_companion
    source=info.get('source_pins',{});main=info.get(MANIFEST)
    current=any(n in source for n in SOURCES)or main is not None
    if not current:return info,resources
    if not isinstance(source,dict)or any(source.get(n)!=v for n,v in pins().items()):raise ValueError('Unconsumed navigation source pins missing/partial/stale')
    if not isinstance(main,dict)or main.get('previous_stage_contract')!=info.get(previous.MAIN_MANIFEST):raise ValueError('Exact Width Main predecessor absent')
    key=maru_companion.CUSTOMIZER;final=resources.get(key,b'');name=dbpf_build.tgi(key)
    if info.get('patched_resource_sha256')!=sha(final)or info.get('patched_resources',{}).get(name)!=sha(final):raise ValueError('Advertised scheduling Main bytes differ')
    prior,base=historical(main,final)
    updated=copy.deepcopy(info);out=dict(resources);out[key]=base
    updated['patched_resource_sha256']=sha(base);updated['patched_resources'][name]=sha(base)
    return updated,out
