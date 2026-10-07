import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import reusable_profile as reusable
import test_profile as legacy
from source_manifest import sha256, write_json


class ReusableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / reusable.PROTECTED_NAME
        (self.original / 'saves').mkdir(parents=True)
        (self.original / 'Mods').mkdir()
        (self.original / 'saves' / 'precious.save').write_bytes(b'owner data')
        (self.original / 'Mods' / 'precious.package').write_bytes(b'DBPF owner data')
        (self.original / 'UserSetting.ini').write_text('[uiaccountsettings]\n123#mtx.viewedpacks#string = 1,2\n123#cdswelcomeseen#boolean = true\n')
        self.original_inventory = legacy.inventory(self.original)
        self.profile = self.root / 'The Sims 4'
        self.state = self.root / 'work' / 'reusable.json'
        self.state.parent.mkdir()
        self.previous = self.state.parent / 'previous.json'
        self.artifact = self.root / 'old.package'
        self.artifact.write_bytes(b'DBPF old test artifact')
        self.retained = self.make_retained('a' * 32, self.previous)
        self.guard = lambda: None

    def make_retained(self, token, previous):
        retained = self.root / ('The Sims 4.ApexTest.' + token)
        (retained / 'saves').mkdir(parents=True)
        (retained / 'Tray').mkdir()
        (retained / 'Mods' / 'ApexTest').mkdir(parents=True)
        (retained / 'saves' / 'test.save').write_bytes(b'owner created test household')
        (retained / 'Tray' / 'sim.trayitem').write_bytes(b'owner test sim')
        (retained / 'Mods' / 'ApexTest' / self.artifact.name).write_bytes(self.artifact.read_bytes())
        (retained / 'Mods' / 'Resource.cfg').write_text('Priority 500\n')
        write_json(retained / legacy.MARKER, {'token': token, 'disposable': True})
        write_json(previous, {'schema': 1, 'phase': 'restored', 'token': token,
                             'test_archive': str(retained), 'artifacts': legacy.validate_artifacts([self.artifact]),
                             'original_inventory': self.original_inventory})
        return retained

    def adopt(self):
        return reusable.adopt(self.previous, self.profile, self.state, self.original, guard=self.guard)

    def assert_original_untouched(self):
        self.assertEqual(legacy.inventory(self.original), self.original_inventory)

    def test_adopt_reuse_install_and_read_only_original(self):
        before = legacy.inventory(self.retained)
        self.assertTrue(self.adopt()['ready_to_launch'])
        self.assertFalse(self.retained.exists())
        self.assertEqual(legacy.inventory(self.profile), before)
        replacement = self.root / 'next.package'
        replacement.write_bytes(b'DBPF newer test artifact')
        self.assertTrue(reusable.install(self.state, [replacement], self.guard)['ready_to_launch'])
        self.assertEqual((self.profile / 'saves' / 'test.save').read_bytes(), b'owner created test household')
        self.assertFalse((self.profile / 'Mods' / 'precious.package').exists())
        self.assert_original_untouched()
        self.assertTrue(reusable.status(self.state, True)['original_inventory_verified_now'])

    def test_original_path_never_writable_and_legacy_swaps_disabled(self):
        for path in (self.original, self.original / 'saves' / 'any.save'):
            with self.assertRaises(ValueError):
                reusable.writable(path)
        with self.assertRaises(ValueError):
            legacy.activate(self.profile, self.state, [self.artifact], self.guard)
        self.adopt()
        with self.assertRaises(ValueError):
            legacy.restore(self.state, self.guard)
        self.assert_original_untouched()

    def test_adoption_reuses_empty_path_but_refuses_any_unknown_content(self):
        self.profile.mkdir()
        unknown = self.profile / 'owner.txt'
        unknown.write_text('preserve this')
        with self.assertRaises(ValueError):
            self.adopt()
        self.assertEqual(unknown.read_text(), 'preserve this')
        unknown.unlink()
        self.assertTrue(self.adopt()['ready_to_launch'])
        self.assert_original_untouched()

    def test_running_game_refuses_adoption_and_install(self):
        def running():
            raise RuntimeError('game running')
        with self.assertRaises(RuntimeError):
            reusable.adopt(self.previous, self.profile, self.state, self.original, guard=running)
        self.assertTrue(self.retained.is_dir())
        self.assertFalse(self.state.exists())
        self.adopt()
        before = legacy.inventory(self.profile)
        with self.assertRaises(RuntimeError):
            reusable.install(self.state, [self.artifact], running)
        self.assertEqual(legacy.inventory(self.profile), before)
        self.assert_original_untouched()

    def test_unknown_mod_or_tampered_path_refuses_install(self):
        self.adopt()
        intruder = self.profile / 'Mods' / 'unknown.package'
        intruder.write_bytes(b'DBPF unknown')
        before = legacy.inventory(self.profile)
        with self.assertRaises(ValueError):
            reusable.install(self.state, [self.artifact], self.guard)
        self.assertEqual(legacy.inventory(self.profile), before)
        intruder.unlink()
        data = json.loads(self.state.read_text())
        data['artifacts'][0]['name'] = '../precious.package'
        write_json(self.state, data)
        with self.assertRaises(ValueError):
            reusable.install(self.state, [self.artifact], self.guard)
        self.assert_original_untouched()

    def test_consolidation_preserves_every_retired_file_before_removal(self):
        self.adopt()
        previous = self.state.parent / 'older.json'
        retained = self.make_retained('b' * 32, previous)
        (retained / 'extra.dat').write_bytes(b'also keep this')
        rows = {path.relative_to(retained).as_posix(): path.read_bytes() for path in retained.rglob('*') if path.is_file()}
        result = reusable.consolidate(self.state, [previous], self.guard)
        self.assertFalse(retained.exists())
        recovered = json.loads(Path(result['recovery_manifest']).read_text())['files']
        self.assertEqual(set(rows), {row['path'] for row in recovered})
        for row in recovered:
            backup = Path(result['recovery_manifest']).parent / (row['sha256'] + '.bin')
            self.assertEqual(backup.read_bytes(), rows[row['path']])
        self.assert_original_untouched()

    def test_false_seed_marker_refuses_consolidation(self):
        self.adopt()
        previous = self.state.parent / 'older.json'
        retained = self.make_retained('c' * 32, previous)
        write_json(retained / legacy.MARKER, {'token': 'wrong'})
        with self.assertRaises(ValueError):
            reusable.consolidate(self.state, [previous], self.guard)
        self.assertTrue(retained.exists())
        self.assert_original_untouched()

    def test_settings_are_copied_only_into_test_profile(self):
        self.adopt()
        result = reusable.preserve_settings(self.state, self.guard)
        self.assertFalse(result['original_written'])
        self.assertFalse(result['announcement_ui_verified'])
        self.assertEqual((self.profile / 'UserSetting.ini').read_bytes(), (self.original / 'UserSetting.ini').read_bytes())
        self.assert_original_untouched()

    def test_interrupted_install_can_recover_without_original_access(self):
        self.adopt()
        replacement = self.root / 'next.package'
        replacement.write_bytes(b'DBPF newer test artifact')
        replace = reusable.os.replace
        def fail_artifact(source, target):
            if Path(target).suffix == '.package':
                raise OSError('simulated disk failure')
            return replace(source, target)
        with patch.object(reusable.os, 'replace', side_effect=fail_artifact):
            with self.assertRaises(OSError):
                reusable.install(self.state, [replacement], self.guard)
        self.assertFalse(reusable.status(self.state)['ready_to_launch'])
        self.assertTrue(reusable.recover(self.state, self.guard)['ready_to_launch'])
        self.assertEqual(sha256(self.profile / 'Mods' / 'ApexTest' / replacement.name), sha256(replacement))
        self.assert_original_untouched()

    def test_existing_operation_lock_refuses_parallel_mutation(self):
        self.adopt()
        lock = self.state.with_name(self.state.name + '.operation-lock')
        lock.write_text('another process')
        with self.assertRaises(FileExistsError):
            reusable.install(self.state, [self.artifact], self.guard)
        self.assertEqual(lock.read_text(), 'another process')
        self.assert_original_untouched()


if __name__ == '__main__':
    unittest.main()
