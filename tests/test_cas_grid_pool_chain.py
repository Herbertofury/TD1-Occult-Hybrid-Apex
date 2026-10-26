"""Exact two-provider retained widget pool continuation; no compiler/game calls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_grid_pool as pool
import cas_communication_index as communication
import cas_image_boundary_profile as image
import cas_ui_build as ui
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_image_fixture, historical_library_terminals

KINDS = {'canonical': maru_companion.CANONICAL_GRID_LIBRARY, 'donor': maru_companion.GRID_LIBRARY}
DEPENDENCY = maru_companion.UNMODIFIED_OLYMPUS_LIBRARY
READY = all((ROOT / ('.work/v335-grid-pool-' + name) / suffix).is_file()
            for name in KINDS for suffix in ('chained.json', 'final.swf'))


def fixture(name, previous=False):
    path = ROOT / (('.work/v334-image-profile-' if previous else '.work/v335-grid-pool-') + name)
    return json.loads((path / 'chained.json').read_text()), (path / 'final.swf').read_bytes()


def refresh_envelope(record):
    record['previous_stage_sha256'] = communication.contract_digest(record['previous_stage_adapter'])
    record['postproof_sha256'] = communication.contract_digest(record['grid_pool_contract'])


@unittest.skipUnless(READY, 'Both frozen final pool fixtures required')
class PoolContinuationTests(unittest.TestCase):
    def test_exact_two_provider_continuations_preserve_image_history_and_honest_counts(self):
        expected = {dbpf_build.tgi(key) for key in KINDS.values()}
        self.assertEqual(set(pool.FINALS), expected)
        self.assertEqual({item[0] for item in pool.BASELINES.values()}, expected)
        for name, key in KINDS.items():
            record, final = fixture(name)
            previous, before = fixture(name, previous=True)
            with self.subTest(provider=name):
                self.assertTrue(pool.verify_adapter(record, final))
                self.assertEqual(record['previous_stage_adapter'], previous)
                post = record['grid_pool_contract']
                self.assertEqual(post['provider_resource_tgi'], dbpf_build.tgi(key))
                self.assertEqual(post['baseline_swf_sha256'], dbpf_build.digest(before))
                self.assertEqual(post['baseline_abc_sha256'], previous['image_boundary_profile_contract']['abc_sha256'])
                self.assertEqual((post['replaced_owned_bodies'], post['guarded_native_read_bodies'],
                                  post['appended_methods'], post['appended_fields']), (8, 8, 10, 0))
                self.assertIs(post['runtime_qualified'], False)
                self.assertIs(post['hitch_free_claimed'], False)
                verify = maru_companion.verify_canonical_grid_adapter if name == 'canonical' else maru_companion.verify_grid_adapter
                self.assertTrue(verify(record, final))

    def test_rehashed_counts_retention_predicates_sources_and_runtime_claims_cannot_be_forged(self):
        changes = [('ok', 1), ('provider_resource_tgi', '62ECC59A:00000000:0'),
                   ('baseline_swf_sha256', '0' * 64), ('baseline_abc_sha256', '0' * 64), ('abc_sha256', '0' * 64),
                   ('helper_source_sha256', '0' * 64), ('replaced_owned_bodies', 7),
                   ('guarded_native_read_bodies', 7), ('appended_methods', 9), ('appended_fields', 1),
                   ('appended_fields', False),
                   ('whole_abc_rollback_verified', 1), ('native_read_projection_verified', False),
                   ('unarmed_original_native_flow_verified', False), ('protected_namespace_bindings_verified', False),
                   ('serialized_owned_bodies_verified', False), ('all_other_bodies_retained', False),
                   ('runtime_qualified', True), ('hitch_free_claimed', True)]
        for name in KINDS:
            record, final = fixture(name)
            for field, value in changes:
                changed = copy.deepcopy(record)
                changed['grid_pool_contract'][field] = value
                refresh_envelope(changed)
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    pool.verify_adapter(changed, final)
            for source in pool.SOURCES:
                changed = copy.deepcopy(record)
                changed['grid_pool_contract']['source_sha256'][source] = '0' * 64
                refresh_envelope(changed)
                with self.subTest(provider=name, source=source), self.assertRaises(ValueError):
                    pool.verify_adapter(changed, final)

    def test_mixed_providers_recomputed_ancestor_envelopes_and_substituted_bytes_are_refused(self):
        for name in KINDS:
            record, final = fixture(name)
            for field in ('base_resource_sha256', 'patched_resource_sha256', 'previous_stage_sha256', 'postproof_sha256'):
                changed = copy.deepcopy(record)
                changed[field] = '0' * 64
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    pool.verify_adapter(changed, final)
            for other in KINDS:
                if other == name:
                    continue
                changed = copy.deepcopy(record)
                changed['previous_stage_adapter'] = fixture(other, previous=True)[0]
                refresh_envelope(changed)
                with self.subTest(provider=name, mixed=other), self.assertRaises(ValueError):
                    pool.verify_adapter(changed, final)
            changed = copy.deepcopy(record)
            ancestor = changed['previous_stage_adapter']
            ancestor['image_boundary_profile_contract']['changed_native_bodies'] = 2
            ancestor['postproof_sha256'] = communication.contract_digest(ancestor['image_boundary_profile_contract'])
            refresh_envelope(changed)
            with self.subTest(provider=name, forged_history=True), self.assertRaises(ValueError):
                pool.verify_adapter(changed, final)
            for payload in (fixture(name, previous=True)[1], final + b'changed'):
                with self.subTest(provider=name, payload=dbpf_build.digest(payload)), self.assertRaises(ValueError):
                    pool.verify_adapter(record, payload)

    def test_dependency_has_no_grid_pool_and_cannot_enter_the_pool_compiler_seam(self):
        dependency, final = fixture('dependency', previous=True)
        self.assertTrue(image.verify_adapter(dependency, final))
        self.assertNotIn('grid_pool_contract', dependency)
        self.assertNotIn(dbpf_build.digest(final), pool.BASELINES)
        with tempfile.TemporaryDirectory() as directory, patch.object(pool.comm, 'run', side_effect=AssertionError('No dependency compiler call')):
            with self.assertRaises(ValueError):
                pool.adapt(ROOT / '.work/research/OlympusLibrary.swf',
                    ROOT / '.work/v334-image-profile-dependency/final.swf',
                    ROOT / '.work/research/ffdec/ffdec-cli.exe', Path(directory))


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file(), 'Private package and pool fixtures required')
class PoolManifestTests(unittest.TestCase):
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        historical_library_terminals(self.info, self.resources)
        def source_pins(value):
            if isinstance(value, dict):
                if isinstance(value.get('source_sha256'), dict):
                    self.info['source_pins'].update(value['source_sha256'])
                for child in value.values():
                    source_pins(child)
        for name, key in (*KINDS.items(), ('dependency', DEPENDENCY)):
            record, final = fixture(name, previous=name == 'dependency')
            text = dbpf_build.tgi(key)
            source_pins(record)
            self.resources[key] = final
            self.info['base_resources'][text] = record['base_resource_sha256']
            self.info['patched_resources'][text] = record['patched_resource_sha256']
            group = self.info['communication_dependency_adapters'] if name == 'dependency' else self.info['grid_provider_adapters']
            group[text] = record
            if name == 'donor':
                self.info['companion_code_merge']['grid_library_adapter'] = record
        self.info['resources'] = sorted(dbpf_build.tgi(key) for key in self.resources)

    def test_current_manifest_requires_both_pool_providers_and_keeps_dependency_image_final(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for source in pool.SOURCES[:2]:
            self.assertIn(source, ui.source_pins())
        dependency = self.info['communication_dependency_adapters'][dbpf_build.tgi(DEPENDENCY)]
        self.assertEqual(dependency, fixture('dependency', previous=True)[0])
        self.assertIn('image_boundary_profile_contract', dependency)
        self.assertNotIn('grid_pool_contract', dependency)

    def test_current_source_pair_partial_or_full_downgrade_and_proof_absence_are_refused(self):
        for names in (('canonical',), ('donor',), tuple(KINDS)):
            changed, resources = copy.deepcopy(self.info), dict(self.resources)
            for name in names:
                key, text = KINDS[name], dbpf_build.tgi(KINDS[name])
                previous, before = fixture(name, previous=True)
                changed['grid_provider_adapters'][text] = previous
                changed['patched_resources'][text] = previous['patched_resource_sha256']
                resources[key] = before
                if name == 'donor':
                    changed['companion_code_merge']['grid_library_adapter'] = previous
            with self.subTest(downgrade=names), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, resources)
        for name, key in KINDS.items():
            changed = copy.deepcopy(self.info)
            del changed['grid_provider_adapters'][dbpf_build.tgi(key)]
            with self.subTest(missing=name), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)

    def test_stripped_pool_or_ancestor_pins_and_forged_final_proof_cannot_pass(self):
        groups = (pool.SOURCES[:1], pool.SOURCES[1:2], pool.SOURCES[:2],
                  maru_companion.GRID_IMAGE_PROFILE_SOURCES, maru_companion.GRID_COMMUNICATION_REMOVAL_SOURCES,
                  maru_companion.GRID_COMMUNICATION_DOMAIN_SOURCES, maru_companion.GRID_TRANSACTION_SOURCES)
        for group in groups:
            changed = copy.deepcopy(self.info)
            for source in group:
                changed['source_pins'].pop(source, None)
            with self.subTest(stripped=group), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)
        for name, key in KINDS.items():
            changed = copy.deepcopy(self.info)
            record = changed['grid_provider_adapters'][dbpf_build.tgi(key)]
            record['grid_pool_contract']['runtime_qualified'] = True
            refresh_envelope(record)
            if name == 'donor':
                changed['companion_code_merge']['grid_library_adapter'] = record
            with self.subTest(provider=name), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)

    def test_fabricated_third_pool_proof_is_refused_and_historical_v334_image_stays_valid(self):
        changed = copy.deepcopy(self.info)
        changed['communication_dependency_adapters'][dbpf_build.tgi(DEPENDENCY)] = copy.deepcopy(
            changed['grid_provider_adapters'][dbpf_build.tgi(KINDS['canonical'])])
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)
        historical_image_fixture(self.info, self.resources)
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for record in self.info['grid_provider_adapters'].values():
            self.assertIn('image_boundary_profile_contract', record)
            self.assertNotIn('grid_pool_contract', record)


if __name__ == '__main__':
    unittest.main()
