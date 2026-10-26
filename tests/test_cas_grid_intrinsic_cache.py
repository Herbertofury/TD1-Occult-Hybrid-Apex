from pathlib import Path
import ast,copy,os,sys,types,unittest
from unittest.mock import patch
ROOT=Path(os.environ.get('APEX_INTRINSIC_SOURCE_ROOT',Path(__file__).resolve().parents[1])).resolve()
H=ROOT
SOURCE=ROOT/'tools/cas_ui_build.py'
STAGES=[('cas_grid_slice','slice_contract'),('cas_grid_budget','budget_contract'),('cas_grid_featured','featured_contract'),('cas_grid_publication','publication_trace_contract'),('cas_grid_staging_attach','staging_attach_contract'),('cas_swatch_columns','swatch_columns_contract'),('cas_grid_row_delta','row_delta_contract'),('cas_grid_physical','physical_position_contract'),('cas_grid_intrinsic','intrinsic_geometry_contract')]
class BuilderContinuationTests(unittest.TestCase):
 def setup_builder(self):
  tree=ast.parse(SOURCE.read_text());functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ('finish_grid_provider','_finish_grid_provider_physical')];self.assertEqual(len(functions),2)
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
 def prefix(self,key):return {key:{'previous_stage_kind':'staging-attach'}if key=='swatch_columns_contract'else{},'previous_stage_kind':'publication'if key=='staging_attach_contract'else None,'bytes':key.encode()}
 def test_every_authenticated_historical_prefix_continues_exact_missing_stages(self):
  for i,(_,key)in enumerate(STAGES):
   with self.subTest(prefix=key):
    finish,modules=self.setup_builder();prior=self.prefix(key)
    with patch.dict(sys.modules,modules):raw,proof=finish(prior,prior['bytes'],b'original','compiler',H/'unused')
    self.assertEqual([name for kind,name in self.calls if kind=='adapt'],[name for name,_ in STAGES[i+1:]])
    self.assertEqual(self.calls[0],('verify',STAGES[i][0]));self.assertIn('intrinsic_geometry_contract',proof);self.assertEqual(raw,proof['bytes'])
 def test_current_terminal_is_verified_and_never_recompiled(self):
  finish,modules=self.setup_builder();prior=self.prefix('intrinsic_geometry_contract')
  with patch.dict(sys.modules,modules):self.assertEqual(finish(prior,prior['bytes'],b'original','compiler',H/'unused'),(prior['bytes'],prior))
  self.assertEqual(self.calls,[('verify','cas_grid_intrinsic')])
 def test_corrupt_current_or_prefix_never_returns_stale_bytes(self):
  for key in ('intrinsic_geometry_contract','physical_position_contract','row_delta_contract'):
   finish,modules=self.setup_builder();prior=self.prefix(key);prior['corrupt']=True
   with self.subTest(key=key),patch.dict(sys.modules,modules),self.assertRaisesRegex(ValueError,'strict prefix refused'):finish(prior,prior['bytes'],b'original','compiler',H/'unused')
   self.assertFalse(any(kind=='adapt'for kind,_ in self.calls))
 def test_failed_terminal_build_is_not_a_successful_old_prefix(self):
  finish,modules=self.setup_builder();prior=self.prefix('row_delta_contract');self.fail='cas_grid_intrinsic'
  with patch.dict(sys.modules,modules),self.assertRaisesRegex(ValueError,'new stage failed'):finish(prior,prior['bytes'],b'original','compiler',H/'unused')
  self.assertEqual(self.calls,[('verify','cas_grid_row_delta'),('adapt','cas_grid_physical'),('adapt','cas_grid_intrinsic')])
 def test_all_four_new_sources_are_pinned_exactly_once(self):
  tree=ast.parse(SOURCE.read_text());pins=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
  for name in ('tools/cas_grid_intrinsic.py','tools/cas_grid_intrinsic_stage.py','tools/CasGridIntrinsicPatch.java','Source/CASUi/catalog_grid_intrinsic_methods.as'):self.assertEqual(pins.count(name),1)
if __name__=='__main__':unittest.main()
