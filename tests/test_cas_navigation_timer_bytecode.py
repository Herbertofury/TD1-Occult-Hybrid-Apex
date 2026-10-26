"""Mutate the actual cached compiler SWF; strict gates must reject each edit."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'
CASES=('valid','timer-service','timer-scope','timer-disabled','timer-branch','timer-event',
       'timer-status-service','timer-callback','nav-scope','nav-service','nav-identity',
       'nav-fallback','accept-foreign-wire')

@unittest.skipUnless(JAR.is_file() and COMPILED.is_file() and shutil.which('javac') and shutil.which('java'),
                     'Actual cached CAS compiler resource, FFDec and JDK required')
class NavigationTimerBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-navigation-timer-java-')
        cls.addClassCleanup(cls.temp.cleanup)
        run=subprocess.run(['javac','-cp',str(JAR),'-d',cls.temp.name,
            str(ROOT/'tools/CasBytecodePatch.java'),str(ROOT/'tests/CasNavigationTimerBytecodeFixtures.java')],
            capture_output=True,text=True,encoding='utf-8',timeout=60)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)

    def fixture(self,case):
        run=subprocess.run(['java','-cp',os.pathsep.join((str(JAR),self.temp.name)),
            'CasNavigationTimerBytecodeFixtures',str(COMPILED),case],capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr[-2500:])
        self.assertEqual(run.stdout.strip(),'PASS '+case)

for case in CASES:
    setattr(NavigationTimerBytecodeTests,'test_'+case.replace('-','_'),lambda self,case=case:self.fixture(case))

if __name__=='__main__':unittest.main()
