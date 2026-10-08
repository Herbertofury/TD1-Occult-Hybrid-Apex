import argparse
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
from apex_core import cas_ui
from cas_client import execute
from cas_ui_build import replace_abc, unpack, tags


class CasUiTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear()
        cas_ui._CONNECTION = cas_ui._READY = cas_ui._LAST_REPLY = None

    def test_native_startup_is_separate_from_complete_client_state(self):
        cas_ui.observe_ready(1, None)
        self.assertTrue(cas_ui.diagnostics()['native_initializer_observed'])
        self.assertFalse(cas_ui.diagnostics()['ui_transition_verified'])
        with self.assertRaises(ValueError): cas_ui.observe_ready(True, None)
        rid = cas_ui.submit('12', {'operation':'status'}, send=lambda _: None)['cas_request_id']
        self.assertTrue(cas_ui.reply_connection_allowed(rid, None))
        self.assertFalse(cas_ui.reply_connection_allowed('b'*32, None))
        self.assertFalse(cas_ui.reply_connection_allowed(rid, 42))
        cas_ui.observe_connection(42)
        self.assertTrue(cas_ui.reply_connection_allowed(rid, 42))

    def test_absent_distributor_client_refuses_before_record_or_input(self):
        dropped = []
        distributor = SimpleNamespace(client=None, add_op_with_no_owner=dropped.append)
        modules = {'distributor.ops': SimpleNamespace(SendUIMessage=lambda name: name),
                   'distributor.system': SimpleNamespace(Distributor=SimpleNamespace(instance=lambda:distributor))}
        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(ValueError, 'no distributor client'):
                cas_ui.submit('12', {'operation':'status'})
        self.assertEqual(dropped, [])
        self.assertEqual(len(cas_ui._RECORDS), 0)

    def test_lost_read_can_be_superseded_but_mutations_remain_unresolved(self):
        clock = [0]
        send = lambda _: None
        old = cas_ui.submit('12', {'operation':'status'}, send=send, clock=lambda:clock[0])['cas_request_id']
        clock[0] = 9
        with self.assertRaisesRegex(ValueError,'unresolved'):
            cas_ui.submit('12', {'operation':'status'}, send=send, clock=lambda:clock[0])
        clock[0] = 11
        new = cas_ui.submit('12', {'operation':'status'}, send=send, clock=lambda:clock[0])['cas_request_id']
        self.assertEqual(cas_ui.result(old)['outcome'], 'superseded-read')
        self.assertEqual(cas_ui.result(new)['outcome'], 'pending-client')
        cas_ui.receive(old, json.dumps({'protocol':1,'ok':True,'cas_request_id':old,'client':self.client('12')}))
        self.assertTrue(cas_ui.result(old)['ok'])
        self.assertEqual(cas_ui.result(new)['outcome'], 'pending-client')
        cas_ui.receive(new, json.dumps({'protocol':1,'ok':False,'cas_request_id':new}))
        cas_ui.submit('12', {'operation':'undo'}, send=send, clock=lambda:clock[0])
        clock[0] = 100
        with self.assertRaisesRegex(ValueError,'unresolved'):
            cas_ui.submit('12', {'operation':'status'}, send=send, clock=lambda:clock[0])

    def client(self, sim_id='772674414928396571'):
        return {'scope': 'native-cas-client', 'sim': {'simId': sim_id, 'futureField': {'value': '18446744073709551615'}},
                'menu_state': cas_ui.panel('hair'), 'panel_visible': True,
                'outfit': {'outfit_type': 0, 'outfit_index': 0},
                'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                              'preset': None, 'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()]}

    def test_ordered_ascii_transport_and_client_selected_sim_identity(self):
        messages = []
        submitted = cas_ui.submit('772674414928396571', {'operation': 'panel', 'panel': 'hair'}, send=messages.append)
        self.assertFalse(submitted['ok'])
        self.assertEqual((messages[0], messages[-1]), ('ApexCAS.Begin', 'ApexCAS.End'))
        packet = ''.join(chr(int(row.rsplit('.', 1)[1])) for row in messages[1:-1])
        self.assertIn('|panel|-2134376418|', packet)
        rid = submitted['cas_request_id']
        reply = {'protocol': 1, 'ok': True, 'cas_request_id': rid,
                 'client': self.client('different')}
        with self.assertRaisesRegex(ValueError, 'another'): cas_ui.receive(rid, json.dumps(reply))
        self.assertFalse(cas_ui.result(rid)['ok'])
        reply['client']['sim']['simId'] = '772674414928396571'
        cas_ui.receive(rid, json.dumps(reply))
        self.assertTrue(cas_ui.result(rid)['ui_transition_verified'])

    def test_native_readback_rejects_wrong_panel_outfit_and_item(self):
        client = self.client('12')
        with self.assertRaisesRegex(ValueError, 'visibility'):
            cas_ui.validate_client(client, '12', {'operation':'panel', 'panel':'eyebrows'})
        with self.assertRaisesRegex(ValueError, 'outfit'):
            cas_ui.validate_client(client, '12', {'operation':'outfit', 'category':0, 'index':1})
        with self.assertRaisesRegex(ValueError, 'selected item'):
            cas_ui.validate_client(client, '12', {'operation':'select', 'panel':'hair', 'data_id':'18446744073709551615'})
        client['selected'] = [{'dataID':'18446744073709551615', 'newPackField': {'raw': 'preserved'}}]
        cas_ui.validate_client(client, '12', {'operation':'select', 'panel':'hair', 'data_id':'18446744073709551615'})

    def test_complete_catalog_coverage_empty_unknown_and_future_fields(self):
        client = self.client('12')
        client['catalogs'][0].update(supported=False, items=None)
        client['catalogs'][0].update(preset={'presetId':'18446744073709551615','newPackField':{'bytes':'exact'}},
                                    preset_query='returned-value')
        cas_ui.validate_client(client, '12', {'operation':'status'})
        client['catalogs'][0]['items'] = []
        with self.assertRaisesRegex(ValueError, 'distinguish'): cas_ui.validate_client(client, '12', {'operation':'status'})
        client['catalogs'][0]['items'] = None
        client['catalogs'].pop()
        with self.assertRaisesRegex(ValueError, 'every mapped'): cas_ui.validate_client(client, '12', {'operation':'status'})

    def test_bounded_failure_ack_resolves_without_native_mutation_claim(self):
        submitted = cas_ui.submit('12', {'operation':'status'}, send=lambda _: None)
        rid = submitted['cas_request_id']
        cas_ui.receive(rid, json.dumps({'ok': False, 'protocol': 1, 'cas_request_id': rid, 'message':'CAS response exceeds limit'}))
        self.assertEqual(cas_ui.result(rid)['cas_request_state'], 'failed')
        self.assertFalse(cas_ui.result(rid)['ui_transition_verified'])
        cas_ui.submit('12', {'operation':'status'}, send=lambda _: None)

    def test_lost_or_partial_ui_delivery_never_replays_mutation(self):
        count = [0]
        def send(name):
            count[0] += 1
            if count[0] == 4: raise OSError('delivery interrupted')
        with self.assertRaises(OSError): cas_ui.submit('12', {'operation': 'undo'}, send=send)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            cas_ui.submit('12', {'operation': 'undo'}, send=lambda _: self.fail('mutation replayed'))
        self.assertEqual(count[0], 4)

    def test_cli_polls_native_identity_once_without_clicks_or_repeat(self):
        ticks, calls = [0], []
        rid = 'a' * 32
        def request(state, action, sim=None, value=None):
            calls.append((action, value))
            if action == 'cas_ui_request': return {'cas_request_id': rid}
            return {'ok': False, 'outcome': 'pending-client'}
        args = argparse.Namespace(operation='panel', state=Path('state'), sim_id='12', panel='hair',
                                  output=None, seconds=1)
        row = execute(args, request, monotonic=lambda: ticks[0], pause=lambda n: ticks.__setitem__(0, ticks[0]+n))
        self.assertEqual(row['outcome'], 'unresolved')
        self.assertEqual(sum(action=='cas_ui_request' for action, _ in calls), 1)
        self.assertTrue(all(action in ('cas_ui_request', 'cas_ui_result') for action, _ in calls))

    def test_invalid_panel_and_missing_outfit_number_refuse_before_delivery(self):
        for req in ({'operation':'panel','panel':'execute-anything'},
                    {'operation':'select','panel':'skin_details','data_id':'12'},
                    {'operation':'select','panel':'eyes','data_id':'12'},
                    {'operation':'outfit','category':0,'index':None},
                    {'operation':'select','panel':'hair','data_id':'1|undo'},
                    {'operation':'outfit','category':0,'index':5}):
            with self.assertRaises(ValueError): cas_ui.submit('12', req, send=lambda _: self.fail('sent'))

    def test_gfx_patch_retains_opaque_scaleform_tags_and_only_replaces_abc(self):
        def swf(script, opaque):
            # RECT with one-bit coordinates, then frame rate/count.
            prefix = b'\x08\x00\x00\x18\x01\x00'
            def tag(kind, data): return struct.pack('<HI', (kind<<6)|63, len(data))+data
            body = prefix + tag(1000, opaque) + tag(82, script) + b'\x00\x00'
            return b'GFX\x0e'+struct.pack('<I',len(body)+8)+body
        original, compiled = swf(b'old ABC',b'opaque\x00\xff'), swf(b'new ABC',b'FFDec changed this')
        result = replace_abc(original, compiled)
        self.assertEqual(result[:3], b'GFX')
        entries = list(tags(unpack(result)[1]))
        self.assertEqual(entries[0][3], b'opaque\x00\xff')
        self.assertEqual(entries[1][3], b'new ABC')


if __name__ == '__main__': unittest.main()
