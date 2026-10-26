"""Strict Main-only scheduling capability; compiled fixture is opt-in."""
from pathlib import Path
import copy
import json
import os
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import cas_catalog_schedule as schedule
import cas_catalog_binding as binding
import cas_grid_presentation as presentation
import cas_communication_index as comm
import cas_grid_pool as pool
from cas_ui_build import replace_payload


class CatalogSchedulingSourceTests(unittest.TestCase):
    def test_exact_eight_two_main_only_inventory_and_source_pins(self):
        self.assertEqual(len(schedule.stage.REPLACED),8)
        self.assertEqual(len(schedule.stage.ADDED),2)
        self.assertEqual(set(schedule.semantic_pins(schedule.MAIN)),set(schedule.stage.REPLACED+schedule.stage.ADDED))
        self.assertEqual(len(schedule.pins()),4)
        with self.assertRaisesRegex(ValueError,'Main-only'):
            schedule.inventory('olympus.layout.RecyclingGridLayout')

    def test_inactive_bootstrap_and_status_contracts_are_in_executed_owned_source(self):
        source=schedule.stage.fragment()
        for name in schedule.stage.REPLACED+schedule.stage.ADDED:
            start,end=pool.method_extent(source,name)
            self.assertIn('function '+name+'(',source[start:end])
        self.assertNotIn('SetNativeData',source)
        self.assertNotIn('MenuType_SUBMENU',source)
        self.assertIn('width_receipt_valid',source)
        self.assertIn('actual_repair_path',source)
        self.assertIn('ApexGridStep(1,0)',source.replace(' ',''))

    def test_legacy_or_partial_admission_refuses_before_any_compile(self):
        with mock.patch.object(schedule.comm,'run')as run:
            for prior in ({},None,{'row_delta_contract':{}}):
                with self.subTest(prior=prior),self.assertRaisesRegex(ValueError,'current Intrinsic'):
                    schedule.adapt_main(prior,b'',Path('missing'),Path('missing'),Path('missing'))
            run.assert_not_called()

    def test_unmarked_manifest_is_identity_but_any_partial_source_marker_refuses(self):
        info={'unrelated':1};resources={(1,2,3):b'keep'}
        self.assertEqual(schedule.unwrap_manifest(info,resources),(info,resources))
        for name in schedule.SOURCES:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'missing/partial/stale'):
                schedule.unwrap_manifest({'source_pins':{name:'0'*64}},resources)
        with self.assertRaisesRegex(ValueError,'missing/partial/stale'):
            schedule.unwrap_manifest({schedule.MANIFEST:{}},resources)

    def test_previous_source_exact_body_authentication_and_duplicate_helper_refusal(self):
        # A missing/forged method never reaches an appended helper or partial edit.
        for name in schedule.stage.REPLACED:
            body='private function '+name+'():void{}'
            with self.subTest(name=name),self.assertRaises(ValueError):
                schedule.stage.inject_main('package x {class Y {\n'+body+'\n   }\n}')


@unittest.skipUnless(os.environ.get('APEX_CAS_SCHEDULE_FIXTURE_DIR'),'Explicit matching compiled scheduling fixture required')
class CatalogSchedulingCompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=Path(os.environ['APEX_CAS_SCHEDULE_FIXTURE_DIR'])
        cls.contract=json.loads((folder/'contract.json').read_text())
        cls.final=(folder/'final.swf').read_bytes()
        cls.base=(folder/'baseline.swf').read_bytes()
        cls.prior=json.loads((folder/'previous.json').read_text())

    def mutate(self,owner,method):
        prefix,raw=binding._abc_payload(self.final)
        abc=schedule.mechanics.ABC(raw).parse()
        body=presentation.named(abc,owner,method)[1]
        at=raw.find(body['value']['code'],body['start'],body['end'])
        self.assertGreaterEqual(at,body['start'])
        changed=bytearray(raw)
        changed[at]=0xd1 if changed[at]==0xd0 else 0x27
        final=replace_payload(self.final,prefix+bytes(changed))
        contract=copy.deepcopy(self.contract)
        proof=contract[schedule.CONTRACT]
        proof['final_swf_sha256']=schedule.sha(final)
        proof['abc_sha256']=schedule.sha(binding._abc_payload(final)[1])
        contract['final_swf_sha256']=schedule.sha(final)
        contract['postproof_sha256']=comm.contract_digest(proof)
        return contract,final

    def test_actual_complete_raw_rollback_and_full_recursive_predecessor(self):
        self.assertTrue(schedule.verify_main(self.contract,self.final))
        prior,base=schedule.historical(self.contract,self.final)
        self.assertEqual(prior,self.prior)
        self.assertEqual(base,self.base)

    def test_all_ten_owned_cfg_changes_refuse_even_with_reforged_outer_hashes(self):
        for method in schedule.stage.REPLACED+schedule.stage.ADDED:
            with self.subTest(method=method),self.assertRaisesRegex(ValueError,'semantic/CFG'):
                schedule.verify_main(*self.mutate(schedule.MAIN,method))

    def test_original_native_body_change_cannot_be_laundered_through_rollback(self):
        with self.assertRaisesRegex(ValueError,'predecessor bytes'):
            schedule.verify_main(*self.mutate(schedule.MAIN,'OnEnterState'))

    def test_every_required_envelope_and_exact_predecessor_field_is_mandatory(self):
        for key,value in [('source_sha256',{}),('rollback',{}),('whole_abc_rollback_verified',False),
                          ('all_unowned_bodies_retained',False),('native_protected_bindings_verified',False),
                          ('serialized_owned_bodies_verified',False),('runtime_class_QName_verified',True),
                          ('runtime_qualified',True),('performance_gain_claimed',True),('appended_fields',1),
                          ('appended_methods',3),('changed_original_native_bodies',1),('replaced_owned_bodies',7)]:
            bad=copy.deepcopy(self.contract);bad[schedule.CONTRACT][key]=value
            bad['postproof_sha256']=comm.contract_digest(bad[schedule.CONTRACT])
            with self.subTest(key=key),self.assertRaises(ValueError):schedule.verify_main(bad,self.final)
        bad=copy.deepcopy(self.contract);bad['previous_stage_contract'].pop('intrinsic_geometry_contract')
        with self.assertRaises(ValueError):schedule.verify_main(bad,self.final)

    def test_manifest_rolls_only_main_and_preserves_both_provider_values_and_unknown_fields(self):
        import dbpf_build,maru_companion
        main=maru_companion.CUSTOMIZER
        resources={main:self.final,maru_companion.GRID_LIBRARY:b'donor-exact',maru_companion.CANONICAL_GRID_LIBRARY:b'canonical-exact'}
        info={'source_pins':schedule.pins(),schedule.MANIFEST:self.contract,
              'intrinsic_geometry_main_native_bytecode_contract':self.prior,
              'patched_resource_sha256':schedule.sha(self.final),'unknown':{'opaque':[1,2,'preserve']},
              'patched_resources':{dbpf_build.tgi(k):schedule.sha(v)for k,v in resources.items()}}
        before=copy.deepcopy(info)
        updated,restored=schedule.unwrap_manifest(info,resources)
        self.assertEqual(info,before)
        self.assertEqual(restored[main],self.base)
        for key in resources:
            if key!=main:self.assertIs(restored[key],resources[key])
        self.assertEqual(updated['unknown'],info['unknown'])
        self.assertEqual(updated[schedule.MANIFEST],info[schedule.MANIFEST])
        for field,value in [('intrinsic_geometry_main_native_bytecode_contract',{}),('patched_resource_sha256','0'*64)]:
            bad=copy.deepcopy(info);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):schedule.unwrap_manifest(bad,resources)


if __name__=='__main__':unittest.main()
