import json
from pathlib import Path
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_socket, cas_ui


class CasSocketTests(unittest.TestCase):
    def setUp(self):
        cas_ui._PEERS.clear()
        cas_ui._RECORDS.clear()

    def test_fragmented_utf8_frame_and_excess_or_invalid_headers(self):
        left, right = socket.socketpair()
        text = 'ACK|' + 'a'*64 + '|' + 'b'*32 + '|{"name":"音楽💚"}'
        wire = cas_socket.frame(text)
        def writer():
            for byte in wire: left.sendall(bytes([byte]))
            left.close()
        thread = threading.Thread(target=writer); thread.start()
        self.assertEqual(cas_socket.read_frame(right), text)
        right.close(); thread.join()
        for header in (b'00000000', b'00131073', b'garbage!'):
            left, right = socket.socketpair(); left.sendall(header)
            with self.assertRaises(ValueError): cas_socket.read_frame(right)
            left.close(); right.close()

    def test_delivery_binds_sim_nonce_and_claims_only_once(self):
        now = [0]
        peer = cas_ui.attach_client('12', clock=lambda:now[0])
        other = cas_ui.attach_client('13', clock=lambda:now[0])
        row = cas_ui.submit('12', {'operation':'undo'}, clock=lambda:now[0])
        self.assertIsNone(cas_ui.poll_client(other, clock=lambda:now[0]))
        wire = cas_ui.poll_client(peer, clock=lambda:now[0])
        self.assertIn('|12|undo|', wire)
        self.assertIsNone(cas_ui.poll_client(peer, clock=lambda:now[0]))
        rid = row['cas_request_id']
        failure = json.dumps({'protocol':1,'ok':False,'cas_request_id':rid,'message':'No native history change'})
        with self.assertRaisesRegex(ValueError, 'claimed peer'):
            cas_ui.receive_socket(other, rid, failure)
        cas_ui.receive_socket(peer, rid, failure)
        self.assertEqual(cas_ui.result(rid)['cas_request_state'], 'failed')
        cas_ui.detach_client(peer)
        with self.assertRaisesRegex(ValueError, 'claimed peer'):
            cas_ui.receive_socket(peer, rid, failure)

    def test_lost_claim_never_replays_after_disconnect_or_to_new_peer(self):
        peer = cas_ui.attach_client('12', clock=lambda:0)
        cas_ui.submit('12', {'operation':'redo'}, clock=lambda:0)
        self.assertIsNotNone(cas_ui.poll_client(peer, clock=lambda:0))
        cas_ui.detach_client(peer)
        replacement = cas_ui.attach_client('12', clock=lambda:0)
        self.assertIsNone(cas_ui.poll_client(replacement, clock=lambda:0))
        with self.assertRaisesRegex(ValueError,'unresolved'):
            cas_ui.submit('12', {'operation':'redo'}, clock=lambda:0)

    def test_typed_router_never_accepts_unbound_ack_or_unowned_action(self):
        calls = []
        def ack(*args): calls.append(args); return True
        kwargs = dict(attach=lambda sim:'a'*64, poll=lambda peer:'wire', acknowledge=ack)
        response, peer = cas_socket.packet('HELLO|12', None, **kwargs)
        self.assertEqual(response, 'HELLO|'+'a'*64)
        self.assertEqual(cas_socket.packet('POLL|'+peer, peer, **kwargs)[0], 'wire')
        for bad in ('ACK|'+peer+'|id|{}', 'POLL|other', 'EXEC|delete', 'HELLO|12'):
            with self.assertRaises(ValueError):
                cas_socket.packet(bad, None if bad.startswith('ACK') else peer, **kwargs)
        self.assertEqual(calls, [])
        reply, _ = cas_socket.packet('ACK|'+peer+'|'+'b'*32+'|{"unknown":"raw|retained"}', peer, **kwargs)
        self.assertEqual(reply,'ACK|'+'b'*32)
        self.assertEqual(calls[0][2],'{"unknown":"raw|retained"}')

    def test_owned_ack_keeps_large_unicode_and_escaped_fields_without_second_encoding_loss(self):
        peer = cas_ui.attach_client('12', clock=lambda:0)
        rid = cas_ui.submit('12', {'operation':'status'}, clock=lambda:0)['cas_request_id']
        cas_ui.poll_client(peer, clock=lambda:0)
        value = '音' * 25000 + '\\"' * 10000
        payload = json.dumps({'protocol':1, 'ok':False, 'cas_request_id':rid, 'futureField':value}, ensure_ascii=False)
        cas_socket.frame('ACK|' + peer + '|' + rid + '|' + payload)
        self.assertGreater(len(json.dumps({'payload':payload})), 132000)
        result = cas_ui.dispatch('cas_ui_socket_ack', None, {'peer':peer, 'request_id':rid, 'payload':payload})
        self.assertTrue(result['acknowledgement_accepted'])
        self.assertEqual(cas_ui.result(rid)['futureField'], value)

    def test_claim_wait_allows_delayed_ack_without_relaxing_idle_wait(self):
        nonce = 'a' * 64
        self.assertGreater(cas_socket.response_wait('POLL|' + nonce, 'b' * 32 + '|12|undo|0|0|0|0'), 20)
        for value, reply in (('POLL|' + nonce, 'WAIT'), ('HELLO|12', 'HELLO|' + nonce),
                             ('ACK|' + nonce + '|' + 'b' * 32 + '|{}', 'ACK|' + 'b' * 32)):
            self.assertEqual(cas_socket.response_wait(value, reply), 3)

    def test_fragmented_header_and_payload_share_absolute_deadline(self):
        now = [0.0]
        class Fragmented:
            def __init__(self):
                self.data = cas_socket.frame('HELLO|12')
                self.timeouts = []
            def settimeout(self, remaining):
                self.timeouts.append(remaining)
            def recv(self, size):
                now[0] += 0.6
                block, self.data = self.data[:1], self.data[1:]
                return block
        slow = Fragmented()
        with self.assertRaises(socket.timeout):
            cas_socket.read_frame(slow, deadline=3, clock=lambda: now[0])
        self.assertTrue(slow.data)
        self.assertEqual(slow.timeouts[0], 3)
        self.assertTrue(all(left > right for left, right in zip(slow.timeouts, slow.timeouts[1:])))

    def test_validated_accept_intent_retains_claim_wait_until_native_outcome(self):
        nonce, rid = 'a' * 64, 'b' * 32
        receipt = {'protocol': 1, 'ok': True, 'cas_request_id': rid,
                   'lifecycle_stage': 'accept-intent', 'commit_submitted': False}
        wire = 'ACK|' + nonce + '|' + rid + '|' + json.dumps(receipt)
        self.assertEqual(cas_socket.response_wait(wire, 'ACK|' + rid), cas_socket.CLAIM_SECONDS)
        rejected = dict(receipt, ok=False, lifecycle_stage='accept-result', commit_attempted=True,
                        commit_accepted=False)
        wire = 'ACK|' + nonce + '|' + rid + '|' + json.dumps(rejected)
        self.assertEqual(cas_socket.response_wait(wire, 'ACK|' + rid), cas_socket.IDLE_SECONDS)

    def test_wait_extension_requires_exact_accepted_intent_metadata(self):
        nonce, rid = 'a' * 64, 'b' * 32
        receipt = {'protocol': 1, 'ok': True, 'cas_request_id': rid,
                   'lifecycle_stage': 'accept-intent', 'commit_submitted': False}
        cases = [dict(receipt, protocol=True), dict(receipt, ok=1),
                 dict(receipt, cas_request_id='c' * 32), dict(receipt, commit_submitted=0),
                 dict(receipt, lifecycle_stage='completed'), [], 'bad JSON']
        for value in cases:
            payload = value if value == 'bad JSON' else json.dumps(value)
            wire = 'ACK|' + nonce + '|' + rid + '|' + payload
            with self.subTest(value=value):
                self.assertEqual(cas_socket.response_wait(wire, 'ACK|' + rid), cas_socket.IDLE_SECONDS)
        wire = 'ACK|' + nonce + '|' + rid + '|' + json.dumps(receipt)
        self.assertEqual(cas_socket.response_wait(wire, 'ACK|' + 'c' * 32), cas_socket.IDLE_SECONDS)

    def test_partial_payload_does_not_get_new_deadline_after_header(self):
        now = [0.0]
        class Parts:
            def __init__(self): self.parts = [b'00000008', b'HELLO|', b'12']; self.timeouts = []
            def settimeout(self, remaining): self.timeouts.append(remaining)
            def recv(self, size):
                now[0] += 1.1
                return self.parts.pop(0)
        connection = Parts()
        self.assertEqual(cas_socket.read_frame(connection, deadline=4, clock=lambda: now[0]), 'HELLO|12')
        self.assertEqual(len(connection.timeouts), 3)
        self.assertAlmostEqual(connection.timeouts[1], 2.9)
        self.assertAlmostEqual(connection.timeouts[2], 1.8)


if __name__ == '__main__': unittest.main()
