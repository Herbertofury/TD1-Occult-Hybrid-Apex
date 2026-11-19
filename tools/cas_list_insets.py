"""Shared native rail/search layout, exact three-owner Main continuation.

All original constructors and unselected ABC bytes are restored before the
complete Workflow predecessor is verified. Grid providers are untouched.
"""
from pathlib import Path
import copy,hashlib,json,re,os
ROOT=Path(__file__).resolve().parents[1]
import cas_list_insets_stage as stage
import cas_catalog_workflow as previous
import cas_grid_budget as mechanics,cas_grid_presentation as presentation
import cas_catalog_binding as binding,cas_cell_attach as attach,cas_communication_index as comm
MAIN=previous.MAIN;CATALOG='widgets.CAS.Customizer.CatalogPanel';BODY='dcc.catalog.BodyTypeTabs'
SOURCES=('tools/cas_list_insets.py','tools/cas_list_insets_stage.py','tools/CasListInsetsPatch.java','Source/CASUi/catalog_list_inset_methods.as')
CONTRACT='catalog_list_insets_contract';MANIFEST='catalog_list_insets_main_native_bytecode_contract'
ROLES=((MAIN,False,stage.MAIN_REPLACED,('ApexCatalogListSlot','ApexCatalogListCurrent','ApexCatalogListRecord','ApexCatalogListApply','ApexCatalogListRail','ApexCatalogListGeometry','ApexCatalogSearchListApply','ApexCatalogSearchListRestore','ApexCatalogListRect','ApexCatalogListStatus'),()),
       (CATALOG,False,('RefreshLayout',),('ApexRawListGeneration','ApexRawListBaseline'),('apexRawListGeneration','apexRawListLayout')),
       (BODY,True,stage.BODY_REPLACED,stage.BODY_ADDED,('apexListLayout',)))
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def pins():return {n:sha((ROOT/n).read_bytes())for n in SOURCES}
class ABC(mechanics.ABC):
 def namespace(self,index):
  return re.sub(r'(?<=5:)(CASCustomizerMain|CatalogPanel|BodyTypeTabs)\.as\$[0-9]+',r'\1.as$SELF',super().namespace(index))
def owner_rows(a,owner,statik):
 ns,leaf=owner.rsplit('.',1);hits=[i for i,v in enumerate(a.instances)if a.qname(v['name'])=='7:'+leaf+':22:'+ns]
 if len(hits)!=1:raise ValueError('Exact native UI owner absent')
 return (a.classes if statik else a.instances)[hits[0]]['traits']
def named(a,owner,statik,name):
 rows=[r for r in owner_rows(a,owner,statik)['rows']if a.string(a.pool(6,r['value']['name'])['name'])==name]
 if len(rows)!=1:raise ValueError('Exact UI trait missing/ambiguous: '+owner+'/'+name)
 t=rows[0]
 if t['value']['flags']&15!=1:raise ValueError('Expected exact method trait')
 bodies=[b for b in a.bodies['rows']if b['value']['method']==t['value']['method']]
 if len(bodies)!=1:raise ValueError('Exact method body absent')
 return t,bodies[0]
def semantic_pins():
 text=(ROOT/SOURCES[2]).read_text();rows=re.findall(r'Map.entry\("([^"\n]+)","([0-9a-f]{64})"\)',text)
 expected={o+'/'+n for o,s,r,added,f in ROLES for n in r+added}
 if len(rows)!=len(expected)or set(n for n,h in rows)!=expected:raise ValueError('Complete list inset semantic pins absent')
 return dict(rows)

def semantic(a,row):
    b=row['value'];info=a.methods['rows'][b['method']]['value'];stack,regs,initial,maximum=b['frame']
    q=lambda n:presentation.draw._qname(a,n)
    text=str(info['flags'])+'|'+q(info['ret'])+''.join('|'+q(p) for p in info['params'])+'|'+str(regs)+'|'+str(stack)+'|'+str(maximum-initial)
    for r in b['traits']['rows']:
        t=r['value']
        if t['flags']&15 not in (0,6):raise ValueError('Presentation activation has non-slot trait.')
        text+='|local:'+q(t['name'])+':'+q(t['type'])+':'+str(t['slot'])+':'+str(t['value'])+':'+str(t.get('value_kind',0))
    code=a.instructions(b['code']);addresses={x[0]:i for i,x in enumerate(code)};addresses[len(b['code'])]=len(code)
    lines=[args[3] for _,_,op,args in code if op==0xef and len(args)==4 and args[0]==1 and args[3]>0];base=min(lines) if lines else None
    names={0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2}
    for start,end,op,args in code:
        text+='\n'+str(op)
        for n,value in enumerate(args):
            target=None
            if 0x0c<=op<=0x1a:target=end+value
            elif op==0x1b and n!=1:target=start+value
            if target is not None:
                if target not in addresses:raise ValueError('Presentation branch leaves instruction boundary.')
                token='@'+str(addresses[target])
            elif n==0 and op in names:token=q(value)
            elif n==1 and op==0xef:token=a.string(value)
            elif n==3 and op==0xef and args[0]==1 and value>0:token='owned-source+'+str(value-base)
            elif n==0 and op==0xf1:token='owned-helper-source'
            elif n==0 and op==0x2c:token=a.string(value)
            elif n==0 and op in (0x2d,0x2e):
                number=a.pool(op-0x2d,value)
                if op==0x2d and number&0x80000000:number-=1<<32
                token=str(number)
            elif n==0 and op==0x2f:
                number=a.pool(2,value)
                tokens={0.01:'0.01',0.8:'0.8',0.88:'0.88'}
                if number not in tokens:raise ValueError('Unreviewed scheduling double constant: '+repr(number))
                token=tokens[number]
            else:token=str(value)
            text+=':'+token
    for start,end,target,kind,name in b['exceptions']:
        if any(v not in addresses for v in (start,end,target)):raise ValueError('Presentation exception leaves instruction boundary.')
        text+='\ncatch:'+str(addresses[start])+':'+str(addresses[end])+':'+str(addresses[target])+':'+q(kind)+':'+q(name)
    return text

def descriptor(base):
 _,raw=binding._abc_payload(base);a=ABC(raw).parse()
 return {'pool_counts':[p['count']for p in a.pools],
         'bodies':{o+'/'+n:raw[named(a,o,s,n)[1]['start']:named(a,o,s,n)[1]['end']].hex()for o,s,r,added,f in ROLES for n in r}}

def reconstruct(final,d):
 from cas_ui_build import replace_payload
 prefix,raw=binding._abc_payload(final);a=ABC(raw).parse();expected={o+'/'+n for o,s,r,added,f in ROLES for n in r}
 if not isinstance(d,dict)or set(d)!={'pool_counts','bodies'}or not isinstance(d['bodies'],dict)or set(d['bodies'])!=expected:raise ValueError('Exact three-owner rollback inventory absent')
 if not isinstance(d['pool_counts'],list)or len(d['pool_counts'])!=7:raise ValueError('Complete original pool prefix absent')
 frozen=semantic_pins();restored={};patches=[];next_method=a.methods['count']-14;next_body=a.bodies['count']-14
 if next_method<1 or next_body<1:raise ValueError('Appended method suffix absent')
 for owner,statik,replaced,added,fields in ROLES:
  ts=owner_rows(a,owner,statik);tail=ts['rows'][-len(added)-len(fields):];anchor=named(a,owner,statik,replaced[0])[1]
  anchor_info=a.methods['rows'][anchor['value']['method']]['value'];normal_scope=anchor['value']['frame'][2]-(1 if anchor_info['flags']&2 else 0)
  for n in replaced+added:
   t,b=named(a,owner,statik,n);v=t['value'];info=a.methods['rows'][b['value']['method']]['value']
   if sha(semantic(a,b).encode())!=frozen[owner+'/'+n]:raise ValueError('Reviewed UI semantic/CFG differs: '+owner+'/'+n)
   if b['value']['frame'][2]!=normal_scope+(1 if info['flags']&2 else 0):raise ValueError('Lexical/activation scope differs')
   for _,_,op,args in a.instructions(b['value']['code']):
    if op in(0x40,0x43,0x44,0x67):raise ValueError('Foreign nested/outer/callmethod linkage')
    if op==0x60 and a.string(a.pool(6,args[0])['name'])=='flash':raise ValueError('Unbound flash package lookup')
    if op in(0x60,0x46,0x4f)and a.string(a.pool(6,args[0])['name'])=='getQualifiedClassName'and a.qname(args[0])!='7:getQualifiedClassName:22:flash.utils':raise ValueError('Runtime class QName differs')
  for i,n in enumerate(added):
   t,b=named(a,owner,statik,n);v=t['value'];info=a.methods['rows'][v['method']]['value']
   flags=17 if owner in(CATALOG,BODY)else 1
   ns='22:'if owner==CATALOG or n=='ApexNativeRailReceipt'else'5:'+owner.rsplit('.',1)[0]+':'+owner.rsplit('.',1)[1]
   if t!=tail[i]or v['flags']!=flags or v['dispatch']!=0 or'metadata'in v or a.qname(v['name'])!='7:'+n+':'+ns or v['method']!=next_method or b!=a.bodies['rows'][next_body]:raise ValueError('Exact appended callable suffix/namespace differs')
   if len(info['optional'])!=(1 if n=='ApexCatalogListRail'else 0)or info['param_names']:raise ValueError('New optional callable ABI differs')
   next_method+=1;next_body+=1
  for i,n in enumerate(fields):
   v=tail[len(added)+i]['value'];kind='int'if n=='apexRawListGeneration'else'Object';namespace='5:'+owner.rsplit('.',1)[0]+':'+owner.rsplit('.',1)[1]
   if(v['flags']!=0 or'metadata'in v or a.qname(v['name'])!='7:'+n+':'+namespace or a.qname(v['type'])!='7:'+kind+':22:'or
      v['slot']!=(41 if statik else 0)or v['value']!=0):raise ValueError('Exact typed UI metadata slot/default differs')
  patches.append((ts['start'],ts['end'],attach._u30(ts['count']-len(tail))+raw[ts['head']:tail[0]['start']]))
  for n in replaced:
   value=d['bodies'][owner+'/'+n]
   if not isinstance(value,str)or re.fullmatch('[0-9a-f]{2,300000}',value)is None:raise ValueError('Original body malformed/unbounded')
   data=bytes.fromhex(value);r=ABC(data);old=r.body();current=named(a,owner,statik,n)[1]
   if r.at!=len(data)or old['method']!=current['value']['method']:raise ValueError('Original body targets foreign method')
   restored[old['method']]=data
 if next_method!=a.methods['count']or next_body!=a.bodies['count']:raise ValueError('Appended suffix incomplete')
 for p,count in zip(a.pools,d['pool_counts']):
  if type(count)is not int or not 0<=count<=p['count']:raise ValueError('Original pool count invalid')
  end=p['head']if count<=1 else p['rows'][count-2]['end'];patches.append((p['start'],p['end'],attach._u30(count)+raw[p['head']:end]))
 table=a.methods;patches.append((table['start'],table['end'],attach._u30(table['count']-14)+raw[table['head']:table['rows'][-14]['start']]))
 table=a.bodies;patches.append((table['start'],table['end'],attach._u30(table['count']-14)+b''.join(restored.get(r['value']['method'],raw[r['start']:r['end']])for r in table['rows'][:-14])))
 limit=len(raw)
 for start,end,value in sorted(patches,reverse=True):
  if start>end or end>limit:raise ValueError('Rollback spans overlap')
  raw=raw[:start]+value+raw[end:];limit=start
 return replace_payload(final,prefix+raw)

def chain(prior,proof,final):
 required=('whole_abc_rollback_verified','all_unowned_bodies_retained','serialized_owned_bodies_verified','native_protected_bindings_verified','constructors_retained','runtime_class_QName_verified')
 expected={'changed_original_native_bodies':4,'replaced_owned_bodies':5,'appended_methods':14,'appended_fields':3}
 if(not isinstance(prior,dict)or 'catalog_workflow_contract'not in prior or not isinstance(proof,dict)or proof.get('ok')is not True or
    any(proof.get(n)is not True for n in required)or any(type(proof.get(n))is not int or proof[n]!=v for n,v in expected.items())or
    proof.get('source_sha256')!=pins()or proof.get('previous_stage_sha256')!=comm.contract_digest(prior)or proof.get('runtime_qualified')is not False or proof.get('performance_gain_claimed')is not False):raise ValueError('Complete list inset proof differs')
 if sha(final)!=proof.get('final_swf_sha256')or sha(binding._abc_payload(final)[1])!=proof.get('abc_sha256'):raise ValueError('Final resource/ABC identity differs')
 original=reconstruct(final,proof.get('rollback'))
 if sha(original)!=proof.get('baseline_swf_sha256')or sha(original)!=prior.get('final_swf_sha256')or sha(binding._abc_payload(original)[1])!=proof.get('baseline_abc_sha256'):raise ValueError('Complete original bytes differ')
 if previous.verify_main(prior,original)is not True:raise ValueError('Full Workflow predecessor differs')
 return {'previous_stage_contract':copy.deepcopy(prior),'previous_stage_sha256':comm.contract_digest(prior),CONTRACT:copy.deepcopy(proof),'postproof_sha256':comm.contract_digest(proof),'final_swf_sha256':sha(final)}

def verify_main(contract,final):
 if not isinstance(contract,dict)or chain(contract.get('previous_stage_contract'),contract.get(CONTRACT),final)!=contract:raise ValueError('Exact shared list inset contract differs')
 return True

def historical(contract,final):
 verify_main(contract,final)
 return contract['previous_stage_contract'],reconstruct(final,contract[CONTRACT]['rollback'])

def inject_main(source):
 source=stage.main(previous.inject_main(source));extra=(ROOT/SOURCES[-1]).read_text();suffix='\n'+extra
 if not source.endswith(suffix):raise ValueError('Exact composed helper suffix differs')
 source=source[:-len(suffix)];at=source.rfind('\n   }')
 if at<0:raise ValueError('Main class boundary absent')
 source=source[:at]+'\n'+extra+source[at:]
 return source.replace('   import flash.utils.describeType;','   import flash.utils.getQualifiedClassName;\n   import flash.utils.describeType;',1)

def _extent(source,name):
 matches=list(re.finditer(r'\b(?:public|private|protected)(?: (?:static|final))? function '+re.escape(name)+r'\([^)]*\)\s*:\s*[\w.<>]+\s*\{',source))
 if len(matches)!=1:raise ValueError('Exact native source method boundary differs')
 start=matches[0].start();at=matches[0].end();depth=1
 while depth:depth+=(source[at]=='{')-(source[at]=='}');at+=1
 return start,at
def _append(source,extra):
 at=source.rfind('\n   }')
 if at<0:raise ValueError('Native class boundary absent')
 return source[:at]+'\n'+extra+source[at:]

def adapt_main(prior,base,source,ffdec,work):
 from cas_ui_build import replace_payload
 if not isinstance(prior,dict)or'catalog_workflow_contract'not in prior or previous.verify_main(prior,base)is not True:raise ValueError('Exact current Workflow predecessor required')
 work=Path(work);work.mkdir(parents=True,exist_ok=True);ffdec=Path(ffdec);start=pins();(work/'baseline.swf').write_bytes(base)
 owned=work/'CASCustomizerMain.as';owned.write_text(inject_main(Path(source).read_text(encoding='utf-8-sig')),encoding='utf-8')
 current=work/'main-compiled.swf';comm.run([ffdec,'-importAssets','yes,local','-replace',work/'baseline.swf',current,MAIN,owned],work/'main-compile.log')
 for owner in(CATALOG,BODY):
  native=work/('native-'+owner.rsplit('.',1)[1]);comm.run([ffdec,'-selectclass',owner,'-export','script',native,work/'baseline.swf'],work/(owner.rsplit('.',1)[1]+'-export.log'))
  original=(native/'scripts'/Path(owner.replace('.','/')+'.as')).read_text(encoding='utf-8-sig')
  if owner==CATALOG:text,extra=stage.catalog(original)
  else:
   made,extra=stage.body(original);text=original
   for name in stage.BODY_REPLACED:
    a,b=_extent(text,name);x,y=_extent(made,name);text=text[:a]+made[x:y]+text[b:]
  owned=work/(owner.rsplit('.',1)[1]+'.as');owned.write_text(_append(text,extra),encoding='utf-8');target=work/(owner.rsplit('.',1)[1]+'-compiled.swf')
  comm.run([ffdec,'-importAssets','yes,local','-replace',current,target,owner,owned],work/(owner.rsplit('.',1)[1]+'-compile.log'));current=target
 classes=work/'classes';classes.mkdir(exist_ok=True);jar=ffdec.with_name('ffdec.jar');project=presentation.ROOT
 comm.run(['javac','-cp',jar,'-d',classes,project/'tools/CasStructuralRolesPatch.java',project/'tools/CasCommunicationIndexPatch.java',ROOT/SOURCES[2]],work/'javac.log')
 output=work/'retained.abc';report=work/'proof.json';comm.run(['java','-cp',str(jar)+os.pathsep+str(classes),'CasListInsetsPatch',work/'baseline.swf',current,output,report],work/'transplant.log')
 if start!=pins():raise ValueError('List inset source changed during compilation')
 final=replace_payload(base,binding._abc_payload(base)[0]+output.read_bytes());proof=json.loads(report.read_text())
 proof.update(source_sha256=start,previous_stage_sha256=comm.contract_digest(prior),rollback=descriptor(base),final_swf_sha256=sha(final))
 return final,chain(prior,proof,final)

def unwrap_manifest(info,resources):
 import dbpf_build,maru_companion
 source=info.get('source_pins',{});contract=info.get(MANIFEST);current=any(n in source for n in SOURCES)or contract is not None
 if not current:return info,resources
 if not isinstance(source,dict)or any(source.get(n)!=v for n,v in pins().items()):raise ValueError('List inset source pins missing/partial/stale')
 if not isinstance(contract,dict)or contract.get('previous_stage_contract')!=info.get(previous.MANIFEST):raise ValueError('Exact Workflow manifest predecessor differs')
 key=maru_companion.CUSTOMIZER;final=resources.get(key,b'');name=dbpf_build.tgi(key)
 if info.get('patched_resource_sha256')!=sha(final)or info.get('patched_resources',{}).get(name)!=sha(final):raise ValueError('Advertised composed Main differs')
 prior,base=historical(contract,final);updated=copy.deepcopy(info);out=dict(resources);out[key]=base
 updated['patched_resource_sha256']=sha(base);updated['patched_resources'][name]=sha(base)
 return updated,out
