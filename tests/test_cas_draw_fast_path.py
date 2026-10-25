"""Exact post-structural Draw tails and separate historical/final proof chain."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import cas_draw_fast_path as fast


def valid_proof():
    value = dict(ok=True, edited_existing_methods=1, appended_methods=0,
                 appended_traits=0, appended_pool_entries=0, disabled_added_instructions=5,
                 disabled_callback_reads=1, disabled_marker_checks=0, profiled_marker_count=45,
                 runtime_verified=False, performance_gain_claimed=False)
    value.update({key: True for key in fast.PROOFS})
    return value


class ContractTests(unittest.TestCase):
    def test_requires_exact_work_and_retention_contract(self):
        fast.validate_contract(valid_proof())
        for field, original in valid_proof().items():
            with self.subTest(field=field):
                proof = valid_proof()
                proof[field] = not original if isinstance(original, bool) else original + 1
                with self.assertRaises(ValueError):
                    fast.validate_contract(proof)
        for field in ('edited_existing_methods', 'appended_traits', 'disabled_callback_reads'):
            proof = valid_proof()
            proof[field] = bool(proof[field])
            with self.assertRaises(ValueError):
                fast.validate_contract(proof)

    def test_chain_keeps_structural_proof_historical_and_checks_final_bytes(self):
        # A small synthetic DoABC SWF is sufficient for the Python proof layer;
        # the Java tests below use the actual serialized customizer ABC.
        import struct
        def tag(kind, data):
            return struct.pack('<H', (kind << 6) | len(data)) + data
        payload = b'\x00\x00\x00\x00\x00abc'
        body = b'\x08\x00\x00\x0c\x01\x00' + tag(82, payload) + tag(0, b'')
        swf = b'FWS\x09' + struct.pack('<I', len(body) + 8) + body
        import cas_structural_roles as roles
        base = {'proof': 'native', 'native_method_count': 2650, 'unchanged_native_methods': 2616}
        structural = dict(base_contract_sha256=fast.contract_digest(base),
                          abc_sha256='old abc', draw_sha256='old draw',
                          final_swf_sha256='old swf', unchanged_original_native_bodies_after_chain=2615)
        structural.update(ok=True, base_donor_body_count=2650, edited_baseline_methods=2,
                          appended_helpers=1, additional_native_changes_after_base=['dcc.history.CurrentOutfitUI.IsCurrent'],
                          unchanged_baseline_bodies=999, baseline_body_count=1001,
                          additional_changed_original_native_bodies=1, edited_existing_adapter_bodies=1,
                          source_sha256={name: fast.digest((ROOT / name).read_bytes()) for name in
                              ('tools/CasStructuralRolesPatch.java', 'tools/cas_structural_roles.py')},
                          private_source_sha256=roles.PRIVATE_SOURCE_PINS, donor_swf_sha256=roles.DONOR_SHA256)
        for key in ('explicit_jump_switch_exception_fixtures', 'compiled_helper_control_flow_oracle',
                    'compiled_cross_class_receiver_abi', 'serialized_whole_abc_rollback_projection',
                    'main_and_height_preserved', 'unowned_corruption_rejected',
                    'draw_replaces_existing_trace_adapter', 'base_contract_requires_post_adapter_chain'):
            structural[key] = True
        proof = valid_proof()
        proof.update(structural_contract_sha256=fast.contract_digest(structural),
                     baseline_abc_sha256='old abc', baseline_draw_sha256='old draw',
                     baseline_swf_sha256='old swf', abc_sha256=fast.digest(b'abc'),
                     source_sha256={name: fast.digest((ROOT / name).read_bytes()) for name in fast.SOURCES})
        chained = fast.chain_contract(base, structural, proof, swf)
        self.assertEqual(chained['unchanged_original_native_bodies_after_chain'], 2615)
        self.assertEqual(chained['additional_changed_original_native_bodies'], 0)
        self.assertEqual(fast.chain_contract(base, structural, chained, swf), chained)
        for field in ('baseline_abc_sha256', 'baseline_draw_sha256', 'baseline_swf_sha256',
                      'structural_contract_sha256', 'abc_sha256', 'source_sha256'):
            with self.subTest(field=field):
                changed = copy.deepcopy(proof)
                changed[field] = 'changed'
                with self.assertRaises(ValueError):
                    fast.chain_contract(base, structural, changed, swf)


JAR = ROOT / '.work/research/ffdec/ffdec.jar'
INPUT = ROOT / '.work/research/structural-roles/retained.abc'


@unittest.skipUnless(JAR.exists() and INPUT.exists() and shutil.which('javac'),
                     'Private compiled structural-role ABC and JDK required')
class SerializedBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='apex-draw-fast-path-')
        cls.directory = Path(cls.temp.name)
        subprocess.run(['javac', '-cp', str(JAR), '-d', str(cls.directory),
                        str(ROOT / fast.SOURCES[0]),
                        str(ROOT / 'tests/java/CasDrawFastPathFixtures.java')],
                       check=True, capture_output=True, timeout=60)
        cls.classpath = str(JAR) + os.pathsep + str(cls.directory)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_serialized_adversaries_cfg_callbacks_and_native_exceptions(self):
        result = subprocess.run(['java', '-cp', self.classpath, 'CasDrawFastPathFixtures', str(INPUT)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('512 CFG paths each state;1024 identical native throws', result.stdout)

    def test_authenticated_input_and_published_counts(self):
        proof = json.loads((INPUT.parent / 'contract.json').read_text())
        output, report = self.directory / 'retained.abc', self.directory / 'contract.json'
        args = ['java', '-cp', self.classpath, 'CasDrawFastPathPatch', str(INPUT),
                proof['abc_sha256'], proof['draw_sha256'], str(output), str(report)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = json.loads(report.read_text())
        fast.validate_contract(result)
        self.assertEqual(result['abc_sha256'], fast.digest(output.read_bytes()))
        self.assertEqual((result['fast_draw_instructions'], result['output_draw_instructions']), (710, 1783))
        self.assertEqual((result['fast_draw_bytes'], result['output_draw_bytes']), (1578, 3886))
        for index in (5, 6):
            with self.subTest(hash_argument=index):
                bad = args.copy()
                bad[index] = '0' * 64
                bad_output = self.directory / ('bad-' + str(index) + '.abc')
                bad[7] = str(bad_output)
                failed = subprocess.run(bad, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(failed.returncode, 0)
                self.assertFalse(bad_output.exists())

    def test_wrapper_requires_real_structural_proof_and_preserves_final_chain(self):
        import cas_ui_build as ui
        import dbpf_build
        import maru_companion
        package = ROOT / 'dist/candidate/ApexCASBridge.package'
        manifest = package.with_suffix('.package.manifest.json')
        if not package.exists() or not manifest.exists():
            self.skipTest('Current private package proof required')
        info = json.loads(manifest.read_text())
        baseline = dbpf_build.read(package.read_bytes())[maru_companion.CUSTOMIZER]
        structural = info['structural_roles_native_bytecode_contract']
        if info.get('draw_fast_path_native_bytecode_contract') is not None:
            final = baseline
            old_tag = next(t[3] for t in ui.tags(ui.unpack(final)[1]) if t[0] == 82)
            baseline = ui.replace_payload(final, old_tag[:old_tag.index(b'\0', 4) + 1] + INPUT.read_bytes())
            self.assertEqual(fast.digest(baseline), structural['final_swf_sha256'])
            self.assertEqual(fast.chain_contract(info['native_bytecode_contract'], structural,
                info['draw_fast_path_native_bytecode_contract'], final), info['draw_fast_path_native_bytecode_contract'])
        abc, proof = fast.adapt(info['native_bytecode_contract'], structural, baseline,
                                JAR, self.directory / 'wrapper')
        old_tag = next(t[3] for t in ui.tags(ui.unpack(baseline)[1]) if t[0] == 82)
        result = ui.replace_payload(baseline, old_tag[:old_tag.index(b'\0', 4) + 1] + abc)
        chained = fast.chain_contract(info['native_bytecode_contract'], structural, proof, result)
        self.assertEqual(chained['unchanged_original_native_bodies_after_chain'],
                         structural['unchanged_original_native_bodies_after_chain'])
        self.assertEqual(fast.chain_contract(info['native_bytecode_contract'], structural, chained, result), chained)
        with self.assertRaises(ValueError):
            fast.chain_contract(info['native_bytecode_contract'], structural, proof, baseline)
        for field in ('abc_sha256', 'source_sha256', 'private_source_sha256', 'base_contract_sha256'):
            changed = copy.deepcopy(structural)
            changed[field] = 'changed'
            with self.subTest(structural_field=field), self.assertRaises(ValueError):
                fast.adapt(info['native_bytecode_contract'], changed, baseline, JAR,
                           self.directory / ('refused-' + field))


if __name__ == '__main__':
    unittest.main()
