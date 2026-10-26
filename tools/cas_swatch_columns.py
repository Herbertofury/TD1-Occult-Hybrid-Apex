"""Honor explicit swatch columns during the donor's native width reflow.

Terminal continuation after Publication and staging Attach. The DCC raw-code graft preserves every
original native instruction/edge and only selects its already-calculated count.
"""
from pathlib import Path
import copy,json,re,os
import cas_grid_featured as previous
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_grid_presentation as presentation
import cas_communication_index as comm
import cas_swatch_geometry as swatch
import cas_swatch_provider as swatch_provider
ROOT=Path(__file__).resolve().parents[1]
TYPE='widgets.CAS.controls.ColorSwatchPanel';METHOD='ApexSwatchGeometry';SELECTOR='ApexSwatchColumns'
NATIVE='DCCReflowSkinSwatches';NATIVE_PIN='31c3a74c47a66e24be6c579c62d81d6c4507c6926d904bad0020cce1e930b1b7'
SOURCES=('tools/cas_swatch_columns.py','tools/CasSwatchColumnsPatch.java','Source/CASUi/swatch_columns_methods.as')
sha=previous.sha
class ABC(previous.scroll.ABC):
 def namespace(self,index):
  return re.sub(r'(?<=5:)ColorSwatchPanel\.as\$[0-9]+','ColorSwatchPanel.as$SELF',super().namespace(index))
def pins():return {n:sha((ROOT/n).read_bytes())for n in SOURCES}

def predecessor(prior,main=False):
 """Explicit current terminal authority; historical Featured is test evidence only."""
 if not isinstance(prior,dict):raise ValueError('Swatch columns predecessor missing')
 if main and 'publication_trace_contract' in prior:
  import cas_grid_publication
  return 'publication',cas_grid_publication.verify_main
 if not main and 'staging_attach_contract' in prior:
  if prior.get('previous_stage_kind')!='publication':raise ValueError('Swatch columns refuse nonproduction Attach predecessor')
  import cas_grid_staging_attach
  return 'staging-attach',cas_grid_staging_attach.verify_adapter
 if ('featured_main_contract' if main else 'featured_contract') in prior:
  return 'featured-fixture',previous.verify_main if main else previous.verify_adapter
 raise ValueError('Swatch columns unknown/partial terminal predecessor')
def semantics(a):
 rows=re.findall(r'Map.entry\("(main|provider)/[^"\n]+/(\w+)","([0-9a-f]{64})"\)',(ROOT/SOURCES[1]).read_text())
 if len(rows)!=4 or {(mode,name)for mode,name,_ in rows}!={(mode,name)for mode in('main','provider')for name in(METHOD,SELECTOR)}:raise ValueError('Swatch column semantic pin inventory differs')
 owner=next(i for i in a.instances if a.qname(i['name'])=='7:ColorSwatchPanel:22:widgets.CAS.controls')
 mode='provider'if any(a.string(a.pool(6,t['value']['name'])['name'])==NATIVE for t in owner['traits']['rows'])else'main'
 return {name:value for kind,name,value in rows if kind==mode}
def descriptor(base):return previous.scroll.build_descriptor(base,TYPE,(METHOD,))
def expected_code(a,old):
 if(sha(old['code'])!=NATIVE_PIN or old['frame']!=(10,9,12,13)or old['exceptions']or old['traits']['count']):raise ValueError('Exact donor DCC reflow native body/metadata differs')
 code=old['code'];rows=a.instructions(code)
 hits=[n for n,(_,_,op,args)in enumerate(rows)if op==0x61 and a.string(a.pool(6,args[0])['name'])=='mMaxCols']
 if len(hits)!=1:raise ValueError('DCC column store inventory differs')
 n=hits[0]
 if n<3 or rows[n-2][2]!=0xd0 or rows[n-1][2]!=0x62 or rows[n-3][2]!=0x63 or rows[n-1][3]!=rows[n-3][3]:raise ValueError('DCC calculated-count local store seam differs')
 register=rows[n-3][3][0];start=rows[n-3][1]
 if register!=7 or rows[n-4][2]!=0x73 or rows[n-5][2]!=0x46 or rows[n-5][3][1]!=2 or a.string(a.pool(6,rows[n-5][3][0])['name'])!='max':raise ValueError('DCC legacy floor/max calculation differs')
 trait,_=presentation.named(a,TYPE,SELECTOR);selector=trait['value']['name']
 if a.qname(selector)!='7:'+SELECTOR+':5:widgets.CAS.controls:ColorSwatchPanel':raise ValueError('DCC selector private QName differs')
 insertion=b'\xd0\x62'+attach._u30(register)+b'\x46'+attach._u30(selector)+b'\x01\x63'+attach._u30(register)
 size=len(insertion);mapping={at:at+(size if at>=start else 0)for at,_,_,_ in rows};mapping[len(code)]=len(code)+size;out=bytearray()
 def s24(value):
  if not -8388608<=value<=8388607:raise ValueError('DCC branch range overflow')
  return (value&0xffffff).to_bytes(3,'little')
 for at,end,op,args in rows:
  if at==start:out+=insertion
  raw=code[at:end]
  if 0x0c<=op<=0x1a:
   target=end+args[0]
   if target not in mapping or target==start:raise ValueError('DCC branch enters selector seam')
   raw=bytes([op])+s24(mapping[target]-mapping[end])
  elif op==0x1b:raise ValueError('Unreviewed donor DCC switch')
  out+=raw
 return bytes(out)
def replace_code(payload,newcode):
 reader=ABC(payload);reader.u30()
 for _ in range(4):reader.u30()
 length_at=reader.at;oldlength=reader.u30();start=reader.at
 return payload[:length_at]+attach._u30(len(newcode))+newcode+payload[start+oldlength:]
def graft_native(base):
 from cas_ui_build import replace_payload
 prefix,raw=binding._abc_payload(base);a=ABC(raw).parse();row=presentation.named(a,TYPE,NATIVE)[1];old=raw[row['start']:row['end']]
 made=replace_code(old,expected_code(a,row['value']));return replace_payload(base,prefix+raw[:row['start']]+made+raw[row['end']:]),old.hex()
def restore_native(final,native):
 from cas_ui_build import replace_payload
 if native is None:return final
 if not isinstance(native,str)or not 0<len(native)<=20000 or re.fullmatch('[0-9a-f]+',native)is None:raise ValueError('DCC native raw rollback absent')
 oldraw=bytes.fromhex(native);reader=ABC(oldraw);old=reader.body()
 if reader.at!=len(oldraw):raise ValueError('DCC native rollback trailing bytes')
 prefix,raw=binding._abc_payload(final);a=ABC(raw).parse();row=presentation.named(a,TYPE,NATIVE)[1];current=row['value']
 if(current['method']!=old['method']or current['frame']!=old['frame']or current['exceptions']or current['traits']['count']or current['code']!=expected_code(a,old)):raise ValueError('DCC native CFG/counted selector differs')
 return replace_payload(final,prefix+raw[:row['start']]+oldraw+raw[row['end']:])
def reconstruct(final,proof):
 from cas_ui_build import replace_payload
 if proof.get('declares')is False:
  if proof.get('rollback')!={'unchanged_resource':True}:raise ValueError('Nondeclaring swatch provider rollback differs')
  return final
 restored=restore_native(final,proof.get('native_body'));prefix,raw=binding._abc_payload(restored);a=ABC(raw).parse();d=proof.get('rollback')
 if not isinstance(d,dict)or set(d)!={'pool_counts','bodies'}or set(d['bodies'])!={METHOD}:raise ValueError('Swatch exact old helper rollback missing')
 if not isinstance(d['pool_counts'],list)or len(d['pool_counts'])!=7:raise ValueError('Swatch constant prefix missing')
 oldtext=d['bodies'][METHOD]
 if not isinstance(oldtext,str)or not 0<len(oldtext)<=200000 or re.fullmatch('[0-9a-f]+',oldtext)is None:raise ValueError('Swatch old helper malformed')
 oldraw=bytes.fromhex(oldtext);reader=ABC(oldraw);old=reader.body();row=presentation.named(a,TYPE,METHOD)[1]
 if reader.at!=len(oldraw)or old['method']!=row['value']['method']or old['frame'][2]!=row['value']['frame'][2]:raise ValueError('Swatch helper rollback target differs')
 namespace,leaf=TYPE.rsplit('.',1);instance=next(r for r in a.instances if a.qname(r['name'])=='7:'+leaf+':22:'+namespace);traits=instance['traits'];t,b=presentation.named(a,TYPE,SELECTOR);v=t['value'];initial=a.methods['count']-1
 if(t!=traits['rows'][-1]or v['flags']!=1 or v['dispatch']!=0 or 'metadata'in v or v['method']!=initial or a.qname(v['name'])!='7:'+SELECTOR+':5:'+namespace+':'+leaf or b!=a.bodies['rows'][-1]or b['value']['frame'][2]!=row['value']['frame'][2]):raise ValueError('Swatch selector is not exact appended private ABI')
 info=a.methods['rows'][initial]['value']
 if(info['flags']!=0 or info['optional']or info['param_names']or len(info['params'])!=1 or a.qname(info['params'][0])!='7:int:22:'or a.qname(info['ret'])!='7:int:22:'):raise ValueError('Swatch selector callable signature differs')
 frozen=semantics(a)
 for name in(METHOD,SELECTOR):
  _,body=presentation.named(a,TYPE,name)
  if sha(swatch_provider.semantic(a,body).encode())!=frozen[name]:raise ValueError('Swatch reviewed helper semantic differs: '+name)
 patches=[(traits['start'],traits['end'],attach._u30(traits['count']-1)+raw[traits['head']:traits['rows'][-1]['start']])]
 for pool,count in zip(a.pools,d['pool_counts']):
  if type(count)is not int or not 0<=count<=pool['count']:raise ValueError('Swatch pool prefix differs')
  end=pool['head']if count<=1 else pool['rows'][count-2]['end'];patches.append((pool['start'],pool['end'],attach._u30(count)+raw[pool['head']:end]))
 table=a.methods;patches.append((table['start'],table['end'],attach._u30(table['count']-1)+raw[table['head']:table['rows'][-1]['start']]))
 table=a.bodies;rows=table['rows'][:-1];body=attach._u30(table['count']-1)+b''.join(oldraw if r['value']['method']==old['method']else raw[r['start']:r['end']]for r in rows);patches.append((table['start'],table['end'],body));limit=len(raw)
 for start,end,value in sorted(patches,reverse=True):
  if end>limit or start>end:raise ValueError('Swatch rollback overlaps')
  raw=raw[:start]+value+raw[end:];limit=start
 return replace_payload(restored,prefix+raw)

def validate_proof(proof,final):
 if not isinstance(proof,dict)or proof.get('ok')is not True or type(proof.get('declares'))is not bool or type(proof.get('dcc'))is not bool or proof.get('dcc')and not proof['declares']:raise ValueError('Swatch column class capability proof differs')
 if(proof.get('source_sha256')!=pins()or proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False or proof.get('final_swf_sha256')!=sha(final)or proof.get('abc_sha256')!=sha(binding._abc_payload(final)[1])):raise ValueError('Swatch column final/source pins differ')
 if proof['declares']:
  if any(type(proof.get(k))is not int or proof[k]!=v for k,v in{'owned_helpers_replaced':1,'appended_methods':1,'appended_fields':0,'changed_original_native_bodies':1 if proof['dcc']else 0}.items()):raise ValueError('Swatch column mutation inventory differs')
  if any(proof.get(k)is not True for k in('helper_rollback_verified','serialized_owned_bodies_verified','all_unowned_bodies_retained','native_protected_bindings_verified','native_cfg_projection_verified')):raise ValueError('Swatch column semantic/native guarantees missing')
  if proof['dcc']!=(proof.get('native_body')is not None):raise ValueError('Swatch donor callback rollback missing or unrequested')
 else:
  a=ABC(binding._abc_payload(final)[1]).parse()
  if proof['dcc']or proof.get('baseline_swf_sha256')!=sha(final)or any(a.qname(i['name'])=='7:ColorSwatchPanel:22:widgets.CAS.controls'for i in a.instances):raise ValueError('Nondeclaring canonical swatch provider differs')

def chain_adapter(prior,proof,final):
 validate_proof(proof,final)
 kind,verifier=predecessor(prior)
 if proof.get('previous_stage_kind')!=kind:raise ValueError('Swatch columns predecessor authority differs')
 if(not isinstance(prior,dict)or proof.get('baseline_swf_sha256')!=prior.get('patched_resource_sha256')or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or proof['declares']!=(prior.get('base_resource_sha256')=='6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0')or proof['dcc']!=proof['declares']):raise ValueError('Swatch columns exact Featured provider predecessor differs')
 base=reconstruct(final,proof)
 if sha(base)!=proof.get('baseline_swf_sha256')or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256')or verifier(prior,base)is not True:raise ValueError('Swatch columns complete provider rollback differs')
 return dict(base_resource_sha256=prior['base_resource_sha256'],patched_resource_sha256=sha(final),previous_stage_adapter=copy.deepcopy(prior),previous_stage_sha256=comm.contract_digest(prior),swatch_columns_contract=copy.deepcopy(proof),postproof_sha256=comm.contract_digest(proof))
def verify_adapter(adapter,final):
 if not isinstance(adapter,dict)or chain_adapter(adapter.get('previous_stage_adapter'),adapter.get('swatch_columns_contract'),final)!=adapter:raise ValueError('Swatch columns provider adapter differs')
 return True
def chain_main(prior,proof,final):
 validate_proof(proof,final)
 kind,verifier=predecessor(prior,True)
 if proof.get('previous_stage_kind')!=kind:raise ValueError('Swatch columns Main predecessor authority differs')
 if(not isinstance(prior,dict)or proof.get('baseline_swf_sha256')!=prior.get('final_swf_sha256')or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or proof['declares']is not True or proof['dcc']is not False):raise ValueError('Swatch columns exact Featured Main predecessor differs')
 base=reconstruct(final,proof)
 if sha(base)!=proof.get('baseline_swf_sha256')or sha(binding._abc_payload(base)[1])!=proof.get('baseline_abc_sha256')or verifier(prior,base)is not True:raise ValueError('Swatch columns complete Main rollback differs')
 return dict(previous_stage_contract=copy.deepcopy(prior),previous_stage_sha256=comm.contract_digest(prior),swatch_columns_main_contract=copy.deepcopy(proof),postproof_sha256=comm.contract_digest(proof),final_swf_sha256=sha(final))
def verify_main(contract,final):
 if not isinstance(contract,dict)or chain_main(contract.get('previous_stage_contract'),contract.get('swatch_columns_main_contract'),final)!=contract:raise ValueError('Swatch columns Main contract differs')
 return True
def historical(adapter,final):
 verify_adapter(adapter,final);return adapter['previous_stage_adapter'],reconstruct(final,adapter['swatch_columns_contract'])

def _compile(base,original,ffdec,work):
 from cas_ui_build import replace_payload
 ffdec=Path(ffdec);work=Path(work);work.mkdir(parents=True,exist_ok=True);start=pins();incoming=work/'baseline.swf';incoming.write_bytes(base);source=work/'native-source'
 comm.run([ffdec,'-selectclass',TYPE,'-export','script',source,original],work/'export.log')
 owned=work/'ColorSwatchPanel.as';owned.write_text(swatch.inject((source/'scripts/widgets/CAS/controls/ColorSwatchPanel.as').read_text(encoding='utf-8-sig'),(ROOT/SOURCES[-1]).read_text()),encoding='utf-8');compiled=work/'compiled.swf'
 comm.run([ffdec,'-importAssets','yes,local','-replace',incoming,compiled,TYPE,owned],work/'compile.log')
 classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=previous.presentation.ROOT
 comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',ROOT/SOURCES[1]],work/'javac.log')
 output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasSwatchColumnsPatch','grid',incoming,compiled,output,report],work/'transplant.log')
 if start!=pins():raise ValueError('Swatch column sources changed during compilation')
 final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text());proof['helper_rollback_verified']=proof.pop('whole_abc_rollback_verified');proof['owned_helpers_replaced']=proof.pop('replaced_owned_bodies')
 proof.update(declares=True,source_sha256=start,rollback=descriptor(base),native_cfg_projection_verified=True,runtime_qualified=False,performance_gain_claimed=False,native_body=None)
 return final,proof
def adapt(prior,base,original,ffdec,work):
 kind,verifier=predecessor(prior)
 if kind!='staging-attach' or verifier(prior,base)is not True:raise ValueError('Swatch columns require complete current Staging-Attach provider')
 if sha(Path(original).read_bytes())!=prior.get('base_resource_sha256'):raise ValueError('Swatch columns original native provider differs')
 if prior['base_resource_sha256']=='5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae':
  proof=dict(ok=True,declares=False,dcc=False,source_sha256=pins(),runtime_qualified=False,performance_gain_claimed=False,baseline_swf_sha256=sha(base),baseline_abc_sha256=sha(binding._abc_payload(base)[1]),final_swf_sha256=sha(base),abc_sha256=sha(binding._abc_payload(base)[1]),previous_stage_sha256=comm.contract_digest(prior),previous_stage_kind=kind,rollback={'unchanged_resource':True})
  return base,chain_adapter(prior,proof,base)
 final,proof=_compile(base,original,ffdec,work);final,native=graft_native(final)
 proof.update(dcc=True,native_body=native,changed_original_native_bodies=1,previous_stage_kind=kind,previous_stage_sha256=comm.contract_digest(prior),final_swf_sha256=sha(final),abc_sha256=sha(binding._abc_payload(final)[1]))
 return final,chain_adapter(prior,proof,final)
def adapt_main(prior,base,original,ffdec,work):
 kind,verifier=predecessor(prior,True)
 if kind!='publication' or verifier(prior,base)is not True:raise ValueError('Swatch columns require complete current Publication Main')
 final,proof=_compile(base,original,ffdec,work)
 proof.update(dcc=False,changed_original_native_bodies=0,previous_stage_kind=kind,previous_stage_sha256=comm.contract_digest(prior),final_swf_sha256=sha(final),abc_sha256=sha(binding._abc_payload(final)[1]))
 return final,chain_main(prior,proof,final)
def unwrap_providers(evidence,resources,dependencies=None):
 import dbpf_build,maru_companion
 keys={dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)}
 if not isinstance(evidence,dict)or set(evidence)!=keys:raise ValueError('Both swatch column provider continuations required')
 out=dict(resources);providers={}
 for name in keys:
  adapter=evidence[name]
  if not isinstance(adapter,dict)or not isinstance(adapter.get('swatch_columns_contract'),dict)or adapter['swatch_columns_contract'].get('previous_stage_kind')!='staging-attach':raise ValueError('Swatch column current provider stage missing/downgraded')
  key=tuple(int(n,16)for n in name.split(':'));providers[name],out[key]=historical(adapter,resources.get(key,b''))
 return providers,out,dependencies
def unwrap_manifest(info,resources):
 import dbpf_build,maru_companion
 source=info.get('source_pins',{});providers=info.get('grid_provider_adapters');main=info.get('swatch_columns_main_native_bytecode_contract')
 current=any(n in source for n in SOURCES)or main is not None or any(isinstance(a,dict)and 'swatch_columns_contract'in a for a in(providers or {}).values())
 if not current:return info,resources
 if not isinstance(source,dict)or any(source.get(k)!=v for k,v in pins().items()):raise ValueError('Swatch column source pins missing/partial/stale')
 if not isinstance(main,dict)or main.get('previous_stage_contract')!=info.get('publication_trace_main_native_bytecode_contract')or main.get('swatch_columns_main_contract',{}).get('previous_stage_kind')!='publication':raise ValueError('Swatch column exact Publication Main predecessor absent')
 key=maru_companion.CUSTOMIZER;final=resources.get(key,b'')
 if info.get('patched_resource_sha256')!=sha(final)or info.get('patched_resources',{}).get(dbpf_build.tgi(key))!=sha(final):raise ValueError('Advertised swatch column Main identity differs')
 verify_main(main,final)
 for name in(dbpf_build.tgi(maru_companion.GRID_LIBRARY),dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)):
  native=tuple(int(n,16)for n in name.split(':'))
  if info.get('patched_resources',{}).get(name)!=sha(resources.get(native,b'')):raise ValueError('Advertised swatch column provider identity differs')
 p,r,_=unwrap_providers(providers,resources);updated=copy.deepcopy(info);updated['grid_provider_adapters']=p;updated['companion_code_merge']['grid_library_adapter']=p[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
 for name,adapter in p.items():updated['patched_resources'][name]=adapter['patched_resource_sha256']
 r[key]=reconstruct(final,main['swatch_columns_main_contract']);updated['patched_resource_sha256']=sha(r[key]);updated['patched_resources'][dbpf_build.tgi(key)]=sha(r[key])
 return updated,r
