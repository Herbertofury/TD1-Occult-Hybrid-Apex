"""Optional exact two-provider/current-terminal rollback and corruption proofs."""
from pathlib import Path
import copy,hashlib,json,os,sys,unittest
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/dbpf_build.py').is_file())
SOURCE=Path(os.environ.get('APEX_LOGICAL_BANK_SOURCE_ROOT',H if(H/'tools/cas_grid_logical_bank.py').is_file()else R))
F=Path(os.environ['APEX_LOGICAL_BANK_FIXTURE_DIR'])if os.environ.get('APEX_LOGICAL_BANK_FIXTURE_DIR')else H/'compiled'
sys.path[:0]=[str(SOURCE/'tools'),str(R/'tools')]
import cas_grid_logical_bank as m,cas_catalog_binding as binding,cas_ui_build as ui,cas_communication_index as comm

@unittest.skipUnless((F/'adapters.json').is_file(),'Set APEX_LOGICAL_BANK_FIXTURE_DIR for exact paired compiled provider qualification')
class LogicalBankChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.adapters=json.loads((F/'adapters.json').read_text());cls.rows=[]
  for key,adapter in cls.adapters.items():
   folder=F/key.rsplit(':',1)[1];cls.rows.append((key,adapter,(folder/'final.swf').read_bytes(),(folder/'baseline.swf').read_bytes()))
  if len(cls.rows)!=2:raise ValueError('Both exact logical-bank provider fixtures required')

 def mutated(self,adapter,final,edit):
  changed=copy.deepcopy(adapter);prefix,raw=binding._abc_payload(final);a=m.mechanics.ABC(raw).parse();at,old,new=edit(a,raw)
  self.assertEqual(raw[at:at+len(old)],old);raw=raw[:at]+new+raw[at+len(old):];final=ui.replace_payload(final,prefix+raw)
  proof=changed['logical_bank_contract'];proof['final_swf_sha256']=m.sha(final);proof['abc_sha256']=m.sha(raw);changed['patched_resource_sha256']=m.sha(final);changed['postproof_sha256']=comm.contract_digest(proof)
  return changed,final

 def test_both_exact_native_position_predecessors_restore_all_original_abc_bytes(self):
  for key,adapter,final,base in self.rows:
   with self.subTest(provider=key):
    self.assertTrue(m.verify_adapter(adapter,final));prior,restored=m.historical(adapter,final)
    self.assertEqual(restored,base);self.assertEqual(prior,adapter['previous_stage_adapter']);self.assertIn('native_position_contract',prior)
    proof=adapter['logical_bank_contract'];self.assertEqual((proof['replaced_owned_bodies'],proof['appended_methods'],proof['appended_fields'],proof['changed_original_native_bodies']),(1,1,0,0))
    self.assertTrue(proof['all_unowned_bodies_retained']);self.assertTrue(proof['native_protected_bindings_verified'])

 def test_updated_outer_hash_does_not_accept_changed_normalizer_guard_cfg(self):
  for key,adapter,final,base in self.rows:
   def edit(a,raw):
    row=m.presentation.named(a,m.GRID,'ApexGridCommitLogicalBank')[1];body=row['value'];op=next(op for op in a.instructions(body['code'])if op[2]in(0x11,0x12));at=raw.index(body['code'],row['start'],row['end'])+op[0]
    return at,bytes([op[2]]),bytes([0x12 if op[2]==0x11 else 0x11])
   changed,raw=self.mutated(adapter,final,edit)
   with self.subTest(provider=key),self.assertRaisesRegex(ValueError,'semantic/CFG'):m.verify_adapter(changed,raw)

 def test_unowned_native_override_or_constructor_cannot_change_under_rehashed_outer_contract(self):
  for key,adapter,final,base in self.rows:
   def edit(a,raw):
    row=m.presentation.named(a,m.previous.GRID,'PositionCells')[1];body=row['value'];at=raw.index(body['code'],row['start'],row['end']);self.assertEqual(raw[at],0xd0)
    return at,b'\xd0',b'\xd1'
   changed,raw=self.mutated(adapter,final,edit)
   with self.subTest(provider=key),self.assertRaisesRegex(ValueError,'Original complete predecessor bytes'):m.verify_adapter(changed,raw)

 def test_new_helper_trait_cannot_gain_final_or_public_callable_authority(self):
  for key,adapter,final,base in self.rows:
   def edit(a,raw):
    trait,row=m.presentation.named(a,m.GRID,'ApexGridCommitLogicalBank');reader=m.mechanics.ABC(raw[trait['start']:trait['end']]);reader.u30();at=trait['start']+reader.at
    return at,b'\x01',b'\x11'
   changed,raw=self.mutated(adapter,final,edit)
   with self.subTest(provider=key),self.assertRaisesRegex(ValueError,'helper ABI/ownership'):m.verify_adapter(changed,raw)

 def test_missing_source_native_proof_or_rollback_inventory_never_falls_through(self):
  key,adapter,final,base=self.rows[0]
  for field in('source_sha256','native_protected_bindings_verified','whole_abc_rollback_verified','rollback'):
   changed=copy.deepcopy(adapter);del changed['logical_bank_contract'][field]
   with self.subTest(field=field),self.assertRaises(ValueError):m.verify_adapter(changed,final)
  changed=copy.deepcopy(adapter);changed['logical_bank_contract']['rollback']['bodies']={}
  with self.assertRaisesRegex(ValueError,'rollback body inventory'):m.verify_adapter(changed,final)

 def test_older_spare_or_mixed_provider_heads_cannot_be_relabeled_as_current(self):
  key,adapter,final,base=self.rows[0];changed=copy.deepcopy(adapter);changed['previous_stage_adapter']=changed['previous_stage_adapter']['previous_stage_adapter']
  with self.assertRaises(ValueError):m.verify_adapter(changed,final)
  evidence=copy.deepcopy(self.adapters);evidence[key]=evidence[key]['previous_stage_adapter']
  resources={tuple(int(v,16)for v in name.split(':')):data for name,row,data,old in self.rows}
  with self.assertRaisesRegex(ValueError,'absent/downgraded'):m.unwrap_providers(evidence,resources)

 def test_provider_only_manifest_rollback_preserves_main_and_unknown_fields(self):
  import dbpf_build as dbpf,maru_companion as maru
  resources={tuple(int(v,16)for v in name.split(':')):data for name,row,data,old in self.rows};resources[maru.CUSTOMIZER]=b'unmodified-main-sentinel'
  donor=dbpf.tgi(maru.GRID_LIBRARY);info={'source_pins':m.pins(),'grid_provider_adapters':copy.deepcopy(self.adapters),'companion_code_merge':{'grid_library_adapter':copy.deepcopy(self.adapters[donor])},
    'patched_resources':{name:m.sha(data)for name,row,data,old in self.rows},'patched_resource_sha256':m.sha(resources[maru.CUSTOMIZER]),'unknown_future_metadata':{'keep':[0,'all fields',False]}}
  before=copy.deepcopy(info);out,rolled=m.unwrap_manifest(info,resources)
  self.assertEqual(info,before);self.assertEqual(rolled[maru.CUSTOMIZER],resources[maru.CUSTOMIZER]);self.assertEqual(out['patched_resource_sha256'],info['patched_resource_sha256']);self.assertEqual(out['unknown_future_metadata'],info['unknown_future_metadata'])
  for key,adapter,final,base in self.rows:self.assertEqual(rolled[tuple(int(v,16)for v in key.split(':'))],base)

if __name__=='__main__':unittest.main()
