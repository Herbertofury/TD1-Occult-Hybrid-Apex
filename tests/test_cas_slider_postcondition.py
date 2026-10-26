"""Same-peer UI-only failed slider acknowledgments; no game/DLL or retry."""
import copy,json
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_ui,cas_controls,cas_socket
import test_cas_controls as fixture


def producer_client():
    client=fixture.CasControlsTests().client()
    client['sim'].update(householdId='22',occultLayer=0,occultType=2)
    client.update(form_strip=dict(sim_id='12',selected_owner_id='active/2',native_owner_state='bound',desired_owner_id='',gesture_pending=False),
        native_context={'rendered_form':{'query':'returned-value','value':2}},owner_pair_observation={'session':7})
    return client


def workspace():
    result=dict(visible=True,view='style',error='',context='12|active/2',outfit={'category':0,'index':0},
        preferences=dict(columns=12,color=0x00c9eb,glow=0,border=3,period=1.4,strength=1,animation='none'),
        card_preferences=dict(scale=1,gap_x=4,gap_y=4),
        slider_thumbs=dict(columns=.5,red=0,green=201/255,blue=235/255,glow=0,border=2/7,period=.1875,strength=1))
    result['slider_geometry']={name:dict(x=fraction*300,track_pixels=300,track_scale_x=1,attached=True)for name,fraction in result['slider_thumbs'].items()}
    return result


class SliderFailedPostconditionTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear();cas_ui._PEERS.clear();self.addCleanup(cas_ui._RECORDS.clear);self.addCleanup(cas_ui._PEERS.clear)
        self.peer=cas_ui.attach_client('12',clock=lambda:0)
        status=cas_ui.submit('12',{'operation':'status'},clock=lambda:0)['cas_request_id']
        cas_ui.poll_client(self.peer,clock=lambda:0)
        initial=dict(protocol=1,ok=True,cas_request_id=status,client=producer_client())
        cas_ui.receive_socket(self.peer,status,json.dumps(initial),clock=lambda:0)
        self.request={'operation':'catalog-slider','control':'columns','fraction':1/3}
        self.rid=cas_ui.submit('12',self.request,clock=lambda:0)['cas_request_id'];cas_ui.poll_client(self.peer,clock=lambda:0)
        client=producer_client();client['control']=dict(operation='catalog-slider',appearance_written=False,workspace=workspace())
        self.packet=dict(protocol=1,ok=True,cas_request_id=self.rid,operation='catalog-slider',scope='native-cas-client',mutation_started=False,client=client)

    def test_complete_same_owner_ui_only_mismatch_finishes_failed_and_consumes_exact_socket_ack(self):
        payload=json.dumps(self.packet)
        def acknowledge(peer,rid,raw):return cas_ui.receive_socket(peer,rid,raw,clock=lambda:1)['acknowledgement_accepted']
        reply,_=cas_socket.packet('ACK|'+self.peer+'|'+self.rid+'|'+payload,self.peer,attach=None,poll=None,acknowledge=acknowledge)
        self.assertEqual(reply,'ACK|'+self.rid)
        failed=cas_ui.result(self.rid);self.assertFalse(failed['ok']);self.assertFalse(failed['ui_transition_verified'])
        self.assertEqual(failed['cas_request_state'],'failed');self.assertEqual(failed['outcome'],'native-postcondition-failed')
        self.assertEqual(failed['native_acknowledgement'],self.packet);self.assertEqual(failed['native_acknowledgement_sha256'],cas_ui._baseline_hash(self.packet))
        self.assertFalse(failed['retry_submitted']);self.assertFalse(failed['mutation_started']);self.assertFalse(failed['postcondition_verified'])
        cas_ui.receive_socket(self.peer,self.rid,payload,clock=lambda:1)
        self.assertEqual(cas_ui.result(self.rid),failed)
        self.assertNotEqual(cas_ui.submit('12',{'operation':'status'},clock=lambda:1)['cas_request_id'],self.rid)
        self.assertIsNotNone(cas_ui.poll_client(self.peer,clock=lambda:1))

    def test_wrong_expected_preference_with_complete_valid_values_is_also_definite_ui_failure(self):
        self.packet['client']['control']['workspace']['preferences']['columns']=13
        response=cas_ui.receive_socket(self.peer,self.rid,json.dumps(self.packet),clock=lambda:1)
        self.assertTrue(response['acknowledgement_accepted']);self.assertFalse(response['ui_transition_verified'])
        self.assertEqual(cas_ui.result(self.rid)['cas_request_state'],'failed')

    def test_old_twip_case_now_completes_successfully_through_normal_validation(self):
        self.packet['client']['control']['workspace']['slider_thumbs']['columns']=.3331666666666667
        self.packet['client']['control']['workspace']['slider_geometry']['columns']['x']=99.95
        cas_ui.receive_socket(self.peer,self.rid,json.dumps(self.packet),clock=lambda:1)
        self.assertTrue(cas_ui.result(self.rid)['ok']);self.assertEqual(cas_ui.result(self.rid)['cas_request_state'],'completed')

    def test_foreign_partial_malformed_or_appearance_capable_packet_stays_pending(self):
        modes=('foreign-sim','wrong-owner','session','layer','outfit','missing-catalog','missing-preference','bad-preference','missing-thumb',
            'bad-thumb','missing-pixels','detached-pixels','scaled-pixels','gesture','unbound','possible-write','mutation-started','history','extra-unknown-envelope','wrong-operation','wrong-view','workspace-error','missing-lease')
        for mode in modes:
            with self.subTest(mode=mode):
                row=cas_ui._RECORDS[self.rid];row['state']='pending';row['result']=None
                row['slider_owner_lease']=dict(peer=self.peer,context=cas_ui._slider_owner_context(producer_client(),'12'))
                packet=copy.deepcopy(self.packet);client=packet['client'];w=client['control']['workspace']
                if mode=='foreign-sim':client['sim']['simId']='13'
                elif mode=='wrong-owner':client['form_strip']['selected_owner_id']='native/4';client['native_context']['rendered_form']['value']=4;w['context']='12|native/4'
                elif mode=='session':client['owner_pair_observation']['session']+=1
                elif mode=='layer':client['sim']['occultLayer']=1
                elif mode=='outfit':client['outfit']['outfit_index']=1;w['outfit']['index']=1
                elif mode=='missing-catalog':client['catalogs'].pop()
                elif mode=='missing-preference':w['preferences'].pop('period')
                elif mode=='bad-preference':w['preferences']['period']=float('nan')
                elif mode=='missing-thumb':w['slider_thumbs'].pop('blue')
                elif mode=='bad-thumb':w['slider_thumbs']['blue']=True
                elif mode=='missing-pixels':w.pop('slider_geometry')
                elif mode=='detached-pixels':w['slider_geometry']['columns']['attached']=False
                elif mode=='scaled-pixels':w['slider_geometry']['columns']['track_scale_x']=2
                elif mode=='gesture':client['form_strip']['gesture_pending']=True
                elif mode=='unbound':client['form_strip']['native_owner_state']='pending'
                elif mode=='possible-write':client['control']['appearance_written']=True
                elif mode=='mutation-started':packet['mutation_started']=True
                elif mode=='history':packet['history_before_json']='{}'
                elif mode=='extra-unknown-envelope':packet['future_transition']='unclassified'
                elif mode=='wrong-operation':packet['operation']='undo'
                elif mode=='wrong-view':w['view']='layout'
                elif mode=='workspace-error':w['error']='Unknown native scope'
                else:row.pop('slider_owner_lease')
                with self.assertRaises(ValueError):cas_ui.receive_socket(self.peer,self.rid,json.dumps(packet),clock=lambda:1)
                self.assertEqual(row['state'],'pending');self.assertEqual(cas_ui._PEERS[self.peer]['observed_at'],0)
                with self.assertRaisesRegex(ValueError,'unresolved'):cas_ui.submit('12',{'operation':'status'},clock=lambda:1)

    def test_changed_failed_packet_is_never_reclassified_or_replayed(self):
        raw=json.dumps(self.packet);cas_ui.receive_socket(self.peer,self.rid,raw,clock=lambda:1)
        original=cas_ui.result(self.rid);changed=copy.deepcopy(self.packet);changed['client']['control']['workspace']['slider_thumbs']['columns']=.4
        with self.assertRaises(ValueError):cas_ui.receive_socket(self.peer,self.rid,json.dumps(changed),clock=lambda:2)
        self.assertEqual(cas_ui.result(self.rid),original);self.assertEqual(cas_ui._PEERS[self.peer]['observed_at'],1)

    def test_appearance_and_history_operations_do_not_gain_slider_terminalization(self):
        for operation in ('physique','undo','redo','form-owner-select','pair-copy'):
            with self.subTest(operation=operation):
                row=cas_ui._RECORDS[self.rid];row['request']=dict(self.request,operation=operation);row['state']='pending';row['result']=None
                with self.assertRaises((ValueError,KeyError,TypeError)):cas_ui.receive_socket(self.peer,self.rid,json.dumps(self.packet),clock=lambda:1)
                self.assertEqual(row['state'],'pending')


if __name__=='__main__':unittest.main()
