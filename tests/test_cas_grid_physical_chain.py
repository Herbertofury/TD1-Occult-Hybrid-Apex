from pathlib import Path
import sys,json,copy,unittest,os
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'));H=Path(os.environ['APEX_CAS_GRID_PHYSICAL_FIXTURE'])if os.environ.get('APEX_CAS_GRID_PHYSICAL_FIXTURE')else None
import cas_grid_physical as s,dbpf_build as dbpf,maru_companion as maru

@unittest.skipUnless(H is not None,'Explicit authenticated Physical provider fixtures required')
class ChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(c):
  c.a=json.loads((H/'adapters.json').read_text());c.r={tuple(int(n,16)for n in k.split(':')):(H/k.rsplit(':',1)[1]/'final.swf').read_bytes()for k in c.a}
 def test_both_actual_providers_recursively_reconstruct_exact_incoming_current_bytes(self):
  for n,a in self.a.items():
   raw=self.r[tuple(int(v,16)for v in n.split(':'))];self.assertTrue(s.verify_adapter(a,raw));prior,old=s.historical(a,raw);self.assertTrue(s.previous.verify_adapter(prior,old));self.assertEqual(old,(H/n.rsplit(':',1)[1]/'baseline.swf').read_bytes())
 def test_missing_false_typed_bad_count_source_and_rollback_refuse_even_rehashed(self):
  for key,a in self.a.items():
   raw=self.r[tuple(int(v,16)for v in key.split(':'))]
   for mutate in [lambda p:p.pop('source_sha256'),lambda p:p['source_sha256'].pop(s.SOURCES[0]),lambda p:p.update(whole_abc_rollback_verified=False),lambda p:p.update(appended_methods=True),lambda p:p.update(replaced_owned_bodies=8),lambda p:p['rollback']['bodies'].pop('ApexGridDeltaBorrow'),lambda p:p['rollback'].update(pool_counts=[True]*7)]:
    bad=copy.deepcopy(a);mutate(bad['physical_position_contract']);bad['postproof_sha256']=s.comm.contract_digest(bad['physical_position_contract'])
    with self.assertRaises(ValueError):s.verify_adapter(bad,raw)
 def test_foreign_predecessor_or_one_changed_native_byte_cannot_be_relabelled(self):
  names=list(self.a)
  for index,key in enumerate(names):
   bad=copy.deepcopy(self.a[key]);raw=self.r[tuple(int(v,16)for v in key.split(':'))];bad['previous_stage_adapter']=copy.deepcopy(self.a[names[1-index]]['previous_stage_adapter']);bad['previous_stage_sha256']=s.comm.contract_digest(bad['previous_stage_adapter']);bad['physical_position_contract']['previous_stage_sha256']=bad['previous_stage_sha256'];bad['postproof_sha256']=s.comm.contract_digest(bad['physical_position_contract'])
   with self.assertRaises(ValueError):s.verify_adapter(bad,raw)
   with self.assertRaises(ValueError):s.verify_adapter(self.a[key],raw+b'x')
 def test_paired_provider_refuses_missing_or_partial_terminal_without_mutating_input(self):
  for missing in list(self.a):
   bad=copy.deepcopy(self.a);bad[missing]=bad[missing]['previous_stage_adapter'];before=copy.deepcopy(bad)
   with self.assertRaises(ValueError):s.unwrap_providers(bad,self.r)
   self.assertEqual(before,bad)
 def test_manifest_refuses_missing_source_advertised_bytes_or_foreign_donor_alias(self):
  info={'source_pins':s.pins(),'grid_provider_adapters':copy.deepcopy(self.a),'patched_resources':{k:s.sha(self.r[tuple(int(n,16)for n in k.split(':'))])for k in self.a},'companion_code_merge':{'grid_library_adapter':copy.deepcopy(self.a[dbpf.tgi(maru.GRID_LIBRARY)])}}
  old,rolled=s.unwrap_manifest(info,self.r);self.assertNotEqual(old['grid_provider_adapters'],self.a)
  for mutate in [lambda i:i['source_pins'].pop(s.SOURCES[0]),lambda i:i['patched_resources'].update({next(iter(self.a)):'0'*64}),lambda i:i['companion_code_merge'].update(grid_library_adapter={})]:
   bad=copy.deepcopy(info);mutate(bad);before=copy.deepcopy(bad)
   with self.assertRaises(ValueError):s.unwrap_manifest(bad,self.r)
   self.assertEqual(bad,before)
 def test_rehashed_owned_or_unowned_code_mutation_still_fails_semantics_or_full_rollback(self):
  from cas_ui_build import replace_payload
  for name in ('ApexGridDeltaBorrow','ApexGridDeltaTexture'):
   key=next(iter(self.a));raw=self.r[tuple(int(v,16)for v in key.split(':'))];bad=copy.deepcopy(self.a[key])
   prefix,abcraw=s.binding._abc_payload(raw);a=s.mechanics.ABC(abcraw).parse();body=s.presentation.named(a,s.GRID,name)[1]['value']['code'];code=bytearray(body)
   at=next(start for start,end,op,args in a.instructions(body)if op==0x27);code[at]=0x26;self.assertEqual(abcraw.count(body),1)
   modified=abcraw.replace(body,bytes(code),1);changed=replace_payload(raw,prefix+modified);proof=bad['physical_position_contract']
   proof.update(final_swf_sha256=s.sha(changed),abc_sha256=s.sha(modified));bad['patched_resource_sha256']=s.sha(changed);bad['postproof_sha256']=s.comm.contract_digest(proof)
   with self.assertRaises(ValueError):s.verify_adapter(bad,changed)

if __name__=='__main__':unittest.main()
