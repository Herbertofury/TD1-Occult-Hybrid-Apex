import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui


def client():
    return {'scope': 'native-cas-client', 'sim': {'simId': '12', 'futurePackData': {'exact': '18446744073709551615'}},
            'menu_state': 0, 'panel_visible': False, 'outfit': {'outfit_type': 0, 'outfit_index': 0},
            'hair_selected_swatch_id': '414264',
            'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                          'preset': None, 'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()],
            'planned_outfits': [{'category': 0, 'data': {'outfit_list': [
                {'outfit_type': 0, 'outfit_index': 0, 'selected': True}]}}]}


class CasHistoryAckTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear()
        cas_ui._PEERS.clear()
        cas_ui._CONNECTION = cas_ui._READY = cas_ui._LAST_REPLY = None

    def submit(self, before, after, operation='undo'):
        rid = cas_ui.submit('12', {'operation': operation}, send=lambda _: None)['cas_request_id']
        reply = {'protocol': 1, 'ok': True, 'cas_request_id': rid, 'client': after,
                 'history_before_json': json.dumps(before)}
        return rid, json.dumps(reply)

    def assert_rejected_history(self, rid, payload):
        result = cas_ui.result(rid)
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'invalid-native-acknowledgement')
        self.assertEqual(result['cas_request_state'], 'pending')
        self.assertEqual(result['native_acknowledgement'], json.loads(payload))
        self.assertNotIn('history_data_change_verified', result)
        # A rejected reply is observable; it still cannot authorize a repeat.
        with self.assertRaises(ValueError):
            cas_ui.submit('12', {'operation': 'undo'}, send=lambda _: None)

    def test_navigation_only_changes_cannot_prove_history(self):
        before, after = client(), client()
        after.update(menu_state=42, panel_visible=True, outfit={'outfit_type': 1, 'outfit_index': 0},
                     native_context={'edit_mode': {'value': 7}})
        after['planned_outfits'][0]['data']['outfit_list'][0]['selected'] = False
        rid, payload = self.submit(before, after)
        with self.assertRaisesRegex(ValueError, 'only navigation'):
            cas_ui.receive(rid, payload)
        self.assert_rejected_history(rid, payload)

    def test_exact_swatch_change_verified_and_duplicate_ack_idempotent(self):
        before, after = client(), client()
        after['hair_selected_swatch_id'] = '414266'
        rid, payload = self.submit(before, after)
        cas_ui.receive(rid, payload)
        cas_ui.receive(rid, payload)
        result = cas_ui.result(rid)
        self.assertTrue(result['history_data_change_verified'])
        self.assertFalse(result['history_expected_target_verified'])
        self.assertEqual(json.loads(result['history_before_json']), before)
        self.assertEqual(result['client'], after)

    def test_all_sim_fields_equipped_item_preset_and_slot_existence_count(self):
        for change in ('future', 'item', 'preset', 'outfit'):
            with self.subTest(change=change):
                self.setUp()
                before, after = client(), client()
                if change == 'future': after['sim']['futurePackData']['exact'] = '18446744073709551614'
                if change == 'item': after['catalogs'][0]['items'] = [{'dataID': '12', 'futureLayer': {'raw': 1}}]
                if change == 'preset':
                    after['catalogs'][0].update(preset={'presetId': '123', 'index': 2}, preset_query='returned-value')
                if change == 'outfit':
                    after['planned_outfits'][0]['data']['outfit_list'].append(
                        {'outfit_type': 0, 'outfit_index': 1, 'selected': False})
                rid, payload = self.submit(before, after, 'redo')
                cas_ui.receive(rid, payload)
                self.assertTrue(cas_ui.result(rid)['history_data_change_verified'])

    def test_record_order_and_key_order_do_not_count_as_history(self):
        before, after = client(), client()
        after['sim'] = dict(reversed(list(after['sim'].items())))
        after['catalogs'].reverse()
        rid, payload = self.submit(before, after)
        with self.assertRaisesRegex(ValueError, 'only navigation'):
            cas_ui.receive(rid, payload)

    def test_missing_or_different_sim_prestate_cannot_resolve_history(self):
        before, after = client(), client()
        after['hair_selected_swatch_id'] = '414266'
        for mode in ('missing', 'wrong-sim', 'incomplete', 'invalid-json'):
            with self.subTest(mode=mode):
                self.setUp()
                rid, payload = self.submit(before, after)
                reply = json.loads(payload)
                if mode == 'missing': reply.pop('history_before_json')
                elif mode == 'invalid-json': reply['history_before_json'] = '{'
                else:
                    old = copy.deepcopy(before)
                    if mode == 'wrong-sim': old['sim']['simId'] = '13'
                    else: old.pop('catalogs')
                    reply['history_before_json'] = json.dumps(old)
                rejected_payload = json.dumps(reply)
                with self.assertRaises(ValueError): cas_ui.receive(rid, rejected_payload)
                self.assert_rejected_history(rid, rejected_payload)


if __name__ == '__main__':
    unittest.main()
