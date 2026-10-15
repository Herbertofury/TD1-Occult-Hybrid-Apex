"""Native admission wrappers with real durable CAS receiver transactions.

Synthetic native methods model the inspected generator's early lock return;
host instruction pins cover only these fixtures. Production Python 3.7 pins
were independently checked against the installed simulation.zip code objects.
No game, profile, save file, native game code or native serializer is run.
"""
import copy
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_save_boundary as gate, cas_bank_transaction as bank
from apex_core import form_bank, test_driver
import test_cas_bank_transaction as fixture
SaveGameResult = Obj(FAILED_SAVE_LOCKED='FAILED_SAVE_LOCKED')


def native_service_type():
    class NativePersistence:
        def __init__(self):
            self.native_reason = None
            self.native_locked = False
            self.serializer_calls = []
            self.save_file_creations = []

        def get_save_slot_proto_guid(self):
            return 30

        def is_save_locked(self):
            return self.native_locked

        def get_save_lock_tooltip(self):
            return self.native_reason

        def _save_game_gen(self, timeline, save_game_data, check_cooldown):
            # Inspected EA generator checks this before any other save work.
            reason = self.get_save_lock_tooltip()
            if reason is not None:
                return ('FAILED_SAVE_LOCKED', reason)
            self.serializer_calls.append(save_game_data)
            yield 'serialized'
            self.save_file_creations.append(save_game_data)
            return ('SUCCESS', None)

        def save(self, mode):
            return self._save_game_gen(None, mode, True)
    return NativePersistence


class NativeSaveBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.game = fixture.CasBankReceiverTests()
        self.game.setUp()
        self.addCleanup(self.game.doCleanups)
        self.backend = self.game.backend
        self.cls = native_service_type()
        self.service = self.cls()
        self.backend.services.get_persistence_service = lambda: self.service
        self.contract = {name: gate._shape(getattr(self.cls, name)) for name in gate._CONTRACT}
        self.enterContext(patch.object(gate, '_CONTRACT', self.contract))
        self.reason = object()
        self.original_generator = self.cls._save_game_gen

    def install(self):
        return gate.install(self.backend, reason_factory=lambda _text: self.reason)

    def finish_unchanged(self):
        self.game.observe()
        self.game.prepare([])
        return self.game.commit()

    def run_save(self, mode='Save'):
        steps = []
        generator = self.service.save(mode)
        try:
            while True:
                steps.append(next(generator))
        except StopIteration as ended:
            return ended.value, steps

    def assert_blocked_before_serialization(self, pending=None):
        self.assertTrue(self.service.is_save_locked())
        self.assertIs(self.service.get_save_lock_tooltip(), self.reason)
        if pending is not None:
            self.assertEqual(self.backend._APEX_CAS_SAVE_ADMISSION['pending_sim_ids'], pending)
        for mode in ('Save', 'Save As', 'Save and Exit', 'autosave'):
            result, steps = self.run_save(mode)
            self.assertEqual(result, ('FAILED_SAVE_LOCKED', self.reason))
            self.assertEqual(steps, [])
        self.assertEqual(self.service.serializer_calls, [])
        self.assertEqual(self.service.save_file_creations, [])
        self.assertEqual(self.game.native_writes, [])

    def test_all_native_save_modes_fail_before_serializer_during_real_capture_then_allow_after_commit(self):
        self.install()
        original = self.game.path.read_bytes()
        self.game.begin()
        retained = self.game.path.read_bytes()
        self.assertNotEqual(original, retained)
        self.assert_blocked_before_serialization(['10'])
        self.assertEqual(self.game.path.read_bytes(), retained)
        receipt = self.finish_unchanged()
        self.assertTrue(receipt['all_native_owners_verified'])
        self.assertFalse(self.service.is_save_locked())
        self.assertIsNone(self.service.get_save_lock_tooltip())
        self.assertEqual(self.run_save(), (('SUCCESS', None), ['serialized']))
        self.assertEqual(self.service.serializer_calls, ['Save'])
        self.assertEqual(self.service.save_file_creations, ['Save'])

    def test_raw_unaccepted_human_and_spellcaster_edits_remain_locked_without_automatic_restore(self):
        self.install()
        self.game.begin()
        self.game.edit(1, value='unaccepted Human')
        self.game.edit(16, value='unaccepted Spellcaster')
        self.game.observe()
        self.assertEqual(self.game.observation['changed_lanes'], ['1', '16'])
        retained = self.game.path.read_bytes()
        self.assert_blocked_before_serialization(['10'])
        self.assertEqual(self.game.forms[1].physique, 'unaccepted Human')
        self.assertEqual(self.game.forms[16].physique, 'unaccepted Spellcaster')
        self.assertEqual(self.game.path.read_bytes(), retained)
        self.assertFalse(self.backend._APEX_CAS_SAVE_ADMISSION['automatic_restore_performed'])

    def test_internal_cas_snapshot_serialization_still_runs_and_native_save_generator_is_unmodified(self):
        self.install()
        self.game.begin()
        self.assertTrue(self.service.is_save_locked())
        self.assertEqual(self.game.snapshot_calls, [])
        self.game.observe()
        self.assertEqual(self.game.snapshot_calls, [10])
        self.assertIs(self.cls._save_game_gen, self.original_generator)
        self.assertEqual(self.service.serializer_calls, [])
        self.assertEqual(self.service.save_file_creations, [])

    def test_unloaded_old_runtime_companion_blocks_after_selected_member_explicit_commit(self):
        self.install()
        self.game.begin()
        value = self.game.data()
        value['records']['30:99']['pending'] = {'runtime_pid': 1, 'state': 'legacy-unresolved'}
        form_bank.save(self.game.path, value)
        self.assert_blocked_before_serialization(['10', '99'])
        self.finish_unchanged()
        self.assertFalse(bank._blocked(self.game.record(), self.game.key))
        self.assert_blocked_before_serialization(['99'])
        self.assertNotIn(99, self.game.snapshot_calls)

    def test_actual_completed_old_runtime_receipt_is_allowed_without_replaying_appearance(self):
        self.game.begin()
        self.finish_unchanged()
        self.assertTrue(bank._completed(self.game.record()['cas_transaction']))
        self.install()
        original = self.game.path.read_bytes()
        with patch.object(bank.os, 'getpid', return_value=1):
            self.assertFalse(self.service.is_save_locked())
            self.assertIsNone(self.service.get_save_lock_tooltip())
        self.assertEqual(self.game.path.read_bytes(), original)
        self.assertEqual(self.game.native_writes, [])

    def test_corrupt_completed_receipt_stays_blocked_after_runtime_change(self):
        self.game.begin()
        self.finish_unchanged()
        data = self.game.data()
        data['records'][self.game.key]['cas_transaction']['metadata_commit']['plan_sha256'] = 'f' * 64
        form_bank.save(self.game.path, data)
        self.install()
        self.assert_blocked_before_serialization(['10'])

    def test_other_save_unresolved_record_is_ignored_but_current_save_switch_is_locked(self):
        data = self.game.data()
        data['records']['31:88'] = {'pending': {'runtime_pid': 1}}
        form_bank.save(self.game.path, data)
        self.install()
        self.assertFalse(self.service.is_save_locked())
        data = self.game.data()
        data['records']['30:99']['switch_pending'] = {'runtime_pid': 1}
        form_bank.save(self.game.path, data)
        self.assert_blocked_before_serialization(['99'])

    def test_native_lock_and_reason_win_without_reading_bank_and_other_service_is_unchanged(self):
        self.install()
        self.service.native_locked = True
        native_reason = object()
        self.service.native_reason = native_reason
        other = self.cls()
        with patch.object(gate, 'admission', side_effect=AssertionError('unexpected scan')):
            self.assertTrue(self.service.is_save_locked())
            self.assertIs(self.service.get_save_lock_tooltip(), native_reason)
            self.assertFalse(other.is_save_locked())
            self.assertIsNone(other.get_save_lock_tooltip())

    def test_queries_fail_closed_on_malformed_duplicated_nonfinite_unknown_or_oversized_bank(self):
        self.install()
        payloads = (
            b'{', b'{"schema":1,"schema":1,"records":{}}',
            b'{"schema":1,"records":{},"future":NaN}',
            b'{"schema":true,"records":{}}',
            b'{"schema":1,"records":{"bad-owner":{}}}',
            b'{"schema":1,"records":{"30:99":[]}}', b'', b'x' * 257)
        for payload in payloads:
            with self.subTest(payload=payload[:80]), patch.object(gate, 'MAX_BANK', 256):
                self.game.path.write_bytes(payload)
                self.assert_blocked_before_serialization()
                result = self.backend._APEX_CAS_SAVE_ADMISSION
                self.assertEqual(result['reason'], 'retained-cas-authority-unavailable')
                self.assertFalse(result['save_file_written'])
                self.assertFalse(result['appearance_written'])
                self.assertEqual(self.game.path.read_bytes(), payload)

    def test_absent_or_empty_bank_allows_and_unknown_writer_lease_refuses_without_removal(self):
        self.install()
        self.game.path.unlink()
        self.assertFalse(self.service.is_save_locked())
        self.game.path.write_text('{"schema":1,"records":{}}', encoding='utf-8')
        self.assertFalse(self.service.is_save_locked())
        held = bank._lease_path(self.game.path)
        held.write_bytes(b'unresolved old writer')
        self.assert_blocked_before_serialization()
        self.assertEqual(held.read_bytes(), b'unresolved old writer')

    def test_wrong_game_thread_or_unknown_save_guid_refuses_before_serializer(self):
        self.install()
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident + 1
        self.assert_blocked_before_serialization()
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident
        for guid in (0, -1, '030', True, None, 1 << 64):
            with self.subTest(guid=guid):
                self.service.get_save_slot_proto_guid = lambda guid=guid: guid
                self.assert_blocked_before_serialization()

    def test_version_mismatch_refuses_before_wrapper_install_and_before_new_entry(self):
        for name in self.contract:
            with self.subTest(method=name), patch.dict(gate._CONTRACT, {name: ('f' * 64, 'e' * 64)}):
                with self.assertRaisesRegex(ValueError, name):
                    self.install()
                self.assertFalse(self.backend._APEX_CAS_SAVE_BOUNDARY_READY)
                self.assertFalse(hasattr(self.cls.is_save_locked, '_apex_cas_save_boundary'))
                self.assertFalse(hasattr(self.cls.get_save_lock_tooltip, '_apex_cas_save_boundary'))
        self.backend.services.client_manager = lambda: Obj(get_first_client=lambda: Obj(id=50))
        self.game.sim.get_sim_instance = lambda: object()
        before = self.game.path.read_bytes()
        for mode in (None, 'full', 'native-full', 'mccc-full'):
            with self.subTest(mode=mode), patch.object(test_driver, 'guard', return_value=mode), \
                    patch.object(gate, 'require_installed', side_effect=ValueError('unsupported save boundary')):
                with self.assertRaisesRegex(ValueError, 'unsupported save boundary'):
                    test_driver.dispatch(self.backend, 'test_cas', '10', '{}')
        self.assertEqual(self.game.path.read_bytes(), before)
        self.assertEqual(self.game.native_writes, [])
        self.assertEqual(self.game.snapshot_calls, [])

    def test_localized_reason_required_and_install_is_idempotent_with_no_periodic_scan(self):
        with self.assertRaisesRegex(ValueError, 'localized'):
            gate.install(self.backend, reason_factory=lambda _text: None)
        with patch.object(gate, 'admission', side_effect=AssertionError('install must not scan')):
            self.assertTrue(self.install())
            locked, tooltip = self.cls.is_save_locked, self.cls.get_save_lock_tooltip
            self.assertTrue(gate.require_installed(self.backend))
        self.assertIs(self.cls.is_save_locked, locked)
        self.assertIs(self.cls.get_save_lock_tooltip, tooltip)
        self.assertIs(self.cls._save_game_gen, self.original_generator)

    def test_probe_exercises_only_the_real_early_locked_branch_and_never_an_idle_save(self):
        self.install()
        self.game.begin()
        result = gate.probe(self.backend, True)
        self.assertTrue(result['native_locked_generator_verified'])
        self.assertEqual(self.service.serializer_calls, [])
        self.assertEqual(self.service.save_file_creations, [])
        self.finish_unchanged()
        with self.assertRaisesRegex(ValueError, 'actual pending'):
            gate.probe(self.backend, True)
        self.assertEqual(self.service.serializer_calls, [])


if __name__ == '__main__':
    unittest.main()
