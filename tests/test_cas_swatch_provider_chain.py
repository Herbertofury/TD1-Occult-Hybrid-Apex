"""Authenticate library swatch grafts and reconstruct the entire prior chain."""
from pathlib import Path
import copy,json,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import cas_swatch_provider as stage
import cas_swatch_geometry as swatch
import cas_catalog_binding as binding
import cas_communication_index as comm
import dbpf_build,maru_companion

class SwatchProviderChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=os.environ.get('APEX_SWATCH_PROVIDER_PROOFS')
        if fixture:
            cls.providers={};cls.resources={}
            for tgi in (maru_companion.GRID_LIBRARY,maru_companion.CANONICAL_GRID_LIBRARY):
                folder=Path(fixture)/format(tgi[2],'016X')
                cls.providers[dbpf_build.tgi(tgi)]=json.loads((folder/'adapter.json').read_text(encoding='utf-8'))
                cls.resources[tgi]=(folder/'final.swf').read_bytes()
        else:
            package=ROOT/'dist/candidate/ApexCASBridge.package'
            manifest_path=Path(str(package)+'.manifest.json')
            if not package.is_file() or not manifest_path.is_file():
                raise unittest.SkipTest('Private sealed CAS package and manifest required')
            manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
            cls.providers=manifest['grid_provider_adapters'];cls.resources=dbpf_build.read(package.read_bytes())
        # Current packages wrap this historical swatch layer. Authenticate
        # and raw-roll back only complete known terminal provider stages.
        import cas_grid_row_delta,cas_swatch_columns,cas_grid_staging_attach,cas_grid_publication
        import cas_grid_featured,cas_grid_budget,cas_grid_slice,cas_grid_scroll
        for module,contract in ((cas_grid_row_delta,'row_delta_contract'),
                                (cas_swatch_columns,'swatch_columns_contract'),
                                (cas_grid_staging_attach,'staging_attach_contract'),
                                (cas_grid_publication,'publication_trace_contract'),
                                (cas_grid_featured,'featured_contract'),
                                (cas_grid_budget,'budget_contract'),
                                (cas_grid_slice,'slice_contract'),
                                (cas_grid_scroll,'scroll_contract')):
            if any(isinstance(adapter,dict) and contract in adapter for adapter in cls.providers.values()):
                cls.providers,cls.resources,_=module.unwrap_providers(cls.providers,cls.resources)
        cls.key=dbpf_build.tgi(maru_companion.GRID_LIBRARY)

    def test_declaring_provider_appends_one_adapter_and_reconstructs_exact_progress_bytes(self):
        adapter=self.providers[self.key];final=self.resources[maru_companion.GRID_LIBRARY]
        self.assertTrue(stage.verify_adapter(adapter,final))
        prior,base=stage.historical(adapter,final)
        self.assertIn('progress_contract',prior)
        self.assertTrue(stage.previous.verify_adapter(prior,base))
        proof=adapter['swatch_provider_contract']
        self.assertIs(proof['provider_declares_swatch'],True)
        self.assertEqual((proof['appended_methods'],proof['appended_fields'],proof['changed_native_bodies']),(1,1,0))

    def test_nondeclaring_data_library_is_complete_unchanged_resource_not_a_fabricated_class(self):
        key=dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY);a=self.providers[key];raw=self.resources[maru_companion.CANONICAL_GRID_LIBRARY]
        prior,base=stage.historical(a,raw)
        self.assertEqual(base,raw);self.assertEqual(prior['patched_resource_sha256'],a['patched_resource_sha256'])
        proof=a['swatch_provider_contract'];self.assertIs(proof['provider_declares_swatch'],False)
        self.assertEqual((proof['appended_methods'],proof['appended_fields']),(0,0))
        abc=binding._ABC(binding._abc_payload(raw)[1]).parse()
        self.assertFalse(any(abc.qname(i['name'])=='7:ColorSwatchPanel:22:widgets.CAS.controls' for i in abc.instances))

    def test_missing_pins_history_and_rehashed_claims_refuse(self):
        base=self.providers[self.key];raw=self.resources[maru_companion.GRID_LIBRARY]
        changes=[lambda p:p.pop('source_sha256'),lambda p:p['source_sha256'].pop(stage.SOURCES[0]),
            lambda p:p.update(appended_methods=2),lambda p:p.update(changed_native_bodies=1),
            lambda p:p.update(provider_declares_swatch=False),lambda p:p.update(full_abc_rollback_exact=False),
            lambda p:p.update(original_provider_sha256=stage.ABSENT),lambda p:p['rollback'].update(scope=99)]
        for change in changes:
            a=copy.deepcopy(base);p=a['swatch_provider_contract'];change(p);a['postproof_sha256']=comm.contract_digest(p)
            with self.subTest(proof=p),self.assertRaises(ValueError):stage.verify_adapter(a,raw)
        a=copy.deepcopy(base);a['previous_stage_adapter'].pop('progress_contract')
        a['previous_stage_sha256']=comm.contract_digest(a['previous_stage_adapter'])
        a['swatch_provider_contract']['previous_stage_sha256']=a['previous_stage_sha256']
        a['postproof_sha256']=comm.contract_digest(a['swatch_provider_contract'])
        with self.assertRaises(ValueError):stage.verify_adapter(a,raw)

    def test_rehashed_executable_helper_mutation_cannot_authorize_wrong_geometry(self):
        from cas_ui_build import replace_payload
        a=copy.deepcopy(self.providers[self.key]);final=self.resources[maru_companion.GRID_LIBRARY]
        prefix,raw=binding._abc_payload(final);abc=binding._ABC(raw).parse();body=swatch.method(abc,'ColorSwatchPanel','ApexSwatchGeometry')[2]['value']['code']
        self.assertEqual(raw.count(body),1)
        instructions=abc.instructions(body);first=next(row for row in instructions if row[2]==0x24 and tuple(row[3])==(2,))
        changed=bytearray(body);changed[first[0]+1]=3;mutated=raw.replace(body,bytes(changed),1)
        final=replace_payload(final,prefix+mutated);p=a['swatch_provider_contract']
        p.update(abc_sha256=stage.sha(mutated),final_swf_sha256=stage.sha(final))
        a.update(patched_resource_sha256=stage.sha(final),postproof_sha256=comm.contract_digest(p))
        with self.assertRaisesRegex(ValueError,'method differs'):stage.verify_adapter(a,final)

    def test_manifest_requires_both_complete_providers_and_full_new_source_inventory(self):
        info=dict(source_pins=stage.pins(),grid_provider_adapters=self.providers,
            companion_code_merge=dict(grid_library_adapter=self.providers[self.key]),
            patched_resources={k:a['patched_resource_sha256'] for k,a in self.providers.items()})
        old,resources=stage.unwrap_manifest(info,self.resources)
        self.assertNotIn('swatch_provider_contract',old['grid_provider_adapters'][self.key])
        for mutate in (lambda i:i['source_pins'].pop(stage.SOURCES[0]),lambda i:i['grid_provider_adapters'].pop(self.key),
                       lambda i:i['grid_provider_adapters'][self.key].pop('swatch_provider_contract')):
            changed=copy.deepcopy(info);mutate(changed)
            with self.assertRaises(ValueError):stage.unwrap_manifest(changed,self.resources)

if __name__=='__main__':unittest.main()
