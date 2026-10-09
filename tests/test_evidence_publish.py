from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import source_manifest


class EvidencePublicationTests(unittest.TestCase):
    def error(self, code):
        error = PermissionError('destination temporarily held')
        error.winerror = code
        return error

    def test_transient_windows_reader_lock_retries_same_flushed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proof.json'
            path.write_text('old evidence')
            real_replace = source_manifest.os.replace
            with patch.object(source_manifest.os, 'replace', side_effect=[self.error(32), self.error(5), None]) as replace, patch.object(source_manifest.time, 'sleep') as sleep:
                def publish(src, dst):
                    if replace.call_count < 3: raise self.error(32)
                    real_replace(src, dst)
                replace.side_effect = publish
                source_manifest.write_json(path, {'ok': True})
                self.assertEqual(len(set(call.args[0] for call in replace.call_args_list)), 1)
                self.assertEqual(sleep.call_count, 2)
                self.assertIn('true', path.read_text())
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_permanent_lock_is_bounded_and_preserves_prior_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proof.json'; path.write_text('prior')
            with patch.object(source_manifest.os, 'replace', side_effect=self.error(5)) as replace, patch.object(source_manifest.time, 'sleep'):
                with self.assertRaises(PermissionError): source_manifest.write_json(path, {'new': True})
                self.assertEqual(replace.call_count, 11)
            self.assertEqual(path.read_text(), 'prior')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_other_permissions_do_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(source_manifest.os, 'replace', side_effect=self.error(87)) as replace, patch.object(source_manifest.time, 'sleep') as sleep:
                with self.assertRaises(PermissionError): source_manifest.write_json(Path(directory) / 'proof.json', {})
                replace.assert_called_once(); sleep.assert_not_called()
