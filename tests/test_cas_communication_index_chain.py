"""No compiler/game calls: validate real frozen provider continuation artifacts."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_communication_index as communication
import cas_ui_build
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_provider_fixture

NAMES = ('canonical', 'donor')
KEYS = {'canonical': maru_companion.CANONICAL_GRID_LIBRARY,
        'donor': maru_companion.GRID_LIBRARY}
TRANSACTIONS = ROOT / '.work/v331-grid-selection-final'


def fixture(name):
    path = ROOT / ('.work/v331-comm-index-stage-' + name)
    return json.loads((path / 'chained.json').read_text()), (path / 'final.swf').read_bytes()


def refresh_envelope(record):
    """An adversary can recompute metadata hashes; substantive gates must hold."""
    record['retained_transaction_sha256'] = communication.contract_digest(record['retained_transaction_adapter'])
    record['postproof_sha256'] = communication.contract_digest(record['communication_index_contract'])


READY = all((ROOT / ('.work/v331-comm-index-stage-' + name) / suffix).is_file()
            for name in NAMES for suffix in ('chained.json', 'final.swf'))


@unittest.skipUnless(READY, 'Private frozen communication provider continuations required')
class CommunicationProviderChainTests(unittest.TestCase):
    def verify(self, name, record, data):
        method = (maru_companion.verify_canonical_grid_adapter if name == 'canonical'
                  else maru_companion.verify_grid_adapter)
        return method(record, data)

    def test_both_real_final_providers_chain_separate_historical_and_current_abcs(self):
        for name in NAMES:
            record, data = fixture(name)
            with self.subTest(provider=name):
                self.assertTrue(self.verify(name, record, data))
                self.assertTrue(communication.verify_adapter(record, data))
                tx = record['retained_transaction_adapter']
                message = record['communication_index_contract']
                self.assertEqual(tx, json.loads((TRANSACTIONS / (name + '.json')).read_text()))
                self.assertEqual(message['baseline_swf_sha256'], tx['patched_resource_sha256'])
                self.assertEqual(message['baseline_abc_sha256'], tx['native_bytecode_contract']['abc_sha256'])
                self.assertNotEqual(message['abc_sha256'], message['baseline_abc_sha256'])
                self.assertNotEqual(record['patched_resource_sha256'], tx['patched_resource_sha256'])
                self.assertEqual((message['changed_native_bodies'], message['appended_methods'],
                                  message['appended_fields'], message['appended_static_fields']), (5, 7, 2, 5))
                self.assertFalse(message['runtime_qualified'])
                self.assertFalse(message['hitch_free_claimed'])
                self.assertEqual(record['patched_resource_sha256'], dbpf_build.digest(data))
                self.assertEqual(record['retained_transaction_sha256'], communication.contract_digest(tx))
                self.assertEqual(record['postproof_sha256'], communication.contract_digest(message))

    def test_message_proof_corruption_is_refused_after_envelope_hashes_are_recomputed(self):
        changes = [('base_provider_sha256', '0' * 64), ('baseline_swf_sha256', '0' * 64),
                   ('baseline_abc_sha256', '0' * 64), ('abc_sha256', '0' * 64),
                   ('provider_resource_tgi', dbpf_build.tgi(maru_companion.UNMODIFIED_OLYMPUS_LIBRARY)),
                   ('changed_native_bodies', 4), ('appended_methods', 6), ('appended_fields', 1),
                   ('appended_static_fields', 4), ('whole_abc_rollback_verified', 1),
                   ('reviewed_helper_semantic_pins_verified', False), ('protected_field_namespace_verified', False),
                   ('bound_closure_runtime_eligibility_probe', False), ('explicit_primitive_diagnostics', False),
                   ('native_array_dispatch_order_retained', False), ('public_alias_falls_back_to_original', False),
                   ('deferred_removal_semantics_retained', False), ('runtime_qualified', True),
                   ('hitch_free_claimed', True)]
        for name in NAMES:
            record, data = fixture(name)
            for field, value in changes:
                changed = copy.deepcopy(record)
                changed['communication_index_contract'][field] = value
                refresh_envelope(changed)
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    self.verify(name, changed, data)
            for source in record['communication_index_contract']['source_sha256']:
                changed = copy.deepcopy(record)
                changed['communication_index_contract']['source_sha256'][source] = '0' * 64
                refresh_envelope(changed)
                with self.subTest(provider=name, source=source), self.assertRaises(ValueError):
                    self.verify(name, changed, data)

    def test_historical_transaction_counts_identity_source_and_flags_remain_substantive(self):
        changes = [('original_method_info_count', 0), ('original_method_body_count', 0),
                   ('baseline_method_info_count', 0), ('baseline_method_body_count', 0),
                   ('unchanged_original_native_bodies', 0), ('unchanged_baseline_bodies', 0),
                   ('guarded_original_native_bodies', 16), ('guarded_existing_adapter_bodies', 0),
                   ('guarded_native_bodies', 17), ('appended_methods', 44), ('appended_fields', 2),
                   ('base_provider_sha256', '0' * 64), ('baseline_swf_sha256', '0' * 64),
                   ('whole_abc_rollback_verified', 1), ('serialized_projection_verified', False),
                   ('protected_field_namespace_bindings_verified', False),
                   ('explicit_jump_switch_exception_fixtures', False), ('unarmed_original_native_flow_verified', False),
                   ('runtime_qualified', True), ('hitch_free_claimed', True)]
        for name in NAMES:
            record, data = fixture(name)
            for field, value in changes:
                changed = copy.deepcopy(record)
                changed['retained_transaction_adapter']['native_bytecode_contract'][field] = value
                refresh_envelope(changed)
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    self.verify(name, changed, data)
            for source in record['retained_transaction_adapter']['native_bytecode_contract']['source_sha256']:
                changed = copy.deepcopy(record)
                changed['retained_transaction_adapter']['native_bytecode_contract']['source_sha256'][source] = '0' * 64
                refresh_envelope(changed)
                with self.subTest(provider=name, source=source), self.assertRaises(ValueError):
                    self.verify(name, changed, data)
            changed = copy.deepcopy(record)
            changed['retained_transaction_adapter']['retained_base_adapter']['native_bytecode_contract']['getter_read_only_verified'] = 1
            refresh_envelope(changed)
            with self.subTest(provider=name, base_getter_proof=True), self.assertRaises(ValueError):
                self.verify(name, changed, data)

    def test_coordinated_historical_abc_forgery_cannot_relabel_the_pinned_baseline(self):
        for name in NAMES:
            record, data = fixture(name)
            changed = copy.deepcopy(record)
            changed['retained_transaction_adapter']['native_bytecode_contract']['abc_sha256'] = '0' * 64
            changed['communication_index_contract']['baseline_abc_sha256'] = '0' * 64
            refresh_envelope(changed)
            with self.subTest(provider=name), self.assertRaises(ValueError):
                self.verify(name, changed, data)

    def test_current_bytes_and_envelopes_cannot_be_substituted_or_downgraded(self):
        for name in NAMES:
            record, data = fixture(name)
            for field in ('base_resource_sha256', 'patched_resource_sha256',
                          'retained_transaction_sha256', 'postproof_sha256'):
                changed = copy.deepcopy(record)
                changed[field] = '0' * 64
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    self.verify(name, changed, data)
            with self.subTest(provider=name, bytes=True), self.assertRaises(ValueError):
                self.verify(name, record, data + b'changed')
            with self.subTest(provider=name, prior_bytes=True), self.assertRaises(ValueError):
                self.verify(name, record, (TRANSACTIONS / (name + '.swf')).read_bytes())


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file() and
                     (ROOT / 'dist/candidate/ApexCASBridge.package.manifest.json').is_file(),
                     'Private merged package and frozen provider continuations required')
class CurrentCommunicationManifestTests(unittest.TestCase):
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        historical_provider_fixture(self.info, self.resources, keep_dependency=False)
        for name in NAMES:
            record, data = fixture(name)
            key, text = KEYS[name], dbpf_build.tgi(KEYS[name])
            self.resources[key] = data
            self.info['grid_provider_adapters'][text] = record
            self.info['base_resources'][text] = record['base_resource_sha256']
            self.info['patched_resources'][text] = record['patched_resource_sha256']
            self.info['source_pins'].update(record['retained_transaction_adapter']['native_bytecode_contract']['source_sha256'])
            self.info['source_pins'].update(record['communication_index_contract']['source_sha256'])
            if name == 'donor':
                self.info['companion_code_merge']['grid_library_adapter'] = record

    def test_current_source_manifest_requires_both_complete_proof_source_sets(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        sources = set(maru_companion.GRID_TRANSACTION_PROOF_SOURCES) | set(maru_companion.GRID_COMMUNICATION_SOURCES)
        for source in sources:
            for action in ('missing', 'changed'):
                changed = copy.deepcopy(self.info)
                if action == 'missing':
                    del changed['source_pins'][source]
                else:
                    changed['source_pins'][source] = '0' * 64
                with self.subTest(source=source, action=action), self.assertRaises(ValueError):
                    maru_companion.verify_merged(changed, self.resources)
        for source in maru_companion.GRID_COMMUNICATION_SOURCES:
            self.assertIn(source, cas_ui_build.source_pins())

    def test_current_manifest_refuses_both_provider_downgrades_even_with_correct_inventory(self):
        for stage in ('transaction', 'getter'):
            changed, resources = copy.deepcopy(self.info), dict(self.resources)
            for name in NAMES:
                key, text = KEYS[name], dbpf_build.tgi(KEYS[name])
                prior = changed['grid_provider_adapters'][text]['retained_transaction_adapter']
                payload = (TRANSACTIONS / (name + '.swf')).read_bytes()
                if stage == 'getter':
                    prior = prior['retained_base_adapter']
                    payload = (ROOT / '.work/v328-grid-perf-native' / (name + '-profile.swf')).read_bytes()
                changed['grid_provider_adapters'][text] = prior
                changed['patched_resources'][text] = prior['patched_resource_sha256']
                resources[key] = payload
                if name == 'donor':
                    changed['companion_code_merge']['grid_library_adapter'] = prior
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed, resources)

    def test_mixed_native_provider_stages_are_refused(self):
        for name in NAMES:
            for stage in ('transaction', 'getter'):
                changed, resources = copy.deepcopy(self.info), dict(self.resources)
                key, text = KEYS[name], dbpf_build.tgi(KEYS[name])
                prior = changed['grid_provider_adapters'][text]['retained_transaction_adapter']
                payload = (TRANSACTIONS / (name + '.swf')).read_bytes()
                if stage == 'getter':
                    prior = prior['retained_base_adapter']
                    payload = (ROOT / '.work/v328-grid-perf-native' / (name + '-profile.swf')).read_bytes()
                changed['grid_provider_adapters'][text] = prior
                changed['patched_resources'][text] = prior['patched_resource_sha256']
                resources[key] = payload
                if name == 'donor':
                    changed['companion_code_merge']['grid_library_adapter'] = prior
                with self.subTest(provider=name, stage=stage), self.assertRaises(ValueError):
                    maru_companion.verify_grid_providers(changed['grid_provider_adapters'], resources)

    def test_manifest_inventory_and_donor_provider_evidence_are_exact(self):
        for name in NAMES:
            text = dbpf_build.tgi(KEYS[name])
            for field in ('base_resources', 'patched_resources'):
                changed = copy.deepcopy(self.info)
                changed[field][text] = '0' * 64
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    maru_companion.verify_merged(changed, self.resources)
        changed = copy.deepcopy(self.info)
        changed['companion_code_merge']['grid_library_adapter'] = changed['grid_provider_adapters'][dbpf_build.tgi(KEYS['canonical'])]
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(changed, self.resources)


if __name__ == '__main__':
    unittest.main()
