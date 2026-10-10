"""Actual serialized CAS safety fixtures when the local build/JDK are present."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / '.work/research/ffdec/ffdec.jar'
COMPILED = ROOT / '.work/research/apex-cas-compiled.swf'
CASES = ('actual-constructor-timer-path', 'native-snapshot-detached', 'native-snapshot-borrowed', 'connect-native-getter', 'connect-native-helper',
    'connect-transport-send', 'connect-event-owner', 'constructor-connect-event',
    'constructor-connect-callback', 'handshake-native-getter', 'handshake-consume-once',
    'handshake-exact-sim-payload', 'selector-service-contract', 'selector-helper-native-write',
    'selection-current-index', 'selection-write-order', 'selection-typed-boolean',
    'selection-next-tick-readback', 'earrings-wrong-bodytype', 'ambiguous-swatch-count')


class FormSelectBytecodeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not JAR.is_file() or not COMPILED.is_file() or not shutil.which('javac') or not shutil.which('java'):
            raise unittest.SkipTest('Actual CAS bytecode fixtures require the local compiled resource, FFDec and JDK.')
        cls.temporary = tempfile.TemporaryDirectory(prefix='apex-form-select-java-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.classes = Path(cls.temporary.name)
        result = subprocess.run(['javac', '-cp', str(JAR), '-d', str(cls.classes),
            str(ROOT / 'tools/CasBytecodePatch.java'), str(ROOT / 'tests/java/CasFormSelectionSafetyFixtures.java')],
            capture_output=True, text=True, encoding='utf-8', timeout=60)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def fixture(self, case):
        result = subprocess.run(['java', '-cp', os.pathsep.join((str(JAR), str(self.classes))),
            'CasFormSelectionSafetyFixtures', case, str(COMPILED)], capture_output=True,
            text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-2000:])
        self.assertEqual(result.stdout.strip(), 'PASS ' + case)


for _case in CASES:
    setattr(FormSelectBytecodeSafetyTests, 'test_' + _case.replace('-', '_'),
            lambda self, case=_case: self.fixture(case))


if __name__ == '__main__':
    unittest.main()
