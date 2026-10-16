import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_controls, cas_ui, native_cas_engine, test_driver
from test_cas_occult_view import OccultViewTests, client
import test_cas_form_select as fixture


class NativeOwnerViewTests(OccultViewTests):
    def setUp(self):
        super().setUp()
        self.backend._all_occults=lambda:(1,4,64)
        self.backend._has_occult=lambda tracker,kind:kind in tracker.forms
        cas_ui.capture_original_owner(self.backend,self.sim)

    def owner_request(self):
        return dict(operation='occult-owner-view',occult_type=4,expected_all_occults=65,
            household_id=fixture.HH,native_session=1,expected_layer=0,owned_mask=69,test_token='a'*32)

    def test_owned_human_and_cross_kind_wire_never_add_unowned_forms(self):
        value=self.owner_request(); _,wire=cas_ui.envelope(fixture.SIM,value)
        self.assertEqual(wire.split('|')[3:6],['1','65','4'])
        cas_ui.envelope(fixture.SIM,dict(value,occult_type=1))
        with self.assertRaises(ValueError):cas_ui.envelope(fixture.SIM,dict(value,occult_type=2))

    def test_unactivated_engine_refuses_before_guard_or_socket_delivery(self):
        with patch.object(native_cas_engine,'selection_ready',return_value=False),patch.object(test_driver,'guard') as guard:
            with self.assertRaisesRegex(ValueError,'quarantined'):cas_ui.submit(fixture.SIM,self.owner_request(),backend=self.backend)
            guard.assert_not_called()
        self.assertFalse(cas_ui._RECORDS)

    def test_native_selection_retains_every_owned_kind_and_accepts_only_human_bit_normalization(self):
        request=self.owner_request()
        for mask in (69,68):
            after=client(4,mask);after['control']=dict(operation='occult-owner-view',occults=[dict(occult_type=4)])
            cas_controls.validate(after,request)
        for mask in (5,4,65,True):
            after=client(4,mask);after['control']=dict(operation='occult-owner-view',occults=[dict(occult_type=4)])
            with self.subTest(mask=mask),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(after,request)

    def test_even_activated_engine_cannot_dispatch_the_mislabeling_conversion(self):
        with patch.object(native_cas_engine, 'selection_ready', return_value=True) as ready, \
                patch.object(test_driver, 'guard') as guard:
            with self.assertRaisesRegex(ValueError, 'independent owner'):
                cas_ui.submit(fixture.SIM, self.owner_request(), backend=self.backend)
            ready.assert_not_called()
            guard.assert_not_called()
        self.assertFalse(cas_ui._RECORDS)
