import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui


def client():
    return {'scope': 'native-cas-client', 'sim': {'simId': '12'},
            'menu_state': 0, 'panel_visible': False,
            'outfit': {'outfit_type': 0, 'outfit_index': 0},
            'catalogs': [{'panel': name, 'menu_state': state, 'supported': True,
                          'items': [], 'preset': None, 'preset_query': 'returned-null'}
                         for name, state in cas_ui.PANELS.items()],
            'control': {'operation': 'swatch', 'selected': '59238'}}


class CasFailedPostconditionTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear()
        cas_ui._PEERS.clear()
        self.addCleanup(cas_ui._RECORDS.clear)
        self.addCleanup(cas_ui._PEERS.clear)
        self.sent = []
        self.rid = cas_ui.submit('12', {'operation': 'swatch', 'swatch_type': 3,
            'data_id': '270531', 'color_index': 0}, send=self.sent.append)['cas_request_id']
        self.packet = {'protocol': 1, 'ok': True, 'cas_request_id': self.rid,
                       'mutation_started': True, 'client': client(),
                       'future': {'untouched': ['18446744073709551615']}}

    def test_complete_failed_swatch_allows_next_request_without_retry_or_success(self):
        with self.assertRaisesRegex(ValueError, 'exact selected identity'):
            cas_ui.receive(self.rid, json.dumps(self.packet))
        before = len(self.sent)
        result = cas_ui.result(self.rid)
        self.assertFalse(result['ok'])
        self.assertEqual(result['cas_request_state'], 'failed')
        self.assertEqual(result['native_acknowledgement'], self.packet)
        self.assertFalse(result['retry_submitted'])
        self.assertFalse(result['ui_transition_verified'])
        self.assertFalse(result['postcondition_verified'])
        self.assertTrue(result['mutation_started'])
        self.assertEqual(result['native_acknowledgement_sha256'], cas_ui._baseline_hash(self.packet))
        cas_ui.receive(self.rid, json.dumps(self.packet))
        self.assertEqual(len(self.sent), before)
        changed = copy.deepcopy(self.packet)
        changed['client']['control']['selected'] = '270531'
        with self.assertRaisesRegex(ValueError, 'acknowledgement changed'):
            cas_ui.receive(self.rid, json.dumps(changed))
        cas_ui.submit('12', {'operation': 'status'}, send=self.sent.append)
        self.assertEqual(cas_ui.result(self.rid), result)

    def test_foreign_incomplete_or_untyped_readbacks_remain_blocked(self):
        for mode in ('foreign', 'incomplete', 'untyped', 'operation', 'empty'):
            with self.subTest(mode=mode):
                cas_ui._RECORDS[self.rid]['state'] = 'pending'
                cas_ui._RECORDS[self.rid]['result'] = None
                packet = copy.deepcopy(self.packet)
                if mode == 'foreign': packet['client']['sim']['simId'] = '13'
                if mode == 'incomplete': packet['client']['catalogs'].pop()
                if mode == 'untyped': packet['client']['control']['selected'] = 59238
                if mode == 'operation': packet['client']['control']['operation'] = 'status'
                if mode == 'empty': packet['client']['control']['selected'] = ''
                with self.assertRaises(ValueError): cas_ui.receive(self.rid, json.dumps(packet))
                self.assertEqual(cas_ui.result(self.rid)['cas_request_state'], 'pending')
                with self.assertRaisesRegex(ValueError, 'unresolved'):
                    cas_ui.submit('12', {'operation': 'status'}, send=self.sent.append)


if __name__ == '__main__':
    unittest.main()
