"""One-class swatch geometry graft on both exact library providers.

The complete preceding product/presentation/progress authority remains required.
No native body is replaced, and raw rollback must reconstruct that exact resource.
"""
from pathlib import Path
import json,os,re
import cas_grid_progress as previous
import cas_swatch_geometry as swatch
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as comm

ROOT=Path(__file__).resolve().parents[1]
TYPE='ColorSwatchPanel'
QUALIFIED='widgets.CAS.controls.'+TYPE
METHOD='ApexSwatchGeometry'
SEMANTIC='b7e342acf4dfb73f9512fa04b39938e3da60b9b4272d422f17cbff68e9309328'
ORIGINALS={'6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0',
           '5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae'}
DECLARING='6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0'
ABSENT='5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae'
SOURCES=('tools/cas_swatch_provider.py','tools/CasSwatchProviderPatch.java',
         'tools/CasStructuralRolesPatch.java','tools/CasCommunicationIndexPatch.java',
         'tools/cas_swatch_geometry.py','Source/CASUi/swatch_geometry_adapter_methods.as')
sha=swatch.digest

def pins():return {n:sha((ROOT/n).read_bytes()) for n in SOURCES}

def semantic(a,row):
    text=swatch.semantic(a,row)
    text=re.sub(r'(?<=5:)ColorSwatchPanel\.as\$[0-9]+','ColorSwatchPanel.as$SELF',text)
    rows=list(re.finditer(r'(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$',text))
    if rows:
        base=min(int(r.group(2)) for r in rows)
        text=re.sub(r'(?m)^(239:1:.*:[0-9]+):([1-9][0-9]*)$',lambda m:m.group(1)+':owned-source+'+str(int(m.group(2))-base),text)
    return text

def descriptor(base):
    _,raw=binding._abc_payload(base);a=binding._ABC(raw).parse()
    scope=swatch.method(a,TYPE,'ResetLayout')[2]['value']['frame'][2]
    return {'pool_counts':[p['count'] for p in a.pools],'scope':scope}

def reconstruct(final,proof):
    from cas_ui_build import replace_payload
    prefix,raw=binding._abc_payload(final);a=binding._ABC(raw).parse();d=proof.get('rollback')
    if proof.get('provider_declares_swatch')is False:
        if proof.get('original_provider_sha256')!=ABSENT or d!={'unchanged_resource':True} or any(a.qname(i['name'])=='7:'+TYPE+':22:widgets.CAS.controls' for i in a.instances):raise ValueError('Nondeclaring swatch provider inventory differs.')
        return bytes(final)
    if not isinstance(d,dict) or set(d)!={'pool_counts','scope'} or type(d['scope'])is not int:raise ValueError('Swatch-provider exact rollback absent.')
    if not isinstance(d['pool_counts'],list) or len(d['pool_counts'])!=7:raise ValueError('Swatch-provider pool prefix absent.')
    owner,t,b=swatch.method(a,TYPE,METHOD);v=t['value'];traits=owner['traits'];total=a.methods['count']-1
    if(v['method']!=total or t!=traits['rows'][-1] or b!=a.bodies['rows'][-1] or v['flags']!=1 or v['dispatch']!=0 or
       a.qname(v['name'])!='7:'+METHOD+':22:' or b['value']['frame'][2]!=d['scope'] or sha(semantic(a,b).encode())!=SEMANTIC):raise ValueError('Reviewed appended swatch-provider method differs.')
    _,f=swatch.named(a,TYPE,'apexSwatchGeometry');fv=f['value']
    if(f!=traits['rows'][-2] or fv['flags']!=0 or fv['slot']!=0 or fv['value']!=0 or a.qname(fv['type'])!='7:Object:22:' or
       a.qname(fv['name'])!='7:apexSwatchGeometry:5:widgets.CAS.controls:ColorSwatchPanel'):raise ValueError('Swatch-provider state is not exact private default-null Object.')
    patches=[(traits['start'],traits['end'],attach._u30(traits['count']-2)+raw[traits['head']:traits['rows'][-2]['start']])]
    for table in(a.methods,a.bodies):patches.append((table['start'],table['end'],attach._u30(table['count']-1)+raw[table['head']:table['rows'][-1]['start']]))
    for pool,count in zip(a.pools,d['pool_counts']):
        if type(count)is not int or not 0<=count<=pool['count']:raise ValueError('Swatch-provider pool prefix differs.')
        end=pool['head'] if count<=1 else pool['rows'][count-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count)+raw[pool['head']:end]))
    limit=len(raw)
    for start,end,value in sorted(patches,reverse=True):
        if end>limit or start>end:raise ValueError('Swatch-provider rollback spans overlap.')
        raw=raw[:start]+value+raw[end:];limit=start
    return replace_payload(final,prefix+raw)

def chain_adapter(prior,proof,final):
    flags=('same_native_class_scope','same_native_field_bindings','original_callbacks_feeds_initializers_retained','all_unrelated_bodies_exact','full_abc_rollback_exact')
    declares=isinstance(proof,dict) and proof.get('provider_declares_swatch')is True
    count=1 if declares else 0
    if(not isinstance(prior,dict) or not isinstance(proof,dict) or proof.get('ok')is not True or proof.get('phase')!='native-swatch-provider' or
       any(proof.get(k)is not True for k in flags) or proof.get('original_provider_sha256')not in ORIGINALS or
       proof.get('original_provider_sha256')!=prior.get('base_resource_sha256') or
       type(proof.get('provider_declares_swatch'))is not bool or declares!=(proof.get('original_provider_sha256')==DECLARING) or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in {'appended_methods':count,'appended_fields':count,'changed_native_bodies':0}.items()) or
       proof.get('source_sha256')!=pins() or proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False or
       proof.get('previous_stage_sha256')!=comm.contract_digest(prior) or proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256') or
       proof.get('final_swf_sha256')!=sha(final) or proof.get('abc_sha256')!=sha(binding._abc_payload(final)[1])):raise ValueError('Swatch-provider continuation/provenance differs.')
    base=reconstruct(final,proof)
    if sha(base)!=proof['baseline_swf_sha256'] or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256') or previous.verify_adapter(prior,base)is not True:raise ValueError('Swatch-provider complete prior continuation differs.')
    return dict(base_resource_sha256=prior['base_resource_sha256'],patched_resource_sha256=sha(final),previous_stage_adapter=json.loads(json.dumps(prior)),previous_stage_sha256=comm.contract_digest(prior),swatch_provider_contract=json.loads(json.dumps(proof)),postproof_sha256=comm.contract_digest(proof))

def verify_adapter(adapter,final):
    if not isinstance(adapter,dict) or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('swatch_provider_contract'),final)!=adapter:raise ValueError('Swatch-provider adapter differs.')
    return True

def adapt(prior,base,original,ffdec,work):
    from cas_ui_build import replace_payload
    base=bytes(base);original=Path(original);ffdec=Path(ffdec);work=Path(work)
    if previous.verify_adapter(prior,base)is not True or 'progress_contract'not in prior:raise ValueError('Swatch-provider requires complete progress/presentation history.')
    if sha(original.read_bytes())!=prior.get('base_resource_sha256') or prior['base_resource_sha256']not in ORIGINALS:raise ValueError('Exact original swatch provider differs.')
    start=pins();work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(base);source=work/'native-source'
    if prior['base_resource_sha256']==ABSENT:
        # ClassLibraryGamedata has no ColorSwatchPanel. Never add a second class
        # or pretend an adapter was installed there: authenticate the complete
        # no-op resource and retain the preceding progress proof exactly.
        for data in(base,original.read_bytes()):
            a=binding._ABC(binding._abc_payload(data)[1]).parse()
            if any(a.qname(i['name'])=='7:'+TYPE+':22:widgets.CAS.controls' for i in a.instances):raise ValueError('Expected nondeclaring swatch provider gained the class.')
        proof=dict(ok=True,phase='native-swatch-provider',provider_declares_swatch=False,baseline_swf_sha256=sha(base),baseline_abc_sha256=sha(binding._abc_payload(base)[1]),abc_sha256=sha(binding._abc_payload(base)[1]),original_provider_sha256=ABSENT,appended_methods=0,appended_fields=0,changed_native_bodies=0,same_native_class_scope=True,same_native_field_bindings=True,original_callbacks_feeds_initializers_retained=True,all_unrelated_bodies_exact=True,full_abc_rollback_exact=True,runtime_qualified=False,performance_gain_claimed=False,source_sha256=start,previous_stage_sha256=comm.contract_digest(prior),rollback={'unchanged_resource':True},final_swf_sha256=sha(base))
        return base,chain_adapter(prior,proof,base)
    comm.run([ffdec,'-selectclass',QUALIFIED,'-export','script',source,original],work/'export.log')
    owned=work/(TYPE+'.as');owned.write_text(swatch.inject((source/'scripts/widgets/CAS/controls/ColorSwatchPanel.as').read_text(encoding='utf-8-sig'),(ROOT/SOURCES[-1]).read_text(encoding='utf-8')),encoding='utf-8')
    compiled=work/'compiled.swf';comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,QUALIFIED,owned],work/'ffdec.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
    comm.run(['javac','-cp',jar,'-d',classes,ROOT/'tools/CasStructuralRolesPatch.java',ROOT/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasSwatchProviderPatch.java'],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasSwatchProviderPatch',incoming,compiled,original,output,report],work/'transplant.log')
    abc=output.read_bytes();proof=json.loads(report.read_text());final=replace_payload(base,binding._abc_payload(base)[0]+abc)
    if start!=pins():raise ValueError('Swatch-provider sources changed during compilation.')
    proof.update(provider_declares_swatch=True,source_sha256=start,previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base),final_swf_sha256=sha(final))
    return final,chain_adapter(prior,proof,final)

def historical(adapter,final):
    verify_adapter(adapter,final)
    return adapter['previous_stage_adapter'],reconstruct(final,adapter['swatch_provider_contract'])

def unwrap_providers(evidence,resources,dependencies=None):
    import dbpf_build,maru_companion
    keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
    if not isinstance(evidence,dict) or set(evidence)!=keys:raise ValueError('Both swatch-library providers required.')
    out=dict(resources);providers={}
    for key in keys:
        a=evidence[key]
        if not isinstance(a,dict) or 'swatch_provider_contract'not in a:raise ValueError('Both native providers require exact swatch continuation.')
        tgi=tuple(int(n,16) for n in key.split(':'));providers[key],out[tgi]=historical(a,resources.get(tgi,b''))
    return providers,out,dependencies

def unwrap_manifest(info,resources):
    source=info.get('source_pins',{});providers=info.get('grid_provider_adapters')
    # Shared historic geometry fragments are insufficient to imply this NEW
    # layer. Its unique tools, or any provider proof, require all exact pins.
    current=any(n in source for n in SOURCES[:2]) or any(isinstance(a,dict) and 'swatch_provider_contract'in a for a in(providers or {}).values())
    if not current:return info,resources
    if not isinstance(source,dict) or any(source.get(k)!=v for k,v in pins().items()):raise ValueError('Swatch-provider source pins are missing, partial or stale.')
    import dbpf_build,maru_companion
    p,r,_=unwrap_providers(providers,resources);updated=json.loads(json.dumps(info));updated['grid_provider_adapters']=p
    updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
    for key,adapter in p.items():updated['patched_resources'][key]=adapter['patched_resource_sha256']
    return updated,r
