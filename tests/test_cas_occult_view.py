import copy,json,sys
from pathlib import Path
from types import SimpleNamespace as Obj
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_controls,cas_ui
import test_cas_form_select as fixture


def client(target=64,mask=127):
    row=fixture.client(layer=1,alternate_form=target)
    row['sim']['allOccultTypes']=mask
    obs=row['owner_pair_observation'];obs['selected']['all_occult_types']=mask
    for source in ('raw_feed','retained'):
        for pair in obs['selector_feed'][source]['pairs']:
            pair['base']['all_occult_types']=pair['alternate']['all_occult_types']=mask
    return row


class OccultViewTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear();cas_ui._PEERS.clear();cas_ui._OWNER_BASELINES.clear()
        self.sim=Obj(id=int(fixture.SIM),household_id=int(fixture.HH))
        tracker=Obj(sim_info=self.sim,forms={1:Obj(id=10),4:Obj(id=11),64:Obj(id=12)})
        self.sim.occult_tracker=tracker
        self.backend=Obj(_get_sim_info_by_id=lambda _:self.sim,_form_map=lambda t:t.forms,
            services=Obj(get_persistence_service=lambda:Obj(get_save_slot_proto_guid=lambda:int(fixture.GUID))))
        cas_ui.capture_original_owner(self.backend,self.sim)
        self.peer=cas_ui.attach_client(fixture.SIM,clock=lambda:10)

    def request(self):
        return dict(operation='occult-view',occult_type=4,expected_all_occults=127,
            household_id=fixture.HH,native_session=1,expected_layer=1)

    def observe(self):
        rid=cas_ui.submit(fixture.SIM,{'operation':'status'},clock=lambda:10)['cas_request_id']
        cas_ui.poll_client(self.peer,clock=lambda:10)
        cas_ui.receive_socket(self.peer,rid,json.dumps(dict(protocol=1,ok=True,cas_request_id=rid,client=client())),clock=lambda:10,backend=self.backend)

    def test_wire_never_allows_human_conversion_unowned_states_or_stale_mask_shapes(self):
        _,wire=cas_ui.envelope(fixture.SIM,self.request())
        self.assertEqual(wire.split('|')[3:6],['1','127','4'])
        for change in (dict(occult_type=1),dict(occult_type=3),dict(occult_type=True),
                       dict(expected_all_occults=65),dict(expected_layer=True),dict(native_session=0)):
            request=self.request();request.update(change)
            with self.assertRaises(ValueError):cas_ui.envelope(fixture.SIM,request)

    def test_view_requires_a_fresh_owned_status_and_actual_original_target(self):
        with self.assertRaises(ValueError):cas_ui.submit(fixture.SIM,self.request(),clock=lambda:10,backend=self.backend)
        self.observe()
        value=self.request();value['occult_type']=8
        with self.assertRaisesRegex(ValueError,'captured owner'):
            cas_ui.submit(fixture.SIM,value,clock=lambda:10,backend=self.backend)

    def test_same_id_ack_is_idempotent_and_does_not_claim_appearance_persistence(self):
        self.observe()
        rid=cas_ui.submit(fixture.SIM,self.request(),clock=lambda:10,backend=self.backend)['cas_request_id']
        cas_ui.poll_client(self.peer,clock=lambda:10)
        after=client(4);after['control']=dict(operation='occult-view',occults=[{'occult_type':i} for i in (2,4,8,16,32,64)])
        payload=json.dumps(dict(protocol=1,ok=True,cas_request_id=rid,client=after))
        for _ in range(2):
            self.assertTrue(cas_ui.receive_socket(self.peer,rid,payload,clock=lambda:10,backend=self.backend)['ok'])
        result=cas_ui.result(rid)
        self.assertTrue(result['selection_only_verified'])
        self.assertFalse(result['appearance_persistence_verified'])

    def test_lost_membership_is_not_a_success_and_preserves_the_original_native_packet(self):
        self.observe()
        rid=cas_ui.submit(fixture.SIM,self.request(),clock=lambda:10,backend=self.backend)['cas_request_id']
        cas_ui.poll_client(self.peer,clock=lambda:10)
        after=client(4,5);after['control']=dict(operation='occult-view',occults=[{'occult_type':4}])
        payload=json.dumps(dict(protocol=1,ok=True,cas_request_id=rid,client=after,mutation_started=True))
        with self.assertRaises(cas_controls.PostconditionMismatch):
            cas_ui.receive_socket(self.peer,rid,payload,clock=lambda:10,backend=self.backend)
        result=cas_ui.result(rid)
        self.assertFalse(result['ok'])
        self.assertEqual(cas_ui._RECORDS[rid]['state'],'pending')
        self.assertEqual(cas_ui._RECORDS[rid]['rejected_acknowledgement'],json.loads(payload))

    def test_read_catalog_retains_future_native_registered_bits_without_fabricating_membership(self):
        data=client();data['control']=dict(operation='occults',occults=[{'occult_type':128,'future_name':'new native kind'}])
        cas_controls.validate(data,dict(operation='occults'))
        data['control']['occults'].append({'occult_type':128})
        with self.assertRaises(ValueError):cas_controls.validate(data,dict(operation='occults'))
