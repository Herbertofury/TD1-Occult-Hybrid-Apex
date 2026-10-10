import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_bank_seal as seal, form_bank, form_appearance as appearance, test_driver, cas_ui
from test_outfit_snapshot import outfit

SIM, HH, GUID = '285159751289798669', '285159751289798668', '1841692672'


class SealFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.profile = self.root / 'The Sims 4'
        self.protected = self.root / 'The Sims 4 DO NOT FUCKING TOUCH!!!'
        self.protected.mkdir(); (self.protected / 'owner-save').write_bytes(b'owner original')
        (self.profile / 'saves').mkdir(parents=True); self.data_dir = self.profile / 'TD1_OccultHybridApexData'; self.data_dir.mkdir()
        self.slot = self.profile / 'saves/Slot_00000002.save'; self.slot.write_bytes(b'prior native save')
        self.identity = {'pid': os.getpid(), 'profile': str(self.profile), 'test_token': 'a' * 32, 'script_sha256': 'b' * 64}
        (self.profile / '.apex-disposable-profile.json').write_text(json.dumps({'disposable': True, 'token': 'a' * 32}))
        self.forms = {flag: Obj(id=1000 + flag, physique='independent-' + str(flag), pelt_layers=b'pelt-' + str(flag).encode(),
            custom_texture=b'texture-' + str(flag).encode(), genetic_data=b'genetics-' + str(flag).encode(),
            blob=outfit(0, flag) + outfit(7, flag + 90)) for flag in seal.FORMS}
        self.sim = Obj(id=int(SIM), household_id=int(HH), current_occult_types=64)
        for name, value in vars(self.forms[64]).items():
            if name != 'id': setattr(self.sim, name, value)
        self.tracker = Obj(sim_info=self.sim, _sim_info=self.sim, _sim_info_map=self.forms, OCCULT_DATA={flag: object() for flag in seal.FORMS[1:]},
                           has_occult_type=lambda kind: True)
        self.sim.occult_tracker = self.tracker
        def generate(kind, generate_new):
            self.assertFalse(generate_new)
            owner = Obj(id=2000 + int(kind), physique='native incomplete Witch', blob=outfit(0, 888))
            self.forms[int(kind)] = owner
            return owner
        self.tracker._generate_sim_info = Mock(side_effect=generate)
        self.writes = []
        def restore(owner, fields):
            self.writes.append(owner.id)
            for name, value in fields.items():
                if name == '__outfits__': owner.blob = value[1]
                else: setattr(owner, name, value)
        self.backend = Obj(__file__='fixture', _data_directory=lambda: str(self.data_dir),
            services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: int(GUID))),
            _all_occults=lambda: seal.FORMS[1:], _form_map=lambda tracker: tracker._sim_info_map,
            _coerce_flags=int, _get_current_flags=lambda owner: owner.current_occult_types,
            _v8_read_outfit_blob=lambda owner: owner.blob, _restore_siminfo_payload=restore,
            _ensure_human_form=lambda tracker: self.forms.get(1), _ensure_form=lambda tracker, kind, **kwargs: self.forms.get(kind),
            _resend_all_visuals=lambda sim: None)
        self.key = GUID + ':' + SIM; self.bank_path = self.data_dir / 'form_bank.json'
        self.bank = {'schema': 1, 'records': {self.key: {'runtime_pid': self.identity['pid'], 'pending': None,
            'switch_pending': None, 'history': [{'state': 'completed'}],
            'bank': {str(flag): appearance.packed(self.backend, owner) for flag, owner in self.forms.items()}}}}
        self.bank_path.write_text(json.dumps(self.bank)); self.path = self.data_dir / 'form_bank_seals.json'
        self.target = {'slot_id': 2, 'slot_name': 'Apex Disposable', 'expected_save_sha256': hashlib.sha256(self.slot.read_bytes()).hexdigest(),
                       'save_guid': GUID, 'household_id': HH, 'sim_id': SIM}
        self.enterContext(patch.object(test_driver, 'runtime_identity', side_effect=lambda _: dict(self.identity)))
        self.enterContext(patch.object(test_driver, 'snapshot', side_effect=lambda *args: self.live()))
        self.enterContext(patch('apex_core.hybrid_persistence._appearance_backend', return_value=self.backend))
        self.enterContext(patch('apex_core.form_bank_seal.os.getpid', side_effect=lambda: self.identity['pid']))
        cas_ui._PEERS.clear(); cas_ui._RECORDS.clear(); seal._LOADED.clear()
        self.addCleanup(cas_ui._PEERS.clear); self.addCleanup(cas_ui._RECORDS.clear); self.addCleanup(seal._LOADED.clear)

    def tearDown(self):
        self.assertEqual((self.protected / 'owner-save').read_bytes(), b'owner original')

    def live(self):
        return {'ok': True, 'save_slot': 2, 'save_guid': GUID, 'household_id': HH, 'client_id': '44', 'zone_id': '55',
            'in_build_buy': False, 'zone_running': True, 'clock_speed': 0,
            'runtime_queries': {'client_id': 'returned-value', 'zone_running': 'returned-value'},
            'sim': {'id': SIM, 'instanced': True}, 'persistence': {'persistence_verified_before_save': True,
                'checks': {name: True for name in ('active_household_membership', 'runtime_household_identity', 'manager_identity',
                    'account_save_eligible', 'sim_proto_exists', 'sim_proto_identity', 'sim_proto_household_identity',
                    'household_proto_exists', 'household_proto_identity', 'household_proto_membership')}}}

    def begin(self):
        return seal.begin_save(self.backend, self.sim, self.target, self.live(), test_driver._save_file_evidence(self.profile, 2))

    def certify(self):
        receipt = self.begin(); seal.submitted(self.backend, self.sim, receipt, True)
        self.slot.write_bytes(b'actual changed native save')
        checksum = hashlib.sha256(self.slot.read_bytes()).hexdigest()
        return seal.complete_save(self.backend, self.sim, {'intent_id': receipt['intent_id'], 'expected_save_sha256': checksum})

    def reload(self):
        self.identity['pid'] += 1
        self.forms.pop(16)
        self.forms[1].physique = 'native lost Human'; self.forms[1].pelt_layers = b'native lost pelt'
        self.forms[64].custom_texture = b'native lost texture'; self.sim.custom_texture = b'native lost texture'
        seal.note_loaded(self.tracker)


class SealTests(SealFixture):
    def test_fresh_native_rebase_without_new_cas_completion_cannot_reuse_old_completed_history(self):
        bank = form_bank.load(self.bank_path)
        bank['records'][self.key]['native_rebase_requires_cas_completion'] = True
        form_bank.save(self.bank_path, bank)
        with self.assertRaisesRegex(ValueError, 'completed seven-lane'):
            self.begin()
        self.assertFalse(self.path.exists()); self.assertEqual(self.writes, [])

    def test_sealed_current_runtime_switch_authorization_is_exact_and_does_not_rewrite_bank(self):
        certified = self.certify(); self.reload()
        seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        original = self.bank_path.read_bytes()
        record = form_bank.load(self.bank_path)['records'][self.key]
        self.assertTrue(seal.current_runtime_bank_verified(self.backend, self.sim, record))
        altered = copy.deepcopy(record); altered['bank']['1']['physique']['value'] = 'changed bank'
        self.assertFalse(seal.current_runtime_bank_verified(self.backend, self.sim, altered))
        self.identity['script_sha256'] = 'c' * 64
        self.assertFalse(seal.current_runtime_bank_verified(self.backend, self.sim, record))
        self.assertEqual(self.bank_path.read_bytes(), original)

    def test_certified_reloaded_owners_restore_complete_appearance_and_native_witch_without_touching_save_or_bank(self):
        certified = self.certify(); bank_before, file_before = self.bank_path.read_bytes(), self.slot.read_bytes()
        self.reload(); self.assertEqual(self.writes, [])
        result = seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.assertTrue(result['ok']); self.assertEqual(result['stored_forms_verified'], list(seal.FORMS))
        self.assertEqual(result['created_forms'], [{'flags': 16, 'id': '2016'}])
        self.tracker._generate_sim_info.assert_called_once_with(16, generate_new=False)
        for lane, expected in self.bank['records'][self.key]['bank'].items():
            self.assertEqual(appearance.packed(self.backend, self.forms[int(lane)]), expected)
        self.assertEqual(appearance.packed(self.backend, self.sim), self.bank['records'][self.key]['bank']['64'])
        self.assertEqual(self.bank_path.read_bytes(), bank_before); self.assertEqual(self.slot.read_bytes(), file_before)
        with self.assertRaisesRegex(ValueError, 'already reconciled in this runtime'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})

    def test_preexisting_bank_native_mismatch_refuses_before_native_save_or_sidecar_write(self):
        self.forms[1].physique = 'new unsaved edit'
        with self.assertRaisesRegex(ValueError, 'differs from bank before save'): self.begin()
        self.assertFalse(self.path.exists()); self.assertEqual(self.writes, [])

    def test_next_save_after_certified_reconciliation_uses_current_receipt_without_rewriting_bank_pid(self):
        certified = self.certify(); self.reload()
        original_bank = self.bank_path.read_bytes()
        seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        next_intent = self.begin()
        self.assertEqual(next_intent['state'], 'save-intent')
        self.assertNotEqual(next_intent['intent_id'], certified['intent_id'])
        self.assertEqual(self.bank_path.read_bytes(), original_bank)
        self.assertEqual(seal._store(self.path)['records'][self.key]['identity']['pid'], self.identity['pid'])

    def test_completion_needs_original_submitted_intent_and_actual_changed_file(self):
        receipt = self.begin()
        value = {'intent_id': receipt['intent_id'], 'expected_save_sha256': self.target['expected_save_sha256']}
        with self.assertRaisesRegex(ValueError, 'submitted native save intent'):
            seal.complete_save(self.backend, self.sim, value)
        seal.submitted(self.backend, self.sim, receipt, True)
        with self.assertRaisesRegex(ValueError, 'changed completion hash'):
            seal.complete_save(self.backend, self.sim, value)
        self.assertFalse(seal._store(self.path)['records'][self.key]['sealed'])

    def test_new_user_save_hash_refuses_before_native_appearance_writes(self):
        certified = self.certify(); self.reload(); self.slot.write_bytes(b'new external valid save')
        with self.assertRaisesRegex(ValueError, 'certified file'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.assertEqual(self.writes, []); self.tracker._generate_sim_info.assert_not_called()

    def test_new_bank_edit_refuses_before_restoration(self):
        certified = self.certify(); self.reload()
        row = json.loads(self.bank_path.read_text()); row['records'][self.key]['bank']['1']['physique'] = appearance.encode('new accepted edit')
        self.bank_path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, 'newer edits were preserved'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.assertEqual(self.writes, [])

    def test_unsaved_native_edit_after_load_is_not_overwritten_by_old_certified_bank(self):
        certified = self.certify(); self.reload(); self.forms[1].physique = 'new native CAS edit'
        with self.assertRaisesRegex(ValueError, 'newer unsaved edits were preserved'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.assertEqual(self.forms[1].physique, 'new native CAS edit'); self.assertEqual(self.writes, [])

    def test_repeated_native_load_before_reconcile_does_not_refresh_edited_baseline(self):
        certified = self.certify(); self.reload()
        first = seal._LOADED[self.key]
        self.forms[1].physique = 'new unsaved native edit before zone reload'
        seal.note_loaded(self.tracker)
        self.assertIs(seal._LOADED[self.key], first)
        with self.assertRaisesRegex(ValueError, 'newer unsaved edits were preserved'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.assertEqual(self.forms[1].physique, 'new unsaved native edit before zone reload')
        self.assertEqual(self.writes, [])

    def test_repeated_native_load_after_reconcile_never_replays_old_seal_over_unsaved_edit(self):
        certified = self.certify(); self.reload()
        seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.writes.clear()
        self.sim.physique = 'new unsaved active appearance after successful repair'
        seal.note_loaded(self.tracker)
        self.assertNotIn(self.key, seal._LOADED)
        with self.assertRaisesRegex(ValueError, 'already reconciled in this runtime'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.assertEqual(self.sim.physique, 'new unsaved active appearance after successful repair')
        self.assertEqual(self.writes, [])

    def test_script_token_contract_or_tampered_seal_and_pending_cas_refuse(self):
        certified = self.certify(); self.reload()
        original = self.path.read_bytes()
        for kind in ('source', 'contract', 'payload', 'peer'):
            with self.subTest(kind=kind):
                self.path.write_bytes(original)
                if kind == 'source': self.identity['script_sha256'] = 'c' * 64
                elif kind == 'peer': cas_ui._PEERS[SIM] = {'age_seconds': 0}
                else:
                    value = seal._store(self.path)
                    value['records'][self.key]['contract_sha256' if kind == 'contract' else 'file_sha256'] = 'd' * 64
                    self.path.write_text(json.dumps(value))
                with self.assertRaises(ValueError): seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
                self.identity['script_sha256'] = 'b' * 64; cas_ui._PEERS.clear()
        self.assertEqual(self.writes, [])

    def test_no_native_load_receipt_never_authorizes_a_restore(self):
        certified = self.certify(); self.identity['pid'] += 1
        with self.assertRaisesRegex(ValueError, 'load-boundary receipt'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.assertEqual(self.writes, [])

    def test_unsupported_witch_native_tuning_stays_unsupported_without_generation(self):
        certified = self.certify(); self.reload(); self.tracker.OCCULT_DATA.pop(16)
        with self.assertRaisesRegex(ValueError, 'reconstruction is unsupported'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        self.tracker._generate_sim_info.assert_not_called()
        self.assertEqual(self.writes, [])
        self.assertFalse(getattr(self.tracker, '_apex_seal_recovery_required', False))
        self.assertEqual(seal._store(self.path)['records'][self.key]['state'], 'sealed')

    def test_partial_native_restore_failure_retains_originals_and_blocks_replay(self):
        certified = self.certify(); self.reload(); originals = seal._native(self.backend, self.sim)
        restore = self.backend._restore_siminfo_payload; failed = [False]
        def fail_once(owner, fields):
            if owner.id == 1001 and not failed[0]:
                failed[0] = True; raise RuntimeError('native appearance setter failed')
            restore(owner, fields)
        self.backend._restore_siminfo_payload = fail_once
        with self.assertRaises(RuntimeError): seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        row = seal._store(self.path)['records'][self.key]
        self.assertEqual(row['state'], 'recovery-required'); self.assertEqual(row['reconciliation']['native_before'], originals)
        self.assertTrue(row['reconciliation']['original_payloads_restored_verified'])
        self.assertFalse(row['reconciliation']['rollback_verified'])
        self.assertIn('16', row['reconciliation']['rollback_native_after']['stored'])
        self.assertNotIn('16', originals['stored'])
        self.assertEqual(row['reconciliation']['created_forms'], [{'flags': 16, 'id': '2016'}])
        self.assertTrue(self.tracker._apex_seal_recovery_required)
        with self.assertRaises(ValueError): seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})

    def test_native_failure_remains_original_if_recovery_evidence_write_also_fails(self):
        certified = self.certify(); self.reload()
        self.backend._restore_siminfo_payload = Mock(side_effect=RuntimeError('original native appearance failure'))
        write = seal._write
        def fail_recovery(path, data):
            if data['records'][self.key]['state'] == 'recovery-required':
                raise OSError('recovery evidence disk full')
            write(path, data)
        with patch.object(seal, '_write', side_effect=fail_recovery), self.assertRaisesRegex(RuntimeError, 'original native appearance failure'):
            seal.reconcile(self.backend, self.sim, {'seal_sha256': certified['seal_sha256']})
        retained = self.tracker._apex_seal_reconciliation_failure
        self.assertEqual(retained['error'], 'original native appearance failure')
        self.assertEqual(retained['evidence_write_error'], 'recovery evidence disk full')
        self.assertTrue(self.tracker._apex_seal_recovery_required)


class AbandonTests(SealFixture):
    def pending(self):
        pending = {'state': 'captured', 'runtime_pid': self.identity['pid'] - 1, 'lane': '64', 'label': 'Jéwélry',
            'originals': {'64': {'all_future_values': [123, 'retain']}},
            'native_original': {'sim_id': SIM, 'save_guid': GUID, 'data': {'fields': [
                {'name': 'household_id', 'present': True, 'value': HH}]}}}
        self.bank['records'][self.key]['pending'] = pending
        self.bank_path.write_text(json.dumps(self.bank))
        value = {'expected_pending_sha256': hashlib.sha256(json.dumps(pending, sort_keys=True, ensure_ascii=False,
            allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest(), 'prior_pid': self.identity['pid'] - 1,
            'expected_save_sha256': self.target['expected_save_sha256'], 'slot_id': 2, 'save_guid': GUID, 'household_id': HH,
            'failed_return_proof_sha256': 'e' * 64}
        return pending, value

    def test_abandonment_archives_exact_unicode_pending_and_only_clears_metadata(self):
        pending, value = self.pending(); before = copy.deepcopy(self.bank['records'][self.key]); slot = self.slot.read_bytes()
        with patch.object(form_bank, '_old_process_absent', return_value=True) as process:
            result = form_bank.abandon_unsaved(self.backend, self.sim, value)
        process.assert_called_once_with(value['prior_pid']); self.assertTrue(result['abandoned'])
        after = json.loads(self.bank_path.read_text())['records'][self.key]
        self.assertIsNone(after['pending']); archived = after.pop('failed_history')[-1]
        self.assertEqual(archived['pending'], pending); self.assertEqual(archived['pending_sha256'], value['expected_pending_sha256'])
        for key in before:
            if key != 'pending': self.assertEqual(before[key], after[key])
        self.assertEqual(self.slot.read_bytes(), slot); self.assertEqual(self.writes, []); self.assertFalse(self.path.exists())

    def test_live_unknown_prior_pid_or_wrong_pending_hash_never_clear_pending(self):
        pending, value = self.pending(); before = self.bank_path.read_bytes()
        for live in (False, ValueError('ACCESS_DENIED')):
            with self.subTest(live=live), patch.object(form_bank, '_old_process_absent', side_effect=live if isinstance(live, Exception) else None, return_value=live):
                with self.assertRaises(ValueError): form_bank.abandon_unsaved(self.backend, self.sim, value)
            self.assertEqual(self.bank_path.read_bytes(), before)
        with patch.object(form_bank, '_old_process_absent', return_value=True), self.assertRaises(ValueError):
            form_bank.abandon_unsaved(self.backend, self.sim, dict(value, expected_pending_sha256='f' * 64))
        self.assertEqual(self.bank_path.read_bytes(), before); self.assertEqual(self.writes, [])

    def test_auto_save_sentinel_requires_explicit_metadata_only_optin_and_never_certifies_loaded_file(self):
        pending, value = self.pending(); original = self.bank_path.read_bytes(); slot = self.slot.read_bytes()
        native = self.live(); native['save_slot'] = 0xffffffff
        with patch.object(test_driver, 'snapshot', return_value=native), patch.object(form_bank, '_old_process_absent', return_value=True):
            for flag in (None, False, 'true', 1):
                argument = value if flag is None else dict(value, allow_auto_save_slot_metadata_only=flag)
                with self.subTest(flag=flag), self.assertRaises(ValueError):
                    form_bank.abandon_unsaved(self.backend, self.sim, argument)
                self.assertEqual(self.bank_path.read_bytes(), original)
            result = form_bank.abandon_unsaved(self.backend, self.sim, dict(value, allow_auto_save_slot_metadata_only=True))
        self.assertTrue(result['abandoned']); self.assertTrue(result['metadata_archive_only'])
        self.assertEqual(result['actual_native_slot_id'], 0xffffffff)
        self.assertFalse(result['disk_slot_verified']); self.assertFalse(result['loaded_file_verified'])
        self.assertFalse(result['save_reload_verified']); self.assertFalse(result['appearance_mutated'])
        self.assertFalse(result['save_written']); self.assertEqual(self.writes, [])
        self.assertEqual(self.slot.read_bytes(), slot)
        archived = json.loads(self.bank_path.read_text())['records'][self.key]['failed_history'][-1]
        self.assertEqual(archived['pending'], pending); self.assertFalse(archived['disk_slot_verified'])

    def test_explicit_metadata_only_optin_does_not_allow_other_native_slot_or_scratch_zero(self):
        pending, value = self.pending(); original = self.bank_path.read_bytes()
        for slot in (0, 3):
            native = self.live(); native['save_slot'] = slot
            with self.subTest(slot=slot), patch.object(test_driver, 'snapshot', return_value=native), \
                    patch.object(form_bank, '_old_process_absent', return_value=True), self.assertRaises(ValueError):
                form_bank.abandon_unsaved(self.backend, self.sim, dict(value, allow_auto_save_slot_metadata_only=True))
            self.assertEqual(self.bank_path.read_bytes(), original); self.assertEqual(self.writes, [])


class PriorProcessTests(unittest.TestCase):
    def native(self, opened=0x12345678000000aa, error=0, exit_code=259, query=1, close=1):
        calls = []; bindings = []
        class Call:
            def __init__(self, binding):
                self.name = binding[0]
                bindings.append((self.name, self._restype_, self._argtypes_))
            def __call__(self, *args):
                calls.append((self.name, args))
                if self.name == 'OpenProcess': value = opened
                elif self.name == 'GetLastError': value = error
                elif self.name == 'GetExitCodeProcess':
                    ctypes.cast(args[1], ctypes.POINTER(ctypes.c_uint32)).contents.value = exit_code
                    value = query
                elif self.name == 'CloseHandle': value = close
                else: raise AssertionError('Unexpected Win32 function: ' + self.name)
                return self._restype_(value)
        native = Obj(_SimpleCData=ctypes._SimpleCData, CFuncPtr=Call, FUNCFLAG_STDCALL=0,
            POINTER=ctypes.POINTER, byref=ctypes.byref, LoadLibrary=Mock(return_value=222), FreeLibrary=Mock())
        return native, calls, bindings

    def check(self, **config):
        native, calls, bindings = self.native(**config)
        with patch.dict(sys.modules, {'paths': Obj(DLL_PATH='fixture/Python/DLLs')}), \
                patch('apex_core.overlay_loader._game_ctypes', return_value=native):
            result = form_bank._old_process_absent(12345)
        return result, native, calls, bindings

    def test_exact_typed_64_bit_handle_queries_live_and_exited_pid_and_always_closes(self):
        for code, expected in ((259, False), (0, True)):
            with self.subTest(code=code):
                result, native, calls, bindings = self.check(exit_code=code)
                self.assertIs(result, expected)
                self.assertEqual([name for name, args in calls], ['OpenProcess', 'GetExitCodeProcess', 'CloseHandle'])
                self.assertEqual(calls[0][1], (0x1000, 0, 12345))
                self.assertEqual(calls[1][1][0], 0x12345678000000aa)
                self.assertEqual(calls[2][1], (0x12345678000000aa,))
                self.assertEqual(ctypes.sizeof(bindings[0][1]), ctypes.sizeof(ctypes.c_void_p))
                self.assertEqual(ctypes.sizeof(bindings[0][2][2]), 4)
                native.FreeLibrary.assert_called_once_with(222)

    def test_only_invalid_parameter_means_absent_denied_and_failed_query_refuse(self):
        result, native, calls, _bindings = self.check(opened=0, error=87)
        self.assertTrue(result); self.assertEqual([name for name, args in calls], ['OpenProcess', 'GetLastError'])
        native.FreeLibrary.assert_called_once_with(222)
        for config, message in (({'opened': 0, 'error': 5}, 'Win32 error 5'),
                ({'query': 0}, 'exit observation failed'), ({'close': 0}, 'handle closure failed')):
            with self.subTest(config=config):
                native, calls, _bindings = self.native(**config)
                with patch.dict(sys.modules, {'paths': Obj(DLL_PATH='fixture/Python/DLLs')}), \
                        patch('apex_core.overlay_loader._game_ctypes', return_value=native), \
                        self.assertRaisesRegex(ValueError, message):
                    form_bank._old_process_absent(12345)
                native.FreeLibrary.assert_called_once_with(222)
                self.assertEqual('CloseHandle' in [name for name, args in calls], config.get('opened') != 0)

    def test_invalid_self_or_bool_pid_is_rejected_before_any_native_binding(self):
        with patch('apex_core.overlay_loader._game_ctypes') as native:
            for pid in (True, False, 0, -1, 0x100000000, '12345', os.getpid()):
                with self.subTest(pid=pid), self.assertRaises(ValueError): form_bank._old_process_absent(pid)
            native.assert_not_called()


if __name__ == '__main__':
    unittest.main()
