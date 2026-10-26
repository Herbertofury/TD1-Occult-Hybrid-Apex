"""Run the actual builder's verified-prefix continuation control flow."""
from pathlib import Path
import ast,hashlib,os,sys,tempfile,types,unittest
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in(ROOT,*ROOT.parents)if(p/'tools/cas_grid_budget.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools')]
import cas_grid_featured as featured
import dbpf_build,maru_companion
BUILD=Path(os.environ.get('APEX_CAS_GRID_FEATURED_BUILD_SOURCE',ROOT/'tools/cas_ui_build.py'))

class FeatureCacheTests(unittest.TestCase):
 def function(self,name,namespace):
  node=next(n for n in ast.walk(ast.parse(BUILD.read_text()))if isinstance(n,ast.FunctionDef)and n.name==name)
  exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(BUILD),'exec'),namespace);return namespace[name]
 def run_prefix(self,stage,refuse=None):
  calls=[];old={};names=('cas_grid_slice','cas_grid_budget','cas_grid_featured')
  for name in names:
   old[name]=sys.modules.get(name);spy=types.ModuleType(name)
   def verify(adapter,raw,name=name):
    calls.append((name+'.verify',adapter,raw))
    if refuse==name:raise ValueError('Exact prefix proof refused')
    return True
   def adapt(adapter,raw,original,ffdec,work,name=name):
    calls.append((name+'.adapt',adapter,raw))
    if refuse==name+'.adapt':raise ValueError('Terminal compiler refused')
    contract='budget_contract'if name=='cas_grid_budget'else'featured_contract'
    return name.encode(),{contract:{'ok':True},'previous_stage_adapter':adapter}
   spy.verify_adapter=verify;spy.adapt=adapt;sys.modules[name]=spy
  try:
   with tempfile.TemporaryDirectory()as folder:
    path=Path(folder)/'original.swf';path.write_bytes(b'original-native');digest=hashlib.sha256(path.read_bytes()).hexdigest()
    key=maru_companion.CANONICAL_GRID_LIBRARY;prior={stage+'_contract':{}};cache={'original_sha256':{key:digest,maru_companion.GRID_LIBRARY:'0'*64},'used':set(),'providers':{dbpf_build.tgi(key):prior},'resources':{key:b'prefix'}}
    namespace={'Path':Path,'hashlib':hashlib,'maru_companion':maru_companion,'dbpf_build':dbpf_build,'work':Path(folder),'ffdec':'private-compiler'}
    self.function('finish_grid_provider',namespace);fn=self.function('adapt_grid_provider',namespace)
    if refuse:
     with self.assertRaises(ValueError):fn(path,digest,'out.abc',cache)
     result=None
    else:result=fn(path,digest,'out.abc',cache)
    return result,calls,cache,prior,key
  finally:
   for name in names:
    if old[name]is None:sys.modules.pop(name,None)
    else:sys.modules[name]=old[name]
 def test_verified_slice_prefix_compiles_only_budget_then_featured(self):
  result,calls,cache,prior,key=self.run_prefix('slice')
  self.assertEqual([r[0]for r in calls],['cas_grid_slice.verify','cas_grid_budget.adapt','cas_grid_featured.adapt'])
  self.assertIs(calls[0][1],prior);self.assertEqual(calls[0][2],b'prefix');self.assertEqual(calls[2][2],b'cas_grid_budget')
  self.assertEqual(result[0],b'cas_grid_featured');self.assertEqual(cache['continued'],{dbpf_build.tgi(key)})
 def test_verified_budget_prefix_compiles_featured_only(self):
  result,calls,cache,prior,key=self.run_prefix('budget')
  self.assertEqual([r[0]for r in calls],['cas_grid_budget.verify','cas_grid_featured.adapt']);self.assertEqual(result[0],b'cas_grid_featured')
 def test_current_featured_resource_verifies_without_any_compiler_call(self):
  result,calls,cache,prior,key=self.run_prefix('featured')
  self.assertEqual([r[0]for r in calls],['cas_grid_featured.verify']);self.assertEqual(result,(b'prefix',prior));self.assertNotIn('continued',cache)
 def test_refused_prefix_or_failed_terminal_never_returns_stale_cached_bytes(self):
  for stage,refusal in [('slice','cas_grid_slice'),('budget','cas_grid_budget'),('featured','cas_grid_featured'),('slice','cas_grid_budget.adapt'),('budget','cas_grid_featured.adapt')]:
   result,calls,*_=self.run_prefix(stage,refusal);self.assertIsNone(result);self.assertTrue(calls)
 def test_shape_admission_requires_complete_known_topology(self):
  gate=self.function('current_grid_stages',{});tail={}
  for key in reversed(('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract')):tail={key:{},'previous_stage_adapter':tail}
  budget={'budget_contract':{},'previous_stage_adapter':tail};final={'featured_contract':{},'previous_stage_adapter':budget}
  for valid in(tail,budget,final):self.assertTrue(gate(valid))
  for invalid in({},tail['previous_stage_adapter'],{'featured_contract':{},'previous_stage_adapter':tail},{'budget_contract':None,'previous_stage_adapter':tail}):self.assertFalse(gate(invalid))
 def test_all_sources_are_pinned_and_fresh_main_and_native_order_is_budget_then_featured(self):
  source=BUILD.read_text();tree=ast.parse(source);assignment=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
  self.assertTrue(set(featured.SOURCES)<=set(ast.literal_eval(assignment.value)))
  self.assertLess(source.index('payload, budget_main_contract = cas_grid_budget.adapt_main'),source.index('payload, featured_main_contract = cas_grid_featured.adapt_main'))
  self.assertIn('return finish_grid_provider(adapter, grid_payload',source)

if __name__=='__main__':unittest.main()
