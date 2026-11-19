import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui, cas_controls, native_cas_engine, test_driver
from test_cas_occult_view import OccultViewTests, client
import test_cas_form_select as fixture


class IndependentOwnerSelectTests(OccultViewTests):
    def setUp(self):
        super().setUp()
        self.owner_request = dict(operation='form-owner-select', owner_id='native/4', native_kind=4,
            owned_mask=69, household_id=fixture.HH, native_session=1, expected_layer=0, test_token='a'*32)

    def fresh(self):
        rid = cas_ui.submit(fixture.SIM, {'operation': 'status'}, clock=lambda: 10)['cas_request_id']
        cas_ui.poll_client(self.peer, clock=lambda: 10)
        initial = client(64, 65); initial['sim']['occultLayer'] = 0
        cas_ui.receive_socket(self.peer, rid, json.dumps(dict(protocol=1, ok=True,
            cas_request_id=rid, client=initial)), clock=lambda: 10, backend=self.backend)

    def test_each_named_form_is_an_exact_owner_even_when_it_uses_human_rendering(self):
        for owner in ('plantsim/plant', 'servo/robot', 'ghost/living', 'reaper/unrobed',
                      'skeleton/skeleton', 'scarecrow/human_cc', 'imaginary_friend/real',
                      'fairy/alternate', 'future_mod/new_form'):
            request = dict(self.owner_request, owner_id=owner, native_kind=1)
            _, wire = cas_ui.envelope(fixture.SIM, request)
            self.assertEqual(wire.split('|')[-1], owner)
        for owner in ('ghost', '../human', 'Ghost/base', 'a/b/c', ''):
            with self.subTest(owner=owner), self.assertRaises(ValueError):
                cas_ui.envelope(fixture.SIM, dict(self.owner_request, owner_id=owner))

    def test_stage_is_one_shot_and_native_receipt_is_required_for_the_same_owner(self):
        self.fresh()
        with patch.object(test_driver, 'guard'), patch.object(native_cas_engine, 'stage_view', return_value=0x12345678) as stage:
            rid = cas_ui.submit(fixture.SIM, self.owner_request, clock=lambda: 10, backend=self.backend)['cas_request_id']
        stage.assert_called_once_with(self.backend, fixture.SIM, rid, self.owner_request)
        wire = cas_ui.poll_client(self.peer, clock=lambda: 10)
        self.assertEqual(wire.split('|')[5:], [str(0x12345678), 'native/4'])
        after = client(4, 69)
        after['native_context']['rendered_form'] = dict(query='returned-value', value=4)
        after['control'] = dict(operation='form-owner-select', owner_id='native/4')
        after['form_strip'] = dict(sim_id=fixture.SIM, selected_owner_id='native/4',
                                  native_owner_state='bound', desired_owner_id='')
        receipt = dict(request_id=rid, owner_id='native/4', state='applied', conversion_called=False)
        with patch.object(native_cas_engine, 'view_result', return_value=receipt) as result:
            cas_ui.receive_socket(self.peer, rid, json.dumps(dict(protocol=1, ok=True, cas_request_id=rid,
                client=after, mutation_started=True)), clock=lambda: 10, backend=self.backend)
        result.assert_called_once_with(self.backend, fixture.SIM, rid, self.owner_request)
        readback = cas_ui.result(rid)
        self.assertTrue(readback['ok'])
        self.assertEqual(readback['native_owner_view_receipt'], receipt)
        self.assertFalse(readback['appearance_persistence_verified'])

    def test_same_rendering_kind_never_suffices_for_wrong_form_identity(self):
        request = dict(self.owner_request, owner_id='ghost/ghost', native_kind=1)
        observed = client(1, 69)
        observed['control'] = dict(operation='form-owner-select', owner_id='plantsim/plant')
        with self.assertRaises(cas_controls.PostconditionMismatch): cas_controls.validate(observed, request)

    def test_a_kind_match_cannot_qualify_another_forms_native_undo_history(self):
        from apex_core import overlay_loader
        request=dict(self.owner_request,owner_id='ghost/living',native_kind=1)
        receipt=dict(request_id='a'*32,sim_id=fixture.SIM,owner_id='ghost/living',state='applied',
            conversion_called=False,native_kind=1,owned_mask=69,independent_undo_bound=True,undo_owner_id='ghost/living')
        status=dict(owner_view_result=receipt,selected_native=dict(available=True,sim_id=fixture.SIM,
            occult_type=1,model_occult_type=1))
        with patch.dict(sys.modules,{'paths':SimpleNamespace(DLL_PATH='fixture')}), \
             patch.object(overlay_loader,'native_cas_engine_control',return_value=status):
            self.assertEqual(native_cas_engine.view_result(SimpleNamespace(__file__='fixture'),fixture.SIM,'a'*32,request),receipt)
            receipt['undo_owner_id']='plantsim/plant'
            with self.assertRaisesRegex(ValueError,'completed binding receipt'):
                native_cas_engine.view_result(SimpleNamespace(__file__='fixture'),fixture.SIM,'a'*32,request)
            receipt['undo_owner_id']='ghost/living';receipt['independent_undo_bound']=False
            with self.assertRaisesRegex(ValueError,'completed binding receipt'):
                native_cas_engine.view_result(SimpleNamespace(__file__='fixture'),fixture.SIM,'a'*32,request)

    def test_family_metadata_never_substitutes_for_the_actual_rendered_form(self):
        request = dict(self.owner_request, owner_id='alien/alien', native_kind=2)
        observed = client(4, 69)
        observed['control'] = dict(operation='form-owner-select', owner_id='alien/alien')
        observed['form_strip'] = dict(sim_id=fixture.SIM, selected_owner_id='alien/alien',
                                     native_owner_state='bound', desired_owner_id='')
        observed['native_context']['rendered_form'] = dict(query='returned-value', value=2)
        cas_controls.validate(observed, request)
        self.assertEqual(observed['sim']['occultType'], 4)
        for bad in (dict(query='returned-null', value=2), dict(query='returned-value', value=4),
                    dict(query='returned-value', value=True), dict(query='returned-value', value=2.0), {}):
            observed['native_context']['rendered_form'] = bad
            with self.subTest(bad=bad), self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(observed, request)

    def test_matching_renderer_and_echoed_target_cannot_hide_another_or_pending_owner(self):
        request=dict(self.owner_request,owner_id='native/2',native_kind=2)
        observed=client(4,69)
        observed['native_context']['rendered_form']=dict(query='returned-value',value=2)
        observed['control']=dict(operation='form-owner-select',owner_id='native/2')
        valid=dict(sim_id=fixture.SIM,selected_owner_id='native/2',native_owner_state='bound',desired_owner_id='')
        observed['form_strip']=dict(valid)
        cas_controls.validate(observed,request)
        for change in ({'selected_owner_id':'native/1'},{'desired_owner_id':'native/1'},
                       {'desired_owner_id':'native/2'},{'native_owner_state':'unbound'},
                       {'native_owner_state':'unresolved'},{'sim_id':'13'}):
            with self.subTest(change=change):
                observed['form_strip']=dict(valid,**change)
                with self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(observed,request)
