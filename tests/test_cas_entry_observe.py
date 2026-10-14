import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cas_entry_observe import entry_identity


class AcceptedEntryObservationTests(unittest.TestCase):
    def setUp(self):
        self.identity = {'pid': 123, 'test_token': 'a' * 32, 'script_sha256': 'b' * 64}
        self.entry = {'operation': 'observe-native-cas-entry', 'entry_submitted': True,
                      'entry_accepted': True, 'requested_sim_id': '7', 'identity': self.identity,
                      'ok': False, 'error': 'observer timed out', 'crash': {'outcome': 'unchanged'}}

    def test_observer_timeout_does_not_require_replaying_accepted_entry(self):
        original = copy.deepcopy(self.entry)
        entry_identity(self.entry, self.identity, '7')
        self.assertEqual(self.entry, original)

    def test_rejected_or_unsubmitted_entry_is_not_promoted_by_followup(self):
        for key in ('entry_submitted', 'entry_accepted'):
            bad = copy.deepcopy(self.entry); bad[key] = False
            with self.subTest(key=key), self.assertRaises(ValueError): entry_identity(bad, self.identity, '7')

    def test_changed_runtime_identity_blocks_followup(self):
        for key, value in (('pid', 124), ('test_token', 'c' * 32), ('script_sha256', 'd' * 64)):
            changed = dict(self.identity, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError): entry_identity(self.entry, changed, '7')

    def test_changed_sim_crash_and_untyped_document_are_refused(self):
        with self.assertRaises(ValueError): entry_identity(self.entry, self.identity, '8')
        bad = copy.deepcopy(self.entry); bad['crash']['outcome'] = 'changed'
        with self.assertRaises(ValueError): entry_identity(bad, self.identity, '7')
        with self.assertRaises(ValueError): entry_identity([], self.identity, '7')


if __name__ == '__main__': unittest.main()
