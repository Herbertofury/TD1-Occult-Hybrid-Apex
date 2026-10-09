"""Source fixtures for one authenticated start/focus and observed DXGI selection."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_capture
import game_focus
import game_window


SCRIPT, DLL, TOKEN = 'a' * 64, 'b' * 64, 'c' * 32


def status(native=1, **change):
    return dict({'ok': True, 'native_status': native, 'visible': False,
        'game_window_verified': native >= 2, 'renderer_initialized': native == 3,
        'rendered_frames': 7 if native == 3 else 0, 'frame_submission_verified': native == 3,
        'captures_completed': 0, 'dll_sha256': DLL}, **change)


def identity(**change):
    return dict({'pid': 42, 'test_token': TOKEN, 'script_sha256': SCRIPT}, **change)


def focused(**change):
    return dict({'ok': True, 'foreground_verified': True, 'foreground_pid': 42,
        'window': {'pid': 42, 'hwnd': 12, 'visible': True, 'class': 'Canvas-123',
                   'width': 1278, 'height': 1376}}, **change)


class RendererBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.values = [status(), status(), status(2)]
        self.start = {'ok': True, 'native_code': 0, 'protocol': 1, 'dll_sha256': DLL}
        self.identities, self.focused = [identity()] * 3, focused()
        self.calls, self.evidence, self.records, self.clock = [], {}, [], 0.0
        self.after_focus = None
        self.after_fallback = None
        self.fallback_result = focused(automatic_pre_input_focus=True, focus_helper_proof='d' * 64)

    def call(self, _state, action, **kwargs):
        self.calls.append(action)
        self.assertEqual(self.evidence['steps'][-1], {'action': action, 'state': 'attempted'})
        if action == 'overlay_status':
            value = self.values.pop(0) if len(self.values) > 1 else self.values[0]
        elif action == 'overlay_start':
            self.assertTrue(self.evidence['start_attempted'])
            value = self.start
        else:
            self.fail('Unexpected input or visibility action: ' + action)
        if isinstance(value, Exception): raise value
        return copy.deepcopy(value)

    def bridge(self, _state):
        return self.identities.pop(0) if len(self.identities) > 1 else self.identities[0]

    def focus(self, pid):
        self.calls.append('focus')
        self.assertEqual(pid, 42)
        self.assertTrue(self.evidence['focus_attempted'])
        if self.after_focus: self.after_focus()
        if isinstance(self.focused, Exception): raise self.focused
        return copy.deepcopy(self.focused)

    def fallback(self, state, pid, prior):
        self.calls.append('focus-fallback')
        self.assertEqual(state, 'state')
        self.assertEqual(pid, 42)
        self.assertEqual(prior, dict(self.focused, input_submitted=False))
        self.assertTrue(self.evidence['focus_fallback_attempted'])
        self.assertTrue(self.records[-1]['focus_fallback_attempted'])
        if self.after_fallback: self.after_fallback()
        if isinstance(self.fallback_result, Exception): raise self.fallback_result
        return copy.deepcopy(self.fallback_result)

    def run_bootstrap(self, expected=None, default_focus=False):
        journal = {'token': TOKEN, 'artifacts': [
            {'name': 'ApexOccultHybrid.ts4script', 'sha256': SCRIPT},
            {'name': 'ApexOverlay.dll', 'sha256': DLL}]}
        with patch.object(game_capture.reusable_profile, 'load', return_value=(None, journal, None, None)), \
                patch.object(game_window, 'focus', side_effect=self.focus), \
                patch.object(game_focus, 'focus_for_input', side_effect=self.fallback):
            return game_capture.prepare_window('state', self.call, self.evidence,
                lambda: self.records.append(copy.deepcopy(self.evidence)), identity=expected,
                identity_provider=self.bridge, focus=None if default_focus else self.focus, monotonic=lambda: self.clock,
                pause=lambda seconds: setattr(self, 'clock', self.clock + seconds))

    def test_exact_not_started_starts_once_then_focuses_and_observes_actual_window(self):
        self.values = [{'ok': False, 'message': 'F11 sidecar has not been started.'}, status(), status(), status(2)]
        result = self.run_bootstrap(expected=identity())
        self.assertEqual(result['native_status'], 2)
        self.assertTrue(self.evidence['game_window_verified'])
        self.assertEqual(self.calls.count('overlay_start'), 1)
        self.assertEqual(self.calls.count('focus'), 1)
        self.assertEqual(self.calls[:4], ['overlay_status', 'overlay_start', 'overlay_status', 'focus'])
        self.assertTrue(self.records[1]['steps'][0]['state'] == 'observed')

    def test_started_transitional_status_is_never_treated_as_ready(self):
        result = self.run_bootstrap()
        self.assertEqual(result['native_status'], 2)
        self.assertFalse(self.evidence['start_attempted'])
        self.assertEqual(self.calls, ['overlay_status', 'focus', 'overlay_status', 'overlay_status'])
        self.assertGreater(self.clock, .1)

    def test_already_observed_window_needs_no_restart_or_os_focus(self):
        self.values = [status(3)]
        self.identities = [{'pid': 'unverified'}]
        self.assertEqual(self.run_bootstrap()['native_status'], 3)
        self.assertEqual(self.calls, ['overlay_status'])
        self.assertFalse(self.evidence['start_attempted'])
        self.assertFalse(self.evidence['focus_attempted'])

    def test_unknown_and_failed_loader_status_never_start_or_focus(self):
        for value in ({'ok': False, 'message': 'F11 loader: hash mismatch'},
                      {'ok': True, 'native_status': 1},
                      {'ok': False, 'message': 'F11 sidecar has not been started.', 'visible': True},
                      status(game_window_verified=True), status(visible=0), status(native_status=True)):
            with self.subTest(value=value):
                self.setUp(); self.values = [value]
                with self.assertRaises(ValueError): self.run_bootstrap()
                self.assertEqual(self.calls, ['overlay_status'])

    def test_mismatched_cached_lifecycle_or_installed_script_refuses_before_start(self):
        for change in ({'pid': 43}, {'pid': True}, {'test_token': 'd' * 32}, {'script_sha256': 'd' * 64}):
            with self.subTest(change=change):
                self.setUp(); self.values = [{'ok': False, 'message': 'F11 sidecar has not been started.'}]
                with self.assertRaises(ValueError): self.run_bootstrap(identity(**change))
                self.assertEqual(self.calls, ['overlay_status'])

    def test_lost_or_unresolved_start_is_preserved_without_replay(self):
        for failed in (TimeoutError('start response lost'), dict(self.start, request_state='unknown', request_id='f' * 32)):
            with self.subTest(failed=failed):
                self.setUp(); self.values = [{'ok': False, 'message': 'F11 sidecar has not been started.'}]
                self.start = failed
                with self.assertRaises((OSError, ValueError)): self.run_bootstrap()
                self.assertEqual(self.calls, ['overlay_status', 'overlay_start'])
                self.assertTrue(self.evidence['start_attempted'])
                self.assertEqual(self.evidence['steps'][-1]['state'], 'unresolved')

    def test_rejected_wrong_dll_or_boolean_start_receipt_never_focuses(self):
        for change in ({'ok': False}, {'dll_sha256': 'd' * 64}, {'native_code': False}, {'protocol': True}):
            with self.subTest(change=change):
                self.setUp(); self.values = [{'ok': False, 'message': 'F11 sidecar has not been started.'}]
                self.start.update(change)
                with self.assertRaises(ValueError): self.run_bootstrap()
                self.assertEqual(self.calls, ['overlay_status', 'overlay_start'])

    def test_wrong_started_dll_and_changed_bridge_never_focus(self):
        self.values = [status(dll_sha256='d' * 64)]
        with self.assertRaises(ValueError): self.run_bootstrap()
        self.assertEqual(self.calls, ['overlay_status'])
        self.setUp(); self.identities = [identity(), identity(pid=43)]
        with self.assertRaises(ValueError): self.run_bootstrap()
        self.assertEqual(self.calls, ['overlay_status'])

    def test_wrong_or_ambiguous_window_receipt_never_polls_or_replays_focus(self):
        for change in ({'ok': False}, {'foreground_verified': False}, {'foreground_pid': 43},
                       {'window': dict(focused()['window'], pid=43)},
                       {'window': dict(focused()['window'], visible=False)},
                       {'window': dict(focused()['window'], **{'class': 'EADesktop'})},
                       {'window': dict(focused()['window'], width=True)}):
            with self.subTest(change=change):
                self.setUp(); self.focused.update(change)
                with self.assertRaises(ValueError): self.run_bootstrap()
                self.assertEqual(self.calls, ['overlay_status', 'focus'])

    def test_lost_focus_and_selection_timeout_never_start_or_repeat_focus(self):
        self.focused = OSError('focus observation failed')
        with self.assertRaises(OSError): self.run_bootstrap()
        self.assertEqual(self.calls, ['overlay_status', 'focus'])
        self.setUp(); self.values = [status()]
        with self.assertRaises(TimeoutError): self.run_bootstrap()
        self.assertEqual(self.calls.count('focus'), 1)
        self.assertEqual(self.calls.count('overlay_start'), 0)
        self.assertFalse(self.evidence['game_window_verified'])
        self.assertLessEqual(self.clock, 3.001)

    def test_sidecar_or_bridge_changes_during_observation_refuse(self):
        self.values = [status(), status(2, dll_sha256='d' * 64)]
        with self.assertRaises(ValueError): self.run_bootstrap()
        self.assertFalse(self.evidence['game_window_verified'])
        self.setUp(); self.identities = [identity(), identity(), identity(pid=43)]
        with self.assertRaises(ValueError): self.run_bootstrap()
        self.assertFalse(self.evidence['game_window_verified'])

    def test_late_native_selection_is_not_accepted_after_deadline(self):
        self.values = [status(), status(2)]
        original = self.call
        def delayed(state, action, **kwargs):
            value = original(state, action, **kwargs)
            if action == 'overlay_status' and value.get('native_status') == 2: self.clock += 4
            return value
        self.call = delayed
        with self.assertRaises(TimeoutError): self.run_bootstrap()
        self.assertFalse(self.evidence['game_window_verified'])

    def refused_default_focus(self):
        self.focused = focused(ok=False, foreground_verified=False, foreground_pid=22412,
                               foreground_alt_unlock=None)

    def test_default_explicit_refusal_uses_one_authenticated_focus_and_retains_both_receipts(self):
        self.refused_default_focus()
        result = self.run_bootstrap(expected=identity(), default_focus=True)
        self.assertEqual(result['native_status'], 2)
        self.assertEqual(self.calls.count('focus'), 1)
        self.assertEqual(self.calls.count('focus-fallback'), 1)
        self.assertEqual(self.evidence['focus'], self.focused)
        self.assertEqual(self.evidence['focus_fallback'], self.fallback_result)
        self.assertTrue(self.evidence['focus_fallback_attempted'])
        self.assertTrue(self.evidence['game_window_verified'])
        self.assertTrue(any(record.get('focus_fallback') == self.fallback_result for record in self.records))
        self.assertFalse(any(action in ('test_input', 'overlay_show', 'overlay_hide') for action in self.calls))

    def test_successful_default_focus_does_not_launch_a_helper(self):
        self.run_bootstrap(default_focus=True)
        self.assertEqual(self.calls.count('focus'), 1)
        self.assertNotIn('focus-fallback', self.calls)
        self.assertFalse(self.evidence['focus_fallback_attempted'])

    def test_injected_explicit_focus_refusal_never_causes_hidden_elevation(self):
        self.refused_default_focus()
        with self.assertRaises(ValueError): self.run_bootstrap()
        self.assertEqual(self.calls, ['overlay_status', 'focus'])
        self.assertFalse(self.evidence['focus_fallback_attempted'])

    def test_lost_default_focus_is_never_replayed_by_helper(self):
        self.focused = OSError('Normal focus observation lost')
        with self.assertRaisesRegex(OSError, 'observation lost'): self.run_bootstrap(default_focus=True)
        self.assertEqual(self.calls, ['overlay_status', 'focus'])
        self.assertFalse(self.evidence['focus_fallback_attempted'])

    def test_ambiguous_refusal_foreign_canvas_or_possible_input_never_launches_helper(self):
        changes = ({'ok': 0}, {'foreground_verified': 0}, {'foreground_pid': True},
            {'foreground_verified': True}, {'request_state': 'unknown'}, {'outcome': 'unresolved'},
            {'input_submitted': None}, {'input_submitted': True}, {'input_sent': True},
            {'foreground_alt_unlock': {'attempted': True}},
            {'window': dict(focused()['window'], pid=43)},
            {'window': dict(focused()['window'], visible=False)},
            {'window': dict(focused()['window'], **{'class': 'EA-Window'})},
            {'window': dict(focused()['window'], hwnd=True)})
        for change in changes:
            with self.subTest(change=change):
                self.setUp(); self.refused_default_focus(); self.focused.update(change)
                with self.assertRaises(ValueError): self.run_bootstrap(default_focus=True)
                self.assertEqual(self.calls, ['overlay_status', 'focus'])
                self.assertFalse(self.evidence['focus_fallback_attempted'])

    def test_changed_pinned_bridge_after_normal_refusal_refuses_before_helper(self):
        for change in ({'pid': 43}, {'test_token': 'e' * 32}, {'script_sha256': 'e' * 64}):
            with self.subTest(change=change):
                self.setUp(); self.refused_default_focus()
                self.identities = [identity(), identity(), identity(**change)]
                with self.assertRaises(ValueError): self.run_bootstrap(default_focus=True)
                self.assertEqual(self.calls, ['overlay_status', 'focus'])
                self.assertFalse(self.evidence['focus_fallback_attempted'])

    def test_changed_pinned_bridge_during_helper_refuses_without_renderer_reads_or_replay(self):
        for change in ({'pid': 43}, {'test_token': 'e' * 32}, {'script_sha256': 'e' * 64}):
            with self.subTest(change=change):
                self.setUp(); self.refused_default_focus()
                self.identities = [identity(), identity(), identity(), identity(**change)]
                with self.assertRaises(ValueError): self.run_bootstrap(default_focus=True)
                self.assertEqual(self.calls, ['overlay_status', 'focus', 'focus-fallback'])
                self.assertEqual(self.evidence['focus_fallback'], self.fallback_result)
                self.assertFalse(self.evidence['game_window_verified'])

    def test_lost_or_unresolved_helper_keeps_one_attempt_without_following_input(self):
        for outcome in (TimeoutError('One focus helper acknowledgment lost'),
                focused(ok=False, foreground_verified=False),
                focused(automatic_pre_input_focus=True, focus_helper_proof='d' * 64, outcome='unresolved'),
                focused(automatic_pre_input_focus=True, focus_helper_proof='d' * 64, input_sent=None),
                focused(automatic_pre_input_focus=True, focus_helper_proof='d' * 64, foreground_pid=43),
                focused(automatic_pre_input_focus=True, focus_helper_proof='d' * 64,
                        window=dict(focused()['window'], pid=43)),
                focused(automatic_pre_input_focus=True, focus_helper_proof='not-a-sha')):
            with self.subTest(outcome=outcome):
                self.setUp(); self.refused_default_focus(); self.fallback_result = outcome
                with self.assertRaises((OSError, ValueError)): self.run_bootstrap(default_focus=True)
                self.assertEqual(self.calls, ['overlay_status', 'focus', 'focus-fallback'])
                self.assertTrue(self.evidence['focus_fallback_attempted'])
                self.assertFalse(self.evidence['game_window_verified'])
                self.assertIn('focus_error', self.evidence)

    def test_caller_deadline_after_normal_refusal_prevents_helper_dispatch(self):
        self.refused_default_focus()
        self.after_focus = lambda: setattr(self, 'clock', 4)
        base = self.bridge
        def deadline_bridge(state):
            if self.clock >= 3:
                raise TimeoutError('Caller observation deadline expired')
            return base(state)
        self.bridge = deadline_bridge
        with self.assertRaisesRegex(TimeoutError, 'Caller observation deadline'): self.run_bootstrap(default_focus=True)
        self.assertEqual(self.calls, ['overlay_status', 'focus'])
        self.assertFalse(self.evidence['focus_fallback_attempted'])

    def test_caller_deadline_after_helper_preserves_receipt_but_refuses_following_actions(self):
        self.refused_default_focus()
        self.after_fallback = lambda: setattr(self, 'clock', 4)
        base = self.bridge
        def deadline_bridge(state):
            if self.clock >= 3:
                raise TimeoutError('Caller observation deadline expired')
            return base(state)
        self.bridge = deadline_bridge
        with self.assertRaisesRegex(TimeoutError, 'Caller observation deadline'): self.run_bootstrap(default_focus=True)
        self.assertEqual(self.calls, ['overlay_status', 'focus', 'focus-fallback'])
        self.assertEqual(self.evidence['focus_fallback'], self.fallback_result)
        self.assertFalse(self.evidence['game_window_verified'])

    def test_helper_lease_late_success_never_authorizes_renderer_or_input(self):
        self.refused_default_focus()
        self.after_fallback = lambda: setattr(self, 'clock', game_focus.LEASE + 1)
        with self.assertRaisesRegex(TimeoutError, 'after its helper lease'): self.run_bootstrap(default_focus=True)
        self.assertEqual(self.calls, ['overlay_status', 'focus', 'focus-fallback'])
        self.assertEqual(self.evidence['focus_fallback'], self.fallback_result)
        self.assertFalse(self.evidence['game_window_verified'])


if __name__ == '__main__':
    unittest.main()
