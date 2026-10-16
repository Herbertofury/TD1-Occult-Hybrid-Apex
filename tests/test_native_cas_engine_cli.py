from contextlib import nullcontext
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_cas_engine_cli as client
from test_native_cas_probe_cli import Evidence


class EngineCliTests(unittest.TestCase):
    def run_engine(self, request, argument, evidence=None):
        with patch.object(client, 'session', return_value=nullcontext()), \
                patch.object(client.reusable_profile, 'load', return_value=(None, {'token':'b'*32}, None, None)), \
                patch.object(client, 'IntentEvidence', return_value=evidence or Evidence()):
            return client.run(Path('state'), Path('new.json'), request, argument)

    def test_invalid_scope_refuses_before_start_or_submission(self):
        def unexpected(*_, **__):raise AssertionError('Invalid scope reached a game call')
        with self.assertRaises(ValueError):self.run_engine(unexpected, dict(operation='arm'))
        with self.assertRaises(ValueError):client.run(Path('state'), None, unexpected, dict(operation='status'))

    def test_failed_native_start_does_not_submit_scope(self):
        calls=[]
        def request(state, action, **options):calls.append(action);return dict(ok=False)
        self.assertFalse(self.run_engine(request, dict(operation='status'))['ok'])
        self.assertEqual(calls, ['overlay_start'])

    def test_native_response_loss_is_recorded_and_never_replayed(self):
        calls=[]; evidence=Evidence()
        def request(state, action, **options):
            calls.append(action)
            if action=='overlay_start':return dict(ok=True)
            raise OSError('Lost acknowledgment')
        with self.assertRaises(OSError):self.run_engine(request, dict(operation='status'), evidence)
        self.assertEqual(calls, ['overlay_start','test_native_cas_engine'])
        self.assertEqual(evidence.failed, 'Lost acknowledgment')

    def test_scope_intent_precedes_the_exact_guarded_native_request(self):
        import json
        scope=dict(operation='arm',scope_id='a'*32,members=[dict(sim_id='123',owned_mask=127)])
        evidence=Evidence(); calls=[]
        def request(state, action, **options):
            calls.append(action)
            self.assertEqual(evidence.proof['native_engine_request'],scope)
            value=json.loads(options['value'])
            self.assertEqual(value,dict(test_token='b'*32,value=None if action=='overlay_start' else scope))
            return dict(ok=True, production_ready=False)
        self.assertTrue(self.run_engine(request,scope,evidence)['ok'])
        self.assertEqual(calls,['overlay_start','test_native_cas_engine'])
