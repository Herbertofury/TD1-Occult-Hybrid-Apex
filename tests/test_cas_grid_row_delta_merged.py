"""Current full package gate and fail-closed merged-manifest admission."""
from pathlib import Path
import copy,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/dbpf_build.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools')]
import cas_grid_row_delta as c,cas_ui_build as build,maru_companion as maru,dbpf_build
FIXTURE=Path(os.environ['APEX_CAS_ROW_DELTA_MERGED_FIXTURE'])if os.environ.get('APEX_CAS_ROW_DELTA_MERGED_FIXTURE')else None
@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_ROW_DELTA_MERGED_FIXTURE for authenticated current merged resources')
class MergedTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.info=json.loads((FIXTURE/'info.json').read_text());cls.resources=dbpf_build.read((FIXTURE/'ApexCASBridge.package').read_bytes())
 def test_current_full_merged_chain_and_complete_source_pin_gate(self):
  self.assertTrue(build.verify_source_pins(self.info));self.assertTrue(maru.verify_merged(self.info,self.resources))
 def test_missing_partial_stale_and_absent_all_current_tool_pins_refuse(self):
  for mode in('missing','partial','stale','all'):
   bad=copy.deepcopy(self.info)
   if mode=='missing':bad.pop('source_pins')
   elif mode=='partial':bad['source_pins'].pop(c.SOURCES[-1])
   elif mode=='stale':bad['source_pins'][c.SOURCES[0]]='0'*64
   else:
    for key in c.SOURCES:bad['source_pins'].pop(key)
   with self.assertRaises(ValueError):c.unwrap_manifest(bad,self.resources)
 def test_missing_main_or_downgraded_terminal_cannot_skip_current_stage(self):
  for mode in('main','providers','all-markers'):
   bad=copy.deepcopy(self.info)
   if mode in('main','all-markers'):bad.pop('row_delta_main_native_bytecode_contract')
   if mode in('providers','all-markers'):bad['grid_provider_adapters']={n:a['previous_stage_adapter']for n,a in bad['grid_provider_adapters'].items()}
   with self.assertRaises(ValueError):c.unwrap_manifest(bad,self.resources)
 def test_both_main_advertised_hashes_are_bound_to_actual_bytes(self):
  key=dbpf_build.tgi(maru.CUSTOMIZER)
  for mode in('top','resource'):
   bad=copy.deepcopy(self.info)
   if mode=='top':bad['patched_resource_sha256']='0'*64
   else:bad['patched_resources'][key]='0'*64
   with self.assertRaisesRegex(ValueError,'Advertised'):c.unwrap_manifest(bad,self.resources)
 def test_exact_main_skin_predecessor_is_required_without_adoption(self):
  bad=copy.deepcopy(self.info);bad['swatch_columns_main_native_bytecode_contract']={}
  with self.assertRaisesRegex(ValueError,'predecessor'):c.unwrap_manifest(bad,self.resources)
 def test_provider_pair_is_atomic_and_mixed_or_single_provider_refuses(self):
  evidence=self.info['grid_provider_adapters'];names=list(evidence)
  for kind in('missing','mixed'):
   bad=copy.deepcopy(evidence)
   if kind=='missing':bad.pop(names[0])
   else:bad[names[0]]=bad[names[0]]['previous_stage_adapter']
   with self.assertRaises(ValueError):c.unwrap_providers(bad,self.resources)

if __name__=='__main__':unittest.main()
