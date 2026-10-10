"""Every retained lane remains visible; selection is a separate native capability."""
import copy
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_room
from test_cas_form_select import client, SIM, HH, GUID


class CasRoomTests(unittest.TestCase):
    def baseline(self):
        return {'complete': True, 'runtime_pid': os.getpid(), 'original_sim_id': SIM,
            'household_id': HH, 'save_guid': GUID,
            'wrappers': [{'form_flags': n, 'sim_id': str(int(SIM)+n)}
                         for n in (1,2,4,8,16,32,64,128)]}

    def test_every_captured_form_including_future_form_is_visible(self):
        b, c = self.baseline(), client()
        before = copy.deepcopy((b,c))
        result = cas_room.inventory(b,c)
        self.assertEqual([r['form_flags'] for r in result['rows']], [1,2,4,8,16,32,64,128])
        self.assertTrue(all(r['visible'] for r in result['rows']))
        self.assertEqual([r['form_flags'] for r in result['rows'] if r['navigation_supported']], [1,64])
        self.assertFalse(result['all_forms_editable_this_visit'])
        self.assertEqual((b,c),before)
        result['rows'][0]['label']='changed'
        self.assertEqual(cas_room.inventory(b,c)['rows'][0]['label'],'Human')

    def test_alternate_selected_row_does_not_hide_any_original(self):
        r=cas_room.inventory(self.baseline(),client(1))
        self.assertEqual([x['form_flags'] for x in r['rows'] if x['selected']], [64])
        self.assertEqual(len(r['rows']),8)
        self.assertFalse(r['alternate_accept_authorized'])

    def test_vampire_primary_and_dark_share_kind_without_becoming_human_or_hiding_forms(self):
        for layer in (0,1):
            r=cas_room.inventory(self.baseline(),client(layer,base_form=4,alternate_form=4))
            self.assertEqual([x['form_flags'] for x in r['rows']],[1,2,4,8,16,32,64,128])
            self.assertEqual([x['form_flags'] for x in r['native_layers']],[4,4])
            self.assertEqual([x['layer'] for x in r['native_layers'] if x['selected']],[layer])
            v=next(x for x in r['rows'] if x['form_flags']==4)
            self.assertIsNone(v['native_layer'])
            self.assertFalse(v['navigation_supported'])
            self.assertFalse(r['mapping_verified'])

    def test_observed_creature_base_disguise_order_is_not_assumed_human_base(self):
        c=client()
        c['sim'].update(occultType=2,allOccultTypes=3)
        obs=c['owner_pair_observation'];obs['selected'].update(occult_type=2,all_occult_types=3)
        for name in ('raw_feed','retained'):
            p=obs['selector_feed'][name]['pairs'][0]
            p['base'].update(occult_type=2,all_occult_types=3)
            p['alternate'].update(occult_type=1,all_occult_types=3)
        r=cas_room.inventory(self.baseline(),c)
        self.assertEqual(r['selected_form'],2)
        self.assertEqual(next(x for x in r['rows'] if x['form_flags']==2)['native_layer'],0)
        self.assertEqual(next(x for x in r['rows'] if x['form_flags']==1)['native_layer'],1)
        self.assertEqual([x['form_flags'] for x in r['rows'] if x['navigation_supported']], [1,2])
        self.assertFalse(r['alternate_accept_authorized'])

    def test_captured_owner_alias_missing_or_foreign_identity_is_refused(self):
        for change in ('pid','sim','household','owner-alias','main-alias','duplicate-lane','invalid-lane'):
            with self.subTest(change=change):
                b=self.baseline()
                if change=='pid':b['runtime_pid']+=1
                elif change=='sim':b['original_sim_id']=str(int(SIM)+900)
                elif change=='household':b['household_id']=str(int(HH)+900)
                elif change=='owner-alias':b['wrappers'][1]['sim_id']=b['wrappers'][0]['sim_id']
                elif change=='main-alias':b['wrappers'][1]['sim_id']=SIM
                elif change=='duplicate-lane':b['wrappers'][1]['form_flags']=1
                else:b['wrappers'][1]['form_flags']=3
                with self.assertRaises(ValueError):cas_room.inventory(b,client())

    def test_native_reset_mismatched_raw_pair_selection_and_untyped_fields_refused(self):
        for change in ('reset','raw-pair','selected','session','native-form','layer','missing-owner'):
            with self.subTest(change=change):
                b,c=self.baseline(),client();o=c['owner_pair_observation']
                if change=='reset':o['selector_feed']['raw_feed']['delivered']=False
                elif change=='raw-pair':o['selector_feed']['raw_feed']['pairs'][0]['base']['sim_id']=HH
                elif change=='selected':o['selector_feed']['retained']['pairs'][0]['base']['selected']=False
                elif change=='session':o['session']=True
                elif change=='native-form':c['sim']['occultType']=2
                elif change=='layer':c['sim']['occultLayer']=False
                else:b['wrappers']=[x for x in b['wrappers'] if x['form_flags']!=64]
                with self.assertRaises(ValueError):cas_room.inventory(b,c)


if __name__=='__main__':unittest.main()
