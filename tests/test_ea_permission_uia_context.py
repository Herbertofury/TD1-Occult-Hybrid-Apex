import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ea_permission_broker as broker
import ea_native_permission as native

class LaunchContextUIA(unittest.TestCase):
    def test_uia_revalidates_pinned_context_before_intent_and_never_uses_pixel_fallback_after_success(self):
        target={'pid':123,'creation_time':456};context={'fixture':'exact Sims handoff'}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            response=SimpleNamespace(returncode=0,stdout='{"ok":true,"acknowledged":true}')
            with patch.object(broker,'process_identity',return_value=target), \
                    patch.object(broker,'validate_launch_context'), \
                    patch.object(broker.subprocess,'run',return_value=response) as invoke, \
                    patch.object(native,'NativeEA') as pixels:
                result=broker.acknowledge_exact(target,root,110,context,clock=lambda:100)
            self.assertTrue(result['acknowledged']);pixels.assert_not_called()
            script=invoke.call_args.args[0][-1]
            self.assertLess(script.index('--verify-context-only'),script.index('invoke-intent'))
            self.assertIn('if ($LASTEXITCODE -ne 0)',script)
            self.assertEqual(script.count('$pattern.Invoke()'),1)
            files=list(root.glob('ea-uia-context-*.json'));self.assertEqual(len(files),1)
            proof=json.loads(files[0].read_text(encoding='utf-8'))
            self.assertEqual(proof['ea'],target);self.assertEqual(proof['launch_context'],context)
            self.assertEqual(proof['expires_at'],110)

    def test_timed_out_uia_never_replays_through_native_pixels(self):
        target={'pid':123,'creation_time':456}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(broker,'process_identity',return_value=target), \
                patch.object(broker,'validate_launch_context'), \
                patch.object(broker.subprocess,'run',side_effect=subprocess.TimeoutExpired('UIA',15)), \
                patch.object(native,'NativeEA') as pixels:
            result=broker.acknowledge_exact(target,Path(folder),110,{'fixture':True},clock=lambda:100)
            self.assertTrue(result['acknowledgement_unresolved']);self.assertFalse(result['retry_safe'])
            pixels.assert_not_called()

    def test_read_only_child_validates_exact_unchanged_proof_and_never_acknowledges(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/('ea-uia-context-'+'a'*32+'.json')
            request={'launch_context':{'fixture':'current Sims'},'ea':{'pid':123}}
            path.write_text(json.dumps(request),encoding='utf-8')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(broker,'evidence_directory'),patch.object(broker,'validate_request') as validate, \
                    patch.object(broker.time,'time',return_value=100),patch.object(broker,'acknowledge_exact') as acknowledge:
                self.assertEqual(broker.verify_context_only(path,digest),dict(ok=True,input_sent=False,launch_context_verified=True))
                validate.assert_called_once_with(request,root,100);acknowledge.assert_not_called()
                validate.reset_mock()
                with self.assertRaises(ValueError):broker.verify_context_only(path,'b'*64)
                validate.assert_not_called()
                path.write_text('{"launch_context":null}',encoding='utf-8')
                with self.assertRaises(ValueError):broker.verify_context_only(path,hashlib.sha256(path.read_bytes()).hexdigest())
                validate.assert_not_called();acknowledge.assert_not_called()

if __name__=='__main__':unittest.main()
