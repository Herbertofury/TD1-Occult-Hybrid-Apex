"""Phone decisions against the real durable receiver/native-owner fixture."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import phone_cas, cas_bank_transaction as receiver, form_appearance as appearance
import test_cas_bank_transaction as fixture


class PhoneCasTests(unittest.TestCase):
    def setUp(self):
        phone_cas._SESSIONS.clear()
        self.addCleanup(phone_cas._SESSIONS.clear)
        self.game = fixture.CasBankReceiverTests()
        self.game.setUp()
        self.addCleanup(self.game.doCleanups)
        self.backend, self.sim = self.game.backend, self.game.sim
        self.sim.get_sim_instance = lambda: object()
        self.ticks, self.wall_ticks, self.speed, self.time = 100, 1000, 0, 0
        self.zone = Obj(id=40, is_zone_running=True, is_in_build_buy=False)
        self.client = Obj(id=50)
        self.clock = Obj(clock_speed=0, now=lambda: Obj(absolute_ticks=lambda: self.wall_ticks))
        self.timeline = Obj(sim_timeline=object(), sim_now=Obj(absolute_ticks=lambda: self.ticks))
        self.backend.services.current_zone = lambda: self.zone
        self.backend.services.active_household = lambda: Obj(id=20)
        self.backend.services.client_manager = lambda: Obj(get_first_client=lambda: self.client)
        self.backend.services.game_clock_service = lambda: self.clock
        self.backend.services.time_service = lambda: self.timeline
        self.diagnostic = {'ok': True, 'native_peers': [], 'requests': []}
        self.actions, self.clock_controls, self.callbacks = [], [], []
        self.fault = None
        def run_action(action, sim_id=None, value=None):
            self.actions.append((action, value))
            if action == 'cas_ui_diagnostics':
                return copy.deepcopy(self.diagnostic)
            result = receiver.dispatch(self.backend, self.sim, action, value)
            if self.fault:
                replacement = self.fault(action, result)
                if replacement is not None:
                    return replacement
            return result
        self.backend.run_action = run_action
        self.alarms = []
        def add_alarm(owner, interval, callback, repeating=False):
            alarm = Obj(owner=owner, callback=callback, active=True)
            self.alarms.append(alarm)
            return alarm
        self.backend.alarms = Obj(add_alarm_real_time=add_alarm, cancel_alarm=lambda alarm: setattr(alarm, 'active', False))
        self.backend.clock = Obj(interval_in_real_seconds=lambda value: value)
        def set_speed(name, source, _connection):
            self.assertEqual(_connection, 50)
            self.clock_controls.append((name, source))
            self.clock.clock_speed = {'one': 1, 'paused': 0}[name]
        self.enterContext(patch.dict(sys.modules, {'server_commands.clock_commands': Obj(set_speed=set_speed)}))
        self.enterContext(patch.object(phone_cas.time, 'monotonic', side_effect=lambda: self.time))
        self.session = phone_cas.session(self.backend, '10')

    def fire(self, advance=30):
        self.time += .25
        self.wall_ticks += 100
        if self.clock.clock_speed == 1:
            self.ticks += advance
        for alarm in tuple(self.alarms):
            if alarm.active:
                alarm.callback(alarm)

    def observe(self):
        result = self.session.start_observe(self.callbacks.append)
        self.assertTrue(result['pending'])
        self.assertEqual(self.game.snapshot_calls, [])
        self.fire()
        self.fire()
        self.assertEqual(self.callbacks[-1], {'ok': True, 'page': 'cas_review'})
        self.assertEqual(self.clock.clock_speed, 0)
        self.assertTrue(self.session.probe['positive_normal_ticks_verified'])
        self.assertTrue(self.session.probe['paused_verified'])
        return self.session

    def test_all_changed_owner_decisions_bind_real_raw_journal_and_one_commit_preserves_other_owners(self):
        self.session.begin()
        self.assertEqual(self.game.snapshot_calls, [])
        for lane in (1, 4, 32, 64):
            self.game.edit(lane)
        self.observe()
        self.assertEqual(self.game.snapshot_calls, [10])
        review = phone_cas.rows(self.backend, '10', 'cas_review')
        pages = [row[0] for row in review if row[0].startswith('page:cas_form:')]
        self.assertEqual(pages, ['page:cas_form:1', 'page:cas_form:4', 'page:cas_form:32', 'page:cas_form:64'])
        with self.assertRaisesRegex(ValueError, 'EVERY'):
            self.session.prepare(self.session.nonce)
        self.assertFalse(self.session.prepare_attempted)
        self.assertEqual(self.game.native_writes, [])
        for lane in ('1', '4', '32', '64'):
            self.session.choose(self.session.nonce, lane, 'restore-original' if lane == '32' else 'accept-returned')
        self.session.prepare(self.session.nonce)
        self.assertEqual(self.game.native_writes, [])
        self.assertTrue(self.session.commit(self.session.nonce)['ok'])
        record = self.game.record()
        self.assertIsNone(record['pending'])
        self.assertEqual(record['bank']['32'], self.game.originals['32'])
        for lane in ('1', '4', '64'):
            self.assertEqual(appearance.decode(record['bank'][lane]['physique']), 'accepted-' + lane)
        self.assertEqual(self.game.data()['records']['30:99'], self.game.foreign)
        self.assertEqual(self.game.data()['unknown_top_level'], self.game.initial['unknown_top_level'])
        with self.assertRaisesRegex(ValueError, 'already attempted'):
            self.session.commit(self.session.nonce)
        self.assertEqual(sum(action == 'cas_bank_commit' for action, _ in self.actions), 1)

    def test_returned_journal_is_durable_before_receiver_serializer_and_existing_return_is_not_reobserved(self):
        self.session.begin()
        self.game.edit(64)
        old_snapshot = self.game.snapshot_calls
        def raw_journal_check(action, result):
            if action == 'cas_bank_observe':
                row = self.game.record()
                self.assertEqual(row['cas_transaction']['journal']['state'], 'observed')
                self.assertEqual(appearance.decode(row['cas_transaction']['journal']['raw_return']['stored']['64']['physique']), 'accepted-64')
        self.fault = raw_journal_check
        self.observe()
        self.assertIs(self.game.snapshot_calls, old_snapshot)
        self.assertTrue(self.session.start_observe()['ok'])
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.actions), 1)
        self.assertEqual(len(self.clock_controls), 2)

    def test_no_clock_progress_cancels_alarm_pauses_once_and_never_serializes_or_observes(self):
        self.session.begin()
        self.session.start_observe(self.callbacks.append)
        self.fire(advance=0)
        for _ in range(41):
            self.fire(advance=0)
        self.assertEqual(self.session.phase, 'blocked')
        self.assertFalse(self.callbacks[-1]['ok'])
        self.assertFalse(any(action == 'cas_bank_observe' for action, _ in self.actions))
        self.assertEqual(self.game.snapshot_calls, [])
        self.assertEqual([name for name, _ in self.clock_controls], ['one', 'paused'])
        self.assertTrue(all(not alarm.active for alarm in self.alarms))

    def test_wrong_sim_or_changed_household_never_observes_or_pauses_a_different_context(self):
        self.session.begin()
        self.session.start_observe(self.callbacks.append)
        self.fire()
        self.sim.household_id = 99
        self.fire()
        self.assertEqual(self.session.phase, 'blocked')
        self.assertEqual([name for name, _ in self.clock_controls], ['one'])
        self.assertEqual(self.game.snapshot_calls, [])

    def test_cas_peer_or_unresolved_accept_blocks_probe_before_any_clock_or_serializer_action(self):
        self.session.begin()
        self.diagnostic['native_peers'] = [{'sim_id': '10', 'age_seconds': .1}]
        with self.assertRaisesRegex(ValueError, 'Native CAS is active'):
            self.session.start_observe()
        self.diagnostic['native_peers'] = []
        self.diagnostic['requests'] = [{'state': 'completed', 'lifecycle_stage': 'accept-intent'}]
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.session.start_observe()
        self.assertEqual(self.clock_controls, [])
        self.assertEqual(self.game.snapshot_calls, [])

    def test_lost_observe_result_retains_actual_raw_return_and_never_repeats_observation(self):
        self.session.begin()
        self.game.edit(64)
        def lost(action, _result):
            if action == 'cas_bank_observe':
                raise OSError('lost after durable raw observation')
        self.fault = lost
        self.session.start_observe(self.callbacks.append)
        self.fire(); self.fire()
        self.assertFalse(self.callbacks[-1]['ok'])
        self.assertTrue(self.session.observe_attempted)
        self.assertEqual(self.game.record()['cas_transaction']['journal']['state'], 'observed')
        self.fault = None
        self.session.start_observe()
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.actions), 1)
        self.assertEqual(self.session.receipts[-1]['state'], 'attempted')

    def test_stale_nonce_unchanged_lane_and_external_bytes_are_never_decisions(self):
        self.session.begin()
        self.game.edit(64)
        self.observe()
        for nonce, lane, decision in (('f' * 32, '64', 'accept-returned'),
                (self.session.nonce, '1', 'accept-returned'),
                (self.session.nonce, '64', {'appearance': 'external'})):
            with self.subTest(lane=lane, decision=decision), self.assertRaises((ValueError, TypeError)):
                self.session.choose(nonce, lane, decision)
        self.assertEqual(self.session.decisions, {})
        self.assertFalse(any(action == 'cas_bank_prepare' for action, _ in self.actions))

    def test_changed_field_names_all_render_individually_without_raw_values_or_notification_truncation(self):
        self.session.begin()
        self.game.edit(64, 'physique', 'private raw shape data')
        self.game.edit(64, 'facial_attributes', b'private face data')
        self.observe()
        rows = phone_cas.rows(self.backend, '10', 'cas_form:64')
        fields = self.session.evidence[0]['fields']
        for field in fields:
            self.assertTrue(any('[' + field + ']' in label for _, label, _ in rows))
        self.assertNotIn('private raw', json.dumps(rows))
        choices = [tag for tag, _, _ in rows if tag.startswith('cas:decision:')]
        self.assertEqual(len(choices), 2)

    def test_unresolved_prepare_or_commit_never_replays_native_or_metadata_submission(self):
        self.session.begin()
        self.game.edit(64)
        self.observe()
        self.session.choose(self.session.nonce, '64', 'accept-returned')
        def lost(action, _result):
            if action == 'cas_bank_prepare':
                raise OSError('plan ACK lost')
        self.fault = lost
        with self.assertRaises(OSError):
            self.session.prepare(self.session.nonce)
        self.fault = None
        with self.assertRaisesRegex(ValueError, 'already attempted'):
            self.session.prepare(self.session.nonce)
        self.assertEqual(sum(action == 'cas_bank_prepare' for action, _ in self.actions), 1)
        self.assertEqual(self.game.native_writes, [])

    def test_clock_authority_missing_or_wrong_thread_fails_before_native_observation(self):
        self.session.begin()
        self.backend.services.game_clock_service = lambda: None
        with self.assertRaisesRegex(ValueError, 'clock authority'):
            self.session.start_observe()
        self.backend._APEX_GAME_THREAD_IDENT = -1
        with self.assertRaisesRegex(ValueError, 'canonical game thread'):
            phone_cas.rows(self.backend, '10', 'cas_review')
        self.assertEqual(self.game.snapshot_calls, [])

    def test_ticks_before_own_normal_submission_do_not_count_and_alarm_callback_is_inert_after_completion(self):
        self.session.begin()
        self.clock.clock_speed = 1
        self.session.start_observe(self.callbacks.append)
        self.fire(advance=60)
        self.fire(advance=0)
        self.assertFalse(self.session.probe['positive_normal_ticks_verified'])
        self.assertFalse(any(action == 'cas_bank_observe' for action, _ in self.actions))
        self.fire(advance=30)
        self.assertTrue(self.callbacks[-1]['ok'])
        calls = list(self.actions), list(self.clock_controls), list(self.callbacks)
        self.alarms[0].callback(self.alarms[0])
        self.assertEqual((self.actions, self.clock_controls, self.callbacks), calls)

    def test_existing_cli_observed_return_needs_phone_live_proof_without_replaying_serializer(self):
        self.game.begin()
        self.game.edit(64)
        self.game.observe()
        self.session.refresh()
        self.session.choose(self.session.nonce, '64', 'accept-returned')
        with self.assertRaisesRegex(ValueError, 'normal Live ticks'):
            self.session.prepare(self.session.nonce)
        self.session.start_observe(self.callbacks.append)
        self.fire(); self.fire()
        self.assertEqual(self.game.snapshot_calls, [10])
        self.assertFalse(any(action == 'cas_bank_observe' for action, _ in self.actions))
        self.assertTrue(self.callbacks[-1]['ok'])
        self.assertTrue(self.session.prepare(self.session.nonce)['ok'])

    def test_lost_commit_ack_retains_completed_durable_receipt_without_a_second_native_write(self):
        self.session.begin()
        self.game.edit(64)
        self.observe()
        self.session.choose(self.session.nonce, '64', 'accept-returned')
        self.session.prepare(self.session.nonce)
        def lost(action, _result):
            if action == 'cas_bank_commit':
                raise OSError('commit ACK lost after durable completion')
        self.fault = lost
        with self.assertRaises(OSError):
            self.session.commit(self.session.nonce)
        native_writes = list(self.game.native_writes)
        self.fault = None
        self.assertTrue(self.session.refresh()['completed_receipt'])
        with self.assertRaisesRegex(ValueError, 'already attempted'):
            self.session.commit(self.session.nonce)
        self.assertEqual(self.game.native_writes, native_writes)
        self.assertEqual(sum(action == 'cas_bank_commit' for action, _ in self.actions), 1)

    def test_explicit_new_capture_after_other_frontend_completion_invalidates_old_phone_tags(self):
        self.game.begin()
        self.game.edit(64)
        self.game.observe()
        self.session.refresh()
        old_nonce, old_epoch = self.session.nonce, self.session.epoch
        self.game.prepare([(64, 'accept-returned')])
        self.game.commit()
        self.assertTrue(self.session.begin()['ok'])
        self.assertNotEqual(self.session.nonce, old_nonce)
        self.assertNotEqual(self.session.epoch, old_epoch)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.session.choose(old_nonce, '64', 'accept-returned')

    def test_client_or_zone_change_after_prepare_blocks_commit_before_a_native_write(self):
        self.session.begin()
        self.game.edit(64)
        self.observe()
        self.session.choose(self.session.nonce, '64', 'accept-returned')
        self.session.prepare(self.session.nonce)
        self.zone.id = 41
        with self.assertRaisesRegex(ValueError, 'unchanged'):
            self.session.commit(self.session.nonce)
        self.assertFalse(self.session.commit_attempted)
        self.assertEqual(self.game.native_writes, [])
        self.assertFalse(any(action == 'cas_bank_commit' for action, _ in self.actions))

    def test_unproven_commit_receipt_cannot_claim_native_owner_verification_or_save_reload(self):
        self.session.begin()
        self.game.edit(64)
        self.observe()
        self.session.choose(self.session.nonce, '64', 'accept-returned')
        self.session.prepare(self.session.nonce)
        def unproven(action, result):
            if action == 'cas_bank_commit':
                result = dict(result)
                result.pop('all_native_owners_verified')
                return result
        self.fault = unproven
        with self.assertRaisesRegex(ValueError, 'not acknowledged'):
            self.session.commit(self.session.nonce)
        self.assertEqual(self.session.phase, 'blocked')
        self.assertTrue(self.session.commit_attempted)

    def ui(self, action, argument=None):
        return phone_cas.ui_dispatch(self.backend, '10', 'cas_bank_ui_' + action, argument)

    def test_f11_existing_raw_return_needs_one_owned_clock_probe_and_preserves_actual_receiver_acks(self):
        self.game.begin()
        self.game.edit(32)
        self.game.edit(64)
        self.game.observe()
        before = self.ui('status')
        self.assertEqual(before['phase'], 'observed')
        self.assertIs(before['clock_proof_validated'], False)
        review_argument = {'expected_pending_sha256': before['expected_pending_sha256']}
        pending = self.ui('review', review_argument)
        self.assertIs(pending['pending'], True)
        self.assertIs(pending['clock_proof_validated'], False)
        duplicate = self.ui('review', review_argument)
        for key in ('pending', 'clock_proof_validated', 'review_nonce', 'expected_pending_sha256', 'review_state'):
            self.assertEqual(duplicate[key], pending[key])
        self.assertEqual(len(self.alarms), 1)
        self.assertEqual(self.clock_controls, [])
        self.fire(); self.fire()
        ready = self.ui('status')
        self.assertIs(ready['clock_proof_validated'], True)
        self.assertEqual(ready['review_nonce'], pending['review_nonce'])
        self.assertEqual(self.game.snapshot_calls, [10])
        self.assertFalse(any(action == 'cas_bank_observe' for action, _ in self.actions))
        reopened = self.ui('review', review_argument)
        self.assertIs(reopened['pending'], False)
        self.assertIs(reopened['clock_proof_validated'], True)
        prepare = self.ui('prepare', {'expected_pending_sha256': ready['expected_pending_sha256'],
            'expected_raw_return_sha256': ready['raw_return_sha256'], 'review_nonce': ready['review_nonce'],
            'dispositions': [{'lane': '32', 'action': 'restore-original'}, {'lane': '64', 'action': 'accept-returned'}]})
        original_prepare = self.session.receipts[-1]['receipt']
        for key, value in original_prepare.items():
            self.assertEqual(prepare[key], value)
        self.assertIs(prepare['clock_proof_validated'], True)
        self.assertEqual(self.game.native_writes, [])
        commit_arg = {'expected_pending_sha256': ready['expected_pending_sha256'],
            'expected_plan_sha256': prepare['plan_sha256'], 'review_nonce': ready['review_nonce']}
        committed = self.ui('commit', commit_arg)
        for key, value in self.session.receipts[-1]['receipt'].items():
            self.assertEqual(committed[key], value)
        self.assertIs(committed['all_native_owners_verified'], True)
        self.assertIs(committed['save_reload_verified'], False)
        writes = list(self.game.native_writes)
        with self.assertRaisesRegex(ValueError, 'already attempted'):
            self.ui('commit', commit_arg)
        self.assertEqual(self.game.native_writes, writes)

    def test_f11_review_stale_epoch_and_prepare_nonce_partial_choices_or_external_hair_reject_before_writes(self):
        self.session.begin()
        self.game.edit(64)
        status = self.ui('status')
        with self.assertRaisesRegex(ValueError, 'exact current'):
            self.ui('review', {'expected_pending_sha256': 'f' * 64})
        self.assertEqual(self.alarms, [])
        self.ui('review', {'expected_pending_sha256': status['expected_pending_sha256']})
        self.fire(); self.fire()
        status = self.ui('status')
        valid = {'expected_pending_sha256': status['expected_pending_sha256'],
            'expected_raw_return_sha256': status['raw_return_sha256'], 'review_nonce': status['review_nonce'],
            'dispositions': [{'lane': '64', 'action': 'accept-returned'}]}
        cases = [dict(valid, review_nonce='f' * 32), dict(valid, expected_raw_return_sha256='e' * 64),
                 dict(valid, dispositions=[]), dict(valid, hair_targets={'appearance': 'arbitrary'})]
        for argument in cases:
            with self.subTest(argument=argument), self.assertRaises(ValueError):
                self.ui('prepare', argument)
        self.assertEqual(self.session.decisions, {})
        self.assertFalse(any(action == 'cas_bank_prepare' for action, _ in self.actions))
        self.assertEqual(self.game.native_writes, [])

    def test_f11_read_only_status_proof_fails_after_client_change_and_prepare_never_uses_old_ticks(self):
        self.session.begin()
        self.game.edit(64)
        self.observe()
        status = self.ui('status')
        self.client.id = 51
        changed = self.ui('status')
        self.assertEqual(changed['expected_pending_sha256'], status['expected_pending_sha256'])
        self.assertIs(changed['clock_proof_validated'], False)
        with self.assertRaisesRegex(ValueError, 'unchanged'):
            self.ui('prepare', {'expected_pending_sha256': status['expected_pending_sha256'],
                'expected_raw_return_sha256': status['raw_return_sha256'], 'review_nonce': status['review_nonce'],
                'dispositions': [{'lane': '64', 'action': 'accept-returned'}]})
        self.assertEqual(self.session.decisions, {})
        self.assertEqual(self.game.native_writes, [])

    def test_explicit_reopen_adopts_fresh_other_frontend_epoch_and_invalidates_old_proof_without_auto_observation(self):
        self.session.begin()
        self.game.edit(64)
        self.observe()
        old_nonce, old_epoch = self.session.nonce, self.session.epoch
        old_receipts = list(self.session.receipts)
        self.game.epoch = self.session.epoch
        self.game.observation = self.session.receipts[-1]['receipt']
        self.game.prepare([(64, 'accept-returned')]); self.game.commit(); self.game.begin()
        passive = self.ui('status')
        self.assertNotEqual(passive['expected_pending_sha256'], old_epoch)
        self.assertIs(passive['clock_proof_validated'], False)
        self.assertEqual(self.session.nonce, old_nonce)
        rows = phone_cas.rows(self.backend, '10', 'cas_review')
        self.assertTrue(any('captured' in label for _, label, _ in rows))
        self.assertNotEqual(self.session.nonce, old_nonce)
        self.assertEqual(self.session.epoch, passive['expected_pending_sha256'])
        self.assertIsNone(self.session.probe)
        self.assertEqual(self.session.decisions, {})
        self.assertEqual(self.session.receipts[:len(old_receipts)], old_receipts)
        self.assertEqual(sum(action == 'cas_bank_observe' for action, _ in self.actions), 1)
        self.assertEqual(len(self.clock_controls), 2)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.session.choose(old_nonce, '64', 'accept-returned')

    def test_f11_lost_prepare_ack_retains_attempt_and_does_not_repeat_even_when_plan_is_durable(self):
        self.session.begin(); self.game.edit(64); self.observe()
        status = self.ui('status')
        argument = {'expected_pending_sha256': status['expected_pending_sha256'],
            'expected_raw_return_sha256': status['raw_return_sha256'], 'review_nonce': status['review_nonce'],
            'dispositions': [{'lane': '64', 'action': 'accept-returned'}]}
        def lost(action, result):
            if action == 'cas_bank_prepare':
                raise OSError('receiver plan persisted but UI ACK lost')
        self.fault = lost
        with self.assertRaises(OSError):
            self.ui('prepare', argument)
        self.fault = None
        retained = self.ui('status')
        self.assertEqual(retained['phase'], 'planned')
        self.assertIs(retained['clock_proof_validated'], False)
        with self.assertRaises(ValueError):
            self.ui('prepare', argument)
        self.assertEqual(sum(action == 'cas_bank_prepare' for action, _ in self.actions), 1)
        self.assertEqual(self.game.native_writes, [])

    def test_advancing_game_clock_with_frozen_simulation_cannot_prove_live_changes_settled(self):
        self.session.begin()
        self.game.edit(64)
        status = self.ui('status')
        self.ui('review', {'expected_pending_sha256': status['expected_pending_sha256']})
        self.fire(advance=0)
        for _ in range(41):
            self.fire(advance=0)
        self.assertGreater(self.wall_ticks, 4000)
        self.assertEqual(self.ticks, 100)
        self.assertEqual(self.session.phase, 'blocked')
        self.assertIs(self.ui('status')['clock_proof_validated'], False)
        self.assertEqual(self.game.snapshot_calls, [])
        self.assertFalse(any(action == 'cas_bank_observe' for action, _ in self.actions))

    def test_context_change_inside_receiver_prepare_cannot_attach_true_clock_proof_to_acknowledgement(self):
        self.session.begin(); self.game.edit(64); self.observe()
        status = self.ui('status')
        argument = {'expected_pending_sha256': status['expected_pending_sha256'],
            'expected_raw_return_sha256': status['raw_return_sha256'], 'review_nonce': status['review_nonce'],
            'dispositions': [{'lane': '64', 'action': 'accept-returned'}]}
        def change(action, result):
            if action == 'cas_bank_prepare':
                self.zone.id = 41
        self.fault = change
        with self.assertRaisesRegex(ValueError, 'unchanged'):
            self.ui('prepare', argument)
        self.assertEqual(self.session.receipts[-1]['state'], 'acknowledged')
        self.assertEqual(self.session.phase, 'planned')
        self.assertIs(self.ui('status')['clock_proof_validated'], False)
        self.assertEqual(self.game.native_writes, [])
        with self.assertRaises(ValueError):
            self.ui('prepare', argument)
        self.assertEqual(sum(action == 'cas_bank_prepare' for action, _ in self.actions), 1)


if __name__ == '__main__':
    unittest.main()
