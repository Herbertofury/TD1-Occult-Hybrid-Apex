from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_script import build


class ScriptBuildTests(unittest.TestCase):
    def test_exact_source_only_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'Source'
            (source / 'apex_core').mkdir(parents=True)
            (source / 'td1_occult_hybrid_apex.py').write_bytes(b'x = 1\n')
            (source / 'apex_core' / '__init__.py').write_bytes(b'')
            (source / 'apex_core' / 'domain.py').write_bytes(b'x = 2\n')
            (source / 'private-save.json').write_bytes(b'NEVER SHIP THIS')
            (source / 'old.pyc').write_bytes(b'wrong Python bytecode')
            first, second = root / 'a.ts4script', root / 'b.ts4script'
            self.assertEqual(build(source, first)['sha256'], build(source, second)['sha256'])
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(sorted(archive.namelist()), ['apex_core/__init__.py', 'apex_core/domain.py', 'td1_occult_hybrid_apex.py'])
                self.assertEqual(archive.read('td1_occult_hybrid_apex.py'), b'x = 1\n')

    def test_unsupported_python_syntax_fails_before_output(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'Source'
            source.mkdir()
            (source / 'td1_occult_hybrid_apex.py').write_text('match x:\n    case 1: pass\n')
            with self.assertRaises(SyntaxError):
                build(source, root / 'bad.ts4script')
            self.assertFalse((root / 'bad.ts4script').exists())


if __name__ == '__main__':
    unittest.main()
