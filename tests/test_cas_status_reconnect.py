import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cas_client import _submit_status


class StatusReconnectTests(unittest.TestCase):
    def args(self):
        return SimpleNamespace(state='state', sim_id='123', seconds=2)

    def test_refused_read_waits_for_exact_peer_and_keeps_one_queued_read(self):
        clock = [0.0]; calls = []
        responses = iter([
            dict(ok=False, message='Native UI transport has no distributor client; no CAS request sent.'),
            dict(native_peers=[dict(sim_id='456', age_seconds=0)]),
            dict(native_peers=[dict(sim_id='123', age_seconds=4)]),
            dict(native_peers=[dict(sim_id='123', age_seconds=.1)]),
            dict(ok=True, cas_request_id='a' * 32),
        ])
        def request(_state, action, *_args, **_kwargs):
            calls.append(action)
            return next(responses)
        result = _submit_status(self.args(), request, lambda: clock[0],
                                lambda delay: clock.__setitem__(0, clock[0] + delay))
        self.assertEqual(result['cas_request_id'], 'a' * 32)
        self.assertEqual(calls, ['cas_ui_request'] + ['cas_ui_diagnostics'] * 3 + ['cas_ui_request'])

    def test_queued_or_unrelated_failures_are_never_replayed(self):
        for response in (dict(ok=False, cas_request_id='a' * 32),
                         dict(ok=False, message='A CAS client request is unresolved.')):
            calls = []
            def request(*_args, **_kwargs):
                calls.append(1)
                return response
            self.assertIs(_submit_status(self.args(), request, lambda: 0, lambda _: None), response)
            self.assertEqual(len(calls), 1)

    def test_missing_peer_expires_without_submitting_another_read(self):
        clock = [0.0]; reads = []
        def request(_state, action, *_args, **_kwargs):
            if action == 'cas_ui_request':
                reads.append(1)
                return dict(ok=False, message='Native UI transport has no distributor client; no CAS request sent.')
            return dict(native_peers=[dict(sim_id='123', age_seconds=float('nan'))])
        result = _submit_status(self.args(), request, lambda: clock[0],
                                lambda delay: clock.__setitem__(0, clock[0] + delay))
        self.assertFalse(result['ok'])
        self.assertEqual(len(reads), 1)
        self.assertGreaterEqual(clock[0], 2)
