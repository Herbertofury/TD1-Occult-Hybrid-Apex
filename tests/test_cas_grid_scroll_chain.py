"""Optional actual compiled resources plus portable source/cache admission gates."""
from pathlib import Path
import os,sys,json,copy,unittest,ast
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_progress.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools')]
import cas_grid_scroll as scroll,cas_grid_slice as slice,cas_catalog_binding as binding,cas_ui_build as build
import cas_grid_budget as budget,cas_grid_featured as featured
BUILD=Path(os.environ.get('APEX_CAS_GRID_SCROLL_BUILD_SOURCE',ROOT/'tools/cas_ui_build.py'))
class IntegrationSourceTests(unittest.TestCase):
 def test_cache_prefix_requires_all_current_layers_before_any_resource_return(self):
  source=BUILD.read_text();node=ast.parse(source);function=next(n for n in node.body if isinstance(n,ast.FunctionDef)and n.name=='verified_library_cache');checker=next(n for n in ast.walk(function)if isinstance(n,ast.FunctionDef)and n.name=='current_grid_stages');loop=next(n for n in ast.walk(checker)if isinstance(n,ast.For));self.assertEqual(ast.literal_eval(loop.iter),('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract'))
  self.assertIn('not current_grid_stages(providers.get(dbpf_build.tgi(key)))',ast.get_source_segment(source,function));self.assertIn('maru_companion.verify_grid_providers',ast.get_source_segment(source,function))
 def test_every_new_source_is_in_builder_exact_pin_inventory(self):
  node=ast.parse(BUILD.read_text());assignment=next(n for n in node.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets));self.assertTrue(set(scroll.SOURCES+slice.SOURCES)<=set(ast.literal_eval(assignment.value)))
 def test_provider_build_order_is_swatch_scroll_slice(self):
  tree=ast.parse(BUILD.read_text());provider=next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name=='adapt_grid_provider')
  calls={n.func.value.id:n.lineno for n in ast.walk(provider)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='adapt'and isinstance(n.func.value,ast.Name)and n.func.value.id in('cas_swatch_provider','cas_grid_scroll','cas_grid_slice')}
  terminal=max(n.lineno for n in ast.walk(provider)if isinstance(n,ast.Return)and isinstance(n.value,ast.Call)and isinstance(n.value.func,ast.Name)and n.value.func.id=='finish_grid_provider')
  self.assertLess(calls['cas_swatch_provider'],calls['cas_grid_scroll']);self.assertLess(calls['cas_grid_scroll'],calls['cas_grid_slice']);self.assertLess(calls['cas_grid_slice'],terminal)
  finish=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='finish_grid_provider')
  intrinsic=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_finish_grid_provider_intrinsic')
  physical=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_finish_grid_provider_physical')
  imports={a.name for helper in(finish,intrinsic,physical)for n in ast.walk(helper)if isinstance(n,ast.Import)for a in n.names}
  self.assertTrue({'cas_grid_featured','cas_grid_budget','cas_grid_slice','cas_grid_publication','cas_grid_staging_attach','cas_swatch_columns','cas_grid_row_delta','cas_grid_physical','cas_grid_intrinsic','cas_grid_spares'}<=imports)

FIXTURE=Path(os.environ['APEX_CAS_GRID_SCROLL_FIXTURE'])if os.environ.get('APEX_CAS_GRID_SCROLL_FIXTURE')else None
@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_GRID_SCROLL_FIXTURE for optional authenticated compiled resources')
class CompiledChainTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.info=json.loads((FIXTURE/'info.json').read_text());cls.resources={tuple(int(n,16)for n in k.split(':')):bytes.fromhex(v)for k,v in json.loads((FIXTURE/'resource-map.json').read_text()).items()}
 def slice_fixture(self):
  info,resources=self.info,self.resources
  # Authenticate the exact newer heads before constructing an explicit Slice
  # fixture. Their complete bytes, unique source pins and envelopes move back
  # together; no hash is repinned and a partial/forged head cannot be skipped.
  from cas_main_chain_fixtures import unwrap_catalog_heads
  info,resources=unwrap_catalog_heads(info,resources,stop_before='cas_grid_slice')
  return info,resources
 def test_complete_provider_and_main_chain_passes_and_restores_exact_previous_layers(self):
  info,res=self.slice_fixture();info,res=slice.unwrap_manifest(info,res);info,res=scroll.unwrap_manifest(info,res);self.assertTrue(all('swatch_provider_contract'in a for a in info['grid_provider_adapters'].values()));self.assertEqual(scroll.sha(res[(0x62ECC59A,0,0xDF09D526F4C77B95)]),info['preview_transition_native_bytecode_contract']['final_swf_sha256'])
 def test_missing_partial_stale_slice_source_pins_refuse(self):
  for mode in('missing','partial','stale'):
   original,resources=self.slice_fixture();info=copy.deepcopy(original)
   if mode=='missing':info['source_pins']={k:v for k,v in info['source_pins'].items()if k not in slice.SOURCES}
   elif mode=='partial':info['source_pins'].pop(slice.SOURCES[-1])
   else:info['source_pins'][slice.SOURCES[0]]='0'*64
   with self.assertRaises(ValueError):slice.unwrap_manifest(info,resources)
 def test_missing_or_downgraded_provider_never_admits_one_sided_stage(self):
  for mode in('missing','downgraded'):
   original,resources=self.slice_fixture();info=copy.deepcopy(original);name=next(iter(info['grid_provider_adapters']))
   if mode=='missing':info['grid_provider_adapters'].pop(name)
   else:info['grid_provider_adapters'][name]=info['grid_provider_adapters'][name]['previous_stage_adapter']
   with self.assertRaises(ValueError):slice.unwrap_manifest(info,resources)
 def test_missing_main_and_advertised_main_mismatch_refuse_before_rollback(self):
  info,res=self.slice_fixture();info,res=slice.unwrap_manifest(info,res)
  for mode in('missing','top_hash','map_hash','prior'):
   bad=copy.deepcopy(info)
   if mode=='missing':bad.pop('scroll_main_native_bytecode_contract')
   elif mode=='top_hash':bad['patched_resource_sha256']='0'*64
   elif mode=='map_hash':bad['patched_resources']['62ECC59A:00000000:DF09D526F4C77B95']='0'*64
   else:bad['scroll_main_native_bytecode_contract']['previous_stage_contract']={}
   with self.assertRaises(ValueError):scroll.unwrap_manifest(bad,res)
 def test_advertised_grid_hash_cannot_be_hidden_by_unwrap(self):
  original,resources=self.slice_fixture();info=copy.deepcopy(original);info['patched_resources']['62ECC59A:00000000:12272E1AC0C1F8E2']='0'*64
  with self.assertRaises(ValueError):slice.unwrap_manifest(info,resources)
 def test_recomputed_outer_hash_does_not_hide_owned_step_cfg_mutation(self):
  info,resources=self.slice_fixture();key=(0x62ECC59A,0,0x12272E1AC0C1F8E2);final=resources[key];prefix,raw=binding._abc_payload(final);a=scroll.ABC(raw).parse();row=scroll.presentation.named(a,scroll.GRID,'ApexTxnStep')[1];code=row['value']['code'];old=raw[row['start']:row['end']];at=old.index(code);changed=old[:at]+code[:-1]+bytes([code[-1]^1])+old[at+len(code):];final=build.replace_payload(final,prefix+raw[:row['start']]+changed+raw[row['end']:]);adapter=copy.deepcopy(info['grid_provider_adapters']['62ECC59A:00000000:12272E1AC0C1F8E2']);proof=adapter['slice_contract'];proof['final_swf_sha256']=scroll.sha(final);proof['abc_sha256']=scroll.sha(binding._abc_payload(final)[1]);adapter['patched_resource_sha256']=scroll.sha(final);adapter['postproof_sha256']=scroll.comm.contract_digest(proof)
  with self.assertRaises(ValueError):slice.verify_adapter(adapter,final)
if __name__=='__main__':unittest.main()
