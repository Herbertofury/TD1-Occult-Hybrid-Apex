import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from save_intent_archive import validate_record


class SaveArchiveTests(unittest.TestCase):
    def setUp(self):
        self.token, self.digest = 'a' * 32, 'b' * 64
        identity = {'pid': 123, 'test_token': self.token}
        self.record = {'state': 'save-submitted', 'intent_id': 'c' * 32, 'identity': identity,
                       'before_file': {'sha256': self.digest},
                       'target': {'slot_id': 2, 'expected_save_sha256': self.digest}}
        self.failure = {'identity': identity, 'save_completed_file_verified': False,
                        'steps': [{'action': 'test_save', 'result': {'form_bank_seal': {'intent_id': 'c' * 32}}}]}
        self.closure = {'identity': identity, 'ok': True, 'normal_exit_verified': True,
                        'exit_without_save_input_accepted': True, 'save_files_unchanged_verified': True,
                        'game_exit_verified': True, 'after_all_saves': {'Slot_00000002.save': {'sha256': self.digest}}}

    def validate(self, **change):
        args = dict(record=self.record, failure=self.failure, closure=self.closure,
                    token=self.token, save_hash=self.digest, old_absent=True)
        args.update(change)
        return validate_record(**args)

    def test_proven_unsaved_exit_accepts_original_intent_without_changing_it(self):
        before = copy.deepcopy(self.record)
        self.assertEqual(self.validate(), 2)
        self.assertEqual(self.record, before)

    def test_live_or_unknown_old_process_refuses_archival(self):
        for absent in (False, None, 1):
            with self.subTest(absent=absent), self.assertRaises(ValueError): self.validate(old_absent=absent)

    def test_each_native_closure_condition_is_required(self):
        for key in ('ok', 'normal_exit_verified', 'exit_without_save_input_accepted', 'save_files_unchanged_verified', 'game_exit_verified'):
            bad = copy.deepcopy(self.closure); bad[key] = False
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(closure=bad)

    def test_saved_or_different_runtime_proof_refuses_archival(self):
        for key, value in (('save_completed_file_verified', True), ('identity', {'pid': 124, 'test_token': self.token})):
            bad = copy.deepcopy(self.failure); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(failure=bad)

    def test_different_observed_intent_is_not_removed(self):
        bad = copy.deepcopy(self.failure)
        bad['steps'][0]['result']['form_bank_seal']['intent_id'] = 'd' * 32
        with self.assertRaises(ValueError): self.validate(failure=bad)

    def test_changed_target_file_or_untyped_slot_refuses_archival(self):
        with self.assertRaises(ValueError): self.validate(save_hash='e' * 64)
        for slot in (True, 0, 0xffffffff, '2'):
            bad = copy.deepcopy(self.record); bad['target']['slot_id'] = slot
            with self.subTest(slot=slot), self.assertRaises(ValueError): self.validate(record=bad)


if __name__ == '__main__': unittest.main()
