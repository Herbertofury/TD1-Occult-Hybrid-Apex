import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cas_transition import protected_initial_member
import test_cas_transition as fixture


class EntryMemberTests(unittest.TestCase):
    def setUp(self):
        rows = [{'sim_id': sid, 'form_checkpoint': {'ok': True}, 'owner_observation':
                 {'original_owner': {'complete': True, 'original_sim_id': sid, 'household_id': '20'}}}
                for sid in ('12', '13')]
        self.entry = {'requested_editor': 'existing-household-full', 'household_form_checkpoints':
                      {'ok': True, 'household_id': '20', 'roster_sim_ids': ['12', '13'], 'members': rows}}
        self.diagnostic = fixture.diagnostic('12')

    def test_only_exact_fresh_captured_household_peer_can_select_requested_member(self):
        self.assertEqual(protected_initial_member(self.entry, self.diagnostic, '13'),
                         {'source': '12', 'target': '13', 'household': '20'})

    def test_foreign_stale_ambiguous_or_missing_owner_peer_never_authorizes_navigation(self):
        for mode in ('foreign', 'stale', 'household', 'missing', 'duplicate', 'single'):
            entry, diagnostic = copy.deepcopy(self.entry), copy.deepcopy(self.diagnostic)
            scope = entry['household_form_checkpoints']
            if mode == 'foreign': diagnostic['native_peers'][0]['sim_id'] = '99'
            if mode == 'stale': diagnostic['native_peers'][0]['age_seconds'] = 4
            if mode == 'household': scope['members'][0]['owner_observation']['original_owner']['household_id'] = '21'
            if mode == 'missing': scope['members'][0].pop('owner_observation')
            if mode == 'duplicate': scope['members'].append(copy.deepcopy(scope['members'][0]))
            if mode == 'single': entry['requested_editor'] = 'existing-single-sim'
            with self.subTest(mode=mode): self.assertIsNone(protected_initial_member(entry, diagnostic, '13'))

    def test_requested_member_already_selected_or_not_captured_needs_no_handoff(self):
        self.assertIsNone(protected_initial_member(self.entry, fixture.diagnostic('13'), '13'))
        self.assertIsNone(protected_initial_member(self.entry, self.diagnostic, '99'))


if __name__ == '__main__': unittest.main()
