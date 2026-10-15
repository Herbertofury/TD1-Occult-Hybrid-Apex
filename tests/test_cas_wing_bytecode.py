"""Verify the actual serialized native wing base/color getter contract."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / '.work/research/ffdec/ffdec.jar'
COMPILED = ROOT / '.work/research/apex-cas-compiled.swf'
CASES = (
    'wing-exact-serialized', 'wing-base-getter', 'wing-color-getter',
    'wing-color-bodytype', 'wing-panel-state', 'wing-base-arity', 'wing-base-native-flag',
    'wing-base-detachment', 'wing-filter-detachment', 'wing-color-arity',
    'wing-color-coerced-string', 'wing-base-count', 'wing-base-type',
    'wing-color-type', 'wing-base-intent', 'wing-color-intent',
    'wing-variant-source', 'wing-refusal-bypass', 'wing-refusal-throw',
    'wing-color-ack', 'wing-native-write', 'wing-observation-color-detachment',
    'wing-observation-qualified', 'wing-observation-base-type', 'wing-observation-raw-color',
    'wing-observation-bound', 'wing-observation-panel', 'wing-observation-publication',
    'wing-observation-native-property', 'wing-observation-socket-caller',
)


class WingBytecodeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not JAR.is_file() or not COMPILED.is_file() or not shutil.which('javac') or not shutil.which('java'):
            raise unittest.SkipTest('Wing bytecode fixtures require the local compiled CAS resource, FFDec and JDK.')
        cls.temporary = tempfile.TemporaryDirectory(prefix='apex-wing-java-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.classes = Path(cls.temporary.name)
        result = subprocess.run(['javac', '-cp', str(JAR), '-d', str(cls.classes),
            str(ROOT / 'tools/CasBytecodePatch.java'), str(ROOT / 'tests/java/CasWingSafetyFixtures.java')],
            capture_output=True, text=True, encoding='utf-8', timeout=60)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def fixture(self, case):
        result = subprocess.run(['java', '-cp', os.pathsep.join((str(JAR), str(self.classes))),
            'CasWingSafetyFixtures', case, str(COMPILED)], capture_output=True,
            text=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'PASS ' + case)


for _case in CASES:
    setattr(WingBytecodeSafetyTests, 'test_' + _case.replace('-', '_'),
            lambda self, case=_case: self.fixture(case))


if __name__ == '__main__':
    unittest.main()
