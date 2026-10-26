"""Complete Main binding continuation and package admission; no compiler calls."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import cas_catalog_binding as binding
import cas_cell_attach as attach
import cas_communication_index as communication
import cas_ui_build as ui
import dbpf_build
import maru_companion
import cas_draw_phase as phase
from cas_main_chain_fixtures import READY, current_main

KEY = maru_companion.CUSTOMIZER
TEXT = dbpf_build.tgi(KEY)


def fixture():
    return current_main('binding')[:2]


def baseline_fixture():
    return current_main('binding')[2]


def refresh(record):
    record['previous_stage_sha256'] = communication.contract_digest(record['previous_stage_contract'])
    record['catalog_binding_contract']['previous_stage_sha256'] = record['previous_stage_sha256']
    record['postproof_sha256'] = communication.contract_digest(record['catalog_binding_contract'])


def historical_binding_fixture(info, resources):
    """Remove the later diagnostic with its exact bytes and unique tool pins."""
    record = info.pop('draw_phase_native_bytecode_contract', None)
    if record is not None:
        assert phase.verify_contract(record, resources[KEY])
        assert record['previous_stage_contract'] == info['catalog_binding_native_bytecode_contract']
        resources[KEY] = phase.reconstruct_previous(resources[KEY], record['draw_phase_contract'])
    for source in phase.SOURCES[:2]:
        info['source_pins'].pop(source, None)
    info['patched_resource_sha256'] = info['patched_resources'][TEXT] = binding.digest(resources[KEY])
    return info, resources


def install_fixture(info, resources):
    historical_binding_fixture(info, resources)
    record, final = fixture()
    previous = record['previous_stage_contract']
    info.update(copy.deepcopy(previous['previous_chain']))
    for proof in previous['previous_chain'].values():
        info['source_pins'].update(proof.get('source_sha256', {}))
    info['cell_attach_native_bytecode_contract'] = copy.deepcopy(previous)
    info['catalog_binding_native_bytecode_contract'] = copy.deepcopy(record)
    info['source_pins'].update(previous['cell_attach_contract']['source_sha256'])
    info['source_pins'].update(record['catalog_binding_contract']['source_sha256'])
    resources[KEY] = final
    info['patched_resource_sha256'] = info['patched_resources'][TEXT] = binding.digest(final)
    return info, resources


def historical_attach_fixture(info, resources):
    historical_binding_fixture(info, resources)
    record = info.pop('catalog_binding_native_bytecode_contract')
    final = resources[KEY]
    assert binding.verify_contract(record, final)
    assert record['previous_stage_contract'] == info['cell_attach_native_bytecode_contract']
    resources[KEY] = binding.reconstruct_previous(final, record['catalog_binding_contract'])
    for source in binding.SOURCES[:2]:
        info['source_pins'].pop(source, None)
    info['patched_resource_sha256'] = info['patched_resources'][TEXT] = binding.digest(resources[KEY])
    return info, resources


@unittest.skipUnless(READY, 'Frozen complete binding continuation required')
class BindingContinuationTests(unittest.TestCase):
    def test_exact_main_history_reconstructs_its_complete_prior_and_retains_honest_counts(self):
        record, final = fixture()
        self.assertTrue(binding.verify_contract(record, final))
        previous = record['previous_stage_contract']
        before = binding.reconstruct_previous(final, record['catalog_binding_contract'])
        self.assertEqual(before, baseline_fixture())
        self.assertTrue(attach.verify_contract(previous, before))
        self.assertNotEqual(binding.digest(final), previous['final_swf_sha256'])
        proof = record['catalog_binding_contract']
        self.assertEqual(tuple(proof[name] for name in ('changed_native_bodies', 'replaced_owned_bodies',
                         'appended_methods', 'appended_fields')), (1, 1, 2, 0))
        self.assertIs(proof['runtime_qualified'], False)
        self.assertIs(proof['performance_gain_claimed'], False)
        for source in binding.SOURCES[:2]:
            self.assertIn(source, ui.source_pins())

    def test_rehashed_counts_sources_native_authority_and_runtime_claims_cannot_be_forged(self):
        record, final = fixture()
        changes = [('ok', 1), ('phase', 'different'), ('changed_native_bodies', True),
                   ('changed_native_bodies', 0), ('replaced_owned_bodies', True), ('replaced_owned_bodies', 2),
                   ('appended_methods', 1), ('appended_fields', False), ('appended_fields', 1),
                   ('native_first_bind_only_verified', False), ('other_four_binds_retained', 1),
                   ('native_binding_body_retained', False), ('native_cfg_projection_verified', False),
                   ('listener_insertion_order_verified', False), ('exact_dispatch_payload_verified', False),
                   ('protected_namespace_bindings_verified', False), ('whole_abc_rollback_verified', False),
                   ('all_other_bodies_retained', False), ('runtime_qualified', True),
                   ('performance_gain_claimed', True), ('baseline_swf_sha256', '0' * 64),
                   ('baseline_abc_sha256', '0' * 64), ('baseline_native_align_sha256', '0' * 64),
                   ('native_bind_sha256', '0' * 64), ('abc_sha256', '0' * 64),
                   ('helper_source_sha256', '0' * 64)]
        for name, value in changes:
            changed = copy.deepcopy(record)
            changed['catalog_binding_contract'][name] = value
            refresh(changed)
            with self.subTest(field=name, value=value), self.assertRaises(ValueError):
                binding.verify_contract(changed, final)
        for source in binding.SOURCES:
            changed = copy.deepcopy(record)
            changed['catalog_binding_contract']['source_sha256'][source] = '0' * 64
            refresh(changed)
            with self.subTest(source=source), self.assertRaises(ValueError):
                binding.verify_contract(changed, final)

    def test_final_byte_substitution_and_rehashed_complete_history_corruption_are_refused(self):
        record, final = fixture()
        for value in (baseline_fixture(), final + b'changed'):
            with self.subTest(payload=binding.digest(value)), self.assertRaises(ValueError):
                binding.verify_contract(record, value)
        for stage, field in [('native_bytecode_contract', 'native_method_count'),
                             ('structural_roles_native_bytecode_contract', 'main_and_height_preserved'),
                             ('draw_fast_path_native_bytecode_contract', 'disabled_callback_reads')]:
            changed = copy.deepcopy(record)
            previous = changed['previous_stage_contract']
            previous['previous_chain'][stage][field] = 0
            previous['previous_chain_sha256'] = communication.contract_digest(previous['previous_chain'])
            previous['cell_attach_contract']['previous_chain_sha256'] = previous['previous_chain_sha256']
            previous['postproof_sha256'] = communication.contract_digest(previous['cell_attach_contract'])
            refresh(changed)
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                binding.verify_contract(changed, final)


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file(), 'Private merged package required')
class BindingManifestTests(unittest.TestCase):
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        install_fixture(self.info, self.resources)

    def test_current_source_manifest_requires_exact_binding_history_and_actual_final_bytes(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        record = self.info['catalog_binding_native_bytecode_contract']
        self.assertEqual(record['previous_stage_contract'], self.info['cell_attach_native_bytecode_contract'])
        self.assertEqual(binding.digest(self.resources[KEY]), record['final_swf_sha256'])
        self.assertTrue(binding.verify_contract(record, self.resources[KEY]))

    def test_missing_partial_or_all_binding_source_pins_and_missing_proof_are_refused(self):
        for names in ((binding.SOURCES[0],), (binding.SOURCES[1],), binding.SOURCES[:2], binding.SOURCES):
            changed = copy.deepcopy(self.info)
            for name in names:
                changed['source_pins'].pop(name, None)
            with self.subTest(sources=names), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)
        changed = copy.deepcopy(self.info)
        changed.pop('catalog_binding_native_bytecode_contract')
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)
        for name in binding.SOURCES[:2]:
            changed['source_pins'].pop(name, None)
        # Stripping the marker and pins cannot make its altered bytes an old Main.
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)

    def test_retained_current_source_rejects_historical_bytes_and_independent_prior_relabelling(self):
        changed, resources = copy.deepcopy(self.info), dict(self.resources)
        historical_attach_fixture(changed, resources)
        changed['source_pins'].update(self.info['catalog_binding_native_bytecode_contract']['catalog_binding_contract']['source_sha256'])
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, resources)
        changed = copy.deepcopy(self.info)
        changed['cell_attach_native_bytecode_contract']['previous_chain_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)
        changed = copy.deepcopy(self.info)
        del changed['cell_attach_native_bytecode_contract']
        for source in attach.SOURCES[:2]:
            changed['source_pins'].pop(source, None)
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)

    def test_rehashed_binding_claim_or_final_identity_cannot_enter_the_package(self):
        changed = copy.deepcopy(self.info)
        changed['catalog_binding_native_bytecode_contract']['catalog_binding_contract']['runtime_qualified'] = True
        refresh(changed['catalog_binding_native_bytecode_contract'])
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)
        changed, resources = copy.deepcopy(self.info), dict(self.resources)
        resources[KEY] = baseline_fixture()
        changed['patched_resource_sha256'] = changed['patched_resources'][TEXT] = binding.digest(resources[KEY])
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, resources)

    def test_explicit_historical_main_normalization_removes_only_binding_and_retains_full_attach(self):
        historical_attach_fixture(self.info, self.resources)
        self.assertNotIn('catalog_binding_native_bytecode_contract', self.info)
        self.assertTrue(all(name not in self.info['source_pins'] for name in binding.SOURCES[:2]))
        self.assertTrue(all(name in self.info['source_pins'] for name in binding.SOURCES[2:]))
        self.assertTrue(attach.verify_contract(self.info['cell_attach_native_bytecode_contract'], self.resources[KEY]))
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))


if __name__ == '__main__':
    unittest.main()
