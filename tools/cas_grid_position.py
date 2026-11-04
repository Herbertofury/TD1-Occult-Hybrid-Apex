"""Gate the exact native PositionCells override before its unconditional selection tail.

Exact current Spare-terminal provider-only continuation, with complete native ABC rollback.
All build inputs and source pins are repository-relative; no private work paths.
"""
from pathlib import Path
import copy,hashlib,json,re,os
ROOT=Path(__file__).resolve().parents[1]
import cas_grid_position_stage as stage
import cas_grid_spares as previous
import cas_grid_budget as mechanics
import cas_grid_presentation as presentation
import cas_grid_publication as publication
import cas_grid_staging_attach as staging_attach
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as comm
GRID='olympus.layout.SelectableRecyclingGridLayout';MAIN=publication.MAIN
SOURCES=('tools/cas_grid_position.py','tools/cas_grid_position_stage.py','tools/CasGridPositionPatch.java','Source/CASUi/catalog_native_position_gate.as')
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def pins():return {n:sha((ROOT/n).read_bytes())for n in SOURCES}
def helpers():return stage.fragment()
TARGETS=((GRID,'PositionCells'),(stage.REC,'ApexGridBegin'),(stage.REC,'ApexGridNativeGuard'),(stage.REC,'ApexGridMetrics'))

def inventory(owner):
    if owner!=GRID:raise ValueError('Exact native/owned position diagnostic class set required')
    return tuple(kind+'/'+name for kind,name in TARGETS),()

def semantic_pins(owner):
    rows=re.findall(r'Map.entry\("([^"\n]+)","([0-9a-f]{64})"\)',(ROOT/SOURCES[2]).read_text())
    result=dict(rows)
    if len(rows)!=len(TARGETS)or set(result)!=set(inventory(owner)[0]):raise ValueError('Complete native/owned semantic inventory missing')
    return result

def descriptor(base):
    prefix,raw=binding._abc_payload(base);a=mechanics.ABC(raw).parse()
    return {'pool_counts':[r['count']for r in a.pools],'bodies':{kind+'/'+name:raw[b['start']:b['end']].hex()for kind,name in TARGETS for b in[presentation.named(a,kind,name)[1]]}}

def reconstruct(final,d,owner):
    from cas_ui_build import replace_payload
    names,_=inventory(owner);prefix,raw=binding._abc_payload(final);a=mechanics.ABC(raw).parse()
    if not isinstance(d,dict)or set(d)!={'pool_counts','bodies'}or set(d['bodies'])!=set(names):raise ValueError('Exact native/owned rollback inventory missing')
    if not isinstance(d['pool_counts'],list)or len(d['pool_counts'])!=7:raise ValueError('Exact constant prefix missing')
    frozen=semantic_pins(owner);restored={};patches=[]
    for key,text in d['bodies'].items():
        if not isinstance(text,str)or re.fullmatch('[0-9a-f]{2,200000}',text)is None:raise ValueError('Original native/owned body malformed or unbounded')
        kind,name=key.rsplit('/',1);value=bytes.fromhex(text);r=mechanics.ABC(value);old=r.body();row=presentation.named(a,kind,name)[1]
        if r.at!=len(value)or old['method']!=row['value']['method']or old['frame'][2]!=row['value']['frame'][2]:raise ValueError('Original callable/scope target differs')
        if sha(presentation.semantic(a,row).encode())!=frozen[key]:raise ValueError('Reviewed native/owned semantic/CFG differs: '+key)
        if any(op in(0x40,0x43,0x44,0x67)for _,_,op,_ in a.instructions(row['value']['code'])):raise ValueError('Foreign nested/outer linkage')
        restored[old['method']]=value
    for p,count in zip(a.pools,d['pool_counts']):
        if type(count)is not int or not 0<=count<=p['count']:raise ValueError('Constant prefix malformed')
        end=p['head']if count<=1 else p['rows'][count-2]['end'];patches.append((p['start'],p['end'],attach._u30(count)+raw[p['head']:end]))
    table=a.bodies;patches.append((table['start'],table['end'],attach._u30(table['count'])+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']])for r in table['rows'])))
    limit=len(raw)
    for start,end,value in sorted(patches,reverse=True):
        if end>limit or start>end:raise ValueError('Rollback spans overlap')
        raw=raw[:start]+value+raw[end:];limit=start
    return replace_payload(final,prefix+raw)

def chain(prior,proof,final,owner):
    replaced,added=inventory(owner)
    required=('whole_abc_rollback_verified','all_unowned_bodies_retained','serialized_owned_bodies_verified','native_protected_bindings_verified')
    if(not isinstance(prior,dict)or not isinstance(proof,dict)or proof.get('ok')is not True or proof.get('mode')!=('grid'if owner==GRID else'main')or
       any(proof.get(k)is not True for k in required)or proof.get('runtime_class_QName_verified')is not False or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in {'replaced_owned_bodies':3,'replaced_native_bodies':1,'appended_methods':len(added),'appended_fields':0,'changed_original_native_bodies':1}.items())or
       proof.get('source_sha256')!=pins()or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or
       proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False):raise ValueError('Complete native-position proof differs')
    if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Final SWF/ABC identity differs')
    base=reconstruct(final,proof.get('rollback'),owner)
    expected=prior.get('patched_resource_sha256')if owner==GRID else prior.get('final_swf_sha256')
    if sha(base)!=proof.get('baseline_swf_sha256')or sha(base)!=expected or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256'):raise ValueError('Original complete predecessor bytes differ')
    if 'spare_custody_contract'not in prior:raise ValueError('Current exact Spare predecessor missing/downgraded')
    if(previous.verify_adapter(prior,base)if owner==GRID else previous.verify_main(prior,base))is not True:raise ValueError('Full recursive preceding chain differs')
    result={'previous_stage_adapter'if owner==GRID else'previous_stage_contract':copy.deepcopy(prior),
            'previous_stage_sha256':comm.contract_digest(prior),'native_position_contract':copy.deepcopy(proof),'postproof_sha256':comm.contract_digest(proof),
            'patched_resource_sha256'if owner==GRID else'final_swf_sha256':sha(final)}
    if owner==GRID:result['base_resource_sha256']=prior['base_resource_sha256']
    return result
def verify_adapter(adapter,final):
    if not isinstance(adapter,dict)or chain(adapter.get('previous_stage_adapter'),adapter.get('native_position_contract'),final,GRID)!=adapter:raise ValueError('Complete native-position adapter differs')
    return True
def historical(adapter,final,owner=GRID):
    if owner!=GRID:raise ValueError("Native position gate does not patch Main")
    verify_adapter(adapter,final)
    return adapter['previous_stage_adapter'if owner==GRID else'previous_stage_contract'],reconstruct(final,adapter['native_position_contract']['rollback'],owner)

def _transplant(prior,base,compiled,ffdec,work,owner,start):
    from cas_ui_build import replace_payload
    work=Path(work);ffdec=Path(ffdec);classes=work/'classes';classes.mkdir(exist_ok=True)
    jar=ffdec.with_name('ffdec.jar');project=presentation.ROOT
    comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',project/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridPositionPatch.java'],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json';mode='grid'if owner==GRID else'main'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridPositionPatch',mode,work/'baseline.swf',compiled,output,report],work/'transplant.log')
    if start!=pins():raise ValueError('Native position gate source changed during compilation')
    final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
    proof.update(source_sha256=start,previous_stage_sha256=comm.contract_digest(prior),
                 rollback=descriptor(base),final_swf_sha256=sha(final))
    return final,chain(prior,proof,final,owner)

def adapt(prior,base,original,ffdec,work):
    if not isinstance(prior,dict)or 'spare_custody_contract'not in prior or previous.verify_adapter(prior,base)is not True:raise ValueError('Native position gate requires complete current Spare provider')
    if sha(Path(original).read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Original native provider identity differs')
    work=Path(work);ffdec=Path(ffdec);work.mkdir(parents=True,exist_ok=True);start=pins();(work/'baseline.swf').write_bytes(base)
    native=work/'native-source';comm.run([ffdec,'-selectclass',stage.REC,'-export','script',native,original],work/'export-grid.log')
    text=presentation.inject_grid((native/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig'));before=presentation.helpers()
    if text.count(before)!=1:raise ValueError('Exact complete provider source seam differs')
    text=text.replace(before,stage.helpers(),1).replace('   import flash.display.DisplayObject;','   import flash.utils.getQualifiedClassName;\n   import flash.display.DisplayObject;',1)
    owned=work/'RecyclingGridLayout.as';owned.write_text(text,encoding='utf-8');grid=work/'compiled-grid.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',work/'baseline.swf',grid,stage.REC,owned],work/'compile-grid.log')
    comm.run([ffdec,'-selectclass',GRID,'-export','script',native,original],work/'export-position.log')
    text=stage.inject((native/'scripts/olympus/layout/SelectableRecyclingGridLayout.as').read_text(encoding='utf-8-sig'))
    owned=work/'SelectableRecyclingGridLayout.as';owned.write_text(text,encoding='utf-8');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',grid,compiled,GRID,owned],work/'compile-position.log')
    return _transplant(prior,base,compiled,ffdec,work,GRID,start)

def unwrap_providers(evidence,resources,dependencies=None):
    import dbpf_build,maru_companion
    keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
    if not isinstance(evidence,dict)or set(evidence)!=keys:raise ValueError('Both current native-position providers required')
    out=dict(resources);providers={}
    for name in keys:
        a=evidence[name]
        if not isinstance(a,dict)or 'native_position_contract'not in a:raise ValueError('Native position gate provider absent/downgraded')
        key=tuple(int(n,16)for n in name.split(':'));providers[name],out[key]=historical(a,resources.get(key,b''))
    return providers,out,dependencies

def unwrap_manifest(info,resources):
    import dbpf_build,maru_companion
    source=info.get('source_pins',{});providers=info.get('grid_provider_adapters')
    current=any(n in source for n in SOURCES)or any(isinstance(a,dict)and 'native_position_contract'in a for a in(providers or {}).values())
    if not current:return info,resources
    if not isinstance(source,dict)or any(source.get(n)!=v for n,v in pins().items()):raise ValueError('Spare-custody source pins missing/partial/stale')
    donor=dbpf_build.tgi(maru_companion.GRID_LIBRARY)
    if not isinstance(providers,dict)or not isinstance(info.get('companion_code_merge'),dict)or info['companion_code_merge'].get('grid_library_adapter')!=providers.get(donor):raise ValueError('Advertised native-position donor alias differs')
    for n in(dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
        k=tuple(int(v,16)for v in n.split(':'))
        if info.get('patched_resources',{}).get(n)!=sha(resources.get(k,b'')):raise ValueError('Advertised native-position provider bytes differ')
    p,r,_=unwrap_providers(providers,resources);updated=copy.deepcopy(info);updated['grid_provider_adapters']=p
    updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
    for n,a in p.items():updated['patched_resources'][n]=a['patched_resource_sha256']
    return updated,r
