"""Compiled formal-index authority and bounded, throwing-only native refusal."""
from pathlib import Path
import os,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'

@unittest.skipUnless(JAR.is_file() and COMPILED.is_file() and shutil.which('javac'),'Compiled native-anchored CAS fixture and FFDec/JDK required')
class CompilerArgumentProvenanceTests(unittest.TestCase):
    def test_actual_parameter_capture_and_refusal_branch_with_adversarial_compiled_operands(self):
        with tempfile.TemporaryDirectory(prefix='apex-argument-proof-') as output:
            compiled=subprocess.run(['javac','-cp',str(JAR),'-d',output,str(ROOT/'tools/CasBytecodePatch.java'),str(ROOT/'tests/CasCompilerArgumentProvenanceFixtures.java')],capture_output=True,text=True,timeout=60)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            result=subprocess.run(['java','-cp',str(JAR)+os.pathsep+output,'CasCompilerArgumentProvenanceFixtures',str(COMPILED)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(len(result.stdout.splitlines()),20)
            self.assertIn('PASS bypass-capture',result.stdout)
            self.assertIn('PASS actual-typed-control-inventory',result.stdout)
            self.assertIn('PASS nonthrowing-refusal',result.stdout)

if __name__=='__main__':unittest.main()
