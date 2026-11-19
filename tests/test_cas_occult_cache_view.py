"""A native pair projection must never masquerade as complete membership proof."""
import copy,json,os,sys
from pathlib import Path
from unittest.mock import patch
from contextlib import nullcontext
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_ui,cas_controls,test_driver
from test_cas_occult_view import OccultViewTests,client
import test_cas_form_select as fixture


class CacheQualificationTests(OccultViewTests):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(cas_ui,'CACHE_VIEW_QUARANTINED',False))
        self.backend._all_occults=lambda:(1,4,64)
        self.backend._has_occult=lambda tracker,kind:kind in tracker.forms
        cas_ui.capture_original_owner(self.backend,self.sim)

    def probe(self):
        return dict(operation='occult-cache-view',occult_type=4,expected_all_occults=127,
            household_id=fixture.HH,native_session=1,expected_layer=1,owned_mask=69,test_token='a'*32)

    def test_owned_wrappers_do_not_authorize_new_or_forged_membership(self):
        request=self.probe();request['expected_all_occults']=65
        _,wire=cas_ui.envelope(fixture.SIM,request)
        self.assertEqual(wire.split('|')[-1],fixture.HH+',1,69')
        self.assertNotIn('a'*32,wire)
        for change in ({'owned_mask':65},{'occult_type':1},{'owned_mask':255},{'test_token':'bad'},
                       {'expected_all_occults':127}):
            with self.subTest(change=change):
                value=dict(request,**change)
                with self.assertRaises(ValueError):cas_ui.envelope(fixture.SIM,value)

    def test_disposable_guard_runs_before_any_selection_is_queued(self):
        request=self.probe();request['expected_all_occults']=65
        with patch.object(test_driver,'guard',side_effect=ValueError('wrong profile')):
            with self.assertRaisesRegex(ValueError,'wrong profile'):
                cas_ui.submit(fixture.SIM,request,clock=lambda:10,backend=self.backend)
        self.assertFalse(any(row['request']['operation']=='occult-cache-view' for row in cas_ui._RECORDS.values()))

    def test_native_projection_is_distinct_from_persistent_membership_and_retention(self):
        # The regular fixture carries 127; use a larger actual captured roster
        # while retaining the same complete distinct owner identities.
        self.backend._all_occults=lambda:(1,2,4,8,16,32,64)
        self.backend._has_occult=lambda tracker,kind:True
        cas_ui.capture_original_owner(self.backend,self.sim)
        self.observe();request=self.probe();request['owned_mask']=127
        with patch.object(test_driver,'guard',return_value=None) as guard:
            rid=cas_ui.submit(fixture.SIM,request,clock=lambda:10,backend=self.backend)['cas_request_id']
        guard.assert_called_once()
        cas_ui.poll_client(self.peer,clock=lambda:10)
        after=client(4,5);after['control']=dict(operation='occult-cache-view',occults=[{'occult_type':4}])
        payload=json.dumps(dict(protocol=1,ok=True,cas_request_id=rid,client=after,mutation_started=True))
        cas_ui.receive_socket(self.peer,rid,payload,clock=lambda:10,backend=self.backend)
        result=cas_ui.result(rid)
        self.assertTrue(result['ok']);self.assertTrue(result['experimental'])
        self.assertTrue(result['selection_only_verified'])
        self.assertFalse(result['native_cache_retention_verified'])
        self.assertFalse(result['appearance_persistence_verified'])
        # A duplicate exact ACK does not repeat the conversion.
        cas_ui.receive_socket(self.peer,rid,payload,clock=lambda:10,backend=self.backend)

    def test_changed_capture_or_unowned_target_never_reaches_socket_delivery(self):
        self.observe();request=self.probe();request['owned_mask']=127
        with patch.object(test_driver,'guard',return_value=None):
            with self.assertRaisesRegex(ValueError,'actual membership capture'):
                cas_ui.submit(fixture.SIM,request,clock=lambda:10,backend=self.backend)
        self.assertFalse(any(row['request']['operation']=='occult-cache-view' for row in cas_ui._RECORDS.values()))

    def test_wrong_native_projection_retains_failed_postcondition(self):
        request=self.probe();request['owned_mask']=127
        for mask in (3,9,127,True):
            after=client(4,mask);after['control']=dict(operation='occult-cache-view',occults=[{'occult_type':4}])
            with self.subTest(mask=mask),self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(after,request)

    def test_future_or_untyped_membership_only_disables_the_experimental_capability(self):
        for kinds in ((1,4,128),(1,True,4)):
            self.backend._all_occults=lambda:kinds
            value=cas_ui.capture_original_owner(self.backend,self.sim)
            self.assertTrue(value['original_owner']['complete'])
            stored=next(reversed(cas_ui._OWNER_BASELINES.values()))
            self.assertIsNone(stored['cache_membership'])

    def test_actual_native_crash_quarantine_precedes_guard_and_queueing(self):
        with patch.object(cas_ui,'CACHE_VIEW_QUARANTINED',True),patch.object(test_driver,'guard') as guard:
            with self.assertRaisesRegex(ValueError,'quarantined'):
                cas_ui.submit(fixture.SIM,self.probe(),clock=lambda:10,backend=self.backend)
            guard.assert_not_called()
        self.assertFalse(cas_ui._RECORDS)

    def test_host_cli_quarantine_precedes_every_rpc_or_token_read(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
        import cas_client
        from types import SimpleNamespace
        from unittest.mock import Mock
        with patch('cli_identity_cache.session',return_value=nullcontext()),\
                patch.object(cas_ui,'CACHE_VIEW_QUARANTINED',True),patch('reusable_profile.load') as load:
            request=Mock()
            args=SimpleNamespace(operation='occult-cache-view',state=Path('unused'),output=None,
                seconds=1,request_id=None,sim_id=fixture.SIM)
            with self.assertRaisesRegex(ValueError,'quarantined'):cas_client.execute(args,request)
            request.assert_not_called();load.assert_not_called()
