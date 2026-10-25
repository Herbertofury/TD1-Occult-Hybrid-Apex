"""Authenticate the actual native Main initializer bootstrap seam and CFG.

The adversarial variants extend a native-anchored fixture; no game input or
profile/process access. The compiled full controller is gated by the builder.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JAR=ROOT/'.work/research/ffdec/ffdec.jar'
NATIVE=ROOT/'.work/research/maru-integrated/DynamicCASCustomizer.swf'

@unittest.skipUnless(JAR.exists() and NATIVE.exists() and shutil.which('javac'),
                     'Private native initializer and FFDec required')
class GridBootstrapBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-grid-bootstrap-')
        cls.addClassCleanup(cls.temp.cleanup)
        subprocess.run(['javac','-cp',str(JAR),'-d',cls.temp.name,
            str(ROOT/'tools/CasBytecodePatch.java'),
            str(ROOT/'tests/CasGridBootstrapBytecodeFixtures.java')],
            check=True,capture_output=True,text=True,timeout=60)

    def run_case(self,mode):
        result=subprocess.run(['java','-cp',str(JAR)+os.pathsep+self.temp.name,
            'CasGridBootstrapBytecodeFixtures',str(NATIVE),mode],
            capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout[-1000:]+result.stderr[-2000:])
        self.assertIn('PASS '+mode,result.stdout)

    def test_actual_initializer_serialized_projection_whole_abc_rollback_and_hook_abi(self):
        self.run_case('valid')

    def test_native_seam_shape_order_and_dominance_fail_closed(self):
        for mode in ('missing','duplicate','receiver','wrong-order','bypass'):
            with self.subTest(mode=mode):self.run_case(mode)

    def test_conditional_jump_switch_and_exception_relocation(self):
        for mode in ('synthetic-valid','synthetic-stale-if','synthetic-stale-jump',
                     'synthetic-stale-switch','synthetic-exception'):
            with self.subTest(mode=mode):self.run_case(mode)

    def test_original_instructions_receiver_arguments_and_locals_are_immutable(self):
        for mode in ('wrong-this','wrong-args','retained','locals'):
            with self.subTest(mode=mode):self.run_case(mode)

if __name__=='__main__':unittest.main()
