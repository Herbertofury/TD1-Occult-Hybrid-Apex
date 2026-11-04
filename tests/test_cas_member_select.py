"""Household member transfers acknowledge the actual destination, never a click."""
import copy
import json
import os
import unittest
from types import SimpleNamespace as Obj
from test_cas_form_select import client, SIM, HH, GUID
from apex_core import cas_ui
from cas_client import execute

TARGET = '9223372036854775816'


def request():
    return dict(operation='member-select',household_id=HH,expected_layer=0,
                native_session=1,target_sim_id=TARGET)


def household(selected=SIM):
    value=client(0); value['native_context']['edit_mode']['value']=0
    obs=value['owner_pair_observation']; selector=obs['selector_feed']
    for feed_name in ('raw_feed','retained'):
        feed=selector[feed_name]; second=copy.deepcopy(feed['pairs'][0]); second['index']=1
        for side in ('base','alternate'):
            second[side].update(sim_id=TARGET,index=1,selected=False)
        feed['pairs'].append(second)
    selector['raw_feed'].update(base_row_count=2,alternate_row_count=2)
    retained=selector['retained']; index=0 if selected==SIM else 1
    for pair in retained['pairs']:
        pair['base']['selected']=pair['index']==index
        pair['alternate']['selected']=False
    retained.update(selected_index=index,selected_sim_id=selected)
    obs['selected']['sim_id']=selected; value['sim']['simId']=selected
    return value


class MemberSelectionTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear();cas_ui._PEERS.clear();cas_ui._OWNER_BASELINES.clear()
        self.now=10; self.sims={}
        for sid in (SIM,TARGET):
            sim=Obj(id=int(sid),household_id=int(HH));sim.occult_tracker=Obj(sim_info=sim,forms={64:Obj(id=int(sid)+100)})
            self.sims[sid]=sim
        self.backend=Obj(_get_sim_info_by_id=lambda sid:self.sims.get(str(sid)),_form_map=lambda t:t.forms,
            services=Obj(get_persistence_service=lambda:Obj(get_save_slot_proto_guid=lambda:int(GUID))))
        for sim in self.sims.values():cas_ui.capture_original_owner(self.backend,sim)
        self.peer=cas_ui.attach_client(SIM,clock=lambda:self.now)
        rid=cas_ui.submit(SIM,{'operation':'status'},clock=lambda:self.now)['cas_request_id']
        cas_ui.poll_client(self.peer,clock=lambda:self.now)
        cas_ui.receive_socket(self.peer,rid,json.dumps(dict(protocol=1,ok=True,cas_request_id=rid,client=household())),clock=lambda:self.now,backend=self.backend)

    def submit(self):
        return cas_ui.submit(SIM,request(),clock=lambda:self.now,backend=self.backend)['cas_request_id']

    def acknowledgement(self,rid):
        return dict(protocol=1,ok=True,cas_request_id=rid,client=household(TARGET),member_selection=dict(
            native_session=1,household_id=HH,source_sim_id=SIM,target_sim_id=TARGET,source_index=0,target_index=1,
            target_form_flags=1,selection_verified=True,appearance_persistence_verified=False))

    def receive(self,rid,reply):
        cas_ui.poll_client(self.peer,clock=lambda:self.now)
        cas_ui.receive_socket(self.peer,rid,json.dumps(reply),clock=lambda:self.now,backend=self.backend)

    def test_actual_destination_ack_completes_once_on_original_claim(self):
        rid=self.submit(); reply=self.acknowledgement(rid);self.receive(rid,reply)
        result=cas_ui.result(rid)
        self.assertTrue(result['ok']);self.assertEqual(result['outcome'],'member-selected')
        self.assertEqual(result['client']['sim']['simId'],TARGET)
        self.assertFalse(result['appearance_persistence_verified'])
        self.assertIsNone(cas_ui.poll_client(self.peer,clock=lambda:self.now))

    def test_wrong_sim_ack_is_retained_unresolved_and_blocks_replay(self):
        rid=self.submit(); reply=self.acknowledgement(rid);reply['client']=household(SIM)
        with self.assertRaises(ValueError):self.receive(rid,reply)
        self.assertEqual(cas_ui._RECORDS[rid]['state'],'pending')
        self.assertIn('rejected_acknowledgement',cas_ui._RECORDS[rid])
        with self.assertRaises(ValueError):self.submit()

    def test_changed_roster_or_receipt_refuses_complete_success(self):
        for kind in ('roster','receipt','session'):
            with self.subTest(kind=kind):
                self.setUp();rid=self.submit();reply=self.acknowledgement(rid)
                if kind=='receipt':reply['member_selection']['target_index']=0
                elif kind=='session':reply['client']['owner_pair_observation']['session']=2
                else:
                    for feed in ('raw_feed','retained'):
                        for side in ('base','alternate'):
                            reply['client']['owner_pair_observation']['selector_feed'][feed]['pairs'][0][side]['all_occult_types']=7
                with self.assertRaises(ValueError):self.receive(rid,reply)
                self.assertEqual(cas_ui._RECORDS[rid]['state'],'pending')

    def test_absent_or_uncaptured_target_refuses_before_delivery(self):
        for kind in ('absent','uncaptured'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind=='uncaptured':
                    for key in list(cas_ui._OWNER_BASELINES):
                        if key[2]==TARGET:del cas_ui._OWNER_BASELINES[key]
                else:
                    prior=next(reversed(cas_ui._RECORDS.values()))
                    for feed in ('raw_feed','retained'):
                        for side in ('base','alternate'):
                            prior['result']['client']['owner_pair_observation']['selector_feed'][feed]['pairs'][1][side]['sim_id']='42'
                with self.assertRaises(ValueError):self.submit()
                self.assertEqual(len(cas_ui._RECORDS),1)

    def test_single_sim_editor_and_invalid_request_are_rejected(self):
        value=household();value['native_context']['edit_mode']['value']=7
        with self.assertRaises(ValueError):cas_ui.member_selection_binding(value,SIM,request())
        for key,bad in (('target_sim_id','01'),('native_session',True),('expected_layer',2),('household_id','0')):
            value=request();value[key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):cas_ui.envelope(SIM,value)

    def test_filtered_alternates_do_not_block_exact_household_navigation(self):
        value=household();selector=value['owner_pair_observation']['selector_feed']
        selector['retained']['complete']=False
        for pair in selector['retained']['pairs']:pair['alternate']=None
        before=copy.deepcopy(value)
        bound=cas_ui.member_selection_binding(value,SIM,request())
        self.assertEqual(bound['target_index'],1)
        self.assertEqual(value,before)  # No filtered row was filled or invented.
        # This does not authorize the native pair's stronger layer selection.
        with self.assertRaises(ValueError):cas_ui.form_selection_binding(value,SIM,dict(
            operation='layer-select',household_id=HH,expected_layer=0,target_layer=1,native_session=1))

    def test_filtered_alternates_still_require_all_retained_base_identities(self):
        for damage in ('base-id','base-index','raw-id','duplicate','retained-alternate','household','selected-layer'):
            with self.subTest(damage=damage):
                value=household();obs=value['owner_pair_observation'];selector=obs['selector_feed']
                selector['retained']['complete']=False
                for pair in selector['retained']['pairs']:pair['alternate']=None
                if damage=='base-id':selector['retained']['pairs'][1]['base']['sim_id']='42'
                elif damage=='base-index':selector['retained']['pairs'][1]['base']['index']=0
                elif damage=='raw-id':selector['raw_feed']['pairs'][1]['alternate']['sim_id']='42'
                elif damage=='duplicate':
                    for feed in ('raw_feed','retained'):
                        for side in ('base','alternate'):
                            row=selector[feed]['pairs'][1][side]
                            if row is not None:row['sim_id']=SIM
                elif damage=='retained-alternate':
                    selector['retained']['pairs'][1]['alternate']=copy.deepcopy(selector['raw_feed']['pairs'][1]['alternate'])
                    selector['retained']['pairs'][1]['alternate']['occult_type']=2
                elif damage=='household':value['sim']['householdId']='42'
                else:selector['retained']['selected_layer']=1
                with self.assertRaises(ValueError):cas_ui.member_selection_binding(value,SIM,request())

    def test_destination_can_resume_its_existing_alternate_layer(self):
        value=household(TARGET);obs=value['owner_pair_observation'];selector=obs['selector_feed']
        value['sim'].update(occultLayer=1,occultType=64)
        obs['selected'].update(occult_layer=1,occult_type=64)
        selector['retained'].update(selected_layer=1,complete=False)
        for pair in selector['retained']['pairs']:pair['alternate']=None
        bound=cas_ui.member_selection_binding(value,SIM,request(),resulting=True)
        self.assertEqual(bound['target_index'],1)
        self.assertEqual(bound['source_index'],1)

    def test_mutation_failure_remains_unresolved(self):
        rid=self.submit();self.receive(rid,dict(protocol=1,ok=False,cas_request_id=rid,mutation_started=True,message='Native destination unavailable'))
        self.assertEqual(cas_ui._RECORDS[rid]['state'],'form-select-unresolved')
        with self.assertRaises(ValueError):self.submit()



class MemberPeerHandoffTests(unittest.TestCase):
    def run_command(self, lost=False, wrong=False, transient=False):
        now=[0.0]; calls=[]; queued={}; counter=[0]; diagnostic=[0]
        target_reads=[0]
        def transport(state,action,sim_id=None,value=None):
            calls.append((action,sim_id,value))
            if action=='cas_ui_request':
                counter[0]+=1;rid=format(counter[0],'032x');queued[rid]=(sim_id,json.loads(value)['operation'])
                return dict(ok=False,outcome='pending-client',cas_request_id=rid)
            if action=='cas_ui_result':
                selected,op=queued[value]
                if op=='member-select':
                    return dict(protocol=1,ok=True,cas_request_id=value,client=household(TARGET),member_selection=dict(
                        native_session=1,household_id=HH,source_sim_id=SIM,target_sim_id=TARGET,source_index=0,target_index=1,
                        target_form_flags=1,selection_verified=True,appearance_persistence_verified=False))
                client=household(SIM if wrong else selected)
                client['form_strip']=dict(sim_id=client['sim']['simId'],selected_owner_id='native/1',
                    native_owner_state='bound',desired_owner_id='',gesture_pending=False)
                if selected==TARGET:
                    target_reads[0]+=1
                    if transient and target_reads[0]==1:
                        client['form_strip'].update(selected_owner_id='',native_owner_state='')
                return dict(protocol=1,ok=True,cas_request_id=value,client=client)
            if action=='cas_ui_diagnostics':
                diagnostic[0]+=1
                return dict(ok=True,native_peers=[] if lost or diagnostic[0]<3 else [dict(sim_id=TARGET,age_seconds=.1)])
            raise AssertionError(action)
        args=Obj(operation='member-select',state='unused-test-state.json',sim_id=SIM,seconds=2,output=None,
            household_id=HH,expected_layer=0,native_session=1,target_sim_id=TARGET)
        result=execute(args,transport,monotonic=lambda:now[0],pause=lambda seconds:now.__setitem__(0,now[0]+seconds))
        return result,calls
    def test_success_waits_for_rebound_and_fresh_actual_destination(self):
        result,calls=self.run_command()
        self.assertTrue(result['peer_rebound_verified']);self.assertTrue(result['next_native_commands_ready'])
        mutations=[c for c in calls if c[0]=='cas_ui_request' and json.loads(c[2])['operation']=='member-select']
        self.assertEqual(len(mutations),1)
        self.assertEqual(result['destination_status']['client']['sim']['simId'],TARGET)
    def test_missing_new_peer_retains_completed_selection_without_replaying(self):
        result,calls=self.run_command(lost=True)
        self.assertFalse(result['ok']);self.assertEqual(result['outcome'],'member-selected-peer-unresolved')
        self.assertTrue(result['member_selection']['selection_verified'])
        self.assertEqual(sum(c[0]=='cas_ui_request' and json.loads(c[2])['operation']=='member-select' for c in calls),1)
    def test_changed_destination_refuses_before_any_next_edit(self):
        with self.assertRaisesRegex(ValueError,'destination changed'):self.run_command(wrong=True)
    def test_initial_peer_without_bound_owner_is_observed_again_without_reselecting(self):
        result,calls=self.run_command(transient=True)
        self.assertTrue(result['next_native_commands_ready'])
        self.assertEqual(result['destination_status']['client']['form_strip']['native_owner_state'],'bound')
        self.assertEqual(sum(c[0]=='cas_ui_request' and json.loads(c[2])['operation']=='member-select' for c in calls),1)
        self.assertEqual(sum(c[0]=='cas_ui_request' and c[1]==TARGET and json.loads(c[2])['operation']=='status' for c in calls),2)
