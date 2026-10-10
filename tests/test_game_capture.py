from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_capture


def bmp():
    raw = bytearray(78)
    raw[:2] = b'BM'
    for offset, value, count in ((2, len(raw), 4), (10, 54, 4), (14, 40, 4),
                                 (18, 2, 4), (22, 3, 4), (26, 1, 2), (28, 24, 2), (34, 24, 4)):
        raw[offset:offset + count] = value.to_bytes(count, 'little')
    return bytes(raw)


def diagnostic():
    return {'ok': True, 'native_initializer_observed': False, 'native_peers': [], 'requests': [],
            'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021,
                                 'startup_error': None, 'native_connection_verified': False}}


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.profile, self.original = self.root / 'profile', self.root / 'original'
        (self.profile / 'TD1ApexScreenshots').mkdir(parents=True)
        (self.profile / 'saves').mkdir()
        (self.original / 'saves').mkdir(parents=True)
        (self.profile / 'saves/Slot_00000002.save').write_bytes(b'disposable save unchanged')
        (self.original / 'saves/Slot_00000002.save').write_bytes(b'protected owner save')
        (self.original / 'lastCrash.txt').write_bytes(b'protected owner crash')
        self.output = self.root / 'proof.bmp'
        self.visible, self.initialized, self.rendered = False, False, 0
        self.completed, self.clock, self.status_count = 0, 0.0, 0
        self.never_initialize = False
        self.initialization_status = 2
        self.diag, self.calls, self.handler = diagnostic(), [], None
        self.emit_capture = True
        self.raw = bmp()

    def status(self):
        return {'ok': True, 'native_status': 3 if self.initialized else 2,
                'game_window_verified': True, 'renderer_initialized': self.initialized,
                'rendered_frames': self.rendered, 'frame_submission_verified': self.rendered > 0,
                'captures_completed': self.completed, 'visible': self.visible,
                'runtime_verified': False, 'message': 'Old loaded script startup text'}

    def request(self, _state, action, **kwargs):
        self.calls.append((action, kwargs))
        if self.handler:
            result = self.handler(action, kwargs)
            if result is not None:
                return result
        if action == 'cas_ui_diagnostics':
            return self.diag
        if action == 'overlay_status':
            self.status_count += 1
            if self.visible and not self.never_initialize and self.status_count >= self.initialization_status:
                self.initialized, self.rendered = True, 7
            return self.status()
        if action in ('overlay_show', 'overlay_hide'):
            evidence = json.loads(self.output.with_suffix('.json').read_text(encoding='utf-8'))
            self.assertEqual(evidence['renderer_preparation']['steps'][-1], {'action': action, 'state': 'attempted'})
            self.visible = action == 'overlay_show'
            return dict(self.status(), request_id='a' * 32, request_state='completed')
        if action == 'test_capture':
            before = self.status()
            if self.emit_capture:
                mode = json.loads(kwargs['value'])['value']
                prefix = 'TD1Apex_overlay_' if mode == 'overlay' else 'TD1Apex_full_'
                (self.profile / 'TD1ApexScreenshots' / (prefix + 'one.bmp')).write_bytes(self.raw)  # Emulate game output.
                self.completed += 1
            return dict(before, native_code=0, capture_requested=True,
                        capture_completed_verified=False, request_id='b' * 32, request_state='completed')
        self.fail('Unexpected game action: ' + action)

    def run_capture(self, overlay=False):
        original = {str(path.relative_to(self.original)): path.read_bytes()
                    for path in self.original.rglob('*') if path.is_file()}
        with patch.object(game_capture.reusable_profile, 'load', return_value=(None,
                {'token': 'c' * 32, 'artifacts': []}, self.profile, self.original)):
            result = game_capture.capture('state', self.output, self.request, overlay=overlay,
                monotonic=lambda: self.clock, pause=lambda duration: setattr(self, 'clock', self.clock + duration))
        proof = json.loads(self.output.with_suffix('.json').read_text(encoding='utf-8'))
        self.assertEqual(result, proof)
        self.assertEqual(original, {str(path.relative_to(self.original)): path.read_bytes()
                                   for path in self.original.rglob('*') if path.is_file()})
        self.assertEqual((self.profile / 'saves/Slot_00000002.save').read_bytes(), b'disposable save unchanged')
        return result

    def test_hidden_ready_renderer_captures_without_any_visibility_or_cas_request(self):
        self.initialized, self.rendered = True, 1
        self.diag['native_peers'] = [{'sim_id': '4', 'age_seconds': 0}]
        result = self.run_capture()
        self.assertTrue(result['ok'])
        self.assertEqual(self.output.read_bytes(), self.raw)
        self.assertEqual((result['width'], result['height']), (2, 3))
        self.assertFalse(self.visible)
        self.assertFalse(any(action in ('overlay_show', 'overlay_hide', 'cas_ui_diagnostics') for action, _ in self.calls))

    def test_hidden_uninitialized_renderer_shows_once_then_hides_before_plain_capture(self):
        result = self.run_capture()
        self.assertTrue(result['ok'])
        self.assertFalse(self.visible)
        actions = [action for action, _ in self.calls]
        self.assertEqual(actions[:6], ['overlay_status', 'cas_ui_diagnostics', 'overlay_show',
                                      'overlay_status', 'overlay_hide', 'cas_ui_diagnostics'])
        self.assertLess(actions.index('overlay_hide'), actions.index('test_capture'))
        self.assertEqual(actions.count('overlay_show'), 1)
        self.assertEqual(actions.count('overlay_hide'), 1)
        self.assertEqual(actions.count('test_capture'), 1)
        self.assertTrue(result['renderer_preparation']['original_visibility_verified'])
        self.assertFalse(result['requested']['visible'])

    def test_visible_uninitialized_renderer_waits_without_show_or_hide_and_keeps_visibility(self):
        self.visible = True
        result = self.run_capture()
        self.assertTrue(result['ok'])
        self.assertTrue(self.visible)
        self.assertFalse(any(action in ('overlay_show', 'overlay_hide', 'cas_ui_diagnostics') for action, _ in self.calls))

    def test_attached_cas_refuses_hidden_initialization_without_show_capture_or_native_mutation(self):
        self.diag['native_peers'] = [{'sim_id': '4', 'age_seconds': 900}]
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertFalse(result['capture_submitted'])
        self.assertEqual([action for action, _ in self.calls], ['overlay_status', 'cas_ui_diagnostics'])
        self.assertEqual(result['renderer_preparation']['visibility_cas_guard']['outcome'], 'cas-active-refused')
        self.assertFalse(self.output.exists())

    def test_unresolved_accept_refuses_hidden_initialization_and_retains_uuid(self):
        self.diag['requests'] = [{'cas_request_id': 'd' * 32, 'state': 'accept-unresolved',
                                 'operation': 'accept', 'age_seconds': 1}]
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertEqual(result['renderer_preparation']['visibility_cas_guard']['blocking_native_requests'][0]['cas_request_id'], 'd' * 32)
        self.assertEqual([action for action, _ in self.calls], ['overlay_status', 'cas_ui_diagnostics'])

    def test_cas_appearing_during_initialization_is_hidden_and_capture_refused(self):
        def handler(action, _kwargs):
            if action == 'overlay_hide':
                self.diag['native_peers'] = [{'sim_id': '4', 'age_seconds': 0}]
        self.handler = handler
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertFalse(self.visible)
        self.assertTrue(result['renderer_preparation']['original_visibility_verified'])
        self.assertFalse(result['capture_submitted'])
        self.assertFalse(any(action == 'test_capture' for action, _ in self.calls))

    def test_missing_or_unknown_visibility_never_shows_or_captures(self):
        def handler(action, _kwargs):
            if action == 'overlay_status':
                return {'ok': True, 'renderer_initialized': False, 'native_status': 2}
        self.handler = handler
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertEqual([action for action, _ in self.calls], ['overlay_status'])

    def test_initialization_times_out_with_only_one_show_and_one_restoring_hide(self):
        self.never_initialize = True
        result = self.run_capture()
        self.assertFalse(result['ok'])
        actions = [action for action, _ in self.calls]
        self.assertEqual(actions.count('overlay_show'), 1)
        self.assertEqual(actions.count('overlay_hide'), 1)
        self.assertNotIn('test_capture', actions)
        self.assertLessEqual(self.clock, 3.001)
        self.assertFalse(self.visible)
        self.assertTrue(result['renderer_preparation']['original_visibility_verified'])

    def test_ambiguous_show_retains_uuid_hides_once_and_never_replays_show(self):
        def handler(action, _kwargs):
            if action == 'overlay_show':
                self.visible = True  # Command may have executed despite lost completion.
                return dict(self.status(), request_id='e' * 32, request_state='unknown', outcome='unresolved')
        self.handler = handler
        result = self.run_capture()
        self.assertFalse(result['ok'])
        steps = result['renderer_preparation']['steps']
        show = next(row for row in steps if row['action'] == 'overlay_show')
        self.assertEqual(show['result']['request_id'], 'e' * 32)
        self.assertEqual(show['state'], 'unresolved')
        self.assertEqual(sum(action == 'overlay_show' for action, _ in self.calls), 1)
        self.assertEqual(sum(action == 'overlay_hide' for action, _ in self.calls), 1)
        self.assertFalse(any(action == 'test_capture' for action, _ in self.calls))
        self.assertFalse(self.visible)

    def test_failed_hide_is_never_replayed_or_followed_by_plain_capture(self):
        def handler(action, _kwargs):
            if action == 'overlay_hide':
                return dict(self.status(), ok=False, request_id='f' * 32, request_state='unknown')
        self.handler = handler
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'visibility-unresolved')
        self.assertFalse(result['capture_submitted'])
        self.assertEqual(sum(action == 'overlay_hide' for action, _ in self.calls), 1)
        self.assertFalse(any(action == 'test_capture' for action, _ in self.calls))

    def test_overlay_image_captures_while_borrowed_visible_then_restores_hidden(self):
        result = self.run_capture(overlay=True)
        self.assertTrue(result['ok'])
        self.assertTrue(result['requested']['visible'])
        self.assertFalse(self.visible)
        actions = [action for action, _ in self.calls]
        self.assertGreater(actions.index('overlay_hide'), actions.index('test_capture'))
        self.assertEqual(actions.count('test_capture'), 1)

    def test_lost_capture_response_is_not_replayed_and_borrowed_visibility_restored(self):
        def handler(action, _kwargs):
            if action == 'test_capture':
                raise TimeoutError('native capture response lost')
        self.handler = handler
        result = self.run_capture(overlay=True)
        self.assertFalse(result['ok'])
        self.assertTrue(result['capture_attempted'])
        self.assertIsNone(result['capture_submitted'])
        self.assertIn('response lost', result['error'])
        self.assertEqual(sum(action == 'test_capture' for action, _ in self.calls), 1)
        self.assertFalse(self.visible)

    def test_missing_unique_image_times_out_without_capture_replay(self):
        self.initialized, self.rendered, self.emit_capture = True, 1, False
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'unresolved')
        self.assertEqual(sum(action == 'test_capture' for action, _ in self.calls), 1)
        self.assertFalse(self.output.exists())
        self.assertLessEqual(self.clock, 5.101)

    def test_bad_capture_bytes_preserve_failure_proof_without_output_or_replay(self):
        self.initialized, self.rendered, self.raw = True, 1, b'not an actual BMP'
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertIn('bounded BMP', result['error'])
        self.assertFalse(self.output.exists())
        self.assertEqual(sum(action == 'test_capture' for action, _ in self.calls), 1)

    def test_existing_evidence_and_profile_or_original_targets_refuse_without_requests(self):
        self.output.with_suffix('.json').write_text('old proof', encoding='utf-8')
        with patch.object(game_capture.reusable_profile, 'load', return_value=(None,
                {'token': 'c' * 32, 'artifacts': []}, self.profile, self.original)):
            for output in (self.output, self.profile / 'capture.bmp', self.original / 'capture.bmp'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    game_capture.capture('state', output, self.request)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.output.with_suffix('.json').read_text(encoding='utf-8'), 'old proof')

    def test_renderer_evidence_rejects_boolean_counters_and_contradictory_flags(self):
        good = self.status()
        for change in ({'native_status': True}, {'visible': 0}, {'renderer_initialized': True},
                       {'rendered_frames': True}, {'captures_completed': True}, {'frame_submission_verified': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                game_capture.renderer_status(dict(good, **change))

    def test_explicit_capture_refusal_proves_no_submission_without_replay(self):
        self.initialized, self.rendered = True, 1
        def handler(action, _kwargs):
            if action == 'test_capture':
                return dict(self.status(), ok=False, native_code=-2, capture_requested=False, request_id='e' * 32)
        self.handler = handler
        result = self.run_capture()
        self.assertFalse(result['ok'])
        self.assertTrue(result['capture_attempted'])
        self.assertFalse(result['capture_submitted'])
        self.assertEqual(result['requested']['request_id'], 'e' * 32)
        self.assertEqual(sum(action == 'test_capture' for action, _ in self.calls), 1)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
