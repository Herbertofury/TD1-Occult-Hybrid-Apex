"""Execute the current native PositionCells terminal through the actual builder."""
from pathlib import Path
import ast,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import test_cas_grid_budget_cache as harness
class PositionBuilderTests(unittest.TestCase):
 def cached(self,*args,**kwargs):return harness.CacheTests('runTest').cached(*args,**kwargs)
 def test_exact_native_position_prefix_is_verified_before_new_successors(self):
  result,calls,cache,prior,key=self.cached('position');self.assertEqual([name for name,_ in calls],['cas_grid_position.verify','cas_grid_logical_bank.adapt','cas_grid_frame_status.adapt','cas_grid_eof.adapt','cas_grid_width.adapt']);self.assertEqual(result[0],b'cas_grid_width');self.assertIn('view_width_transfer_contract',result[1]);self.assertIn('eof_delta_contract',result[1]['previous_stage_adapter']);self.assertIn('continued',cache)
 def test_spare_prefix_must_compile_new_native_stage_and_transfer_exact_prior_bytes(self):
  result,calls,cache,prior,key=self.cached('spares');self.assertEqual([name for name,_ in calls],['cas_grid_spares.verify','cas_grid_position.adapt','cas_grid_logical_bank.adapt','cas_grid_frame_status.adapt','cas_grid_eof.adapt','cas_grid_width.adapt']);self.assertEqual(calls[1][1][:2],(prior,b'cached'));self.assertEqual(result[0],b'cas_grid_width');self.assertIn('native_position_contract',result[1]['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']);self.assertIs(result[1]['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter'],prior);self.assertIn('continued',cache)
 def test_corrupt_current_or_failed_new_compiler_cannot_return_old_bytes(self):
  for prefix,refuse in [('position','cas_grid_position.verify'),('spares','cas_grid_position.adapt')]:
   with self.subTest(prefix=prefix):
    result,calls,*_=self.cached(prefix,refuse);self.assertIsNone(result);self.assertEqual(calls[-1][0],refuse)
 def test_cache_shape_requires_exact_immediate_spare_predecessor(self):
  gate=harness.CacheTests('runTest').function('current_grid_stages',{});tail={}
  for key in reversed(('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract')):tail={key:{},'previous_stage_adapter':tail}
  prefixes=[tail]
  for _,_,key in harness.STAGES[1:next(i for i,row in enumerate(harness.STAGES)if row[0]=='position')]:
   current={key:{},'previous_stage_adapter':prefixes[-1]}
   if key=='staging_attach_contract':current['previous_stage_kind']='publication'
   prefixes.append(current)
  for prefix in prefixes:
   with self.subTest(predecessor=list(prefix)[0]):self.assertEqual(gate({'native_position_contract':{},'previous_stage_adapter':prefix}),prefix is prefixes[-1])
  self.assertFalse(gate({'native_position_contract':None,'previous_stage_adapter':prefixes[-1]}))
 def test_four_new_pins_complete_fresh_path_and_native_only_scope(self):
  import cas_grid_position as position
  source=(ROOT/'tools/cas_ui_build.py').read_text();tree=ast.parse(source);pins=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
  for name in position.SOURCES:self.assertEqual(pins.count(name),1)
  self.assertEqual(len(pins),len(set(pins)));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_finish_grid_provider_position');code=ast.get_source_segment(source,fn);self.assertIn('_finish_grid_provider_spares(',code);self.assertIn('cas_grid_position.adapt(',code);self.assertNotIn('cas_grid_position.adapt_main',source)
  with self.assertRaises(ValueError):position.inventory(position.MAIN)
 def test_complete_verifier_peels_position_before_spares_at_every_library_entry(self):
  source=(ROOT/'tools/maru_companion.py').read_text();tree=ast.parse(source)
  for method in ('_verify_grid_adapter','verify_grid_providers','verify_merged'):
   fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name==method);body=ast.get_source_segment(source,fn);self.assertLess(body.index('cas_grid_position'),body.index('cas_grid_spares'))
if __name__=='__main__':unittest.main()
