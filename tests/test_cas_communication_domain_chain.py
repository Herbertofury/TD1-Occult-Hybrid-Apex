"""Real final domain envelopes and mocked compiler seams; no game/Java calls."""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_communication_dependency as dependency
import cas_communication_domain_probe as domain
import cas_communication_index as communication
import cas_communication_removal_miss as removal
import cas_image_boundary_profile as image
import cas_grid_pool as pool
import cas_grid_presentation as presentation
import cas_ui_build
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_domain_fixture

KINDS = {'canonical': maru_companion.CANONICAL_GRID_LIBRARY,
         'donor': maru_companion.GRID_LIBRARY,
         'dependency': maru_companion.UNMODIFIED_OLYMPUS_LIBRARY}
READY = all((ROOT / ('.work/v332-domain-probe-' + name) / suffix).is_file()
            for name in KINDS for suffix in ('chained.json', 'final.swf'))


def fixture(name):
    path = ROOT / ('.work/v332-domain-probe-' + name)
    return json.loads((path / 'chained.json').read_text()), (path / 'final.swf').read_bytes()


def previous_bytes(name):
    path = (ROOT / '.work/v332-communication-dependency' if name == 'dependency'
            else ROOT / ('.work/v331-comm-index-stage-' + name))
    return (path / 'final.swf').read_bytes()


def abc(raw):
    tag = next(t[3] for t in cas_ui_build.tags(cas_ui_build.unpack(raw)[1]) if t[0] == 82)
    return tag[tag.index(b'\0', 4) + 1:]


def refresh_envelope(record):
    record['previous_stage_sha256'] = communication.contract_digest(record['previous_stage_adapter'])
    record['postproof_sha256'] = communication.contract_digest(record['communication_domain_probe_contract'])


@unittest.skipUnless(READY, 'All three private frozen domain-probe stages required')
class DomainContinuationTests(unittest.TestCase):
    def test_all_three_exact_final_bytes_keep_previous_stage_separate(self):
        for name in KINDS:
            record, data = fixture(name)
            with self.subTest(provider=name):
                self.assertTrue(domain.verify_adapter(record, data))
                self.assertEqual(record['patched_resource_sha256'], dbpf_build.digest(data))
                before = record['previous_stage_adapter']
                post = record['communication_domain_probe_contract']
                self.assertEqual(post['baseline_swf_sha256'], before['patched_resource_sha256'])
                self.assertEqual(dbpf_build.digest(previous_bytes(name)), before['patched_resource_sha256'])
                self.assertEqual(post['changed_native_bodies'], 0)
                self.assertEqual(post['appended_methods'], 2 if name == 'dependency' else 3)
                self.assertEqual(post['replaced_owned_button_bodies'], int(name == 'dependency'))
                self.assertFalse(post['runtime_qualified'])
                self.assertFalse(post['hitch_free_claimed'])
                self.assertNotEqual(post['abc_sha256'], post['baseline_abc_sha256'])
                if name == 'dependency':
                    self.assertNotIn('retained_transaction_adapter', before)
                    self.assertIs(before['communication_dependency_contract']['grid_stage_present'], False)
                else:
                    verify = maru_companion.verify_canonical_grid_adapter if name == 'canonical' else maru_companion.verify_grid_adapter
                    self.assertTrue(verify(record, data))

    def test_mutated_domain_claims_fail_even_when_the_envelope_hash_is_recomputed(self):
        changes = [('phase', 'other'), ('provider_resource_tgi', '62ECC59A:00000000:0'),
                   ('baseline_swf_sha256', '0' * 64), ('baseline_abc_sha256', '0' * 64), ('abc_sha256', '0' * 64),
                   ('changed_native_bodies', 1), ('appended_methods', 1), ('replaced_owned_button_bodies', 2),
                   ('whole_abc_rollback_verified', 1), ('original_index_bodies_retained', False),
                   ('actual_listener_instance_read_verified', False), ('protected_singleton_binding_verified', False),
                   ('public_native_array_not_exposed', False), ('no_dispatch_write_or_services', False),
                   ('runtime_qualified', True), ('hitch_free_claimed', True)]
        for name in KINDS:
            record, data = fixture(name)
            for field, value in changes:
                changed = copy.deepcopy(record)
                changed['communication_domain_probe_contract'][field] = value
                refresh_envelope(changed)
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    domain.verify_adapter(changed, data)
            for source in domain.SOURCES:
                changed = copy.deepcopy(record)
                changed['communication_domain_probe_contract']['source_sha256'][source] = '0' * 64
                refresh_envelope(changed)
                with self.subTest(provider=name, source=source), self.assertRaises(ValueError):
                    domain.verify_adapter(changed, data)

    def test_historical_metadata_forgery_and_substituted_final_bytes_are_refused(self):
        for name in KINDS:
            record, data = fixture(name)
            for field in ('base_resource_sha256', 'patched_resource_sha256', 'previous_stage_sha256', 'postproof_sha256'):
                changed = copy.deepcopy(record)
                changed[field] = '0' * 64
                with self.subTest(provider=name, field=field), self.assertRaises(ValueError):
                    domain.verify_adapter(changed, data)
            changed = copy.deepcopy(record)
            prior = changed['previous_stage_adapter']
            contract = prior.get('communication_dependency_contract', prior.get('communication_index_contract'))
            contract['whole_abc_rollback_verified'] = False
            prior['postproof_sha256'] = communication.contract_digest(contract)
            refresh_envelope(changed)
            with self.subTest(provider=name, forged_history=True), self.assertRaises(ValueError):
                domain.verify_adapter(changed, data)
            for payload in (previous_bytes(name), data + b'changed'):
                with self.subTest(provider=name, bytes=dbpf_build.digest(payload)), self.assertRaises(ValueError):
                    domain.verify_adapter(record, payload)

    def test_actual_dependency_builder_block_chains_index_domain_removal_image_and_presentation(self):
        tree = ast.parse(Path(cas_ui_build.__file__).read_text())
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'adapt_dependency_provider')
        record, domain_bytes = fixture('dependency')
        removal_stage = ROOT / '.work/v333-removal-miss-dependency'
        removal_record = json.loads((removal_stage / 'chained.json').read_text())
        removal_bytes = (removal_stage / 'final.swf').read_bytes()
        image_stage = ROOT / '.work/v334-image-profile-dependency'
        latest = json.loads((image_stage / 'chained.json').read_text())
        final = (image_stage / 'final.swf').read_bytes()
        package=ROOT/'dist/candidate/ApexCASBridge.package'
        current=json.loads(Path(str(package)+'.manifest.json').read_text())
        current_resources=dbpf_build.read(package.read_bytes())
        dependency_key=maru_companion.UNMODIFIED_OLYMPUS_LIBRARY
        presentation_adapter=current['communication_dependency_adapters'][dbpf_build.tgi(dependency_key)]
        presentation_final=current_resources[dependency_key]
        self.assertTrue(presentation.verify_adapter(presentation_adapter,presentation_final))
        old_adapter,old_bytes=presentation.previous(presentation_adapter,presentation_final)
        self.assertEqual(old_adapter,latest);self.assertEqual(old_bytes,final)
        self.assertEqual(latest['previous_stage_adapter'], removal_record)
        self.assertEqual(removal_record['previous_stage_adapter'], record)
        prior = record['previous_stage_adapter']
        baseline = previous_bytes('dependency')
        with tempfile.TemporaryDirectory() as directory:
            namespace = vars(cas_ui_build).copy()
            namespace.update(work=Path(directory), ffdec=ROOT / '.work/research/ffdec/ffdec-cli.exe',
                             cleanup_library=ROOT / '.work/research/OlympusLibrary.swf')
            order = []
            def adapt_dependency(*args):
                order.append('dependency')
                self.assertEqual(Path(args[0]).read_bytes(), namespace['cleanup_library'].read_bytes())
                return abc(baseline), prior['communication_dependency_contract']
            def adapt_domain(*args):
                order.append('domain')
                self.assertEqual(Path(args[0]).read_bytes(), baseline)
                return abc(domain_bytes), record['communication_domain_probe_contract']
            def adapt_removal(*args):
                order.append('removal')
                self.assertEqual(Path(args[0]).read_bytes(), namespace['cleanup_library'].read_bytes())
                self.assertEqual(Path(args[1]).read_bytes(), domain_bytes)
                return abc(removal_bytes), removal_record['communication_removal_miss_contract']
            def adapt_image(*args):
                order.append('image')
                self.assertEqual(Path(args[0]).read_bytes(), namespace['cleanup_library'].read_bytes())
                self.assertEqual(Path(args[1]).read_bytes(), removal_bytes)
                return abc(final), latest['image_boundary_profile_contract']
            def adapt_presentation(*args):
                order.append('presentation')
                self.assertEqual(args[0],latest)
                self.assertEqual(args[1],final)
                self.assertEqual(args[2],namespace['cleanup_library'])
                return presentation_final,presentation_adapter
            with patch.object(dependency, 'adapt', side_effect=adapt_dependency), patch.object(domain, 'adapt', side_effect=adapt_domain), \
                 patch.object(removal, 'adapt', side_effect=adapt_removal), \
                 patch.object(image, 'adapt', side_effect=adapt_image), \
                 patch.object(presentation, 'adapt', side_effect=adapt_presentation), \
                 patch.object(pool, 'adapt', side_effect=AssertionError('Dependency must stay image-final')):
                exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-dependency-seam>', 'exec'), namespace)
                output, adapter = namespace['adapt_dependency_provider'](
                    namespace['cleanup_library'], namespace['ffdec'], namespace['work'], cache=None)
            self.assertEqual(order, ['dependency', 'domain', 'removal', 'image', 'presentation'])
            self.assertEqual(output, presentation_final)
            self.assertEqual(adapter, presentation_adapter)


@unittest.skipUnless(READY and (ROOT / 'dist/candidate/ApexCASBridge.package').is_file() and
                     (ROOT / 'dist/candidate/ApexCASBridge.package.manifest.json').is_file(),
                     'Private compiled merge and three frozen domain stages required')
class HistoricalDomainManifestTests(unittest.TestCase):
    """These domain-pinned V332 manifests explicitly predate removal sources."""
    def setUp(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        self.info = json.loads(Path(str(package) + '.manifest.json').read_text())
        self.resources = dbpf_build.read(package.read_bytes())
        historical_domain_fixture(self.info, self.resources)
        self.info['communication_dependency_adapters'] = {}
        for name, key in KINDS.items():
            record, data = fixture(name)
            text = dbpf_build.tgi(key)
            prior = record['previous_stage_adapter']
            self.resources[key] = data
            self.info['base_resources'][text] = record['base_resource_sha256']
            self.info['patched_resources'][text] = record['patched_resource_sha256']
            self.info['source_pins'].update(record['communication_domain_probe_contract']['source_sha256'])
            if name == 'dependency':
                self.info['communication_dependency_adapters'][text] = record
                self.info['source_pins'].update(prior['communication_dependency_contract']['source_sha256'])
                self.info.setdefault('unmodified_dependency_resources', {}).pop(text, None)
            else:
                self.info['grid_provider_adapters'][text] = record
                self.info['source_pins'].update(prior['communication_index_contract']['source_sha256'])
                self.info['source_pins'].update(prior['retained_transaction_adapter']['native_bytecode_contract']['source_sha256'])
                if name == 'donor':
                    self.info['companion_code_merge']['grid_library_adapter'] = record
        self.info['resources'] = sorted(dbpf_build.tgi(key) for key in self.resources)

    def test_current_manifest_authenticates_all_three_final_wrappers_and_source_sets(self):
        self.assertTrue(maru_companion.verify_merged(self.info, self.resources))
        for source in domain.SOURCES:
            self.assertIn(source, cas_ui_build.source_pins())
            for action in ('missing', 'changed'):
                altered = copy.deepcopy(self.info)
                if action == 'missing':
                    del altered['source_pins'][source]
                else:
                    altered['source_pins'][source] = '0' * 64
                with self.subTest(source=source, action=action), self.assertRaises(ValueError):
                    maru_companion.verify_merged(altered, self.resources)

    def test_current_manifest_refuses_partial_or_full_domain_downgrade(self):
        for names in [('canonical',), ('donor',), ('dependency',), tuple(KINDS)]:
            altered, resources = copy.deepcopy(self.info), dict(self.resources)
            for name in names:
                key, text = KINDS[name], dbpf_build.tgi(KINDS[name])
                group = altered['communication_dependency_adapters'] if name == 'dependency' else altered['grid_provider_adapters']
                prior = group[text]['previous_stage_adapter']
                group[text] = prior
                altered['patched_resources'][text] = prior['patched_resource_sha256']
                resources[key] = previous_bytes(name)
                if name == 'donor':
                    altered['companion_code_merge']['grid_library_adapter'] = prior
            with self.subTest(downgrade=names), self.assertRaises(ValueError):
                maru_companion.verify_merged(altered, resources)

    def test_wrappers_cannot_strip_both_domain_source_names_or_hide_dependency(self):
        altered = copy.deepcopy(self.info)
        for source in maru_companion.GRID_COMMUNICATION_DOMAIN_SOURCES:
            del altered['source_pins'][source]
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(altered, self.resources)
        altered, resources = copy.deepcopy(self.info), dict(self.resources)
        del resources[KINDS['dependency']]
        del altered['communication_dependency_adapters']
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(altered, resources)

    def test_explicit_pre_domain_three_provider_manifest_remains_historical(self):
        altered, resources = copy.deepcopy(self.info), dict(self.resources)
        for source in maru_companion.GRID_COMMUNICATION_DOMAIN_SOURCES:
            del altered['source_pins'][source]
        for name, key in KINDS.items():
            text = dbpf_build.tgi(key)
            group = altered['communication_dependency_adapters'] if name == 'dependency' else altered['grid_provider_adapters']
            prior = group[text]['previous_stage_adapter']
            group[text] = prior
            altered['patched_resources'][text] = prior['patched_resource_sha256']
            resources[key] = previous_bytes(name)
            if name == 'donor':
                altered['companion_code_merge']['grid_library_adapter'] = prior
        self.assertTrue(maru_companion.verify_merged(altered, resources))


if __name__ == '__main__':
    unittest.main()
