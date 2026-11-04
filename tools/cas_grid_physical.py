"""Keep ideal logical coordinates separate from native display readbacks.

Exact current RowDelta-terminal provider-only continuation, with complete native ABC rollback.
All build inputs and source pins are repository-relative; no private work paths.
"""
from pathlib import Path
import copy,hashlib,json,re,os
ROOT=Path(__file__).resolve().parents[1]
import cas_grid_physical_stage as stage
import cas_grid_row_delta as previous
import cas_grid_budget as mechanics
import cas_grid_presentation as presentation
import cas_grid_publication as publication
import cas_grid_staging_attach as staging_attach
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as comm
GRID=publication.GRID;MAIN=publication.MAIN
SOURCES=('tools/cas_grid_physical.py','tools/cas_grid_physical_stage.py','tools/CasGridPhysicalPatch.java')
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def pins():return {n:sha((ROOT/n).read_bytes())for n in SOURCES}
def helpers():return stage.helpers()
def inventory(owner):
    if owner==GRID:return stage.REPLACED,stage.ADDED
    raise ValueError('Exact owned physical-position class required')
def semantic_pins(owner):
    rows=re.findall(r'Map.entry\("([^"\n]+)","([0-9a-f]{64})"\)',(ROOT/SOURCES[2]).read_text())
    out={n.rsplit('/',1)[1]:v for n,v in rows if n.rsplit('/',1)[0]==owner}
    if len(out)!=len(sum(inventory(owner),())) or set(out)!=set(sum(inventory(owner),())):raise ValueError('Complete physical-position semantic inventory missing')
    return out
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
        first=a.methods['count']-count;normal=presentation.named(a,owner,'ApexGridBind')[1]['value']['frame'][2]
        for i,name in enumerate(added):
            t,b=presentation.named(a,owner,name);v=t['value'];info=a.methods['rows'][b['value']['method']]['value']
            if(t!=traits['rows'][-count+i]or v['flags']!=1 or v['dispatch']!=0 or 'metadata'in v or v['method']!=first+i or
               a.qname(v['name'])!='7:'+name+':5:'+namespace+':'+leaf or b!=a.bodies['rows'][-count+i]or
               b['value']['frame'][2]!=normal+(1 if info['flags']&2 else 0)or info['optional']or info['param_names']):raise ValueError('Appended private helper ABI/ownership differs')
        patches.append((traits['start'],traits['end'],attach._u30(traits['count']-count)+raw[traits['head']:traits['rows'][-count]['start']]))
    runtime_class=False
    for name in replaced+added:
        t,b=presentation.named(a,owner,name)
        if sha(presentation.semantic(a,b).encode())!=frozen[name]:raise ValueError('Reviewed physical-position semantic/CFG differs: '+name)
        for _,_,op,args in a.instructions(b['value']['code']):
            if op in(0x40,0x43,0x44,0x67):raise ValueError('Foreign nested/outer linkage')
            if op in(0x60,0x46,0x4f)and a.string(a.pool(6,args[0])['name'])=='getQualifiedClassName':
                if a.qname(args[0])!='7:getQualifiedClassName:22:flash.utils':raise ValueError('Runtime class namespace differs')
                runtime_class=True
    if owner==GRID and not runtime_class:raise ValueError('Exact runtime class proof getter missing')
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
def chain(prior,proof,final,owner):
    replaced,added=inventory(owner)
    required=('whole_abc_rollback_verified','all_unowned_bodies_retained','serialized_owned_bodies_verified','native_protected_bindings_verified')
    if(not isinstance(prior,dict)or not isinstance(proof,dict)or proof.get('ok')is not True or proof.get('mode')!=('grid'if owner==GRID else'main')or
       any(proof.get(k)is not True for k in required)or proof.get('runtime_class_QName_verified')is not(owner==GRID)or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in {'replaced_owned_bodies':len(replaced),'appended_methods':len(added),'appended_fields':0,'changed_original_native_bodies':0}.items())or
       proof.get('source_sha256')!=pins()or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or
       proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False):raise ValueError('Complete physical-position proof differs')
    if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Final SWF/ABC identity differs')
    base=reconstruct(final,proof.get('rollback'),owner)
    expected=prior.get('patched_resource_sha256')if owner==GRID else prior.get('final_swf_sha256')
    if sha(base)!=proof.get('baseline_swf_sha256')or sha(base)!=expected or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256'):raise ValueError('Original complete predecessor bytes differ')
    if 'row_delta_contract'not in prior:raise ValueError('Current exact RowDelta predecessor missing/downgraded')
    if(previous.verify_adapter(prior,base)if owner==GRID else previous.verify_main(prior,base))is not True:raise ValueError('Full recursive preceding chain differs')
    result={'previous_stage_adapter'if owner==GRID else'previous_stage_contract':copy.deepcopy(prior),
            'previous_stage_sha256':comm.contract_digest(prior),'physical_position_contract':copy.deepcopy(proof),'postproof_sha256':comm.contract_digest(proof),
            'patched_resource_sha256'if owner==GRID else'final_swf_sha256':sha(final)}
    if owner==GRID:result['base_resource_sha256']=prior['base_resource_sha256']
    return result
def verify_adapter(adapter,final):
    if not isinstance(adapter,dict)or chain(adapter.get('previous_stage_adapter'),adapter.get('physical_position_contract'),final,GRID)!=adapter:raise ValueError('Complete physical-position adapter differs')
    return True
def historical(adapter,final,owner=GRID):
    if owner!=GRID:raise ValueError("Physical positions do not patch Main")
    verify_adapter(adapter,final)
    return adapter['previous_stage_adapter'if owner==GRID else'previous_stage_contract'],reconstruct(final,adapter['physical_position_contract']['rollback'],owner)

def _transplant(prior,base,compiled,ffdec,work,owner,start):
    from cas_ui_build import replace_payload
    work=Path(work);ffdec=Path(ffdec);classes=work/'classes';classes.mkdir(exist_ok=True)
    jar=ffdec.with_name('ffdec.jar');project=presentation.ROOT
    comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',project/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridPhysicalPatch.java'],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json';mode='grid'if owner==GRID else'main'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridPhysicalPatch',mode,work/'baseline.swf',compiled,output,report],work/'transplant.log')
    if start!=pins():raise ValueError('Physical position source changed during compilation')
    final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
    proof.update(source_sha256=start,previous_stage_sha256=comm.contract_digest(prior),
                 rollback=mechanics.build_descriptor(base,owner,inventory(owner)[0]),final_swf_sha256=sha(final))
    return final,chain(prior,proof,final,owner)

def adapt(prior,base,original,ffdec,work):
    if not isinstance(prior,dict)or 'row_delta_contract'not in prior or previous.verify_adapter(prior,base)is not True:raise ValueError('Physical position requires complete current RowDelta provider')
    if sha(Path(original).read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Original native provider identity differs')
    work=Path(work);ffdec=Path(ffdec);work.mkdir(parents=True,exist_ok=True);start=pins();(work/'baseline.swf').write_bytes(base)
    native=work/'native-source';comm.run([ffdec,'-selectclass',GRID,'-export','script',native,original],work/'export.log')
    text=presentation.inject_grid((native/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig'));before=presentation.helpers()
    if text.count(before)!=1:raise ValueError('Exact native compiler helper seam differs')
    text=text.replace(before,helpers(),1).replace('   import flash.display.DisplayObject;','   import flash.utils.getQualifiedClassName;\n   import flash.display.DisplayObject;',1)
    owned=work/'RecyclingGridLayout.as';owned.write_text(text,encoding='utf-8');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',work/'baseline.swf',compiled,GRID,owned],work/'compile.log')
    return _transplant(prior,base,compiled,ffdec,work,GRID,start)

def unwrap_providers(evidence,resources,dependencies=None):
    import dbpf_build,maru_companion
    keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
    if not isinstance(evidence,dict)or set(evidence)!=keys:raise ValueError('Both current physical-position providers required')
    out=dict(resources);providers={}
    for name in keys:
        a=evidence[name]
        if not isinstance(a,dict)or 'physical_position_contract'not in a:raise ValueError('Physical position provider absent/downgraded')
        key=tuple(int(n,16)for n in name.split(':'));providers[name],out[key]=historical(a,resources.get(key,b''))
    return providers,out,dependencies

def unwrap_manifest(info,resources):
    import dbpf_build,maru_companion
    source=info.get('source_pins',{});providers=info.get('grid_provider_adapters')
    current=any(n in source for n in SOURCES)or any(isinstance(a,dict)and 'physical_position_contract'in a for a in(providers or {}).values())
    if not current:return info,resources
    if not isinstance(source,dict)or any(source.get(n)!=v for n,v in pins().items()):raise ValueError('Physical-position source pins missing/partial/stale')
    donor=dbpf_build.tgi(maru_companion.GRID_LIBRARY)
    if not isinstance(providers,dict)or not isinstance(info.get('companion_code_merge'),dict)or info['companion_code_merge'].get('grid_library_adapter')!=providers.get(donor):raise ValueError('Advertised physical-position donor alias differs')
    for n in(dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
        k=tuple(int(v,16)for v in n.split(':'))
        if info.get('patched_resources',{}).get(n)!=sha(resources.get(k,b'')):raise ValueError('Advertised physical-position provider bytes differ')
    p,r,_=unwrap_providers(providers,resources);updated=copy.deepcopy(info);updated['grid_provider_adapters']=p
    updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
    for n,a in p.items():updated['patched_resources'][n]=a['patched_resource_sha256']
    return updated,r
