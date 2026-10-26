import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import test_profile


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.profile = self.root / 'The Sims 4'
        (self.profile / 'saves').mkdir(parents=True)
        (self.profile / 'Mods').mkdir()
        (self.profile / 'saves' / 'Slot_00000001.save').write_bytes(b'valuable original save')
        (self.profile / 'Mods' / 'original.package').write_bytes(b'DBPF original CC')
        self.artifact = self.root / 'test.package'
        self.artifact.write_bytes(b'DBPF test artifact')
        self.state = self.root / 'session.json'
        self.baseline = test_profile.inventory(self.profile)
        self.guard = lambda: None

    def activate(self):
        return test_profile.activate(self.profile, self.state, [self.artifact], self.guard)

    def test_round_trip_preserves_original_and_retains_test_saves(self):
        self.activate()
        self.assertEqual(list((self.profile / 'saves').iterdir()), [])
        self.assertFalse((self.profile / 'Mods' / 'original.package').exists())
        (self.profile / 'saves' / 'test.save').write_bytes(b'disposable test')
        result = test_profile.restore(self.state, self.guard)
        self.assertEqual(test_profile.inventory(self.profile), self.baseline)
        self.assertEqual((Path(result['test_archive']) / 'saves' / 'test.save').read_bytes(), b'disposable test')
        self.assertEqual(test_profile.restore(self.state, self.guard)['phase'], 'restored')

    def test_running_game_guard_prevents_any_mutation(self):
        def running():
            raise RuntimeError('running')
        with self.assertRaises(RuntimeError):
            test_profile.activate(self.profile, self.state, [self.artifact], running)
        self.assertFalse(self.state.exists())
        self.assertEqual(test_profile.inventory(self.profile), self.baseline)

    def test_unknown_active_profile_is_never_overwritten(self):
        self.activate()
        (self.profile / test_profile.MARKER).unlink()
        with self.assertRaises(RuntimeError):
            test_profile.restore(self.state, self.guard)
        self.assertTrue(self.profile.exists())
        self.assertTrue(Path(json.loads(self.state.read_text())['original']).exists())

    def test_changed_original_save_refuses_restore(self):
        self.activate()
        original = Path(json.loads(self.state.read_text())['original'])
        (original / 'saves' / 'Slot_00000001.save').write_bytes(b'changed!')
        with self.assertRaises(RuntimeError):
            test_profile.restore(self.state, self.guard)
        self.assertTrue((self.profile / test_profile.MARKER).exists())

    def test_crash_after_original_rename_can_restore(self):
        rename = test_profile.os.rename
        calls = []
        def fail_second(source, destination):
            calls.append(source)
            if len(calls) == 2:
                raise OSError('simulated power loss')
            return rename(source, destination)
        with patch.object(test_profile.os, 'rename', side_effect=fail_second):
            with self.assertRaises(OSError):
                self.activate()
        self.assertFalse(self.profile.exists())
        test_profile.restore(self.state, self.guard)
        self.assertEqual(test_profile.inventory(self.profile), self.baseline)

    def test_tampered_journal_path_refuses_restore(self):
        self.activate()
        data = json.loads(self.state.read_text())
        data['original'] = str(self.root.parent / 'somewhere-else')
        self.state.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            test_profile.restore(self.state, self.guard)

    def test_existing_session_lock_prevents_parallel_activation(self):
        (self.root / test_profile.LOCK).write_text('{}')
        with self.assertRaises(FileExistsError):
            self.activate()
        self.assertEqual(test_profile.inventory(self.profile), self.baseline)
        self.assertFalse(self.state.exists())

    def test_crash_before_swap_during_staging_restores_without_deleting_either_profile(self):
        with patch.object(test_profile.shutil, 'copy2', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.activate()
        self.assertTrue((self.root / test_profile.LOCK).exists())
        result = test_profile.restore(self.state, self.guard)
        self.assertEqual(test_profile.inventory(self.profile), self.baseline)
        self.assertFalse((self.root / test_profile.LOCK).exists())
        self.assertEqual(result['phase'], 'restored')

    def test_retained_disposable_save_can_seed_next_session_without_original_mods(self):
        self.activate()
        (self.profile / 'saves' / 'test.save').write_bytes(b'owner-created test household')
        result = test_profile.restore(self.state, self.guard)
        next_state = self.root / 'next.json'
        test_profile.activate(self.profile, next_state, [self.artifact], guard=self.guard, seed_state=self.state)
        self.assertEqual((self.profile / 'saves' / 'test.save').read_bytes(), b'owner-created test household')
        self.assertFalse((self.profile / 'saves' / 'Slot_00000001.save').exists())
        self.assertFalse((self.profile / 'Mods' / 'original.package').exists())
        self.assertTrue((Path(result['test_archive']) / 'saves' / 'test.save').exists())
        test_profile.restore(next_state, self.guard)
        self.assertEqual(test_profile.inventory(self.profile), self.baseline)

    def test_unrestored_or_wrongly_marked_seed_is_rejected_before_mutation(self):
        self.activate()
        with self.assertRaises(ValueError):
            test_profile.test_seed(self.state, self.profile)
        result = test_profile.restore(self.state, self.guard)
        (Path(result['test_archive']) / test_profile.MARKER).write_text('{}')
        with self.assertRaises(ValueError):
            test_profile.activate(self.profile, self.root / 'next.json', [self.artifact], guard=self.guard, seed_state=self.state)
        self.assertEqual(test_profile.inventory(self.profile), self.baseline)


if __name__ == '__main__':
    unittest.main()
