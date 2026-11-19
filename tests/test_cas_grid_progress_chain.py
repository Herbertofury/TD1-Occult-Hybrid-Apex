from pathlib import Path
import copy,hashlib,importlib.util,json,sys,types,unittest,os
HOME=Path(__file__).resolve().parents[1];ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tools/cas_grid_transaction.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import cas_catalog_binding as binding,cas_grid_product_rows as rows,cas_ui_build as ui,dbpf_build,cas_communication_index as comm
spec=importlib.util.spec_from_file_location('cas_grid_progress',HOME/'tools/cas_grid_progress.py');s=importlib.util.module_from_spec(spec);sys.modules[spec.name]=s;spec.loader.exec_module(s)
class ChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.fixture=Path(os.environ.get("APEX_CAS_GRID_PROGRESS_FIXTURE",str(HOME/"compiled")))
  if not (cls.fixture/"proofs.json").is_file():raise unittest.SkipTest("Authenticated FFDec provider fixtures require APEX_CAS_GRID_PROGRESS_FIXTURE")
  cls.entries=[]
  for suffix in ('12272E1AC0C1F8E2','89D13757C58C2E05'):
   w=cls.fixture/suffix;final=(w/'final.swf').read_bytes();adapter=json.loads((w/'adapter.json').read_text());cls.entries.append((suffix,adapter,final,(w/'baseline.swf').read_bytes()))
 def test_both_actual_v343_providers_exact_native_source_previous_chain_and_complete_rollback(self):
  for suffix,a,final,base in self.entries:
   with self.subTest(suffix=suffix):self.assertTrue(s.verify_adapter(a,final));self.assertEqual(s.reconstruct(final,a['progress_contract']),base);self.assertTrue(rows.verify_adapter(a['previous_stage_adapter'],base))
 def test_missing_partial_stale_source_pins_refuse(self):
  for value in (None,{},dict(list(s.pins().items())[:-1]),{**s.pins(),s.SOURCES[0]:'0'*64}):
   a=copy.deepcopy(self.entries[0][1]);a['progress_contract']['source_sha256']=value
   with self.subTest(value=value),self.assertRaises(ValueError):s.chain_adapter(a['previous_stage_adapter'],a['progress_contract'],self.entries[0][2])
 def test_all_proof_truths_counts_and_runtime_claims_are_strict(self):
  a=self.entries[0][1];final=self.entries[0][2]
  for key,bad in [('whole_abc_rollback_verified',False),('serialized_owned_bodies_verified',None),('all_unowned_bodies_retained',1),('replaced_owned_bodies',True),('appended_methods',1),('changed_original_native_bodies',1),('runtime_qualified',True),('hitch_free_claimed',True)]:
   proof=copy.deepcopy(a['progress_contract']);proof[key]=bad
   with self.subTest(key=key),self.assertRaises(ValueError):s.chain_adapter(a['previous_stage_adapter'],proof,final)
 def test_corrupt_actual_step_code_refuses_even_with_updated_output_hashes(self):
  _,a,final,_=self.entries[0];prefix,raw=binding._abc_payload(final);parser=s.previous.previous.ABC(raw).parse();row=s.previous.previous.named(parser,s.GRID,'ApexTxnStep')[1];code=row['value']['code'];at=raw.index(code,row['start'],row['end']);changed=raw[:at]+bytes([raw[at]^1])+raw[at+1:];mutated=ui.replace_payload(final,prefix+changed);proof=copy.deepcopy(a['progress_contract']);proof['final_swf_sha256']=s.sha(mutated);proof['abc_sha256']=s.sha(changed)
  with self.assertRaises(ValueError):s.chain_adapter(a['previous_stage_adapter'],proof,mutated)
 def test_previous_native_or_unowned_body_cannot_be_relabelled(self):
  _,a,final,_=self.entries[0];prefix,raw=binding._abc_payload(final);parser=s.previous.previous.ABC(raw).parse();row=s.previous.previous.named(parser,s.GRID,'ApexGridNow')[1];code=row['value']['code'];at=raw.index(code,row['start'],row['end']);changed=raw[:at]+bytes([raw[at]^1])+raw[at+1:];mutated=ui.replace_payload(final,prefix+changed);proof=copy.deepcopy(a['progress_contract']);proof['final_swf_sha256']=s.sha(mutated);proof['abc_sha256']=s.sha(changed)
  with self.assertRaises(ValueError):s.chain_adapter(a['previous_stage_adapter'],proof,mutated)
 def test_missing_rollback_body_and_fake_pool_counts_refuse(self):
  _,a,final,_=self.entries[0]
  for change in (lambda p:p['rollback']['bodies'].clear(),lambda p:p['rollback']['pool_counts'].__setitem__(0,True),lambda p:p['rollback']['pool_counts'].__setitem__(6,999999)):
   proof=copy.deepcopy(a['progress_contract']);change(proof)
   with self.assertRaises(ValueError):s.chain_adapter(a['previous_stage_adapter'],proof,final)
 def test_complete_combined_manifest_verifier_accepts_progress_and_rejects_downgrade(self):
  manifest=json.loads((self.fixture/'actual-manifest.json').read_text());package=(self.fixture/'actual-package.package').read_bytes();self.assertEqual(dbpf_build.digest(package),manifest['sha256']);resources=dbpf_build.read(package)
  m=types.ModuleType('progress_maru');m.__file__=str(ROOT/'tools/maru_companion.py');verifier=HOME/'maru_companion-patched.py';verifier=verifier if verifier.is_file() else Path(m.__file__);exec(compile(verifier.read_text(),m.__file__,'exec'),m.__dict__)
  # Current native provider proof is wrapped once, while Main/Selector/all
  # other resources are the untouched actual V343 candidate.
  updated=copy.deepcopy(manifest);updated['source_pins'].update(s.pins())
  for suffix,a,final,_ in self.entries:
   key=(0x62ECC59A,0,int(suffix,16));tgi=dbpf_build.tgi(key);resources[key]=final;updated['grid_provider_adapters'][tgi]=a;updated['patched_resources'][tgi]=s.sha(final)
  donor='62ECC59A:00000000:89D13757C58C2E05';updated['companion_code_merge']['grid_library_adapter']=updated['grid_provider_adapters'][donor]
  self.assertTrue(m.verify_merged(updated,resources))
  downgraded=copy.deepcopy(updated);downgraded['grid_provider_adapters'][donor]=downgraded['grid_provider_adapters'][donor]['previous_stage_adapter']
  with self.assertRaises(ValueError):m.verify_merged(downgraded,resources)
if __name__=='__main__':unittest.main()
