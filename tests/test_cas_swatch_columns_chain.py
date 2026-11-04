"""Authenticate actual compiled swatch helpers/native graft and every predecessor."""
from pathlib import Path
import copy,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_featured.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools')]
import cas_swatch_columns as s
import cas_ui_build as build
FIXTURE=Path(os.environ['APEX_CAS_SWATCH_COLUMNS_FIXTURE'])if os.environ.get('APEX_CAS_SWATCH_COLUMNS_FIXTURE')else None

@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_SWATCH_COLUMNS_FIXTURE for exact compiled resources')
class CompiledSwatchColumnsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.adapters=json.loads((FIXTURE/'adapters.json').read_text());cls.main=json.loads((FIXTURE/'main-contract.json').read_text());cls.key='62ECC59A:00000000:89D13757C58C2E05'
 def data(self,key=None):return(FIXTURE/(key or self.key).rsplit(':',1)[1]/'final.swf').read_bytes()
 def reseal(self,adapter,final):
  proof=adapter['swatch_columns_contract'];proof.update(final_swf_sha256=s.sha(final),abc_sha256=s.sha(s.binding._abc_payload(final)[1]));adapter.update(patched_resource_sha256=s.sha(final),postproof_sha256=s.comm.contract_digest(proof));return adapter
 def mutate_code(self,final,name,change):
  prefix,raw=s.binding._abc_payload(final);a=s.ABC(raw).parse();row=s.presentation.named(a,s.TYPE,name)[1];body=raw[row['start']:row['end']];made=s.replace_code(body,change(a,row['value']['code']))
  return build.replace_payload(final,prefix+raw[:row['start']]+made+raw[row['end']:])
 def test_both_provider_bytes_and_full_history_restore_exactly(self):
  for key,adapter in self.adapters.items():
   final=self.data(key);self.assertTrue(s.verify_adapter(adapter,final));prior,old=s.historical(adapter,final);self.assertEqual(old,(FIXTURE/key.rsplit(':',1)[1]/'baseline.swf').read_bytes());self.assertTrue(s.predecessor(prior)[1](prior,old))
 def test_main_complete_raw_rollback_and_separate_scope_pin(self):
  final=(FIXTURE/'main/final.swf').read_bytes();self.assertTrue(s.verify_main(self.main,final));old=s.reconstruct(final,self.main['swatch_columns_main_contract']);self.assertEqual(old,(FIXTURE/'main/baseline.swf').read_bytes());self.assertTrue(s.predecessor(self.main['previous_stage_contract'],True)[1](self.main['previous_stage_contract'],old))
 def test_missing_metadata_or_rehashed_counts_authority_and_raw_rollback_refuse(self):
  final=self.data()
  for case in('pin','native','counts','authority','rollback','previous','source'):
   adapter=copy.deepcopy(self.adapters[self.key]);p=adapter['swatch_columns_contract']
   if case=='pin':p['source_sha256'].pop(s.SOURCES[-1])
   elif case=='native':p['native_body']=None
   elif case=='counts':p['changed_original_native_bodies']=0
   elif case=='authority':p['previous_stage_kind']='publication'
   elif case=='rollback':p['rollback']['bodies']={}
   elif case=='previous':adapter['previous_stage_adapter']={};p['previous_stage_sha256']=s.comm.contract_digest({});adapter['previous_stage_sha256']=p['previous_stage_sha256']
   else:p['source_sha256'][s.SOURCES[0]]='0'*64
   adapter['postproof_sha256']=s.comm.contract_digest(p)
   with self.assertRaises(ValueError,msg=case):s.verify_adapter(adapter,final)
 def test_rehashed_native_branch_and_selector_call_operands_refuse(self):
  final=self.data()
  def branch(a,code):
   row=next(r for r in a.instructions(code)if 0x0c<=r[2]<=0x1a);changed=bytearray(code);changed[row[0]+1]^=1;return bytes(changed)
  def call(a,code):
   row=next(r for r in a.instructions(code)if r[2]==0x46 and a.string(a.pool(6,r[3][0])['name'])==s.SELECTOR);changed=bytearray(code);changed[row[1]-1]=0;return bytes(changed)
  for change in(branch,call):
   bad=self.mutate_code(final,s.NATIVE,change);adapter=self.reseal(copy.deepcopy(self.adapters[self.key]),bad)
   with self.assertRaises(ValueError):s.verify_adapter(adapter,bad)
 def test_rehashed_owned_selector_policy_change_refuses(self):
  def mutation(a,code):
   row=next(r for r in a.instructions(code)if r[2]==0x24 and r[3]==[32]);changed=bytearray(code);changed[row[0]+1]=33;return bytes(changed)
  final=self.mutate_code(self.data(),s.SELECTOR,mutation);adapter=self.reseal(copy.deepcopy(self.adapters[self.key]),final)
  with self.assertRaises(ValueError):s.verify_adapter(adapter,final)
 def test_rehashed_selector_method_signature_change_refuses(self):
  prefix,raw=s.binding._abc_payload(self.data());a=s.ABC(raw).parse();_,row=s.presentation.named(a,s.TYPE,s.SELECTOR);info=a.methods['rows'][row['value']['method']];changed=bytearray(raw);reader=s.ABC(raw);reader.at=info['start'];self.assertEqual(reader.u30(),1);changed[reader.at]=0
  final=build.replace_payload(self.data(),prefix+bytes(changed));adapter=self.reseal(copy.deepcopy(self.adapters[self.key]),final)
  with self.assertRaises(ValueError):s.verify_adapter(adapter,final)
 def test_rehashed_native_preimage_mutation_refuses(self):
  final=self.data();adapter=copy.deepcopy(self.adapters[self.key]);p=adapter['swatch_columns_contract'];native=bytearray.fromhex(p['native_body']);native[-1]^=1;p['native_body']=native.hex();adapter['postproof_sha256']=s.comm.contract_digest(p)
  with self.assertRaises(ValueError):s.verify_adapter(adapter,final)
 def test_wrong_main_scope_semantics_cannot_use_donor_pins(self):
  final=(FIXTURE/'main/final.swf').read_bytes();a=s.ABC(s.binding._abc_payload(final)[1]).parse();donor=s.ABC(s.binding._abc_payload(self.data())[1]).parse();self.assertNotEqual(s.semantics(a),s.semantics(donor))
 def test_historical_featured_fixture_cannot_authorize_current_unwrap(self):
  if next(iter(self.adapters.values()))['swatch_columns_contract']['previous_stage_kind']!='featured-fixture':self.skipTest('Current production-stage fixture')
  resources={tuple(int(n,16)for n in k.split(':')):self.data(k)for k in self.adapters}
  with self.assertRaises(ValueError):s.unwrap_providers(self.adapters,resources)

if __name__=='__main__':unittest.main()
