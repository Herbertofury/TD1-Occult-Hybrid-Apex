import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_controls,cas_ui

class PairControlTests(unittest.TestCase):
    def receipt(self,operation='pair-copy'):
        pair=dict(sim_id='12',base_owner_id='active/2',alternate_owner_id='native/1',human_owner_id='native/1',linked=False)
        return dict(sim=dict(simId='12'),control=dict(operation=operation,request_id='a'*32,sim_id='12',acknowledged=True,
            source_owner_id='active/2',target_owner_id='native/1',scope='whole-appearance',pair=pair,enabled=False))

    def test_whole_copy_names_both_independent_owners_including_named_special_forms(self):
        for source,target in [('active/2','native/1'),('native/1','ghost/manifested'),('fairy/alternate','native/1')]:
            request=dict(operation='pair-copy',source_owner_id=source,target_owner_id=target)
            _,wire=cas_ui.envelope('12',request)
            fields=wire.split('|')
            self.assertEqual(len(fields),7,'The real GFx frame parser requires exactly seven fields')
            self.assertEqual(fields[2],'pair-copy')
            self.assertEqual(fields[6].split(','),[source,target])
            self.assertEqual(cas_controls.wire(request,lambda _:0),(0,0,0,source+','+target))

    def test_link_requires_a_bool_and_an_exact_form_instead_of_a_genus_number(self):
        request=dict(operation='pair-link',owner_id='ghost/manifested',enabled=True)
        _,wire=cas_ui.envelope('12',request)
        self.assertEqual(len(wire.split('|')),7)
        self.assertEqual(wire.split('|')[6].split(','),['ghost/manifested','1'])
        self.assertEqual(cas_controls.wire(request,lambda _:0),(0,0,0,'ghost/manifested,1'))
        for bad in (1,'true',None):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                cas_controls.wire(dict(request,enabled=bad),lambda _:0)

    def test_malformed_or_same_owner_copy_refuses_before_a_native_frame(self):
        for source,target in [('native/1','native/1'),('native/1|other','active/2'),('native/1','../x'),('12','native/1')]:
            with self.subTest(source=source,target=target),self.assertRaises(ValueError):
                cas_ui.envelope('12',dict(operation='pair-copy',source_owner_id=source,target_owner_id=target))

    def test_a_future_control_cannot_inject_an_outer_frame_field(self):
        with patch.object(cas_controls,'wire',return_value=(0,0,0,'native/1|native/4')):
            with self.assertRaisesRegex(ValueError,'field separator'):
                cas_ui.envelope('12',dict(operation='pair-copy',source_owner_id='native/1',target_owner_id='native/4'))

    def test_copy_requires_its_acknowledged_direction_and_current_shared_human_pair(self):
        request=dict(operation='pair-copy',source_owner_id='active/2',target_owner_id='native/1')
        cas_controls.validate(self.receipt(),request)
        for damage in ('sim','ack','request','source','target','human','scope'):
            client=self.receipt();c=client['control']
            if damage=='sim':c['sim_id']='13'
            elif damage=='ack':c['acknowledged']=False
            elif damage=='request':c['request_id']='not-a-request'
            elif damage=='source':c['source_owner_id']='native/4'
            elif damage=='target':c['target_owner_id']='native/4'
            elif damage=='human':c['pair']['human_owner_id']='ghost/absent'
            else:c['scope']='unrequested-partial-copy'
            with self.subTest(damage=damage),self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(client,request)

    def test_link_and_unlink_are_specific_to_the_current_actual_pair(self):
        for enabled in (False,True):
            request=dict(operation='pair-link',owner_id='active/2',enabled=enabled)
            client=self.receipt('pair-link');client['control']['enabled']=enabled;client['control']['pair']['linked']=enabled
            cas_controls.validate(client,request)
            changed=copy.deepcopy(client);changed['control']['pair']['linked']=not enabled
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(changed,request)
            with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,dict(request,owner_id='native/4'))

    def test_werewolf_fur_copy_exception_is_exactly_scoped_to_current_human_cc(self):
        target='werewolf/werewolf_human_cc'
        request=dict(operation='pair-copy',source_owner_id='native/32',target_owner_id=target,category_flags=16777232)
        client=self.receipt();client['form_strip']={'selected_owner_id':target}
        client['control'].update(source_owner_id='native/32',target_owner_id=target,scope='selected-categories',category_flags=16777232)
        client['control']['pair'].update(base_owner_id='native/1',alternate_owner_id=target)
        cas_controls.validate(client,request)
        for selected in ('native/1','native/32',None):
            changed=copy.deepcopy(client);changed['form_strip']['selected_owner_id']=selected
            with self.subTest(selected=selected),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(changed,request)
        changed=copy.deepcopy(client);del changed['form_strip']
        with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(changed,request)
