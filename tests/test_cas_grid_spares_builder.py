"""Execute the real builder continuation, with bounded compiler doubles only."""
from pathlib import Path
import ast,sys,types,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'integration/cas_ui_build.py'if(ROOT/'integration/cas_ui_build.py').is_file()else ROOT/'tools/cas_ui_build.py'
STAGES=[('cas_grid_slice','slice_contract'),('cas_grid_budget','budget_contract'),('cas_grid_featured','featured_contract'),('cas_grid_publication','publication_trace_contract'),('cas_grid_staging_attach','staging_attach_contract'),('cas_swatch_columns','swatch_columns_contract'),('cas_grid_row_delta','row_delta_contract'),('cas_grid_physical','physical_position_contract'),('cas_grid_intrinsic','intrinsic_geometry_contract'),('cas_grid_spares','spare_custody_contract'),('cas_grid_position','native_position_contract')]
class SpareBuilderTests(unittest.TestCase):
 def setup_builder(self):
  tree=ast.parse(SOURCE.read_text());functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('finish_grid_provider','_finish_grid_provider_spares','_finish_grid_provider_intrinsic','_finish_grid_provider_physical')];self.assertEqual(len(functions),4)
  ns={'Path':Path};exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),str(SOURCE),'exec'),ns);self.calls=[];modules={}
  for module,key in STAGES:
   def verify(proof,raw,module=module,key=key):
    self.calls.append(('verify',module));self.assertEqual(raw,proof['bytes']);self.assertIn(key,proof)
    if proof.get('corrupt'):raise ValueError('strict prefix refused')
    return True
   def adapt(proof,raw,original,ffdec,work,module=module,key=key):
    self.calls.append(('adapt',module));self.assertEqual(raw,proof['bytes']);self.assertEqual(original,b'original');self.assertEqual(ffdec,'compiler')
    if self.fail==module:raise ValueError('new stage failed')
    new=key.encode();return new,{key:{'previous_stage_kind':'staging-attach'}if key=='swatch_columns_contract'else{},'previous_stage_adapter':proof,'previous_stage_kind':'publication'if key=='staging_attach_contract'else None,'bytes':new}
   modules[module]=types.SimpleNamespace(verify_adapter=verify,adapt=adapt)
  self.fail=None;return ns['finish_grid_provider'],modules
 def prefix(self,key):
  result={key:{'previous_stage_kind':'staging-attach'}if key=='swatch_columns_contract'else{},'previous_stage_kind':'publication'if key=='staging_attach_contract'else None,'bytes':key.encode()}
  if key=='native_position_contract':result['previous_stage_adapter']={'spare_custody_contract':{}}
  return result
 def test_all_eleven_prefixes_continue_every_missing_stage(self):
  for i,(_,key)in enumerate(STAGES):
   finish,modules=self.setup_builder();prior=self.prefix(key)
   with self.subTest(key=key),patch.dict(sys.modules,modules):raw,proof=finish(prior,prior['bytes'],b'original','compiler',ROOT/'unused')
   self.assertEqual([n for kind,n in self.calls if kind=='adapt'],[n for n,_ in STAGES[i+1:]]);self.assertEqual(self.calls[0],('verify',STAGES[i][0]));self.assertIn('native_position_contract',proof);self.assertIn('spare_custody_contract',proof['previous_stage_adapter'])
 def test_current_terminal_verified_and_never_recompiled(self):
  finish,modules=self.setup_builder();prior=self.prefix('native_position_contract')
  with patch.dict(sys.modules,modules):self.assertEqual(finish(prior,prior['bytes'],b'original','compiler',ROOT/'unused'),(prior['bytes'],prior))
  self.assertEqual(self.calls,[('verify','cas_grid_position')])
 def test_corrupt_current_or_previous_prefix_refuses_before_build(self):
  for key in('native_position_contract','spare_custody_contract','intrinsic_geometry_contract','row_delta_contract'):
   finish,modules=self.setup_builder();prior=self.prefix(key);prior['corrupt']=True
   with self.subTest(key=key),patch.dict(sys.modules,modules),self.assertRaisesRegex(ValueError,'strict prefix refused'):finish(prior,prior['bytes'],b'original','compiler',ROOT/'unused')
   self.assertFalse(any(kind=='adapt'for kind,_ in self.calls))
 def test_new_stage_failure_never_returns_previous_prefix(self):
  finish,modules=self.setup_builder();prior=self.prefix('intrinsic_geometry_contract');self.fail='cas_grid_spares'
  with patch.dict(sys.modules,modules),self.assertRaisesRegex(ValueError,'new stage failed'):finish(prior,prior['bytes'],b'original','compiler',ROOT/'unused')
  self.assertEqual(self.calls,[('verify','cas_grid_intrinsic'),('adapt','cas_grid_spares')])
 def test_four_source_pins_and_cache_continuation_are_mandatory(self):
  tree=ast.parse(SOURCE.read_text());pins=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
  for name in('tools/cas_grid_spares.py','tools/cas_grid_spares_stage.py','tools/CasGridSparesPatch.java','Source/CASUi/catalog_spare_custody_methods.as'):self.assertEqual(pins.count(name),1)
  text=SOURCE.read_text();self.assertIn("if 'native_position_contract' not in prior:cache.setdefault('continued',set())",text)
  verifier=SOURCE.with_name('maru_companion.py').read_text();self.assertLess(verifier.index('info, resources = cas_grid_spares.unwrap_manifest'),verifier.index('info, resources = cas_catalog_workflow.unwrap_manifest'))

if __name__=='__main__':unittest.main()
