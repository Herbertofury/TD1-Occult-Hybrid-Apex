"""Authenticate final V334 image profiles using frozen bytes, never compilers."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_communication_index as communication
import cas_image_boundary_profile as image
import cas_ui_build
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_removal_fixture, historical_image_fixture

KINDS = {'canonical': maru_companion.CANONICAL_GRID_LIBRARY,
         'donor': maru_companion.GRID_LIBRARY,
         'dependency': maru_companion.UNMODIFIED_OLYMPUS_LIBRARY}
READY = all((ROOT / ('.work/v334-image-profile-' + name) / suffix).is_file()
            for name in KINDS for suffix in ('chained.json', 'final.swf'))


def fixture(name, previous=False):
    path = ROOT / (('.work/v333-removal-miss-' if previous else '.work/v334-image-profile-') + name)
    return json.loads((path / 'chained.json').read_text()), (path / 'final.swf').read_bytes()


def refresh_envelope(record):
    record['previous_stage_sha256'] = communication.contract_digest(record['previous_stage_adapter'])
    record['postproof_sha256'] = communication.contract_digest(record['image_boundary_profile_contract'])


@unittest.skipUnless(READY, 'All three frozen final image-profile artifacts required')
class ImageProfileContinuationTests(unittest.TestCase):
    def test_all_three_exact_final_wrappers_preserve_removal_history_and_honest_counts(self):
        for name, key in KINDS.items():
            record, final = fixture(name)
            previous, before = fixture(name, previous=True)
            with self.subTest(provider=name):
                self.assertTrue(image.verify_adapter(record, final))
                self.assertEqual(record['previous_stage_adapter'], previous)
                post = record['image_boundary_profile_contract']
                self.assertEqual(post['provider_resource_tgi'], dbpf_build.tgi(key))
                self.assertEqual(post['baseline_swf_sha256'], dbpf_build.digest(before))
                self.assertEqual(post['baseline_abc_sha256'], previous['communication_removal_miss_contract']['abc_sha256'])
                self.assertEqual((post['changed_native_bodies'], post['replaced_owned_button_bodies'],
                                  post['appended_methods'], post['appended_static_fields']), (3, 1, 6, 4))
                self.assertEqual((post['budget_limit'], post['depth_limit'], post['record_limit']), (4096, 32, 0))
                self.assertIs(post['runtime_qualified'], False)
                self.assertIs(post['optimization_claimed'], False)
                self.assertNotEqual(record['patched_resource_sha256'], previous['patched_resource_sha256'])
                if name == 'dependency':
                    self.assertNotIn('retained_transaction_adapter', previous['previous_stage_adapter']['previous_stage_adapter'])
                else:
                    verify = maru_companion.verify_canonical_grid_adapter if name == 'canonical' else maru_companion.verify_grid_adapter
                    self.assertTrue(verify(record, final))

    def test_counts_projection_predicates_source_pins_and_runtime_claim_forgery_are_refused(self):
        changes = [('provider_resource_tgi', '62ECC59A:00000000:0'), ('baseline_swf_sha256', '0' * 64),
                   ('baseline_abc_sha256', '0' * 64), ('abc_sha256', '0' * 64), ('ok', 1),
                   ('changed_native_bodies', 4), ('replaced_owned_button_bodies', 0),
                   ('appended_methods', 5), ('appended_static_fields', 3),
                   ('budget_limit', 4097), ('depth_limit', 33), ('record_limit', 1),
                   ('whole_abc_rollback_verified', 1), ('native_disabled_projection_verified', False),
                   ('native_enabled_projection_verified', False), ('native_exceptions_not_intercepted', False),
                   ('actual_loader_instance_route_verified', False), ('disabled_no_allocation_clock_counter', False),
                   ('bounded_primitive_state_verified', False), ('native_input_mode_oracle_verified', False),
                   ('runtime_qualified', True), ('optimization_claimed', True)]
        for name in KINDS:
            record, final = fixture(name)
            for field, value in changes:
                changed = copy.deepcopy(record)
                changed['image_boundary_profile_contract'][field] = value
                refresh_envelope(changed)
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    image.verify_adapter(changed, final)
            for source in image.SOURCES:
                changed = copy.deepcopy(record)
                changed['image_boundary_profile_contract']['source_sha256'][source] = '0' * 64
                refresh_envelope(changed)
                with self.subTest(provider=name, source=source), self.assertRaises(ValueError):
                    image.verify_adapter(changed, final)

    def test_rehashed_ancestor_forgery_mixed_providers_and_changed_bytes_are_refused(self):
        for name in KINDS:
            record, final = fixture(name)
            for field in ('base_resource_sha256', 'patched_resource_sha256', 'previous_stage_sha256', 'postproof_sha256'):
                changed = copy.deepcopy(record)
                changed[field] = '0' * 64
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    image.verify_adapter(changed, final)
            changed = copy.deepcopy(record)
            ancestor = changed['previous_stage_adapter']
            ancestor['communication_removal_miss_contract']['changed_native_bodies'] = 0
            ancestor['postproof_sha256'] = communication.contract_digest(ancestor['communication_removal_miss_contract'])
            refresh_envelope(changed)
            with self.subTest(provider=name, forged_ancestor=True), self.assertRaises(ValueError):
                image.verify_adapter(changed, final)
            for other in KINDS:
                if other == name:
                    continue
                changed = copy.deepcopy(record)
                changed['previous_stage_adapter'] = fixture(other, previous=True)[0]
                refresh_envelope(changed)
                with self.subTest(provider=name, mixed=other), self.assertRaises(ValueError):
                    image.verify_adapter(changed, final)
            for payload in (fixture(name, previous=True)[1], final + b'changed'):
                with self.subTest(provider=name, payload=dbpf_build.digest(payload)), self.assertRaises(ValueError):
                    image.verify_adapter(record, payload)


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file() and
                     (ROOT / 'dist/candidate/ApexCASBridge.package.manifest.json').is_file(),
                     'Private compiled merge and all final image stages required')
class CurrentImageProfileManifestTests(unittest.TestCase):
    """Explicit V334 image sources predate the V335 pool requirement."""
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        historical_image_fixture(self.info, self.resources)
        self.info['communication_dependency_adapters'] = {}
        def source_pins(value):
            if isinstance(value, dict):
                if isinstance(value.get('source_sha256'), dict):
                    self.info['source_pins'].update(value['source_sha256'])
                for child in value.values():
                    source_pins(child)
        for name, key in KINDS.items():
            record, final = fixture(name)
            text = dbpf_build.tgi(key)
            source_pins(record)
            self.resources[key] = final
            self.info['base_resources'][text] = record['base_resource_sha256']
            self.info['patched_resources'][text] = record['patched_resource_sha256']
            group = self.info['communication_dependency_adapters'] if name == 'dependency' else self.info['grid_provider_adapters']
            group[text] = record
            if name == 'dependency':
                self.info.setdefault('unmodified_dependency_resources', {}).pop(text, None)
            elif name == 'donor':
                self.info['companion_code_merge']['grid_library_adapter'] = record
        self.info['resources'] = sorted(dbpf_build.tgi(key) for key in self.resources)

    def test_current_manifest_admits_all_three_latest_proofs_and_two_new_source_pins(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for source in image.SOURCES[:2]:
            self.assertIn(source, cas_ui_build.source_pins())

    def test_source_stripping_ancestor_source_loss_and_forged_source_proofs_are_refused(self):
        groups = (image.SOURCES[:2], maru_companion.GRID_COMMUNICATION_REMOVAL_SOURCES,
                  maru_companion.GRID_COMMUNICATION_DOMAIN_SOURCES,
                  maru_companion.GRID_COMMUNICATION_DEPENDENCY_SOURCES,
                  maru_companion.GRID_COMMUNICATION_SOURCES, maru_companion.GRID_TRANSACTION_SOURCES)
        for group in groups:
            changed = copy.deepcopy(self.info)
            for source in group:
                changed['source_pins'].pop(source, None)
            with self.subTest(stripped=group), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)
        for source in image.SOURCES:
            changed = copy.deepcopy(self.info)
            changed['source_pins'][source] = '0' * 64
            with self.subTest(source=source), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)

    def test_current_manifest_refuses_partial_and_full_image_stage_downgrade(self):
        for names in [('canonical',), ('donor',), ('dependency',), tuple(KINDS)]:
            changed, resources = copy.deepcopy(self.info), dict(self.resources)
            for name in names:
                key, text = KINDS[name], dbpf_build.tgi(KINDS[name])
                group = changed['communication_dependency_adapters'] if name == 'dependency' else changed['grid_provider_adapters']
                previous, before = fixture(name, previous=True)
                group[text] = previous
                changed['patched_resources'][text] = previous['patched_resource_sha256']
                resources[key] = before
                if name == 'donor':
                    changed['companion_code_merge']['grid_library_adapter'] = previous
            with self.subTest(downgrade=names), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, resources)

    def test_missing_dependency_or_forged_current_image_contract_cannot_pass(self):
        changed, resources = copy.deepcopy(self.info), dict(self.resources)
        del changed['communication_dependency_adapters']
        del resources[KINDS['dependency']]
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, resources)
        for name, key in KINDS.items():
            changed = copy.deepcopy(self.info)
            group = changed['communication_dependency_adapters'] if name == 'dependency' else changed['grid_provider_adapters']
            record = group[dbpf_build.tgi(key)]
            record['image_boundary_profile_contract']['runtime_qualified'] = True
            refresh_envelope(record)
            if name == 'donor':
                changed['companion_code_merge']['grid_library_adapter'] = record
            with self.subTest(provider=name), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)

    def test_explicit_historical_v333_removal_manifest_remains_valid(self):
        changed, resources = copy.deepcopy(self.info), dict(self.resources)
        historical_removal_fixture(changed, resources)
        self.assertTrue(maru_companion.verify_merged(changed, resources))
        for group in ('grid_provider_adapters', 'communication_dependency_adapters'):
            for adapter in changed[group].values():
                self.assertIn('communication_removal_miss_contract', adapter)
                self.assertNotIn('image_boundary_profile_contract', adapter)


if __name__ == '__main__':
    unittest.main()
