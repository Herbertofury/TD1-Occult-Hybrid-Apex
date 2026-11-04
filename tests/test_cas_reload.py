import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_reload
from source_manifest import sha256
from apex_core import form_appearance

SIM, HOUSEHOLD, GUID = '285159751289798669', '285159751289798668', '1841692672'
TOKEN, OLD_SCRIPT, NEW_SCRIPT = 'c' * 32, 'a' * 64, 'b' * 64


def fields(flags):
    return {'skin_tone': form_appearance.encode(flags), 'physique': form_appearance.encode('native-' + str(flags)),
            'facial_attributes': form_appearance.encode(b'complete face bytes\x00\xff'),
            'genetic_data': form_appearance.encode(b'complete genetics'),
            'custom_texture': {'kind': 'resourcekey', 'value': [3, 8, 0]},
            '__outfits__': form_appearance.encode(('protobuf', b'\x0a\x02\x10\x00'))}


def appearance(value):
    return dict(cas_reload.appearance_fingerprint(value), typed_payload=value)


def native_record():
    raw = b'complete existing native save buffer\x00\xff'
    return {'schema': 1, 'sim_id': SIM, 'household_id': HOUSEHOLD, 'save_guid': GUID,
            'source': 'native-existing-save-buffer', 'native_sha256': hashlib.sha256(raw).hexdigest(),
            'native_base64': base64.b64encode(raw).decode('ascii'), 'native_bytes': len(raw),
            'field_schemas': {'NativeSim': [{'name': 'future_field', 'number': 900}]},
            'data': {'message_type': 'NativeSim', 'fields': [
                {'name': 'sim_id', 'present': True, 'value': SIM},
                {'name': 'household_id', 'present': True, 'value': HOUSEHOLD},
                {'name': 'future_field', 'present': True, 'value': {'raw': 'preserve'}}]},
            'unknown_fields_retained_in_native_bytes': True}


class ReloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.profile = self.root / 'Electronic Arts/The Sims 4'
        self.original = self.root / 'Electronic Arts/The Sims 4 DO NOT FUCKING TOUCH!!!'
        (self.profile / 'saves').mkdir(parents=True); (self.original / 'saves').mkdir(parents=True)
        (self.original / 'saves/Slot_00000002.save').write_bytes(b'protected owner save')
        (self.original / 'owner-mod.package').write_bytes(b'protected owner mod')
        self.slot = self.profile / 'saves/Slot_00000002.save'; self.slot.write_bytes(b'native saved Slot02 bytes')
        (self.profile / 'saves/Slot_ffffffff.save').write_bytes(b'untouched CAS scratch save')
        self.state, self.output, self.saved = self.root / 'state.json', self.root / 'proof.json', self.root / 'save-exit.json'
        self.state.write_text('journal fixture', encoding='utf-8')
        self.identity = {'pid': 222, 'profile': str(self.profile), 'test_token': TOKEN, 'script_sha256': NEW_SCRIPT}
        self.journal = {'token': TOKEN, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': NEW_SCRIPT}]}
        self.saved_row = {'sha256': sha256(self.slot), 'bytes': self.slot.stat().st_size, 'mtime_ns': 2}
        self.closed = {'schema': 1, 'ok': True, 'operation': 'normal-save-and-exit', 'outcome': 'normal-save-and-exit',
            'normal_exit_verified': True, 'game_exit_verified': True, 'final_process_alive': False,
            'save_and_exit_input_accepted': True, 'save_completed_file_verified': True,
            'identity': {'pid': 111, 'profile': str(self.profile), 'test_token': TOKEN, 'script_sha256': OLD_SCRIPT},
            'inputs': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': OLD_SCRIPT}],
            'before_saves': {'Slot_00000002.save': {'sha256': 'd' * 64, 'bytes': 1, 'mtime_ns': 1}},
            'after_saves': {'Slot_00000002.save': self.saved_row}, 'rewritten_normal_slots': {'Slot_00000002.save': self.saved_row},
            'crash': {'preserved': False, 'outcome': 'unchanged'}}
        self.bank_path = self.profile / 'TD1_OccultHybridApexData/form_bank.json'; self.bank_path.parent.mkdir()
        self.bank = {'schema': 1, 'records': {GUID + ':' + SIM: {'runtime_pid': 111, 'pending': None,
            'switch_pending': None, 'bank': {str(flags): fields(flags) for flags in cas_reload.FORMS},
            'history': [{'state': 'completed', 'lane': '1', 'membership': list(cas_reload.MEMBERS), 'native_after': native_record()}]}}}
        self.clock, self.ticks, self.speed, self.sequence = 0.0, 1000, 0, 0
        self.calls, self.commands, self.forms_read = [], [], []
        self.handler = None; self.live_change = {}; self.membership_missing = None
        self.native_change = None; self.active_change = None; self.missing_form = None; self.no_ticks = False
        self.alive = True
        self.save_proof_path = None

    def prepare_certified_save(self, reconciled=False):
        from apex_core.form_bank_seal import CONTRACT
        self.save_proof_path = self.root / 'controlled-save.json'
        self.seal_path = self.bank_path.with_name('form_bank_seals.json')
        prior = dict(self.identity, pid=111)
        target = {'slot_id': 2, 'slot_name': 'Disposable test', 'expected_save_sha256': 'd' * 64,
                  'sim_id': SIM, 'household_id': HOUSEHOLD, 'save_guid': GUID}
        selected = self.bank['records'][GUID + ':' + SIM]
        row = {'intent_id': 'e' * 32, 'identity': prior, 'contract_sha256': CONTRACT, 'target': target,
               'bank_record_sha256': hashlib.sha256(cas_reload.encoded(selected)).hexdigest(),
               'appearances': selected['bank'], 'file_sha256': self.saved_row['sha256'],
               'state': 'reconciled' if reconciled else 'sealed', 'sealed': True}
        names = ('intent_id', 'identity', 'contract_sha256', 'target', 'bank_record_sha256', 'appearances', 'file_sha256')
        row['seal_sha256'] = hashlib.sha256(cas_reload.encoded({name: row[name] for name in names})).hexdigest()
        if reconciled:
            row['reconciliation'] = {'ok': True, 'pid': self.identity['pid']}
        self.seals = {'schema': 1, 'records': {GUID + ':' + SIM: row}}
        receipt = dict({name: row[name] for name in ('intent_id', 'seal_sha256', 'file_sha256', 'bank_record_sha256')},
                       ok=True, state='sealed', save_reload_verified=False)
        crash = {'before': {'state': 'absent'}, 'after': {'state': 'absent'}, 'preserved': False, 'outcome': 'unchanged'}
        self.save_proof = {'schema': 1, 'operation': 'explicit-existing-disposable-save',
            'outcome': 'existing-target-save-file-observed', 'ok': True, 'identity': prior,
            'inputs': copy.deepcopy(self.journal['artifacts']), 'target': target,
            'save_command_attempted': True, 'save_submitted': True, 'save_completed_file_verified': True,
            'native_target_slot_verified': True, 'form_bank_seal_verified': True, 'crash_clear_verified': True,
            'finalized': True, 'process_exit_verified': False, 'save_request_id': 'f' * 32,
            'target_before': {'path': str(self.slot), 'sha256': 'd' * 64, 'bytes': 1, 'mtime_ns': 1},
            'target_after': dict(self.saved_row, path=str(self.slot)), 'native_after': self.live(),
            'form_bank_seal': receipt, 'crash_before': {'state': 'absent'}, 'crash': copy.deepcopy(crash)}
        auto = self.profile / 'saves/Slot_ffffffff.save'
        inventory = {'Slot_00000002.save': self.saved_row,
                     auto.name: {'sha256': sha256(auto), 'bytes': auto.stat().st_size, 'mtime_ns': 3}}
        self.closed = {'schema': 1, 'operation': 'normal-exit-without-saving', 'outcome': 'normal-exit-without-saving',
            'ok': True, 'identity': prior, 'inputs': copy.deepcopy(self.journal['artifacts']),
            'normal_exit_verified': True, 'game_exit_verified': True, 'final_process_alive': False,
            'exit_without_save_input_accepted': True, 'save_files_unchanged_verified': True,
            'save_requested': False, 'save_and_exit_input_accepted': False, 'save_completed_file_verified': False,
            'requested_sim_id': SIM, 'requested_household_id': HOUSEHOLD, 'requested_save_guid': GUID,
            'before_all_saves': copy.deepcopy(inventory), 'after_all_saves': copy.deepcopy(inventory),
            'unsaved_exit_native_before': self.live(), 'before_crash': {'state': 'absent'}, 'crash': crash}

    def write_inputs(self):
        self.saved.write_text(json.dumps(self.closed), encoding='utf-8')
        self.bank_path.write_text(json.dumps(self.bank), encoding='utf-8')
        if self.save_proof_path is not None:
            self.save_proof_path.write_text(json.dumps(self.save_proof), encoding='utf-8')
            self.seal_path.write_text(json.dumps(self.seals), encoding='utf-8')

    def live(self):
        result = {'ok': True, 'save_slot': 2, 'save_guid': GUID, 'household_id': HOUSEHOLD,
            'client_id': '99', 'zone_id': '98', 'zone_running': True, 'in_build_buy': False,
            'sim_now_ticks': str(self.ticks), 'sim_time_source': cas_reload.cas_return.SIM_TIME_SOURCE,
            'clock_speed': self.speed,
            'runtime_queries': {name: 'returned-value' for name in ('client_id', 'zone_running', 'sim_now_ticks')},
            'sim': {'id': SIM, 'instanced': True, 'occult_flags': 127, 'current_form': 1,
                    'progressing_gameplay_field': self.ticks},
            'persistence': {'persistence_verified_before_save': True,
                'checks': {name: True for name in cas_reload.PERSISTENCE_CHECKS},
                'household_sim_ids': [SIM], 'persisted_household_sim_ids': [SIM], 'errors': []}}
        result.update(self.live_change)
        return result

    def transport(self, path, query=None, timeout=12):
        self.assertGreater(timeout, 0)
        if path == '/api/bridge':
            return copy.deepcopy(self.identity)
        self.assertEqual(path, '/api/command')
        persisted = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(persisted['owner_requests'][-1]['request_id'], query['request_id'])
        self.commands.append(copy.deepcopy(query))
        action = query['action']; argument = json.loads(query['value'])['value']
        if self.handler:
            result = self.handler(action, argument)
            if result is not None:
                return result
        if action == 'cas_ui_diagnostics':
            return {'ok': True, 'native_initializer_observed': False, 'native_peers': [], 'requests': [],
                'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021, 'startup_error': None,
                                     'native_connection_verified': False}}
        if action == 'test_snapshot':
            if self.speed == 1 and not self.no_ticks:
                self.ticks += 1000
            return self.live()
        if action in ('test_play', 'test_pause'):
            self.speed = 1 if action == 'test_play' else 0
            return self.live()
        self.assertEqual(action, 'test_form_snapshot')
        flags = argument['form_flags']; self.forms_read.append(flags)
        stored = fields(flags)
        if self.native_change == flags:
            stored['skin_tone'] = form_appearance.encode(900)
        live_fields = fields(flags)
        if self.active_change == flags:
            live_fields['skin_tone'] = form_appearance.encode(999)
        result = {'ok': True, 'sim_id': SIM, 'form_flags': flags, 'native_wrapper_id': str(5000 + flags),
            'source': 'native-form-map', 'stored_form_present': True, 'current_form_flags': 1,
            'appearance': appearance(stored), 'active_live_appearance': appearance(live_fields) if flags == 1 else None,
            'native_record': native_record() if argument['include_native_record'] else None,
            'native_membership': [{'flags': kind, 'occult': name, 'query': 'returned-value',
                                  'has_occult': kind != self.membership_missing} for kind, name in cas_reload.MEMBERS.items()],
            'live_context': self.live(), 'bank_read': False, 'form_created': False, 'appearance_mutated': False,
            'unknown_future_field': {'captured': True, 'gameplay_ticks': self.ticks}}
        if self.missing_form == flags:
            result.update(ok=False, outcome='missing-native-form', native_wrapper_id=None, appearance=None,
                          stored_form_present=False)
        return result

    def request(self, _state, action, *, sim_id=None, value=None, transport=None, **kwargs):
        self.calls.append(action)
        self.assertEqual(sim_id, SIM)
        self.assertEqual(json.loads(value)['test_token'], TOKEN)
        transport('/api/bridge')
        self.sequence += 1
        rid = '{:032x}'.format(self.sequence)
        result = transport('/api/command', {'action': action, 'sim_id': sim_id, 'value': value, 'request_id': rid})
        return dict(result, request_id=rid, request_state=result.get('request_state', 'completed'))

    def run_observer(self, seconds=60):
        self.write_inputs()
        original = {str(path.relative_to(self.original)): path.read_bytes() for path in self.original.rglob('*') if path.is_file()}
        slot, scratch, bank = self.slot.read_bytes(), (self.profile / 'saves/Slot_ffffffff.save').read_bytes(), self.bank_path.read_bytes()
        with patch.object(cas_reload.reusable_profile, 'load', return_value=(self.state, self.journal, self.profile, self.original)):
            result = cas_reload.observe(self.state, self.output, self.identity, self.request, self.saved, sha256(self.saved),
                SIM, HOUSEHOLD, GUID, seconds=seconds, settle_ticks=750, transport=self.transport,
                alive=lambda _pid: self.alive, monotonic=lambda: self.clock,
                pause=lambda value: setattr(self, 'clock', self.clock + value),
                save_proof=self.save_proof_path,
                expected_save_proof_sha256=sha256(self.save_proof_path) if self.save_proof_path is not None else None)
        self.assertEqual(original, {str(path.relative_to(self.original)): path.read_bytes() for path in self.original.rglob('*') if path.is_file()})
        self.assertEqual(self.slot.read_bytes(), slot)
        self.assertEqual((self.profile / 'saves/Slot_ffffffff.save').read_bytes(), scratch)
        self.assertEqual(self.bank_path.read_bytes(), bank)
        return result, json.loads(self.output.read_text(encoding='utf-8'))

    def assert_certified_refused(self, expected_save_sha=None):
        self.write_inputs()
        with patch.object(cas_reload.reusable_profile, 'load', return_value=(self.state, self.journal, self.profile, self.original)), self.assertRaises(ValueError):
            cas_reload.observe(self.state, self.output, self.identity, self.request, self.saved, sha256(self.saved),
                SIM, HOUSEHOLD, GUID, transport=self.transport, save_proof=self.save_proof_path,
                expected_save_proof_sha256=expected_save_sha or sha256(self.save_proof_path))
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())

    def test_certified_controlled_save_and_same_pid_unsaved_exit_bind_actual_sidecar_and_verify_native(self):
        self.prepare_certified_save()
        result, proof = self.run_observer()
        self.assertTrue(result['save_reload_verified'])
        self.assertEqual(proof['closed_session']['reference_kind'], 'controlled-sealed-save-and-normal-unsaved-exit')
        self.assertEqual(proof['closed_session']['controlled_save']['sha256'], sha256(self.save_proof_path))
        self.assertEqual(proof['closed_session']['sidecar']['sha256'], sha256(self.seal_path))
        self.assertTrue(proof['certified_reference_unchanged_verified'])
        self.assertEqual(self.calls.count('test_play'), 1)
        self.assertEqual(self.calls.count('test_pause'), 1)

    def test_certified_current_pid_reconciled_receipt_preserves_bank_prior_pid(self):
        self.prepare_certified_save(reconciled=True)
        result, proof = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertEqual(proof['closed_session']['sidecar']['state'], 'reconciled')
        self.assertEqual(proof['bank']['runtime_pid'], 111)

    def test_certified_mismatched_source_pid_token_or_proof_hash_refuse_before_requests(self):
        for field, value in (('pid', 333), ('pid', True), ('test_token', '7' * 32), ('script_sha256', OLD_SCRIPT), ('profile', str(self.original))):
            with self.subTest(field=field, value=value):
                self.prepare_certified_save()
                self.save_proof['identity'] = dict(self.save_proof['identity'], **{field: value})
                self.assert_certified_refused()
        self.prepare_certified_save()
        self.assert_certified_refused(expected_save_sha='8' * 64)
        self.prepare_certified_save()
        self.closed['identity'] = dict(self.closed['identity'], script_sha256=OLD_SCRIPT)
        self.save_proof['identity'] = dict(self.save_proof['identity'], script_sha256=OLD_SCRIPT)
        for value in (self.closed, self.save_proof):
            value['inputs'][0]['sha256'] = OLD_SCRIPT
        self.assert_certified_refused()

    def test_certified_exact_sim_household_guid_and_normal_slot_are_required_in_both_proofs(self):
        for source, field, value in (('save', 'sim_id', '99'), ('save', 'household_id', '99'), ('save', 'save_guid', '99'),
                ('save', 'slot_id', 0xffffffff), ('exit', 'requested_sim_id', '99'),
                ('exit', 'requested_household_id', '99'), ('exit', 'requested_save_guid', '99')):
            with self.subTest(source=source, field=field):
                self.prepare_certified_save()
                (self.save_proof['target'] if source == 'save' else self.closed)[field] = value
                self.assert_certified_refused()

    def test_certified_changed_target_backup_hash_native_slot_or_save_again_exit_refuse(self):
        for change in ('file-hash', 'file-path', 'backup', 'native-slot', 'save-input', 'alive', 'crash', 'crash-label-only'):
            with self.subTest(change=change):
                self.prepare_certified_save()
                if change == 'file-hash':
                    self.save_proof['target_after']['sha256'] = '7' * 64
                elif change == 'file-path':
                    self.save_proof['target_after']['path'] = str(self.original / 'saves/Slot_00000002.save')
                elif change == 'backup':
                    self.closed['after_all_saves']['Slot_ffffffff.save']['sha256'] = '7' * 64
                elif change == 'native-slot':
                    self.save_proof['native_after']['save_slot'] = 0xffffffff
                elif change == 'save-input':
                    self.closed['save_and_exit_input_accepted'] = True
                elif change == 'alive':
                    self.closed['final_process_alive'] = True
                elif change == 'crash':
                    self.closed['crash']['preserved'] = True
                else:
                    self.closed['crash']['after'] = {'state': 'read', 'sha256': '7' * 64}
                self.assert_certified_refused()

    def test_certified_sidecar_tamper_wrong_target_bank_or_reload_pid_refuse(self):
        for change in ('receipt', 'bank', 'seal', 'household', 'guid', 'source', 'reconciled-pid', 'rebase-incomplete'):
            with self.subTest(change=change):
                self.prepare_certified_save(reconciled=change == 'reconciled-pid')
                row = self.seals['records'][GUID + ':' + SIM]
                if change == 'receipt':
                    self.save_proof['form_bank_seal']['seal_sha256'] = '7' * 64
                elif change == 'bank':
                    self.bank['records'][GUID + ':' + SIM]['bank']['4']['skin_tone'] = form_appearance.encode(999)
                elif change == 'seal':
                    row['appearances']['2']['skin_tone'] = form_appearance.encode(998)
                elif change in ('household', 'guid'):
                    row['target'] = dict(row['target'], **{'household_id' if change == 'household' else 'save_guid': '99'})
                elif change == 'source':
                    row['identity'] = dict(row['identity'], script_sha256=OLD_SCRIPT)
                elif change == 'reconciled-pid':
                    row['reconciliation']['pid'] = 333
                else:
                    self.bank['records'][GUID + ':' + SIM]['native_rebase_requires_cas_completion'] = True
                self.assert_certified_refused()
                # prepare_certified_save intentionally seals the existing bank;
                # restore that fixture between independently corrupted cases.
                self.bank['records'][GUID + ':' + SIM]['bank'] = {str(flags): fields(flags) for flags in cas_reload.FORMS}
                self.bank['records'][GUID + ':' + SIM].pop('native_rebase_requires_cas_completion', None)

    def test_certified_sidecar_change_during_native_reads_cannot_claim_persistence(self):
        self.prepare_certified_save()
        def handler(action, _argument):
            if action == 'test_play':
                self.seal_path.write_text(json.dumps({'schema': 1, 'records': {}}), encoding='utf-8')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertTrue(proof['initial_appearances_verified'])
        self.assertTrue(proof['settled_appearances_verified'])
        self.assertFalse(proof['certified_reference_unchanged_verified'])

    def test_certified_proof_pair_and_external_locations_are_required_before_requests(self):
        self.prepare_certified_save()
        self.write_inputs()
        with patch.object(cas_reload.reusable_profile, 'load', return_value=(self.state, self.journal, self.profile, self.original)):
            for source, checksum in ((self.save_proof_path, None), (None, sha256(self.save_proof_path)),
                    (self.original / 'owner-mod.package', sha256(self.save_proof_path)),
                    (self.profile / 'saves/Slot_00000002.save', sha256(self.save_proof_path))):
                with self.subTest(source=source, checksum=checksum), self.assertRaises(ValueError):
                    cas_reload.observe(self.state, self.output, self.identity, self.request, self.saved, sha256(self.saved),
                        SIM, HOUSEHOLD, GUID, transport=self.transport, save_proof=source, expected_save_proof_sha256=checksum)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())
        self.assertEqual((self.original / 'owner-mod.package').read_bytes(), b'protected owner mod')

    def test_restart_native_all_lanes_and_six_memberships_verified_before_and_after_progression(self):
        result, proof = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertTrue(result['save_reload_verified'])
        self.assertTrue(result['final_paused'])
        self.assertEqual(self.forms_read, list(cas_reload.FORMS) * 2)
        self.assertEqual(self.calls.count('test_play'), 1)
        self.assertEqual(self.calls.count('test_pause'), 1)
        self.assertGreaterEqual(int(proof['native_progress']['to_ticks']) - int(proof['native_progress']['from_ticks']), 750)
        self.assertGreaterEqual(proof['native_progress']['elapsed_seconds'], .5)
        self.assertEqual(proof['baseline_live']['sim_time_source'], cas_reload.cas_return.SIM_TIME_SOURCE)
        self.assertEqual(proof['native_progress']['sim_time_source'], cas_reload.cas_return.SIM_TIME_SOURCE)
        self.assertEqual(proof['settled_paused_live']['sim_time_source'], cas_reload.cas_return.SIM_TIME_SOURCE)
        self.assertFalse(set(self.calls) - {'cas_ui_diagnostics', 'test_snapshot', 'test_form_snapshot', 'test_play', 'test_pause'})
        pause_index = self.calls.index('test_pause')
        self.assertEqual(self.calls[:pause_index].count('test_form_snapshot'), len(cas_reload.FORMS))
        self.assertEqual(self.calls[pause_index:].count('test_form_snapshot'), len(cas_reload.FORMS))
        self.assertTrue(proof['save_file_unchanged_verified'])
        self.assertTrue(proof['bank_unchanged_verified'])
        for phase in proof['phases']:
            self.assertTrue(phase['verified'])
            self.assertTrue(phase['active_live_comparison_observed'])
            self.assertEqual(phase['paused_active_form_flags'], 1)
            for row in phase['forms']:
                raw = Path(row['raw']['path']); self.assertEqual(sha256(raw), row['raw']['sha256'])
                retained = json.loads(raw.read_text(encoding='utf-8'))
                self.assertEqual(retained['unknown_future_field']['captured'], True)
                self.assertEqual(retained['appearance']['typed_payload'], fields(row['form_flags']))
                if row['form_flags'] == 1:
                    self.assertIn('future_field', json.dumps(retained['native_record']['field_schemas']))

    def test_missing_simulation_origin_refuses_before_native_reads_or_unpause(self):
        def handler(action, _argument):
            if action == 'test_snapshot':
                live = self.live(); live.pop('sim_time_source')
                live['sim_now_ticks'] = str(1 << 60)
                return live
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertFalse(result['clock_progress_verified'])
        self.assertIn('simulation timeline origin', proof['error'])
        self.assertEqual(self.forms_read, [])
        self.assertEqual(self.calls, ['cas_ui_diagnostics', 'test_snapshot'])
        self.assertFalse(proof['play_attempted'])
        self.assertFalse(proof['pause_attempted'])

    def test_game_clock_origin_cannot_certify_reload_even_with_large_positive_ticks(self):
        self.live_change = {'sim_time_source': 'services.game_clock_service().now',
                            'sim_now_ticks': str(1 << 60)}
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertFalse(result['clock_progress_verified'])
        self.assertIn('simulation timeline origin', proof['error'])
        self.assertEqual(self.forms_read, [])
        self.assertNotIn('test_play', self.calls)
        self.assertNotIn('test_pause', self.calls)

    def test_advancing_wrong_origin_after_play_cannot_certify_settled_appearance(self):
        def handler(action, _argument):
            if action == 'test_snapshot' and self.speed == 1:
                self.ticks += 1000
                live = self.live()
                live['sim_time_source'] = 'services.game_clock_service().now'
                return live
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertTrue(result['initial_appearances_verified'])
        self.assertFalse(result['settled_appearances_verified'])
        self.assertFalse(result['clock_progress_verified'])
        self.assertNotIn('native_progress', proof)
        self.assertIn('simulation timeline origin', proof['error'])
        self.assertEqual(self.calls.count('test_play'), 1)
        self.assertNotIn('test_pause', self.calls)
        self.assertEqual(self.forms_read, list(cas_reload.FORMS))
        self.assertEqual(proof['baseline_live']['sim_time_source'], cas_reload.cas_return.SIM_TIME_SOURCE)
        self.assertEqual(proof['steps'][-1]['action'], 'test_snapshot')
        self.assertEqual(proof['steps'][-1]['state'], 'observed')
        self.assertEqual(proof['steps'][-1]['owner_requests'][-1]['request_id'], self.commands[-1]['request_id'])

    def test_stored_native_mismatch_is_not_hidden_by_matching_bank_or_live_owner(self):
        self.native_change = 1
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(result['outcome'], 'native-appearance-mismatch')
        self.assertEqual(proof['phases'][0]['forms'][0]['appearance']['changed_fields'], ['skin_tone'])
        self.assertTrue(proof['phases'][0]['forms'][0]['active_live_appearance']['verified'])
        self.assertEqual(len(self.forms_read), 14)
        self.assertTrue(result['final_paused'])

    def test_active_live_mismatch_is_not_hidden_by_matching_stored_wrapper(self):
        self.active_change = 1
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        row = proof['phases'][0]['forms'][0]
        self.assertTrue(row['appearance']['verified'])
        self.assertFalse(row['active_live_appearance']['verified'])

    def test_changed_paused_form_cannot_skip_both_active_live_comparisons(self):
        def handler(action, argument):
            if action != 'test_form_snapshot' or self.calls.count('test_pause') == 0:
                return None
            self.handler = None
            result = self.transport('/api/command', self.commands[-1])
            self.handler = handler
            current = 32 if argument['form_flags'] == 1 else 1
            result['current_form_flags'] = current
            result['live_context']['sim']['current_form'] = current
            result['active_live_appearance'] = None
            return result
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertFalse(result['settled_appearances_verified'])
        self.assertIn('Paused active native form changed', proof['error'])
        self.assertFalse(proof['phases'][1]['active_live_comparison_observed'])
        self.assertEqual(self.calls.count('test_pause'), 1)
        self.assertTrue(result['final_paused'])

    def test_stable_paused_active_lane_requires_complete_live_appearance(self):
        def handler(action, argument):
            if action != 'test_form_snapshot' or self.calls.count('test_pause') == 0 or argument['form_flags'] != 1:
                return None
            self.handler = None
            result = self.transport('/api/command', self.commands[-1])
            self.handler = handler
            result['active_live_appearance'] = None
            return result
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertFalse(proof['phases'][1]['forms'][0]['active_live_appearance']['verified'])
        self.assertEqual(self.calls.count('test_pause'), 1)

    def test_bitmask_127_cannot_infer_missing_native_sixth_membership(self):
        self.membership_missing = 16
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(proof['baseline_live']['sim']['occult_flags'], 127)
        witch = next(row for row in proof['phases'][1]['forms'][0]['membership'] if row['flags'] == 16)
        self.assertFalse(witch['verified'])
        self.assertFalse(proof['phases'][1]['forms'][0]['six_memberships_verified'])

    def test_missing_native_form_is_explicit_without_bank_fallback_creation_or_skipped_lanes(self):
        self.missing_form = 16
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.forms_read), 14)
        for phase in proof['phases']:
            row = next(row for row in phase['forms'] if row['form_flags'] == 16)
            self.assertEqual(row['reason'], 'missing-native-form')
        self.assertFalse(any(action in ('cas_session_begin', 'cas_session_finish', 'switch', 'human') for action in self.calls))

    def test_live_only_owner_cannot_claim_native_stored_form_persistence(self):
        def handler(action, argument):
            if action == 'test_form_snapshot' and argument['form_flags'] == 4:
                self.native_change = None
                self.handler = None
                result = self.transport('/api/command', self.commands[-1])
                self.handler = handler
                result.update(source='current-live-only', stored_form_present=False)
                return result
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        row = next(row for row in proof['phases'][0]['forms'] if row['form_flags'] == 4)
        self.assertEqual(row['reason'], 'stored-native-owner-unverified')

    def test_native_context_changes_refuse_before_play_and_keep_original_and_saves_read_only(self):
        self.live_change['save_guid'] = '99'
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertIn('context differs', proof['error'])
        self.assertNotIn('test_play', self.calls)
        self.assertNotIn('test_pause', self.calls)

    def test_pause_only_once_after_missing_tick_progress_without_clock_replay(self):
        self.no_ticks = True
        result, proof = self.run_observer(seconds=2)
        self.assertFalse(result['ok'])
        self.assertFalse(result['clock_progress_verified'])
        self.assertTrue(result['final_paused'])
        self.assertEqual(self.calls.count('test_play'), 1)
        self.assertEqual(self.calls.count('test_pause'), 1)
        self.assertIn('deadline', proof['error'])

    def test_lost_play_completion_retains_owner_uuid_before_transport_and_pauses_once(self):
        def handler(action, _argument):
            if action == 'test_play':
                self.speed = 1
                raise TimeoutError('play response lost')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['final_paused'])
        self.assertEqual(self.calls.count('test_play'), 1)
        self.assertEqual(self.calls.count('test_pause'), 1)
        row = next(row for row in proof['steps'] if row['action'] == 'test_play')
        self.assertEqual(row['state'], 'unresolved')
        self.assertEqual(len(row['owner_requests']), 1)
        self.assertIn(row['owner_requests'][0], proof['owner_requests'])

    def test_failed_native_persistence_is_not_a_reloaded_sim_proof(self):
        original = self.live
        def changed_live():
            result = original()
            result['persistence']['checks']['sim_proto_household_identity'] = False
            return result
        self.live = changed_live
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertIn('persistence checks', proof['error'])
        self.assertNotIn('test_play', self.calls)

    def test_changed_crash_is_retained_and_cannot_pass_even_when_all_appearances_match(self):
        raw = b'<report><type>crash</type><categoryid>native-crash</categoryid></report>'
        def handler(action, _argument):
            if action == 'test_play':
                (self.profile / 'lastCrash.txt').write_bytes(raw)
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'crash')
        self.assertTrue(result['initial_appearances_verified'])
        self.assertTrue(result['settled_appearances_verified'])
        self.assertTrue(result['final_paused'])
        self.assertEqual(Path(proof['crash']['path']).read_bytes(), raw)
        self.assertEqual(sha256(Path(proof['crash']['path'])), proof['crash']['after']['sha256'])
        self.assertFalse(proof['crash_clear_verified'])

    def test_rejected_changed_crash_cannot_be_reported_as_a_success(self):
        def handler(action, _argument):
            if action == 'test_play':
                (self.profile / 'lastCrash.txt').write_bytes(b'<!DOCTYPE report><report/>')
        self.handler = handler
        result, proof = self.run_observer()
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(result['outcome'], 'changed-crash-report-refused')
        self.assertEqual(proof['crash']['outcome'], 'refused')
        self.assertFalse(proof['crash']['preserved'])
        self.assertTrue(result['final_paused'])

    def test_unreadable_crash_baseline_refuses_before_any_game_request(self):
        self.write_inputs()
        with patch.object(cas_reload.reusable_profile, 'load', return_value=(self.state, self.journal, self.profile, self.original)), \
                patch.object(cas_reload.cas_transition, 'read_crash', return_value=({'state': 'unreadable'}, None)), \
                self.assertRaisesRegex(ValueError, 'crash baseline'):
            cas_reload.observe(self.state, self.output, self.identity, self.request, self.saved, sha256(self.saved),
                               SIM, HOUSEHOLD, GUID, transport=self.transport)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())

    def test_invalid_closed_proof_hash_same_pid_wrong_bank_key_or_incomplete_history_refuse_before_commands(self):
        for change in ('hash', 'same-pid', 'history', 'bank-pid', 'household', 'untyped-pending', 'untyped-save-size'):
            with self.subTest(change=change):
                self.write_inputs(); expected = sha256(self.saved)
                identity = copy.deepcopy(self.identity); bank = copy.deepcopy(self.bank)
                if change == 'hash':
                    expected = 'e' * 64
                elif change == 'same-pid':
                    identity['pid'] = 111
                elif change == 'history':
                    bank['records'][GUID + ':' + SIM]['history'][-1]['state'] = 'recovery-required'
                elif change == 'bank-pid':
                    bank['records'][GUID + ':' + SIM]['runtime_pid'] = 222
                elif change == 'household':
                    bank['records'][GUID + ':' + SIM]['history'][-1]['native_after']['data']['fields'][1]['value'] = '99'
                elif change == 'untyped-pending':
                    bank['records'][GUID + ':' + SIM]['switch_pending'] = False
                elif change == 'untyped-save-size':
                    closed = copy.deepcopy(self.closed)
                    for field in ('after_saves', 'rewritten_normal_slots'):
                        closed[field]['Slot_00000002.save']['bytes'] = True
                    self.saved.write_text(json.dumps(closed), encoding='utf-8')
                    expected = sha256(self.saved)
                self.bank_path.write_text(json.dumps(bank), encoding='utf-8')
                with patch.object(cas_reload.reusable_profile, 'load', return_value=(self.state, self.journal, self.profile, self.original)), self.assertRaises(ValueError):
                    cas_reload.observe(self.state, self.output, identity, self.request, self.saved, expected,
                                       SIM, HOUSEHOLD, GUID, transport=self.transport)
                self.assertEqual(self.calls, [])
                self.assertFalse(self.output.exists())

    def test_changed_save_hash_or_protected_output_refuse_before_commands(self):
        self.write_inputs()
        expected = sha256(self.saved)
        self.slot.write_bytes(b'other saved slot bytes')
        with patch.object(cas_reload.reusable_profile, 'load', return_value=(self.state, self.journal, self.profile, self.original)):
            for output in (self.output, self.profile / 'proof.json', self.original / 'proof.json'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    cas_reload.observe(self.state, output, self.identity, self.request, self.saved, expected,
                                       SIM, HOUSEHOLD, GUID, transport=self.transport)
        self.assertEqual(self.calls, [])


class CompletedTransactionReloadTests(unittest.TestCase):
    def setUp(self):
        from test_cas_bank_transaction import CasBankReceiverTests
        from apex_core import sim_data
        fixture = CasBankReceiverTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        native = native_record()
        native.update(sim_id='10', save_guid='30', native_message_type='NativeSim',
                      native_serializer_called=True, save_file_written=False)
        native['data']['fields'][0]['value'] = '10'
        native['data']['fields'][1]['value'] = '20'
        self.enterContext(patch.object(sim_data, 'snapshot', return_value=native))
        fixture.begin()
        fixture.edit(32)
        fixture.observe()
        fixture.prepare([(32, 'accept-returned')])
        fixture.commit()
        self.selected = fixture.record()
        self.reference = {'reference_kind': 'controlled-sealed-save-and-normal-unsaved-exit',
                          'prior_identity': {'pid': self.selected['runtime_pid']}}

    def check(self, selected=None, reference=None):
        return cas_reload.completed_bank_history(selected or self.selected, reference or self.reference, '10', '20', '30')

    def test_actual_receiver_completion_supports_sealed_reload_with_legacy_history_empty(self):
        self.selected['history'] = []
        proof = self.check()
        self.assertEqual(proof['source'], 'sealed-all-owner-cas-transaction')
        self.assertEqual(proof['membership'], list(cas_reload.MEMBERS))

    def test_invalid_current_receipt_never_falls_back_to_legacy_history(self):
        changed = copy.deepcopy(self.selected)
        changed['cas_transaction']['metadata_commit']['committed'] = False
        with self.assertRaisesRegex(ValueError, 'exact completed'):
            self.check(changed)
        for reference in ({'reference_kind': 'legacy', 'prior_identity': self.reference['prior_identity']},
                          {'reference_kind': self.reference['reference_kind'], 'prior_identity': {'pid': 1}}):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                self.check(reference=reference)

    def test_changed_bank_and_unbound_native_serializer_refuse_current_receipt(self):
        changed = copy.deepcopy(self.selected)
        changed['bank']['32']['physique'] = form_appearance.encode('foreign appearance')
        with self.assertRaisesRegex(ValueError, 'current bank'):
            self.check(changed)
        changed = copy.deepcopy(self.selected)
        changed['cas_transaction']['journal']['native_serialized_append']['data']['fields'][1]['value'] = '999'
        with self.assertRaisesRegex(ValueError, 'native record'):
            self.check(changed)


class FingerprintTests(unittest.TestCase):
    def test_host_matches_native_exact_growth_cleanup_without_changing_payload(self):
        from test_genetics_snapshot import genetic, part
        growth = part(300336, 78)
        raw = genetic([part(414264, 2), growth], [growth])
        cleaned = genetic([part(414264, 2)], [growth])
        original = fields(16)
        original['genetic_data'] = form_appearance.encode(raw)
        updated = copy.deepcopy(original)
        updated['genetic_data'] = form_appearance.encode(cleaned)
        with patch.dict(sys.modules, {'sims4': Obj(), 'sims4.resources': Obj(Key=lambda *args: args)}):
            expected = form_appearance.fingerprint(original)
        observed = cas_reload.appearance_fingerprint(original)
        self.assertEqual(observed, {name: expected[name] for name in ('appearance_sha256', 'field_sha256', 'readable_fields')})
        self.assertEqual(observed, cas_reload.appearance_fingerprint(updated))
        self.assertEqual(original['genetic_data'], form_appearance.encode(raw))
    def test_offline_fingerprint_matches_production_including_resource_keys_without_native_game_loading(self):
        payload = fields(16)
        with patch.dict(sys.modules, {'sims4': Obj(), 'sims4.resources': Obj(Key=lambda *args: args)}):
            production = form_appearance.fingerprint(payload)
        offline = cas_reload.appearance_fingerprint(payload)
        self.assertEqual(offline, {name: production[name] for name in ('appearance_sha256', 'field_sha256', 'readable_fields')})

    def test_unknown_invalid_or_missing_appearance_fields_never_become_empty_or_partial(self):
        for change in ({'future_field': {'kind': 'value', 'value': 1}},
                       {'skin_tone': {'kind': 'value', 'value': float('nan')}},
                       {'custom_texture': {'kind': 'resourcekey', 'value': [True, 1, 0]}},
                       {'__outfits__': {'kind': 'protobuf', 'value': 'bad base64'}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                cas_reload.appearance_fingerprint(dict(fields(1), **change))
        payload = fields(1); payload.pop('__outfits__')
        with self.assertRaises(ValueError):
            cas_reload.appearance_fingerprint(payload)


if __name__ == '__main__':
    unittest.main()
