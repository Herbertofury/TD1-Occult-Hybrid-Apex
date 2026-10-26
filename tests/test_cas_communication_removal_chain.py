"""V333 removal/Manager final wrappers, using frozen artifacts only."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_communication_index as communication
import cas_communication_removal_miss as removal
import cas_ui_build
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_domain_fixture, historical_removal_fixture

KINDS = {'canonical': maru_companion.CANONICAL_GRID_LIBRARY,
         'donor': maru_companion.GRID_LIBRARY,
         'dependency': maru_companion.UNMODIFIED_OLYMPUS_LIBRARY}
READY = all((ROOT / ('.work/v333-removal-miss-' + name) / suffix).is_file()
            for name in KINDS for suffix in ('chained.json', 'final.swf'))


def fixture(name):
    path = ROOT / ('.work/v333-removal-miss-' + name)
    return json.loads((path / 'chained.json').read_text()), (path / 'final.swf').read_bytes()


def domain_fixture(name):
    path = ROOT / ('.work/v332-domain-probe-' + name)
    return json.loads((path / 'chained.json').read_text()), (path / 'final.swf').read_bytes()


def refresh_envelope(record):
    record['previous_stage_sha256'] = communication.contract_digest(record['previous_stage_adapter'])
    record['postproof_sha256'] = communication.contract_digest(record['communication_removal_miss_contract'])


@unittest.skipUnless(READY, 'All three frozen final removal/Manager stages required')
class RemovalContinuationTests(unittest.TestCase):
    def test_all_three_final_wrappers_preserve_exact_domain_history_and_honest_counts(self):
        for name, key in KINDS.items():
            record, final = fixture(name)
            previous, before = domain_fixture(name)
            with self.subTest(provider=name):
                self.assertTrue(removal.verify_adapter(record, final))
                self.assertEqual(record['previous_stage_adapter'], previous)
                post = record['communication_removal_miss_contract']
                self.assertEqual(post['provider_resource_tgi'], dbpf_build.tgi(key))
                self.assertEqual(post['baseline_swf_sha256'], dbpf_build.digest(before))
                self.assertEqual(post['baseline_abc_sha256'], previous['communication_domain_probe_contract']['abc_sha256'])
                self.assertEqual((post['changed_existing_bodies'], post['changed_native_bodies'],
                                  post['replaced_owned_manager_bodies'], post['appended_methods'], post['appended_fields']), (2, 1, 1, 1, 0))
                self.assertIs(post['runtime_qualified'], False)
                self.assertIs(post['hitch_free_claimed'], False)
                self.assertTrue(post['manager_native_static_getter_oracle_verified'])
                self.assertTrue(post['manager_native_dynamic_map_oracle_verified'])
                self.assertTrue(post['diagnostic_reason_fields_verified'])
                self.assertNotEqual(record['patched_resource_sha256'], previous['patched_resource_sha256'])
                if name == 'dependency':
                    self.assertNotIn('retained_transaction_adapter', previous['previous_stage_adapter'])
                else:
                    verify = maru_companion.verify_canonical_grid_adapter if name == 'canonical' else maru_companion.verify_grid_adapter
                    self.assertTrue(verify(record, final))

    def test_proof_counts_predicates_manager_oracles_source_and_runtime_forgery_are_refused(self):
        changes = [('provider_resource_tgi', '62ECC59A:00000000:0'), ('baseline_swf_sha256', '0' * 64),
                   ('baseline_abc_sha256', '0' * 64), ('abc_sha256', '0' * 64),
                   ('changed_existing_bodies', 1), ('changed_native_bodies', 0), ('replaced_owned_manager_bodies', 0),
                   ('appended_methods', 0), ('appended_fields', 1), ('helper_source_sha256', '0' * 64),
                   ('whole_abc_rollback_verified', 1), ('native_instruction_projection_verified', False),
                   ('negative_only_predicate_verified', False), ('private_field_binding_verified', False),
                   ('manager_native_static_getter_oracle_verified', False), ('manager_native_dynamic_map_oracle_verified', False),
                   ('diagnostic_reason_fields_verified', False), ('deferred_removal_original_path_verified', False),
                   ('native_positive_null_alias_unbuilt_paths_retained', False), ('no_lazy_index_build_or_allocation', False),
                   ('all_other_bodies_retained', False), ('runtime_qualified', True), ('hitch_free_claimed', True)]
        for name in KINDS:
            record, final = fixture(name)
            for field, value in changes:
                changed = copy.deepcopy(record)
                changed['communication_removal_miss_contract'][field] = value
                refresh_envelope(changed)
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    removal.verify_adapter(changed, final)
            for source in removal.SOURCES:
                changed = copy.deepcopy(record)
                changed['communication_removal_miss_contract']['source_sha256'][source] = '0' * 64
                refresh_envelope(changed)
                with self.subTest(provider=name, source=source), self.assertRaises(ValueError):
                    removal.verify_adapter(changed, final)

    def test_recomputed_historical_envelopes_and_substituted_final_bytes_cannot_pass(self):
        for name in KINDS:
            record, final = fixture(name)
            for field in ('base_resource_sha256', 'patched_resource_sha256', 'previous_stage_sha256', 'postproof_sha256'):
                changed = copy.deepcopy(record)
                changed[field] = '0' * 64
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    removal.verify_adapter(changed, final)
            changed = copy.deepcopy(record)
            changed['previous_stage_adapter']['communication_domain_probe_contract']['changed_native_bodies'] = 1
            changed['previous_stage_adapter']['postproof_sha256'] = communication.contract_digest(
                changed['previous_stage_adapter']['communication_domain_probe_contract'])
            refresh_envelope(changed)
            with self.subTest(provider=name, prior_stage_forgery=True), self.assertRaises(ValueError):
                removal.verify_adapter(changed, final)
            for payload in (domain_fixture(name)[1], final + b'changed'):
                with self.subTest(provider=name, bytes=dbpf_build.digest(payload)), self.assertRaises(ValueError):
                    removal.verify_adapter(record, payload)


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file() and
                     (ROOT / 'dist/candidate/ApexCASBridge.package.manifest.json').is_file(),
                     'Private compiled merge and all frozen final removal stages required')
class CurrentRemovalManifestTests(unittest.TestCase):
    """Explicit V333 manifests predate the V334 image-profile source pair."""
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        historical_removal_fixture(self.info, self.resources)
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

    def test_current_manifest_authenticates_all_three_latest_wrappers(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for source in removal.SOURCES:
            self.assertIn(source, cas_ui_build.source_pins())

    def test_stripping_any_required_source_pair_or_changing_source_proof_is_refused(self):
        groups = (removal.SOURCES[:2], maru_companion.GRID_COMMUNICATION_DOMAIN_SOURCES,
                  maru_companion.GRID_COMMUNICATION_DEPENDENCY_SOURCES,
                  maru_companion.GRID_COMMUNICATION_SOURCES, maru_companion.GRID_TRANSACTION_SOURCES)
        for group in groups:
            changed = copy.deepcopy(self.info)
            for source in group:
                changed['source_pins'].pop(source, None)
            with self.subTest(stripped=group), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)
        for source in removal.SOURCES:
            changed = copy.deepcopy(self.info)
            changed['source_pins'][source] = '0' * 64
            with self.subTest(source=source), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)

    def test_current_manifest_refuses_partial_and_full_latest_stage_downgrade(self):
        for names in [('canonical',), ('donor',), ('dependency',), tuple(KINDS)]:
            changed, resources = copy.deepcopy(self.info), dict(self.resources)
            for name in names:
                key, text = KINDS[name], dbpf_build.tgi(KINDS[name])
                group = changed['communication_dependency_adapters'] if name == 'dependency' else changed['grid_provider_adapters']
                prior = group[text]['previous_stage_adapter']
                group[text] = prior
                changed['patched_resources'][text] = prior['patched_resource_sha256']
                resources[key] = domain_fixture(name)[1]
                if name == 'donor':
                    changed['companion_code_merge']['grid_library_adapter'] = prior
            with self.subTest(downgrade=names), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, resources)

    def test_explicit_historical_v332_domain_manifest_stays_valid(self):
        changed, resources = copy.deepcopy(self.info), dict(self.resources)
        historical_domain_fixture(changed, resources)
        self.assertTrue(maru_companion.verify_merged(changed, resources))
        for group in ('grid_provider_adapters', 'communication_dependency_adapters'):
            for adapter in changed[group].values():
                self.assertIn('communication_domain_probe_contract', adapter)
                self.assertNotIn('communication_removal_miss_contract', adapter)


if __name__ == '__main__':
    unittest.main()
