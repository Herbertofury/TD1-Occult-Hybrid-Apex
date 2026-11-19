"""Optional real compiled provider proof; set APEX_CAS_SPARES_FIXTURE_DIR.

The directory only selects bytes. Complete recursive production verification
still authenticates both providers, every replacement, and all predecessors.
"""
from pathlib import Path
import copy,json,os,sys,unittest
REPO=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
ROOT=Path(os.environ.get('APEX_SPARES_SOURCE_ROOT',Path(__file__).resolve().parents[1])).resolve()
sys.path[:0]=[str(ROOT/'tools'),str(REPO/'tools')]
import cas_grid_spares as stage,cas_catalog_binding as binding,cas_grid_presentation as presentation,cas_communication_index as comm
from cas_ui_build import replace_payload
FIXTURE=os.environ.get('APEX_CAS_SPARES_FIXTURE_DIR')

@unittest.skipUnless(FIXTURE,'Set APEX_CAS_SPARES_FIXTURE_DIR for authenticated compiled fixtures')
class SpareChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows={}
  for suffix in('12272E1AC0C1F8E2','89D13757C58C2E05'):
   p=Path(FIXTURE)/suffix;cls.rows[suffix]=(json.loads((p/'contract.json').read_text()),(p/'final.swf').read_bytes(),(p/'baseline.swf').read_bytes())
 def mutate(self,final,owner,name):
  prefix,raw=binding._abc_payload(final);a=stage.mechanics.ABC(raw).parse();_,b=presentation.named(a,owner,name);code=b['value']['code'];at=raw.find(code,b['start'],b['end']);self.assertGreaterEqual(at,0)
  data=bytearray(raw);data[at]=0xd1 if data[at]==0xd0 else 0x27
  return replace_payload(final,prefix+bytes(data))
 def rehash(self,contract,final):
  c=copy.deepcopy(contract);p=c['spare_custody_contract'];p['final_swf_sha256']=stage.sha(final);p['abc_sha256']=stage.sha(binding._abc_payload(final)[1]);c['patched_resource_sha256']=stage.sha(final);c['postproof_sha256']=comm.contract_digest(p);return c
 def test_both_native_rollback_bytes_are_exact_complete_intrinsic_predecessors(self):
  for suffix,(c,final,base)in self.rows.items():
   with self.subTest(suffix=suffix):
    self.assertTrue(stage.verify_adapter(c,final));prior,restored=stage.historical(c,final);self.assertEqual(restored,base);self.assertEqual(prior,c['previous_stage_adapter'])
 def test_owned_custody_or_native_body_cannot_change_under_rehashed_claims(self):
  c,final,_=self.rows['12272E1AC0C1F8E2']
  for owner,name in((stage.GRID,'ApexGridSpareCustody'),('olympus.layout.GridLayout','CreateCell')):
   changed=self.mutate(final,owner,name)
   with self.subTest(name=name),self.assertRaises(ValueError):stage.verify_adapter(self.rehash(c,changed),changed)
 def test_every_required_abi_rollback_and_source_fact_is_mandatory(self):
  c,final,_=self.rows['12272E1AC0C1F8E2']
  for key,value in(('source_sha256',{}),('rollback',{}),('appended_fields',1),('changed_original_native_bodies',1),('appended_methods',6),('whole_abc_rollback_verified',False),('native_protected_bindings_verified',False),('runtime_qualified',True),('performance_gain_claimed',True)):
   bad=copy.deepcopy(c);bad['spare_custody_contract'][key]=value;bad['postproof_sha256']=comm.contract_digest(bad['spare_custody_contract'])
   with self.subTest(key=key),self.assertRaises(ValueError):stage.verify_adapter(bad,final)
 def test_downgraded_predecessor_partial_provider_or_foreign_final_refuses(self):
  c,final,_=self.rows['12272E1AC0C1F8E2'];bad=copy.deepcopy(c);bad['previous_stage_adapter']=bad['previous_stage_adapter']['previous_stage_adapter']
  bad['previous_stage_sha256']=comm.contract_digest(bad['previous_stage_adapter'])
  with self.assertRaises(ValueError):stage.verify_adapter(bad,final)
  other=self.rows['89D13757C58C2E05'][1]
  with self.assertRaises(ValueError):stage.verify_adapter(c,other)
  with self.assertRaises(ValueError):stage.unwrap_providers({'62ECC59A:00000000:12272E1AC0C1F8E2':c},{})
 def test_provider_only_manifest_restores_both_libraries_and_keeps_main_exact(self):
  resources={(0x62ECC59A,0,int(n,16)):r[1]for n,r in self.rows.items()};providers={'62ECC59A:00000000:'+n:r[0]for n,r in self.rows.items()}
  main=(0x62ECC59A,0,0xDF09D526F4C77B95);resources[main]=b'unchanged exact Main bytes';donor='62ECC59A:00000000:89D13757C58C2E05'
  info={'source_pins':stage.pins(),'grid_provider_adapters':providers,'companion_code_merge':{'grid_library_adapter':providers[donor]},'patched_resources':{f'{k[0]:08X}:{k[1]:08X}:{k[2]:016X}':stage.sha(v)for k,v in resources.items()}}
  changed,restored=stage.unwrap_manifest(info,resources);self.assertEqual(restored[main],resources[main]);self.assertEqual(set(restored),set(resources))
  for suffix,(_,_,base)in self.rows.items():self.assertEqual(restored[(0x62ECC59A,0,int(suffix,16))],base)
  for missing in stage.SOURCES:
   bad=copy.deepcopy(info);del bad['source_pins'][missing]
   with self.subTest(missing=missing),self.assertRaises(ValueError):stage.unwrap_manifest(bad,resources)

if __name__=='__main__':unittest.main()
