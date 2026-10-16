import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import test_autosave_recovery as recovery
import test_profile
from game_lifecycle import save_files
from source_manifest import sha256, write_json


class AutosaveRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / recovery.reusable_profile.PROTECTED_NAME
        self.original.mkdir()
        (self.original / 'owner.save').write_bytes(b'precious')
        (self.profile / 'saves').mkdir(parents=True)
        self.normal = self.profile / 'saves' / 'Slot_00000002.save'
        self.normal.write_bytes(b'user-created disposable household')
        self.state = self.root / 'work' / 'journal.json'
        self.state.parent.mkdir()
        self.token = 'a' * 32
        write_json(self.profile / test_profile.MARKER, {'disposable': True, 'token': self.token})
        write_json(self.state, {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active',
            'generation': 41, 'token': self.token, 'profile': str(self.profile),
            'protected_original': str(self.original), 'artifacts': []})
        self.store = self.state.parent / 'test-data-recovery'
        self.store.mkdir()
        rows = []
        for name in sorted(recovery.AUTOSAVES):
            saved = self.store / (name + '.old')
            saved.write_bytes(('good ' + name).encode())
            digest = sha256(saved)
            saved.rename(self.store / (digest + '.bin'))
            rows.append({'path': 'saves/' + name, 'sha256': digest, 'bytes': len(('good ' + name).encode())})
            (self.profile / 'saves' / name).write_bytes(('failed ' + name).encode())
        self.backup = self.store / 'latest.json'
        write_json(self.backup, {'schema': 1, 'token': self.token, 'files': rows})
        self.exit = self.state.parent / 'exit.json'
        write_json(self.exit, {'operation': 'normal-discard-failed-cas-session', 'ok': True,
            'normal_exit_verified': True, 'game_exit_verified': True, 'save_submitted': False,
            'save_files_unchanged_verified': True, 'after_saves': save_files(self.profile),
            'identity': {'test_token': self.token, 'profile': str(self.profile)}})
        self.output = self.state.parent / 'receipt.json'
        self.before = test_profile.inventory(self.profile)

    def run_recovery(self, guard=lambda: None):
        return recovery.recover(self.state, self.backup, sha256(self.backup),
            self.exit, sha256(self.exit), self.output, guard=guard)

    def test_only_autosaves_replaced_and_all_failed_bytes_preserved(self):
        result = self.run_recovery()
        self.assertTrue(result['ok'])
        self.assertTrue(result['normal_slots_unchanged'])
        self.assertEqual(self.normal.read_bytes(), b'user-created disposable household')
        self.assertEqual((self.original / 'owner.save').read_bytes(), b'precious')
        receipt = json.loads(self.output.read_text())
        for row in receipt['files']:
            self.assertEqual(Path(row['preserved']).read_bytes(), ('failed ' + row['file']).encode())
            self.assertEqual((self.profile / 'saves' / row['file']).read_bytes(), ('good ' + row['file']).encode())

    def normal_exit(self):
        value = json.loads(self.exit.read_text())
        value.pop('save_submitted')
        value.update(operation='normal-exit-without-saving', outcome='normal-exit-without-saving',
            save_requested=False, exit_without_save_input_accepted=True, final_process_alive=False,
            before_all_saves=recovery.all_save_files(self.profile),
            after_all_saves=recovery.all_save_files(self.profile))
        write_json(self.exit, value)
        return value

    def test_normal_cli_unsaved_exit_preserves_every_current_file_and_replaces_only_six_autosaves(self):
        self.normal_exit()
        result = self.run_recovery()
        self.assertTrue(result['ok'])
        self.assertEqual(self.normal.read_bytes(), b'user-created disposable household')
        self.assertEqual((self.original / 'owner.save').read_bytes(), b'precious')
        rows = json.loads(self.output.read_text())['files']
        self.assertEqual({row['file'] for row in rows}, recovery.AUTOSAVES)
        for row in rows:
            self.assertEqual(Path(row['preserved']).read_bytes(), ('failed ' + row['file']).encode())

    def test_normal_exit_save_selection_unknown_process_or_changed_exit_inventory_refuse_without_writes(self):
        value = self.normal_exit()
        for field, replacement in (('save_requested', True), ('exit_without_save_input_accepted', False),
                ('final_process_alive', None), ('after_all_saves', {}), ('operation', 'normal-save-and-exit')):
            changed = dict(value, **{field: replacement})
            write_json(self.exit, changed)
            with self.assertRaises(ValueError):
                self.run_recovery()
            self.assertEqual(test_profile.inventory(self.profile), self.before)
            self.assertFalse(self.output.exists())

    def test_external_autosave_edit_after_normal_exit_cannot_be_silently_replaced(self):
        self.normal_exit()
        changed = self.profile / 'saves' / 'Slot_ffffffff.save'
        changed.write_bytes(b'newer independent test session')
        before = test_profile.inventory(self.profile)
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            self.run_recovery()
        self.assertEqual(test_profile.inventory(self.profile), before)
        self.assertFalse(self.output.exists())

    def test_running_game_refuses_before_profile_writes(self):
        def running():
            raise ValueError('Game is running')
        with self.assertRaises(ValueError):
            self.run_recovery(running)
        self.assertEqual(test_profile.inventory(self.profile), self.before)

    def test_cross_profile_token_invalidates_receipt(self):
        value = json.loads(self.exit.read_text())
        value['identity']['test_token'] = 'b' * 32
        write_json(self.exit, value)
        with self.assertRaises(ValueError):
            self.run_recovery()
        self.assertEqual(test_profile.inventory(self.profile), self.before)

    def test_changed_normal_save_refuses_before_replacement(self):
        self.normal.write_bytes(b'newer user edit')
        before = test_profile.inventory(self.profile)
        with self.assertRaises(ValueError):
            self.run_recovery()
        self.assertEqual(test_profile.inventory(self.profile), before)

    def test_backup_cannot_select_normal_slot_or_duplicate_target(self):
        value = json.loads(self.backup.read_text())
        value['files'][0]['path'] = 'saves/Slot_00000002.save'
        write_json(self.backup, value)
        with self.assertRaises(ValueError):
            self.run_recovery()
        self.assertEqual(test_profile.inventory(self.profile), self.before)

    def test_interrupted_replacement_has_preserved_every_autosave_and_no_replay(self):
        with patch.object(recovery.os, 'replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.run_recovery()
        receipt = json.loads(self.output.read_text())
        self.assertFalse(receipt['ok'])
        self.assertTrue(all(sha256(Path(row['preserved'])) == row['before_sha256'] for row in receipt['files']))
        with self.assertRaises(ValueError):
            self.run_recovery()
        self.assertEqual(test_profile.inventory(self.profile), self.before)


if __name__ == '__main__':
    unittest.main()
