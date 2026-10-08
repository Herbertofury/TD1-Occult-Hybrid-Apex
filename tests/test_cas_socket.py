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


if __name__ == '__main__': unittest.main()
