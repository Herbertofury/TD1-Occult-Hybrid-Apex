"""Execute every authenticated cache prefix through all missing terminal stages."""
from pathlib import Path
import ast,hashlib,os,sys,tempfile,types,unittest
ROOT=Path(__file__).resolve().parents[1]
PROJECT=next(parent for parent in (ROOT,*ROOT.parents)if(parent/'tools/cas_grid_budget.py').is_file())
sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tools')]
import dbpf_build,maru_companion
BUILD=Path(os.environ.get('APEX_CAS_GRID_BUDGET_BUILD_SOURCE',ROOT/'tools/cas_ui_build.py'))
STAGES=(('slice','cas_grid_slice','slice_contract'),('budget','cas_grid_budget','budget_contract'),
        ('featured','cas_grid_featured','featured_contract'),('publication','cas_grid_publication','publication_trace_contract'),
        ('staging-attach','cas_grid_staging_attach','staging_attach_contract'),
        ('swatch-columns','cas_swatch_columns','swatch_columns_contract'))


class CacheTests(unittest.TestCase):
    def code(self,name):
        return next(n for n in ast.walk(ast.parse(BUILD.read_text(encoding='utf-8')))
                    if isinstance(n,ast.FunctionDef)and n.name==name)

    def function(self,name,namespace):
        node=self.code(name)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(BUILD),'exec'),namespace)
        return namespace[name]

    def test_only_complete_current_or_authenticated_prefix_shapes_pass(self):
        gate=self.function('current_grid_stages',{});tail={}
        for key in reversed(('slice_contract','scroll_contract','swatch_provider_contract','progress_contract','product_rows_contract')):
            tail={key:{},'previous_stage_adapter':tail}
        self.assertTrue(gate(tail));prefixes=[tail]
        for _,_,contract in STAGES[1:]:
            tail={contract:{},'previous_stage_adapter':tail}
            if contract=='staging_attach_contract':tail['previous_stage_kind']='publication'
            prefixes.append(tail);self.assertTrue(gate(tail))
        for index,(_,_,contract)in enumerate(STAGES[1:],1):
            for invalid in ({contract:None,'previous_stage_adapter':prefixes[index-1]},
                            {contract:{},'previous_stage_adapter':{}},
                            {contract:{},'previous_stage_adapter':prefixes[0]}if index>1 else {}):
                with self.subTest(contract=contract,invalid=invalid):self.assertFalse(gate(invalid))
        self.assertFalse(gate(prefixes[0]['previous_stage_adapter']))

    def cached(self,stage='slice',refuse=None,skin_kind='staging-attach',attach_kind='publication'):
        calls=[];names=tuple(name for _,name,_ in STAGES)
        original={name:sys.modules.get(name)for name in names};contracts={name:contract for _,name,contract in STAGES}
        for name in names:
            spy=types.ModuleType(name)
            def verify(*args,name=name):
                calls.append((name+'.verify',args))
                if refuse==name+'.verify':raise ValueError('Exact predecessor proof refused')
                return True
            def adapt(*args,name=name):
                calls.append((name+'.adapt',args))
                if refuse==name+'.adapt':raise ValueError('Exact terminal compile refused')
                adapter={contracts[name]:{'previous_stage_kind':'staging-attach'},'previous_stage_adapter':args[0]}
                if name=='cas_grid_staging_attach':adapter['previous_stage_kind']='publication'
                return name.encode(),adapter
            spy.verify_adapter=verify;spy.adapt=adapt;sys.modules[name]=spy
        try:
            with tempfile.TemporaryDirectory()as directory:
                native=Path(directory)/'original.swf';native.write_bytes(b'original');digest=hashlib.sha256(b'original').hexdigest()
                key=maru_companion.CANONICAL_GRID_LIBRARY;other=maru_companion.GRID_LIBRARY
                contract=next(contract for label,_,contract in STAGES if label==stage)
                prior={contract:{'previous_stage_kind':skin_kind}}
                if stage=='staging-attach':prior['previous_stage_kind']=attach_kind
                cache={'original_sha256':{key:digest,other:'0'*64},'used':set(),
                       'resources':{key:b'cached'},'providers':{dbpf_build.tgi(key):prior}}
                namespace=dict(Path=Path,hashlib=hashlib,dbpf_build=dbpf_build,maru_companion=maru_companion,
                               work=Path(directory),ffdec='ffdec')
                self.function('finish_grid_provider',namespace);function=self.function('adapt_grid_provider',namespace)
                if refuse:
                    with self.assertRaisesRegex(ValueError,'Exact (?:predecessor proof|terminal compile) refused'):
                        function(native,digest,'out.abc',cache)
                    result=None
                elif stage=='swatch-columns'and skin_kind!='staging-attach':
                    with self.assertRaisesRegex(ValueError,'Historical Skin fixture'):
                        function(native,digest,'out.abc',cache)
                    result=None
                elif stage=='staging-attach'and attach_kind!='publication':
                    with self.assertRaisesRegex(ValueError,'Production Attach requires Publication predecessor'):
                        function(native,digest,'out.abc',cache)
                    result=None
                else:result=function(native,digest,'out.abc',cache)
                return result,calls,cache,prior,key
        finally:
            for name in names:
                if original[name]is None:sys.modules.pop(name,None)
                else:sys.modules[name]=original[name]

    def test_every_exact_prefix_verifies_then_runs_only_missing_terminal_compilers(self):
        for index,(stage,name,_)in enumerate(STAGES):
            with self.subTest(stage=stage):
                result,calls,cache,prior,key=self.cached(stage)
                self.assertEqual([label for label,_ in calls],
                                 [name+'.verify']+[name+'.adapt'for _,name,_ in STAGES[index+1:]])
                self.assertIs(calls[0][1][0],prior);self.assertEqual(calls[0][1][1],b'cached')
                for step in range(1,len(calls)):
                    expected=b'cached'if step==1 else STAGES[index+step-1][1].encode()
                    self.assertEqual(calls[step][1][1],expected)
                if index==len(STAGES)-1:
                    self.assertEqual(result,(b'cached',prior));self.assertNotIn('continued',cache)
                else:
                    self.assertEqual(result[0],b'cas_swatch_columns')
                    self.assertEqual(cache['continued'],{dbpf_build.tgi(key)})

    def test_refused_prefix_or_any_terminal_compiler_never_returns_stale_cached_bytes(self):
        for index,(stage,name,_)in enumerate(STAGES):
            for refusal in [name+'.verify']+[name+'.adapt'for _,name,_ in STAGES[index+1:]]:
                with self.subTest(stage=stage,refusal=refusal):
                    result,calls,*_=self.cached(stage,refusal)
                    self.assertIsNone(result);self.assertEqual(calls[-1][0],refusal)

    def test_historical_featured_skin_cannot_enter_current_production_cache(self):
        result,calls,*_=self.cached('swatch-columns',skin_kind='featured-fixture')
        self.assertIsNone(result);self.assertEqual([name for name,_ in calls],['cas_swatch_columns.verify'])

    def test_historical_featured_attach_cannot_enter_current_production_cache(self):
        result,calls,*_=self.cached('staging-attach',attach_kind='featured-fixture')
        self.assertIsNone(result);self.assertEqual(calls,[])

    def test_all_budget_sources_remain_in_exact_builder_pin_inventory(self):
        import cas_grid_budget as budget
        assignment=next(n for n in ast.parse(BUILD.read_text(encoding='utf-8')).body if isinstance(n,ast.Assign)and
                        any(isinstance(t,ast.Name)and t.id=='PINNED_SOURCES'for t in n.targets))
        self.assertTrue(set(budget.SOURCES)<=set(ast.literal_eval(assignment.value)))


if __name__=='__main__':unittest.main()
