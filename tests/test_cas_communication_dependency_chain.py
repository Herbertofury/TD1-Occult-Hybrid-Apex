"""Frozen native Olympus dependency admission; no compiler or game calls."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_communication_dependency as dependency
import cas_communication_index as communication
import cas_ui_build
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_provider_fixture

WORK = ROOT / '.work/v332-communication-dependency'
KEY = maru_companion.UNMODIFIED_OLYMPUS_LIBRARY
TEXT = dbpf_build.tgi(KEY)
READY = all((WORK / name).is_file() for name in ('chained.json', 'final.swf'))


def frozen_dependency():
    return json.loads((WORK / 'chained.json').read_text()), (WORK / 'final.swf').read_bytes()


def providers():
    records, resources = {}, {}
    for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY), ('donor', maru_companion.GRID_LIBRARY)]:
        path = ROOT / ('.work/v331-comm-index-stage-' + name)
        records[dbpf_build.tgi(key)] = json.loads((path / 'chained.json').read_text())
        resources[key] = (path / 'final.swf').read_bytes()
    return records, resources


def refresh_envelope(record):
    record['postproof_sha256'] = communication.contract_digest(record['communication_dependency_contract'])


@unittest.skipUnless(READY, 'Private compiled native communication dependency required')
class CommunicationDependencyAdmissionTests(unittest.TestCase):
    def test_dependency_has_its_own_proof_without_a_fictional_grid_stage(self):
        record, final = frozen_dependency()
        self.assertTrue(dependency.verify_adapter(record, final))
        self.assertNotIn('retained_transaction_adapter', record)
        self.assertNotIn('retained_base_adapter', record)
        post = record['communication_dependency_contract']
        self.assertIs(post['grid_stage_present'], False)
        self.assertEqual(post['provider_resource_tgi'], TEXT)
        self.assertEqual(post['base_provider_sha256'], dependency.PIN)
        self.assertEqual(post['baseline_swf_sha256'], dependency.PIN)
        self.assertEqual((post['changed_native_bodies'], post['appended_methods'],
                          post['appended_communication_methods'], post['appended_button_diagnostic_methods']), (5, 8, 7, 1))
        self.assertEqual((post['appended_fields'], post['appended_static_fields']), (2, 5))
        original = (ROOT / '.work/research/OlympusLibrary.swf').read_bytes()
        self.assertEqual(dbpf_build.digest(original), dependency.PIN)
        self.assertEqual([(t[0], t[3]) for t in cas_ui_build.tags(cas_ui_build.unpack(original)[1]) if t[0] != 82],
                         [(t[0], t[3]) for t in cas_ui_build.tags(cas_ui_build.unpack(final)[1]) if t[0] != 82])

    def test_third_resource_is_admitted_only_with_separate_exact_proof(self):
        evidence, resources = providers()
        record, final = frozen_dependency()
        self.assertTrue(maru_companion.verify_grid_providers(evidence, resources))
        resources[KEY] = final
        self.assertTrue(maru_companion.verify_grid_providers(evidence, resources, {TEXT: record}))
        for missing in (None, {}, {dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY): record}):
            with self.subTest(proof=missing), self.assertRaises(ValueError):
                maru_companion.verify_grid_providers(evidence, resources, missing)
        forged = copy.deepcopy(evidence)
        forged[TEXT] = record
        with self.assertRaises(ValueError):
            maru_companion.verify_grid_providers(forged, resources, {TEXT: record})
        with self.assertRaises(ValueError):
            maru_companion.verify_grid_providers(evidence, resources, {TEXT: evidence[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]})
        del resources[KEY]
        with self.assertRaises(ValueError):
            maru_companion.verify_grid_providers(evidence, resources, {TEXT: record})

    def test_modified_body_original_bytes_and_envelope_hashes_are_refused(self):
        record, final = frozen_dependency()
        original = (ROOT / '.work/research/OlympusLibrary.swf').read_bytes()
        tag = next(t[3] for t in cas_ui_build.tags(cas_ui_build.unpack(final)[1]) if t[0] == 82)
        corrupted = bytearray(tag)
        corrupted[-1] ^= 1
        mutated_body = cas_ui_build.replace_payload(final, bytes(corrupted))
        for payload in (original, final + b'changed', mutated_body):
            with self.subTest(payload_hash=dbpf_build.digest(payload)), self.assertRaises(ValueError):
                dependency.verify_adapter(record, payload)
        for field in ('base_resource_sha256', 'patched_resource_sha256', 'postproof_sha256'):
            changed = copy.deepcopy(record)
            changed[field] = '0' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                dependency.verify_adapter(changed, final)

    def test_corrupt_proof_source_counts_and_runtime_claims_fail_after_rehashing(self):
        record, final = frozen_dependency()
        changes = [('provider_resource_tgi', dbpf_build.tgi(maru_companion.GRID_LIBRARY)),
                   ('base_provider_sha256', '0' * 64), ('baseline_swf_sha256', '0' * 64),
                   ('baseline_abc_sha256', '0' * 64), ('communication_abc_sha256', '0' * 64), ('abc_sha256', '0' * 64),
                   ('changed_native_bodies', 4), ('appended_methods', 7), ('appended_communication_methods', 6),
                   ('appended_button_diagnostic_methods', 0), ('appended_fields', 1), ('appended_static_fields', 4),
                   ('whole_abc_rollback_verified', 1), ('button_whole_abc_rollback_verified', False),
                   ('button_lexical_domain_read_verified', False), ('reviewed_helper_semantic_pins_verified', False),
                   ('protected_field_namespace_verified', False), ('bound_closure_runtime_eligibility_probe', False),
                   ('explicit_primitive_diagnostics', False), ('native_array_dispatch_order_retained', False),
                   ('public_alias_falls_back_to_original', False), ('deferred_removal_semantics_retained', False),
                   ('grid_stage_present', True), ('runtime_qualified', True), ('hitch_free_claimed', True)]
        for field, value in changes:
            changed = copy.deepcopy(record)
            changed['communication_dependency_contract'][field] = value
            refresh_envelope(changed)
            with self.subTest(field=field), self.assertRaises(ValueError):
                dependency.verify_adapter(changed, final)
        for source in dependency.SOURCES:
            changed = copy.deepcopy(record)
            changed['communication_dependency_contract']['source_sha256'][source] = '0' * 64
            refresh_envelope(changed)
            with self.subTest(source=source), self.assertRaises(ValueError):
                dependency.verify_adapter(changed, final)


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file() and
                     (ROOT / 'dist/candidate/ApexCASBridge.package.manifest.json').is_file(),
                     'Private merged package and dependency continuation required')
class CommunicationDependencyManifestTests(unittest.TestCase):
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        historical_provider_fixture(self.info, self.resources, keep_dependency=True)
        grid_evidence, grid_resources = providers()
        self.resources.update(grid_resources)
        self.info['grid_provider_adapters'] = grid_evidence
        for text, record in grid_evidence.items():
            self.info['base_resources'][text] = record['base_resource_sha256']
            self.info['patched_resources'][text] = record['patched_resource_sha256']
            self.info['source_pins'].update(record['retained_transaction_adapter']['native_bytecode_contract']['source_sha256'])
            self.info['source_pins'].update(record['communication_index_contract']['source_sha256'])
        self.info['companion_code_merge']['grid_library_adapter'] = grid_evidence[dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
        record, final = frozen_dependency()
        self.resources[KEY] = final
        self.info['communication_dependency_adapters'] = {TEXT: record}
        self.info['source_pins'].update(record['communication_dependency_contract']['source_sha256'])
        self.info['base_resources'][TEXT] = dependency.PIN
        self.info['patched_resources'][TEXT] = dependency.FINAL_SWF_SHA256
        self.info.setdefault('unmodified_dependency_resources', {}).pop(TEXT, None)
        self.info['resources'] = sorted(dbpf_build.tgi(key) for key in self.resources)

    def test_current_manifest_admits_only_the_exact_adaptation_and_source_pins(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for source in dependency.SOURCES:
            self.assertIn(source, cas_ui_build.source_pins())
            for action in ('missing', 'changed'):
                changed = copy.deepcopy(self.info)
                if action == 'missing':
                    del changed['source_pins'][source]
                else:
                    changed['source_pins'][source] = '0' * 64
                with self.subTest(source=source, action=action), self.assertRaises(ValueError):
                    maru_companion.verify_merged(changed, self.resources)

    def test_missing_original_or_downgraded_dependency_is_refused_for_current_sources(self):
        for action in ('missing-resource', 'original-resource', 'missing-proof', 'empty-proof', 'grid-proof', 'changed-resource'):
            changed, resources = copy.deepcopy(self.info), dict(self.resources)
            if action == 'missing-resource':
                del resources[KEY]
            elif action == 'original-resource':
                resources[KEY] = (ROOT / '.work/research/OlympusLibrary.swf').read_bytes()
            elif action == 'missing-proof':
                del changed['communication_dependency_adapters']
            elif action == 'empty-proof':
                changed['communication_dependency_adapters'] = {}
            elif action == 'grid-proof':
                changed['communication_dependency_adapters'][TEXT] = changed['grid_provider_adapters'][dbpf_build.tgi(maru_companion.GRID_LIBRARY)]
            else:
                resources[KEY] += b'changed'
            with self.subTest(action=action), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, resources)

    def test_unmodified_dependency_lie_and_wrong_resource_inventory_are_refused(self):
        for field in ('base_resources', 'patched_resources', 'unmodified_dependency_resources'):
            changed = copy.deepcopy(self.info)
            changed[field][TEXT] = dependency.PIN if field == 'unmodified_dependency_resources' else '0' * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, self.resources)

    def test_present_override_cannot_strip_source_requirement_to_pose_as_historical(self):
        changed = copy.deepcopy(self.info)
        for source in maru_companion.GRID_COMMUNICATION_DEPENDENCY_SOURCES:
            del changed['source_pins'][source]
        changed['unmodified_dependency_resources'][TEXT] = dependency.PIN
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)

    def test_historical_two_provider_manifests_without_dependency_remain_valid(self):
        for stage in ('communication', 'transaction', 'getter'):
            changed, resources = copy.deepcopy(self.info), dict(self.resources)
            del resources[KEY]
            del changed['communication_dependency_adapters']
            changed['base_resources'].pop(TEXT, None)
            changed['patched_resources'].pop(TEXT, None)
            changed['unmodified_dependency_resources'][TEXT] = dependency.PIN
            for source in maru_companion.GRID_COMMUNICATION_DEPENDENCY_SOURCES:
                del changed['source_pins'][source]
            if stage != 'communication':
                for source in maru_companion.GRID_COMMUNICATION_SOURCES:
                    changed['source_pins'].pop(source, None)
                for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY), ('donor', maru_companion.GRID_LIBRARY)]:
                    text = dbpf_build.tgi(key)
                    record = changed['grid_provider_adapters'][text]['retained_transaction_adapter']
                    payload = (ROOT / '.work/v331-grid-selection-final' / (name + '.swf')).read_bytes()
                    if stage == 'getter':
                        record = record['retained_base_adapter']
                        payload = (ROOT / '.work/v328-grid-perf-native' / (name + '-profile.swf')).read_bytes()
                    changed['grid_provider_adapters'][text] = record
                    changed['patched_resources'][text] = record['patched_resource_sha256']
                    resources[key] = payload
                    if name == 'donor':
                        changed['companion_code_merge']['grid_library_adapter'] = record
                if stage == 'getter':
                    for source in maru_companion.GRID_TRANSACTION_SOURCES:
                        changed['source_pins'].pop(source, None)
            with self.subTest(stage=stage):
                self.assertTrue(maru_companion.verify_merged(changed, resources))


if __name__ == '__main__':
    unittest.main()
