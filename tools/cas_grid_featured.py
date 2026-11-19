"""Private exact Featured schema continuation after the frozen slice provider."""
from pathlib import Path
import copy, hashlib, json, os, re
import cas_grid_budget as previous
import cas_grid_scroll as scroll
import cas_grid_pool as pool
import cas_grid_presentation as presentation
import cas_communication_index as comm
import cas_catalog_binding as binding
import cas_cell_attach as attach

ROOT=Path(__file__).resolve().parents[1]
GRID=scroll.GRID
MAIN=scroll.MAIN
REPLACED=('ApexGridBind','ApexGridReady','ApexGridNativeGuard')
ADDED=('ApexGridFeaturedIdentity','ApexGridFeaturedSame')
MAIN_REPLACED=('ApexCatalogGridProductPanel','ApexCatalogGridPrepare','ApexCatalogGridRequest')
MAIN_ADDED=('ApexCatalogGridFeaturedIdentity',)
SOURCES=('tools/cas_grid_featured.py','tools/CasGridFeaturedPatch.java','tools/CasGridFeaturedMainPatch.java',
         'Source/CASUi/catalog_featured_identity_methods.as','Source/CASUi/catalog_featured_main_identity.as')
sha=presentation.sha

def pins():return {n:sha((ROOT/n).read_bytes()) for n in SOURCES}

def helpers():
    source=previous.helpers()
    # Keep the existing product path and its exact favorite/variant checks. The
    # new branch is explicit and never projects a wrapper into a native product.
    source=pool.edit_method(source,'ApexGridBind',[
        ('var base:String=item==null ? null : String(item.data_id);',
         'var featured:Object=("featuredRowIdentity" in s.request && s.request.featuredRowIdentity!=null) ? ApexGridFeaturedIdentity(item) : null;\n         var base:String=item==null || featured!=null ? null : String(item.data_id);'),
        ('var variation:String=item==null ? null : String(item.GetVariationOrBaseId());',
         'var variation:String=item==null || featured!=null ? null : String(item.GetVariationOrBaseId());'),
        ('var body:int=item==null ? -1 : int(item.body_type);',
         'var body:int=item==null || featured!=null ? -1 : int(item.body_type);'),
        ('var menu:int=item==null ? -1 : int(item.menu_state);',
         'var menu:int=item==null || featured!=null ? -1 : int(item.menu_state);'),
        ('j.boundBase=base;j.boundVariation=variation;j.boundBody=body;j.boundMenu=menu;',
         'j.boundBase=base;j.boundVariation=variation;j.boundBody=body;j.boundMenu=menu;j.boundFeatured=featured;')])
    a,b=pool.method_extent(source,'ApexGridReady');body=source[a:b]
    old='''GetDataIndexOfSortedIndex(j.boundSorted)!=j.boundData || String(item.data_id)!==j.boundBase ||
             String(item.GetVariationOrBaseId())!==j.boundVariation || int(item.body_type)!=j.boundBody || int(item.menu_state)!=j.boundMenu ||
             "dccFavoriteProductId" in cell && cell.dccFavoriteProductId!==j.boundBase'''
    if body.count(old)!=2:raise ValueError('Exact two product post-callback identity checks differ')
    after='''GetDataIndexOfSortedIndex(j.boundSorted)!=j.boundData ||
             (featured!=null || j.boundFeatured!=null ? !ApexGridFeaturedSame(featured,j.boundFeatured) :
             String(item.data_id)!==j.boundBase || String(item.GetVariationOrBaseId())!==j.boundVariation ||
             int(item.body_type)!=j.boundBody || int(item.menu_state)!=j.boundMenu ||
             "dccFavoriteProductId" in cell && cell.dccFavoriteProductId!==j.boundBase)'''
    body=body.replace(old,after)
    first='j.phaseMax.data=Math.max(Number(j.phaseMax.data)||0,getTimer()-started);'
    if body.count(first)!=2:raise ValueError('Exact two data read timing seams differ')
    at=body.index(first)+len(first);body=body[:at]+'\n         var featured:Object=("featuredRowIdentity" in s.request && s.request.featuredRowIdentity!=null) ? ApexGridFeaturedIdentity(item) : null;'+body[at:]
    at=body.rindex(first)+len(first);body=body[:at]+'\n         featured=("featuredRowIdentity" in s.request && s.request.featuredRowIdentity!=null) ? ApexGridFeaturedIdentity(item) : null;'+body[at:]
    source=source[:a]+body+source[b:]
    source=pool.edit_method(source,'ApexGridNativeGuard',[
        ('if(j.phase=="done" && !j.dirty && event!=null && s.ready[event.currentTarget]===j.generation)return false;',
         '''if(j.phase=="done" && !j.dirty && event!=null && s.ready[event.currentTarget]===j.generation) {
               // Featured Draw intentionally forces same-URI reloads. Queue its
               // genuine redraw into the hidden bank; never clear committed art.
               if(s.request!=null && "featuredRowIdentity" in s.request && s.request.featuredRowIdentity!=null) {
                  s.revision++;ApexTxnNotify(j,"update");return true;
               }
               return false;
            }''')])
    return source+'\n'+(ROOT/'Source/CASUi/catalog_featured_identity_methods.as').read_text(encoding='utf-8')

def inject_main(source):
    return extend_main(previous.inject_main(source))

def extend_main(source):
    imports=('gamedata.CAS.Customizer.CASFeaturedLook','widgets.CAS.controls.CASFeaturedFacelookCellView','widgets.CAS.data.FeaturedFaceLookDataFeed')
    for name in imports:
        if 'import '+name+';'not in source:source=source.replace('   import ','   import '+name+';\n   import ',1)
    source=pool.edit_method(source,'ApexCatalogGridProductPanel',[
        ('if(panel!==mcBodyModPanel && panel!==mcFaceModPanel && panel!==mcGenericCatalogPanel)return "";',
         'if(panel!==mcBodyModPanel && panel!==mcFaceModPanel && panel!==mcGenericCatalogPanel && panel!==mcFeaturedFaceLookPanel)return "";'),
        ('if(grid.GetDataFeed()==null)return "";',
         'if(grid.GetDataFeed()==null)return "";\n         if(panel===mcFeaturedFaceLookPanel)return cell===CASFeaturedFacelookCellView && grid.GetDataFeed() is FeaturedFaceLookDataFeed ? "featured" : "";')])
    source=pool.edit_method(source,'ApexCatalogGridPrepare',[
        ('rowValidate:kind=="clothing" ? null : ApexCatalogGridProductRow',
         'rowValidate:kind=="clothing" || kind=="featured" ? null : ApexCatalogGridProductRow,\n            featuredRowIdentity:kind=="featured" ? ApexCatalogGridFeaturedIdentity : null')])
    a,b=pool.method_extent(source,'ApexCatalogGridRequest');body=source[a:b]
    old='rowValidate:lease.panel_kind=="clothing" ? null : ApexCatalogGridProductRow'
    if body.count(old)!=2:raise ValueError('Exact two preceding Main request callbacks differ')
    body=body.replace(old,'rowValidate:lease.panel_kind=="clothing" || lease.panel_kind=="featured" ? null : ApexCatalogGridProductRow,\n               featuredRowIdentity:lease.panel_kind=="featured" ? ApexCatalogGridFeaturedIdentity : null')
    before='         if(view==null || list.mSlider==null'
    if body.count(before)!=1 or body.count('stepBudgetClockContract:nativeCardContract')!=2:raise ValueError('Exact local budget producer fields absent')
    body=body.replace(before,'         var featuredBudgetContract:int=(nativeCardContract==1 || lease.panel_kind=="featured" && lease.cell_type===CASFeaturedFacelookCellView) ? 1 : 0;\n'+before)
    body=body.replace('stepBudgetClockContract:nativeCardContract','stepBudgetClockContract:featuredBudgetContract')
    source=source[:a]+body+source[b:]
    ending=source.rfind('   }')
    return source[:ending]+(ROOT/'Source/CASUi/catalog_featured_main_identity.as').read_text(encoding='utf-8')+'\n'+source[ending:]

def semantics(owner=GRID):
    file='tools/CasGridFeaturedPatch.java' if owner==GRID else 'tools/CasGridFeaturedMainPatch.java'
    rows=re.findall(r'Map.entry\("([^\"]+)","([0-9a-f]{64})"\)',(ROOT/file).read_text())
    required=REPLACED+ADDED if owner==GRID else MAIN_REPLACED+MAIN_ADDED
    if len(rows)!=len(required) or {n for n,_ in rows}!={owner+'/'+n for n in required}:raise ValueError('Featured helper semantic inventory differs')
    return {n.rsplit('/',1)[1]:v for n,v in rows}

def descriptor(base,owner=GRID):
    return scroll.build_descriptor(base,owner,REPLACED if owner==GRID else MAIN_REPLACED)

def reconstruct(final,description,owner=GRID):
    # Reuse the exact raw-span mechanics, but bind this layer's distinct pins,
    # method inventory and private helper namespace/scope checks below.
    from cas_ui_build import replace_payload
    replaced,added=(REPLACED,ADDED)if owner==GRID else(MAIN_REPLACED,MAIN_ADDED)
    prefix,raw=binding._abc_payload(final);a=scroll.ABC(raw).parse();d=description
    if not isinstance(d,dict) or set(d)!={'pool_counts','bodies'} or set(d['bodies'])!=set(replaced):raise ValueError('Featured exact rollback inventory missing')
    if not isinstance(d['pool_counts'],list)or len(d['pool_counts'])!=7:raise ValueError('Featured constant prefix missing')
    restored={};patches=[];frozen=semantics(owner)
    for name,payload in d['bodies'].items():
        if not isinstance(payload,str)or not 0<len(payload)<=200000 or re.fullmatch('[0-9a-f]+',payload)is None:raise ValueError('Featured old body malformed')
        value=bytes.fromhex(payload);reader=scroll.ABC(value);old=reader.body();row=presentation.named(a,owner,name)[1]
        if reader.at!=len(value)or old['method']!=row['value']['method']or old['frame'][2]!=row['value']['frame'][2]:raise ValueError('Featured old method/scope changed')
        restored[old['method']]=value
    namespace,leaf=owner.rsplit('.',1);instance=next(r for r in a.instances if a.qname(r['name'])=='7:'+leaf+':22:'+namespace);traits=instance['traits'];count=len(added)
    initial=a.methods['count']-count;scope=presentation.named(a,owner,replaced[0])[1]['value']['frame'][2]
    for i,name in enumerate(added):
        t,b=presentation.named(a,owner,name);v=t['value']
        if(t!=traits['rows'][-count+i]or v['flags']!=1 or v['dispatch']!=0 or 'metadata'in v or v['method']!=initial+i or
           a.qname(v['name'])!='7:'+name+':5:'+namespace+':'+leaf or b!=a.bodies['rows'][-count+i]or b['value']['frame'][2]!=scope):raise ValueError('Featured appended private helper ABI differs')
    for name in replaced+added:
        t,b=presentation.named(a,owner,name);info=a.methods['rows'][b['value']['method']]['value']
        # NativeGuard's existing event=null optional parameter remains in the
        # unchanged callable table. New private helpers introduce no defaults.
        if((name in added and (info['optional']or info['param_names']))or sha(presentation.semantic(a,b).encode())!=frozen[name]):raise ValueError('Featured reviewed semantic/ABI differs: '+name)
        if any(op in(0x40,0x43,0x44,0x67)for _,_,op,_ in a.instructions(b['value']['code'])):raise ValueError('Featured nested/outer dependency')
    patches.append((traits['start'],traits['end'],attach._u30(traits['count']-count)+raw[traits['head']:traits['rows'][-count]['start']]))
    for pool,count0 in zip(a.pools,d['pool_counts']):
        if type(count0)is not int or not 0<=count0<=pool['count']:raise ValueError('Featured pool prefix differs')
        end=pool['head']if count0<=1 else pool['rows'][count0-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count0)+raw[pool['head']:end]))
    table=a.methods;patches.append((table['start'],table['end'],attach._u30(table['count']-count)+raw[table['head']:table['rows'][-count]['start']]))
    table=a.bodies;rows=table['rows'][:-count];out=attach._u30(table['count']-count)+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']])for r in rows);patches.append((table['start'],table['end'],out))
    limit=len(raw)
    for start,end,value in sorted(patches,reverse=True):
        if end>limit or start>end:raise ValueError('Featured rollback spans overlap')
        raw=raw[:start]+value+raw[end:];limit=start
    return replace_payload(final,prefix+raw)

def chain_adapter(prior,proof,final):
    required=('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified')
    if(not isinstance(prior,dict)or not isinstance(proof,dict)or proof.get('ok')is not True or proof.get('mode')!='grid'or
       any(proof.get(k)is not True for k in required)or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in{'replaced_owned_bodies':3,'appended_methods':2,'appended_fields':0,'changed_original_native_bodies':0}.items())or
       proof.get('source_sha256')!=pins()or proof.get('helper_source_sha256')!=sha(helpers().encode())or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or
       proof.get('runtime_qualified')is not False or proof.get('hitch_free_claimed')is not False or proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256')):raise ValueError('Featured continuation proof differs')
    if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Featured final bytes differ')
    base=reconstruct(final,proof.get('rollback'))
    if sha(base)!=proof.get('baseline_swf_sha256')or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256')or previous.verify_adapter(prior,base)is not True:raise ValueError('Featured complete preceding local-budget differs')
    return dict(base_resource_sha256=prior['base_resource_sha256'],patched_resource_sha256=sha(final),previous_stage_adapter=copy.deepcopy(prior),previous_stage_sha256=comm.contract_digest(prior),featured_contract=copy.deepcopy(proof),postproof_sha256=comm.contract_digest(proof))

def verify_adapter(adapter,final):
    if not isinstance(adapter,dict)or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('featured_contract'),final)!=adapter:raise ValueError('Featured complete adapter differs')
    return True

def historical(adapter,final):
    verify_adapter(adapter,final);return adapter['previous_stage_adapter'],reconstruct(final,adapter['featured_contract']['rollback'])

def chain_main(prior,proof,final):
    required=('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified')
    if(not isinstance(prior,dict)or not isinstance(proof,dict)or proof.get('ok')is not True or proof.get('mode')!='grid'or
       any(proof.get(k)is not True for k in required)or
       any(type(proof.get(k))is not int or proof[k]!=v for k,v in{'replaced_owned_bodies':3,'appended_methods':1,'appended_fields':0,'changed_original_native_bodies':0}.items())or
       proof.get('source_sha256')!=pins()or proof.get('main_identity_source_sha256')!=sha((ROOT/SOURCES[-1]).read_bytes())or
       proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or proof.get('runtime_qualified')is not False or proof.get('hitch_free_claimed')is not False or
       proof.get('baseline_swf_sha256')!=prior.get('final_swf_sha256')):raise ValueError('Featured Main continuation proof differs')
    if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Featured Main final bytes differ')
    base=reconstruct(final,proof.get('rollback'),MAIN)
    if sha(base)!=proof.get('baseline_swf_sha256')or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256')or previous.verify_contract(prior,base)is not True:raise ValueError('Featured Main complete preceding local-budget differs')
    return dict(previous_stage_contract=copy.deepcopy(prior),previous_stage_sha256=comm.contract_digest(prior),featured_main_contract=copy.deepcopy(proof),postproof_sha256=comm.contract_digest(proof),final_swf_sha256=sha(final))

def verify_main(contract,final):
    if not isinstance(contract,dict)or chain_main(contract.get('previous_stage_contract'),contract.get('featured_main_contract'),final)!=contract:raise ValueError('Featured Main complete contract differs')
    return True


def adapt(prior,base,original,ffdec,work):
    from cas_ui_build import replace_payload
    base=bytes(base);original=Path(original);ffdec=Path(ffdec);work=Path(work)
    if previous.verify_adapter(prior,base)is not True or 'budget_contract'not in prior:raise ValueError('Featured requires exact complete local-budget provider')
    if sha(original.read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Featured original native provider differs')
    start=pins();work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(base);source=work/'native-source'
    comm.run([ffdec,'-selectclass',GRID,'-export','script',source,original],work/'export.log')
    text=presentation.inject_grid((source/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig'));before=presentation.helpers()
    if text.count(before)!=1:raise ValueError('Featured complete compiler helper seam differs')
    owned=work/'RecyclingGridLayout.as';owned.write_text(text.replace(before,helpers(),1),encoding='utf-8');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,GRID,owned],work/'compile.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=presentation.ROOT
    comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',project/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridFeaturedPatch.java'],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridFeaturedPatch','grid',incoming,compiled,output,report],work/'transplant.log')
    if start!=pins():raise ValueError('Featured source changed during compilation')
    final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
    proof.update(source_sha256=start,helper_source_sha256=sha(helpers().encode()),previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base),final_swf_sha256=sha(final))
    return final,chain_adapter(prior,proof,final)

def adapt_main(prior,base,source,ffdec,work):
    from cas_ui_build import replace_payload
    if previous.verify_contract(prior,base)is not True:raise ValueError('Featured Main requires exact local-budget Main predecessor')
    start=pins();ffdec=Path(ffdec);work=Path(work);work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(base)
    owned=work/'CASCustomizerMain.as';owned.write_text(inject_main(Path(source).read_text(encoding='utf-8-sig')),encoding='utf-8');compiled=work/'compiled.swf'
    comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,MAIN,owned],work/'compile.log')
    classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=presentation.ROOT
    comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',project/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridFeaturedMainPatch.java'],work/'javac.log')
    output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridFeaturedMainPatch','grid',incoming,compiled,output,report],work/'transplant.log')
    if start!=pins():raise ValueError('Featured source changed during Main compilation')
    final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
    proof.update(source_sha256=start,main_identity_source_sha256=sha((ROOT/SOURCES[-1]).read_bytes()),previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base,MAIN),final_swf_sha256=sha(final))
    return final,chain_main(prior,proof,final)

def unwrap_providers(evidence,resources,dependencies=None):
    import dbpf_build,maru_companion
    keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
    if not isinstance(evidence,dict)or set(evidence)!=keys:raise ValueError('Both Featured provider continuations are required')
    out=dict(resources);providers={}
    for key in keys:
        a=evidence[key]
        if not isinstance(a,dict)or 'featured_contract'not in a:raise ValueError('Featured provider stage absent or downgraded')
        native=tuple(int(n,16)for n in key.split(':'));providers[key],out[native]=historical(a,resources.get(native,b''))
    return providers,out,dependencies

def unwrap_manifest(info,resources):
    import dbpf_build,maru_companion
    source=info.get('source_pins',{});providers=info.get('grid_provider_adapters');main=info.get('featured_main_native_bytecode_contract')
    current=any(n in source for n in SOURCES)or main is not None or any(isinstance(a,dict)and 'featured_contract'in a for a in(providers or {}).values())
    if not current:return info,resources
    if not isinstance(source,dict)or any(source.get(k)!=v for k,v in pins().items()):raise ValueError('Featured source pins absent/partial/stale')
    if not isinstance(main,dict)or main.get('previous_stage_contract')!=info.get('budget_main_native_bytecode_contract'):raise ValueError('Featured Main exact budget predecessor missing')
    key=maru_companion.CUSTOMIZER;final=resources.get(key,b'')
    if info.get('patched_resource_sha256')!=sha(final)or info.get('patched_resources',{}).get(dbpf_build.tgi(key))!=sha(final):raise ValueError('Advertised Featured Main identity differs')
    verify_main(main,final)
    for name in(dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
        native=tuple(int(n,16)for n in name.split(':'))
        if info.get('patched_resources',{}).get(name)!=sha(resources.get(native,b'')):raise ValueError('Advertised Featured provider identity differs')
    p,r,_=unwrap_providers(providers,resources);updated=copy.deepcopy(info);updated['grid_provider_adapters']=p
    updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
    for name,adapter in p.items():updated['patched_resources'][name]=adapter['patched_resource_sha256']
    r[key]=reconstruct(final,main['featured_main_contract']['rollback'],MAIN);updated['patched_resource_sha256']=sha(r[key]);updated['patched_resources'][dbpf_build.tgi(key)]=sha(r[key])
    return updated,r
