"""Execute synthetic Java bytecode safety fixtures when FFDec/JDK are present."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAR = ROOT / '.work/research/ffdec/ffdec.jar'
NATIVE_SELECTOR = ROOT / '.work/research/cas-hair-cassimselector-current.swf'
COMPILED_SELECTOR = ROOT / '.work/research/apex-cas-selector-compiled.swf'
CASES = (
    'entry-preserves-branch', 'tail-preserves-return-branch', 'unknown-native-exception',
    'scope-prologue', 'multiple-return', 'branch-to-prologue', 'native-suffix-tamper',
    'hook-qname-tamper', 'hook-argument-tamper', 'callback-copy-only', 'callback-native-getter',
    'service-native-getter', 'callback-native-class', 'callback-retained-getter',
    'service-native-write', 'service-observation-write', 'initialize-clears-feed',
    'callback-closure', 'callback-direct-call', 'callback-outer-scope', 'local-scope-overflow',
    'arbitrary-constructor', 'registration-exact', 'registration-event', 'registration-callback',
    'registration-arity', 'registration-duplicate',
    'inventory-exact', 'inventory-extra', 'inventory-duplicate', 'inventory-private-namespace',
    'inventory-slot-collision', 'inventory-optional-signature', 'inventory-missing-bound', 'inventory-read-argument',
)
ACTUAL_CASES = ('actual-default-exact', 'actual-default-reverted', 'actual-remembered-guard',
    'actual-default-owner-key', 'actual-remembered-choice-read', 'actual-link-inversion',
    'actual-explicit-link-memory', 'actual-sync-zero', 'actual-sync-service',
    'actual-sync-payload', 'actual-copy-handler', 'actual-copy-exception',
    'actual-copy-trait', 'actual-native-already-patched')


class SelectorBytecodeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not JAR.is_file() or not shutil.which('javac') or not shutil.which('java'):
            raise unittest.SkipTest('Synthetic selector fixtures require the local FFDec library and JDK.')
        cls.temporary = tempfile.TemporaryDirectory(prefix='apex-selector-java-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.classes = Path(cls.temporary.name)
        result = subprocess.run(['javac', '-cp', str(JAR), '-d', str(cls.classes),
            str(ROOT / 'tools/CasBytecodePatch.java'), str(ROOT / 'tools/CasSelectorBytecodePatch.java'),
            str(ROOT / 'tests/java/CasSelectorSafetyFixtures.java')], capture_output=True,
            text=True, encoding='utf-8', timeout=60)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def fixture(self, case):
        actual = case in ACTUAL_CASES
        if actual and (not NATIVE_SELECTOR.is_file() or not COMPILED_SELECTOR.is_file()):
            self.skipTest('Actual selector fixtures require the locally extracted native and compiled resources.')
        result = subprocess.run(['java', '-cp', os.pathsep.join((str(JAR), str(self.classes))),
            'CasSelectorSafetyFixtures', case] + ([str(NATIVE_SELECTOR), str(COMPILED_SELECTOR)] if actual else []),
            capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'PASS ' + case)


for _case in CASES + ACTUAL_CASES:
    setattr(SelectorBytecodeSafetyTests, 'test_' + _case.replace('-', '_'),
            lambda self, case=_case: self.fixture(case))


if __name__ == '__main__':
    unittest.main()
