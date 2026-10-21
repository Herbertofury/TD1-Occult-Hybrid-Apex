"""Exercise the real compiled catalog gate when the private build exists."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'
CARDS_COMPILED=ROOT/'.work/research/apex-cas-cards-compiled.swf'
ORIGINAL=ROOT/'.work/research/current-cas-customizer.swf'


@unittest.skipUnless(JAR.exists() and COMPILED.exists() and shutil.which('javac'),'Local FFDec/JDK CAS build required')
class CatalogBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(prefix='apex-catalog-bytecode-')
        cls.addClassCleanup(cls.directory.cleanup)
        subprocess.run(['javac','-cp',str(JAR),'-d',cls.directory.name,
            str(ROOT/'tools/CasBytecodePatch.java'),str(ROOT/'tests/CasCatalogBytecodeFixtures.java'),
            str(ROOT/'tests/CasCardBytecodeFixtures.java')],
            check=True,capture_output=True,timeout=60)

    def test_compiled_input_and_inventory_contract(self):
        for case in ('valid','extra-argument','missing-outfit-prefix','transport-wait','style-regrids','missing-native-margin','missing-cache-reset','missing-closed-outline'):
            with self.subTest(case=case):
                result=subprocess.run(['java','-cp',str(JAR)+os.pathsep+self.directory.name,
                    'CasCatalogBytecodeFixtures',str(COMPILED),case],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-1500:])
                self.assertIn('PASS '+case,result.stdout)

    @unittest.skipUnless(CARDS_COMPILED.exists() and ORIGINAL.exists(),'Compiled native card adapter required')
    def test_only_owned_marker_enables_scaled_height(self):
        for case in ('valid','missing-marker','unscaled-height'):
            with self.subTest(case=case):
                result=subprocess.run(['java','-cp',str(JAR)+os.pathsep+self.directory.name,
                    'CasCardBytecodeFixtures',str(ORIGINAL),str(CARDS_COMPILED),case],
                    capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout[-500:]+result.stderr[-1500:])
                self.assertIn('PASS '+case,result.stdout)


if __name__=='__main__':unittest.main()
