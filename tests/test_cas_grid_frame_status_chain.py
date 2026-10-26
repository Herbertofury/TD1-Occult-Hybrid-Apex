"""Optional exact three-resource frame-status continuation; no Game access.

Set APEX_CAS_FRAME_STATUS_FIXTURE_DIR to the authenticated compiled directory.
The selector never supplies authority: every predecessor and raw rollback is
still verified by the production terminal module.
"""
from pathlib import Path
import copy,json,os,sys,unittest
REPO=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
ROOT=Path(os.environ.get('APEX_FRAME_STATUS_SOURCE_ROOT',Path(__file__).resolve().parents[1])).resolve()
PARENT=Path(os.environ.get('APEX_LOGICAL_BANK_SOURCE_ROOT',REPO)).resolve()
sys.path[:0]=[str(ROOT/'tools'),str(PARENT/'tools'),str(REPO/'tools')]
import cas_grid_frame_status as stage,cas_catalog_binding as binding,cas_grid_presentation as presentation,cas_communication_index as comm
from cas_ui_build import replace_payload
FIXTURE=os.environ.get('APEX_CAS_FRAME_STATUS_FIXTURE_DIR')

@unittest.skipUnless(FIXTURE,'Set APEX_CAS_FRAME_STATUS_FIXTURE_DIR for authenticated compiled fixtures')
class FrameStatusChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows={}
  for suffix in('12272E1AC0C1F8E2','89D13757C58C2E05','main'):
   p=Path(FIXTURE)/suffix;cls.rows[suffix]=(json.loads((p/'contract.json').read_text()),(p/'final.swf').read_bytes(),(p/'baseline.swf').read_bytes())
 def verify(self,name,c,raw):return stage.verify_main(c,raw)if name=='main'else stage.verify_adapter(c,raw)
 def mutate(self,final,owner,name):
  prefix,raw=binding._abc_payload(final);a=stage.mechanics.ABC(raw).parse();_,b=presentation.named(a,owner,name);code=b['value']['code'];at=raw.find(code,b['start'],b['end']);self.assertGreaterEqual(at,0)
  data=bytearray(raw);data[at]=0xd1 if data[at]==0xd0 else 0x27
  return replace_payload(final,prefix+bytes(data))
 def rehash(self,c,final,name):
  c=copy.deepcopy(c);p=c[stage.CONTRACT];p['final_swf_sha256']=stage.sha(final);p['abc_sha256']=stage.sha(binding._abc_payload(final)[1]);c['final_swf_sha256'if name=='main'else'patched_resource_sha256']=stage.sha(final);c['postproof_sha256']=comm.contract_digest(p);return c
 def test_all_three_raw_predecessors_and_their_complete_proofs_are_exact(self):
  for name,(c,final,base)in self.rows.items():
   with self.subTest(name=name):
    self.assertTrue(self.verify(name,c,final));owner=stage.MAIN if name=='main'else stage.GRID;prior,restored=stage.historical(c,final,owner);self.assertEqual(restored,base);self.assertEqual(prior,c['previous_stage_contract'if name=='main'else'previous_stage_adapter'])
 def test_every_owned_api_and_unowned_native_body_refuses_rehashed_mutation(self):
  for name,(c,final,_)in self.rows.items():
   owner=stage.MAIN if name=='main'else stage.GRID
   names=list(sum(stage.inventory(owner),()))
   names.append('SetState'if name=='main'else'ApexGridReady')
   for method in names:
    changed=self.mutate(final,owner,method)
    with self.subTest(resource=name,method=method),self.assertRaises(ValueError):self.verify(name,self.rehash(c,changed,name),changed)
 def test_complete_counts_source_abi_and_effect_claims_are_mandatory(self):
  facts=[('source_sha256',{}),('rollback',{}),('appended_fields',1),('changed_original_native_bodies',1),('appended_methods',0),('whole_abc_rollback_verified',False),('all_unowned_bodies_retained',False),('serialized_owned_bodies_verified',False),('native_protected_bindings_verified',False),('runtime_qualified',True),('performance_gain_claimed',True)]
  for name,(c,final,_)in self.rows.items():
   for key,value in facts:
    bad=copy.deepcopy(c);bad[stage.CONTRACT][key]=value;bad['postproof_sha256']=comm.contract_digest(bad[stage.CONTRACT])
    with self.subTest(resource=name,key=key),self.assertRaises(ValueError):self.verify(name,bad,final)
 def test_final_public_frame_abi_has_exact_visibility_namespace_and_no_fields(self):
  c,final,_=self.rows['12272E1AC0C1F8E2'];_,raw=binding._abc_payload(final);a=stage.mechanics.ABC(raw).parse()
  for name in stage.stage.ADDED:
   trait,body=presentation.named(a,stage.GRID,name);public=name in('ApexGridBeginFrame','ApexGridPendingFrame','ApexGridGeometryFrame')
   self.assertEqual(trait['value']['flags'],17 if public else 1);self.assertEqual(a.qname(trait['value']['name']),'7:'+name+(':22:'if public else':5:olympus.layout:RecyclingGridLayout'))
  bad=copy.deepcopy(c);bad[stage.CONTRACT]['runtime_class_QName_verified']=True;bad['postproof_sha256']=comm.contract_digest(bad[stage.CONTRACT])
  with self.assertRaises(ValueError):stage.verify_adapter(bad,final)
 def test_prior_downgrade_missing_main_and_partial_providers_refuse(self):
  for name,(c,final,_)in self.rows.items():
   key='previous_stage_contract'if name=='main'else'previous_stage_adapter';bad=copy.deepcopy(c);bad[key]=bad[key][key];bad['previous_stage_sha256']=comm.contract_digest(bad[key])
   with self.subTest(name=name),self.assertRaises(ValueError):self.verify(name,bad,final)
  c,final,_=self.rows['12272E1AC0C1F8E2'];other=self.rows['89D13757C58C2E05'][1]
  with self.assertRaises(ValueError):stage.verify_adapter(c,other)
  with self.assertRaises(ValueError):stage.unwrap_providers({'62ECC59A:00000000:12272E1AC0C1F8E2':c},{})
 def info(self):
  import maru_companion,dbpf_build
  main=maru_companion.CUSTOMIZER;resources={(0x62ECC59A,0,int(n,16)):r[1]for n,r in self.rows.items()if n!='main'};resources[main]=self.rows['main'][1];resources[(1,0,99)]=b'unrelated unchanged bytes'
  providers={'62ECC59A:00000000:'+n:r[0]for n,r in self.rows.items()if n!='main'};donor='62ECC59A:00000000:89D13757C58C2E05';c=self.rows['main'][0]
  info={'source_pins':stage.pins(),'grid_provider_adapters':providers,'companion_code_merge':{'grid_library_adapter':providers[donor]},stage.MANIFEST:c,stage.main_previous.MANIFEST:c['previous_stage_contract'],'patched_resource_sha256':stage.sha(resources[main]),'patched_resources':{dbpf_build.tgi(k):stage.sha(v)for k,v in resources.items()}}
  return info,resources
 def test_manifest_recursively_unwraps_three_resources_and_preserves_all_other_bytes(self):
  import maru_companion
  info,resources=self.info();changed,restored=stage.unwrap_manifest(info,resources);self.assertEqual(set(resources),set(restored));self.assertEqual(restored[(1,0,99)],resources[(1,0,99)])
  for name,(_,_,base)in self.rows.items():self.assertEqual(restored[maru_companion.CUSTOMIZER if name=='main'else(0x62ECC59A,0,int(name,16))],base)
  self.assertEqual(changed['patched_resource_sha256'],stage.sha(self.rows['main'][2]))
 def test_manifest_rejects_missing_partial_pins_aliases_or_advertised_identities(self):
  info,resources=self.info()
  for missing in stage.SOURCES:
   bad=copy.deepcopy(info);del bad['source_pins'][missing]
   with self.subTest(missing=missing),self.assertRaises(ValueError):stage.unwrap_manifest(bad,resources)
  for key in(stage.MANIFEST,stage.main_previous.MANIFEST,'patched_resource_sha256'):
   bad=copy.deepcopy(info);del bad[key]
   with self.subTest(missing=key),self.assertRaises(ValueError):stage.unwrap_manifest(bad,resources)
  bad=copy.deepcopy(info);bad['companion_code_merge']['grid_library_adapter']={}
  with self.assertRaises(ValueError):stage.unwrap_manifest(bad,resources)

if __name__=='__main__':unittest.main()
