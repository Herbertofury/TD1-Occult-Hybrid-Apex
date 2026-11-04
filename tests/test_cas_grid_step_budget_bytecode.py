"""Exact compiled Step argument, clock, store and deadline operands."""
from pathlib import Path
import os,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'

@unittest.skipUnless(JAR.is_file() and COMPILED.is_file() and shutil.which('javac'),'Compiled native-anchored CAS fixture and FFDec/JDK required')
class GridStepBudgetBytecodeTests(unittest.TestCase):
    def test_current_controller_and_both_exact_deadlines_reject_stack_operand_and_cfg_mutations(self):
        with tempfile.TemporaryDirectory(prefix='apex-step-budget-') as output:
            compiled=subprocess.run(['javac','-cp',str(JAR),'-d',output,str(ROOT/'tools/CasBytecodePatch.java'),str(ROOT/'tests/CasGridStepBudgetFixtures.java')],capture_output=True,text=True,timeout=60)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            result=subprocess.run(['java','-cp',str(JAR)+os.pathsep+output,'CasGridStepBudgetFixtures',str(COMPILED)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(len(result.stdout.splitlines()),26)
            self.assertIn('PASS actual-full-controller',result.stdout)
            self.assertIn('PASS historical-plain-suffix',result.stdout)
            self.assertIn('PASS branch-into-deadline',result.stdout)

if __name__=='__main__':unittest.main()
