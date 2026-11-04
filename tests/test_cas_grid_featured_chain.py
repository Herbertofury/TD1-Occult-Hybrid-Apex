"""Private actual compiled bytes: strict complete history and raw rollback."""
from pathlib import Path
import copy,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_budget.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools')]
import cas_grid_featured as f
import cas_ui_build as build
import os
FIXTURE=Path(os.environ['APEX_CAS_GRID_FEATURED_FIXTURE'])if os.environ.get('APEX_CAS_GRID_FEATURED_FIXTURE')else None

@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_GRID_FEATURED_FIXTURE for authenticated actual compiled resources')

class CompiledFeaturedTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.adapters=json.loads((FIXTURE/'adapters.json').read_text())
  cls.main=json.loads((FIXTURE/'main-contract.json').read_text())
 def test_both_provider_chains_restore_exact_prior_swf_bytes(self):
  for key,adapter in self.adapters.items():
   folder=FIXTURE/key.rsplit(':',1)[1];final=(folder/'final.swf').read_bytes()
   self.assertTrue(f.verify_adapter(adapter,final));prior,raw=f.historical(adapter,final)
   self.assertEqual(raw,(folder/'baseline.swf').read_bytes());self.assertTrue(f.previous.verify_adapter(prior,raw))
 def test_main_exact_rollback_preserves_all_original_featured_draw_click_and_feeds(self):
  final=(FIXTURE/'main/final.swf').read_bytes();self.assertTrue(f.verify_main(self.main,final))
  raw=f.reconstruct(final,self.main['featured_main_contract']['rollback'],f.MAIN)
  self.assertEqual(raw,(FIXTURE/'main/baseline.swf').read_bytes())
  self.assertTrue(f.previous.verify_contract(self.main['previous_stage_contract'],raw))
 def test_missing_pin_prior_or_required_guarantee_cannot_be_rehashed_into_admission(self):
  key=next(iter(self.adapters));final=(FIXTURE/key.rsplit(':',1)[1]/'final.swf').read_bytes()
  for mode in ('pin','previous','rollback','native_changes','source_stale'):
   adapter=copy.deepcopy(self.adapters[key]);proof=adapter['featured_contract']
   if mode=='pin':proof['source_sha256'].pop(f.SOURCES[-1])
   elif mode=='previous':adapter['previous_stage_adapter']={};proof['previous_stage_sha256']=f.comm.contract_digest({});adapter['previous_stage_sha256']=proof['previous_stage_sha256']
   elif mode=='rollback':proof['rollback']['bodies'].pop(f.REPLACED[-1])
   elif mode=='native_changes':proof['changed_original_native_bodies']=1
   else:proof['source_sha256'][f.SOURCES[0]]='0'*64
   adapter['postproof_sha256']=f.comm.contract_digest(proof)
   with self.assertRaises(ValueError,msg=mode):f.verify_adapter(adapter,final)
 def mutate(self,final,owner,name):
  prefix,raw=f.binding._abc_payload(final);a=f.scroll.ABC(raw).parse();row=f.presentation.named(a,owner,name)[1]
  code=row['value']['code'];old=raw[row['start']:row['end']];at=old.index(code)
  self.assertIn(code[-1],(0x47,0x48));changed=code[:-1]+bytes([0x47 if code[-1]==0x48 else 0x48])
  changed=old[:at]+changed+old[at+len(code):]
  return build.replace_payload(final,prefix+raw[:row['start']]+changed+raw[row['end']:])
 def test_rehashed_owned_helper_cfg_change_still_refuses(self):
  key=next(iter(self.adapters));adapter=copy.deepcopy(self.adapters[key]);folder=FIXTURE/key.rsplit(':',1)[1]
  final=self.mutate((folder/'final.swf').read_bytes(),f.GRID,'ApexGridFeaturedSame');proof=adapter['featured_contract']
  proof['final_swf_sha256']=f.sha(final);proof['abc_sha256']=f.sha(f.binding._abc_payload(final)[1]);adapter['patched_resource_sha256']=f.sha(final);adapter['postproof_sha256']=f.comm.contract_digest(proof)
  with self.assertRaises(ValueError):f.verify_adapter(adapter,final)
 def test_rehashed_original_native_draw_change_still_refuses(self):
  contract=copy.deepcopy(self.main);final=self.mutate((FIXTURE/'main/final.swf').read_bytes(),'widgets.CAS.controls.CASFeaturedFacelookCellView','Draw')
  proof=contract['featured_main_contract'];proof['final_swf_sha256']=f.sha(final);proof['abc_sha256']=f.sha(f.binding._abc_payload(final)[1]);contract['final_swf_sha256']=f.sha(final);contract['postproof_sha256']=f.comm.contract_digest(proof)
  with self.assertRaises(ValueError):f.verify_main(contract,final)
 def test_main_malformed_pool_prefix_or_partial_rollback_refuses(self):
  final=(FIXTURE/'main/final.swf').read_bytes()
  for mode in ('scope','missing_body','missing_pin'):
   contract=copy.deepcopy(self.main);proof=contract['featured_main_contract']
   if mode=='scope':proof['rollback']['pool_counts'][0]=0
   elif mode=='missing_body':proof['rollback']['bodies'].pop(f.MAIN_REPLACED[0])
   else:proof['source_sha256'].pop(f.SOURCES[-1])
   contract['postproof_sha256']=f.comm.contract_digest(proof)
   with self.assertRaises(ValueError,msg=mode):f.verify_main(contract,final)

if __name__=='__main__':unittest.main()
