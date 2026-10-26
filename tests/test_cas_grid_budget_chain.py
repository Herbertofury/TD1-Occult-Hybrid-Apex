from pathlib import Path
import os,sys,json,copy,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_slice.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools')]
import cas_grid_budget as b,cas_ui_build as build,cas_catalog_binding as binding
import cas_grid_featured as featured
FIXTURE=Path(os.environ['APEX_CAS_GRID_BUDGET_FIXTURE'])if os.environ.get('APEX_CAS_GRID_BUDGET_FIXTURE')else None
@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_GRID_BUDGET_FIXTURE for authenticated compiled resources')
class BudgetChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.info=json.loads((FIXTURE/'info.json').read_text());cls.res={tuple(int(n,16)for n in k.split(':')):bytes.fromhex(v)for k,v in json.loads((FIXTURE/'resource-map.json').read_text()).items()}
  previous,rolled=featured.unwrap_manifest(cls.info,cls.res)
  if previous is not cls.info or rolled is not cls.res:
   previous.pop('featured_main_native_bytecode_contract')
   for source in featured.SOURCES:previous['source_pins'].pop(source,None)
   cls.info,cls.res=previous,rolled
 def test_full_main_and_both_provider_chains_restore_the_exact_declared_predecessor(self):
  info,res=b.unwrap_manifest(self.info,self.res)
  for key,adapter in info['grid_provider_adapters'].items():self.assertIn('slice_contract',adapter)
  self.assertEqual(b.sha(res[(0x62ECC59A,0,0xDF09D526F4C77B95)]),info['scroll_main_native_bytecode_contract']['final_swf_sha256'])
 def test_missing_partial_and_stale_source_pins_refuse(self):
  for mode in('missing','partial','stale'):
   info=copy.deepcopy(self.info)
   if mode=='missing':info['source_pins']={n:v for n,v in info['source_pins'].items()if n not in b.SOURCES}
   elif mode=='partial':info['source_pins'].pop(b.SOURCES[-1])
   else:info['source_pins'][b.SOURCES[0]]='0'*64
   with self.assertRaises(ValueError):b.unwrap_manifest(info,self.res)
 def test_missing_or_downgraded_main_never_pretends_to_have_a_local_budget(self):
  for mode in('missing','prior','scope'):
   info=copy.deepcopy(self.info)
   if mode=='missing':info.pop('budget_main_native_bytecode_contract')
   elif mode=='prior':info['budget_main_native_bytecode_contract']['previous_stage_contract']={}
   else:info['budget_main_native_bytecode_contract']['budget_main_contract']['owned_main_replacements']=1
   with self.assertRaises(ValueError):b.unwrap_manifest(info,self.res)
 def test_one_sided_or_downgraded_provider_stage_is_refused(self):
  for mode in('missing','downgraded'):
   info=copy.deepcopy(self.info);key=next(iter(info['grid_provider_adapters']))
   if mode=='missing':info['grid_provider_adapters'].pop(key)
   else:info['grid_provider_adapters'][key]=info['grid_provider_adapters'][key]['previous_stage_adapter']
   with self.assertRaises(ValueError):b.unwrap_manifest(info,self.res)
 def test_advertised_main_or_grid_final_hashes_are_checked_before_rollback(self):
  for key in('main','62ECC59A:00000000:DF09D526F4C77B95','62ECC59A:00000000:12272E1AC0C1F8E2'):
   info=copy.deepcopy(self.info)
   if key=='main':info['patched_resource_sha256']='0'*64
   else:info['patched_resources'][key]='0'*64
   with self.assertRaises(ValueError):b.unwrap_manifest(info,self.res)
 def mutate(self,key,name):
  raw=self.res[key];prefix,abc=binding._abc_payload(raw);a=b.ABC(abc).parse();owner=b.MAIN if key[2]==0xDF09D526F4C77B95 else b.GRID;row=b.presentation.named(a,owner,name)[1];body=abc[row['start']:row['end']];code=row['value']['code'];at=body.index(code);changed=body[:at]+code[:-1]+bytes([code[-1]^1])+body[at+len(code):];return build.replace_payload(raw,prefix+abc[:row['start']]+changed+abc[row['end']:])
 def test_recomputed_outer_hash_cannot_hide_budget_helper_cfg_changes(self):
  key=(0x62ECC59A,0,0x12272E1AC0C1F8E2);final=self.mutate(key,'ApexTxnBudgetStep');adapter=copy.deepcopy(self.info['grid_provider_adapters']['62ECC59A:00000000:12272E1AC0C1F8E2']);proof=adapter['budget_contract'];proof['final_swf_sha256']=b.sha(final);proof['abc_sha256']=b.sha(binding._abc_payload(final)[1]);adapter['patched_resource_sha256']=b.sha(final);adapter['postproof_sha256']=b.comm.contract_digest(proof)
  with self.assertRaises((ValueError,IndexError)):b.verify_adapter(adapter,final)
 def test_recomputed_outer_hash_cannot_hide_a_changed_legacy_loop(self):
  key=(0x62ECC59A,0,0x12272E1AC0C1F8E2);final=self.mutate(key,'ApexTxnStep');adapter=copy.deepcopy(self.info['grid_provider_adapters']['62ECC59A:00000000:12272E1AC0C1F8E2']);proof=adapter['budget_contract'];proof['final_swf_sha256']=b.sha(final);proof['abc_sha256']=b.sha(binding._abc_payload(final)[1]);adapter['patched_resource_sha256']=b.sha(final);adapter['postproof_sha256']=b.comm.contract_digest(proof)
  with self.assertRaises((ValueError,IndexError)):b.verify_adapter(adapter,final)
 def test_recomputed_outer_hash_cannot_hide_clock_bracket_cfg_changes(self):
  key=(0x62ECC59A,0,0xDF09D526F4C77B95);final=self.mutate(key,'ApexCatalogGridStatus');contract=copy.deepcopy(self.info['budget_main_native_bytecode_contract']);proof=contract['budget_main_contract'];proof['final_swf_sha256']=b.sha(final);proof['abc_sha256']=b.sha(binding._abc_payload(final)[1]);contract['final_swf_sha256']=b.sha(final);contract['postproof_sha256']=b.comm.contract_digest(proof)
  with self.assertRaises((ValueError,IndexError)):b.verify_contract(contract,final)
if __name__=='__main__':unittest.main()
