from pathlib import Path
import ast,copy,json,os,sys,types,unittest
from unittest.mock import patch
H=Path(__file__).resolve().parents[1];R=next(p for p in(H,*H.parents)if(p/'tools/cas_grid_featured.py').is_file());P=R/'.work/v347-publication-port'
sys.path[:0]=[str(H/'tools'),str(R/'tools')]+([str(P/'tools')]if H!=R else [])
import cas_grid_staging_attach as a
import cas_ui_build as ui
FIXTURE=Path(os.environ['APEX_CAS_STAGING_ATTACH_FIXTURE'])if os.environ.get('APEX_CAS_STAGING_ATTACH_FIXTURE')else(H/'publication-compiled'if H!=R and(H/'publication-compiled').is_dir()else None)
INTEGRATION=H/'integration'if(H/'integration/cas_ui_build.py').is_file()else R/'tools'


@unittest.skipUnless(FIXTURE is not None,'Set APEX_CAS_STAGING_ATTACH_FIXTURE for authenticated compiled Publication/Attach providers')
class CompiledAttachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows={}
        for suffix,adapter in json.loads((FIXTURE/'adapters.json').read_text()).items():
            w=FIXTURE/suffix;cls.rows[suffix]=(adapter,(w/'final.swf').read_bytes(),(w/'baseline.swf').read_bytes())
    def test_both_providers_restore_exact_full_publication_predecessor(self):
        for suffix,(adapter,final,base)in self.rows.items():
            with self.subTest(suffix=suffix):
                self.assertTrue(a.verify_adapter(adapter,final));prior,raw=a.historical(adapter,final)
                self.assertEqual(raw,base);self.assertTrue(a.verify_prior(prior,base,'publication'))
    def test_missing_stale_partial_pins_or_raw_rollback_refuse_even_rehashed(self):
        adapter,final,_=next(iter(self.rows.values()))
        for mode in('missing','stale','partial','rollback','kind','guarantee','count'):
            changed=copy.deepcopy(adapter);proof=changed['staging_attach_contract']
            if mode=='missing':proof.pop('source_sha256')
            elif mode=='stale':proof['source_sha256'][a.SOURCES[0]]='0'*64
            elif mode=='partial':proof['source_sha256'].pop(a.SOURCES[-1])
            elif mode=='rollback':proof['rollback']['bodies']={}
            elif mode=='kind':proof['previous_stage_kind']='unknown'
            elif mode=='guarantee':proof['whole_abc_rollback_verified']=False
            else:proof['new_fields']=False
            changed['postproof_sha256']=a.comm.contract_digest(proof)
            with self.assertRaises(ValueError,msg=mode):a.verify_adapter(changed,final)
    def test_rehashed_downgraded_predecessor_cannot_skip_publication(self):
        adapter,final,_=next(iter(self.rows.values()));changed=copy.deepcopy(adapter);prior=changed['previous_stage_adapter']['previous_stage_adapter']
        changed['previous_stage_adapter']=prior;changed['previous_stage_sha256']=a.comm.contract_digest(prior)
        proof=changed['staging_attach_contract'];proof['previous_stage_sha256']=changed['previous_stage_sha256'];changed['postproof_sha256']=a.comm.contract_digest(proof)
        with self.assertRaises(ValueError):a.verify_adapter(changed,final)
    def mutate(self,raw,name):
        prefix,data=a.binding._abc_payload(raw);abc=a.mechanics.ABC(data).parse();row=a.presentation.named(abc,a.GRID,name)[1];body=data[row['start']:row['end']];code=row['value']['code'];at=body.index(code)
        self.assertIn(code[-1],(0x47,0x48));new=code[:-1]+bytes([0x47 if code[-1]==0x48 else 0x48]);body=body[:at]+new+body[at+len(code):]
        return ui.replace_payload(raw,prefix+data[:row['start']]+body+data[row['end']:])
    def test_recomputed_final_hash_cannot_hide_owned_or_original_body_changes(self):
        adapter,final,_=next(iter(self.rows.values()))
        for name in('ApexGridAttach','ApexGridNow'):
            changed=copy.deepcopy(adapter);raw=self.mutate(final,name);proof=changed['staging_attach_contract'];proof['final_swf_sha256']=a.sha(raw);proof['abc_sha256']=a.sha(a.binding._abc_payload(raw)[1]);changed['patched_resource_sha256']=a.sha(raw);changed['postproof_sha256']=a.comm.contract_digest(proof)
            with self.assertRaises(ValueError,msg=name):a.verify_adapter(changed,raw)
    def test_production_unwrap_requires_both_publication_attach_providers(self):
        import dbpf_build,maru_companion
        evidence={f'62ECC59A:00000000:{k}':v[0]for k,v in self.rows.items()};resources={(0x62ECC59A,0,int(k,16)):v[1]for k,v in self.rows.items()}
        for mode in('missing','downgraded','historical'):
            altered=copy.deepcopy(evidence);key=next(iter(altered))
            if mode=='missing':altered.pop(key)
            elif mode=='downgraded':altered[key]=altered[key]['previous_stage_adapter']
            else:altered[key]['previous_stage_kind']='featured-fixture'
            with self.assertRaises(ValueError,msg=mode):a.unwrap_providers(altered,resources)
        old,raw,_=a.unwrap_providers(evidence,resources)
        self.assertTrue(all('publication_trace_contract'in row for row in old.values()))
        for key,row in old.items():self.assertEqual(a.sha(raw[tuple(int(n,16)for n in key.split(':'))]),row['patched_resource_sha256'])


class BuilderTests(unittest.TestCase):
    def function(self,name):
        source=(INTEGRATION/'cas_ui_build.py').read_text();tree=ast.parse(source)
        found=[n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name==name]
        self.assertEqual(len(found),1);namespace={'Path':Path};exec(compile(ast.fix_missing_locations(ast.Module(body=[found[0]],type_ignores=[])),str(INTEGRATION/'cas_ui_build.py'),'exec'),namespace);return namespace[name]
    def mocks(self,events):
        result={}
        for name,key in(('cas_swatch_columns','swatch_columns_contract'),('cas_grid_staging_attach','staging_attach_contract'),('cas_grid_publication','publication_trace_contract'),('cas_grid_featured','featured_contract'),('cas_grid_budget','budget_contract'),('cas_grid_slice','slice_contract')):
            module=types.ModuleType(name)
            def verify(prior,raw,n=name,k=key):events.append(('verify',n));self.assertIn(k,prior);return True
            def adapt(prior,raw,*args,n=name,k=key):events.append(('adapt',n));return raw+b'|'+n.encode(),{k:{},'previous_stage_kind':'publication','previous_stage_adapter':prior}
            module.verify_adapter=verify;module.adapt=adapt;result[name]=module
        return result
    def test_publication_prefix_continues_attach_without_recompiling_older_layers(self):
        fn=self.function('finish_grid_provider');events=[]
        with patch.dict(sys.modules,self.mocks(events)):
            raw,proof=fn({'publication_trace_contract':{}},b'pub',Path('original'),'ffdec',Path('private'))
        self.assertEqual(events,[('verify','cas_grid_publication'),('adapt','cas_grid_staging_attach'),('adapt','cas_swatch_columns')]);self.assertIn('swatch_columns_contract',proof)
    def test_verified_attach_prefix_continues_only_the_missing_skin_stage(self):
        fn=self.function('finish_grid_provider');events=[];prior={'staging_attach_contract':{},'previous_stage_kind':'publication'}
        with patch.dict(sys.modules,self.mocks(events)):raw,proof=fn(prior,b'final',Path('original'),'ffdec',Path('private'))
        self.assertIsNot(proof,prior);self.assertEqual(raw,b'final|cas_swatch_columns');self.assertEqual(events,[('verify','cas_grid_staging_attach'),('adapt','cas_swatch_columns')])
    def test_current_skin_final_verifies_without_recompilation(self):
        fn=self.function('finish_grid_provider');events=[];prior={'swatch_columns_contract':{'previous_stage_kind':'staging-attach'}}
        with patch.dict(sys.modules,self.mocks(events)):raw,proof=fn(prior,b'final',Path('original'),'ffdec',Path('private'))
        self.assertIs(proof,prior);self.assertEqual(raw,b'final');self.assertEqual(events,[('verify','cas_swatch_columns')])
    def test_featured_budget_slice_prefixes_reach_all_missing_terminal_layers(self):
        fn=self.function('finish_grid_provider')
        for key,expected in(('featured_contract',['cas_grid_publication','cas_grid_staging_attach','cas_swatch_columns']),('budget_contract',['cas_grid_featured','cas_grid_publication','cas_grid_staging_attach','cas_swatch_columns']),('slice_contract',['cas_grid_budget','cas_grid_featured','cas_grid_publication','cas_grid_staging_attach','cas_swatch_columns'])):
            events=[]
            with patch.dict(sys.modules,self.mocks(events)):_,proof=fn({key:{}},b'prefix',Path('original'),'ffdec',Path('private'))
            self.assertEqual([n for op,n in events if op=='adapt'],expected);self.assertIn('swatch_columns_contract',proof)
    def test_cache_shape_rejects_attach_over_wrong_predecessor(self):
        if FIXTURE is None:self.skipTest('Authenticated Attach fixture required')
        fn=self.function('current_grid_stages');adapter=next(iter(json.loads((FIXTURE/'adapters.json').read_text()).values()))
        self.assertTrue(fn(adapter));bad=copy.deepcopy(adapter);bad['previous_stage_adapter']=bad['previous_stage_adapter']['previous_stage_adapter'];self.assertFalse(fn(bad))
    def test_merged_verifier_unwraps_attach_before_publication(self):
        source=(INTEGRATION/'maru_companion.py').read_text();method=source[source.index('def verify_merged('):]
        self.assertLess(method.index('cas_swatch_columns.unwrap_manifest'),method.index('cas_grid_staging_attach.unwrap_manifest'))
        self.assertLess(method.index('cas_grid_staging_attach.unwrap_manifest'),method.index('cas_grid_publication.unwrap_manifest'))


if __name__=='__main__':unittest.main()
