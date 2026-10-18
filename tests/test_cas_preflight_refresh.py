import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1]/'Source')]
import cas_client
import test_cas_form_select as fixture
from test_cas_occult_view import client

REFUSAL='Read fresh CAS status before selecting an independent form.'

class PreflightRefreshTests(unittest.TestCase):
    def run_case(self,refusals=None,changed_layer=False,transport_error=False):
        calls=[];status_count=0;mutation_count=0
        initial=client(2,127);initial['sim']['occultLayer']=0
        args=SimpleNamespace(operation='form-owner-select',state=Path('fixture'),output=None,
            seconds=10,sim_id=fixture.SIM,owner_id='native/4',native_kind=4,owned_mask=127,
            household_id=fixture.HH,native_session=1,expected_layer=0)
        rejections=refusals if refusals is not None else [dict(ok=False,message=REFUSAL,request_state='failed')]
        def request(state,action,sim_id,value=None):
            nonlocal status_count,mutation_count
            calls.append((action,value))
            if action=='cas_ui_request':
                operation=json.loads(value)['operation']
                if operation=='status':
                    status_count+=1
                    return dict(ok=False,cas_request_id=str(status_count)*32,outcome='pending-client')
                mutation_count+=1
                if transport_error:raise OSError('Response lost after dispatch')
                if mutation_count<=len(rejections):return copy.deepcopy(rejections[mutation_count-1])
                return dict(ok=False,cas_request_id='a'*32,outcome='pending-client')
            if action=='cas_ui_result':
                observed=copy.deepcopy(initial)
                if changed_layer and status_count>1:observed['sim']['occultLayer']=1
                return dict(ok=True,cas_request_id=value,client=observed,outcome='completed')
            raise AssertionError(action)
        with patch('reusable_profile.load',return_value=(None,{'token':'a'*32},None,None)):
            result=cas_client._execute(args,request,pause=lambda _seconds:None)
        return result,status_count,mutation_count,calls

    def test_definite_prequeue_refusal_refreshes_once_and_submits_one_native_request(self):
        result,statuses,submissions,_=self.run_case()
        self.assertTrue(result['ok']);self.assertEqual((statuses,submissions),(2,2))
        self.assertEqual(result['preflight_refresh']['refresh_count'],1)
        self.assertFalse(result['preflight_refresh']['native_request_created'])

    def test_second_expiration_stops_without_a_loop(self):
        refusal=dict(ok=False,message=REFUSAL,request_state='failed')
        result,statuses,submissions,_=self.run_case([refusal,refusal])
        self.assertFalse(result['ok']);self.assertEqual((statuses,submissions),(2,2))

    def test_changed_context_refuses_before_another_selection_submission(self):
        with self.assertRaisesRegex(ValueError,'context differs'):
            self.run_case(changed_layer=True)

    def test_a_native_uuid_or_possible_mutation_never_permits_resubmission(self):
        for addition in ({'cas_request_id':'a'*32},{'cas_request_id':None},{'mutation_started':True},
                         {'input_submitted':True},{'request_state':'running'},{'request_state':'unknown'}):
            with self.subTest(addition=addition):
                refusal=dict(ok=False,message=REFUSAL,request_state='failed');refusal.update(addition)
                _result,statuses,submissions,_=self.run_case([refusal])
                self.assertEqual((statuses,submissions),(1,1))

    def test_other_refusals_and_lost_responses_never_trigger_refresh(self):
        result,statuses,submissions,_=self.run_case([dict(ok=False,message='Different form owner')])
        self.assertFalse(result['ok']);self.assertEqual((statuses,submissions),(1,1))
        with self.assertRaises(OSError):self.run_case(transport_error=True)

if __name__=='__main__':unittest.main()
