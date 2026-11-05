import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

_source_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'tools', 'source_manifest.py')
source_manifest = types.ModuleType('_apex_manifest_publication_under_test')
source_manifest.__file__ = _source_path
with open(_source_path, 'rb') as _source:
    exec(compile(_source.read(), _source_path, 'exec'), source_manifest.__dict__)


def failure(winerror):
    error = PermissionError('injected publication failure')
    error.winerror = winerror
    return error


class PublicationTests(unittest.TestCase):
    def test_access_denied_is_not_retried_or_published(self):
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parent)) as root:
            dest = Path(root) / 'manifest.json'
            dest.write_bytes(b'last-good')
            with patch.object(source_manifest.os, 'replace', side_effect=failure(5)) as replace, \
                 patch.object(source_manifest.time, 'sleep') as sleep:
                with self.assertRaises(PermissionError):
                    source_manifest.write_json(dest, {'new': True})
            self.assertEqual(replace.call_count, 1)
            sleep.assert_not_called()
            self.assertEqual(dest.read_bytes(), b'last-good')
            self.assertEqual([p.name for p in Path(root).iterdir()], ['manifest.json'])

    def test_sharing_violation_retries_existing_flushed_payload(self):
        for code in (32, 33):
            with self.subTest(winerror=code), tempfile.TemporaryDirectory(dir=str(Path(__file__).parent)) as root:
                dest = Path(root) / 'manifest.json'
                real_replace = source_manifest.os.replace
                calls = []
                def replace(src, target):
                    calls.append((src, target))
                    if len(calls) == 1:
                        raise failure(code)
                    return real_replace(src, target)
                with patch.object(source_manifest.os, 'replace', side_effect=replace), \
                     patch.object(source_manifest.time, 'sleep') as sleep:
                    source_manifest.write_json(dest, {'new': True})
                self.assertEqual(len(calls), 2)
                self.assertEqual(calls[0], calls[1])
                sleep.assert_called_once()
                self.assertEqual(dest.read_bytes(), b'{\n  "new": true\n}\n')

    def test_persistent_sharing_failure_retains_destination_and_cleans_temp(self):
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).parent)) as root:
            dest = Path(root) / 'manifest.json'
            dest.write_bytes(b'last-good')
            with patch.object(source_manifest.os, 'replace', side_effect=failure(33)) as replace, \
                 patch.object(source_manifest.time, 'sleep') as sleep:
                with self.assertRaises(PermissionError):
                    source_manifest.write_json(dest, {'new': True})
            self.assertEqual(replace.call_count, 11)
            self.assertEqual(sleep.call_count, 10)
            self.assertEqual(dest.read_bytes(), b'last-good')
            self.assertEqual([p.name for p in Path(root).iterdir()], ['manifest.json'])


if __name__ == '__main__':
    unittest.main()
