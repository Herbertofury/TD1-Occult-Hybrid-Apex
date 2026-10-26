from pathlib import Path
import ast,sys,unittest,types
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import cas_grid_physical as stage

def function(name):
 tree=ast.parse((ROOT/'tools/cas_ui_build.py').read_text());found=[n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name==name];assert len(found)==1
 ns={'Path':Path};helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in('_finish_grid_provider_physical','_finish_grid_provider_intrinsic','_finish_grid_provider_spares')]if name=='finish_grid_provider'else[];exec(compile(ast.fix_missing_locations(ast.Module(body=helpers+found,type_ignores=[])),'builder-fixture','exec'),ns);return ns[name]

class BuildTests(unittest.TestCase):
 def mocks(self,events,fail=False):
  modules={}
  for name,key in (('cas_grid_spares','spare_custody_contract'),('cas_grid_position','native_position_contract'),('cas_grid_intrinsic','intrinsic_geometry_contract'),('cas_grid_physical','physical_position_contract'),('cas_grid_row_delta','row_delta_contract')):
   m=types.ModuleType(name)
   def verify(prior,raw,n=name,k=key):
    events.append(('verify',n));self.assertIn(k,prior)
    if fail and n in('cas_grid_physical','cas_grid_intrinsic','cas_grid_spares'):raise ValueError('actual stage refused')
    return True
   def adapt(prior,raw,*args,n=name,k=key):
    events.append(('adapt',n))
    if fail:raise ValueError('new stage failed')
    return raw+b'|'+n.rsplit('_',1)[1].encode(),{k:{},'previous_stage_adapter':prior}
   m.verify_adapter=verify;m.adapt=adapt;modules[name]=m
  return modules
 def test_verified_physical_prefix_continues_intrinsic_and_spares(self):
  events=[];p={'physical_position_contract':{}}
  with patch.dict(sys.modules,self.mocks(events)):raw,proof=function('finish_grid_provider')(p,b'current',Path('original'),'ffdec',Path('private'))
  self.assertIsNot(proof,p);self.assertEqual(raw,b'current|intrinsic|spares|position');self.assertEqual(events,[('verify','cas_grid_physical'),('adapt','cas_grid_intrinsic'),('adapt','cas_grid_spares'),('adapt','cas_grid_position')]);self.assertIn('native_position_contract',proof);self.assertIn('spare_custody_contract',proof['previous_stage_adapter']);self.assertIn('intrinsic_geometry_contract',proof['previous_stage_adapter']['previous_stage_adapter'])
 def test_current_rowdelta_prefix_must_continue_through_physical(self):
  events=[];p={'row_delta_contract':{}}
  with patch.dict(sys.modules,self.mocks(events)):raw,proof=function('finish_grid_provider')(p,b'current',Path('original'),'ffdec',Path('private'))
  self.assertEqual(events,[('verify','cas_grid_row_delta'),('adapt','cas_grid_physical'),('adapt','cas_grid_intrinsic'),('adapt','cas_grid_spares'),('adapt','cas_grid_position')]);self.assertIn('native_position_contract',proof);self.assertIn('spare_custody_contract',proof['previous_stage_adapter']);self.assertIn('intrinsic_geometry_contract',proof['previous_stage_adapter']['previous_stage_adapter']);self.assertEqual(raw,b'current|physical|intrinsic|spares|position')
 def test_failed_current_or_missing_stage_does_not_return_stale_prefix_bytes(self):
  for key in ('spare_custody_contract','intrinsic_geometry_contract','physical_position_contract','row_delta_contract'):
   with patch.dict(sys.modules,self.mocks([],True)),self.assertRaises(ValueError):function('finish_grid_provider')({key:{}},b'current',Path('original'),'ffdec',Path('private'))
 def test_provider_only_manifest_rollback_precedes_rowdelta_and_main_is_never_replaced(self):
  text=(ROOT/'tools/maru_companion.py').read_text();body=text[text.index('def verify_merged('):]
  self.assertLess(body.index('cas_grid_physical.unwrap_manifest'),body.index('cas_grid_row_delta.unwrap_manifest'))
  source=(ROOT/'tools/cas_ui_build.py').read_text();self.assertNotIn('cas_grid_physical.adapt_main',source)
  self.assertIn("if 'native_position_contract' not in prior:cache.setdefault('continued',set())",source)
 def test_all_three_sources_are_required_once_and_new_helpers_retain_native_constructor_draw_click(self):
  tree=ast.parse((ROOT/'tools/cas_ui_build.py').read_text());names=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
  for name in stage.SOURCES:self.assertEqual(names.count(name),1)
  self.assertEqual(len(stage.inventory(stage.GRID)[0]),7);self.assertEqual(len(stage.inventory(stage.GRID)[1]),1)
  with self.assertRaises(ValueError):stage.inventory(stage.MAIN)
  for name in stage.inventory(stage.GRID)[0]:self.assertTrue(name.startswith('ApexGrid'))

if __name__=='__main__':unittest.main()
