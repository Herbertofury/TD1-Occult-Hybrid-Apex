"""Exact Main/provider successor seams; no compiler, package, game or private fixture required."""
from pathlib import Path
import ast,sys,types,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_grid_width as width,cas_catalog_unconsumed as key

class WidthUnconsumedBuildTests(unittest.TestCase):
 def tree(self,name='cas_ui_build.py'):
  return ast.parse((ROOT/'tools'/name).read_text(encoding='utf-8-sig'))
 def calls(self):
  names={'catalog_authority_main_contract','view_width_transfer_main_contract','catalog_unconsumed_main_contract'}
  found={}
  for n in ast.walk(self.tree()):
   if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Tuple)and isinstance(n.value,ast.Call):
    targets=n.targets[0].elts
    if len(targets)==2 and isinstance(targets[1],ast.Name)and targets[1].id in names:found[targets[1].id]=n
  self.assertEqual(set(found),names);return found
 def function(self,name,namespace=None,source='cas_ui_build.py'):
  node=next(n for n in self.tree(source).body if isinstance(n,ast.FunctionDef)and n.name==name)
  namespace={}if namespace is None else namespace
  exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),source,'exec'),namespace)
  return namespace[name]
 def test_every_actual_UI_source_is_pinned_exactly_once(self):
  pins=next(ast.literal_eval(n.value)for n in self.tree().body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
  sources=width.SOURCES+key.SOURCES;self.assertEqual(len(set(sources)),len(sources))
  for name in sources:self.assertEqual(pins.count(name),1,name)
 def test_two_fresh_adapters_follow_exact_immediate_Main_predecessor(self):
  calls=self.calls();a=calls['catalog_authority_main_contract'];w=calls['view_width_transfer_main_contract'];k=calls['catalog_unconsumed_main_contract']
  self.assertLess(a.lineno,w.lineno);self.assertLess(w.lineno,k.lineno)
  for node,module,prior in((w,'cas_grid_width','catalog_authority_main_contract'),(k,'cas_catalog_unconsumed','view_width_transfer_main_contract')):
   self.assertEqual(ast.unparse(node.value.func),module+'.adapt_main')
   self.assertEqual([ast.unparse(a)for a in node.value.args[:4]],[prior,'payload','patched','ffdec'])
 def execute(self,refuse=None):
  calls=self.calls();nodes=[calls['view_width_transfer_main_contract'],calls['catalog_unconsumed_main_contract']]
  trace=[];authority=object();widthproof=object();keyproof=object();source=object();ffdec=object()
  def adapter(name,proof,result):
   def call(*args):
    trace.append((name,args))
    if refuse==name:raise ValueError(name+' exact proof refused')
    return result,proof
   return call
  ns={'catalog_authority_main_contract':authority,'payload':b'Authority','patched':source,'ffdec':ffdec,'work':Path('build'),
      'cas_grid_width':types.SimpleNamespace(adapt_main=adapter('width',widthproof,b'Width')),
      'cas_catalog_unconsumed':types.SimpleNamespace(adapt_main=adapter('key',keyproof,b'Key'))}
  code=compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'fresh-Main','exec')
  if refuse:
   with self.assertRaisesRegex(ValueError,refuse+' exact proof refused'):exec(code,ns)
  else:exec(code,ns)
  return ns,trace,authority,widthproof,keyproof,source,ffdec
 def test_actual_assignment_passes_returned_Width_bytes_and_proof_to_Key(self):
  ns,calls,a,w,k,s,f=self.execute()
  self.assertEqual(calls,[('width',(a,b'Authority',s,f,Path('build/view-width-transfer-main'))),
                          ('key',(w,b'Width',s,f,Path('build/catalog-unconsumed-main')))])
  self.assertEqual(ns['payload'],b'Key');self.assertIs(ns['catalog_unconsumed_main_contract'],k)
 def test_Width_refusal_never_invokes_Key_or_returns_predecessor_as_final(self):
  ns,calls,*_=self.execute('width');self.assertEqual([n for n,_ in calls],['width'])
  self.assertEqual(ns['payload'],b'Authority');self.assertNotIn('catalog_unconsumed_main_contract',ns)
 def test_Key_refusal_never_labels_Width_as_Key(self):
  ns,calls,*_=self.execute('key');self.assertEqual([n for n,_ in calls],['width','key'])
  self.assertEqual(ns['payload'],b'Width');self.assertNotIn('catalog_unconsumed_main_contract',ns)
 def test_manifest_has_both_exact_successor_aliases(self):
  for wanted,var in((width.MAIN_MANIFEST,'view_width_transfer_main_contract'),(key.MANIFEST,'catalog_unconsumed_main_contract')):
   rows=[]
   for n in ast.walk(self.tree()):
    if isinstance(n,ast.Dict):rows.extend(v for k,v in zip(n.keys,n.values)if isinstance(k,ast.Constant)and k.value==wanted)
   self.assertEqual(len(rows),1);self.assertEqual(ast.unparse(rows[0]),var)
 def test_bundle_unwrap_is_Key_then_Width_before_original_Authority_and_EOF(self):
  class Done(Exception):pass
  names=('cas_catalog_unconsumed','cas_grid_width','cas_catalog_authority','cas_grid_eof')
  modules={n:types.ModuleType(n)for n in names};trace=[];info=object();resources=object()
  for name in names:
   def unwrap(i,r,name=name):
    self.assertIs(i,info);self.assertIs(r,resources);trace.append(name)
    if name==names[-1]:raise Done()
    return i,r
   modules[name].unwrap_manifest=unwrap
  with patch.dict(sys.modules,modules),self.assertRaises(Done):self.function('verify_merged',source='maru_companion.py')(info,resources)
  self.assertEqual(trace,list(names))
 def test_refused_Key_bundle_gate_never_reaches_Width(self):
  modules={n:types.ModuleType(n)for n in('cas_catalog_unconsumed','cas_grid_width')};trace=[]
  def refuse(*args):trace.append('key');raise ValueError('Exact Key refused')
  def forbidden(*args):raise AssertionError('Refusal fell through to Width')
  modules['cas_catalog_unconsumed'].unwrap_manifest=refuse;modules['cas_grid_width'].unwrap_manifest=forbidden
  with patch.dict(sys.modules,modules),self.assertRaisesRegex(ValueError,'Exact Key refused'):
   self.function('verify_merged',source='maru_companion.py')({}, {})
  self.assertEqual(trace,['key'])
 def test_current_Width_provider_verifies_without_recompiling(self):
  calls=[];proof={width.CONTRACT:{}};module=types.ModuleType('cas_grid_width')
  module.verify_adapter=lambda *args:calls.append(('verify',args))
  module.adapt=lambda *args:(_ for _ in()).throw(AssertionError('Current provider compiled'))
  ns={'Path':Path,'_finish_grid_provider_eof':lambda *args:(_ for _ in()).throw(AssertionError('Current provider downgraded'))}
  with patch.dict(sys.modules,{'cas_grid_width':module}):result=self.function('finish_grid_provider',ns)(proof,b'final','native','ffdec',Path('work'))
  self.assertEqual(result,(b'final',proof));self.assertEqual(calls,[('verify',(proof,b'final'))])
 def test_EOF_prefix_continues_only_missing_Width_and_consumes_returned_bytes(self):
  calls=[];prior={'eof_delta_contract':{}};current={width.CONTRACT:{}};module=types.ModuleType('cas_grid_width')
  module.verify_adapter=lambda *args:(_ for _ in()).throw(AssertionError('Prefix relabeled current'))
  module.adapt=lambda *args:(calls.append(('width',args))or(b'Width',current))
  def eof(*args):calls.append(('eof',args));return b'EOF',prior
  ns={'Path':Path,'_finish_grid_provider_eof':eof}
  with patch.dict(sys.modules,{'cas_grid_width':module}):result=self.function('finish_grid_provider',ns)(prior,b'cached','native','ffdec',Path('work'))
  self.assertEqual(result,(b'Width',current));self.assertEqual(calls[1],('width',(prior,b'EOF','native','ffdec',Path('work/view-width-transfer'))))
 def test_no_library_cache_or_provider_finish_ever_compiles_Main(self):
  for n in self.tree().body:
   if isinstance(n,ast.FunctionDef)and(n.name.startswith(('finish_grid_provider','_finish_grid_provider'))or n.name=='verified_library_cache'):
    with self.subTest(helper=n.name):self.assertFalse(any(isinstance(c,ast.Call)and isinstance(c.func,ast.Attribute)and c.func.attr=='adapt_main'for c in ast.walk(n)))

if __name__=='__main__':unittest.main()
