"""Append-only getter, serialized native retention and exact donor merge gates."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import cas_ui_build
import dbpf_build
import maru_companion
from cas_provider_chain_fixtures import historical_provider_fixture

JAR = ROOT / '.work/research/ffdec/ffdec.jar'
JAVA = shutil.which('java')
JAVAC = shutil.which('javac')


def original_grid():
    for path in (ROOT / '.work/research/maru-integrated/DynamicCASGridLibrary.swf',
                 ROOT / '.work/v325-grid-getter/original.swf'):
        if path.is_file() and dbpf_build.digest(path.read_bytes()) == maru_companion.GRID_LIBRARY_SHA256:
            return path.read_bytes()
    package = ROOT / 'dist/candidate/ApexCASBridge.package'
    if package.is_file():
        raw = dbpf_build.read(package.read_bytes()).get(maru_companion.GRID_LIBRARY)
        if raw is not None and dbpf_build.digest(raw) == maru_companion.GRID_LIBRARY_SHA256:
            return raw
    raise unittest.SkipTest('The authenticated private donor grid resource is required')


def original_canonical_grid():
    for name in ('ClassLibraryGamedata.swf', 'current-class-library.swf',
                 'native-library-v124-12272E1AC0C1F8E2.swf'):
        path = ROOT / '.work/research' / name
        if path.is_file() and dbpf_build.digest(path.read_bytes()) == maru_companion.CANONICAL_GRID_LIBRARY_SHA256:
            return path.read_bytes()
    raise unittest.SkipTest('The authenticated native ClassLibraryGamedata resource is required')


class GridSourcePinTests(unittest.TestCase):
    def test_adapter_and_exact_donor_identity_are_pinned(self):
        self.assertIn('tools/CasGridBytecodePatch.java', cas_ui_build.source_pins())
        self.assertEqual(maru_companion.expected_resources()[dbpf_build.tgi(maru_companion.GRID_LIBRARY)],
                         maru_companion.GRID_LIBRARY_SHA256)
        with self.assertRaises(ValueError):
            maru_companion.verify_grid_adapter(None, b'')
        self.assertNotIn(dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY), maru_companion.expected_resources())
        self.assertNotEqual(maru_companion.CANONICAL_GRID_LIBRARY, cas_ui_build.CLEANUP_KEY)


@unittest.skipUnless(JAR.exists() and JAVA and JAVAC, 'Private FFDec and a JDK are required')
class GridGetterBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='apex-grid-getter-')
        cls.work = Path(cls.temporary.name)
        cls.cp = str(JAR) + os.pathsep + str(cls.work)
        result = subprocess.run([JAVAC, '-cp', str(JAR), '-d', str(cls.work),
                                 str(ROOT / 'tools/CasGridBytecodePatch.java'),
                                 str(ROOT / 'tests/java/CasGridGetterFixtures.java'),
                                 str(ROOT / 'tests/java/CasGridResetProfileFixtures.java')],
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            cls.temporary.cleanup()
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_serialized_synthetic_positive_and_twenty_nine_refusals(self):
        result = subprocess.run([JAVA, '-cp', self.cp, 'CasGridGetterFixtures'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sum(line.startswith('PASS ') for line in result.stdout.splitlines()), 30)

    def test_profile_executes_native_effects_and_reports_phase_totals_without_changing_throws(self):
        result = subprocess.run([JAVA, '-cp', self.cp, 'CasGridResetProfileFixtures'],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sum(line.startswith('PASS ') for line in result.stdout.splitlines()), 8)

    def patched_grid(self, canonical=False):
        raw = original_canonical_grid() if canonical else original_grid()
        expected_contract = maru_companion.CANONICAL_GRID_LIBRARY_CONTRACT if canonical else maru_companion.GRID_LIBRARY_CONTRACT
        prefix = 'canonical' if canonical else 'donor'
        source, output = self.work / (prefix + '.swf'), self.work / (prefix + '.abc')
        source.write_bytes(raw)
        result = subprocess.run([JAVA, '-cp', self.cp, 'CasGridBytecodePatch', str(source), str(output)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        contract = json.loads(result.stdout)
        self.assertEqual(contract, expected_contract)
        tag = next(t[3] for t in cas_ui_build.tags(cas_ui_build.unpack(raw)[1]) if t[0] == 82)
        boundary = tag.index(b'\0', 4) + 1
        data = cas_ui_build.replace_payload(raw, tag[:boundary] + output.read_bytes())
        evidence = dict(base_resource_sha256=dbpf_build.digest(raw),
                        patched_resource_sha256=dbpf_build.digest(data), native_bytecode_contract=contract)
        return raw, data, evidence

    def test_authenticated_donor_retains_all_8479_methods_and_non_script_tags(self):
        original, data, evidence = self.patched_grid()
        self.assertTrue(maru_companion.verify_grid_adapter(evidence, data))
        self.assertEqual(len(data) - len(original), 604)
        self.assertEqual([(t[0], t[3]) for t in cas_ui_build.tags(cas_ui_build.unpack(original)[1]) if t[0] != 82],
                         [(t[0], t[3]) for t in cas_ui_build.tags(cas_ui_build.unpack(data)[1]) if t[0] != 82])
        for key, value in [('base_resource_sha256', '0' * 64), ('patched_resource_sha256', '0' * 64)]:
            changed = copy.deepcopy(evidence)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                maru_companion.verify_grid_adapter(changed, data)
        for value in (False, 1):
            changed = copy.deepcopy(evidence)
            changed['native_bytecode_contract']['getter_read_only_verified'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                maru_companion.verify_grid_adapter(changed, data)
        with self.assertRaises(ValueError):
            maru_companion.verify_grid_adapter(evidence, data + b'changed')

    def test_canonical_provider_retains_all_9194_methods_and_non_script_tags(self):
        original, data, evidence = self.patched_grid(canonical=True)
        self.assertTrue(maru_companion.verify_canonical_grid_adapter(evidence, data))
        self.assertEqual(len(data) - len(original), 604)
        self.assertEqual([(t[0], t[3]) for t in cas_ui_build.tags(cas_ui_build.unpack(original)[1]) if t[0] != 82],
                         [(t[0], t[3]) for t in cas_ui_build.tags(cas_ui_build.unpack(data)[1]) if t[0] != 82])
        for field, value in [('base_resource_sha256', '0' * 64), ('patched_resource_sha256', '0' * 64)]:
            changed = copy.deepcopy(evidence);changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                maru_companion.verify_canonical_grid_adapter(changed, data)
        for field, value in [('native_method_count', 9193), ('provider_identity_verified', 1),
                             ('provider_resource_tgi', dbpf_build.tgi(cas_ui_build.CLEANUP_KEY)),
                             ('appended_reset_profile_methods', 0), ('reset_profile_native_flow_verified', 1),
                             ('reset_profile_report_verified', False), ('reset_profile_scope_verified', False)]:
            changed = copy.deepcopy(evidence);changed['native_bytecode_contract'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                maru_companion.verify_canonical_grid_adapter(changed, data)
        with self.assertRaises(ValueError):
            maru_companion.verify_canonical_grid_adapter(evidence, data + b'changed')

    def test_uninspected_olympus_provider_is_not_an_admissible_input(self):
        path = ROOT / '.work/research/OlympusLibrary.swf'
        if not path.exists():
            self.skipTest('Private Olympus reference required')
        result = subprocess.run([JAVA, '-cp', self.cp, 'CasGridBytecodePatch', str(path), str(self.work / 'forbidden.abc')],
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('differs from the two reviewed native resources', result.stderr)

    def test_donor_combine_accepts_only_the_authenticated_library_overlap(self):
        original, data, adapter = self.patched_grid()
        donor = {maru_companion.CUSTOMIZER: b'private-customizer', maru_companion.GRID_LIBRARY: original,
                 (0x62ECC59A, 0, 123): b'retained dependency'}
        evidence = dict(resource_sha256={dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in donor.items()},
                        grid_library_adapter=adapter)
        apex = {maru_companion.CUSTOMIZER: b'reviewed customizer adapter', maru_companion.GRID_LIBRARY: data}
        with patch.object(maru_companion, 'read_package', return_value=donor):
            result = maru_companion.combine('fixture', apex, evidence)
        self.assertEqual(result[maru_companion.GRID_LIBRARY], data)
        self.assertEqual(result[(0x62ECC59A, 0, 123)], b'retained dependency')
        for change in ('missing-evidence', 'missing-library', 'changed-library', 'extra-overlap'):
            changed_apex, changed_evidence = dict(apex), copy.deepcopy(evidence)
            if change == 'missing-evidence':
                del changed_evidence['grid_library_adapter']
            elif change == 'missing-library':
                del changed_apex[maru_companion.GRID_LIBRARY]
            elif change == 'changed-library':
                changed_apex[maru_companion.GRID_LIBRARY] = data + b'changed'
            else:
                changed_apex[(0x62ECC59A, 0, 123)] = b'unreviewed override'
            with self.subTest(change=change), patch.object(maru_companion, 'read_package', return_value=donor), self.assertRaises(ValueError):
                maru_companion.combine('fixture', changed_apex, changed_evidence)

    def test_bundle_gate_keeps_original_dependencies_and_refuses_unproved_adaptation(self):
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        manifest = Path(str(package) + '.manifest.json')
        if not package.exists() or not manifest.exists():
            self.skipTest('A private compiled donor merge is required')
        original, data, adapter = self.patched_grid()
        resources = dbpf_build.read(package.read_bytes())
        info = json.loads(manifest.read_text(encoding='utf-8'))
        if info.get('companion_code_merge') is None:
            self.skipTest('The bundle must use the exact donor code merge')
        # This case exercises the historical getter/profile envelope, not a
        # current transaction/index/domain manifest with its later requirements.
        historical_provider_fixture(info, resources, keep_dependency=False)
        for source in maru_companion.GRID_TRANSACTION_SOURCES + maru_companion.GRID_COMMUNICATION_SOURCES:
            info['source_pins'].pop(source, None)
        resources[maru_companion.GRID_LIBRARY] = data
        info['companion_code_merge']['grid_library_adapter'] = adapter
        original_canonical, canonical, canonical_adapter = self.patched_grid(canonical=True)
        resources[maru_companion.CANONICAL_GRID_LIBRARY] = canonical
        info['grid_provider_adapters'] = {dbpf_build.tgi(maru_companion.GRID_LIBRARY): adapter,
                                         dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY): canonical_adapter}
        for key, provider in info['grid_provider_adapters'].items():
            info.setdefault('base_resources', {})[key] = provider['base_resource_sha256']
            info.setdefault('patched_resources', {})[key] = provider['patched_resource_sha256']
        self.assertTrue(maru_companion.verify_merged(info, resources))
        for change in ('missing-provider-evidence', 'missing-canonical', 'original-canonical', 'changed-canonical',
                       'unmodified-claim', 'unexpected-olympus-override', 'wrong-resource-manifest'):
            changed_info, changed_resources = copy.deepcopy(info), dict(resources)
            if change == 'missing-provider-evidence':
                del changed_info['grid_provider_adapters']
            elif change == 'missing-canonical':
                del changed_resources[maru_companion.CANONICAL_GRID_LIBRARY]
            elif change == 'original-canonical':
                changed_resources[maru_companion.CANONICAL_GRID_LIBRARY] = original_canonical
            elif change == 'changed-canonical':
                changed_resources[maru_companion.CANONICAL_GRID_LIBRARY] += b'changed'
            elif change == 'unmodified-claim':
                changed_info.setdefault('unmodified_dependency_resources', {})[dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)] = maru_companion.CANONICAL_GRID_LIBRARY_SHA256
            elif change == 'unexpected-olympus-override':
                changed_resources[cas_ui_build.CLEANUP_KEY] = b'unreviewed override'
            else:
                changed_info['patched_resources'][dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)] = '0' * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                maru_companion.verify_merged(changed_info, changed_resources)
        omitted = copy.deepcopy(info)
        del omitted['companion_code_merge']['grid_library_adapter']
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(omitted, resources)
        omitted.setdefault('source_pins', {})['tools/CasGridBytecodePatch.java'] = 'current-source-pin'
        restored = dict(resources)
        restored[maru_companion.GRID_LIBRARY] = original
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(omitted, restored)
        corrupted = dict(resources)
        corrupted[maru_companion.GRID_LIBRARY] += b'changed'
        with self.assertRaises(ValueError):
            maru_companion.verify_merged(info, corrupted)

    def test_dual_provider_combine_requires_exact_canonical_evidence(self):
        original, donor_data, donor_adapter = self.patched_grid()
        _, canonical_data, canonical_adapter = self.patched_grid(canonical=True)
        donor = {maru_companion.CUSTOMIZER: b'private-customizer', maru_companion.GRID_LIBRARY: original,
                 (0x62ECC59A, 0, 123): b'retained dependency'}
        evidence = dict(resource_sha256={dbpf_build.tgi(k): dbpf_build.digest(v) for k, v in donor.items()},
                        grid_library_adapter=donor_adapter)
        apex = {maru_companion.CUSTOMIZER: b'reviewed customizer adapter',
                maru_companion.GRID_LIBRARY: donor_data, maru_companion.CANONICAL_GRID_LIBRARY: canonical_data}
        providers = {dbpf_build.tgi(maru_companion.GRID_LIBRARY): donor_adapter,
                     dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY): canonical_adapter}
        with patch.object(maru_companion, 'read_package', return_value=donor):
            combined = maru_companion.combine('fixture', apex, evidence, providers)
        self.assertEqual(combined[maru_companion.CANONICAL_GRID_LIBRARY], canonical_data)
        self.assertEqual(combined[(0x62ECC59A, 0, 123)], b'retained dependency')
        for change in ('omitted', 'missing-provider', 'extra-provider', 'wrong-identity', 'changed-resource', 'olympus-override'):
            changed_providers, changed_apex = copy.deepcopy(providers), dict(apex)
            if change == 'omitted':
                changed_providers = None
            elif change == 'missing-provider':
                del changed_providers[dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)]
            elif change == 'extra-provider':
                changed_providers[dbpf_build.tgi(cas_ui_build.CLEANUP_KEY)] = canonical_adapter
            elif change == 'wrong-identity':
                changed_providers[dbpf_build.tgi(maru_companion.CANONICAL_GRID_LIBRARY)]['native_bytecode_contract']['provider_resource_tgi'] = dbpf_build.tgi(cas_ui_build.CLEANUP_KEY)
            elif change == 'changed-resource':
                changed_apex[maru_companion.CANONICAL_GRID_LIBRARY] += b'changed'
            else:
                changed_apex[cas_ui_build.CLEANUP_KEY] = b'unreviewed Olympus override'
            with self.subTest(change=change), patch.object(maru_companion, 'read_package', return_value=donor), self.assertRaises(ValueError):
                maru_companion.combine('fixture', changed_apex, evidence, changed_providers)


if __name__ == '__main__':
    unittest.main()
