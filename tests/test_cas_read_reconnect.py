from pathlib import Path
import json,sys
from types import SimpleNamespace as Obj
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import cas_client


class CasReadReconnectTests(unittest.TestCase):
    def run_case(self, refusal=None, status_ok=True, operation='catalog'):
        calls=[]; issued={}; queries=0
        args=Obj(operation=operation,state=Path('fixture-state.json'),sim_id='12',seconds=1,output=None,
                 panel='clothing_hair',offset=0,limit=8,data_id='100')
        def request(state,action,sim_id=None,**kw):
            nonlocal queries
            value=kw.get('value');op=json.loads(value)['operation'] if action=='cas_ui_request' else value
            calls.append((action,op))
            if action=='cas_ui_request':
                if op!='status':
                    queries+=1
                    if queries==1:
                        return dict(ok=False,message='Native UI transport has no distributor client; no CAS request sent.',
                            request_id='a'*32,request_state='failed',**(refusal or {}))
                rid=str(len(issued)+1).zfill(32);issued[rid]=op
                return dict(ok=False,outcome='pending-client',cas_request_id=rid)
            if action=='cas_ui_result':
                return dict(ok=status_ok if issued[value]=='status' else True,cas_request_id=value,
                    cas_request_state='completed',client={})
            return dict(ok=True,native_peers=[])
        result=cas_client._execute(args,request)
        return result,calls

    def test_read_reconnects_only_after_explicit_no_native_request_refusal(self):
        result,calls=self.run_case()
        self.assertTrue(result['ok']);self.assertEqual(result['read_reconnect']['refresh_count'],1)
        self.assertEqual([op for action,op in calls if action=='cas_ui_request'],['catalog','status','catalog'])

    def test_selection_is_queued_natively_once_after_explicit_prequeue_refusal(self):
        result,calls=self.run_case(operation='select')
        self.assertTrue(result['ok'])
        self.assertEqual([op for action,op in calls if action=='cas_ui_request'],['select','status','select'])
        self.assertEqual(len([op for action,op in calls if action=='cas_ui_result' and op!='00000000000000000000000000000001']),1)

    def test_selection_with_an_issued_or_unknown_native_uuid_is_never_requeued(self):
        result,calls=self.run_case(dict(cas_request_id=None),operation='select')
        self.assertFalse(result['ok']);self.assertEqual(calls,[('cas_ui_request','select')])

    def test_unknown_cas_id_or_started_mutation_cannot_enter_reconnect(self):
        for refusal in (dict(cas_request_id=None),dict(mutation_started=True),dict(input_submitted=True)):
            result,calls=self.run_case(refusal)
            self.assertFalse(result['ok']);self.assertEqual(calls,[('cas_ui_request','catalog')])

    def test_failed_reconnect_does_not_submit_catalog_again(self):
        result,calls=self.run_case(status_ok=False)
        self.assertFalse(result['ok']);self.assertFalse(result['read_query_submitted'])
        self.assertEqual([op for action,op in calls if action=='cas_ui_request'],['catalog','status'])
