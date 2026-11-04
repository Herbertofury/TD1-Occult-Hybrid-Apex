"""A failed value readback must not be promoted to success or sever CAS."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'Source'), str(Path(__file__).resolve().parents[1] / 'tools')]
from apex_core import cas_ui, cas_socket
import test_cas_controls as controls_fixture


class PostconditionTransportTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear(); cas_ui._PEERS.clear()
        self.addCleanup(cas_ui._RECORDS.clear); self.addCleanup(cas_ui._PEERS.clear)
        self.peer = cas_ui.attach_client('12', clock=lambda: 0)
        self.rid = cas_ui.submit('12', {'operation': 'swatch', 'swatch_type': 3,
            'data_id': '123', 'color_index': 0}, clock=lambda: 0)['cas_request_id']
        cas_ui.poll_client(self.peer, clock=lambda: 0)
        client = controls_fixture.CasControlsTests().client()
        client['control'] = {'operation': 'swatch', 'selected': '124'}
        self.data = {'protocol': 1, 'ok': True, 'cas_request_id': self.rid,
                     'operation': 'swatch', 'mutation_started': True, 'client': client}

    def test_complete_mismatch_ack_is_consumed_failed_receipt_retained_and_status_can_continue(self):
        raw = json.dumps(self.data)
        def acknowledge(peer, rid, payload):
            return cas_ui.receive_socket(peer, rid, payload, clock=lambda: 1)['acknowledgement_accepted']
        reply, peer = cas_socket.packet('ACK|' + self.peer + '|' + self.rid + '|' + raw,
            self.peer, attach=None, poll=None, acknowledge=acknowledge)
        self.assertEqual(reply, 'ACK|' + self.rid)
        failed = cas_ui.result(self.rid)
        self.assertFalse(failed['ok']); self.assertFalse(failed['ui_transition_verified'])
        self.assertEqual(failed['outcome'], 'native-postcondition-failed')
        self.assertEqual(failed['native_acknowledgement'], self.data)
        self.assertFalse(failed['retry_submitted'])
        self.assertIn(self.peer, cas_ui._PEERS)
        result = cas_ui.submit('12', {'operation': 'status'}, clock=lambda: 1)
        self.assertNotEqual(result['cas_request_id'], self.rid)
        self.assertIsNotNone(cas_ui.poll_client(self.peer, clock=lambda: 1))

    def test_malformed_or_foreign_ack_keeps_request_unresolved_and_raises(self):
        for mode in ('foreign', 'incomplete', 'bad-target'):
            data = copy.deepcopy(self.data)
            if mode == 'foreign': data['client']['sim']['simId'] = '13'
            if mode == 'incomplete': data['client']['catalogs'].pop()
            if mode == 'bad-target': data['client']['control']['selected'] = 'not-an-id'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                cas_ui.receive_socket(self.peer, self.rid, json.dumps(data), clock=lambda: 1)
            self.assertEqual(cas_ui._RECORDS[self.rid]['state'], 'pending')

    def test_duplicate_identical_failed_packet_is_idempotent_but_changed_packet_is_refused(self):
        raw = json.dumps(self.data)
        for _ in range(2):
            response = cas_ui.receive_socket(self.peer, self.rid, raw, clock=lambda: 1)
            self.assertTrue(response['acknowledgement_accepted']); self.assertFalse(response['ui_transition_verified'])
        data = copy.deepcopy(self.data); data['client']['control']['selected'] = '125'
        with self.assertRaises(ValueError): cas_ui.receive_socket(self.peer, self.rid, json.dumps(data), clock=lambda: 1)


if __name__ == '__main__': unittest.main()
