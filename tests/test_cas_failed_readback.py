import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
import cas_failed_readback
from apex_core import cas_ui


class FailedReadbackClosureTests(unittest.TestCase):
    def setUp(self):
        self.rid = 'a' * 32
        self.diagnostic = {'native_peers': [], 'requests': [
            {'cas_request_id': self.rid, 'state': 'pending', 'operation': 'swatch'}]}
        client = {'scope': 'native-cas-client', 'sim': {'simId': '12'},
            'menu_state': 0, 'panel_visible': False,
            'outfit': {'outfit_type': 0, 'outfit_index': 0},
            'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                          'preset': None, 'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()],
            'control': {'operation': 'swatch', 'selected': '59238'}}
        self.receipt = {'ok': False, 'cas_request_id': self.rid, 'cas_request_state': 'pending',
            'outcome': 'invalid-native-acknowledgement',
            'message': 'Native swatch did not read back its exact selected identity.',
            'native_acknowledgement': {'protocol': 1, 'ok': True, 'cas_request_id': self.rid,
                'operation': 'swatch', 'mutation_started': True, 'client': client},
            'future': {'full': ['18446744073709551615']}}

    def test_classifies_only_for_unsaved_exit_and_retains_complete_original(self):
        original = copy.deepcopy(self.diagnostic)
        projected, evidence = cas_failed_readback.classify(self.diagnostic, {self.rid: self.receipt}, '12')
        self.assertEqual(self.diagnostic, original)
        self.assertEqual(projected['requests'][0]['state'], 'failed')
        self.assertEqual(evidence[0]['source_receipt'], self.receipt)
        self.assertFalse(evidence[0]['save_authorized'])
        self.assertFalse(evidence[0]['cas_writer_unlocked'])
        self.assertFalse(evidence[0]['source_request_state_changed'])

    def test_foreign_missing_changed_or_active_native_context_refuses(self):
        for mode in ('peer', 'foreign', 'incomplete', 'nonce', 'lost', 'wrong-operation', 'unknown-error'):
            with self.subTest(mode=mode):
                diagnostic, receipt = copy.deepcopy(self.diagnostic), copy.deepcopy(self.receipt)
                if mode == 'peer': diagnostic['native_peers'] = [{'sim_id': '12'}]
                if mode == 'foreign': receipt['native_acknowledgement']['client']['sim']['simId'] = '13'
                if mode == 'incomplete': receipt['native_acknowledgement']['client']['catalogs'].pop()
                if mode == 'nonce': receipt['native_acknowledgement']['cas_request_id'] = 'b' * 32
                if mode == 'lost': receipt.pop('native_acknowledgement')
                if mode == 'wrong-operation': receipt['native_acknowledgement']['operation'] = 'accept'
                if mode == 'unknown-error': receipt['message'] = 'Unknown completion.'
                with self.assertRaises(ValueError): cas_failed_readback.classify(diagnostic, {self.rid: receipt}, '12')

    def test_other_pending_operations_are_preserved_and_never_reclassified(self):
        self.diagnostic['requests'].append({'cas_request_id': 'b' * 32, 'state': 'accept-unresolved', 'operation': 'accept'})
        projected, _ = cas_failed_readback.classify(self.diagnostic, {self.rid: self.receipt}, '12')
        self.assertEqual(projected['requests'][1], self.diagnostic['requests'][1])


if __name__ == '__main__':
    unittest.main()
