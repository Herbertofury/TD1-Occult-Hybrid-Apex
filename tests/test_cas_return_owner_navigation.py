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
        return dict(sim=dict(simId='44',allOccultTypes=127),owner_pair_observation=dict(session=9),
                    form_strip=dict(sim_id='44',native_owner_state='bound',cross_kind_navigation=True,
                                    owned_mask=127,life_states=[dict(family='human',variants=[dict(owner_id='native/1')])]))

    def test_bound_fairy_uses_shared_human_owner_without_legacy_pair_delivery(self):
        client=self.client();client['owner_pair_observation'].update(complete=False,delivered=False,pairs=[])
        before=copy.deepcopy(client)
        request=primary_navigation(client,'44','55','a'*32)
        self.assertEqual(request,dict(operation='form-owner-select',owner_id='native/1',
            native_kind=1,owned_mask=127,household_id='55',expected_layer=1,native_session=9,test_token='a'*32))
        request_id,wire=envelope('44',request)
        self.assertEqual(len(request_id),32);self.assertIn('|form-owner-select|',wire)
        self.assertEqual(client,before)

    def test_original_human_owner_can_be_active_instead_of_stored(self):
        client=self.client();client['form_strip']['life_states'][0]['variants'][0]['owner_id']='active/1'
        self.assertEqual(primary_navigation(client,'44','55','a'*32)['owner_id'],'active/1')

    def test_missing_duplicate_wrong_sim_or_nonhuman_owner_refuses_without_falling_back(self):
        for damage in ('missing','duplicate','werewolf','wrong-sim','mask','not-navigation'):
            client=self.client();strip=client['form_strip']
            if damage=='missing':strip['life_states']=[]
            elif damage=='duplicate':strip['life_states']*=2
            elif damage=='werewolf':strip['life_states'][0]['variants'][0]['owner_id']='active/32'
            elif damage=='wrong-sim':strip['sim_id']='45'
            elif damage=='mask':strip['owned_mask']=5
            else:strip['cross_kind_navigation']=False
            with self.subTest(damage=damage),self.assertRaises(ValueError):primary_navigation(client,'44','55','a'*32)

    def test_legacy_editor_keeps_its_existing_pair_contract(self):
        client=self.client();client.pop('form_strip')
        self.assertEqual(primary_navigation(client,'44','55'),dict(operation='layer-select',household_id='55',expected_layer=1,target_layer=0,native_session=9))

    def test_invalid_session_refuses_both_paths(self):
        for value in (None,0,True,'9'):
            client=self.client();client['owner_pair_observation']['session']=value
            with self.subTest(value=value),self.assertRaises(ValueError):primary_navigation(client,'44','55')

    def test_missing_profile_token_refuses_the_native_owner_operation(self):
        with self.assertRaisesRegex(ValueError,'token'):primary_navigation(self.client(),'44','55')
