"""Provider-local relative soft slices and explicit one-off clock evidence.

Legacy/unknown callers retain the exact preceding path. The elapsed-time clone
preserves every original owner/lease/callback fence and handles signed rollover.
"""
from pathlib import Path
import sys,json,re,hashlib,os,copy
ROOT=Path(__file__).resolve().parents[1]
import cas_grid_presentation as presentation,cas_catalog_binding as binding,cas_cell_attach as attach,cas_grid_slice as previous,cas_grid_scroll as main_previous,cas_grid_pool as pool,cas_communication_index as comm
GRID=presentation.GRID;MAIN='widgets.CAS.Customizer.CASCustomizerMain'
REPLACED=('ApexGridStep',);ADDED=('ApexTxnBudgetStep',);MAIN_REPLACED=('ApexCatalogGridRequest','ApexCatalogGridStatus')
SOURCES=('tools/cas_grid_budget.py','tools/CasGridBudgetPatch.java','tools/CasGridBudgetMainPatch.java','Source/CASUi/catalog_grid_budget_step_methods.as','Source/CASUi/catalog_grid_budget_loop_methods.as','Source/CASUi/catalog_grid_budget_main_request.as','Source/CASUi/catalog_grid_budget_main_status.as')
sha=presentation.sha
def pins():return {n:sha((ROOT/n).read_bytes()) for n in SOURCES}
def helpers():
 source=previous.helpers();a,b=pool.method_extent(source,'ApexGridStep')
 return source[:a]+(ROOT/SOURCES[3]).read_text().strip()+source[b:]+'\n'+(ROOT/SOURCES[4]).read_text()
def inject_main(source):
 source=main_previous.inject_main(source)
 for name,file in zip(MAIN_REPLACED,SOURCES[-2:]):
  a,b=pool.method_extent(source,name);source=source[:a]+(ROOT/file).read_text().strip()+source[b:]
 return source
class ABC(presentation.ABC):
 def namespace(self,index):
  return re.sub(r'(?<=5:)CASCustomizerMain\.as\$[0-9]+','CASCustomizerMain.as$SELF',super().namespace(index))

def pinset(owner):
 file='tools/CasGridBudgetPatch.java' if owner==GRID else 'tools/CasGridBudgetMainPatch.java'
 rows=re.findall(r'Map.entry\("([^"\n]+)","([0-9a-f]{64})"\)',(ROOT/file).read_text())
 pins={name.rsplit('/',1)[-1]:value for name,value in rows}
 expected=set(REPLACED+ADDED) if owner==GRID else set(MAIN_REPLACED)
 if len(rows)!=len(expected) or set(pins)!=expected:raise ValueError('Budget semantic pin inventory differs')
 return pins

def build_descriptor(base,owner,replaced):
 prefix,raw=binding._abc_payload(base);a=ABC(raw).parse()
 return dict(pool_counts=[r['count'] for r in a.pools],bodies={name:raw[row['start']:row['end']].hex() for name in replaced for row in [presentation.named(a,owner,name)[1]]})

def reconstruct(final,descriptor,owner,replaced,added):
 from cas_ui_build import replace_payload
 prefix,raw=binding._abc_payload(final);a=ABC(raw).parse()
 if not isinstance(descriptor,dict) or set(descriptor)!={'pool_counts','bodies'} or set(descriptor['bodies'])!=set(replaced):raise ValueError('Exact old-body rollback inventory missing')
 pools=descriptor['pool_counts']
 if not isinstance(pools,list) or len(pools)!=7:raise ValueError('Exact constant prefix missing')
 pins=pinset(owner);restored={};patches=[];old={}
 for name,text in descriptor['bodies'].items():
  if not isinstance(text,str) or not 0<len(text)<=200000 or re.fullmatch('[0-9a-f]+',text)is None:raise ValueError('Old method body malformed or unbounded')
  payload=bytes.fromhex(text);reader=ABC(payload);b=reader.body();row=presentation.named(a,owner,name)[1]
  if reader.at!=len(payload) or b['method']!=row['value']['method'] or b['frame'][2]!=row['value']['frame'][2]:raise ValueError('Method/scope rollback target changed')
  restored[b['method']]=payload;old[name]=b
 namespace,leaf=owner.rsplit('.',1);instance=next(r for r in a.instances if a.qname(r['name'])=='7:'+leaf+':22:'+namespace);traits=instance['traits'];total=len(added)
 if total:
  initial=a.methods['count']-total;scope=presentation.named(a,owner,'ApexGridBind')[1]['value']['frame'][2]
  for i,name in enumerate(added):
   t,b=presentation.named(a,owner,name);v=t['value']
   if(t!=traits['rows'][-total+i] or v['flags']!=1 or v['dispatch']!=0 or 'metadata' in v or v['method']!=initial+i or
      a.qname(v['name'])!='7:'+name+':5:olympus.layout:RecyclingGridLayout' or b!=a.bodies['rows'][-total+i] or
      b['value']['frame'][2]!=scope+(1 if name=='ApexTxnBudgetStep' else 0)):raise ValueError('New helper is not exact appended native-private ABI')
  patches.append((traits['start'],traits['end'],attach._u30(traits['count']-total)+raw[traits['head']:traits['rows'][-total]['start']]))
 for name in (*replaced,*added):
  t,b=presentation.named(a,owner,name);info=a.methods['rows'][b['value']['method']]['value']
  # Replaced NativeGuard retains its original optional event=null MethodInfo;
  # the full rollback comparison pins that entire callable table unchanged.
  if (name in added and (info['optional'] or info['param_names'])) or sha(presentation.semantic(a,b).encode())!=pins[name]:raise ValueError('Reviewed helper ABI/CFG differs: '+name)
  if any(op in (0x40,0x43,0x44,0x67) for _,_,op,_ in a.instructions(b['value']['code'])):raise ValueError('Foreign nested/outer dependency')
 for pool,count in zip(a.pools,pools):
  if type(count)is not int or not 0<=count<=pool['count']:raise ValueError('Constant prefix invalid')
  end=pool['head'] if count<=1 else pool['rows'][count-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count)+raw[pool['head']:end]))
 if total:
  table=a.methods;patches.append((table['start'],table['end'],attach._u30(table['count']-total)+raw[table['head']:table['rows'][-total]['start']]))
 table=a.bodies;rows=table['rows'][:-total] if total else table['rows'];body=attach._u30(table['count']-total)+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']]) for r in rows);patches.append((table['start'],table['end'],body))
 limit=len(raw)
 for start,end,value in sorted(patches,reverse=True):
  if end>limit or start>end:raise ValueError('Rollback spans overlap')
  raw=raw[:start]+value+raw[end:];limit=start
 return replace_payload(final,prefix+raw)

def chain_adapter(prior,proof,final):
 required=('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified')
 if(not isinstance(prior,dict) or not isinstance(proof,dict) or proof.get('ok')is not True or proof.get('mode')!='grid' or
    any(proof.get(n)is not True for n in required) or
    any(type(proof.get(k))is not int or proof[k]!=v for k,v in {'replaced_owned_bodies':1,'appended_methods':1,'appended_fields':0,'changed_original_native_bodies':0}.items()) or
    proof.get('source_sha256')!=pins() or proof.get('helper_source_sha256')!=sha(helpers().encode()) or
    proof.get('previous_stage_sha256')!=comm.contract_digest(prior) or proof.get('runtime_qualified')is not False or proof.get('hitch_free_claimed')is not False or
    proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256')):raise ValueError('Provider-budget native continuation proof differs')
 if sha(final)!=proof.get('final_swf_sha256') or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Provider-budget final bytes differ')
 base=reconstruct(final,proof.get('rollback'),GRID,REPLACED,ADDED)
 if sha(base)!=proof.get('baseline_swf_sha256') or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256') or previous.verify_adapter(prior,base)is not True:raise ValueError('Provider-budget complete preceding native chain differs')
 return dict(base_resource_sha256=prior['base_resource_sha256'],patched_resource_sha256=sha(final),previous_stage_adapter=copy.deepcopy(prior),previous_stage_sha256=comm.contract_digest(prior),budget_contract=copy.deepcopy(proof),postproof_sha256=comm.contract_digest(proof))
def verify_adapter(adapter,final):
 if not isinstance(adapter,dict) or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('budget_contract'),final)!=adapter:raise ValueError('Provider-budget native adapter differs')
 return True
def chain_contract(prior,proof,final):
 import cas_grid_scroll as preview
 required=('whole_abc_rollback_verified','all_other_bodies_retained','native_timer_QNames_verified')
 if(not isinstance(prior,dict) or not isinstance(proof,dict) or proof.get('ok')is not True or
    any(proof.get(n)is not True for n in required) or
    any(type(proof.get(k))is not int or proof[k]!=v for k,v in {'new_traits':0,'new_fields':0,'native_original_changes':0,'owned_main_replacements':2}.items()) or
    proof.get('source_sha256')!=pins() or proof.get('main_source_sha256')!=sha('\n'.join((ROOT/n).read_text()for n in SOURCES[-2:]).encode()) or
    proof.get('previous_stage_sha256')!=comm.contract_digest(prior) or proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False or
    proof.get('baseline_swf_sha256')!=prior.get('final_swf_sha256')):raise ValueError('Main provider-budget producer contract differs')
 if sha(final)!=proof.get('final_swf_sha256') or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Main provider-budget final identity differs')
 base=reconstruct(final,proof.get('rollback'),MAIN,MAIN_REPLACED,())
 if sha(base)!=proof.get('baseline_swf_sha256') or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256') or preview.verify_contract(prior,base)is not True:raise ValueError('Main provider-budget preceding full history differs')
 return dict(previous_stage_contract=copy.deepcopy(prior),previous_stage_sha256=comm.contract_digest(prior),budget_main_contract=copy.deepcopy(proof),postproof_sha256=comm.contract_digest(proof),final_swf_sha256=sha(final))
def verify_contract(contract,final):
 if not isinstance(contract,dict) or chain_contract(contract.get('previous_stage_contract'),contract.get('budget_main_contract'),final)!=contract:raise ValueError('Main provider-budget complete contract differs')
 return True
def adapt(prior,base,original,ffdec,work):
 from cas_ui_build import replace_payload
 base=bytes(base);original=Path(original);ffdec=Path(ffdec);work=Path(work)
 if previous.verify_adapter(prior,base)is not True or 'slice_contract'not in prior:raise ValueError('Provider-budget stage requires current complete swatch native chain')
 if sha(original.read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Provider-budget original native provider differs')
 start=pins();work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(base);source=work/'native-source'
 comm.run([ffdec,'-selectclass',GRID,'-export','script',source,original],work/'export.log')
 text=presentation.inject_grid((source/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig'));before=presentation.helpers()
 if text.count(before)!=1:raise ValueError('Exact native helper source seam differs')
 owned=work/'RecyclingGridLayout.as';owned.write_text(text.replace(before,helpers(),1),encoding='utf-8');compiled=work/'compiled.swf';comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,GRID,owned],work/'ffdec.log')
 classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=previous.previous.previous.ROOT
 comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',project/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridBudgetPatch.java'],work/'javac.log')
 output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridBudgetPatch','grid',incoming,compiled,output,report],work/'transplant.log')
 final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
 if start!=pins():raise ValueError('Provider-budget sources changed during compile')
 proof.update(source_sha256=start,helper_source_sha256=sha(helpers().encode()),previous_stage_sha256=comm.contract_digest(prior),rollback=build_descriptor(base,GRID,REPLACED),final_swf_sha256=sha(final))
 return final,chain_adapter(prior,proof,final)
def adapt_main(prior,base,source,ffdec,work):
 from cas_ui_build import replace_payload
 import cas_grid_scroll as preview
 if preview.verify_contract(prior,base)is not True:raise ValueError('Provider-budget Main requires full native preview history')
 start=pins();ffdec=Path(ffdec);work=Path(work);work.mkdir(parents=True,exist_ok=True);incoming=work/'baseline.swf';incoming.write_bytes(base);owned=work/'CASCustomizerMain.as';owned.write_text(inject_main(Path(source).read_text(encoding='utf-8-sig')),encoding='utf-8');compiled=work/'compiled.swf'
 comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,MAIN,owned],work/'ffdec.log')
 classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=previous.previous.previous.ROOT
 comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',ROOT/'tools/CasGridBudgetMainPatch.java'],work/'javac.log');output=work/'retained.abc';report=work/'proof.json'
 comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridBudgetMainPatch',incoming,compiled,output,report],work/'transplant.log');final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
 if start!=pins():raise ValueError('Provider-budget Main sources changed during compile')
 proof.update(source_sha256=start,main_source_sha256=sha('\n'.join((ROOT/n).read_text()for n in SOURCES[-2:]).encode()),previous_stage_sha256=comm.contract_digest(prior),rollback=build_descriptor(base,MAIN,MAIN_REPLACED),baseline_swf_sha256=sha(base),baseline_abc_sha256=sha(binding._abc_payload(base)[1]),final_swf_sha256=sha(final),performance_gain_claimed=False)
 return final,chain_contract(prior,proof,final)
def historical(adapter,final):
 verify_adapter(adapter,final);return adapter['previous_stage_adapter'],reconstruct(final,adapter['budget_contract']['rollback'],GRID,REPLACED,ADDED)
def unwrap_providers(evidence,resources,dependencies=None):
 import dbpf_build,maru_companion
 keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
 if not isinstance(evidence,dict) or set(evidence)!=keys:raise ValueError('Both provider-budget native providers required')
 out=dict(resources);providers={}
 for key in keys:
  a=evidence[key]
  if not isinstance(a,dict) or 'budget_contract'not in a:raise ValueError('Both providers must use complete provider-budget stage')
  tgi=tuple(int(n,16)for n in key.split(':'));providers[key],out[tgi]=historical(a,resources.get(tgi,b''))
 return providers,out,dependencies
def unwrap_manifest(info,resources):
 import dbpf_build,maru_companion
 source=info.get('source_pins',{});providers=info.get('grid_provider_adapters');main=info.get('budget_main_native_bytecode_contract')
 current=any(n in source for n in SOURCES) or main is not None or any(isinstance(a,dict)and'budget_contract'in a for a in(providers or {}).values())
 if not current:return info,resources
 if not isinstance(source,dict) or any(source.get(k)!=v for k,v in pins().items()):raise ValueError('Provider-budget source pins missing/partial/stale')
 if not isinstance(main,dict) or main.get('previous_stage_contract')!=info.get('scroll_main_native_bytecode_contract'):raise ValueError('Provider-budget Main prior proof absent/downgraded')
 key=maru_companion.CUSTOMIZER;final=resources.get(key,b'')
 if info.get('patched_resource_sha256')!=sha(final) or info.get('patched_resources',{}).get(dbpf_build.tgi(key))!=sha(final):raise ValueError('Advertised final Main identity differs before scroll rollback')
 verify_contract(main,final)
 for name in (dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
  native_key=tuple(int(n,16)for n in name.split(':'))
  if info.get('patched_resources',{}).get(name)!=sha(resources.get(native_key,b'')):raise ValueError('Advertised final grid identity differs before scroll rollback')
 p,r,_=unwrap_providers(providers,resources);updated=copy.deepcopy(info);updated['grid_provider_adapters']=p;updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
 for name,adapter in p.items():updated['patched_resources'][name]=adapter['patched_resource_sha256']
 r[key]=reconstruct(final,main['budget_main_contract']['rollback'],MAIN,MAIN_REPLACED,());updated['patched_resource_sha256']=sha(r[key]);updated['patched_resources'][dbpf_build.tgi(key)]=sha(r[key])
 return updated,r
