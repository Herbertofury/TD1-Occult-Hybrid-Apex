"""Real sidecar receiver around a synthetic one-shot native save generator."""
import hashlib
import threading
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch
import test_household_bank_seal as fixture
from apex_core import named_save_boundary as boundary, form_bank_seal as seal

SaveGameResult = Obj(SUCCESS='SUCCESS', FAILED_SAVE_LOCKED='FAILED_SAVE_LOCKED')


class NamedSaveBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.game = fixture.HouseholdBankSealTests(); self.game.setUp()
        self.addCleanup(self.game.doCleanups)
        self.backend = self.game.backend
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        self.backend._get_active_sim_info = lambda: self.game.sim
        self.service = Obj(get_save_slot_proto_guid=lambda: int(fixture.GUID), get_save_lock_tooltip=lambda: None)
        self.backend.services.get_persistence_service = lambda: self.service
        self.data = Obj(slot_id=2, slot_name=self.game.target['slot_name'])
        self.native_calls = []; self.target = self.game.slot
        self.reason = object()

    def run_save(self, native=None):
        game = self
        if native is None:
            def native(service, timeline, save_game_data, check_cooldown=True):
                game.native_calls.append(save_game_data)
                yield 'native-wait'
                game.target.write_bytes(b'one native generator completed household save')
                return (SaveGameResult.SUCCESS, None)
        wrapped = boundary.wrap(self.backend, native, self.reason)
        generator = wrapped(self.service, None, self.data)
        steps = []
        try:
            while True: steps.append(next(generator))
        except StopIteration as stopped:
            return stopped.value, steps

    def test_normal_save_certifies_all_members_without_cli_or_second_native_submission(self):
        bank_before = self.game.bank_path.read_bytes()
        returned, steps = self.run_save()
        self.assertEqual(returned, (SaveGameResult.SUCCESS, None))
        self.assertEqual(steps, ['native-wait']); self.assertEqual(len(self.native_calls), 1)
        records = seal._store(self.game.path)['records']
        self.assertEqual(len(records), 3)
        self.assertEqual({row['state'] for row in records.values()}, {'sealed'})
        self.assertEqual({row['file_sha256'] for row in records.values()}, {hashlib.sha256(self.target.read_bytes()).hexdigest()})
        self.assertEqual(self.game.bank_path.read_bytes(), bank_before); self.assertEqual(self.game.writes, [])

    def test_save_as_new_native_slot_does_not_need_preexisting_file(self):
        self.data.slot_id = 7
        original_live = self.game.live
        self.game.live = lambda: dict(original_live(), save_slot=7)
        self.target = self.game.profile / 'saves/Slot_00000007.save'
        self.assertFalse(self.target.exists())
        returned, _ = self.run_save()
        self.assertEqual(returned[0], SaveGameResult.SUCCESS)
        records = seal._store(self.game.path)['records']
        self.assertEqual({row['target']['slot_id'] for row in records.values()}, {7})
        self.assertEqual({row['before_file']['exists'] for row in records.values()}, {False})
        self.assertEqual(self.backend._APEX_NAMED_SAVE_BOUNDARY['state'], 'sealed')

    def test_cli_prepared_submission_is_reused_and_later_completion_is_idempotent(self):
        receipt = self.game.begin(); seal.submitted(self.backend, self.game.sim, receipt, True)
        with patch.object(seal, 'begin_save', side_effect=AssertionError('second capture')):
            self.run_save()
        self.assertEqual(self.backend._APEX_NAMED_SAVE_BOUNDARY['intent_id'], receipt['intent_id'])
        result = seal.complete_save(self.backend, self.game.sim, dict(intent_id=receipt['intent_id'],
            expected_save_sha256=hashlib.sha256(self.target.read_bytes()).hexdigest()))
        self.assertEqual(result['state'], 'sealed'); self.assertEqual(len(self.native_calls), 1)

    def test_capture_failure_refuses_before_native_serialization(self):
        self.game.sims[-1].occult_tracker._sim_info_map[2].physique = 'unreviewed native change'
        original = self.target.read_bytes()
        returned, steps = self.run_save()
        self.assertEqual(returned, (SaveGameResult.FAILED_SAVE_LOCKED, self.reason))
        self.assertEqual(steps, []); self.assertEqual(self.native_calls, [])
        self.assertFalse(self.game.path.exists()); self.assertEqual(self.target.read_bytes(), original)

    def test_native_failure_retains_rejected_metadata_and_native_return(self):
        def native(service, timeline, save_game_data, check_cooldown=True):
            yield 'native-check'
            return ('FAILED_ON_COOLDOWN', 'native-reason')
        returned, _ = self.run_save(native)
        self.assertEqual(returned, ('FAILED_ON_COOLDOWN', 'native-reason'))
        self.assertEqual({row['state'] for row in seal._store(self.game.path)['records'].values()}, {'save-rejected'})

    def test_native_exception_remains_unknown_and_is_not_swallowed_or_replayed(self):
        def native(service, timeline, save_game_data, check_cooldown=True):
            yield 'native-start'
            raise RuntimeError('native serialization exception')
        with self.assertRaisesRegex(RuntimeError, 'native serialization exception'): self.run_save(native)
        self.assertEqual({row['state'] for row in seal._store(self.game.path)['records'].values()}, {'save-submitted'})

    def test_cancelled_native_generator_keeps_pending_intent_without_second_save(self):
        def native(service, timeline, save_game_data, check_cooldown=True):
            yield 'native-start'
            raise AssertionError('cancelled work continued')
        generator = boundary.wrap(self.backend, native, self.reason)(self.service, None, self.data)
        self.assertEqual(next(generator), 'native-start'); generator.close()
        self.assertEqual({row['state'] for row in seal._store(self.game.path)['records'].values()}, {'save-submitted'})

    def test_sidecar_completion_failure_does_not_lie_about_or_repeat_successful_native_save(self):
        with patch.object(seal, 'complete_save', side_effect=OSError('sidecar unavailable')):
            returned, _ = self.run_save()
        self.assertEqual(returned, (SaveGameResult.SUCCESS, None)); self.assertEqual(len(self.native_calls), 1)
        self.assertTrue(self.target.exists()); self.assertEqual(self.backend._APEX_NAMED_SAVE_BOUNDARY['state'], 'completion-unresolved')
        self.assertFalse(self.backend._APEX_NAMED_SAVE_BOUNDARY['native_save_replay_allowed'])

    def test_internal_scratch_save_has_no_player_sidecar_or_extra_native_work(self):
        self.data.slot_id = 0
        with patch.object(seal, '_identity', side_effect=AssertionError('scratch player save')):
            self.run_save()
        self.assertFalse(self.game.path.exists()); self.assertEqual(len(self.native_calls), 1)
