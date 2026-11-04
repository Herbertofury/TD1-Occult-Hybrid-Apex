"""Exercise actual builder control flow with strict prefix/failure contracts."""
from pathlib import Path
import ast,os,sys,types,unittest
ROOT=Path(__file__).resolve().parents[1]
BUILD=Path(os.environ.get('APEX_CAS_ROW_DELTA_BUILD_SOURCE',ROOT/'tools/cas_ui_build.py'))
STAGES=(('cas_grid_slice','slice_contract'),('cas_grid_budget','budget_contract'),('cas_grid_featured','featured_contract'),('cas_grid_publication','publication_trace_contract'),('cas_grid_staging_attach','staging_attach_contract'),('cas_swatch_columns','swatch_columns_contract'),('cas_grid_row_delta','row_delta_contract'),('cas_grid_physical','physical_position_contract'),('cas_grid_intrinsic','intrinsic_geometry_contract'),('cas_grid_spares','spare_custody_contract'),('cas_grid_position','native_position_contract'),('cas_grid_logical_bank','logical_bank_contract'),('cas_grid_frame_status','frame_status_contract'),('cas_grid_eof','eof_delta_contract'),('cas_grid_width','view_width_transfer_contract'))
class BuildTests(unittest.TestCase):
 def function(self,name,namespace):
  node=next(n for n in ast.walk(ast.parse(BUILD.read_text()))if isinstance(n,ast.FunctionDef)and n.name==name)
  exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(BUILD),'exec'),namespace);return namespace[name]
 def run_prefix(self,index,refuse=None,historical=False):
  old={};calls=[]
  for name,key in STAGES:
   old[name]=sys.modules.get(name);module=types.ModuleType(name)
   def verify(prior,raw,name=name):
    calls.append(name+'.verify')
    if refuse==name:raise ValueError('Authenticated prefix refused')
    return True
   def adapt(prior,raw,original,ffdec,work,name=name,key=key):
    calls.append(name+'.adapt')
    if refuse==name+'.adapt':raise ValueError('Required compilation refused')
    return name.encode(),{key:{'previous_stage_kind':'staging-attach'}if key=='swatch_columns_contract'else{},'previous_stage_adapter':prior}
   module.verify_adapter=verify;module.adapt=adapt;sys.modules[name]=module
  try:
   key=STAGES[index][1];prior={key:{'previous_stage_kind':'featured-fixture'if historical else'staging-attach'}}
   if index==4:prior['previous_stage_kind']='publication'
   if key=='native_position_contract':prior['previous_stage_adapter']={'spare_custody_contract':{}}
   if key=='frame_status_contract':prior['previous_stage_adapter']={'logical_bank_contract':{}}
   if key=='eof_delta_contract':prior['previous_stage_adapter']={'frame_status_contract':{}}
   if key=='view_width_transfer_contract':prior['previous_stage_adapter']={'eof_delta_contract':{},'previous_stage_adapter':{'frame_status_contract':{}}}
   ns={'Path':Path};self.function('_finish_grid_provider_physical',ns);self.function('_finish_grid_provider_intrinsic',ns);self.function('_finish_grid_provider_spares',ns);self.function('_finish_grid_provider_position',ns);self.function('_finish_grid_provider_logical_bank',ns);self.function('_finish_grid_provider_frame_status',ns);self.function('_finish_grid_provider_eof',ns);fn=self.function('finish_grid_provider',ns)
   if refuse or historical:
    with self.assertRaises(ValueError):fn(prior,b'authenticated-prefix','native','compiler',Path('isolated-output'))
    result=None
   else:result=fn(prior,b'authenticated-prefix','native','compiler',Path('isolated-output'))
   return calls,result
  finally:
   for name,value in old.items():
    if value is None:sys.modules.pop(name,None)
    else:sys.modules[name]=value
 def test_every_authenticated_prefix_compiles_all_and_only_missing_stages(self):
  for i,(name,_)in enumerate(STAGES):
   calls,result=self.run_prefix(i);self.assertEqual(calls,[name+'.verify']+[n+'.adapt'for n,_ in STAGES[i+1:]])
   self.assertEqual(result[0],b'authenticated-prefix'if i==len(STAGES)-1 else b'cas_grid_width')
 def test_current_terminal_is_returned_only_after_complete_verification(self):
  calls,result=self.run_prefix(len(STAGES)-1);self.assertEqual(calls,['cas_grid_width.verify']);self.assertIn('view_width_transfer_contract',result[1]);self.assertIn('eof_delta_contract',result[1]['previous_stage_adapter']);self.assertIn('frame_status_contract',result[1]['previous_stage_adapter']['previous_stage_adapter'])
 def test_invalid_prefix_never_silently_rebuilds_or_returns_older_bytes(self):
  for i,(name,_)in enumerate(STAGES):self.assertEqual(self.run_prefix(i,name)[0],[name+'.verify'])
 def test_missing_terminal_failure_cannot_become_successful_skin_cache_hit(self):
  calls,result=self.run_prefix(5,'cas_grid_row_delta.adapt');self.assertIsNone(result);self.assertEqual(calls,['cas_swatch_columns.verify','cas_grid_row_delta.adapt'])
 def test_historical_skin_fixture_is_not_current_build_authority(self):
  self.assertEqual(self.run_prefix(5,historical=True)[0],['cas_swatch_columns.verify'])
 def test_structural_gate_requires_exact_immediate_skin_predecessor(self):
  gate=self.function('current_grid_stages',{});tail={}
  for key in reversed(('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract')):tail={key:{},'previous_stage_adapter':tail}
  prefixes=[tail]
  for _,key in STAGES[1:]:
   v={key:{},'previous_stage_adapter':prefixes[-1]}
   if key=='staging_attach_contract':v['previous_stage_kind']='publication'
   prefixes.append(v)
  for p in prefixes:self.assertTrue(gate(p))
  for predecessor in [p for index,p in enumerate(prefixes)if index!=5]+[{}]:self.assertFalse(gate({'row_delta_contract':{},'previous_stage_adapter':predecessor}))
 def test_four_new_source_pins_main_terminal_order_and_cache_continuation_are_explicit(self):
  text=BUILD.read_text();tree=ast.parse(text);pins=ast.literal_eval(next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets)).value)
  for n in('tools/cas_grid_row_delta.py','tools/cas_row_delta_stage.py','tools/CasGridRowDeltaPatch.java','Source/CASUi/catalog_row_delta_methods.as'):self.assertIn(n,pins)
  self.assertLess(text.index('payload, swatch_columns_main_contract = cas_swatch_columns.adapt_main'),text.index('payload, row_delta_main_contract = cas_grid_row_delta.adapt_main'))
  self.assertIn("if 'view_width_transfer_contract' not in prior:cache.setdefault('continued'",text)
  self.assertIn("'row_delta_main_native_bytecode_contract': row_delta_main_contract",text)

if __name__=='__main__':unittest.main()
