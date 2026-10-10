from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.change_journal import ChangeJournal


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'journal.json')
        self.journal = ChangeJournal(self.path, 'save:sim:werewolf')
        self.current = b'original\x00\xff'

    def read(self):
        return self.current

    def write(self, raw):
        self.current = raw

    def commit(self, raw):
        token = self.journal.prepare('Edit', self.current, raw)
        self.journal.apply(token, self.read, self.write)
        return self.journal.data['cursor']

    def test_preview_cancel_has_no_appearance_mutation(self):
        token = self.journal.prepare('Preview', self.current, b'after')
        self.assertEqual(self.current, b'original\x00\xff')
        self.journal.cancel(token)
        self.assertIsNone(ChangeJournal(self.path, 'save:sim:werewolf').data['pending'])
        self.assertEqual(self.current, b'original\x00\xff')

    def test_stale_preview_never_overwrites_new_intent(self):
        token = self.journal.prepare('Edit', self.current, b'after')
        self.current = b'new intentional CAS edit'
        with self.assertRaisesRegex(ValueError, 'not overwritten'):
            self.journal.apply(token, self.read, self.write)
        self.assertEqual(self.current, b'new intentional CAS edit')

    def test_undo_redo_and_edit_after_undo_preserve_both_branches(self):
        first = self.commit(b'first')
        second = self.commit(b'second')
        token = self.journal.restore('Undo', self.current)
        self.journal.apply(token, self.read, self.write)
        self.assertEqual(self.current, b'first')
        third = self.commit(b'new branch')
        token = self.journal.restore('Undo', self.current)
        self.journal.apply(token, self.read, self.write)
        with self.assertRaisesRegex(ValueError, 'branch explicitly'):
            self.journal.restore('Redo', self.current)
        token = self.journal.restore('Redo', self.current, second)
        self.journal.apply(token, self.read, self.write)
        self.assertEqual(self.current, b'second')
        self.assertEqual({node['id'] for node in self.journal.timeline()}, {first, second, third, self.journal.data['nodes'][0]['id']})
        self.assertTrue(any(row['kind'] == 'Undo' for row in self.journal.data['operations']))

    def test_failed_readback_rolls_back_and_records_failure(self):
        before = self.current
        token = self.journal.prepare('Edit', before, b'after')
        def broken_write(raw):
            self.current = before if raw == before else b'partial corruption'
        with self.assertRaisesRegex(ValueError, 'readback differs'):
            self.journal.apply(token, self.read, broken_write)
        self.assertEqual(self.current, before)
        self.assertEqual(self.journal.data['operations'][-1]['kind'], 'failed-rolled-back')

    def test_interrupted_applied_transaction_recovers_without_rewriting(self):
        self.journal.prepare('Edit', self.current, b'after')
        self.current = b'after'
        restored = ChangeJournal(self.path, 'save:sim:werewolf')
        self.assertIn('already-applied', restored.recover(self.current))
        self.assertIsNone(restored.data['pending'])
        self.assertTrue(restored.data['operations'][-1]['recovered'])

    def test_interrupted_unrecognized_state_and_wrong_lane_are_rejected(self):
        self.journal.prepare('Edit', self.current, b'after')
        with self.assertRaisesRegex(ValueError, 'neither'):
            self.journal.recover(b'newer external edit')
        with self.assertRaisesRegex(ValueError, 'different'):
            ChangeJournal(self.path, 'another-save:sim:human')

    def test_pending_tampering_is_rejected_before_restore(self):
        self.journal.prepare('Edit', self.current, b'after')
        data = json.loads(Path(self.path).read_text())
        data['pending']['after'] = 'dGFtcGVyZWQ='
        Path(self.path).write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Corrupt pending'):
            ChangeJournal(self.path, 'save:sim:werewolf')

    def test_named_checkpoints_remain_distinct_even_for_unchanged_state(self):
        first = self.journal.observe(self.current, 'A', force=True)
        second = self.journal.observe(self.current, 'B', force=True)
        self.assertNotEqual(first, second)
        self.assertEqual(self.journal.timeline()[-1]['label'], 'B')
