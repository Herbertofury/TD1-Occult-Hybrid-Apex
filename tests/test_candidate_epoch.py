from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_candidate


class CandidateEpochTests(unittest.TestCase):
    def test_prior_epoch_is_refused_before_any_build_or_artifact_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); output = root/'dist'/'candidate'; output.mkdir(parents=True)
            prior = output/build_candidate.candidate_filename(None)
            prior.write_bytes(b'immutable prior bundle')
            with patch.object(build_candidate, 'ROOT', root), patch.object(build_candidate, 'build_packages') as build:
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    build_candidate.build(output)
            build.assert_not_called(); self.assertEqual(prior.read_bytes(), b'immutable prior bundle')

    def test_epoch_cannot_traverse_or_inject_a_new_path(self):
        for value in ('../escape', 'new/name', 'NEW', 'x', 'a'*81, 'new:epoch', None):
            if value is None:
                self.assertEqual(build_candidate.candidate_filename(value), 'Apex_Development_Candidate_2026-10-07.zip')
            else:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    build_candidate.candidate_filename(value)
        self.assertEqual(build_candidate.candidate_filename('2026-10-08-all-owner-cas-v1'),
            'Apex_Development_Candidate_2026-10-08-all-owner-cas-v1.zip')


if __name__ == '__main__':
    unittest.main()
