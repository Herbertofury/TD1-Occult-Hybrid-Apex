"""Optional full bytecode/raw rollback qualification, never game access."""
from pathlib import Path
import copy,json,os,sys,unittest
REPO=next(p for p in Path(__file__).resolve().parents if(p/'tools/dbpf_build.py').is_file())
ROOT=Path(os.environ.get('APEX_CATALOG_AUTHORITY_SOURCE_ROOT',REPO)).resolve()
sys.path[:0]=[str(ROOT/'tools'),str(REPO/'tools')]
import cas_catalog_authority as module,cas_catalog_binding as binding,cas_grid_presentation as presentation
from cas_ui_build import replace_payload
FIXTURE=os.environ.get('APEX_CATALOG_AUTHORITY_FIXTURE_ROOT')

@unittest.skipUnless(FIXTURE,'Explicit authenticated compiled Main fixture not supplied')
class AuthorityChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(FIXTURE);cls.final=(cls.path/'final.swf').read_bytes();cls.base=(cls.path/'baseline.swf').read_bytes()
        cls.contract=json.loads((cls.path/'contract.json').read_bytes())
    def test_exact_current_frame_predecessor_and_complete_raw_rollback(self):
        self.assertTrue(module.verify_main(self.contract,self.final));prior,base=module.historical(self.contract,self.final)
        self.assertEqual(base,self.base);self.assertTrue(module.previous.verify_main(prior,base))
    def mutate(self,name):
        prefix,raw=binding._abc_payload(self.final);a=module.mechanics.ABC(raw).parse();_,row=presentation.named(a,module.MAIN,name)
        code=row['value']['code'];at=raw.find(code,row['start'],row['end']);self.assertGreaterEqual(at,0)
        data=bytearray(raw);data[at]=0xd1 if data[at]==0xd0 else 0x27
        return replace_payload(self.final,prefix+bytes(data))
    def rehash(self,contract,final):
        c=copy.deepcopy(contract);p=c[module.CONTRACT];p['final_swf_sha256']=module.sha(final)
        p['abc_sha256']=module.sha(binding._abc_payload(final)[1]);c['final_swf_sha256']=module.sha(final)
        c['postproof_sha256']=module.comm.contract_digest(p);return c
    def test_every_owned_body_and_unowned_native_body_reject_rehashed_mutation(self):
        for name in module.stage.REPLACED+module.stage.ADDED+('SetState',):
            final=self.mutate(name)
            with self.subTest(name=name),self.assertRaises(ValueError):module.verify_main(self.rehash(self.contract,final),final)
    def test_incomplete_stale_or_forged_source_pins_refuse(self):
        for name in module.SOURCES:
            for action in ('remove','stale'):
                c=copy.deepcopy(self.contract);pins=c[module.CONTRACT]['source_sha256']
                pins.pop(name)if action=='remove'else pins.__setitem__(name,'0'*64)
                c['postproof_sha256']=module.comm.contract_digest(c[module.CONTRACT])
                with self.subTest(name=name,action=action),self.assertRaises(ValueError):module.verify_main(c,self.final)
    def test_counts_full_rollback_authority_and_unqualified_claims_cannot_be_forged(self):
        facts={'appended_fields':1,'appended_methods':0,'replaced_owned_bodies':0,'changed_original_native_bodies':1,
               'whole_abc_rollback_verified':False,'all_unowned_bodies_retained':False,'serialized_owned_bodies_verified':False,
               'native_protected_bindings_verified':False,'runtime_class_QName_verified':False,
               'runtime_qualified':True,'performance_gain_claimed':True}
        for key,value in facts.items():
            c=copy.deepcopy(self.contract);c[module.CONTRACT][key]=value;c['postproof_sha256']=module.comm.contract_digest(c[module.CONTRACT])
            with self.subTest(key=key),self.assertRaises(ValueError):module.verify_main(c,self.final)
    def test_predecessor_downgrade_and_wrong_original_callable_cannot_be_laundered(self):
        c=copy.deepcopy(self.contract);c['previous_stage_contract']=c['previous_stage_contract']['previous_stage_contract']
        c['previous_stage_sha256']=module.comm.contract_digest(c['previous_stage_contract'])
        with self.assertRaises(ValueError):module.verify_main(c,self.final)
        for name in module.stage.REPLACED:
            c=copy.deepcopy(self.contract);c[module.CONTRACT]['rollback']['bodies'].pop(name)
            c['postproof_sha256']=module.comm.contract_digest(c[module.CONTRACT])
            with self.subTest(name=name),self.assertRaises(ValueError):module.verify_main(c,self.final)
    def test_all_appended_helpers_are_private_and_original_instance_fields_unchanged(self):
        _,raw=binding._abc_payload(self.final);a=module.mechanics.ABC(raw).parse()
        _,old=binding._abc_payload(self.base);b=module.mechanics.ABC(old).parse()
        for name in module.stage.ADDED:
            trait,body=presentation.named(a,module.MAIN,name);info=a.methods['rows'][body['value']['method']]['value']
            self.assertEqual(trait['value']['flags'],1);self.assertEqual(a.qname(trait['value']['name']),
                 '7:'+name+':5:widgets.CAS.Customizer:CASCustomizerMain');self.assertEqual(info['optional'],[])
        self.assertEqual(a.methods['count']-b.methods['count'],8);self.assertEqual(a.bodies['count']-b.bodies['count'],8)
    def info(self):
        import maru_companion,dbpf_build
        key=maru_companion.CUSTOMIZER;resources={key:self.final,(1,0,99):b'unrelated immutable bytes'}
        info={'source_pins':module.pins(),module.MANIFEST:self.contract,module.previous.MANIFEST:self.contract['previous_stage_contract'],
              'patched_resource_sha256':module.sha(self.final),'patched_resources':{dbpf_build.tgi(key):module.sha(self.final)}}
        return info,resources
    def test_manifest_restores_only_exact_main_and_preserves_unrelated_resources(self):
        import maru_companion
        info,resources=self.info();result,out=module.unwrap_manifest(info,resources)
        self.assertEqual(out[maru_companion.CUSTOMIZER],self.base);self.assertEqual(out[(1,0,99)],resources[(1,0,99)])
        self.assertEqual(result['patched_resource_sha256'],module.sha(self.base))
    def test_manifest_partial_pins_missing_alias_and_wrong_advertised_bytes_refuse(self):
        info,resources=self.info()
        for name in module.SOURCES:
            c=copy.deepcopy(info);del c['source_pins'][name]
            with self.subTest(name=name),self.assertRaises(ValueError):module.unwrap_manifest(c,resources)
        for name in (module.MANIFEST,module.previous.MANIFEST,'patched_resource_sha256'):
            c=copy.deepcopy(info);del c[name]
            with self.subTest(name=name),self.assertRaises(ValueError):module.unwrap_manifest(c,resources)

if __name__=='__main__':unittest.main()
