import json,sys
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_cas_probe_cli as client

class Evidence:
    def __init__(self,*_):self.proof={};self.failed=None
    def record(self):pass
    def wrap(self,request):return request
    def finish(self,value):return dict(value,proof_sha256='a'*64)
    def fail(self,error):self.failed=str(error)

class NativeCodeCliTests(unittest.TestCase):
    def run_probe(self,request,evidence=None,code_window=None):
        with patch.object(client,'session',return_value=nullcontext()),\
                patch.object(client.reusable_profile,'load',return_value=(None,{'token':'b'*32},None,None)),\
                patch.object(client,'IntentEvidence',return_value=evidence or Evidence()):
            return client.run(Path('state.json'),Path('new-proof.json'),request,code_window=code_window)
    def test_cold_menu_initializes_exact_sidecar_before_probe_without_sim_arguments(self):
        calls=[]
        def request(state,action,**options):
            calls.append(action)
            self.assertEqual(json.loads(options['value']),{'test_token':'b'*32,'value':None})
            self.assertNotIn('sim_id',options)
            if action=='overlay_start':return {'ok':True}
            return dict(ok=True,read_only=True,game_memory_written=False,game_files_written=False,native_patch_qualified=False,
                services=[{'targets':[{'references':[{}]}]}],function_snapshots=[{}],code_snapshot_bytes=80)
        result=self.run_probe(request)
        self.assertEqual(calls,['overlay_start','test_native_cas_probe'])
        self.assertTrue(result['ok']);self.assertEqual(result['reference_count'],1)
        self.assertEqual(result['function_snapshots'],1);self.assertFalse(result['native_patch_qualified'])
    def test_unacknowledged_start_does_not_submit_or_retry_a_probe(self):
        calls=[]
        def request(state,action,**_):calls.append(action);return {'ok':False,'message':'mismatched DLL'}
        self.assertFalse(self.run_probe(request)['ok'])
        self.assertEqual(calls,['overlay_start'])
    def test_transport_failure_is_retained_without_repeating_native_initialization(self):
        calls=[];evidence=Evidence()
        def request(state,action,**_):
            calls.append(action)
            if action=='overlay_start':return {'ok':True}
            raise OSError('response lost')
        with self.assertRaisesRegex(OSError,'response lost'):self.run_probe(request,evidence)
        self.assertEqual(calls,['overlay_start','test_native_cas_probe']);self.assertEqual(evidence.failed,'response lost')
    def test_write_claim_or_absent_external_proof_refuses(self):
        def request(state,action,**_):
            if action=='overlay_start':return {'ok':True}
            return dict(ok=True,read_only=True,game_memory_written=True,game_files_written=False,native_patch_qualified=False)
        with self.assertRaisesRegex(ValueError,'no-write'):self.run_probe(request)
        with self.assertRaisesRegex(ValueError,'external --output'):client.run(Path('state.json'),None,request)

    def test_code_window_has_separate_typed_payload_and_retains_its_read_intent(self):
        evidence=Evidence(); calls=[]; window={'rva':0x44a9e0,'bytes':1024}
        def request(state,action,**options):
            calls.append(action); value=json.loads(options['value'])
            self.assertEqual(value,{'test_token':'b'*32,'value':None if action=='overlay_start' else window})
            if action=='overlay_start':return {'ok':True}
            return dict(ok=True,read_only=True,game_memory_written=False,game_files_written=False,
                        native_patch_qualified=False,code_rva=window['rva'],captured_bytes=window['bytes'],code_sha256='c'*64)
        result=self.run_probe(request,evidence,window)
        self.assertEqual(calls,['overlay_start','test_native_cas_code_window'])
        self.assertEqual(evidence.proof['requested_code_window'],window)
        self.assertEqual(result['code_rva'],window['rva']);self.assertEqual(result['captured_bytes'],1024)

    def test_bad_code_windows_never_start_the_loader(self):
        def request(*args,**kwargs):raise AssertionError('Unvalidated code window reached game')
        for window in ({'rva':-1,'bytes':1},{'rva':1,'bytes':8193},{'rva':True,'bytes':1},
                       {'rva':0x140000000,'bytes':1},{'rva':1,'bytes':1,'address':2}):
            with self.assertRaises(ValueError):self.run_probe(request,code_window=window)
