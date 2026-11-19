import copy
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui, cas_socket


class StripMembershipTests(unittest.TestCase):
    def setUp(self):
        self.peers = copy.copy(cas_ui._PEERS)
        self.baselines = copy.copy(cas_ui._OWNER_BASELINES)
        cas_ui._PEERS.clear(); cas_ui._OWNER_BASELINES.clear()
        self.peer = cas_ui.attach_client('12')
        self.key = (os.getpid(), '24', '12')
        baseline = dict(complete=True, runtime_pid=os.getpid(), save_guid='24',
                        original_sim_id='12', capture_id='a'*32)
        self.stored = dict(baseline=baseline, baseline_sha256=cas_ui._baseline_hash(baseline),
                           cache_membership=dict(capture_id='a'*32, owned_mask=127))
        cas_ui._OWNER_BASELINES[self.key] = self.stored

    def tearDown(self):
        cas_ui._PEERS.clear(); cas_ui._PEERS.update(self.peers)
        cas_ui._OWNER_BASELINES.clear(); cas_ui._OWNER_BASELINES.update(self.baselines)

    def test_detached_display_reads_only_sealed_primitive_metadata(self):
        records_before = dict(cas_ui._RECORDS)
        class Disposed:
            def __getattribute__(self, name):
                raise AssertionError('CAS display dereferenced a disposed Live producer')
        for name in ('sim', 'tracker', 'wrappers', 'form_map'):
            self.stored[name] = Disposed()
        self.assertEqual(cas_ui.client_owned_mask(self.peer), 127)
        self.assertEqual(dict(cas_ui._RECORDS), records_before)

    def test_replacement_peer_cannot_read_other_sim_or_unbound_token(self):
        other = cas_ui.attach_client('13')
        self.assertEqual(cas_ui.client_owned_mask(other), 0)
        cas_ui.detach_client(self.peer)
        with self.assertRaises(ValueError): cas_ui.client_owned_mask(self.peer)

    def test_ambiguous_save_or_tampered_capture_is_hidden(self):
        cas_ui._OWNER_BASELINES[(os.getpid(), '25', '12')] = copy.deepcopy(self.stored)
        self.assertEqual(cas_ui.client_owned_mask(self.peer), 0)
        del cas_ui._OWNER_BASELINES[(os.getpid(), '25', '12')]
        self.stored['baseline']['capture_id'] = 'b'*32
        self.assertEqual(cas_ui.client_owned_mask(self.peer), 0)

    def test_membership_display_never_accepts_unknown_bits_or_a_foreign_capture(self):
        for mask in (True, -1, 128, 255, 126, '127', None):
            self.stored['cache_membership']['owned_mask'] = mask
            self.assertEqual(cas_ui.client_owned_mask(self.peer), 0)
        self.stored['cache_membership'] = dict(capture_id='b'*32, owned_mask=127)
        self.assertEqual(cas_ui.client_owned_mask(self.peer), 0)

    def test_only_the_hello_response_carries_read_only_membership(self):
        args = dict(attach=lambda sim: self.peer, poll=lambda token: None,
                    acknowledge=lambda *args: True, owner_mask=cas_ui.client_owned_mask)
        response, peer = cas_socket.packet('HELLO|12', None, **args)
        self.assertEqual(response, 'HELLO|' + self.peer + '|127')
        self.assertEqual(cas_socket.packet('POLL|' + peer, peer, **args)[0], 'WAIT')
        with self.assertRaises(ValueError):
            cas_socket.packet('OWNER|127', peer, **args)
        args['owner_mask'] = lambda token: True
        with self.assertRaises(ValueError): cas_socket.packet('HELLO|12', None, **args)


if __name__ == '__main__': unittest.main()
