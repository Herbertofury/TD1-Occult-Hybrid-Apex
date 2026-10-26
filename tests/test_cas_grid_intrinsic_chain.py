"""Optional actual-compiled proof; set APEX_CAS_INTRINSIC_FIXTURE_DIR explicitly.

Expected fixture layout: main/ and both provider suffixes, each containing
contract.json, final.swf and baseline.swf. All bytes pass the production exact
recursive validators; merely supplying an environment directory grants no trust.
"""
from pathlib import Path
import copy,json,os,sys,unittest
ROOT=Path(os.environ.get('APEX_INTRINSIC_SOURCE_ROOT',Path(__file__).resolve().parents[1])).resolve()
REPO=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(REPO/'tools')]
import cas_grid_intrinsic as stage
import cas_catalog_binding as binding,cas_grid_presentation as presentation,cas_communication_index as comm
from cas_ui_build import replace_payload
FIXTURE=os.environ.get('APEX_CAS_INTRINSIC_FIXTURE_DIR')

@unittest.skipUnless(FIXTURE,"Set APEX_CAS_INTRINSIC_FIXTURE_DIR for authenticated compiled fixtures")
class IntrinsicChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows={}
  for name,owner in [('12272E1AC0C1F8E2',stage.GRID),('89D13757C58C2E05',stage.GRID),('main',stage.MAIN)]:
   folder=Path(FIXTURE)/name;cls.rows[name]=(owner,json.loads((folder/'contract.json').read_text()),(folder/'final.swf').read_bytes(),(folder/'baseline.swf').read_bytes())
 def mutate(self,final,owner,method,operand=False):
  prefix,raw=binding._abc_payload(final);a=stage.mechanics.ABC(raw).parse();_,body=presentation.named(a,owner,method);code=body['value']['code'];at=raw.find(code,body['start'],body['end']);self.assertNotEqual(at,-1)
  value=bytearray(raw)
  if operand:
   first=next(x for x in a.instructions(code)if x[2]==0x24 and x[3]==[1]);value[at+first[0]+1]=2
  else:value[at]=0xd1 if value[at]==0xd0 else 0x27
  return replace_payload(final,prefix+bytes(value))
 def rehash(self,contract,final,owner):
  bad=copy.deepcopy(contract);proof=bad['intrinsic_geometry_contract'];proof['final_swf_sha256']=stage.sha(final);proof['abc_sha256']=stage.sha(binding._abc_payload(final)[1]);bad['patched_resource_sha256'if owner==stage.GRID else'final_swf_sha256']=stage.sha(final);bad['postproof_sha256']=comm.contract_digest(proof);return bad
 def test_three_complete_native_rollbacks_restore_exact_predecessor_bytes(self):
  for name,(owner,contract,final,base)in self.rows.items():
   with self.subTest(name=name):
    self.assertTrue(stage.verify_adapter(contract,final)if owner==stage.GRID else stage.verify_main(contract,final))
    prior,raw=stage.historical(contract,final,owner);self.assertEqual(raw,base);self.assertEqual(prior,contract['previous_stage_adapter'if owner==stage.GRID else'previous_stage_contract'])
 def test_valid_code_and_rehashed_claims_cannot_change_the_intrinsic_capability(self):
  for name,method in [('12272E1AC0C1F8E2','ApexGridIntrinsicCapture'),('main','ApexCatalogGridRequest')]:
   owner,contract,final,_=self.rows[name];changed=self.mutate(final,owner,method,True);bad=self.rehash(contract,changed,owner)
   with self.subTest(name=name),self.assertRaisesRegex(ValueError,'semantic/CFG'):
    stage.verify_adapter(bad,changed)if owner==stage.GRID else stage.verify_main(bad,changed)
 def test_unowned_original_native_method_change_is_not_hidden_by_new_hashes(self):
  owner,contract,final,_=self.rows['12272E1AC0C1F8E2'];changed=self.mutate(final,'olympus.layout.GridLayout','CreateCell');bad=self.rehash(contract,changed,owner)
  with self.assertRaisesRegex(ValueError,'predecessor bytes'):stage.verify_adapter(bad,changed)
 def test_required_source_raw_rollback_and_authority_fields_cannot_disappear(self):
  owner,contract,final,_=self.rows['12272E1AC0C1F8E2']
  for key,value in [('source_sha256',{}),('rollback',{}),('all_unowned_bodies_retained',False),('native_protected_bindings_verified',False),('runtime_qualified',True),('performance_gain_claimed',True),('appended_fields',1)]:
   bad=copy.deepcopy(contract);bad['intrinsic_geometry_contract'][key]=value;bad['postproof_sha256']=comm.contract_digest(bad['intrinsic_geometry_contract'])
   with self.subTest(key=key),self.assertRaises(ValueError):stage.verify_adapter(bad,final)
 def test_main_advertised_alias_and_both_provider_bytes_are_authenticated(self):
  main=self.rows['main'];_,mainContract,mainFinal,mainBase=main
  providers={'62ECC59A:00000000:'+name:row[1]for name,row in self.rows.items()if name!='main'}
  resources={(0x62ECC59A,0,int(name,16)):row[2]for name,row in self.rows.items()if name!='main'};mainKey=(0x62ECC59A,0,0xDF09D526F4C77B95);resources[mainKey]=mainFinal
  donor='62ECC59A:00000000:89D13757C58C2E05';info={'source_pins':stage.pins(),'grid_provider_adapters':providers,'intrinsic_geometry_main_native_bytecode_contract':mainContract,'row_delta_main_native_bytecode_contract':mainContract['previous_stage_contract'],'companion_code_merge':{'grid_library_adapter':providers[donor]},'patched_resource_sha256':stage.sha(mainFinal),'patched_resources':{':'.join(format(x,'08X')if i<2 else format(x,'016X')for i,x in enumerate(k)):stage.sha(v)for k,v in resources.items()}}
  bad=copy.deepcopy(info);bad['companion_code_merge']['grid_library_adapter']={}
  with self.assertRaisesRegex(ValueError,'donor alias'):stage.unwrap_manifest(bad,resources)
  updated,restored=stage.unwrap_manifest(info,resources);self.assertEqual(restored[mainKey],mainBase)
  for name,row in self.rows.items():
   if name!='main':self.assertEqual(restored[(0x62ECC59A,0,int(name,16))],row[3])

if __name__=='__main__':unittest.main()
