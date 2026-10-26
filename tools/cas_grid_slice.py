"""Guarantee one bounded transaction atom after fresh admission checks."""
from pathlib import Path
import hashlib,json,os,re
import cas_grid_scroll as previous
import cas_communication_index as comm
import cas_catalog_binding as binding
import cas_cell_attach as attach
ROOT=Path(__file__).resolve().parents[1]
SOURCES=('tools/cas_grid_slice.py','tools/CasGridSlicePatch.java','Source/CASUi/catalog_grid_slice_methods.as')
OWNED=('ApexTxnStep',)
GRID=previous.GRID
sha=previous.sha

def pins():return {name:sha((ROOT/name).read_bytes()) for name in SOURCES}
def helpers():
 source=previous.helpers();start,end=previous.pool.method_extent(source,'ApexTxnStep')
 return source[:start]+(ROOT/'Source/CASUi/catalog_grid_slice_methods.as').read_text(encoding='utf-8').strip()+source[end:]

def semantics():
 text=(ROOT/'tools/CasGridSlicePatch.java').read_text();rows=re.findall(r'Map.entry\("([^"]+)","([0-9a-f]{64})"\)',text)
 if len(rows)!=1 or {n for n,_ in rows}!={GRID+'/'+n for n in OWNED}:raise ValueError('Grid progress semantic pins differ.')
 return dict(rows)

def descriptor(base):
 _,raw=binding._abc_payload(base);a=previous.ABC(raw).parse();out={}
 for name in OWNED:
  row=previous.presentation.named(a,GRID,name)[1];out[name]=raw[row['start']:row['end']].hex()
 return {'pool_counts':[r['count'] for r in a.pools],'bodies':out}

def reconstruct(final,proof):
 from cas_ui_build import replace_payload
 prefix,raw=binding._abc_payload(final);a=previous.ABC(raw).parse();d=proof.get('rollback')
 if not isinstance(d,dict) or set(d)!={'pool_counts','bodies'} or not isinstance(d['bodies'],dict) or set(d['bodies'])!=set(OWNED):raise ValueError('Grid progress rollback absent.')
 if not isinstance(d['pool_counts'],list) or len(d['pool_counts'])!=7:raise ValueError('Grid progress constant inventory absent.')
 restored={};patches=[]
 for name,text in d['bodies'].items():
  if not isinstance(text,str) or not 0<len(text)<=40000 or re.fullmatch('[0-9a-f]+',text) is None:raise ValueError('Grid progress old body invalid or unbounded.')
  oldraw=bytes.fromhex(text);reader=previous.ABC(oldraw);old=reader.body();row=previous.presentation.named(a,GRID,name)[1]
  if reader.at!=len(oldraw) or old['method']!=row['value']['method'] or old['frame'][2]!=row['value']['frame'][2]:raise ValueError('Grid progress method/scope changed.')
  if sha(previous.presentation.semantic(a,row).encode())!=semantics()[GRID+'/'+name]:raise ValueError('Grid progress exact helper ABI/CFG differs.')
  restored[old['method']]=oldraw
 for pool,count in zip(a.pools,d['pool_counts']):
  if type(count) is not int or count<0 or count>pool['count']:raise ValueError('Grid progress pool prefix differs.')
  end=pool['head'] if count<=1 else pool['rows'][count-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count)+raw[pool['head']:end]))
 table=a.bodies;restored_table=attach._u30(table['count'])+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']]) for r in table['rows']);patches.append((table['start'],table['end'],restored_table))
 limit=len(raw)
 for start,end,value in sorted(patches,reverse=True):
  if end>limit:raise ValueError('Grid progress rollback overlaps.')
  raw=raw[:start]+value+raw[end:];limit=start
 return replace_payload(final,prefix+raw)

def chain_adapter(prior,proof,final):
 required=('whole_abc_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified')
 if(not isinstance(prior,dict) or not isinstance(proof,dict) or proof.get('mode')!='grid' or proof.get('ok') is not True or
    any(proof.get(k) is not True for k in required) or
    any(type(proof.get(k)) is not int or proof[k]!=v for k,v in {'replaced_owned_bodies':1,'appended_methods':0,'appended_fields':0,'changed_original_native_bodies':0}.items()) or
    proof.get('source_sha256')!=pins() or proof.get('helper_source_sha256')!=sha(helpers().encode()) or proof.get('runtime_qualified') is not False or proof.get('hitch_free_claimed') is not False or
    proof.get('previous_stage_sha256')!=comm.contract_digest(prior) or proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256')):raise ValueError('Grid progress continuation proof differs.')
 if sha(final)!=proof.get('final_swf_sha256') or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Grid progress final resource/ABC differs.')
 base=reconstruct(final,proof)
 if sha(base)!=proof['baseline_swf_sha256'] or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256') or previous.verify_adapter(prior,base) is not True:raise ValueError('Grid progress complete previous continuation differs.')
 return dict(base_resource_sha256=prior['base_resource_sha256'],patched_resource_sha256=sha(final),previous_stage_adapter=json.loads(json.dumps(prior)),previous_stage_sha256=comm.contract_digest(prior),slice_contract=json.loads(json.dumps(proof)),postproof_sha256=comm.contract_digest(proof))

def verify_adapter(adapter,final):
 if not isinstance(adapter,dict) or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('slice_contract'),final)!=adapter:raise ValueError('Grid progress adapter differs.')
 return True

def adapt(prior,base,original,ffdec,work):
 from cas_ui_build import replace_payload
 base=bytes(base);original=Path(original);ffdec=Path(ffdec);work=Path(work)
 if previous.verify_adapter(prior,base) is not True or 'scroll_contract' not in prior:raise ValueError('Grid progress stage requires complete native grid presentation.')
 if sha(original.read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Grid progress original native provider differs.')
 start=pins();work.mkdir(parents=True,exist_ok=True);baseline=work/'baseline.swf';baseline.write_bytes(base);source=work/'native-source'
 comm.run([ffdec,'-selectclass',GRID,'-export','script',source,original],work/'export.log')
 owned=work/'RecyclingGridLayout.as';text=previous.presentation.inject_grid((source/'scripts/olympus/layout/RecyclingGridLayout.as').read_text(encoding='utf-8-sig'));before=previous.presentation.helpers()
 if text.count(before)!=1:raise ValueError('Exact prior grid compiler source boundary differs.')
 owned.write_text(text.replace(before,helpers(),1),encoding='utf-8');compiled=work/'compiled.swf'
 comm.run([ffdec,'-importAssets','yes,local','-replace',baseline,compiled,GRID,owned],work/'ffdec.log')
 classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar')
 comm.run(['javac','-cp',jar,'-d',classes,previous.previous.ROOT/'tools/CasStructuralRolesPatch.java',previous.previous.ROOT/'tools/CasCommunicationIndexPatch.java',previous.previous.ROOT/'tools/CasGridPoolPatch.java',ROOT/'tools/CasGridSlicePatch.java'],work/'javac.log')
 output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasGridSlicePatch','grid',baseline,compiled,output,report],work/'transplant.log')
 abc=output.read_bytes();proof=json.loads(report.read_text());final=replace_payload(base,binding._abc_payload(base)[0]+abc)
 if start!=pins():raise ValueError('Grid progress sources changed during compilation.')
 proof.update(source_sha256=start,helper_source_sha256=sha(helpers().encode()),previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base),final_swf_sha256=sha(final))
 return final,chain_adapter(prior,proof,final)

def historical(adapter,final):
 verify_adapter(adapter,final)
 return adapter['previous_stage_adapter'],reconstruct(final,adapter['slice_contract'])

def unwrap_providers(evidence,resources,dependencies=None):
 import dbpf_build,maru_companion
 keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
 if not isinstance(evidence,dict) or set(evidence)!=keys:raise ValueError('Both grid-progress native providers required.')
 out=dict(resources);providers={}
 for key in keys:
  a=evidence[key]
  if not isinstance(a,dict) or 'slice_contract' not in a:raise ValueError('Both native providers must use the same exact grid-progress stage.')
  tgi=tuple(int(n,16) for n in key.split(':'));providers[key],out[tgi]=historical(a,resources.get(tgi,b''))
 return providers,out,dependencies

def unwrap_manifest(info,resources):
 source=info.get('source_pins',{});providers=info.get('grid_provider_adapters')
 current=any(n in source for n in SOURCES) or any(isinstance(a,dict) and 'slice_contract' in a for a in (providers or {}).values())
 if not current:return info,resources
 if not isinstance(source,dict) or any(source.get(k)!=v for k,v in pins().items()):raise ValueError('Grid-progress source pins are missing, partial or stale.')
 import dbpf_build,maru_companion
 for name in (dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
  native_key=tuple(int(n,16)for n in name.split(':'))
  if info.get('patched_resources',{}).get(name)!=sha(resources.get(native_key,b'')):raise ValueError('Advertised final grid identity differs before slice rollback.')
 p,r,_=unwrap_providers(providers,resources);updated=json.loads(json.dumps(info));updated['grid_provider_adapters']=p
 updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
 for key,adapter in p.items():updated['patched_resources'][key]=adapter['patched_resource_sha256']
 return updated,r
