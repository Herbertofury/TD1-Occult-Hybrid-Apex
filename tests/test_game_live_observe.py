"""Independent temporary-file paused-presence fixtures; no real game actions."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_live_observe
from source_manifest import sha256, write_json
from test_game_save import SaveFixture, SIM, HOUSEHOLD, GUID


class PausedLiveTests(SaveFixture):
    def setUp(self):
        super().setUp()
        journal = json.loads(self.state.read_bytes())
        for index in range(13):
            path = self.profile / 'Mods/ApexTest' / ('Fixture{:02d}.package'.format(index))
            path.parent.mkdir(exist_ok=True); path.write_bytes(b'exact fixture artifact')
            journal['artifacts'].append({'name': path.name, 'sha256': sha256(path)})
        write_json(self.state, journal); self.artifacts = journal['artifacts']
        for stem in ('Slot_00000002.save', 'Slot_ffffffff.save'):
            for tail in ['.ver{}'.format(index) for index in range(5)] + ['.day.ver0', '.day.ver1', '.week.ver0']:
                (self.profile / 'saves' / (stem + tail)).write_bytes(b'exact retained backup')
        (self.profile / 'saves/Slot_ffffffff.save').write_bytes(b'current disposable autosave')
        self.before = game_live_observe.game_lifecycle.all_save_files(self.profile)
        self.metadata = {'slot_id': 2, 'slot_name': 'Native fixture', 'save_guid': GUID,
            'active_household_id': HOUSEHOLD, 'file_sha256': self.digest,
            'household': {'id': HOUSEHOLD, 'name': 'Sim', 'member_ids': [SIM], 'home_zone_id': '42'},
            'sim': {'id': SIM, 'household_id': HOUSEHOLD, 'zone_id': '42'},
            'selected_membership_verified': True, 'selected_household_is_active': True}
        checks = ('active_household_membership', 'runtime_household_identity', 'manager_identity',
            'account_save_eligible', 'sim_proto_exists', 'sim_proto_identity', 'sim_proto_household_identity',
            'household_proto_exists', 'household_proto_identity', 'household_proto_membership')
        self.live = {'ok': True, 'save_slot': 0, 'save_guid': GUID, 'household_id': HOUSEHOLD,
            'zone_id': '42', 'client_id': '7', 'clock_speed': 0, 'zone_running': True, 'in_build_buy': False,
            'sim': {'id': SIM, 'instanced': True}, 'sim_now_ticks': '1129711',
            'runtime_queries': {'client_id': 'returned-value', 'zone_running': 'returned-value',
                                'sim_now_ticks': 'returned-value'},
            'persistence': {'persistence_verified_before_save': True,
                'household_sim_ids': [SIM], 'persisted_household_sim_ids': [SIM],
                'checks': {key: True for key in checks}}, 'request_id': '1' * 32, 'request_state': 'completed'}
        native = {'ok': True, 'native_code': 0, 'input_state': 4, 'input_version': 2,
            'input_submitted': True, 'pointer_verified': True, 'execution': 'fixed-native-control',
            'request_id': 'c' * 32, 'request_state': 'completed',
            'window_metrics': {'available': True, 'root_match': True,
                'foreground_pid': 42, 'overlay_pid': 42, 'width': 1278, 'height': 1376}}
        self.prior_path, self.output = self.root / 'failed-map-play.json', self.root / 'paused-live.json'
        prior_before = copy.deepcopy(self.before)
        prior_before['Slot_ffffffff.save']['sha256'] = 'f' * 64
        self.prior = {'schema': 1, 'operation': 'play-existing-selected-disposable-household',
            'ok': False, 'outcome': 'save-files-changed-unexpectedly', 'identity': self.identity,
            'inputs': self.artifacts, 'target': {'sim_id': SIM, 'household_id': HOUSEHOLD, 'save_guid': GUID,
                'slot_id': 2, 'file_sha256': self.digest}, 'play_input_accepted': True,
            'input_replay_attempted': False, 'save_requested': False, 'save_file_written': False,
            'before_saves': prior_before, 'after_saves': self.before,
            'indexed_household': self.metadata, 'loaded_before_pause': self.live,
            'save_files_unchanged': False, 'steps': [{'action': 'test_input', 'result': native}]}
        write_json(self.prior_path, self.prior); self.prior_hash = sha256(self.prior_path)
        self.diagnostics = {'ok': True, 'native_initializer_observed': False, 'native_peers': [], 'requests': [],
            'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021,
                                 'startup_error': None, 'native_connection_verified': False}}

    def run_observe(self, *, snapshots=None, after_read=None, identity=None, diagnostics=None):
        snapshots = list(snapshots or [self.live, dict(self.live, request_id='2' * 32)])
        calls = []
        current = [identity or self.identity]
        def request(_state, action, **_kwargs):
            calls.append(action)
            if action == 'cas_ui_diagnostics': return diagnostics or self.diagnostics
            if action != 'test_snapshot': raise AssertionError('Mutation reached read-only observer: ' + action)
            result = snapshots.pop(0)
            if after_read is not None: after_read(len([a for a in calls if a == 'test_snapshot']), current)
            if isinstance(result, Exception): raise result
            return copy.deepcopy(result)
        result = game_live_observe.observe(self.state, self.output, self.identity, request,
            SIM, HOUSEHOLD, GUID, 2, self.digest, self.prior_path, self.prior_hash,
            identity_provider=lambda _state: current[0], alive=lambda _pid: True, pause=lambda _seconds: None,
            metadata_reader=lambda *_args: copy.deepcopy(self.metadata))
        proof = json.loads(self.output.read_bytes())
        self.assertEqual(self.original_save.read_bytes(), b'owner save must never change')
        return result, proof, calls

    def test_separate_paused_receipt_does_not_certify_native_zero_as_indexed_normal_slot(self):
        result, proof, calls = self.run_observe()
        self.assertTrue(result['ok']); self.assertTrue(result['paused_live_verified'])
        self.assertTrue(result['household_verified']); self.assertFalse(result['native_slot_verified'])
        self.assertEqual(result['native_observed_slot'], 0)
        self.assertEqual(calls.count('test_snapshot'), 2)
        self.assertEqual(set(calls), {'test_snapshot', 'cas_ui_diagnostics'})
        for key in ('input_requested', 'input_submitted', 'gameplay_mutation_requested', 'save_requested', 'save_file_written'):
            self.assertFalse(proof[key])
        self.assertEqual(sha256(self.prior_path), self.prior_hash)
        self.assertFalse(proof['map_play_result_preserved']['ok'])
        self.assertTrue(proof['save_files_unchanged'])

    def test_autosave_sentinel_is_observed_only_and_actual_normal_slot_requires_native_readback(self):
        for slot in (0xffffffff, 2):
            with self.subTest(slot=slot):
                if self.output.exists(): self.output.unlink()
                live = dict(self.live, save_slot=slot)
                result, _proof, _calls = self.run_observe(snapshots=[live, dict(live, request_id='2' * 32)])
                self.assertTrue(result['ok']); self.assertEqual(result['native_slot_verified'], slot == 2)
                self.assertEqual(result['native_observed_slot'], slot)

    def test_wrong_guid_household_sim_zone_or_uninstanced_sim_cannot_pass(self):
        variants = [dict(self.live, save_guid='99'), dict(self.live, household_id='99'),
            dict(self.live, sim={'id': '99', 'instanced': True}), dict(self.live, sim=None),
            dict(self.live, zone_id='99'), dict(self.live, sim={'id': SIM, 'instanced': False})]
        for altered in variants:
            with self.subTest(altered=altered):
                if self.output.exists(): self.output.unlink()
                result, _proof, calls = self.run_observe(snapshots=[altered])
                self.assertFalse(result['ok']); self.assertEqual(calls.count('test_snapshot'), 1)
                self.assertEqual(set(calls), {'test_snapshot', 'cas_ui_diagnostics'})

    def test_all_ten_persistence_checks_and_singleton_member_lists_are_required(self):
        for kind in ('missing-check', 'false-check', 'live-extra-member', 'persisted-extra-member'):
            altered = copy.deepcopy(self.live)
            if kind == 'missing-check': altered['persistence']['checks'].pop('sim_proto_identity')
            elif kind == 'false-check': altered['persistence']['checks']['sim_proto_identity'] = False
            elif kind == 'live-extra-member': altered['persistence']['household_sim_ids'].append('99')
            else: altered['persistence']['persisted_household_sim_ids'].append('99')
            with self.subTest(kind=kind):
                if self.output.exists(): self.output.unlink()
                result, _proof, _calls = self.run_observe(snapshots=[altered])
                self.assertFalse(result['ok'])

    def test_unpaused_clock_or_unreadable_ticks_is_refused_without_pause(self):
        for altered in (dict(self.live, clock_speed=1), dict(self.live, clock_speed=True),
                        dict(self.live, sim_now_ticks=1129711), dict(self.live, sim_now_ticks='01129711')):
            with self.subTest(altered=altered):
                if self.output.exists(): self.output.unlink()
                result, _proof, calls = self.run_observe(snapshots=[altered])
                self.assertFalse(result['ok']); self.assertNotIn('test_pause', calls)

    def test_tick_or_slot_drift_between_paused_reads_is_not_stable_presence(self):
        for field, value in (('sim_now_ticks', '1129712'), ('save_slot', 2), ('client_id', '8')):
            second = dict(self.live, request_id='2' * 32, **{field: value})
            with self.subTest(field=field):
                if self.output.exists(): self.output.unlink()
                result, proof, calls = self.run_observe(snapshots=[self.live, second])
                self.assertFalse(result['ok']); self.assertEqual(len(proof['snapshots']), 2)
                self.assertEqual(calls.count('test_snapshot'), 2)

    def test_same_snapshot_request_identity_does_not_count_as_two_fresh_reads(self):
        result, _proof, calls = self.run_observe(snapshots=[self.live, self.live])
        self.assertFalse(result['ok']); self.assertEqual(calls.count('test_snapshot'), 2)

    def test_changed_source_identity_after_first_read_stops_further_reads(self):
        def drift(_count, current): current[0] = dict(self.identity, script_sha256='f' * 64)
        result, _proof, calls = self.run_observe(after_read=drift)
        self.assertFalse(result['ok']); self.assertEqual(calls.count('test_snapshot'), 1)

    def test_active_cas_refuses_snapshot_and_all_inputs(self):
        diagnostics = copy.deepcopy(self.diagnostics)
        diagnostics['native_peers'] = [{'sim_id': SIM, 'age_seconds': 0}]
        result, _proof, calls = self.run_observe(diagnostics=diagnostics)
        self.assertFalse(result['ok']); self.assertEqual(calls, ['cas_ui_diagnostics'])

    def test_lost_read_response_is_retained_and_never_resubmitted(self):
        result, proof, calls = self.run_observe(snapshots=[OSError('lost snapshot response')])
        self.assertFalse(result['ok']); self.assertIn('lost snapshot', proof['error'])
        self.assertEqual(calls.count('test_snapshot'), 1)

    def test_current_save_drift_fails_the_separate_receipt(self):
        def drift(_count, _current):
            (self.profile / 'saves/Slot_ffffffff.save').write_bytes(b'changed current disposable autosave')
        result, proof, _calls = self.run_observe(after_read=drift)
        self.assertFalse(result['ok']); self.assertFalse(proof['save_files_unchanged'])

    def test_immutable_proof_drift_fails_the_separate_receipt(self):
        def drift(_count, _current): self.prior_path.write_bytes(b'changed external prerequisite')
        result, proof, calls = self.run_observe(after_read=drift)
        self.assertFalse(result['ok']); self.assertFalse(proof['prerequisite_unchanged'])
        self.assertEqual(calls.count('test_snapshot'), 1)

    def test_changed_baseline_or_original_slot_hash_refuses_before_any_read(self):
        self.slot.write_bytes(b'changed disposable normal save')
        with self.assertRaisesRegex(ValueError, 'eighteen-file family'):
            self.run_observe()
        self.assertFalse(self.output.exists())
