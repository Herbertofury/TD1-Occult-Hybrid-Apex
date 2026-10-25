"""Exercise the actual build seam and both authenticated provider proof chains."""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_grid_transaction
import cas_communication_index
import cas_communication_domain_probe
import cas_communication_removal_miss
import cas_image_boundary_profile
import cas_grid_pool
import cas_ui_build
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_provider_fixture

FINAL = ROOT / '.work/v331-grid-selection-final'


def abc(raw):
    tag = next(t[3] for t in cas_ui_build.tags(cas_ui_build.unpack(raw)[1]) if t[0] == 82)
    return tag[tag.index(b'\0', 4) + 1:]


class TransactionPinTests(unittest.TestCase):
    def test_current_build_pins_both_transaction_inputs(self):
        for source in maru_companion.GRID_TRANSACTION_PROOF_SOURCES:
            self.assertIn(source, cas_ui_build.source_pins())


@unittest.skipUnless(all((FINAL / (name + suffix)).is_file()
                        for name in ('canonical', 'donor') for suffix in ('.json', '.swf')),
                     'Private compiled transaction provider fixtures required')
class TransactionProviderChainTests(unittest.TestCase):
    """The Tx fixtures are historical after the communication continuation."""
    def fixtures(self):
        return [(name, json.loads((FINAL / (name + '.json')).read_text()),
                 (FINAL / (name + '.swf')).read_bytes()) for name in ('canonical', 'donor')]

    def test_historical_transaction_providers_keep_precise_native_body_counts(self):
        for name, proof, raw in self.fixtures():
            with self.subTest(provider=name):
                verify = (maru_companion.verify_canonical_grid_adapter if name == 'canonical'
                          else maru_companion.verify_grid_adapter)
                self.assertTrue(verify(proof, raw))
                post = proof['native_bytecode_contract']
                original_bodies = 8928 if name == 'canonical' else 8224
                self.assertEqual(post['original_method_body_count'], original_bodies)
                self.assertEqual(post['unchanged_original_native_bodies'], original_bodies - 17)
                self.assertEqual(post['unchanged_baseline_bodies'], original_bodies + 3 - 18)
                self.assertNotEqual(post['original_method_info_count'], original_bodies)

    def test_duplicate_native_providers_cannot_mix_historical_and_transaction_stages(self):
        providers, resources = {}, {}
        for name, proof, raw in self.fixtures():
            key = maru_companion.CANONICAL_GRID_LIBRARY if name == 'canonical' else maru_companion.GRID_LIBRARY
            providers[dbpf_build.tgi(key)] = proof
            resources[key] = raw
        self.assertTrue(maru_companion.verify_grid_providers(providers, resources))
        for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY), ('donor', maru_companion.GRID_LIBRARY)]:
            altered, payloads = copy.deepcopy(providers), dict(resources)
            altered[dbpf_build.tgi(key)] = altered[dbpf_build.tgi(key)]['retained_base_adapter']
            payloads[key] = (ROOT / '.work/v328-grid-perf-native' / (name + '-profile.swf')).read_bytes()
            with self.subTest(provider=name), self.assertRaisesRegex(ValueError, 'same reviewed adapter stage'):
                maru_companion.verify_grid_providers(altered, payloads)

    def test_rejects_altered_history_abc_final_hash_projections_and_claimed_runtime(self):
        for name, proof, raw in self.fixtures():
            verify = (maru_companion.verify_canonical_grid_adapter if name == 'canonical'
                      else maru_companion.verify_grid_adapter)
            cases = [(['retained_base_adapter', 'patched_resource_sha256'], '0' * 64),
                     (['retained_base_adapter', 'native_bytecode_contract', 'getter_read_only_verified'], 1),
                     (['base_resource_sha256'], '0' * 64), (['patched_resource_sha256'], '0' * 64)]
            post_cases = [('abc_sha256', '0' * 64), ('baseline_swf_sha256', '0' * 64),
                          ('provider_resource_tgi', dbpf_build.tgi(maru_companion.UNMODIFIED_OLYMPUS_LIBRARY)),
                          ('original_method_info_count', 8928 if name == 'canonical' else 8224),
                          ('original_method_body_count', 9194 if name == 'canonical' else 8479),
                          ('baseline_method_info_count', 0), ('baseline_method_body_count', 0),
                          ('unchanged_original_native_bodies', 0), ('unchanged_baseline_bodies', 0),
                          ('guarded_existing_adapter_bodies', 0), ('appended_fields', 2),
                          ('whole_abc_rollback_verified', 1), ('serialized_projection_verified', False),
                          ('unarmed_original_native_flow_verified', False), ('runtime_qualified', True),
                          ('hitch_free_claimed', True)]
            cases += [(['native_bytecode_contract', key], value) for key, value in post_cases]
            for path, value in cases:
                changed = copy.deepcopy(proof)
                target = changed
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.subTest(provider=name, field=path), self.assertRaises(ValueError):
                    verify(changed, raw)
            with self.subTest(provider=name, changed_bytes=True), self.assertRaises(ValueError):
                verify(proof, raw + b'changed')

    def test_actual_nested_grid_builder_seam_chains_all_frozen_stages(self):
        tree = ast.parse(Path(cas_ui_build.__file__).read_text())
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == 'adapt_grid_provider')
        for name, transaction, transaction_bytes in self.fixtures():
            stage = ROOT / ('.work/v331-comm-index-stage-' + name)
            communication = json.loads((stage / 'chained.json').read_text())
            communication_bytes = (stage / 'final.swf').read_bytes()
            domain_stage = ROOT / ('.work/v332-domain-probe-' + name)
            domain = json.loads((domain_stage / 'chained.json').read_text())
            domain_bytes = (domain_stage / 'final.swf').read_bytes()
            removal_stage = ROOT / ('.work/v333-removal-miss-' + name)
            removal = json.loads((removal_stage / 'chained.json').read_text())
            removal_bytes = (removal_stage / 'final.swf').read_bytes()
            image_stage = ROOT / ('.work/v334-image-profile-' + name)
            image = json.loads((image_stage / 'chained.json').read_text())
            image_bytes = (image_stage / 'final.swf').read_bytes()
            pool_stage = ROOT / ('.work/v335-grid-pool-' + name)
            pooled = json.loads((pool_stage / 'chained.json').read_text())
            final = (pool_stage / 'final.swf').read_bytes()
            self.assertEqual(pooled['previous_stage_adapter'], image)
            self.assertEqual(image['previous_stage_adapter'], removal)
            self.assertEqual(removal['previous_stage_adapter'], domain)
            self.assertEqual(domain['previous_stage_adapter'], communication)
            self.assertEqual(communication['retained_transaction_adapter'], transaction)
            baseline = (ROOT / '.work/v328-grid-perf-native' / (name + '-profile.swf')).read_bytes()
            original = (ROOT / ('.work/research/ClassLibraryGamedata.swf' if name == 'canonical'
                        else '.work/research/maru-integrated/DynamicCASGridLibrary.swf'))
            with self.subTest(provider=name), tempfile.TemporaryDirectory() as directory:
                work, order = Path(directory), []
                def run(args):
                    self.assertIn('CasGridBytecodePatch', args)
                    Path(args[-1]).write_bytes(abc(baseline))
                    order.append('getter-profile')
                    return SimpleNamespace(stdout=json.dumps(transaction['retained_base_adapter']['native_bytecode_contract']))
                def adapt_transaction(*args):
                    order.append('transaction')
                    self.assertEqual(args[1], baseline)
                    self.assertIsNone(args[2])
                    return abc(transaction_bytes), transaction['native_bytecode_contract']
                def adapt_communication(*args):
                    order.append('communication')
                    self.assertEqual(args[1], transaction_bytes)
                    self.assertIsNone(args[2])
                    return abc(communication_bytes), communication['communication_index_contract']
                def adapt_domain(*args):
                    order.append('domain')
                    self.assertEqual(Path(args[0]).read_bytes(), communication_bytes)
                    return abc(domain_bytes), domain['communication_domain_probe_contract']
                def adapt_removal(*args):
                    order.append('removal')
                    self.assertEqual(Path(args[0]).read_bytes(), original.read_bytes())
                    self.assertEqual(Path(args[1]).read_bytes(), domain_bytes)
                    return abc(removal_bytes), removal['communication_removal_miss_contract']
                def adapt_image(*args):
                    order.append('image')
                    self.assertEqual(Path(args[0]).read_bytes(), original.read_bytes())
                    self.assertEqual(Path(args[1]).read_bytes(), removal_bytes)
                    return abc(image_bytes), image['image_boundary_profile_contract']
                def adapt_pool(*args):
                    order.append('pool')
                    self.assertEqual(Path(args[0]).read_bytes(), original.read_bytes())
                    self.assertEqual(Path(args[1]).read_bytes(), image_bytes)
                    return abc(final), pooled['grid_pool_contract']
                namespace = vars(cas_ui_build).copy()
                namespace.update(work=work, ffdec=ROOT / '.work/research/ffdec/ffdec-cli.exe',
                                 java_classes=work, run=run)
                exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-provider-seam>', 'exec'), namespace)
                with patch.object(cas_grid_transaction, 'adapt', side_effect=adapt_transaction), \
                     patch.object(cas_communication_index, 'adapt', side_effect=adapt_communication), \
                     patch.object(cas_communication_domain_probe, 'adapt', side_effect=adapt_domain), \
                     patch.object(cas_communication_removal_miss, 'adapt', side_effect=adapt_removal), \
                     patch.object(cas_image_boundary_profile, 'adapt', side_effect=adapt_image), \
                     patch.object(cas_grid_pool, 'adapt', side_effect=adapt_pool):
                    data, chained = namespace['adapt_grid_provider'](original, transaction['base_resource_sha256'], name + '.abc')
                self.assertEqual(order, ['getter-profile', 'transaction', 'communication', 'domain', 'removal', 'image', 'pool'])
                self.assertEqual(data, final)
                self.assertEqual(chained, pooled)
                verify = maru_companion.verify_canonical_grid_adapter if name == 'canonical' else maru_companion.verify_grid_adapter
                self.assertTrue(verify(chained, data))
                with self.assertRaisesRegex(ValueError, 'authenticated native resource'):
                    namespace['adapt_grid_provider'](original, '0' * 64, name + '.abc')


@unittest.skipUnless((ROOT / 'dist/candidate/ApexCASBridge.package').is_file() and
                     (ROOT / 'dist/candidate/ApexCASBridge.package.manifest.json').is_file() and
                     (FINAL / 'canonical.json').is_file() and (FINAL / 'donor.json').is_file(),
                     'Private retained CAS package and compiled transaction fixtures required')
class HistoricalTransactionManifestTests(unittest.TestCase):
    """Archived Tx manifests predate the communication source requirement."""
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        historical_provider_fixture(self.info, self.resources, keep_dependency=False)
        for source in maru_companion.GRID_COMMUNICATION_SOURCES:
            self.info['source_pins'].pop(source, None)
        for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY), ('donor', maru_companion.GRID_LIBRARY)]:
            proof = json.loads((FINAL / (name + '.json')).read_text())
            self.resources[key] = (FINAL / (name + '.swf')).read_bytes()
            text = dbpf_build.tgi(key)
            self.info['grid_provider_adapters'][text] = proof
            self.info['base_resources'][text] = proof['base_resource_sha256']
            self.info['patched_resources'][text] = proof['patched_resource_sha256']
            self.info['source_pins'].update(proof['native_bytecode_contract']['source_sha256'])
            if name == 'donor':
                self.info['companion_code_merge']['grid_library_adapter'] = proof

    def test_historical_transaction_manifest_requires_both_exact_transaction_source_proofs(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for source in maru_companion.GRID_TRANSACTION_PROOF_SOURCES:
            altered = copy.deepcopy(self.info)
            altered['source_pins'][source] = '0' * 64
            with self.subTest(source=source), self.assertRaises(ValueError):
                maru_companion.verify_merged(altered, self.resources)
        altered = copy.deepcopy(self.info)
        del altered['source_pins']['tools/cas_grid_transaction.py']
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            maru_companion.verify_merged(altered, self.resources)

    def test_historical_transaction_manifest_refuses_getter_downgrade(self):
        for name, key in [('canonical', maru_companion.CANONICAL_GRID_LIBRARY), ('donor', maru_companion.GRID_LIBRARY)]:
            altered, resources = copy.deepcopy(self.info), dict(self.resources)
            text = dbpf_build.tgi(key)
            history = altered['grid_provider_adapters'][text]['retained_base_adapter']
            altered['grid_provider_adapters'][text] = history
            altered['patched_resources'][text] = history['patched_resource_sha256']
            resources[key] = (ROOT / '.work/v328-grid-perf-native' / (name + '-profile.swf')).read_bytes()
            if name == 'donor':
                altered['companion_code_merge']['grid_library_adapter'] = history
            with self.subTest(provider=name), self.assertRaisesRegex(ValueError, 'chained grid transaction|same reviewed adapter stage'):
                maru_companion.verify_merged(altered, resources)

    def test_provider_manifest_hash_and_dependency_classification_must_match(self):
        for key in self.info['grid_provider_adapters']:
            for field in ('base_resources', 'patched_resources'):
                altered = copy.deepcopy(self.info)
                altered[field][key] = '0' * 64
                with self.subTest(provider=key, field=field), self.assertRaises(ValueError):
                    maru_companion.verify_merged(altered, self.resources)
        altered = copy.deepcopy(self.info)
        altered.setdefault('unmodified_dependency_resources', {})[dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)] = '0' * 64
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(altered, self.resources)


if __name__ == '__main__':
    unittest.main()
