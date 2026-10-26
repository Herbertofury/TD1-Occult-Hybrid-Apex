"""Authenticate both terminal build seams without a game or compiler fixture."""
from pathlib import Path
import ast,sys,types,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cas_grid_eof,cas_catalog_authority
import cas_grid_width,cas_catalog_unconsumed

class AuthorityBuildIntegrationTests(unittest.TestCase):
    def tree(self):return ast.parse((ROOT/'tools/cas_ui_build.py').read_text(encoding='utf-8'))
    def calls(self):
        names={'frame_status_main_contract','catalog_authority_main_contract'};found={}
        for n in ast.walk(self.tree()):
            if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Tuple)and isinstance(n.value,ast.Call):
                keys=[x.id for x in n.targets[0].elts if isinstance(x,ast.Name)]
                if len(keys)==2 and keys[1]in names:found[keys[1]]=n
        self.assertEqual(set(found),names);return found
    def test_all_new_terminal_sources_are_pinned_once(self):
        pins=next(ast.literal_eval(n.value)for n in self.tree().body if isinstance(n,ast.Assign)and
                  any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
        self.assertEqual(len(set(cas_grid_eof.SOURCES+cas_catalog_authority.SOURCES)),len(cas_grid_eof.SOURCES+cas_catalog_authority.SOURCES))
        for n in cas_grid_eof.SOURCES+cas_catalog_authority.SOURCES:self.assertEqual(pins.count(n),1,n)
    def test_fresh_main_uses_exact_frame_predecessor_and_same_injected_source(self):
        calls=self.calls();before=calls['frame_status_main_contract'];current=calls['catalog_authority_main_contract']
        self.assertLess(before.lineno,current.lineno)
        self.assertEqual(ast.dump(current.value.func),ast.dump(ast.parse('cas_catalog_authority.adapt_main').body[0].value))
        self.assertEqual([ast.dump(a)for a in current.value.args[:4]],
                         [ast.dump(ast.Name(id=n,ctx=ast.Load()))for n in('frame_status_main_contract','payload','patched','ffdec')])
        self.assertEqual(ast.literal_eval(current.value.args[4].right),'catalog-authority-main')
    def test_actual_main_assignment_consumes_returned_frame_bytes(self):
        nodes=sorted(self.calls().values(),key=lambda n:n.lineno);calls=[];prior=object();frame=object();authority=object();source=object();ffdec=object()
        def inner(*args):calls.append(('frame',args));return b'exact-frame-main',frame
        def outer(*args):calls.append(('authority',args));return b'exact-authority-main',authority
        ns={'catalog_list_insets_main_contract':prior,'payload':b'list-insets-main','patched':source,'ffdec':ffdec,'work':Path('work'),
            'cas_grid_frame_status':types.SimpleNamespace(adapt_main=inner),'cas_catalog_authority':types.SimpleNamespace(adapt_main=outer)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'fresh-main','exec'),ns)
        self.assertEqual(calls[1],('authority',(frame,b'exact-frame-main',source,ffdec,Path('work/catalog-authority-main'))))
        self.assertIs(ns['catalog_authority_main_contract'],authority);self.assertEqual(ns['payload'],b'exact-authority-main')
    def test_refused_main_terminal_never_returns_predecessor(self):
        node=self.calls()['catalog_authority_main_contract'];before=object()
        def refuse(*args):raise ValueError('Exact authority proof refused')
        ns={'frame_status_main_contract':object(),'payload':before,'patched':object(),'ffdec':object(),'work':Path('work'),
            'cas_catalog_authority':types.SimpleNamespace(adapt_main=refuse)}
        with self.assertRaisesRegex(ValueError,'Exact authority proof refused'):
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'fresh-main','exec'),ns)
        self.assertIs(ns['payload'],before);self.assertNotIn('catalog_authority_main_contract',ns)
    def test_manifest_exposes_exact_main_terminal(self):
        rows=[]
        for n in ast.walk(self.tree()):
            if isinstance(n,ast.Dict):rows.extend(v for k,v in zip(n.keys,n.values)if isinstance(k,ast.Constant)and k.value==cas_catalog_authority.MANIFEST)
        self.assertEqual(len(rows),1);self.assertIsInstance(rows[0],ast.Name);self.assertEqual(rows[0].id,'catalog_authority_main_contract')
    def verifier(self):
        path=ROOT/'tools/maru_companion.py';n=next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef)and n.name=='verify_merged')
        ns={};exec(compile(ast.fix_missing_locations(ast.Module(body=[n],type_ignores=[])),str(path),'exec'),ns);return ns['verify_merged']
    def test_merged_verifier_unwraps_main_and_provider_before_frame(self):
        class Done(Exception):pass
        calls=[];modules={n:types.ModuleType(n)for n in('cas_catalog_authority','cas_grid_eof','cas_grid_frame_status')}
        original=object();middle=object();resources=object()
        def main(info,res):self.assertIs(info,original);calls.append('authority');return middle,res
        def eof(info,res):self.assertIs(info,middle);calls.append('eof');return info,res
        def frame(info,res):self.assertIs(info,middle);calls.append('frame');raise Done()
        for n,fn in zip(modules,(main,eof,frame)):modules[n].unwrap_manifest=fn
        for outer_name in ("cas_catalog_unconsumed","cas_grid_width"):
            outer=types.ModuleType(outer_name);outer.unwrap_manifest=lambda info,res:(info,res);modules[outer_name]=outer
        with patch.dict(sys.modules,modules),self.assertRaises(Done):self.verifier()(original,resources)
        self.assertEqual(calls,['authority','eof','frame'])
    def test_refused_main_proof_never_runs_older_provider_or_frame(self):
        calls=[];modules={n:types.ModuleType(n)for n in('cas_catalog_authority','cas_grid_eof','cas_grid_frame_status')}
        def refuse(*args):calls.append('authority');raise ValueError('Exact authority refused')
        def forbidden(*args):raise AssertionError('Refusal fell through')
        modules['cas_catalog_authority'].unwrap_manifest=refuse
        modules['cas_grid_eof'].unwrap_manifest=modules['cas_grid_frame_status'].unwrap_manifest=forbidden
        for outer_name in ("cas_catalog_unconsumed","cas_grid_width"):
            outer=types.ModuleType(outer_name);outer.unwrap_manifest=lambda info,res:(info,res);modules[outer_name]=outer
        with patch.dict(sys.modules,modules),self.assertRaisesRegex(ValueError,'Exact authority refused'):self.verifier()({}, {})
        self.assertEqual(calls,['authority'])
    def test_provider_finish_never_compiles_main(self):
        for n in self.tree().body:
            if isinstance(n,ast.FunctionDef)and(n.name.startswith('finish_grid_provider')or n.name.startswith('_finish_grid_provider')or n.name=='verified_library_cache'):
                with self.subTest(helper=n.name):self.assertFalse(any(isinstance(c,ast.Call)and isinstance(c.func,ast.Attribute)and c.func.attr=='adapt_main'for c in ast.walk(n)))
    def test_exact_current_provider_verifies_without_compile(self):
        from tests.test_cas_grid_budget_cache import CacheTests
        result,calls,cache,prior,key=CacheTests('runTest').cached('eof')
        self.assertEqual([n for n,_ in calls],['cas_grid_eof.verify','cas_grid_width.adapt']);self.assertEqual(result[0],b'cas_grid_width');self.assertIs(result[1]['previous_stage_adapter'],prior);self.assertIn('continued',cache)
    def test_frame_prefix_runs_only_missing_eof_compiler(self):
        from tests.test_cas_grid_budget_cache import CacheTests
        result,calls,cache,prior,key=CacheTests('runTest').cached('frame-status')
        self.assertEqual([n for n,_ in calls],['cas_grid_frame_status.verify','cas_grid_eof.adapt','cas_grid_width.adapt'])
        self.assertEqual(result[0],b'cas_grid_width');self.assertIs(result[1]['previous_stage_adapter']['previous_stage_adapter'],prior);self.assertIn('continued',cache)
    def test_refused_eof_compile_never_returns_cached_predecessor(self):
        from tests.test_cas_grid_budget_cache import CacheTests
        result,calls,*_=CacheTests('runTest').cached('frame-status','cas_grid_eof.adapt')
        self.assertIsNone(result);self.assertEqual([n for n,_ in calls],['cas_grid_frame_status.verify','cas_grid_eof.adapt'])

if __name__=='__main__':unittest.main()
