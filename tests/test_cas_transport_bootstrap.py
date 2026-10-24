import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_ui


class BootstrapPriorityTests(unittest.TestCase):
    def setUp(self):
        cas_ui._PEERS.clear();cas_ui._RECORDS.clear()
        self.peer=cas_ui.attach_client('12');self.backend=object()
        self.rid=cas_ui.submit('12',{'operation':'undo'})['cas_request_id']

    def test_initial_catalog_and_state_precede_command_without_claiming_or_replaying_it(self):
        peer=cas_ui._PEERS[self.peer]
        def metadata(token,backend):
            self.assertEqual(token,self.peer);self.assertIs(backend,self.backend)
            if 'owner_catalog' not in peer:
                peer.update(owner_catalog=['human'],owner_catalog_offset=1)
                return 'OWNERS|0|1|human'
            peer['owner_state_identity']=('OWNERSTATE|native/1|1|0|bound',1)
            return peer['owner_state_identity'][0]
        with patch.object(cas_ui,'owner_metadata',side_effect=metadata) as read:
            self.assertTrue(cas_ui.poll_transport(self.peer,self.backend).startswith('OWNERS|'))
            self.assertEqual(cas_ui._RECORDS[self.rid]['delivery'],'queued')
            self.assertTrue(cas_ui.poll_transport(self.peer,self.backend).startswith('OWNERSTATE|'))
            self.assertEqual(cas_ui._RECORDS[self.rid]['delivery'],'queued')
            self.assertIn(self.rid,cas_ui.poll_transport(self.peer,self.backend))
            self.assertEqual(cas_ui._RECORDS[self.rid]['delivery'],'claimed')
            self.assertEqual(read.call_count,2)
            cas_ui.poll_transport(self.peer,self.backend)
            self.assertEqual(cas_ui._RECORDS[self.rid]['delivery'],'claimed')

    def test_unavailable_metadata_falls_back_once_and_does_not_stall_or_duplicate_a_claim(self):
        with patch.object(cas_ui,'owner_metadata',return_value=None) as read:
            self.assertIn(self.rid,cas_ui.poll_transport(self.peer,self.backend))
            read.assert_called_once_with(self.peer,self.backend)
            self.assertIsNone(cas_ui.poll_transport(self.peer,self.backend))

    def test_no_backend_retains_the_original_transport_path(self):
        with patch.object(cas_ui,'owner_metadata') as read:
            self.assertIn(self.rid,cas_ui.poll_transport(self.peer))
            read.assert_not_called()

    def test_later_generation_updates_cannot_starve_new_commands(self):
        cas_ui._PEERS[self.peer].update(owner_catalog=['human'],owner_catalog_offset=1,
                                       owner_state_identity=('OWNERSTATE|native/1|1|0|bound',1))
        with patch.object(cas_ui,'owner_metadata',return_value='OWNERSTATE|native/2|2|0|bound') as read:
            self.assertIn(self.rid,cas_ui.poll_transport(self.peer,self.backend))
            read.assert_not_called()

    def test_invalid_metadata_does_not_claim_work_and_wrong_peer_never_claims_the_sim(self):
        with patch.object(cas_ui,'owner_metadata',side_effect=ValueError('invalid owner descriptor')):
            with self.assertRaisesRegex(ValueError,'invalid owner'):
                cas_ui.poll_transport(self.peer,self.backend)
        self.assertEqual(cas_ui._RECORDS[self.rid]['delivery'],'queued')
        other=cas_ui.attach_client('13')
        with patch.object(cas_ui,'owner_metadata',return_value=None):
            self.assertIsNone(cas_ui.poll_transport(other,self.backend))
        cas_ui.detach_client(self.peer)
        with self.assertRaisesRegex(ValueError,'not bound'):cas_ui.poll_transport(self.peer,self.backend)


if __name__=='__main__':unittest.main()
