from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from source_manifest import manifest


class SourceIdentityTests(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.check_output(['git'] + list(args), cwd=str(root), stderr=subprocess.DEVNULL)

    def setup_repo(self, root):
        self.git(root, 'init')
        self.git(root, 'config', 'user.email', 'fixture@example.invalid')
        self.git(root, 'config', 'user.name', 'Fixture')
        self.git(root, 'config', 'core.autocrlf', 'true')
        (root / '.gitattributes').write_bytes(b'*.txt text\n*.bin -text\n')
        (root / 'source.txt').write_bytes(b'first\r\nsecond\r\n')
        (root / 'exact.bin').write_bytes(b'exact\r\n\x00binary')
        self.git(root, 'add', '.')

    def test_manifest_survives_fresh_checkout_with_different_line_endings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'source'
            root.mkdir()
            self.setup_repo(root)
            before = manifest(root, root / 'manifests' / 'source.json')
            self.git(root, 'commit', '-m', 'fixture')
            clone = Path(temp) / 'clone'
            self.git(root, '-c', 'core.autocrlf=false', 'clone', '--no-local', str(root), str(clone))
            self.git(clone, 'config', 'core.autocrlf', 'false')
            self.git(clone, 'config', 'core.eol', 'lf')
            (clone / 'source.txt').unlink()
            self.git(clone, 'checkout', '--', 'source.txt')
            self.assertEqual((clone / 'source.txt').read_bytes(), b'first\nsecond\n')
            self.assertEqual(before, manifest(clone, clone / 'manifests' / 'source.json'))
            self.assertEqual((clone / 'exact.bin').read_bytes(), (root / 'exact.bin').read_bytes())

    def test_unstaged_edits_and_missing_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.setup_repo(root)
            (root / 'source.txt').write_bytes(b'new content\n')
            with self.assertRaisesRegex(ValueError, 'Stage this source change'):
                manifest(root, root / 'source.json')
            self.git(root, 'add', 'source.txt')
            manifest(root, root / 'source.json')
            (root / 'exact.bin').unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                manifest(root, root / 'source.json')


if __name__ == '__main__':
    unittest.main()
