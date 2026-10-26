"""Optional scalar publication diagnostics with complete native rollback."""
from pathlib import Path
import copy,hashlib,json,re,os
import cas_publication_stage as stage
import cas_grid_featured as previous
import cas_grid_budget as mechanics
import cas_grid_presentation as presentation
import cas_communication_index as comm
import cas_catalog_binding as binding
import cas_cell_attach as attach

ROOT=stage.ROOT;H=ROOT;GRID=previous.GRID;MAIN=previous.MAIN
SOURCES=('tools/cas_publication_stage.py','tools/cas_grid_publication.py','tools/CasPublicationTracePatch.java',
         'Source/CASUi/catalog_publication_trace_methods.as','Source/CASUi/catalog_grid_publication_trace_emit.as')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def pins():return {n:sha((H/n).read_bytes()) for n in SOURCES}
def inventory(owner):
    if owner==GRID:return stage.GRID_REPLACED,stage.GRID_ADDED
    if owner==MAIN:return stage.MAIN_REPLACED,stage.MAIN_ADDED
    raise ValueError('Exact owned diagnostics class required')
def semantics(owner):
    expected=set(sum(inventory(owner),()))
    pattern=r'Map.entry\((GRID|MAIN)\+"/(\w+)","([0-9a-f]{64})"\)'
    rows=[(name,pin)for kind,name,pin in re.findall(pattern,(H/'tools/CasPublicationTracePatch.java').read_text()) if(GRID if kind=='GRID'else MAIN)==owner]
    if len(rows)!=len(expected) or set(name for name,_ in rows)!=expected:raise ValueError('Diagnostic semantic pins missing/partial')
    return dict(rows)
def descriptor(base,owner):return mechanics.build_descriptor(base,owner,inventory(owner)[0])


def reconstruct(final,description,owner):
    from cas_ui_build import replace_payload
    replaced,added=inventory(owner)
    prefix,raw=binding._abc_payload(final);a=mechanics.ABC(raw).parse();d=description
    if not isinstance(d,dict)or set(d)!={'pool_counts','bodies'}or set(d['bodies'])!=set(replaced):raise ValueError('Exact diagnostic rollback body inventory required')
    if not isinstance(d['pool_counts'],list)or len(d['pool_counts'])!=7:raise ValueError('Exact diagnostic constant prefix required')
    restored={};patches=[];frozen=semantics(owner)
    for name,payload in d['bodies'].items():
        if not isinstance(payload,str)or not 0<len(payload)<=200000 or re.fullmatch('[0-9a-f]+',payload)is None:raise ValueError('Original body malformed/unbounded')
        value=bytes.fromhex(payload);reader=mechanics.ABC(value);old=reader.body();row=presentation.named(a,owner,name)[1]
        if reader.at!=len(value)or old['method']!=row['value']['method']or old['frame'][2]!=row['value']['frame'][2]:raise ValueError('Diagnostic method/scope identity changed')
        restored[old['method']]=value
    namespace,leaf=owner.rsplit('.',1);instance=next(r for r in a.instances if a.qname(r['name'])=='7:'+leaf+':22:'+namespace);traits=instance['traits'];initial=a.methods['count']-1
    name=added[0];t,b=presentation.named(a,owner,name);v=t['value']
    old_scope=presentation.named(a,owner,replaced[0])[1]['value']['frame'][2]
    expected_scope=old_scope+(1 if owner==MAIN else 0)
    if(t!=traits['rows'][-1]or v['flags']!=1 or v['dispatch']!=0 or'metadata'in v or v['method']!=initial or
       a.qname(v['name'])!='7:'+name+':5:'+namespace+':'+leaf or b!=a.bodies['rows'][-1]or b['value']['frame'][2]!=expected_scope):raise ValueError('Appended diagnostic helper is not exact private catch ABI')
    for name in replaced+added:
        t,b=presentation.named(a,owner,name);info=a.methods['rows'][b['value']['method']]['value']
        if(name in added and(info['flags']!=2 or info['optional']or info['param_names']))or sha(presentation.semantic(a,b).encode())!=frozen[name]:raise ValueError('Reviewed diagnostic semantic/ABI differs: '+name)
        for _,_,op,args in a.instructions(b['value']['code']):
            if op in(0x40,0x43,0x44,0x67):raise ValueError('Foreign nested/outer dependency')
            if op in(0x5d,0x46,0x4f)and presentation.draw._qname(a,args[0]).startswith('7:getTimer:')and presentation.draw._qname(a,args[0])!='7:getTimer:22:flash.utils':raise ValueError('Clock does not bind exact native QName')
    patches.append((traits['start'],traits['end'],attach._u30(traits['count']-1)+raw[traits['head']:traits['rows'][-1]['start']]))
    for pool,count in zip(a.pools,d['pool_counts']):
        if type(count)is not int or not 0<=count<=pool['count']:raise ValueError('Constant prefix malformed')
        end=pool['head']if count<=1 else pool['rows'][count-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count)+raw[pool['head']:end]))
    table=a.methods;patches.append((table['start'],table['end'],attach._u30(table['count']-1)+raw[table['head']:table['rows'][-1]['start']]))
    table=a.bodies;out=attach._u30(table['count']-1)+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']])for r in table['rows'][:-1]);patches.append((table['start'],table['end'],out))
    limit=len(raw)
    for start,end,value in sorted(patches,reverse=True):
        if end>limit or start>end:raise ValueError('Rollback spans overlap')
        raw=raw[:start]+value+raw[end:];limit=start
    return replace_payload(final,prefix+raw)


def chain(prior,proof,final,owner):
    replaced,added=inventory(owner);mode='grid'if owner==GRID else'main'
    required=('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified','native_clock_QName_verified')
    if(not isinstance(prior,dict)or not isinstance(proof,dict)or proof.get('ok')is not True or proof.get('mode')!=mode or
       any(proof.get(k)is not True for k in required)or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in{'replaced_owned_bodies':2,'appended_methods':1,'appended_fields':0,'changed_original_native_bodies':0}.items())or
       proof.get('source_sha256')!=pins()or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or
       proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False or
       proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256'if owner==GRID else'final_swf_sha256')):raise ValueError('Diagnostic complete native continuation proof differs')
    if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Final diagnostic SWF/ABC identity differs')
    if owner==GRID and proof.get('helper_source_sha256')!=sha(stage.helpers().encode()):raise ValueError('Complete diagnostic helper Source differs')
    base=reconstruct(final,proof.get('rollback'),owner)
    if sha(base)!=proof.get('baseline_swf_sha256')or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256'):raise ValueError('Exact complete preceding native bytes differ')
    verified=previous.verify_adapter(prior,base)if owner==GRID else previous.verify_main(prior,base)
    if verified is not True:raise ValueError('Complete preceding Featured history refused')
    result={'previous_stage_sha256':comm.contract_digest(prior),'publication_trace_contract':copy.deepcopy(proof),'postproof_sha256':comm.contract_digest(proof)}
    if owner==GRID:result.update(previous_stage_adapter=copy.deepcopy(prior),base_resource_sha256=prior['base_resource_sha256'],patched_resource_sha256=sha(final))
    else:result.update(previous_stage_contract=copy.deepcopy(prior),final_swf_sha256=sha(final))
    return result


def verify(contract,final,owner):
    if not isinstance(contract,dict)or chain(contract.get('previous_stage_adapter'if owner==GRID else'previous_stage_contract'),contract.get('publication_trace_contract'),final,owner)!=contract:raise ValueError('Complete diagnostic contract differs')
    return True


def helpers():return stage.helpers()
def inject_main(source):return stage.main(previous.inject_main(source))
def verify_adapter(adapter,final):return verify(adapter,final,GRID)
def verify_main(contract,final):return verify(contract,final,MAIN)

def historical(adapter,final):
    verify_adapter(adapter,final)
    return adapter['previous_stage_adapter'],reconstruct(final,adapter['publication_trace_contract']['rollback'],GRID)

def adapt(prior,base,original,ffdec,work):
    from cas_ui_build import replace_payload
    base=bytes(base);original=Path(original);ffdec=Path(ffdec);work=Path(work)
    if previous.verify_adapter(prior,base)is not True:raise ValueError('Publication requires complete Featured provider')
    if sha(original.read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Publication original native provider differs')
    start=pins();work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(base);source=work/'native-source'
    comm.run([ffdec,'-selectclass',GRID,'-export','script',source,original],work/'export.log')
    text=presentation.inject_grid((source/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig'));before=presentation.helpers()
    if text.count(before)!=1:raise ValueError('Publication compiler helper seam differs')
    owned=work/'RecyclingGridLayout.as';owned.write_text(text.replace(before,helpers(),1),encoding='utf-8');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,GRID,owned],work/'compile.log')
    return _transplant(prior,base,compiled,owned,ffdec,work,GRID,start)

def adapt_main(prior,base,source,ffdec,work):
    if previous.verify_main(prior,base)is not True:raise ValueError('Publication Main requires complete Featured predecessor')
    start=pins();ffdec=Path(ffdec);work=Path(work);work.mkdir(parents=True,exist_ok=True)
    incoming=work/'baseline.swf';incoming.write_bytes(base)
    owned=work/'CASCustomizerMain.as';owned.write_text(inject_main(Path(source).read_text(encoding='utf-8-sig')),encoding='utf-8');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,MAIN,owned],work/'compile.log')
    return _transplant(prior,base,compiled,owned,ffdec,work,MAIN,start)

def _transplant(prior,base,compiled,owned,ffdec,work,owner,start):
    from cas_ui_build import replace_payload
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=previous.ROOT
    comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',project/'tools/CasGridPoolPatch.java',ROOT/'tools/CasPublicationTracePatch.java'],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json';mode='grid'if owner==GRID else'main'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasPublicationTracePatch',mode,work/'baseline.swf',compiled,output,report],work/'transplant.log')
    if start!=pins():raise ValueError('Publication source changed during compilation')
    final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
    proof.update(source_sha256=start,helper_source_sha256=sha(helpers().encode())if owner==GRID else sha(owned.read_bytes()),previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base,owner),final_swf_sha256=sha(final))
    return final,chain(prior,proof,final,owner)

def unwrap_providers(evidence,resources,dependencies=None):
    import dbpf_build,maru_companion
    keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
    if not isinstance(evidence,dict)or set(evidence)!=keys:raise ValueError('Both publication provider continuations are required')
    out=dict(resources);providers={}
    for key in keys:
        adapter=evidence[key]
        if not isinstance(adapter,dict)or 'publication_trace_contract'not in adapter:raise ValueError('Publication provider absent or downgraded')
        native=tuple(int(n,16)for n in key.split(':'));providers[key],out[native]=historical(adapter,resources.get(native,b''))
    return providers,out,dependencies

def unwrap_manifest(info,resources):
    import dbpf_build,maru_companion
    source=info.get('source_pins',{});providers=info.get('grid_provider_adapters');main=info.get('publication_trace_main_native_bytecode_contract')
    current=any(n in source for n in SOURCES)or main is not None or any(isinstance(a,dict)and 'publication_trace_contract'in a for a in(providers or {}).values())
    if not current:return info,resources
    if not isinstance(source,dict)or any(source.get(k)!=v for k,v in pins().items()):raise ValueError('Publication source pins absent/partial/stale')
    if not isinstance(main,dict)or main.get('previous_stage_contract')!=info.get('featured_main_native_bytecode_contract'):raise ValueError('Publication Main Featured predecessor missing')
    key=maru_companion.CUSTOMIZER;final=resources.get(key,b'')
    if info.get('patched_resource_sha256')!=sha(final)or info.get('patched_resources',{}).get(dbpf_build.tgi(key))!=sha(final):raise ValueError('Advertised publication Main identity differs')
    verify_main(main,final)
    for name in(dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
        native=tuple(int(n,16)for n in name.split(':'))
        if info.get('patched_resources',{}).get(name)!=sha(resources.get(native,b'')):raise ValueError('Advertised publication provider identity differs')
    p,r,_=unwrap_providers(providers,resources);updated=copy.deepcopy(info);updated['grid_provider_adapters']=p
    updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
    for name,adapter in p.items():updated['patched_resources'][name]=adapter['patched_resource_sha256']
    r[key]=reconstruct(final,main['publication_trace_contract']['rollback'],MAIN);updated['patched_resource_sha256']=sha(r[key]);updated['patched_resources'][dbpf_build.tgi(key)]=sha(r[key])
    return updated,r
