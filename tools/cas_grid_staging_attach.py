"""Keep freshly attached pending widgets off the committed presentation.

One owned body only. Predecessor kind is explicit: production follows the
Publication stage; authenticated Featured fixtures can be reviewed separately.
"""
from pathlib import Path
import copy,hashlib,importlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1]
PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_featured.py').is_file())
sys.path.insert(0,str(PROJECT/'tools'))
import cas_grid_featured as featured
import cas_grid_budget as mechanics
import cas_grid_presentation as presentation
import cas_grid_pool as pool
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as comm
GRID=featured.GRID;REPLACED=('ApexGridAttach',)
SOURCES=('tools/cas_grid_staging_attach.py','tools/CasGridStagingAttachPatch.java','Source/CASUi/catalog_grid_staging_attach_methods.as')
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def pins():return {n:sha((ROOT/n).read_bytes())for n in SOURCES}
def fragment():return (ROOT/SOURCES[-1]).read_text(encoding='utf-8-sig').strip()
def extend(source):
    a,b=pool.method_extent(source,'ApexGridAttach');old=source[a:b]
    if ''.join(old.split())!='publicfunctionApexGridAttach(cell:Object):void{mGridView.addChild(cellasDisplayObject);}':raise ValueError('Exact preceding native addChild body differs')
    return source[:a]+fragment()+source[b:]
def helpers(base=None,kind='publication'):
    if base is None:
        if kind=='publication':base=importlib.import_module('cas_grid_publication').helpers()
        elif kind=='featured-fixture':base=featured.helpers()
        else:raise ValueError('Explicit supported attach helper predecessor required')
    return extend(base)
def compiler_source():
    # Only declarations needed to compile this body. No constructor/field/body
    # from this stub enters the retained ABC; full rollback proves that.
    return 'package olympus.layout {\nimport flash.display.DisplayObject;\npublic class RecyclingGridLayout extends GridLayout {\nprivate var apexGridState:Object;\npublic function RecyclingGridLayout(){super();}\n'+fragment()+'\n}\n}\n'
def verify_prior(prior,base,kind):
    if kind=='featured-fixture':return featured.verify_adapter(prior,base)
    if kind=='publication':
        module=importlib.import_module('cas_grid_publication')
        return module.verify_adapter(prior,base)
    raise ValueError('Explicit supported complete predecessor verifier required')
def semantic_pin():
    rows=re.findall(r'static final String PIN="([0-9a-f]{64})";',(ROOT/SOURCES[1]).read_text())
    if len(rows)!=1:raise ValueError('Exactly one staging attach semantic pin required')
    return rows[0]
def descriptor(base):return mechanics.build_descriptor(base,GRID,REPLACED)
def reconstruct(final,d):
    from cas_ui_build import replace_payload
    prefix,raw=binding._abc_payload(final);a=mechanics.ABC(raw).parse()
    if not isinstance(d,dict)or set(d)!={'pool_counts','bodies'}or set(d['bodies'])!=set(REPLACED)or not isinstance(d['pool_counts'],list)or len(d['pool_counts'])!=7:raise ValueError('Exact attach raw rollback inventory missing')
    text=d['bodies']['ApexGridAttach']
    if not isinstance(text,str)or re.fullmatch('[0-9a-f]{2,200000}',text)is None:raise ValueError('Original attach body malformed')
    old=bytes.fromhex(text);reader=mechanics.ABC(old);body=reader.body();row=presentation.named(a,GRID,'ApexGridAttach')[1]
    if reader.at!=len(old)or body['method']!=row['value']['method']or body['frame'][2]!=row['value']['frame'][2]:raise ValueError('Original attach method/scope differs')
    info=a.methods['rows'][row['value']['method']]['value']
    if info['flags']!=0 or row['value']['traits']['count']!=0 or row['value']['exceptions']or sha(presentation.semantic(a,row).encode())!=semantic_pin():raise ValueError('Reviewed attach semantic/activation differs')
    patches=[(row['start'],row['end'],old)]
    for p,count in zip(a.pools,d['pool_counts']):
        if type(count)is not int or not 0<=count<=p['count']:raise ValueError('Exact attach constant prefix malformed')
        end=p['head']if count<=1 else p['rows'][count-2]['end'];patches.append((p['start'],p['end'],attach._u30(count)+raw[p['head']:end]))
    limit=len(raw)
    for start,end,value in sorted(patches,reverse=True):
        if end>limit or start>end:raise ValueError('Attach rollback spans overlap')
        raw=raw[:start]+value+raw[end:];limit=start
    return replace_payload(final,prefix+raw)
def chain_adapter(prior,proof,final):
    required=('whole_abc_rollback_verified','all_unowned_bodies_retained','serialized_owned_body_verified','native_bindings_verified')
    kind=proof.get('previous_stage_kind')if isinstance(proof,dict)else None
    if(not isinstance(prior,dict)or not isinstance(proof,dict)or proof.get('ok')is not True or
       any(proof.get(k)is not True for k in required)or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in{'owned_replacements':1,'new_methods':0,'new_traits':0,'new_fields':0,'changed_original_native_bodies':0}.items())or
       proof.get('source_sha256')!=pins()or proof.get('helper_source_sha256')!=sha(fragment().encode())or
       proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256')or
       proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False):raise ValueError('Complete staging attach continuation proof differs')
    if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Attach final SWF/ABC identity differs')
    base=reconstruct(final,proof.get('rollback'))
    if sha(base)!=proof.get('baseline_swf_sha256')or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256')or verify_prior(prior,base,kind)is not True:raise ValueError('Attach complete preceding history differs')
    return {'base_resource_sha256':prior['base_resource_sha256'],'patched_resource_sha256':sha(final),'previous_stage_kind':kind,
            'previous_stage_adapter':copy.deepcopy(prior),'previous_stage_sha256':comm.contract_digest(prior),
            'staging_attach_contract':copy.deepcopy(proof),'postproof_sha256':comm.contract_digest(proof)}
def verify_adapter(adapter,final):
    if not isinstance(adapter,dict)or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('staging_attach_contract'),final)!=adapter:raise ValueError('Complete staging attach adapter differs')
    return True
def historical(adapter,final):
    verify_adapter(adapter,final)
    return adapter['previous_stage_adapter'],reconstruct(final,adapter['staging_attach_contract']['rollback'])
def adapt(prior,base,original,ffdec,work,kind='publication'):
    from cas_ui_build import replace_payload
    import os
    base=bytes(base);original=Path(original);ffdec=Path(ffdec);work=Path(work)
    if verify_prior(prior,base,kind)is not True:raise ValueError('Exact complete attach predecessor required')
    if sha(original.read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Attach original native provider differs')
    start=pins();work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(base)
    owned=work/'RecyclingGridLayout.as';owned.write_text(compiler_source(),encoding='utf-8',newline='\n');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,GRID,owned],work/'compile.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,PROJECT/'tools/CasStructuralRolesPatch.java',PROJECT/'tools/CasCommunicationIndexPatch.java',ROOT/SOURCES[1]],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json'
    comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridStagingAttachPatch',incoming,compiled,output,report],work/'transplant.log')
    if start!=pins():raise ValueError('Attach sources changed during compile')
    final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
    proof.update(source_sha256=start,helper_source_sha256=sha(fragment().encode()),previous_stage_kind=kind,previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base),final_swf_sha256=sha(final))
    return final,chain_adapter(prior,proof,final)
def unwrap_providers(evidence,resources,dependencies=None):
    import dbpf_build,maru_companion
    keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
    if not isinstance(evidence,dict)or set(evidence)!=keys:raise ValueError('Both staging attach providers required')
    out=dict(resources);providers={}
    for key in keys:
        adapter=evidence[key]
        if not isinstance(adapter,dict)or adapter.get('previous_stage_kind')!='publication' or not isinstance(adapter.get('staging_attach_contract'),dict):raise ValueError('Production attach requires exact Publication predecessor')
        native=tuple(int(n,16)for n in key.split(':'));providers[key],out[native]=historical(adapter,resources.get(native,b''))
    return providers,out,dependencies
def unwrap_manifest(info,resources):
    import dbpf_build,maru_companion
    source=info.get('source_pins',{});providers=info.get('grid_provider_adapters')
    current=any(n in source for n in SOURCES)or any(isinstance(a,dict)and'staging_attach_contract'in a for a in(providers or{}).values())
    if not current:return info,resources
    if not isinstance(source,dict)or any(source.get(n)!=v for n,v in pins().items()):raise ValueError('Attach source pins missing/partial/stale')
    for key in(dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
        native=tuple(int(n,16)for n in key.split(':'))
        if info.get('patched_resources',{}).get(key)!=sha(resources.get(native,b'')):raise ValueError('Advertised attach provider final identity differs')
    prior,restored,_=unwrap_providers(providers,resources);updated=copy.deepcopy(info);updated['grid_provider_adapters']=prior
    updated['companion_code_merge']['grid_library_adapter']=prior[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
    for key,adapter in prior.items():updated['patched_resources'][key]=adapter['patched_resource_sha256']
    return updated,restored
