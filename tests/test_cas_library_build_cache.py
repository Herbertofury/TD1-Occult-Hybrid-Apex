"""Optional build reuse must authenticate all three exact native continuations."""
import ast
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,call

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_ui_build as ui
import dbpf_build as dbpf
import maru_companion as maru

PACKAGE = Path(os.environ.get('APEX_LIBRARY_CACHE_PACKAGE', ROOT / 'dist/candidate/ApexCASBridge.package'))
ORIGINALS = {
    maru.CANONICAL_GRID_LIBRARY: ROOT / '.work/research/ClassLibraryGamedata.swf',
    maru.GRID_LIBRARY: ROOT / '.work/research/maru-integrated/DynamicCASGridLibrary.swf',
    ui.CLEANUP_KEY: ROOT / '.work/research/OlympusLibrary.swf',
}
READY = PACKAGE.is_file() and Path(str(PACKAGE) + '.manifest.json').is_file() and all(
    path.is_file() for path in ORIGINALS.values())


@unittest.skipUnless(READY, 'Private compiled package and three original library fixtures required')
class VerifiedLibraryCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = PACKAGE.read_bytes()
        cls.original_info = json.loads(Path(str(PACKAGE) + '.manifest.json').read_text(encoding='utf-8'))
        cls.original_resources = dbpf.read(cls.raw)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / 'previous.package'
        self.manifest = Path(str(self.output) + '.manifest.json')
        self.info = copy.deepcopy(self.original_info)
        self.resources = dict(self.original_resources)
        self.publish()

    def publish(self, rebuild=False):
        raw = dbpf.build(self.resources) if rebuild else self.raw
        self.info['sha256'] = dbpf.digest(raw)
        self.output.write_bytes(raw)
        self.manifest.write_text(json.dumps(self.info), encoding='utf-8')

    def admit(self, originals=None):
        return ui.verified_library_cache(self.output, ORIGINALS if originals is None else originals)

    def test_actual_package_requires_current_complete_native_gate_and_returns_only_three_libraries(self):
        with patch.object(maru, 'verify_grid_providers', wraps=maru.verify_grid_providers) as verify:
            cache = self.admit()
        self.assertIsNotNone(cache)
        self.assertEqual(set(cache['resources']), set(ORIGINALS))
        self.assertNotIn(ui.KEY, cache['resources'])
        self.assertNotIn(ui.SELECTOR_KEY, cache['resources'])
        self.assertEqual(cache['used'], set())
        self.assertEqual(cache['providers'], self.info['grid_provider_adapters'])
        self.assertEqual(cache['dependencies'], self.info['communication_dependency_adapters'])
        self.assertEqual(verify.call_args_list[0],call(self.info['grid_provider_adapters'],cache['resources'],
                                                     self.info['communication_dependency_adapters']))
        # Every exact current terminal is verified, not merely its top wrapper.
        stages=('row_delta_contract','swatch_columns_contract','staging_attach_contract','publication_trace_contract',
                'featured_contract','budget_contract','slice_contract','scroll_contract',
                'swatch_provider_contract','progress_contract','product_rows_contract',
                'presentation_contract','grid_pool_contract')
        observed=[]
        for invocation in verify.call_args_list:
            providers=invocation.args[0]
            found=[stage for stage in stages if all(stage in adapter for adapter in providers.values())]
            self.assertEqual(len(found),1)
            observed.append(found[0])
        self.assertEqual(observed,list(stages))

    def test_missing_or_malformed_manifest_output_and_outer_hash_fall_back(self):
        for case in ('missing-output', 'missing-manifest', 'invalid-json', 'wrong-hash', 'wrong-map-type'):
            self.publish()
            if case == 'missing-output':
                self.output.unlink()
            elif case == 'missing-manifest':
                self.manifest.unlink()
            elif case == 'invalid-json':
                self.manifest.write_text('{', encoding='utf-8')
            elif case == 'wrong-hash':
                self.info['sha256'] = '0' * 64
                self.manifest.write_text(json.dumps(self.info), encoding='utf-8')
            else:
                self.info['base_resources'] = []
                self.publish()
            with self.subTest(case=case):
                self.assertIsNone(self.admit())
            self.info = copy.deepcopy(self.original_info)

    def test_actual_original_inputs_must_match_and_be_complete(self):
        for key in ORIGINALS:
            wrong = Path(self.temporary.name) / 'wrong-original.swf'
            wrong.write_bytes(ORIGINALS[key].read_bytes() + b'changed')
            for replacement in (wrong, wrong.with_name('missing.swf')):
                inputs = dict(ORIGINALS, **{})
                inputs[key] = replacement
                with self.subTest(key=key, replacement=replacement.name):
                    self.assertIsNone(self.admit(inputs))
        incomplete = dict(ORIGINALS)
        incomplete.pop(ui.CLEANUP_KEY)
        self.assertIsNone(self.admit(incomplete))

    def test_declared_input_and_output_hashes_must_match_every_library(self):
        for key in ORIGINALS:
            for field in ('base_resources', 'patched_resources'):
                self.info = copy.deepcopy(self.original_info)
                self.info[field][dbpf.tgi(key)] = '0' * 64
                self.publish()
                with self.subTest(key=key, field=field):
                    self.assertIsNone(self.admit())

    def test_forged_package_and_manifest_hash_do_not_authenticate_changed_final_library(self):
        for key in ORIGINALS:
            self.resources = dict(self.original_resources)
            self.info = copy.deepcopy(self.original_info)
            self.resources[key] += b'forged-final-bytes'
            self.info['patched_resources'][dbpf.tgi(key)] = dbpf.digest(self.resources[key])
            self.publish(rebuild=True)
            with self.subTest(key=key):
                self.assertIsNone(self.admit())

    def test_manifest_must_retain_actual_current_nested_source_pins(self):
        name = 'tools/cas_grid_pool.py'
        for mode in ('missing', 'changed'):
            self.info = copy.deepcopy(self.original_info)
            if mode == 'missing':
                self.info['source_pins'].pop(name)
            else:
                self.info['source_pins'][name] = '0' * 64
            self.publish()
            with self.subTest(mode=mode):
                self.assertIsNone(self.admit())

    def test_stale_history_or_current_gate_rejection_discards_entire_candidate(self):
        text = dbpf.tgi(maru.CANONICAL_GRID_LIBRARY)
        self.info['grid_provider_adapters'][text]['previous_stage_adapter']['patched_resource_sha256'] = '0' * 64
        self.publish()
        self.assertIsNone(self.admit())
        self.info = copy.deepcopy(self.original_info)
        self.publish()
        for outcome in (False, ValueError('Current native source/body proof changed')):
            kwargs = {'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome}
            with patch.object(maru, 'verify_grid_providers', **kwargs):
                self.assertIsNone(self.admit())

    def test_previous_stage_cannot_be_reused_as_current_complete_stage(self):
        for key in ORIGINALS:
            self.info = copy.deepcopy(self.original_info)
            field = 'communication_dependency_adapters' if key == ui.CLEANUP_KEY else 'grid_provider_adapters'
            proof = self.info[field][dbpf.tgi(key)]
            self.info[field][dbpf.tgi(key)] = proof['previous_stage_adapter']
            self.publish()
            with self.subTest(key=key):
                self.assertIsNone(self.admit())

    def test_all_exact_supported_prefixes_admit_only_the_missing_stage_continuation(self):
        import cas_grid_row_delta,cas_swatch_columns,cas_grid_staging_attach,cas_grid_publication,cas_grid_featured,cas_grid_budget
        for continuation in (cas_grid_row_delta,cas_swatch_columns,cas_grid_staging_attach,cas_grid_publication,cas_grid_featured,cas_grid_budget):
            for key in (maru.CANONICAL_GRID_LIBRARY,maru.GRID_LIBRARY):
                text=dbpf.tgi(key)
                previous,raw=continuation.historical(self.info['grid_provider_adapters'][text],self.resources[key])
                self.info['grid_provider_adapters'][text]=previous;self.resources[key]=raw
                self.info['patched_resources'][text]=dbpf.digest(raw)
            self.publish(rebuild=True)
            cache=self.admit();self.assertIsNotNone(cache)
            tree=ast.parse((ROOT/'tools/cas_ui_build.py').read_text())
            method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='adapt_grid_provider')
            seen=[]
            def finish(prior,retained,original,ffdec,work):
                seen.append((prior,retained))
                raise RuntimeError('verified prefix continuation reached')
            namespace=dict(vars(ui),maru_companion=maru,work=Path(self.temporary.name),ffdec='unused',
                java_classes=Path('unused'),finish_grid_provider=finish)
            namespace['run']=lambda *args:self.fail('A verified prefix recompiled an earlier native stage')
            exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual-verified-prefix>','exec'),namespace)
            for key in (maru.CANONICAL_GRID_LIBRARY,maru.GRID_LIBRARY):
                with self.subTest(stage=continuation.__name__,key=key),self.assertRaisesRegex(RuntimeError,'verified prefix continuation reached'):
                    namespace['adapt_grid_provider'](ORIGINALS[key],dbpf.digest(ORIGINALS[key].read_bytes()),'unused.abc',cache)
                self.assertEqual(seen[-1],(self.info['grid_provider_adapters'][dbpf.tgi(key)],self.resources[key]))

    def test_current_stage_inventory_must_be_typed_complete_and_cannot_throw_on_bad_history(self):
        text=dbpf.tgi(maru.GRID_LIBRARY)
        for position in range(7):
            for malformed in (None,False,[],"wrong"):
                self.info=copy.deepcopy(self.original_info);row=self.info['grid_provider_adapters'][text]
                for _ in range(position):row=row['previous_stage_adapter']
                row['previous_stage_adapter']=malformed
                self.publish()
                with self.subTest(position=position,malformed=malformed):self.assertIsNone(self.admit())

    def test_actual_historical_bytes_and_rehashed_manifest_are_valid_history_but_never_current_cache(self):
        import cas_swatch_provider,cas_grid_progress
        self.rollback_to_swatch()
        for continuation in (cas_swatch_provider,cas_grid_progress):
            providers=self.info['grid_provider_adapters']
            for key in (maru.CANONICAL_GRID_LIBRARY,maru.GRID_LIBRARY):
                text=dbpf.tgi(key)
                providers[text],self.resources[key]=continuation.historical(providers[text],self.resources[key])
                self.info['patched_resources'][text]=dbpf.digest(self.resources[key])
            # This is the original regression: all old bytes/proofs are valid,
            # and the package+manifest hashes honestly name those old bytes.
            self.assertTrue(maru.verify_grid_providers(providers,self.resources,self.info['communication_dependency_adapters']))
            self.publish(rebuild=True)
            with self.subTest(stage=continuation.__name__):self.assertIsNone(self.admit())

    def test_rejected_historical_grid_cache_enters_actual_fresh_builder_branch(self):
        import cas_swatch_provider
        self.rollback_to_swatch()
        for key in (maru.CANONICAL_GRID_LIBRARY,maru.GRID_LIBRARY):
            text=dbpf.tgi(key);adapter=self.info['grid_provider_adapters'][text]
            adapter,self.resources[key]=cas_swatch_provider.historical(adapter,self.resources[key])
            self.info['grid_provider_adapters'][text]=adapter
            self.info['patched_resources'][text]=dbpf.digest(self.resources[key])
        self.publish(rebuild=True);cache=self.admit();self.assertIsNone(cache)
        tree=ast.parse((ROOT/'tools/cas_ui_build.py').read_text(encoding='utf-8'))
        build=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build')
        method=next(n for n in build.body if isinstance(n,ast.FunctionDef) and n.name=='adapt_grid_provider')
        namespace=dict(vars(ui),maru_companion=maru,work=Path(self.temporary.name),ffdec=Path('unused-ffdec'),java_classes=Path('unused-classes'))
        def compiler(*args):raise RuntimeError('fresh current native compiler reached')
        namespace['run']=compiler
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual-fresh-provider>','exec'),namespace)
        for key in (maru.CANONICAL_GRID_LIBRARY,maru.GRID_LIBRARY):
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'fresh current native compiler reached'):
                namespace['adapt_grid_provider'](ORIGINALS[key],dbpf.digest(ORIGINALS[key].read_bytes()),'unused.abc',cache)

    def rollback_to_swatch(self):
        """Authenticate all newer provider heads before older-history fixtures.

        Library cache gates intentionally ignore unrelated Main/selector bytes;
        this fixture only changes actual provider bytes/proofs, never relabels a
        resource as its predecessor or weakens the complete provider verifier.
        """
        import cas_grid_row_delta,cas_swatch_columns,cas_grid_staging_attach,cas_grid_publication,cas_grid_featured,cas_grid_budget,cas_grid_slice,cas_grid_scroll
        for continuation in (cas_grid_row_delta,cas_swatch_columns,cas_grid_staging_attach,cas_grid_publication,cas_grid_featured,cas_grid_budget,cas_grid_slice,cas_grid_scroll):
            for key in (maru.CANONICAL_GRID_LIBRARY,maru.GRID_LIBRARY):
                text=dbpf.tgi(key);adapter=self.info['grid_provider_adapters'][text]
                previous,raw=continuation.historical(adapter,self.resources[key])
                self.info['grid_provider_adapters'][text]=previous;self.resources[key]=raw
                self.info['patched_resources'][text]=dbpf.digest(raw)

    def test_unrelated_main_and_selector_are_never_reused_or_required_to_match_prior_source(self):
        self.info['source_pins']['Source/CASUi/semantic_methods.as'] = '0' * 64
        self.info['source_pins']['Source/CASUi/selector_methods.as'] = '0' * 64
        for key in (ui.KEY, ui.SELECTOR_KEY):
            self.resources[key] = b'These resources must be freshly compiled, never reused.'
            self.info['patched_resources'][dbpf.tgi(key)] = dbpf.digest(self.resources[key])
        self.publish(rebuild=True)
        cache = self.admit()
        self.assertIsNotNone(cache)
        self.assertEqual(set(cache['resources']), set(ORIGINALS))

    def test_actual_builder_cache_branches_bypass_compilers_and_return_exact_proofs(self):
        cache = self.admit()
        self.assertIsNotNone(cache)
        tree = ast.parse((ROOT / 'tools/cas_ui_build.py').read_text(encoding='utf-8'))
        build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
        method = next(n for n in build.body if isinstance(n, ast.FunctionDef) and n.name == 'adapt_grid_provider')
        namespace = dict(vars(ui), maru_companion=maru, work=Path(self.temporary.name),
                         ffdec=Path('unused-ffdec'), java_classes=Path('unused-classes'))
        namespace['run'] = lambda *args: self.fail('Verified cached library invoked a compiler')
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<actual-cached-provider>', 'exec'), namespace)
        for key in (maru.CANONICAL_GRID_LIBRARY, maru.GRID_LIBRARY):
            payload, proof = namespace['adapt_grid_provider'](
                ORIGINALS[key], dbpf.digest(ORIGINALS[key].read_bytes()), 'unused.abc', cache)
            self.assertEqual(payload, self.original_resources[key])
            self.assertEqual(proof, self.info['grid_provider_adapters'][dbpf.tgi(key)])
        with patch.object(ui, 'run', side_effect=AssertionError('Cached dependency invoked compiler')):
            payload, proof = ui.adapt_dependency_provider(ORIGINALS[ui.CLEANUP_KEY], None, None, cache)
        self.assertEqual(payload, self.original_resources[ui.CLEANUP_KEY])
        self.assertEqual(proof, self.info['communication_dependency_adapters'][dbpf.tgi(ui.CLEANUP_KEY)])
        self.assertEqual(cache['used'], {dbpf.tgi(key) for key in ORIGINALS})

    def test_rejected_cache_enters_the_original_dependency_compiler_path(self):
        import cas_communication_dependency as dependency
        with patch.object(maru, 'verify_grid_providers', return_value=False):
            cache = self.admit()
        self.assertIsNone(cache)
        with patch.object(dependency, 'adapt', side_effect=RuntimeError('fresh compiler reached')) as adapt:
            with self.assertRaisesRegex(RuntimeError, 'fresh compiler reached'):
                ui.adapt_dependency_provider(ORIGINALS[ui.CLEANUP_KEY], Path('ffdec'), Path(self.temporary.name), cache)
            adapt.assert_called_once()


class BuilderCacheIntegrationTests(unittest.TestCase):
    def test_final_source_and_full_merged_package_gates_remain_after_fresh_build(self):
        tree = ast.parse((ROOT / 'tools/cas_ui_build.py').read_text(encoding='utf-8'))
        build = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
        calls = [(n.lineno, ast.unparse(n.func)) for n in ast.walk(build) if isinstance(n, ast.Call)]
        cache_line = next(line for line, name in calls if name == 'verified_library_cache')
        final_line = next(line for line, name in calls if name == 'maru_companion.verify_merged')
        source_lines = [line for line, name in calls if name == 'source_pins']
        self.assertTrue(any(cache_line < line < final_line for line in source_lines))
        self.assertTrue(any(isinstance(n, ast.Constant) and n.value == 'cached_library_resources' for n in ast.walk(build)))
        self.assertFalse(any(isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and
                             n.value.id == 'library_cache' and isinstance(n.slice, ast.Constant) and
                             n.slice.value == 'resources' for n in ast.walk(build)))


if __name__ == '__main__':
    unittest.main()
