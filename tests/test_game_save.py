import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
from apex_core import test_driver, cas_ui
import apex_cli
import game_save
import reusable_profile
from source_manifest import write_json

SIM = '285159751289798669'
HOUSEHOLD = '285159751289798668'
GUID = '1841692672'


class SaveFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / reusable_profile.PROTECTED_NAME
        (self.profile / 'Mods/Apex').mkdir(parents=True)
        (self.profile / 'saves').mkdir()
        (self.original / 'saves').mkdir(parents=True)
        self.original_save = self.original / 'saves/Slot_00000002.save'
        self.original_save.write_bytes(b'owner save must never change')
        self.slot = self.profile / 'saves/Slot_00000002.save'
        self.slot.write_bytes(b'existing disposable test save')
        self.digest = hashlib.sha256(self.slot.read_bytes()).hexdigest()
        self.token = 'a' * 32
        write_json(self.profile / reusable_profile.legacy.MARKER, {'token': self.token, 'disposable': True})
        script = self.profile / 'Mods/Apex/ApexOccultHybrid.ts4script'
        script.write_bytes(b'exact staged script')
        self.script_hash = hashlib.sha256(script.read_bytes()).hexdigest()
        self.state = self.root / 'session.json'
        write_json(self.state, {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active',
            'token': self.token, 'profile': str(self.profile), 'protected_original': str(self.original),
            'artifacts': [{'name': script.name, 'relative': 'Apex/' + script.name, 'sha256': self.script_hash}]})
        self.identity = {'pid': 42, 'test_token': self.token, 'script_sha256': self.script_hash, 'profile': str(self.profile)}
        self.target = {'slot_id': 2, 'slot_name': 'Apex Disposable Test', 'expected_save_sha256': self.digest,
                       'save_guid': GUID, 'household_id': HOUSEHOLD, 'sim_id': SIM}
        self.slot_proto = Obj(slot_id=0, slot_name='Scratch')
        self.sim = Obj(id=int(SIM), household_id=int(HOUSEHOLD), account_id=123, first_name='Test', last_name='Sim',
                       occult_tracker=Obj(), get_sim_instance=lambda: object(), get_current_outfit=lambda: (0, 0))
        self.household = Obj(id=int(HOUSEHOLD), sim_info_gen=lambda: iter([self.sim]))
        self.native_sim = Obj(sim_id=int(SIM), household_id=int(HOUSEHOLD))
        self.native_household = Obj(household_id=int(HOUSEHOLD), sims=Obj(ids=[int(SIM)]))
        self.client = Obj(id=7)
        self.persistence = Obj(get_save_slot_proto_buff=lambda: self.slot_proto,
            get_save_slot_proto_guid=lambda: int(GUID), get_sim_proto_buff=lambda _sim: self.native_sim,
            get_household_proto_buff=lambda _household: self.native_household)
        self.zone = Obj(id=42, is_zone_running=True, is_in_build_buy=False)
        self.backend = Obj(__file__='ignored-for-identity-fixture', _get_sim_info_by_id=lambda _id: self.sim,
            _data_directory=lambda: str(self.profile / 'TD1_OccultHybridApexData'),
            _all_occults=lambda: (), _get_occult_flags=lambda _sim: 1, _get_current_flags=lambda _sim: 1,
            _v8_read_outfit_blob=lambda _sim: b'complete outfit bytes',
            services=Obj(get_persistence_service=lambda: self.persistence,
                active_household=lambda: self.household, current_zone=lambda: self.zone,
                game_clock_service=lambda: Obj(clock_speed=0, now=lambda: Obj(absolute_ticks=lambda: 100)),
                client_manager=lambda: Obj(get_first_client=lambda: self.client),
                sim_info_manager=lambda: Obj(get=lambda _id: self.sim)))
        self.override = Mock(return_value=None)
        self.modules = {'server_commands': Obj(), 'server_commands.persistence_commands': Obj(override_save_slot=self.override)}
        cas_ui._RECORDS.clear(); cas_ui._PEERS.clear()
        self.addCleanup(cas_ui._RECORDS.clear); self.addCleanup(cas_ui._PEERS.clear)

    def native_save(self, target=None):
        with patch.object(test_driver, 'guard', return_value=self.target if target is None else target), \
                patch.object(test_driver, 'runtime_identity', return_value=self.identity), \
                patch('apex_core.form_bank_seal.os.getpid', return_value=self.identity['pid']), patch.dict(sys.modules, self.modules):
            return test_driver.dispatch(self.backend, 'test_save', SIM, '{}')


class NativeSaveTargetTests(SaveFixture):
    def test_scratch_and_zero_can_target_one_existing_normal_file_without_direct_proto_mutation(self):
        for runtime_slot in (0, 0xffffffff, 2):
            with self.subTest(runtime_slot=runtime_slot):
                self.slot_proto.slot_id = runtime_slot
                self.override.reset_mock()
                result = self.native_save()
                self.assertTrue(result['ok'])
                self.assertTrue(result['save_submitted'])
                self.assertFalse(result['save_completed_file_verified'])
                self.assertFalse(result['save_reload_verified'])
                self.assertFalse(result['retry_safe'])
                self.assertEqual(result['runtime_slot_before'], runtime_slot)
                self.assertEqual(self.slot_proto.slot_id, runtime_slot)
                self.override.assert_called_once_with(2, self.target['slot_name'], auto_save_slot_id=None,
                                                       ignore_callback=False, _connection=7)
                self.assertEqual(self.slot.read_bytes(), b'existing disposable test save')
                self.assertEqual(self.original_save.read_bytes(), b'owner save must never change')

    def test_wrong_native_guid_household_sim_manager_or_proto_membership_refuses_save(self):
        for failure in ('guid', 'household', 'sim', 'manager', 'membership', 'zone'):
            with self.subTest(failure=failure):
                target = dict(self.target)
                changes = []
                if failure in ('guid', 'household', 'sim'):
                    target[{'guid': 'save_guid', 'household': 'household_id', 'sim': 'sim_id'}[failure]] = '123'
                elif failure == 'manager':
                    changes.append(patch.object(self.backend.services, 'sim_info_manager', return_value=Obj(get=lambda _: object())))
                elif failure == 'membership':
                    changes.append(patch.object(self.native_household.sims, 'ids', []))
                else:
                    changes.append(patch.object(self.zone, 'is_zone_running', False))
                for change in changes: change.start()
                try:
                    with self.assertRaises(ValueError): self.native_save(target)
                    self.override.assert_not_called()
                finally:
                    for change in reversed(changes): change.stop()

    def test_hash_mismatch_missing_empty_hardlinked_or_reparse_target_refuses_without_creation(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
            self.native_save(dict(self.target, expected_save_sha256='b' * 64))
        self.slot.unlink()
        with self.assertRaises(FileNotFoundError): self.native_save()
        self.assertFalse(self.slot.exists())
        self.slot.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'existing nonempty'): self.native_save()
        self.slot.unlink()
        os.link(self.original_save, self.slot)
        with self.assertRaisesRegex(ValueError, 'unlinked regular'): self.native_save()
        self.override.assert_not_called()
        self.assertEqual(self.original_save.read_bytes(), b'owner save must never change')

    def test_protected_original_profile_or_active_cas_cannot_be_used_for_save(self):
        with patch.object(test_driver, 'runtime_identity', return_value=dict(self.identity, profile=str(self.original))):
            with self.assertRaises(ValueError):
                with patch.object(test_driver, 'guard', return_value=self.target), patch.dict(sys.modules, self.modules):
                    test_driver.dispatch(self.backend, 'test_save', SIM, '{}')
        cas_ui._PEERS['token'] = {'sim_id': SIM}
        with self.assertRaisesRegex(ValueError, 'CAS is active'): self.native_save()
        self.override.assert_not_called()

    def test_unresolved_cas_or_incomplete_persistence_schema_cannot_pass_as_live_save_context(self):
        cas_ui._RECORDS['a' * 32] = {'state': 'accept-intent'}
        with self.assertRaisesRegex(ValueError, 'CAS is active'): self.native_save()
        cas_ui._RECORDS.clear()
        snapshot = test_driver.snapshot(self.backend, self.sim)
        snapshot['persistence']['checks'].pop('sim_proto_identity')
        with patch.object(test_driver, 'snapshot', return_value=snapshot):
            with self.assertRaises(ValueError): self.native_save()
        self.override.assert_not_called()

    def test_typed_target_cannot_request_scratch_new_slot_arbitrary_paths_or_coerced_ids(self):
        for field, value in (('slot_id', 0), ('slot_id', 0xffffffff), ('slot_id', True),
                             ('slot_id', '2'), ('slot_name', ''), ('slot_name', 'a\nname'),
                             ('slot_name', 'a' * 129), ('sim_id', int(SIM)), ('save_guid', '0' + GUID)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.native_save(dict(self.target, **{field: value}))
        with self.assertRaises(ValueError): self.native_save(dict(self.target, path=str(self.original_save)))
        self.override.assert_not_called()

    def test_native_scheduling_exception_is_ambiguous_with_no_false_completed_or_retry_claim(self):
        self.override.side_effect = RuntimeError('after scheduling may have begun')
        result = self.native_save()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'unresolved')
        self.assertTrue(result['save_submission_attempted'])
        self.assertIsNone(result['save_submitted'])
        self.assertIn('after scheduling', result['native_error'])
        self.assertFalse(result['retry_safe'])
        self.override.assert_called_once()

    def test_native_false_is_refusal_and_unexpected_return_is_unknown_neither_counts_as_submission(self):
        self.override.return_value = False
        result = self.native_save()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'save-rejected')
        self.assertIs(result['save_submitted'], False)
        self.override.reset_mock(); self.override.return_value = True
        result = self.native_save()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'unresolved')
        self.assertIsNone(result['save_submitted'])
        self.assertFalse(result['retry_safe'])

    def test_legacy_untyped_save_cannot_schedule_or_write_any_slot(self):
        with patch.object(test_driver, 'guard', return_value=None), patch.dict(sys.modules, self.modules):
            with self.assertRaisesRegex(ValueError, 'typed existing slot'):
                test_driver.dispatch(self.backend, 'test_save', SIM, '{}')
        self.override.assert_not_called()
        self.assertEqual(self.slot.read_bytes(), b'existing disposable test save')


class SaveObserverTests(SaveFixture):
    def setUp(self):
        super().setUp()
        self.clock = 0
        self.alive = True
        self.output = self.root / 'save-proof.json'
        self.calls = []
        self.submissions = []
        self.handler = None
        self.transport_handler = None

    def transport(self, path, query=None, timeout=12):
        self.assertLessEqual(timeout, 2)
        if self.transport_handler:
            value = self.transport_handler(path, query)
            if value is not None: return value
        if path == '/api/bridge': return copy.deepcopy(self.identity)
        self.assertEqual(path, '/api/command')
        self.submissions.append(copy.deepcopy(query))
        if query['action'] == 'test_save':
            proof = json.loads(self.output.read_text())
            self.assertEqual(proof['save_request_id'], query['request_id'])  # Durable before native write.
        return {'ok': True}

    def request(self, state, action, sim_id=None, value=None, transport=None, **kwargs):
        self.clock += .01
        self.calls.append(action)
        transport('/api/bridge')
        rid = uuid.uuid4().hex
        transport('/api/command', {'action': action, 'request_id': rid})
        argument = json.loads(value)
        self.assertEqual(argument['test_token'], self.token)
        if self.handler:
            replacement = self.handler(action, argument['value'], rid)
            if replacement is not None: return replacement
        if action == 'test_snapshot': return test_driver.snapshot(self.backend, self.sim)
        self.assertEqual(action, 'test_save')
        self.assertEqual(argument['value'], self.target)
        # Emulate the native producer, not an observer file-write implementation.
        self.slot.write_bytes(b'native save contains complete test household')
        self.slot_proto.slot_id = 2
        return {'ok': True, 'save_submitted': True, 'request_id': rid, 'slot_id': 2,
                'save_guid': GUID, 'household_id': HOUSEHOLD, 'sim_id': SIM}

    def run_observer(self, **kwargs):
        result = game_save.observe(self.state, self.output, self.identity, self.request, SIM, 2,
                   self.target['slot_name'], self.digest, GUID, HOUSEHOLD, transport=self.transport,
                   alive=lambda _pid: self.alive, monotonic=lambda: self.clock,
                   pause=lambda seconds: setattr(self, 'clock', self.clock + seconds), seconds=3, **kwargs)
        self.assertEqual(self.original_save.read_bytes(), b'owner save must never change')
        return result, json.loads(self.output.read_text())

    def test_one_target_save_proves_stable_changed_file_and_native_slot_but_does_not_claim_reload(self):
        result, proof = self.run_observer()
        self.assertTrue(result['ok'], proof.get('error'))
        self.assertTrue(result['save_completed_file_verified'])
        self.assertTrue(result['native_target_slot_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertFalse(result['retry_safe'])
        self.assertEqual(self.calls, ['test_snapshot', 'test_save', 'test_snapshot'])
        self.assertEqual(sum(row['action'] == 'test_save' for row in self.submissions), 1)
        self.assertEqual(result['save_request_id'], next(row['request_id'] for row in self.submissions if row['action'] == 'test_save'))
        self.assertNotEqual(proof['target_before']['sha256'], proof['target_after']['sha256'])
        self.assertTrue(proof['crash_clear_verified'])
        self.assertTrue(proof['finalized'])

    def test_save_seal_completion_is_one_owner_request_after_actual_stable_file_change(self):
        intent_id = '1' * 32
        def handler(action, value, rid):
            if action == 'test_save':
                self.slot.write_bytes(b'native save with sealed appearance sidecar')
                self.slot_proto.slot_id = 2
                return {'ok': True, 'save_submitted': True, 'request_id': rid, 'slot_id': 2,
                    'save_guid': GUID, 'household_id': HOUSEHOLD, 'sim_id': SIM,
                    'form_bank_seal': {'state': 'save-intent', 'intent_id': intent_id, 'sealed': False}}
            if action == 'test_form_seal_complete':
                self.assertEqual(value, {'intent_id': intent_id, 'expected_save_sha256': hashlib.sha256(self.slot.read_bytes()).hexdigest()})
                proof = json.loads(self.output.read_text())
                self.assertTrue(proof['save_completed_file_verified'])
                self.assertEqual(proof['owner_requests'][-1]['action'], action)
                return {'ok': True, 'state': 'sealed', 'intent_id': intent_id,
                    'file_sha256': value['expected_save_sha256'], 'seal_sha256': 'c' * 64}
        self.handler = handler
        result, proof = self.run_observer()
        self.assertTrue(result['ok']); self.assertTrue(result['form_bank_seal_verified'])
        self.assertEqual(self.calls.count('test_save'), 1); self.assertEqual(self.calls.count('test_form_seal_complete'), 1)
        self.assertFalse(result['save_reload_verified'])

    def test_lost_seal_completion_keeps_durable_uuid_and_never_repeats_save_or_seal_command(self):
        intent_id = '1' * 32
        def handler(action, _value, rid):
            if action == 'test_save':
                self.slot.write_bytes(b'native changed save before lost seal response'); self.slot_proto.slot_id = 2
                return {'ok': True, 'save_submitted': True, 'request_id': rid, 'slot_id': 2,
                    'save_guid': GUID, 'household_id': HOUSEHOLD, 'sim_id': SIM,
                    'form_bank_seal': {'state': 'save-intent', 'intent_id': intent_id, 'sealed': False}}
            if action == 'test_form_seal_complete':
                raise OSError('completion response lost')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok']); self.assertTrue(result['save_completed_file_verified'])
        self.assertFalse(result['form_bank_seal_verified'])
        self.assertEqual(self.calls.count('test_save'), 1); self.assertEqual(self.calls.count('test_form_seal_complete'), 1)
        self.assertTrue(uuid_id := game_save.uuid_id(next(row['request_id'] for row in proof['owner_requests'] if row['action'] == 'test_form_seal_complete')))

    def test_changed_crash_is_retained_without_claiming_save_success(self):
        raw = b'<report><type>crash</type><categoryid>native-save-crash</categoryid></report>'
        def handler(action, _value, _rid):
            if action == 'test_save':
                (self.profile / 'lastCrash.txt').write_bytes(raw)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'crash')
        self.assertTrue(result['save_completed_file_verified'])
        self.assertTrue(result['native_target_slot_verified'])
        self.assertFalse(proof['crash_clear_verified'])
        self.assertTrue(proof['crash']['preserved'])
        self.assertEqual(Path(proof['crash']['path']).read_bytes(), raw)
        self.assertEqual(proof['crash']['after']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.calls.count('test_save'), 1)

    def test_changed_unsafe_crash_xml_is_refused_without_claiming_save_success(self):
        raw = b'<!DOCTYPE report><report/>'
        def handler(action, _value, _rid):
            if action == 'test_save':
                (self.profile / 'lastCrash.txt').write_bytes(raw)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'changed-crash-report-refused')
        self.assertTrue(result['save_completed_file_verified'])
        self.assertFalse(proof['crash_clear_verified'])
        self.assertEqual(proof['crash']['outcome'], 'refused')
        self.assertFalse(proof['crash']['preserved'])
        self.assertEqual(proof['crash']['after']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertFalse(list(self.root.glob('*-crash-*.xml')))
        self.assertEqual(self.calls.count('test_save'), 1)

    def test_unavailable_final_crash_read_cannot_claim_save_success(self):
        with patch.object(game_save.cas_transition, 'read_crash', side_effect=[
                ({'state': 'absent'}, None), ({'state': 'unreadable', 'error': 'read failed'}, None)]):
            result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'crash-observation-unresolved')
        self.assertTrue(result['save_completed_file_verified'])
        self.assertFalse(proof['crash_clear_verified'])
        self.assertEqual(proof['crash']['after']['state'], 'unreadable')
        self.assertEqual(self.calls.count('test_save'), 1)

    def test_changed_oversized_crash_cannot_claim_save_success(self):
        raw = b'x' * (game_save.cas_transition.MAX_CRASH_BYTES + 1)
        def handler(action, _value, _rid):
            if action == 'test_save':
                (self.profile / 'lastCrash.txt').write_bytes(raw)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'changed-crash-report-refused')
        self.assertTrue(result['save_completed_file_verified'])
        self.assertFalse(proof['crash_clear_verified'])
        self.assertEqual(proof['crash']['after']['state'], 'oversized')
        self.assertFalse(proof['crash']['preserved'])
        self.assertFalse(list(self.root.glob('*-crash-*.xml')))
        self.assertEqual(self.calls.count('test_save'), 1)

    def test_crash_preservation_failure_cannot_claim_save_success(self):
        with patch.object(game_save.cas_transition, 'preserve_crash', side_effect=OSError('evidence file unavailable')):
            result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'crash-observation-unresolved')
        self.assertTrue(result['save_completed_file_verified'])
        self.assertFalse(proof['crash_clear_verified'])
        self.assertEqual(proof['crash']['outcome'], 'refused')
        self.assertIn('evidence file unavailable', proof['crash']['error'])
        self.assertEqual(self.calls.count('test_save'), 1)

    def test_unchanged_prior_crash_does_not_invalidate_save_success(self):
        (self.profile / 'lastCrash.txt').write_bytes(b'<report><type>crash</type></report>')
        result, proof = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertTrue(proof['crash_clear_verified'])
        self.assertEqual(proof['crash']['outcome'], 'unchanged')
        self.assertFalse(proof['crash']['preserved'])
        self.assertFalse(list(self.root.glob('*-crash-*.xml')))

    def test_unreadable_crash_baseline_refuses_before_any_save_request(self):
        with patch.object(game_save.cas_transition, 'read_crash', return_value=({'state': 'unreadable'}, None)), \
                self.assertRaisesRegex(ValueError, 'crash baseline'):
            self.run_observer()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.submissions, [])
        self.assertEqual(self.slot.read_bytes(), b'existing disposable test save')
        self.assertFalse(self.output.exists())

    def test_changed_file_without_native_target_slot_readback_is_not_full_completion(self):
        def handler(action, _value, rid):
            if action == 'test_save':
                self.slot.write_bytes(b'native wrote file but slot state unverified')
                return {'ok': True, 'save_submitted': True, 'request_id': rid, 'slot_id': 2,
                        'save_guid': GUID, 'household_id': HOUSEHOLD, 'sim_id': SIM}
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['save_completed_file_verified'])
        self.assertFalse(result['native_target_slot_verified'])
        self.assertIn('native runtime slot', proof['error'])

    def test_lost_save_submission_response_retains_owner_uuid_without_any_save_replay(self):
        def handler(action, _value, _rid):
            if action == 'test_save':
                self.slot.write_bytes(b'game may have saved before response loss')
                raise OSError('response lost after save scheduling')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(game_save.uuid_id(result['save_request_id']))
        self.assertFalse(result['save_completed_file_verified'])
        self.assertEqual(self.calls, ['test_snapshot', 'test_save'])
        self.assertEqual(sum(row['action'] == 'test_save' for row in self.submissions), 1)

    def test_unchanged_file_after_successful_scheduling_is_unresolved_and_never_resubmitted(self):
        def handler(action, _value, rid):
            if action == 'test_save':
                return {'ok': True, 'save_submitted': True, 'request_id': rid, 'slot_id': 2,
                        'save_guid': GUID, 'household_id': HOUSEHOLD, 'sim_id': SIM}
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['save_submitted'])
        self.assertFalse(result['save_completed_file_verified'])
        self.assertEqual(sum(action == 'test_save' for action in self.calls), 1)
        self.assertLessEqual(len(proof['file_observations']), 2)

    def test_target_changes_after_preflight_or_bad_native_identity_refuse_before_save(self):
        def handler(action, _value, _rid):
            if action == 'test_snapshot': self.slot.write_bytes(b'concurrent external file change')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertIsNone(result['save_request_id'])
        self.assertEqual(self.calls, ['test_snapshot'])
        self.assertFalse(proof['save_command_attempted'])

    def test_bridge_pid_change_or_wrong_owner_receipt_stops_without_save_replay(self):
        self.transport_handler = lambda path, _query: dict(self.identity, pid=43) if path == '/api/bridge' else None
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(self.submissions, [])
        self.output.unlink(); self.calls.clear(); self.transport_handler = None
        def wrong(action, _value, _rid):
            if action == 'test_save': return {'ok': True, 'save_submitted': True, 'request_id': 'f' * 32}
        self.handler = wrong
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertIn('another owner UUID', proof['error'])
        self.assertEqual(self.calls, ['test_snapshot', 'test_save'])

    def test_new_output_hash_and_native_identity_checks_refuse_without_any_game_command(self):
        for output in (self.state, self.profile / 'proof.json', self.original / 'proof.json', self.root / 'missing/proof.json'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                game_save.observe(self.state, output, self.identity, self.request, SIM, 2,
                    self.target['slot_name'], self.digest, GUID, HOUSEHOLD)
        with self.assertRaises(ValueError):
            game_save.observe(self.state, self.output, self.identity, self.request, SIM, 2,
                self.target['slot_name'], 'f' * 64, GUID, HOUSEHOLD)
        self.assertFalse(self.calls)
        self.assertFalse(self.output.exists())

    def test_cli_save_exposes_only_typed_slot_and_native_identity_arguments(self):
        args = apex_cli.parser().parse_args(['game', 'save', '--state', 'state.json', '--sim-id', SIM,
               '--slot-id', '0x2', '--slot-name', 'Test', '--expected-save-sha256', self.digest,
               '--save-guid', GUID, '--household-id', HOUSEHOLD, '--output', 'proof.json'])
        self.assertEqual(args.slot_id, 2)
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli.reusable_profile, 'load',
                  return_value=(self.state, {'token': self.token}, self.profile, self.original)), \
                patch.object(apex_cli, 'verified_identity', return_value=self.identity), \
                patch.object(game_save, 'observe', return_value={'ok': True}) as observe:
            self.assertEqual(apex_cli.execute(args), {'ok': True})
        self.assertEqual(observe.call_args.args[4:10], (SIM, 2, 'Test', self.digest, GUID, HOUSEHOLD))


if __name__ == '__main__':
    unittest.main()
