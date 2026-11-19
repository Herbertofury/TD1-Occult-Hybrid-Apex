"""Verify synchronous product row ABI before native identity extraction."""
from pathlib import Path
import hashlib,json,os,re
import cas_grid_presentation as previous
import cas_communication_index as comm
import cas_catalog_binding as binding
import cas_cell_attach as attach
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('tools/cas_grid_product_rows.py','tools/CasGridProductRowsPatch.java','Source/CASUi/catalog_product_grid_row_guard.as')
OWNED=('ApexGridBind','ApexGridReady')
GRID=previous.GRID
sha=previous.sha

def pins():return {name:sha((ROOT/name).read_bytes()) for name in SOURCES}
def helpers():
 source=previous.helpers();guard=(ROOT/'Source/CASUi/catalog_product_grid_row_guard.as').read_text(encoding='utf-8')
 for name,needle in [('ApexGridBind','var item:Object=GetDataAtIndex(sortedIndex);'),('ApexGridReady','var item:Object=GetDataAtIndex(j.boundSorted);'),('ApexGridReady','item=GetDataAtIndex(j.boundSorted);')]:
  start,end=previous.pool.method_extent(source,name);body=source[start:end]
  if body.count(needle)!=1:raise ValueError('Product row read boundary differs: '+name)
  body=body.replace(needle,needle+'\n'+guard,1);source=source[:start]+body+source[end:]
 return source

def semantics():
 text=(ROOT/'tools/CasGridProductRowsPatch.java').read_text();rows=re.findall(r'Map.entry\("([^"]+)","([0-9a-f]{64})"\)',text)
 if len(rows)!=2 or {n for n,_ in rows}!={GRID+'/'+n for n in OWNED}:raise ValueError('Product row semantic pins differ.')
 return dict(rows)

def descriptor(base):
 _,raw=binding._abc_payload(base);a=previous.ABC(raw).parse();out={}
 for name in OWNED:
  row=previous.named(a,GRID,name)[1];out[name]=raw[row['start']:row['end']].hex()
 return {'pool_counts':[r['count'] for r in a.pools],'bodies':out}

def reconstruct(final,proof):
 from cas_ui_build import replace_payload
 prefix,raw=binding._abc_payload(final);a=previous.ABC(raw).parse();d=proof.get('rollback')
 if not isinstance(d,dict) or set(d)!={'pool_counts','bodies'} or not isinstance(d['bodies'],dict) or set(d['bodies'])!=set(OWNED):raise ValueError('Product row rollback absent.')
 if not isinstance(d['pool_counts'],list) or len(d['pool_counts'])!=7:raise ValueError('Product row constant inventory absent.')
 restored={};patches=[]
 for name,text in d['bodies'].items():
  if not isinstance(text,str) or not 0<len(text)<=40000 or re.fullmatch('[0-9a-f]+',text) is None:raise ValueError('Product row old body invalid or unbounded.')
  oldraw=bytes.fromhex(text);reader=previous.ABC(oldraw);old=reader.body();row=previous.named(a,GRID,name)[1]
  if reader.at!=len(oldraw) or old['method']!=row['value']['method'] or old['frame'][2]!=row['value']['frame'][2]:raise ValueError('Product row method/scope changed.')
  if sha(previous.semantic(a,row).encode())!=semantics()[GRID+'/'+name]:raise ValueError('Product row exact helper ABI/CFG differs.')
  restored[old['method']]=oldraw
 for pool,count in zip(a.pools,d['pool_counts']):
  if type(count) is not int or count<0 or count>pool['count']:raise ValueError('Product row pool prefix differs.')
  end=pool['head'] if count<=1 else pool['rows'][count-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count)+raw[pool['head']:end]))
 table=a.bodies;restored_table=attach._u30(table['count'])+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']]) for r in table['rows']);patches.append((table['start'],table['end'],restored_table))
 limit=len(raw)
 for start,end,value in sorted(patches,reverse=True):
  if end>limit:raise ValueError('Product row rollback overlaps.')
  raw=raw[:start]+value+raw[end:];limit=start
 return replace_payload(final,prefix+raw)

def chain_adapter(prior,proof,final):
 required=('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified')
 if(not isinstance(prior,dict) or not isinstance(proof,dict) or proof.get('mode')!='grid' or proof.get('ok') is not True or
    any(proof.get(k) is not True for k in required) or
    any(type(proof.get(k)) is not int or proof[k]!=v for k,v in {'replaced_owned_bodies':2,'appended_methods':0,'appended_fields':0,'changed_original_native_bodies':0}.items()) or
    proof.get('source_sha256')!=pins() or proof.get('helper_source_sha256')!=sha(helpers().encode()) or proof.get('runtime_qualified') is not False or proof.get('hitch_free_claimed') is not False or
    proof.get('previous_stage_sha256')!=comm.contract_digest(prior) or proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256')):raise ValueError('Product row continuation proof differs.')
 if sha(final)!=proof.get('final_swf_sha256') or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Product row final resource/ABC differs.')
 base=reconstruct(final,proof)
 if sha(base)!=proof['baseline_swf_sha256'] or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256') or previous.verify_adapter(prior,base) is not True:raise ValueError('Product row complete previous continuation differs.')
 return dict(base_resource_sha256=prior['base_resource_sha256'],patched_resource_sha256=sha(final),previous_stage_adapter=json.loads(json.dumps(prior)),previous_stage_sha256=comm.contract_digest(prior),product_rows_contract=json.loads(json.dumps(proof)),postproof_sha256=comm.contract_digest(proof))

def verify_adapter(adapter,final):
 if not isinstance(adapter,dict) or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('product_rows_contract'),final)!=adapter:raise ValueError('Product row adapter differs.')
 return True

def adapt(prior,base,original,ffdec,work):
 from cas_ui_build import replace_payload
 base=bytes(base);original=Path(original);ffdec=Path(ffdec);work=Path(work)
 if previous.verify_adapter(prior,base) is not True or prior.get('presentation_contract',{}).get('mode')!='grid':raise ValueError('Product row stage requires complete native grid presentation.')
 if sha(original.read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Product row original native provider differs.')
 start=pins();work.mkdir(parents=True,exist_ok=True);baseline=work/'baseline.swf';baseline.write_bytes(base);source=work/'native-source'
 comm.run([ffdec,'-selectclass',GRID,'-export','script',source,original],work/'export.log')
 owned=work/'RecyclingGridLayout.as';text=previous.inject_grid((source/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig'));before=previous.helpers()
 if text.count(before)!=1:raise ValueError('Exact prior grid compiler source boundary differs.')
 owned.write_text(text.replace(before,helpers(),1),encoding='utf-8');compiled=work/'compiled.swf'
 comm.run([ffdec,'-importAssets','yes,local','-replace',baseline,compiled,GRID,owned],work/'ffdec.log')
 classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
 comm.run(['javac','-cp',jar,'-d',classes,previous.ROOT/'tools/CasStructuralRolesPatch.java',previous.ROOT/'tools/CasCommunicationIndexPatch.java',previous.ROOT/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridProductRowsPatch.java'],work/'javac.log')
 output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridProductRowsPatch','grid',baseline,compiled,output,report],work/'transplant.log')
 abc=output.read_bytes();proof=json.loads(report.read_text());final=replace_payload(base,binding._abc_payload(base)[0]+abc)
 if start!=pins():raise ValueError('Product row sources changed during compilation.')
 proof.update(source_sha256=start,helper_source_sha256=sha(helpers().encode()),previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base),final_swf_sha256=sha(final))
 return final,chain_adapter(prior,proof,final)

def historical(adapter,final):
 verify_adapter(adapter,final)
 return adapter['previous_stage_adapter'],reconstruct(final,adapter['product_rows_contract'])

def unwrap_providers(evidence,resources,dependencies=None):
 import dbpf_build,maru_companion
 keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
 if not isinstance(evidence,dict) or set(evidence)!=keys:raise ValueError('Both product-row native providers required.')
 out=dict(resources);providers={}
 for key in keys:
  a=evidence[key]
  if not isinstance(a,dict) or 'product_rows_contract' not in a:raise ValueError('Both native providers must use the same exact product-row stage.')
  tgi=tuple(int(n,16) for n in key.split(':'));providers[key],out[tgi]=historical(a,resources.get(tgi,b''))
 return providers,out,dependencies

def unwrap_manifest(info,resources):
 source=info.get('source_pins',{});providers=info.get('grid_provider_adapters')
 current=any(n in source for n in SOURCES) or any(isinstance(a,dict) and 'product_rows_contract' in a for a in (providers or {}).values())
 if not current:return info,resources
 if not isinstance(source,dict) or any(source.get(k)!=v for k,v in pins().items()):raise ValueError('Product-row source pins are missing, partial or stale.')
 import dbpf_build,maru_companion
 p,r,_=unwrap_providers(providers,resources);updated=json.loads(json.dumps(info));updated['grid_provider_adapters']=p
 updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
 for key,adapter in p.items():updated['patched_resources'][key]=adapter['patched_resource_sha256']
 return updated,r
