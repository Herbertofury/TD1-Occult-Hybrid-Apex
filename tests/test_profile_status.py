from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_profile import activate, status


class LaunchPreflightTests(unittest.TestCase):
    def test_only_exact_test_artifacts_allow_launch_and_unknown_mods_block_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / 'The Sims 4'
            (profile / 'Mods').mkdir(parents=True)
            (profile / 'saves').mkdir()
            (profile / 'saves' / 'precious.save').write_bytes(b'original')
            artifact = root / 'Apex.package'
            artifact.write_bytes(b'DBPF fixture')
            state = root / 'session.json'
            activate(profile, state, [artifact], guard=lambda: None)
            result = status(state, verify_original=True)
            self.assertTrue(result['ready_to_launch'])
            self.assertTrue(result['original_inventory_verified_now'])
            self.assertEqual(result['test_save_files'], 0)
            (profile / 'Mods' / 'unexpected.package').write_bytes(b'DBPF unexpected')
            result = status(state)
            self.assertFalse(result['ready_to_launch'])
            self.assertEqual(result['unexpected_mod_files'], ['unexpected.package'])

    def test_changed_or_missing_test_artifact_blocks_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / 'The Sims 4'
            profile.mkdir()
            artifact = root / 'Apex.package'
            artifact.write_bytes(b'DBPF fixture')
            state = root / 'session.json'
            activate(profile, state, [artifact], guard=lambda: None)
            installed = profile / 'Mods' / 'ApexTest' / artifact.name
            installed.write_bytes(b'DBPF changed')
            self.assertFalse(status(state)['ready_to_launch'])
            installed.unlink()
            self.assertFalse(status(state)['ready_to_launch'])


if __name__ == '__main__':
    unittest.main()
