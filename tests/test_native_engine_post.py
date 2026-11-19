from pathlib import Path
from contextlib import nullcontext
import json
import io
import urllib.error
import sys
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import apex_cli

class Response:
    def __init__(self,raw):self.raw=raw;self.read_sizes=[]
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read(self,limit):self.read_sizes.append(limit);return self.raw[:limit]

class NativeEnginePostTests(unittest.TestCase):
    def invoke(self,value,opener,observer=None,transport=None,action='test_native_cas_engine'):
        with patch.object(apex_cli,'verified_identity',return_value=dict(native_cli_available=True)), \
             patch.object(apex_cli.reusable_profile,'load',return_value=(None,dict(token='b'*32),None,None)), \
             patch.object(apex_cli,'local_opener',return_value=opener), \
             patch.object(apex_cli.uuid,'uuid4',return_value=Mock(hex='a'*32)):
            return apex_cli.owned_request(Path('state'),action,value=value,submission_observer=observer,transport=transport)

    def test_large_seed_uses_one_bounded_post_with_exact_identity(self):
        value=json.dumps(dict(test_token='b'*32,value=dict(operation='seed-appearance',native_hex='ab'*50000)))
        response=Response(json.dumps(dict(ok=True,request_id='a'*32,owner_export=dict(native_hex='ab'*50000))).encode())
        opener=Mock();opener.open.return_value=response;observed=[]
        def network(*_,**__):raise AssertionError('Full appearance reached GET transport')
        result=self.invoke(value,opener,lambda *x:observed.append(x),network)
        self.assertTrue(result['ok']);opener.open.assert_called_once()
        request=opener.open.call_args.args[0]
        self.assertEqual(request.get_method(),'POST');self.assertEqual(request.full_url,'http://127.0.0.1:8017/api/native')
        self.assertEqual(json.loads(request.data),dict(action='test_native_cas_engine',value=value,request_id='a'*32))
        self.assertEqual(observed,[('test_native_cas_engine','a'*32)])
        self.assertEqual(response.read_sizes,[8*1024*1024+1])

    def test_post_response_loss_does_not_resend(self):
        opener=Mock();opener.open.side_effect=ConnectionResetError('lost after submission')
        with self.assertRaises(ConnectionResetError):self.invoke('{}',opener)
        opener.open.assert_called_once()

    def test_server_failure_retains_its_reason_without_replay(self):
        opener=Mock();opener.open.side_effect=urllib.error.HTTPError(
            'http://127.0.0.1:8017/api/native',500,'error',{},io.BytesIO(b'{"message":"Native input exceeds guard bound"}'))
        with self.assertRaisesRegex(RuntimeError,'500: Native input exceeds guard bound'):self.invoke('{}',opener)
        opener.open.assert_called_once()

    def test_request_too_large_refuses_before_open(self):
        opener=Mock()
        with self.assertRaises(ValueError):self.invoke('x'*(4*1024*1024),opener)
        opener.open.assert_not_called()

    def test_response_too_large_stays_unresolved_without_replay(self):
        opener=Mock();opener.open.return_value=Response(b'x'*(8*1024*1024+1))
        with self.assertRaises(ValueError):self.invoke('{}',opener)
        opener.open.assert_called_once()

    def test_preview_retains_its_small_response_limit(self):
        opener=Mock();response=Response(b'{"ok":true}');opener.open.return_value=response
        self.assertTrue(self.invoke('{}',opener,action='test_preview')['ok'])
        self.assertEqual(response.read_sizes,[32769])

if __name__=='__main__':unittest.main()
