"""Exercise actual terminal builder/cache dispatch without a compiler or game."""
from pathlib import Path
import ast,os,sys,types,unittest
ROOT=Path(__file__).resolve().parents[1]
BUILD=Path(os.environ.get('APEX_CAS_SWATCH_COLUMNS_BUILD_SOURCE',ROOT/'tools/cas_ui_build.py'))
STAGES=(('cas_grid_slice','slice_contract'),('cas_grid_budget','budget_contract'),('cas_grid_featured','featured_contract'),('cas_grid_publication','publication_trace_contract'),('cas_grid_staging_attach','staging_attach_contract'),('cas_swatch_columns','swatch_columns_contract'),('cas_grid_row_delta','row_delta_contract'),('cas_grid_physical','physical_position_contract'),('cas_grid_intrinsic','intrinsic_geometry_contract'),('cas_grid_spares','spare_custody_contract'),('cas_grid_position','native_position_contract'),('cas_grid_logical_bank','logical_bank_contract'),('cas_grid_frame_status','frame_status_contract'),('cas_grid_eof','eof_delta_contract'))
class SwatchColumnsBuildTests(unittest.TestCase):
 def function(self,name,namespace):
  tree=ast.parse(BUILD.read_text());node=next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name==name);exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(BUILD),'exec'),namespace);return namespace[name]
 def run_prefix(self,index,refuse=None,historical=False):
  old={};calls=[]
  for name,key in STAGES:
   old[name]=sys.modules.get(name);module=types.ModuleType(name)
   def verify(prior,raw,name=name):
    calls.append(name+'.verify')
    if refuse==name:raise ValueError('Strict authenticated prefix refused')
    return True
   def adapt(prior,raw,original,ffdec,work,name=name,key=key):
    calls.append(name+'.adapt')
    if refuse==name+'.adapt':raise ValueError('Compiler refused')
    return name.encode(),{key:{'previous_stage_kind':'staging-attach'}if key=='swatch_columns_contract'else{},'previous_stage_adapter':prior}
   module.verify_adapter=verify;module.adapt=adapt;sys.modules[name]=module
  try:
   key=STAGES[index][1];prior={key:{'previous_stage_kind':'featured-fixture'if historical else'staging-attach'}}
   if index==4:prior['previous_stage_kind']='publication'
   ns={'Path':Path};self.function('_finish_grid_provider_physical',ns);self.function('_finish_grid_provider_intrinsic',ns);self.function('_finish_grid_provider_spares',ns);self.function('_finish_grid_provider_position',ns);self.function('_finish_grid_provider_logical_bank',ns);self.function('_finish_grid_provider_frame_status',ns);fn=self.function('finish_grid_provider',ns)
   if refuse or historical:
    with self.assertRaises(ValueError):fn(prior,b'authenticated-prefix','native','compiler',Path('distinct-private-output'))
    result=None
   else:result=fn(prior,b'authenticated-prefix','native','compiler',Path('distinct-private-output'))
   return calls,result
  finally:
   for name,value in old.items():
    if value is None:sys.modules.pop(name,None)
    else:sys.modules[name]=value
 def test_every_exact_prefix_continues_all_and_only_missing_stages(self):
  for index,(name,_)in enumerate(STAGES):
   with self.subTest(prefix=name):
    calls,result=self.run_prefix(index);self.assertEqual(calls,[name+'.verify']+[n+'.adapt'for n,_ in STAGES[index+1:]])
    self.assertEqual(result[0],b'authenticated-prefix'if index==len(STAGES)-1 else b'cas_grid_eof')
 def test_current_skin_returns_only_after_strict_validation(self):
  calls,result=self.run_prefix(5);self.assertEqual(calls,['cas_swatch_columns.verify','cas_grid_row_delta.adapt','cas_grid_physical.adapt','cas_grid_intrinsic.adapt','cas_grid_spares.adapt','cas_grid_position.adapt','cas_grid_logical_bank.adapt','cas_grid_frame_status.adapt','cas_grid_eof.adapt']);self.assertIn('eof_delta_contract',result[1]);self.assertIn('frame_status_contract',result[1]['previous_stage_adapter']);self.assertIn('logical_bank_contract',result[1]['previous_stage_adapter']['previous_stage_adapter']);self.assertIn('native_position_contract',result[1]['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']);self.assertIn('spare_custody_contract',result[1]['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']);self.assertIn('intrinsic_geometry_contract',result[1]['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter']['previous_stage_adapter'])
 def test_invalid_existing_prefix_never_falls_back_to_any_compiler(self):
  for index,(name,_)in enumerate(STAGES):
   calls,_=self.run_prefix(index,name);self.assertEqual(calls,[name+'.verify'])
 def test_failed_required_terminal_never_returns_authenticated_older_bytes(self):
  calls,result=self.run_prefix(2,'cas_swatch_columns.adapt');self.assertIsNone(result);self.assertEqual(calls[-1],'cas_swatch_columns.adapt')
 def test_explicit_historical_compiler_fixture_cannot_become_current_cache_hit(self):
  calls,_=self.run_prefix(5,historical=True);self.assertEqual(calls,['cas_swatch_columns.verify'])
 def test_structural_cache_gate_requires_complete_terminal_prefixes(self):
  gate=self.function('current_grid_stages',{})
  tail={}
  for key in reversed(('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract')):tail={key:{},'previous_stage_adapter':tail}
  prefixes=[tail]
  for _,key in STAGES[1:]:
   item={key:{},'previous_stage_adapter':prefixes[-1]}
   if key=='staging_attach_contract':item['previous_stage_kind']='publication'
   prefixes.append(item)
  for prefix in prefixes:self.assertTrue(gate(prefix))
  for key in('spare_custody_contract','intrinsic_geometry_contract','physical_position_contract','row_delta_contract','swatch_columns_contract','staging_attach_contract','publication_trace_contract','featured_contract'):
   self.assertFalse(gate({key:{},'previous_stage_adapter':tail}))
 def test_source_pins_and_main_order_are_explicit_and_canonical_requires_wrapper(self):
  source=BUILD.read_text();tree=ast.parse(source);assignment=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets));pins=ast.literal_eval(assignment.value)
  for name in('tools/cas_swatch_columns.py','tools/CasSwatchColumnsPatch.java','Source/CASUi/swatch_columns_methods.as'):self.assertIn(name,pins)
  self.assertLess(source.index('payload, publication_main_contract = cas_grid_publication.adapt_main'),source.index('payload, swatch_columns_main_contract = cas_swatch_columns.adapt_main'))
  self.assertIn("if 'eof_delta_contract' not in prior:cache.setdefault('continued'",source)

if __name__=='__main__':unittest.main()
