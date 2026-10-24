"""Reject serialized menu patches that merge render genera or leak tooltips."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
JAR=ROOT/'.work/research/ffdec/ffdec.jar'
COMPILED=ROOT/'.work/research/apex-cas-compiled.swf'
CASES=('exact','grouping','rendering-kind','tooltip-create','tooltip-rebuild','tooltip-unload','tooltip-shutdown',
       'fast-queue-not-deferred','fast-state-not-native','fast-frame-network-poll','fast-frame-missing-lease','fast-clock-namespace','pair-click-not-deferred','pair-panel-not-deferred',
       'pair-read-mutates','pair-native-action-missing','pair-cli-action-missing',
       'molecule-click-drops-intent','molecule-click-inline','molecule-drain-other-session',
       'molecule-drain-active-command','molecule-drain-inline','molecule-not-consumed')
CASES+=('readonly-operation','readonly-phase','readonly-length','readonly-nonce','readonly-sim','readonly-display-sim','readonly-mutated','readonly-receiving')


class LifeStateMenuBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not JAR.is_file() or not COMPILED.is_file() or not shutil.which('javac') or not shutil.which('java'):
            raise unittest.SkipTest('Requires the local compiled CAS resource, FFDec and JDK.')
        cls.temp=tempfile.TemporaryDirectory(prefix='apex-life-state-menu-');cls.addClassCleanup(cls.temp.cleanup)
        r=subprocess.run(['javac','-cp',str(JAR),'-d',cls.temp.name,str(ROOT/'tools/CasBytecodePatch.java'),
            str(ROOT/'tests/java/CasLifeStateMenuFixtures.java')],capture_output=True,text=True,timeout=60)
        if r.returncode:raise AssertionError(r.stdout+r.stderr)

    def fixture(self,case):
        r=subprocess.run(['java','-cp',os.pathsep.join((str(JAR),self.temp.name)),
            'CasLifeStateMenuFixtures',case,str(COMPILED)],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(r.stdout.strip(),'PASS '+case)


for case in CASES:
    setattr(LifeStateMenuBytecodeTests,'test_'+case.replace('-','_'),lambda self,case=case:self.fixture(case))
