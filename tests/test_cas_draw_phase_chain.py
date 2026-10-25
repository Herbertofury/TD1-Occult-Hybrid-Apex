"""Complete granular Main continuation/package gates without compiler calls."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
import cas_draw_phase as phase
import cas_catalog_binding as binding
import cas_communication_index as communication
import cas_ui_build as ui
import dbpf_build
import maru_companion
from test_cas_catalog_binding_chain import install_fixture as install_binding_fixture,historical_binding_fixture

WORK=ROOT/'.work/v337-draw-phases'
READY=all((WORK/name).is_file() for name in ('chained.json','baseline.swf','final.swf'))
KEY=maru_companion.CUSTOMIZER
TEXT=dbpf_build.tgi(KEY)


def fixture():return json.loads((WORK/'chained.json').read_text(encoding='utf-8')),(WORK/'final.swf').read_bytes()


def refresh(record):
    record['previous_stage_sha256']=communication.contract_digest(record['previous_stage_contract'])
    record['draw_phase_contract']['previous_stage_sha256']=record['previous_stage_sha256']
    record['postproof_sha256']=communication.contract_digest(record['draw_phase_contract'])


def install_fixture(info,resources):
    install_binding_fixture(info,resources)
    record,final=fixture()
    assert record['previous_stage_contract']==info['catalog_binding_native_bytecode_contract']
    assert binding.verify_contract(record['previous_stage_contract'],resources[KEY])
    info['draw_phase_native_bytecode_contract']=copy.deepcopy(record)
    info['source_pins'].update(record['draw_phase_contract']['source_sha256'])
    resources[KEY]=final
    info['patched_resource_sha256']=info['patched_resources'][TEXT]=phase.digest(final)
    return info,resources


@unittest.skipUnless(READY,'Frozen full granular Main continuation required')
class GranularContinuationTests(unittest.TestCase):
    def test_actual_final_reconstructs_full_binding_prior_and_honest_phase_inventory(self):
        record,final=fixture();self.assertTrue(phase.verify_contract(record,final))
        before=phase.reconstruct_previous(final,record['draw_phase_contract'])
        self.assertEqual(before,(WORK/'baseline.swf').read_bytes())
        self.assertTrue(binding.verify_contract(record['previous_stage_contract'],before))
        p=record['draw_phase_contract']
        self.assertEqual((p['changed_draw_bodies'],p['replaced_owned_bodies'],p['appended_methods'],p['appended_fields'],p['disabled_added_instructions'],p['granular_sites']),(1,2,0,0,0,47))
        self.assertEqual(p['phase_sites'],{'overlay':3,'geometry':9,'state':15,'context':11,'tooltip':9})
        self.assertIs(p['runtime_qualified'],False);self.assertIs(p['performance_gain_claimed'],False)
        self.assertNotEqual(phase.digest(final),record['previous_stage_contract']['final_swf_sha256'])
        for source in phase.SOURCES:self.assertIn(source,ui.source_pins())

    def test_rehashed_counts_source_retention_predicates_and_runtime_fidelity_cannot_be_forged(self):
        original,final=fixture()
        changes=[('ok',1),('phase','other'),('changed_draw_bodies',True),('changed_draw_bodies',0),('replaced_owned_bodies',1),
            ('appended_methods',False),('appended_methods',1),('appended_fields',True),('disabled_added_instructions',False),
            ('disabled_added_instructions',1),('granular_sites',46),('granular_sites',True),('disabled_fast_tail_exact',1),
            ('existing_profile_markers_retained',False),('native_cfg_projection_verified',False),('native_throw_propagation_retained',False),
            ('whole_abc_rollback_verified',False),('all_other_bodies_retained',False),('no_borrowed_handles_retained',False),
            ('baseline_swf_sha256','0'*64),('baseline_abc_sha256','0'*64),('abc_sha256','0'*64),
            ('helper_source_sha256','0'*64),('runtime_qualified',True),('performance_gain_claimed',True)]
        for name,value in changes:
            r=copy.deepcopy(original);r['draw_phase_contract'][name]=value;refresh(r)
            with self.subTest(field=name,value=value),self.assertRaises(ValueError):phase.verify_contract(r,final)
        for source in phase.SOURCES:
            r=copy.deepcopy(original);r['draw_phase_contract']['source_sha256'][source]='0'*64;refresh(r)
            with self.subTest(source=source),self.assertRaises(ValueError):phase.verify_contract(r,final)
        for value in (True,1,3.0):
            r=copy.deepcopy(original);r['draw_phase_contract']['phase_sites']['overlay']=value;refresh(r)
            with self.subTest(phase_count=value),self.assertRaises(ValueError):phase.verify_contract(r,final)

    def test_exact_prior_binding_corruption_or_substituted_bytes_cannot_relabel_a_main(self):
        original,final=fixture()
        for value in ((WORK/'baseline.swf').read_bytes(),final+b'extra'):
            with self.subTest(bytes=phase.digest(value)),self.assertRaises(ValueError):phase.verify_contract(original,value)
        r=copy.deepcopy(original);prior=r['previous_stage_contract'];prior['catalog_binding_contract']['other_four_binds_retained']=False
        prior['postproof_sha256']=communication.contract_digest(prior['catalog_binding_contract']);refresh(r)
        with self.assertRaises(ValueError):phase.verify_contract(r,final)
        r=copy.deepcopy(original);r['draw_phase_contract']['rollback']['pool_counts'][0]=True;refresh(r)
        with self.assertRaises(ValueError):phase.verify_contract(r,final)


@unittest.skipUnless(READY and (ROOT/'dist/candidate/ApexCASBridge.package').is_file(),'Private merged package required')
class GranularManifestTests(unittest.TestCase):
    def setUp(self):
        package=ROOT/'dist/candidate/ApexCASBridge.package'
        self.info=json.loads(Path(str(package)+'.manifest.json').read_text(encoding='utf-8'))
        self.resources=dbpf_build.read(package.read_bytes());install_fixture(self.info,self.resources)

    def test_current_sources_require_phase_binding_and_cell_history_on_actual_final_bytes(self):
        self.assertTrue(maru_companion.verify_merged(self.info,self.resources))
        r=self.info['draw_phase_native_bytecode_contract'];self.assertEqual(r['previous_stage_contract'],self.info['catalog_binding_native_bytecode_contract'])
        self.assertTrue(phase.verify_contract(r,self.resources[KEY]));self.assertEqual(phase.digest(self.resources[KEY]),r['final_swf_sha256'])

    def test_missing_partial_or_all_tool_pins_missing_marker_and_combined_stripping_refused(self):
        for names in ((phase.SOURCES[0],),(phase.SOURCES[1],),phase.SOURCES[:2],phase.SOURCES):
            info=copy.deepcopy(self.info)
            for name in names:info['source_pins'].pop(name,None)
            with self.subTest(sources=names),self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)
        info=copy.deepcopy(self.info);info.pop('draw_phase_native_bytecode_contract')
        with self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)
        for name in phase.SOURCES[:2]:info['source_pins'].pop(name,None)
        with self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)

    def test_current_phase_sources_refuse_earlier_main_or_removed_historical_prerequisites(self):
        info,resources=copy.deepcopy(self.info),dict(self.resources);historical_binding_fixture(info,resources)
        info['source_pins'].update(self.info['draw_phase_native_bytecode_contract']['draw_phase_contract']['source_sha256'])
        with self.assertRaises(ValueError):maru_companion.verify_merged(info,resources)
        for field in ('catalog_binding_native_bytecode_contract','cell_attach_native_bytecode_contract'):
            info=copy.deepcopy(self.info);info.pop(field)
            with self.subTest(prerequisite=field),self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)
        info=copy.deepcopy(self.info);info['cell_attach_native_bytecode_contract']['previous_chain_sha256']='0'*64
        with self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)

    def test_current_phase_authority_cannot_bypass_ancestor_gate_by_stripping_ancestor_source_markers(self):
        for names in (('tools/CasStructuralRolesPatch.java',),('tools/CasDrawFastPathPatch.java',),
                      ('tools/CasStructuralRolesPatch.java','tools/cas_structural_roles.py','tools/CasDrawFastPathPatch.java','tools/cas_draw_fast_path.py')):
            info=copy.deepcopy(self.info)
            for name in names:info['source_pins'].pop(name,None)
            with self.subTest(ancestor_markers=names),self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)

    def test_rehashed_runtime_claim_independent_prior_relabelling_and_final_hashes_refused(self):
        info=copy.deepcopy(self.info);info['draw_phase_native_bytecode_contract']['draw_phase_contract']['runtime_qualified']=True;refresh(info['draw_phase_native_bytecode_contract'])
        with self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)
        info=copy.deepcopy(self.info);info['catalog_binding_native_bytecode_contract']['catalog_binding_contract']['other_four_binds_retained']=False
        with self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)
        for field in ('patched_resource_sha256','patched_resources'):
            info=copy.deepcopy(self.info)
            if field=='patched_resources':info[field][TEXT]='0'*64
            else:info[field]='0'*64
            with self.subTest(field=field),self.assertRaises(ValueError):maru_companion.verify_merged(info,self.resources)
        info,resources=copy.deepcopy(self.info),dict(self.resources);resources[KEY]=(WORK/'baseline.swf').read_bytes()
        info['patched_resource_sha256']=info['patched_resources'][TEXT]=phase.digest(resources[KEY])
        with self.assertRaises(ValueError):maru_companion.verify_merged(info,resources)

    def test_explicit_historical_binding_normalization_removes_only_later_phase_authority(self):
        historical_binding_fixture(self.info,self.resources)
        self.assertNotIn('draw_phase_native_bytecode_contract',self.info)
        self.assertTrue(all(n not in self.info['source_pins'] for n in phase.SOURCES[:2]))
        self.assertTrue(all(n in self.info['source_pins'] for n in phase.SOURCES[2:]))
        self.assertTrue(binding.verify_contract(self.info['catalog_binding_native_bytecode_contract'],self.resources[KEY]))
        self.assertTrue(maru_companion.verify_merged(self.info,self.resources))


if __name__=='__main__':unittest.main()
