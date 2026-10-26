"""Execute authenticated cached-provider continuation; no native compilation."""
from pathlib import Path
import ast
import hashlib
import os
import sys
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import dbpf_build,maru_companion
BUILD=Path(os.environ.get('APEX_CAS_GRID_BUDGET_BUILD_SOURCE',ROOT/'tools/cas_ui_build.py'))


class CacheTests(unittest.TestCase):
    def code(self,name):
        return next(n for n in ast.walk(ast.parse(BUILD.read_text()))
                    if isinstance(n,ast.FunctionDef) and n.name==name)

    def function(self,name,namespace):
        node=self.code(name)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(BUILD),'exec'),namespace)
        return namespace[name]

    def test_only_complete_current_or_authenticated_prefix_shapes_pass(self):
        gate=self.function('current_grid_stages',{})
        tail={}
        for key in reversed(('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract')):
            tail={key:{},'previous_stage_adapter':tail}
        budget={'budget_contract':{},'previous_stage_adapter':tail}
        current={'featured_contract':{},'previous_stage_adapter':budget}
        for value in (tail,budget,current):self.assertTrue(gate(value))
        for value in ({},tail['previous_stage_adapter'],{'budget_contract':None,'previous_stage_adapter':tail},
                      {'featured_contract':{},'previous_stage_adapter':tail},
                      {'featured_contract':None,'previous_stage_adapter':budget}):
            self.assertFalse(gate(value))

    def cached(self,stage='slice',refuse=None):
        calls=[];names=('cas_grid_slice','cas_grid_budget','cas_grid_featured')
        original={name:sys.modules.get(name) for name in names}
        for name in names:
            spy=types.ModuleType(name)
            def verify(*args,name=name):
                calls.append((name+'.verify',args))
                if refuse==name+'.verify':raise ValueError('Exact predecessor proof refused')
                return True
            def adapt(*args,name=name):
                calls.append((name+'.adapt',args))
                if refuse==name+'.adapt':raise ValueError('Exact terminal compile refused')
                contract='budget_contract' if name=='cas_grid_budget' else 'featured_contract'
                return name.encode(),{contract:{'ok':True},'previous_stage_adapter':args[0]}
            spy.verify_adapter=verify;spy.adapt=adapt;sys.modules[name]=spy
        try:
            with tempfile.TemporaryDirectory() as directory:
                native=Path(directory)/'original.swf';native.write_bytes(b'original')
                digest=hashlib.sha256(b'original').hexdigest()
                key=maru_companion.CANONICAL_GRID_LIBRARY;other=maru_companion.GRID_LIBRARY
                prior={stage+'_contract':{}}
                cache={'original_sha256':{key:digest,other:'0'*64},'used':set(),
                    'resources':{key:b'cached'},'providers':{dbpf_build.tgi(key):prior}}
                namespace=dict(Path=Path,hashlib=hashlib,dbpf_build=dbpf_build,maru_companion=maru_companion,
                    work=Path(directory),ffdec='ffdec')
                self.function('finish_grid_provider',namespace)
                function=self.function('adapt_grid_provider',namespace)
                if refuse:
                    with self.assertRaisesRegex(ValueError,'Exact (?:predecessor proof|terminal compile) refused'):
                        function(native,digest,'out.abc',cache)
                    result=None
                else:result=function(native,digest,'out.abc',cache)
                return result,calls,cache,prior,key
        finally:
            for name in names:
                if original[name] is None:sys.modules.pop(name,None)
                else:sys.modules[name]=original[name]

    def test_v345_cached_prefix_verifies_then_runs_only_missing_budget_and_featured(self):
        result,calls,cache,prior,key=self.cached()
        self.assertEqual([n for n,_ in calls],['cas_grid_slice.verify','cas_grid_budget.adapt','cas_grid_featured.adapt'])
        self.assertIs(calls[0][1][0],prior);self.assertEqual(calls[0][1][1],b'cached')
        self.assertEqual(calls[-1][1][1],b'cas_grid_budget')
        self.assertEqual(result[0],b'cas_grid_featured')
        self.assertEqual(cache['continued'],{dbpf_build.tgi(key)})

    def test_budget_cached_prefix_verifies_before_the_featured_compiler(self):
        result,calls,*_=self.cached('budget')
        self.assertEqual([n for n,_ in calls],['cas_grid_budget.verify','cas_grid_featured.adapt'])
        self.assertEqual(result[0],b'cas_grid_featured')

    def test_current_featured_resource_requires_full_verification_and_no_compile(self):
        result,calls,cache,prior,key=self.cached('featured')
        self.assertEqual(result,(b'cached',prior))
        self.assertEqual([n for n,_ in calls],['cas_grid_featured.verify'])
        self.assertNotIn('continued',cache)

    def test_refused_prefix_or_compiler_never_returns_stale_cached_bytes(self):
        for stage,refusal in (('slice','cas_grid_slice.verify'),('slice','cas_grid_budget.adapt'),
                              ('budget','cas_grid_budget.verify'),('budget','cas_grid_featured.adapt'),
                              ('featured','cas_grid_featured.verify')):
            with self.subTest(stage=stage,refusal=refusal):
                result,calls,*_=self.cached(stage,refusal)
                self.assertIsNone(result);self.assertEqual(calls[-1][0],refusal)

    def test_all_budget_sources_remain_in_exact_builder_pin_inventory(self):
        import cas_grid_budget as budget
        assignment=next(n for n in ast.parse(BUILD.read_text()).body if isinstance(n,ast.Assign) and
            any(isinstance(t,ast.Name) and t.id=='PINNED_SOURCES' for t in n.targets))
        self.assertTrue(set(budget.SOURCES)<=set(ast.literal_eval(assignment.value)))


if __name__=='__main__':unittest.main()
