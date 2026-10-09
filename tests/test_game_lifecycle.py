from pathlib import Path
import json
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ea_native_permission
import game_lifecycle


def live_cas_diagnostics():
    return {'ok': True, 'native_initializer_observed': False, 'native_peers': [], 'requests': [],
            'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021,
                                 'startup_error': None, 'native_connection_verified': False}}


def observed(labels, width=1278, height=1376):
    return {'ok': True, 'width': width, 'height': height,
            'lines': [{'text': text, 'words': [{'text': text, 'x': 500, 'y': 400 + index * 30,
                                               'width': 150, 'height': 20}]} for index, text in enumerate(labels)]}


class LifecycleTests(unittest.TestCase):
    def resume_surface(self):
        return observed(['HOME', 'MARKETPLACE', 'RESUME GAME', 'LOAD GAME', 'NEW GAME', 'GALLERY'])

    def loaded_snapshot(self, sim_id='285159751289798669'):
        return {'ok': True, 'save_slot': 2, 'save_guid': '1841692672',
                'zone_id': '285159751312710719', 'household_id': '285159751289798668',
                'in_build_buy': False, 'sim': {'id': sim_id, 'instanced': True}}

    def run_resume(self, *, inputs=None, snapshots=None, frames=None, sim_id=None,
                   seconds=3, mismatched_viewport=False, household_id=None, save_guid=None,
                   cas_diagnostic=None, pause_result=None, identities=None, initial_bridge=None,
                   command_times=None, identity_delays=None, game_processes=None,
                   use_default_identity=False):
        inputs = list(inputs or [{'ok': True}])
        snapshots = list(snapshots or [self.loaded_snapshot()])
        frames = list(frames or [self.resume_surface()])
        cas_values = list(cas_diagnostic) if isinstance(cas_diagnostic, list) else None
        calls, clock = [], [0.0]
        initial_identity = ({'pid': 42, 'test_token': 'a' * 32, 'script_sha256': 'b' * 64,
                             'core_tick_ready': True, 'alarm_ready': False}
                            if initial_bridge is None else initial_bridge)
        bridge_values = list(identities) if identities is not None else [initial_identity]
        delays = list(identity_delays or [])
        def identity_provider(_state):
            if delays:
                clock[0] += delays.pop(0)
            value = bridge_values.pop(0) if len(bridge_values) > 1 else bridge_values[0]
            if isinstance(value, Exception):
                raise value
            return value
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile, original = root / 'profile', root / 'original'
            (profile / 'saves').mkdir(parents=True); original.mkdir()
            (profile / 'saves/Slot_00000002.save').write_bytes(b'previously saved test household')
            (original / 'owner-save').write_bytes(b'protected original')
            def request(_state, action, **kwargs):
                if command_times is not None:
                    command_times.append((action, clock[0]))
                calls.append((action, kwargs))
                if action == 'test_input':
                    return inputs.pop(0)
                if action == 'cas_ui_diagnostics':
                    if cas_values is not None:
                        return cas_values.pop(0) if len(cas_values) > 1 else cas_values[0]
                    return live_cas_diagnostics() if cas_diagnostic is None else cas_diagnostic
                if action in ('overlay_status', 'overlay_hide'):
                    return {'ok': True, 'native_status': 3, 'visible': False,
                        'game_window_verified': True, 'renderer_initialized': True,
                        'rendered_frames': 3, 'frame_submission_verified': True, 'captures_completed': 0}
                if action == 'test_pause':
                    if isinstance(pause_result, Exception): raise pause_result
                    return {'ok': True} if pause_result is None else pause_result
                if action == 'test_snapshot':
                    result = snapshots.pop(0) if snapshots else {'ok': False}
                    if isinstance(result, Exception):
                        raise result
                    return result
                return {'ok': True}
            def capture(_state, _image, _request):
                calls.append(('capture', {}))
                return {'ok': True, 'width': 1277 if mismatched_viewport else 1278,
                        'height': 1376, 'sha256': 'a' * 64}
            def ocr(_image):
                return frames.pop(0) if len(frames) > 1 else frames[0]
            with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                    {'token': 'a' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'b' * 64}]}, profile, original)):
                result = game_lifecycle.resume('state', root / 'proof.json', initial_identity, request,
                    sim_id=sim_id, seconds=seconds, capture=capture, ocr=ocr,
                    processes=(lambda: [{'Id': 42}]) if game_processes is None else lambda: game_processes(clock[0]),
                    monotonic=lambda: clock[0],
                    pause=lambda duration: clock.__setitem__(0, clock[0] + duration),
                    household_id=household_id, save_guid=save_guid,
                    identity_provider=None if use_default_identity else identity_provider)
            proof = json.loads((root / 'proof.json').read_text(encoding='utf-8'))
            self.assertEqual((original / 'owner-save').read_bytes(), b'protected original')
            self.assertEqual((profile / 'saves/Slot_00000002.save').read_bytes(), b'previously saved test household')
        return result, proof, calls

    def test_startup_waits_for_fresh_core_owner_before_any_request_and_does_not_need_live_alarm(self):
        cold = self.ready_bridge(False, core_tick_ready=False)
        warm = self.ready_bridge(False)
        timing = []
        result, proof, calls = self.run_resume(initial_bridge=cold, identities=[cold, warm],
            command_times=timing, seconds=2)
        self.assertTrue(result['ok'])
        self.assertEqual(proof['bridge_readiness']['wait_seconds'], .5)
        self.assertEqual(proof['bridge_readiness']['owner_source'], 'core-owner-tick')
        self.assertFalse(proof['bridge_readiness']['last_bridge']['alarm_ready'])
        self.assertTrue(all(at >= .5 for _action, at in timing))
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
        self.assertEqual(proof['identity'], cold)

    def test_default_startup_observer_binds_http_timeout_to_remaining_deadline(self):
        import apex_cli
        cold = self.ready_bridge(False, core_tick_ready=False)
        observed_budgets = []
        def get(path, query=None, timeout=None):
            self.assertEqual(path, '/api/bridge')
            observed_budgets.append(timeout)
            return self.ready_bridge(False)
        def verified(state, transport):
            self.assertEqual(state, 'state')
            return transport('/api/bridge')
        with patch.object(apex_cli, 'get', side_effect=get), \
                patch.object(apex_cli, 'verified_identity', side_effect=verified):
            result, proof, calls = self.run_resume(initial_bridge=cold, use_default_identity=True, seconds=1)
        self.assertTrue(result['ok'])
        self.assertEqual(observed_budgets, [.75])
        self.assertEqual(proof['bridge_readiness']['wait_seconds'], .25)
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)

    def test_startup_deadline_preserves_original_identity_and_sends_no_commands_or_input(self):
        cold = self.ready_bridge(False, core_tick_ready=False)
        result, proof, calls = self.run_resume(initial_bridge=cold, identities=[cold], seconds=.75)
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'bridge-startup-unresolved')
        self.assertEqual(calls, [])
        self.assertEqual(proof['bridge_readiness']['observations'], 3)
        self.assertEqual(proof['bridge_readiness']['wait_seconds'], .75)
        self.assertEqual(proof['identity'], cold)
        self.assertFalse(result['resume_input_accepted'])

    def test_startup_foreign_pid_token_or_script_refuses_before_any_game_thread_request(self):
        cold = self.ready_bridge(False, core_tick_ready=False)
        for changes in ({'pid': 99}, {'pid': True}, {'test_token': 'c' * 32}, {'script_sha256': 'c' * 64}):
            with self.subTest(changes=changes):
                result, proof, calls = self.run_resume(initial_bridge=cold,
                    identities=[self.ready_bridge(False, **changes)])
                self.assertFalse(result['ok']); self.assertEqual(calls, [])
                self.assertEqual(result['outcome'], 'bridge-identity-refused')
                self.assertEqual(proof['identity'], cold)

    def test_startup_unknown_or_coerced_readiness_refuses_without_input(self):
        cold = self.ready_bridge(False, core_tick_ready=False)
        for changes in ({'core_tick_ready': 1}, {'alarm_ready': 'yes'}, {'core_tick_ready': None}):
            with self.subTest(changes=changes):
                result, proof, calls = self.run_resume(initial_bridge=cold,
                    identities=[self.ready_bridge(False, **changes)])
                self.assertFalse(result['ok']); self.assertEqual(calls, [])
                self.assertEqual(result['outcome'], 'bridge-readiness-unknown')

    def test_startup_transient_observation_loss_waits_without_replaying_a_command(self):
        cold = self.ready_bridge(False, core_tick_ready=False)
        timing = []
        result, proof, calls = self.run_resume(initial_bridge=cold,
            identities=[OSError('bridge read temporarily unavailable'), self.ready_bridge(False)],
            command_times=timing, seconds=2)
        self.assertTrue(result['ok'])
        self.assertIn('temporarily unavailable', proof['bridge_readiness']['last_observation_error'])
        self.assertTrue(all(at >= .5 for _action, at in timing))
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)

    def test_startup_process_exit_and_late_ready_observation_cannot_authorize_input(self):
        cold = self.ready_bridge(False, core_tick_ready=False)
        for options, outcome in (({'game_processes': lambda at: [] if at >= .25 else [{'Id': 42}]},
                                   'verified-game-exited'),
                                  ({'identity_delays': [1]}, 'bridge-startup-unresolved')):
            with self.subTest(outcome=outcome):
                result, proof, calls = self.run_resume(initial_bridge=cold,
                    identities=[self.ready_bridge(False)], seconds=.5, **options)
                self.assertFalse(result['ok']); self.assertEqual(calls, [])
                self.assertEqual(result['outcome'], outcome)

    def test_readiness_and_post_resume_observation_share_one_advertised_deadline(self):
        cold = self.ready_bridge(False, core_tick_ready=False)
        timing = []
        result, proof, calls = self.run_resume(initial_bridge=cold,
            identities=[cold, cold, self.ready_bridge(False)], snapshots=[{'ok': False}],
            command_times=timing, seconds=1)
        self.assertFalse(result['ok']); self.assertTrue(result['resume_input_accepted'])
        self.assertEqual(proof['bridge_readiness']['wait_seconds'], .75)
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
        self.assertTrue(all(at < 1 for _action, at in timing))

    def test_resume_requires_complete_home_surface_not_just_a_matching_word(self):
        self.assertEqual(game_lifecycle.button(self.resume_surface(), 'resume')['y'], 470)
        for labels in (['RESUME GAME'], ['HOME', 'MARKETPLACE', 'LOAD GAME', 'NEW GAME', 'GALLERY'],
                       ['HOME', 'MARKETPLACE', 'RESUME GAME', 'RESUME', 'LOAD GAME', 'NEW GAME', 'GALLERY']):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                game_lifecycle.button(observed(labels), 'resume')

    def already_live(self, clock=1):
        result = self.loaded_snapshot()
        result.update(save_slot=0xffffffff, clock_speed=clock, zone_running=True, client_id='44',
            runtime_queries={'client_id': 'returned-value', 'zone_running': 'returned-value'},
            persistence={'persistence_verified_before_save': True, 'checks': {name: True for name in
                ('active_household_membership', 'runtime_household_identity', 'manager_identity', 'account_save_eligible',
                 'sim_proto_exists', 'sim_proto_identity', 'sim_proto_household_identity', 'household_proto_exists',
                 'household_proto_identity', 'household_proto_membership')}})
        return result

    def ready_bridge(self, ready=True, **changes):
        return {'pid': 42, 'test_token': 'a' * 32, 'script_sha256': 'b' * 64,
                'core_tick_ready': True, 'alarm_ready': ready, **changes}

    def test_live_readiness_arrives_after_renderer_and_bypasses_all_home_input(self):
        live, paused = self.already_live(), self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=live['sim']['id'], household_id=live['household_id'],
            save_guid=live['save_guid'], snapshots=[{'ok': False}, live, paused],
            identities=[self.ready_bridge()])
        self.assertTrue(result['native_live_verified'])
        self.assertEqual(result['outcome'], 'existing-household-already-loaded')
        self.assertFalse(result['resume_input_accepted'])
        self.assertEqual(sum(action == 'test_pause' for action, _ in calls), 1)
        self.assertFalse(any(action in ('capture', 'test_input', 'overlay_hide') for action, _ in calls))
        self.assertTrue(any(step['action'] == 'post-renderer-existing-live-snapshot' for step in proof['steps']))

    def test_live_appears_during_capture_and_is_verified_without_using_bitmap_as_proof(self):
        live = self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=live['sim']['id'], household_id=live['household_id'],
            save_guid=live['save_guid'], snapshots=[{'ok': False}, live, live], frames=[observed(['PAUSED'])],
            identities=[self.ready_bridge(False), self.ready_bridge(False), self.ready_bridge()])
        self.assertTrue(result['native_live_verified'])
        self.assertFalse(result['resume_input_accepted'])
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 1)
        self.assertFalse(any(action in ('test_input', 'test_pause') for action, _ in calls))
        self.assertFalse(any(step['action'] == 'recognize-resume' for step in proof['steps']))
        self.assertTrue(any(step['action'] == 'post-capture-existing-live-1-snapshot' for step in proof['steps']))

    def test_live_arrives_after_home_recognition_and_prevents_stale_resume_click(self):
        live = self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=live['sim']['id'], household_id=live['household_id'],
            save_guid=live['save_guid'], snapshots=[{'ok': False}, live, live],
            identities=[self.ready_bridge(False)] * 3 + [self.ready_bridge()])
        self.assertTrue(result['native_live_verified'])
        self.assertFalse(result['resume_input_accepted'])
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 1)
        self.assertFalse(any(action == 'test_input' for action, _ in calls))
        self.assertTrue(any(step['action'] == 'recognize-resume' for step in proof['steps']))
        self.assertTrue(any(step['action'] == 'pre-input-existing-live-1-snapshot' for step in proof['steps']))

    def test_late_live_wrong_identity_or_manager_never_pauses_or_submits_home_input(self):
        original = self.already_live()
        for changed in ['household_id', 'save_guid', 'sim', 'manager']:
            live = self.already_live()
            if changed == 'sim': live['sim']['id'] = '99'
            elif changed == 'manager': live['persistence']['checks']['manager_identity'] = False
            else: live[changed] = '99'
            with self.subTest(changed=changed):
                result, proof, calls = self.run_resume(sim_id=original['sim']['id'],
                    household_id=original['household_id'], save_guid=original['save_guid'],
                    snapshots=[{'ok': False}, live], identities=[self.ready_bridge()])
                self.assertFalse(result['native_live_verified'])
                self.assertFalse(result['resume_input_accepted'])
                self.assertFalse(any(action in ('test_pause', 'test_input', 'capture') for action, _ in calls))

    def test_late_bridge_pid_token_or_script_change_is_refused_before_home_input(self):
        live = self.already_live(clock=0)
        for changes in [{'pid': 99}, {'test_token': 'c' * 32}, {'script_sha256': 'c' * 64}]:
            with self.subTest(changes=changes):
                result, proof, calls = self.run_resume(sim_id=live['sim']['id'], household_id=live['household_id'],
                    save_guid=live['save_guid'], snapshots=[{'ok': False}],
                    identities=[self.ready_bridge(**changes)])
                self.assertFalse(result['ok'])
                self.assertIn('exact process/profile/script', proof['error'])
                self.assertFalse(any(action in ('test_pause', 'test_input', 'capture') for action, _ in calls))

    def test_live_looking_capture_without_alarm_or_native_live_proof_remains_unresolved(self):
        live = self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=live['sim']['id'], household_id=live['household_id'],
            save_guid=live['save_guid'], snapshots=[{'ok': False}], frames=[observed(['PAUSED'])],
            identities=[self.ready_bridge(False)])
        self.assertFalse(result['native_live_verified'])
        self.assertFalse(result['resume_input_accepted'])
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 3)
        self.assertEqual(sum(action == 'test_snapshot' for action, _ in calls), 1)
        self.assertFalse(any(action == 'test_input' for action, _ in calls))

    def test_already_live_exact_household_pauses_once_without_capture_or_resume_or_disk_slot_claim(self):
        before, after = self.already_live(), self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=before['sim']['id'], household_id=before['household_id'],
            save_guid=before['save_guid'], snapshots=[before, after])
        self.assertTrue(result['ok']); self.assertTrue(result['native_live_verified'])
        self.assertEqual(result['outcome'], 'existing-household-already-loaded')
        self.assertFalse(result['resume_input_accepted']); self.assertFalse(result['household_loaded_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual([action for action, kwargs in calls], ['test_snapshot', 'cas_ui_diagnostics', 'test_pause',
                                                              'test_snapshot', 'cas_ui_diagnostics'])
        self.assertTrue(proof['pause_submission_attempted'])

    def test_already_paused_live_reads_back_exact_context_without_redundant_pause(self):
        before = self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=before['sim']['id'], household_id=before['household_id'],
            save_guid=before['save_guid'], snapshots=[before, before])
        self.assertTrue(result['ok']); self.assertFalse(proof['pause_submission_attempted'])
        self.assertEqual([action for action, kwargs in calls], ['test_snapshot', 'cas_ui_diagnostics', 'test_snapshot',
                                                              'cas_ui_diagnostics'])

    def test_wrong_sim_household_guid_or_unknown_cas_never_pause_or_resume(self):
        before = self.already_live(clock=0)
        for changed in ('sim', 'household', 'guid', 'cas'):
            expected = {'sim_id': before['sim']['id'], 'household_id': before['household_id'], 'save_guid': before['save_guid']}
            if changed == 'sim': expected['sim_id'] = '99'
            elif changed == 'household': expected['household_id'] = '99'
            elif changed == 'guid': expected['save_guid'] = '99'
            result, proof, calls = self.run_resume(**expected, snapshots=[before],
                cas_diagnostic={} if changed == 'cas' else None)
            with self.subTest(changed=changed):
                self.assertFalse(result['ok']); self.assertFalse(proof['resume_input_accepted'])
                self.assertFalse(any(action in ('test_pause', 'test_input', 'capture') for action, kwargs in calls))

    def test_lost_pause_response_is_not_replayed_and_changed_postpause_context_refuses(self):
        before = self.already_live()
        options = {'sim_id': before['sim']['id'], 'household_id': before['household_id'], 'save_guid': before['save_guid']}
        for failure in (OSError('response lost'), {'ok': False}):
            result, proof, calls = self.run_resume(**options, snapshots=[before], pause_result=failure)
            with self.subTest(failure=failure):
                self.assertFalse(result['ok']); self.assertTrue(proof['pause_submission_attempted'])
                self.assertEqual(sum(action == 'test_pause' for action, kwargs in calls), 1)
                self.assertFalse(any(action in ('test_input', 'capture') for action, kwargs in calls))
        after = self.already_live(clock=0); after['zone_id'] = '66'
        result, proof, calls = self.run_resume(**options, snapshots=[before, after])
        self.assertFalse(result['ok']); self.assertFalse(result['native_live_verified'])

    def test_resume_rejects_pack_card_and_duplicate_resume_even_with_background_menu(self):
        for extra in ('EXPANSION PACK', 'BUY NOW', 'RESUME GAME', 'Cancel'):
            frame = self.resume_surface()
            frame['lines'].append(observed([extra])['lines'][0])
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                game_lifecycle.button(frame, 'resume')
        failed_ocr = dict(self.resume_surface(), ok=False)
        with self.assertRaises(ValueError):
            game_lifecycle.button(failed_ocr, 'resume')

    def test_resume_proves_existing_live_household_after_one_press_and_waits_for_loading(self):
        expected = '285159751289798669'
        result, proof, calls = self.run_resume(sim_id=expected,
            snapshots=[ValueError('Load the disposable household before in-game commands.'), self.loaded_snapshot(expected)])
        self.assertTrue(result['ok'])
        self.assertTrue(result['household_loaded_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 1)
        snapshot_calls = [kwargs for action, kwargs in calls if action == 'test_snapshot']
        self.assertEqual([row['sim_id'] for row in snapshot_calls], [expected, expected])
        self.assertEqual(proof['loaded_household']['sim']['id'], expected)

    def test_post_resume_auto_slot_pauses_once_and_verifies_exact_live_without_disk_slot_claim(self):
        live, paused = self.already_live(), self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=live['sim']['id'], household_id=live['household_id'],
            save_guid=live['save_guid'], snapshots=[{'ok': False}, live, paused], seconds=60)
        self.assertTrue(result['ok']); self.assertTrue(result['native_live_verified'])
        self.assertEqual(result['outcome'], 'existing-household-resumed-live')
        self.assertTrue(result['resume_input_accepted']); self.assertFalse(result['household_loaded_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertTrue(proof['pause_submission_attempted'])
        self.assertEqual(sum(action == 'test_pause' for action, _ in calls), 1)
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
        self.assertEqual(sum(action == 'test_snapshot' for action, _ in calls), 3)
        self.assertEqual(proof['loaded_household']['clock_speed'], 0)

    def test_post_resume_already_paused_auto_does_not_submit_another_pause(self):
        live = self.already_live(clock=0)
        result, proof, calls = self.run_resume(sim_id=live['sim']['id'], household_id=live['household_id'],
            save_guid=live['save_guid'], snapshots=[{'ok': False}, live, live], seconds=60)
        self.assertTrue(result['native_live_verified'])
        self.assertFalse(proof['pause_submission_attempted'])
        self.assertFalse(any(action == 'test_pause' for action, _ in calls))

    def test_post_resume_wrong_live_identity_refuses_without_pause_or_resume_replay(self):
        original = self.already_live()
        for changed in ('household_id', 'save_guid', 'sim'):
            live = self.already_live()
            if changed == 'sim': live['sim']['id'] = '99'
            else: live[changed] = '99'
            with self.subTest(changed=changed):
                result, proof, calls = self.run_resume(sim_id=original['sim']['id'],
                    household_id=original['household_id'], save_guid=original['save_guid'],
                    snapshots=[{'ok': False}, live], seconds=60)
                self.assertFalse(result['ok']); self.assertFalse(result['native_live_verified'])
                self.assertTrue(proof['resume_input_accepted'])
                self.assertFalse(any(action == 'test_pause' for action, _ in calls))
                self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)

    def test_post_resume_lost_pause_changed_context_or_new_cas_never_claim_live(self):
        live = self.already_live()
        options = {'sim_id': live['sim']['id'], 'household_id': live['household_id'], 'save_guid': live['save_guid']}
        for refusal in (OSError('pause response lost'), {'ok': True, 'request_state': 'unknown'}):
            with self.subTest(refusal=refusal):
                result, proof, calls = self.run_resume(**options, snapshots=[{'ok': False}, live], pause_result=refusal)
                self.assertFalse(result['native_live_verified'])
                self.assertTrue(proof['pause_submission_attempted'])
                self.assertEqual(sum(action == 'test_pause' for action, _ in calls), 1)
                self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
        changed = self.already_live(clock=0); changed['client_id'] = '99'
        result, proof, calls = self.run_resume(**options, snapshots=[{'ok': False}, live, changed])
        self.assertFalse(result['native_live_verified'])
        self.assertEqual(sum(action == 'test_pause' for action, _ in calls), 1)
        result, proof, calls = self.run_resume(**options, snapshots=[{'ok': False}, live, self.already_live(clock=0)],
            cas_diagnostic=[live_cas_diagnostics(), live_cas_diagnostics(), {}])
        self.assertFalse(result['native_live_verified'])
        self.assertEqual(proof['resumed_live_cas_settled_guard']['outcome'], 'cas-state-unknown')

    def test_resume_successful_input_does_not_repeat_when_household_proof_is_wrong(self):
        invalid = self.loaded_snapshot('other Sim')
        result, proof, calls = self.run_resume(sim_id='285159751289798669', snapshots=[invalid])
        self.assertFalse(result['ok'])
        self.assertTrue(result['resume_input_accepted'])
        self.assertFalse(proof['household_loaded_verified'])
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)

    def test_resume_ambiguous_or_other_native_failure_cannot_replay_input(self):
        for failure in ({'ok': False}, {'ok': False, 'input_version': 2, 'input_submitted': False, 'native_code': -7},
                        {'ok': False, 'input_version': 2, 'input_submitted': True, 'native_code': -2}):
            result, _proof, calls = self.run_resume(inputs=[failure])
            with self.subTest(failure=failure):
                self.assertFalse(result['ok'])
                self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
                self.assertFalse(any(action == 'test_snapshot' for action, _ in calls))

    def test_resume_only_explicit_minus_two_before_input_can_reobserve_and_retry(self):
        refusal = {'ok': False, 'input_version': 2, 'input_submitted': False, 'native_code': -2}
        result, _proof, calls = self.run_resume(inputs=[refusal, {'ok': True}])
        self.assertTrue(result['ok'])
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 2)
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 2)
        actions = [action for action, _ in calls]
        self.assertEqual(actions[:7], ['overlay_status', 'cas_ui_diagnostics', 'overlay_hide', 'capture',
                                       'test_input', 'capture', 'test_input'])

    def test_resume_refused_cursor_move_reobserves_before_one_new_button_attempt(self):
        refusal = {'ok': False, 'input_version': 2, 'input_submitted': False,
                   'native_code': 0, 'input_state': -7}
        result, _proof, calls = self.run_resume(inputs=[refusal, {'ok': True}])
        self.assertTrue(result['ok'])
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 2)
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 2)

    def test_resume_checks_renderer_before_hide_and_refuses_unknown_cas_without_input(self):
        result, proof, calls = self.run_resume(cas_diagnostic={})
        self.assertFalse(result['ok'])
        self.assertTrue(proof['renderer_bootstrap']['game_window_verified'])
        self.assertEqual([action for action, _ in calls], ['overlay_status', 'cas_ui_diagnostics'])
        self.assertFalse(any(action in ('overlay_hide', 'capture', 'test_input') for action, _ in calls))

    def test_resume_never_clicks_a_pack_card_or_a_changed_viewport(self):
        card = self.resume_surface()
        card['lines'].append(observed(['BUY NOW'])['lines'][0])
        for options in ({'frames': [card]}, {'mismatched_viewport': True}):
            result, _proof, calls = self.run_resume(**options)
            with self.subTest(options=options):
                self.assertFalse(result['ok'])
                self.assertFalse(any(action == 'test_input' for action, _ in calls))

    def test_loaded_household_rejects_scratch_slot_unsaved_game_and_non_live_sim(self):
        good = self.loaded_snapshot()
        prior = {'Slot_00000002.save': {}}
        self.assertTrue(game_lifecycle.loaded_household(good, prior))
        for change in ({'save_slot': 0xffffffff}, {'save_slot': 0}, {'save_slot': 3},
                       {'household_id': None}, {'in_build_buy': True},
                       {'sim': {'id': good['sim']['id'], 'instanced': False}}):
            with self.subTest(change=change):
                self.assertFalse(game_lifecycle.loaded_household(dict(good, **change), prior))

    def test_confirmation_requires_complete_prompt_and_one_save_and_exit(self):
        frame = observed(['SAVE GAME?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Exit Game', 'Cancel'])
        self.assertEqual(game_lifecycle.button(frame, 'confirmation')['y'], 470)
        frame['lines'].append(frame['lines'][2])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            game_lifecycle.button(frame, 'confirmation')
        with self.assertRaisesRegex(ValueError, 'not recognized'):
            game_lifecycle.button(observed(['Exit Game', 'Save and Exit']), 'confirmation')

    def test_confirmation_cannot_be_mistaken_for_main_menu(self):
        frame = observed(['MENU', 'Save', 'Save As...', 'Exit Game', 'SAVE GAME?'])
        with self.assertRaisesRegex(ValueError, 'main menu'):
            game_lifecycle.button(frame, 'menu')
        with self.assertRaisesRegex(ValueError, 'viewport'):
            game_lifecycle.button(observed(['MENU', 'Save', 'Save As...', 'Exit Game'], width=400), 'menu')

    def test_ea_access_error_cannot_trigger_the_permission_handler(self):
        frame = observed(['You don’t have access', 'Log in to a different account or restart the app to try again.', 'OK', 'CLOSE'])
        with self.assertRaisesRegex(ValueError, 'exact EA'):
            ea_native_permission.dialog_button(frame)
        exact = observed(['This game requires permissions',
            'This game requires administrative privileges. Do you want to grant access and launch the game?', 'OK', 'CLOSE'])
        exact['lines'][-1]['words'][0].update(x=720, y=460)
        self.assertEqual(ea_native_permission.dialog_button(exact), (575, 470))

    def test_shutdown_proves_real_slot_rewrite_and_never_touches_scratch_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile, original = root / 'profile', root / 'original'
            (profile / 'saves').mkdir(parents=True); original.mkdir()
            slot = profile / 'saves/Slot_00000002.save'; slot.write_bytes(b'original test save')
            scratch = profile / 'saves/Slot_ffffffff.save'; scratch.write_bytes(b'CAS scratch original')
            frames = [observed(['MENU', 'Save', 'Save As...', 'Exit Game']),
                      observed(['SAVE GAME?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Exit Game', 'Cancel'])]
            calls = []
            def request(_state, action, **kwargs):
                calls.append((action, kwargs))
                if action == 'cas_ui_diagnostics':
                    return live_cas_diagnostics()
                if action == 'test_input' and len([row for row in calls if row[0] == 'test_input']) == 2:
                    slot.write_bytes(b'native rewritten save')
                return {'ok': True}
            def capture(_state, _image, _request):
                return {'ok': True, 'width': 1278, 'height': 1376, 'sha256': 'a' * 64}
            with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                    {'token': 'a' * 32, 'artifacts': []}, profile, original)):
                result = game_lifecycle.shutdown('state', root / 'proof.json', {'pid': 42}, request,
                    capture=capture, ocr=lambda _: frames.pop(0), processes=lambda: [], pause=lambda _: None)
            self.assertTrue(result['ok'])
            self.assertFalse(result['save_reload_verified'])
            self.assertEqual(scratch.read_bytes(), b'CAS scratch original')
            self.assertTrue(result['normal_exit_verified'])
            self.assertEqual(result['outcome'], 'normal-save-and-exit')
            self.assertEqual([action for action, _ in calls],
                             ['cas_ui_diagnostics', 'overlay_hide', 'cas_ui_diagnostics', 'test_input',
                              'cas_ui_diagnostics', 'test_input'])

    def test_only_explicit_native_refusal_before_button_down_can_be_reobserved_and_retried(self):
        self.assertTrue(game_lifecycle.refused_before_input(dict(input_version=2,input_submitted=False,input_state=-7)))
        self.assertTrue(game_lifecycle.refused_before_input(dict(input_version=2,input_submitted=False,native_code=-2)))
        for result in ({'ok':False},dict(input_version=2,input_submitted=False,input_state=-5),
                       dict(input_version=2,input_submitted=True,input_state=-7),dict(input_version=1,input_submitted=False,input_state=-7)):
            self.assertFalse(game_lifecycle.refused_before_input(result))

    def test_process_exit_without_save_rewrite_is_not_a_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile, original = root / 'profile', root / 'original'
            (profile / 'saves').mkdir(parents=True); original.mkdir()
            (profile / 'saves/Slot_00000002.save').write_bytes(b'unchanged test save')
            frames = [observed(['MENU', 'Save', 'Save As...', 'Exit Game']),
                      observed(['SAVE GAME?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Exit Game', 'Cancel'])]
            with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                    {'token': 'a' * 32, 'artifacts': []}, profile, original)):
                result = game_lifecycle.shutdown('state', root / 'proof.json', {'pid': 42},
                    lambda _state, action, **_kwargs: live_cas_diagnostics() if action == 'cas_ui_diagnostics' else {'ok': True},
                    capture=lambda *_: {'ok': True, 'width': 1278, 'height': 1376},
                    ocr=lambda _: frames.pop(0), processes=lambda: [], pause=lambda _: None)
            self.assertTrue(result['game_exit_verified'])
            self.assertFalse(result['save_completed_file_verified'])
            self.assertFalse(result['ok'])


class ShutdownGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.profile, self.original = self.root / 'profile', self.root / 'original'
        (self.profile / 'saves').mkdir(parents=True)
        (self.original / 'saves').mkdir(parents=True)
        self.slot = self.profile / 'saves/Slot_00000002.save'
        self.slot.write_bytes(b'original disposable save')
        (self.original / 'saves/Slot_00000002.save').write_bytes(b'protected owner save')
        (self.original / 'lastCrash.txt').write_bytes(b'protected owner crash')
        self.diagnostic, self.calls, self.clock = live_cas_diagnostics(), [], 0.0
        self.frames = [observed(['MENU', 'Save', 'Save As...', 'Exit Game']),
                       observed(['SAVE GAME?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Exit Game', 'Cancel'])]
        self.handler = None
        self.alive = False
        self.process_failure = None
        self.output = self.root / 'proof.json'

    def request(self, _state, action, **kwargs):
        self.calls.append((action, kwargs))
        if self.handler:
            result = self.handler(action, kwargs)
            if result is not None:
                return result
        if action == 'cas_ui_diagnostics':
            return self.diagnostic
        return {'ok': True}

    def capture(self, *_args):
        self.calls.append(('capture', {}))
        return {'ok': True, 'width': 1278, 'height': 1376}

    def processes(self):
        if self.process_failure:
            raise self.process_failure
        return [{'Id': 42}] if self.alive else []

    def run_shutdown(self, **options):
        original_bytes = {str(path.relative_to(self.original)): path.read_bytes()
                          for path in self.original.rglob('*') if path.is_file()}
        with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                {'token': 'a' * 32, 'artifacts': []}, self.profile, self.original)):
            result = game_lifecycle.shutdown('state', self.output, {'pid': 42}, self.request,
                capture=self.capture, ocr=lambda _: self.frames.pop(0) if len(self.frames) > 1 else self.frames[0],
                processes=self.processes, monotonic=lambda: self.clock,
                pause=lambda seconds: setattr(self, 'clock', self.clock + seconds), **options)
        proof = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(original_bytes, {str(path.relative_to(self.original)): path.read_bytes()
                                         for path in self.original.rglob('*') if path.is_file()})
        return result, proof

    def unsaved_exit(self):
        native = LifecycleTests().already_live(clock=0)
        options = {'save': False, 'sim_id': native['sim']['id'], 'household_id': native['household_id'], 'save_guid': native['save_guid']}
        self.alive = True
        presses = [0]
        def handler(action, kwargs):
            if action == 'test_snapshot': return native
            if action == 'test_input':
                presses[0] += 1
                if presses[0] == 2: self.alive = False
        self.handler = handler
        return native, options

    def test_explicit_unsaved_exit_selects_exit_game_and_retains_all_save_and_backup_bytes(self):
        native, options = self.unsaved_exit()
        (self.profile / 'saves/Slot_ffffffff.save').write_bytes(b'unchanged automatic save')
        (self.profile / 'saves/Slot_00000002.save.ver0').write_bytes(b'unchanged backup')
        result, proof = self.run_shutdown(**options)
        self.assertTrue(result['ok']); self.assertEqual(result['outcome'], 'normal-exit-without-saving')
        self.assertTrue(result['exit_without_save_input_accepted']); self.assertTrue(result['save_files_unchanged_verified'])
        self.assertFalse(proof['save_and_exit_input_accepted']); self.assertFalse(result['save_completed_file_verified'])
        self.assertEqual(proof['before_all_saves'], proof['after_all_saves'])
        self.assertEqual(proof['operation'], 'normal-exit-without-saving')
        presses = [json.loads(kwargs['value'])['value'] for action, kwargs in self.calls if action == 'test_input']
        self.assertEqual(presses[-1]['y'], 500)  # Measured Exit Game, not Save and Exit at470.
        self.assertFalse(any(action in ('test_save', 'test_pause', 'test_play') for action, kwargs in self.calls))

    def test_unsaved_exit_changed_backup_or_save_never_claims_unchanged_completion(self):
        native, options = self.unsaved_exit()
        backup = self.profile / 'saves/Slot_00000002.save.ver0'; backup.write_bytes(b'before backup')
        original_handler = self.handler
        def changed(action, kwargs):
            result = original_handler(action, kwargs)
            if action == 'test_input' and not self.alive: backup.write_bytes(b'game changed backup')
            return result
        self.handler = changed
        result, proof = self.run_shutdown(**options)
        self.assertFalse(result['ok']); self.assertFalse(result['save_files_unchanged_verified'])
        self.assertTrue(result['game_exit_verified']); self.assertFalse(proof['save_and_exit_input_accepted'])

    def test_unsaved_exit_active_cas_or_wrong_live_identity_refuses_all_inputs(self):
        native, options = self.unsaved_exit()
        self.diagnostic['native_peers'] = [{'sim_id': native['sim']['id'], 'age_seconds': 0}]
        result, proof = self.run_shutdown(**options)
        self.assertFalse(result['ok']); self.assertEqual(result['outcome'], 'cas-active-refused')
        self.assertFalse(any(action in ('test_input', 'test_quit', 'capture', 'overlay_hide') for action, kwargs in self.calls))

    def test_attached_cas_peer_even_stale_refuses_before_hide_quit_capture_or_input(self):
        self.alive = True
        self.diagnostic['native_peers'] = [{'sim_id': '285159751289798669', 'age_seconds': 9000}]
        result, proof = self.run_shutdown()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'cas-active-refused')
        self.assertTrue(result['final_process_alive'])
        self.assertEqual([action for action, _ in self.calls], ['cas_ui_diagnostics'])
        self.assertEqual(proof['steps'][0]['result'], self.diagnostic)
        self.assertIn('semantic cas return', result['message'])
        self.assertEqual(self.slot.read_bytes(), b'original disposable save')

    def test_all_retained_accept_and_unresolved_states_refuse_without_replay(self):
        rows = [dict(state=state, operation=operation) for state, operation in
                [('pending', 'status'), ('accept-intent', 'accept'), ('accept-unresolved', 'accept'),
                 ('superseded-read', 'hair-swatch'), ('new-future-state', 'status')]]
        rows += [dict(state='completed', operation='accept', outcome='unresolved'),
                 dict(state='completed', operation='accept', lifecycle_stage='accept-intent')]
        for row in rows:
            with self.subTest(row=row):
                diagnostic = live_cas_diagnostics()
                diagnostic['requests'] = [dict(row, cas_request_id='b' * 32, age_seconds=2)]
                guard = game_lifecycle.shutdown_cas_state(diagnostic)
                self.assertFalse(guard['safe'])
                self.assertEqual(guard['outcome'], 'cas-unresolved-refused')
        self.diagnostic['requests'] = [dict(rows[2], cas_request_id='b' * 32, age_seconds=2)]
        result, proof = self.run_shutdown()
        self.assertEqual(result['outcome'], 'cas-unresolved-refused')
        self.assertEqual(proof['cas_shutdown_guard']['blocking_native_requests'][0]['cas_request_id'], 'b' * 32)
        self.assertEqual([action for action, _ in self.calls], ['cas_ui_diagnostics'])

    def test_typed_terminal_status_expiry_and_verified_accept_allow_live_path(self):
        for state, operation in [('completed', 'status'), ('failed', 'hair-swatch'),
                                 ('superseded-read', 'status'), ('completed', 'accept')]:
            with self.subTest(state=state, operation=operation):
                diagnostic = live_cas_diagnostics()
                diagnostic['requests'] = [{'cas_request_id': 'b' * 32, 'state': state,
                                           'operation': operation, 'age_seconds': 1}]
                self.assertTrue(game_lifecycle.shutdown_cas_state(diagnostic)['safe'])

    def test_completed_native_form_navigation_permits_idle_shutdown(self):
        diagnostic = live_cas_diagnostics()
        diagnostic['requests'] = [{'cas_request_id': 'b' * 32, 'state': 'completed',
                                   'operation': 'form-select', 'age_seconds': 1}]
        self.assertTrue(game_lifecycle.shutdown_cas_state(diagnostic)['safe'])
        diagnostic['requests'][0]['operation'] = 'form-select-all'
        self.assertEqual(game_lifecycle.shutdown_cas_state(diagnostic)['outcome'], 'cas-state-unknown')

    def test_unresolved_form_navigation_still_blocks_shutdown(self):
        for state in ('pending', 'running', 'unknown'):
            with self.subTest(state=state):
                diagnostic = live_cas_diagnostics()
                diagnostic['requests'] = [{'cas_request_id': 'b' * 32, 'state': state,
                                           'operation': 'form-select', 'age_seconds': 1}]
                self.assertEqual(game_lifecycle.shutdown_cas_state(diagnostic)['outcome'], 'cas-unresolved-refused')

    def test_missing_untyped_or_contradictory_diagnostics_are_unknown_not_empty(self):
        invalid = [None, {}, {'ok': True}, dict(live_cas_diagnostics(), native_peers=None),
                   dict(live_cas_diagnostics(), native_initializer_observed=0),
                   dict(live_cas_diagnostics(), requests=[{'cas_request_id': 'b' * 32,
                       'state': 'completed', 'operation': [], 'age_seconds': 0}]),
                   dict(live_cas_diagnostics(), native_peers=[{'sim_id': True, 'age_seconds': 0}]),
                   dict(live_cas_diagnostics(), native_peers=[{'sim_id': '4', 'age_seconds': True}])]
        for change in ({'bound': False}, {'port': True}, {'native_connection_verified': True}):
            diagnostic = live_cas_diagnostics()
            diagnostic['socket_transport'].update(change)
            invalid.append(diagnostic)
        for diagnostic in invalid:
            with self.subTest(diagnostic=diagnostic):
                self.assertEqual(game_lifecycle.shutdown_cas_state(diagnostic)['outcome'], 'cas-state-unknown')
        self.diagnostic = None
        result, proof = self.run_shutdown()
        self.assertEqual(result['outcome'], 'cas-state-unknown')
        self.assertIsNone(proof['steps'][0]['result'])
        self.assertEqual([action for action, _ in self.calls], ['cas_ui_diagnostics'])

    def test_diagnostic_response_loss_refuses_and_records_unknown_proof(self):
        def handler(action, _kwargs):
            if action == 'cas_ui_diagnostics':
                raise TimeoutError('native diagnostic response lost')
        self.handler = handler
        result, proof = self.run_shutdown()
        self.assertEqual(result['outcome'], 'cas-state-unknown')
        self.assertIn('response lost', proof['steps'][0]['result']['error'])
        self.assertEqual([action for action, _ in self.calls], ['cas_ui_diagnostics'])

    def test_cas_appearing_during_capture_prevents_the_next_quit_or_button(self):
        count = [0]
        def handler(action, _kwargs):
            if action == 'cas_ui_diagnostics':
                count[0] += 1
                if count[0] == 2:
                    self.diagnostic['native_peers'] = [{'sim_id': '4', 'age_seconds': 0}]
        self.handler = handler
        result, _proof = self.run_shutdown()
        self.assertEqual(result['outcome'], 'cas-active-refused')
        self.assertFalse(any(action in ('test_quit', 'test_input') for action, _ in self.calls))
        self.assertEqual(sum(action == 'capture' for action, _ in self.calls), 1)

    def test_new_crash_after_quit_failure_is_preserved_and_final_exit_recorded(self):
        self.frames = [observed([])]
        old = b'<root><type>crash</type><categoryid>old</categoryid></root>'
        crash = b'<root><type>crash</type><categoryid>0x14112c406</categoryid><memdumptxt>private dump</memdumptxt></root>'
        (self.profile / 'lastCrash.txt').write_bytes(old)
        def handler(action, _kwargs):
            if action == 'test_quit':
                (self.profile / 'lastCrash.txt').write_bytes(crash)  # Emulate game output.
        self.handler = handler
        result, proof = self.run_shutdown()
        self.assertEqual(result['outcome'], 'crash')
        self.assertFalse(result['ok'])
        self.assertFalse(result['normal_exit_verified'])
        self.assertTrue(result['game_exit_verified'])
        self.assertFalse(result['final_process_alive'])
        self.assertEqual(proof['crash']['metadata'], {'type': 'crash', 'categoryid': '0x14112c406'})
        target = self.root / ('proof-crash-' + hashlib.sha256(crash).hexdigest() + '.xml')
        self.assertEqual(target.read_bytes(), crash)
        self.assertNotIn('private dump', self.output.read_text(encoding='utf-8'))
        self.assertEqual(sum(action == 'test_quit' for action, _ in self.calls), 1)
        self.assertFalse(any(action == 'test_input' for action, _ in self.calls))
        self.assertEqual(self.slot.read_bytes(), b'original disposable save')

    def test_changed_crash_overrides_save_rewrite_and_successful_confirmation(self):
        count = [0]
        def handler(action, _kwargs):
            if action == 'test_input':
                count[0] += 1
                if count[0] == 2:
                    self.slot.write_bytes(b'game rewrote save before crashing')  # Emulate game.
                    (self.profile / 'lastCrash.txt').write_bytes(b'<root><type>crash</type></root>')
        self.handler = handler
        result, proof = self.run_shutdown()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'crash')
        self.assertTrue(proof['save_and_exit_input_accepted'])
        self.assertTrue(result['save_completed_file_verified'])
        self.assertFalse(result['normal_exit_verified'])

    def test_unchanged_prior_crash_does_not_invalidate_normal_live_save_and_exit(self):
        (self.profile / 'lastCrash.txt').write_bytes(b'<root><type>crash</type></root>')
        count = [0]
        def handler(action, _kwargs):
            if action == 'test_input':
                count[0] += 1
                if count[0] == 2:
                    self.slot.write_bytes(b'game normal save rewrite')
        self.handler = handler
        result, proof = self.run_shutdown()
        self.assertTrue(result['ok'])
        self.assertEqual(result['outcome'], 'normal-save-and-exit')
        self.assertEqual(proof['crash']['outcome'], 'unchanged')
        self.assertFalse(list(self.root.glob('*-crash-*.xml')))

    def test_new_untrusted_crash_xml_is_not_copied_or_claimed_normal(self):
        def handler(action, _kwargs):
            if action == 'overlay_hide':
                (self.profile / 'lastCrash.txt').write_bytes(b'<!DOCTYPE root><root/>')  # Emulate game.
                raise RuntimeError('overlay response failed')
        self.handler = handler
        result, proof = self.run_shutdown()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'changed-crash-report-refused')
        self.assertEqual(proof['crash']['outcome'], 'refused')
        self.assertFalse(list(self.root.glob('*-crash-*.xml')))

    def test_failure_with_unknown_final_process_never_claims_exit(self):
        self.diagnostic = None
        self.process_failure = OSError('cannot inspect exact PID')
        result, proof = self.run_shutdown()
        self.assertIsNone(result['final_process_alive'])
        self.assertFalse(result['game_exit_verified'])
        self.assertFalse(result['normal_exit_verified'])
        self.assertIn('exact PID', proof['process_observation_error'])

    def test_profile_or_original_proof_targets_are_rejected_without_game_actions(self):
        with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                {'token': 'a' * 32, 'artifacts': []}, self.profile, self.original)):
            for target in (self.profile / 'proof.json', self.original / 'proof.json'):
                with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'external'):
                    game_lifecycle.shutdown('state', target, {'pid': 42}, self.request)
        self.assertEqual(self.calls, [])
        self.assertFalse(list(self.profile.glob('proof*')))
        self.assertFalse(list(self.original.glob('proof*')))
