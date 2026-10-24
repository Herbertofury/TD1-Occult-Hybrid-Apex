import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from cas_return import primary_navigation
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core.cas_ui import envelope


class OwnerReturnNavigationTests(unittest.TestCase):
    def client(self):
        return dict(sim=dict(simId='44',allOccultTypes=127,occultLayer=1),owner_pair_observation=dict(session=9),
                    native_context=dict(rendered_form=dict(query='returned-value',value=64)),
                    form_strip=dict(sim_id='44',native_owner_state='bound',cross_kind_navigation=True,
                                    selected_owner_id='active/64',owned_mask=127,
                                    life_states=[dict(family='human',variants=[dict(owner_id='native/1')])]))

    def view(self, human='native/1'):
        return dict(ok=True,scope='native-form-view-status',available=True,state='bound',pid=123,
                    sim_id='44',owner_id='active/64',human_owner_id=human,native_kind=64,generation=7,layer=1,
                    portrait_pair=dict(base_owner_id=human,base_kind=1,alternate_owner_id='active/64',alternate_kind=64))

    def navigate(self, client):
        return primary_navigation(client,'44','55','a'*32,self.view(),123)

    def test_bound_fairy_uses_shared_human_owner_without_legacy_pair_delivery(self):
        client=self.client();client['owner_pair_observation'].update(complete=False,delivered=False,pairs=[])
        before=copy.deepcopy(client)
        request=self.navigate(client)
        self.assertEqual(request,dict(operation='form-owner-select',owner_id='native/1',
            native_kind=1,owned_mask=127,household_id='55',expected_layer=1,native_session=9,test_token='a'*32))
        request_id,wire=envelope('44',request)
        self.assertEqual(len(request_id),32);self.assertIn('|form-owner-select|',wire)
        self.assertEqual(client,before)

    def test_original_human_owner_can_be_active_instead_of_stored(self):
        client=self.client();client['form_strip']['life_states'][0]['variants'][0]['owner_id']='active/1'
        self.assertEqual(primary_navigation(client,'44','55','a'*32,self.view('active/1'),123)['owner_id'],'active/1')

    def test_missing_duplicate_wrong_sim_or_nonhuman_owner_refuses_without_falling_back(self):
        for damage in ('missing','duplicate','werewolf','wrong-sim','mask','not-navigation'):
            client=self.client();strip=client['form_strip']
            if damage=='missing':strip['life_states']=[]
            elif damage=='duplicate':strip['life_states']*=2
            elif damage=='werewolf':strip['life_states'][0]['variants'][0]['owner_id']='active/32'
            elif damage=='wrong-sim':strip['sim_id']='45'
            elif damage=='mask':strip['owned_mask']=5
            else:strip['cross_kind_navigation']=False
            with self.subTest(damage=damage),self.assertRaises(ValueError):self.navigate(client)

    def test_legacy_editor_keeps_its_existing_pair_contract(self):
        client=self.client();client.pop('form_strip')
        self.assertEqual(primary_navigation(client,'44','55'),dict(operation='layer-select',household_id='55',expected_layer=1,target_layer=0,native_session=9))

    def test_invalid_session_refuses_both_paths(self):
        for value in (None,0,True,'9'):
            client=self.client();client['owner_pair_observation']['session']=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.navigate(client)

    def test_missing_profile_token_refuses_the_native_owner_operation(self):
        with self.assertRaisesRegex(ValueError,'token'):primary_navigation(self.client(),'44','55')

    def alien_disguise(self):
        client=self.client();client['form_strip']['selected_owner_id']='native/1'
        client['form_strip']['life_states'].append(dict(family='alien',variants=[dict(owner_id='active/2')]))
        client['native_context']['rendered_form']['value']=1
        view=self.view();view.update(owner_id='native/1',native_kind=1,
            portrait_pair=dict(base_owner_id='active/2',base_kind=2,alternate_owner_id='native/1',alternate_kind=1))
        return client,view

    def test_alien_disguise_returns_to_its_alien_base_preserving_eas_orientation(self):
        client,view=self.alien_disguise();before=copy.deepcopy((client,view))
        request=primary_navigation(client,'44','55','a'*32,view,123)
        self.assertEqual((request['owner_id'],request['native_kind']),('active/2',2))
        envelope('44',request)
        self.assertEqual((client,view),before)

    def test_stale_missing_or_unbound_native_view_cannot_select_or_accept(self):
        changes=[{'pid':124},{'sim_id':'45'},{'owner_id':'native/4'},{'human_owner_id':'active/1'},
                 {'available':False},{'state':'unbound'},{'layer':0},{'generation':True},
                 {'generation':0},{'native_kind':1},{'scope':'another-scope'},{'ok':False}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):
                primary_navigation(self.client(),'44','55','a'*32,dict(self.view(),**change),123)
        with self.assertRaises(ValueError):primary_navigation(self.client(),'44','55','a'*32)

    def test_unknown_or_unowned_alien_pair_refuses_without_legacy_fallback(self):
        for damage in ('missing','duplicate','another-owner','another-kind','other-alternate','boolean-kind'):
            client,view=self.alien_disguise()
            if damage=='missing':client['form_strip']['life_states'].pop()
            elif damage=='duplicate':client['form_strip']['life_states'].append(copy.deepcopy(client['form_strip']['life_states'][-1]))
            elif damage=='another-owner':view['portrait_pair']['base_owner_id']='native/2'
            elif damage=='another-kind':view['portrait_pair']['base_kind']=4
            elif damage=='other-alternate':view['portrait_pair']['alternate_owner_id']='native/4'
            else:view['native_kind']=True
            with self.subTest(damage=damage),self.assertRaises(ValueError):
                primary_navigation(client,'44','55','a'*32,view,123)

    def test_distinct_named_human_renderer_still_returns_to_the_shared_human(self):
        client=self.client();client['form_strip']['selected_owner_id']='ghost/ghost_ghost'
        client['native_context']['rendered_form']['value']=1
        view=self.view();view.update(owner_id='ghost/ghost_ghost',native_kind=1,
            portrait_pair=dict(base_owner_id='native/1',base_kind=1,alternate_owner_id='ghost/ghost_ghost',alternate_kind=1))
        request=primary_navigation(client,'44','55','a'*32,view,123)
        self.assertEqual((request['owner_id'],request['native_kind']),('native/1',1))


class OwnerReturnWorkflowTests(unittest.TestCase):
    def test_observer_reads_native_pair_before_submitting_alien_primary_navigation(self):
        import json
        from test_cas_return import CasReturnTests
        from test_cas_accept import SIM, native_client
        fixture=CasReturnTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        preflights=[];submitted=[];view_read=[False];fresh_after_view=[False];refused=[False]
        client=native_client();client['sim'].update(occultLayer=1,allOccultTypes=127)
        client['native_context']['rendered_form']=dict(query='returned-value',value=1,error='')
        client['owner_pair_observation']=dict(session=9)
        client['form_strip']=dict(sim_id=SIM,native_owner_state='bound',cross_kind_navigation=True,
            selected_owner_id='native/1',owned_mask=127,life_states=[
                dict(family='human',variants=[dict(owner_id='native/1')]),
                dict(family='alien',variants=[dict(owner_id='active/2')])])
        def handler(action,value):
            if action=='cas_ui_request':
                operation=json.loads(value)
                if operation['operation']=='status':
                    if view_read[0] and not refused[0]:
                        refused[0]=True
                        return dict(ok=False,message='Native UI transport has no distributor client; no CAS request sent.')
                    preflights.append(format(len(preflights)+1,'032x'))
                    return dict(ok=True,cas_request_id=preflights[-1])
                self.assertTrue(fresh_after_view[0],'Native read expired the first preflight; refresh status before navigating.')
                submitted.append(operation)
                # Stop before delivering navigation; no CAS acceptance is allowed.
                return dict(ok=False,message='Fixture stops before navigation submission.')
            if action=='cas_ui_result' and value in preflights:
                if view_read[0]:fresh_after_view[0]=True
                return dict(ok=True,cas_request_id=value,ui_transition_verified=True,client=client)
            if action=='test_native_cas_engine':
                view_read[0]=True;fresh_after_view[0]=False;fixture.clock+=4
                self.assertEqual(json.loads(value),dict(test_token=fixture.token,value={'operation':'view-status'}))
                return dict(ok=True,scope='native-form-view-status',available=True,state='bound',pid=42,
                    sim_id=SIM,owner_id='native/1',human_owner_id='native/1',native_kind=1,generation=7,layer=1,
                    portrait_pair=dict(base_owner_id='active/2',base_kind=2,alternate_owner_id='native/1',alternate_kind=1))
        fixture.handler=handler
        result,proof=fixture.run_observer(seconds=20)
        self.assertFalse(result['ok']);self.assertFalse(proof['accept_submission_attempted'])
        self.assertEqual(len(submitted),1)
        self.assertEqual(len(preflights),2);self.assertNotEqual(*preflights)
        self.assertTrue(refused[0])
        self.assertEqual((submitted[0]['owner_id'],submitted[0]['native_kind']),('active/2',2))
        actions=[row[0] for row in fixture.calls]
        self.assertLess(actions.index('test_native_cas_engine'),len(actions)-1)
