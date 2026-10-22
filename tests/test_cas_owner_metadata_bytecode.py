from pathlib import Path
import os,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'
CASES=('exact','frame-lease','lease-branch','nonce','send','stage','wire','deadline','palette-source','palette-slot',
       'bootstrap-state','bootstrap-guard','bound-owner-refresh',
       'pair-refresh-read','pair-refresh-generation','pair-refresh-identity','pair-refresh-protocol','pair-refresh-enabled','pair-refresh-signature',
       'frame-call','frame-gate','frame-write','frame-ready','frame-cleanup','frame-deadline','frame-cli-event','frame-cli-yield',
       'frame-native-ready','frame-target-ready','notify-call','notify-lifetime','notify-write','notify-listener','notify-restart','notify-bound-return')

class OwnerMetadataBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not JAR.is_file() or not COMPILED.is_file() or not shutil.which('javac') or not shutil.which('java'):
            raise unittest.SkipTest('Requires the local compiled CAS resource, FFDec and JDK.')
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-owner-poll-');cls.addClassCleanup(cls.temp.cleanup)
        r=subprocess.run(['javac','-cp',str(JAR),'-d',cls.temp.name,str(ROOT/'tools/CasBytecodePatch.java'),
                          str(ROOT/'tests/java/CasOwnerMetadataFixtures.java')],capture_output=True,text=True,timeout=60)
        if r.returncode:raise AssertionError(r.stdout+r.stderr)
    def fixture(self,case):
        r=subprocess.run(['java','-cp',os.pathsep.join((str(JAR),self.temp.name)),
                          'CasOwnerMetadataFixtures',case,str(COMPILED)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(r.stdout.strip(),'PASS '+case)

for case in CASES:
    setattr(OwnerMetadataBytecodeTests,'test_'+case.replace('-','_'),lambda self,case=case:self.fixture(case))
