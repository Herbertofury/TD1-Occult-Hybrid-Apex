"""Offline native-hop counterexamples for all-owner switch preservation."""
import copy
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_bank, form_appearance as appearance
from apex_core import outfit_hair, studio
from test_outfit_snapshot import outfit
from test_outfit_hair import native_outfit_parser, native_outfit_fields

LANES = (1, 2, 4, 8, 16, 32, 64)


def make_owner(lane, identity):
    owner = Obj(id=identity, physique='independent physique ' + str(lane),
                facial_attributes=('opaque face ' + str(lane)).encode(),
                skin_tone=(1 << 64) - lane, skin_tone_val_shift=lane / 100.0,
                pelt_layers=('opaque pelt ' + str(lane)).encode(),
                genetic_data=('opaque genetics ' + str(lane)).encode(),
                custom_texture=('opaque texture ' + str(lane)).encode(),
                parts_custom_tattoos=(lane * 17, lane * 31),
                voice_pitch=lane / 100.0, voice_actor=lane, voice_effect=lane,
                blob=outfit(0, lane * 100 + 1, (1 << 64) - lane) +
                     outfit(0, lane * 100 + 2, (1 << 63) + lane) +
                     outfit(11, lane * 100 + 3, lane) + b'\x42\x03top')
    return owner


class FormSwitchAllOwnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.forms = {lane: make_owner(lane, 1000 + lane) for lane in LANES}
        self.sim = copy.deepcopy(self.forms[4])
        self.sim.id = 9999
        self.sim.current_occult_types = 4
        self.sim.occult_tracker = Obj()
        self.sim.perks = (23, 29)
        self.sim.fury = 75
        self.writes = []

        def restore(target, fields):
            self.writes.append(target.id)
            for name, value in fields.items():
                if name == '__outfits__':
                    target.blob = value[1]
                else:
                    setattr(target, name, copy.deepcopy(value))
        self.backend = Obj(
            _data_directory=lambda: self.directory.name,
            _form_map=lambda _: self.forms,
            _get_current_flags=lambda sim: sim.current_occult_types,
            _v8_read_outfit_blob=lambda owner: owner.blob,
            _coerce_flags=lambda flags: flags,
            _ensure_human_form=lambda _: self.forms[1],
            _ensure_form=lambda _, kind, **kwargs: self.forms.get(kind),
            _restore_siminfo_payload=restore,
            _resend_all_visuals=lambda _: None,
            services=Obj(get_persistence_service=lambda:
                         Obj(get_save_slot_proto_guid=lambda: 123456)))
        self.path, self.key = form_bank.context(self.backend, self.sim)
        bank = {str(lane): appearance.packed(self.backend, owner)
                for lane, owner in self.forms.items()}
        form_bank.save(self.path, {'schema': 1, 'records': {
            self.key: {'bank': bank, 'history': [], 'runtime_pid': os.getpid()}}})
        # Distinct Live source is deliberately newer than both stored wrapper
        # and accepted bank; selecting away must preserve this unsaved work.
        self.sim.physique = 'newest unsaved Vampire physique'
        self.sim.blob = outfit(0, 7654321, (1 << 64) - 7) + b'\x42\x03new'
        self.original_stored = {str(lane): appearance.packed(self.backend, owner)
                                for lane, owner in self.forms.items()}
        self.original_live = appearance.packed(self.backend, self.sim)
        self.expected = copy.deepcopy(self.original_stored)
        self.expected['4'] = copy.deepcopy(self.original_live)
        self.hops = []

    def operation(self, corrupt_source=False, refused=False, raises=False):
        # First route: store current Vampire, then copy shared shape/hidden
        # clothing into the intermediate Human wrapper. Only the fixture does
        # this; no installed native code is executed or synthesized as fact.
        self.hops.append(1)
        self.backend._restore_siminfo_payload(self.forms[4], appearance.payload(self.original_live))
        self.forms[1].physique = self.sim.physique
        self.forms[1].blob = outfit(0, 9000001) + b'\x42\x03mid'
        self.sim.current_occult_types = 1
        self.sim.physique, self.sim.blob = self.forms[1].physique, self.forms[1].blob
        if raises:
            raise ValueError('fixture native second hop failed')
        if refused:
            return {'ok': False, 'message': 'fixture target did not converge'}
        self.hops.append(64)
        if corrupt_source:
            # An independently injected inactive source overwrite proves that
            # source preservation is also not part of the reported readback.
            self.forms[4].physique = 'inactive source overwritten after intermediate Human'
            self.forms[4].blob = outfit(0, 9000002) + b'\x42\x03bad'
        self.forms[64].physique = 'native final target copied shared shape'
        self.sim.current_occult_types = 64
        self.sim.physique, self.sim.blob = self.forms[64].physique, self.forms[64].blob
        return {'ok': True}

    def record(self):
        return form_bank.load(self.path)['records'][self.key]

    def invoke(self, operation=None):
        self.operation_calls = getattr(self, 'operation_calls', 0)
        action = operation or (lambda: self.operation(corrupt_source=True))
        def once():
            self.operation_calls += 1
            return action()
        return form_bank.switch(self.backend, self.sim, 64, once)

    def assert_all(self, expected=None):
        expected = expected or self.expected
        for lane, owner in self.forms.items():
            with self.subTest(lane=lane):
                self.assertEqual(appearance.fingerprint(appearance.packed(self.backend, owner)),
                                 appearance.fingerprint(expected[str(lane)]))
        self.assertEqual(appearance.packed(self.backend, self.sim), expected['64'])
        self.assertEqual((self.sim.perks, self.sim.fury), ((23, 29), 75))

    def assert_retained(self):
        pending = self.record()['switch_pending']
        self.assertIsNotNone(pending)
        self.assertEqual(pending['stored_originals'], self.original_stored)
        self.assertEqual(pending['active_original'], self.original_live)
        self.assertEqual(self.record()['bank']['4'], self.original_live)
        self.assertEqual(set(pending['desired_stored']), {'1', '2', '4', '8', '16', '32', '64'})
        self.assertFalse(pending['simulation_settled_verified'])
        with self.assertRaises(ValueError):
            self.invoke(lambda: self.fail('Unresolved operation cannot replay.'))
        return pending

    def test_all_seven_and_distinct_latest_source_survive_intermediate_human(self):
        result = self.invoke()
        self.assert_all()
        self.assertEqual(self.operation_calls, 1)
        self.assertTrue(result['all_stored_owners_verified'])
        self.assertTrue(result['active_owner_verified'])
        self.assertFalse(result['simulation_settled_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertIsNone(self.record()['switch_pending'])
        history = self.record()['switch_history'][-1]
        self.assertEqual(history['stored_originals'], self.original_stored)
        self.assertEqual(history['active_original'], self.original_live)
        self.assertEqual(history['request_id'], result['switch_request_id'])


    def test_untouched_fresh_native_owner_does_not_replay_old_bank(self):
        self.forms[8].physique = 'new native Mermaid since previous bank commit'
        self.forms[8].genetic_data = b'new opaque Mermaid genetics'
        self.original_stored['8'] = appearance.packed(self.backend, self.forms[8])
        self.expected['8'] = copy.deepcopy(self.original_stored['8'])
        self.invoke()
        self.assert_all()
        self.assertEqual(self.record()['bank']['8'], self.original_stored['8'])

    def test_fresh_target_edit_wins_and_prior_cached_target_is_retained(self):
        cached_target = copy.deepcopy(self.record()['bank']['64'])
        self.forms[64].physique = 'intentional new inactive Fairy CAS/MCCC edit'
        self.forms[64].blob = outfit(0, 9823451, (1 << 64) - 5) + b'\x42\x03new'
        self.original_stored['64'] = appearance.packed(self.backend, self.forms[64])
        self.expected['64'] = copy.deepcopy(self.original_stored['64'])
        self.invoke()
        self.assert_all()
        history = self.record()['switch_history'][-1]
        self.assertEqual(history['stored_originals']['64'], self.original_stored['64'])
        self.assertEqual(history['previous_bank']['64'], cached_target)
        self.assertEqual(self.record()['bank']['64'], self.original_stored['64'])
        difference = history['native_vs_bank_differences']['64']
        self.assertTrue(difference['bank_present'])
        self.assertEqual(set(difference['changed_fields']), {'physique', '__outfits__'})
        self.assertEqual(difference['bank_appearance_sha256'], appearance.fingerprint(cached_target)['appearance_sha256'])
        self.assertEqual(difference['native_appearance_sha256'], appearance.fingerprint(self.original_stored['64'])['appearance_sha256'])

    def test_final_active_write_collateral_to_earlier_human_is_refused(self):
        original_restore = self.backend._restore_siminfo_payload
        def collateral(owner, fields):
            original_restore(owner, fields)
            if owner is self.sim:
                self.forms[1].physique = 'collateral after final active write'
        self.backend._restore_siminfo_payload = collateral
        with self.assertRaisesRegex(ValueError, 'final readback after the last'):
            self.invoke()
        pending = self.assert_retained()
        self.assertEqual(self.operation_calls, 1)
        self.assertEqual(appearance.decode(pending['returned_stored']['1']['physique']),
                         'collateral after final active write')
        self.assertEqual(pending['state'], 'recovery-required')

    def test_partial_native_restore_refuses_and_retains_complete_returned_data(self):
        original_restore = self.backend._restore_siminfo_payload
        def partial(owner, fields):
            if owner is self.forms[1]:
                return  # Requested Human restore did not take effect.
            original_restore(owner, fields)
        self.backend._restore_siminfo_payload = partial
        with self.assertRaisesRegex(ValueError, 'immediate appearance readback'):
            self.invoke()
        self.assert_retained()
        self.assertEqual(self.operation_calls, 1)

    def test_refused_intermediate_hop_retains_every_original_and_blocks_replay(self):
        result = self.invoke(lambda: self.operation(refused=True))
        self.assertFalse(result['ok'])
        self.assertFalse(result['independent_appearance_verified'])
        pending = self.assert_retained()
        self.assertEqual(pending['state'], 'native-did-not-converge')
        self.assertEqual(self.operation_calls, 1)

    def test_raised_intermediate_hop_retains_every_original_and_blocks_replay(self):
        with self.assertRaisesRegex(ValueError, 'second hop failed'):
            self.invoke(lambda: self.operation(raises=True))
        self.assert_retained()
        self.assertEqual(self.operation_calls, 1)

    def test_replaced_owner_is_retained_only_as_unverified_and_never_restored(self):
        def replacement():
            self.forms[64] = copy.deepcopy(self.forms[64])
            self.forms[64].id += 10
            self.sim.current_occult_types = 64
            return {'ok': True}
        before_writes = len(self.writes)
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.invoke(replacement)
        pending = self.assert_retained()
        self.assertEqual(len(self.writes), before_writes)
        self.assertFalse(pending['returned_identity_verified'])
        self.assertIn('unverified_returned_stored', pending)
        self.assertEqual(self.operation_calls, 1)

    def test_new_owner_after_operation_is_not_generated_or_silently_accepted(self):
        def addition():
            self.forms[128] = make_owner(128, 1128)
            self.sim.current_occult_types = 64
            return {'ok': True}
        with self.assertRaisesRegex(ValueError, 'owner set changed'):
            self.invoke(addition)
        pending = self.assert_retained()
        self.assertIn('128', pending['unverified_returned_stored'])
        self.assertEqual(self.writes, [])
        self.assertEqual(self.operation_calls, 1)

    def test_absent_bank_owner_refuses_before_native_or_file_write(self):
        self.forms.pop(2)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'absent native owner'):
            self.invoke(lambda: self.fail('Absent owner cannot be recreated.'))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.operation_calls, 0)

    def test_stale_bank_refuses_before_native_or_file_write(self):
        before = self.path.read_bytes()
        with patch.object(form_bank, 'current_runtime_authorized', return_value=False):
            with self.assertRaisesRegex(ValueError, 'uncertified'):
                self.invoke(lambda: self.fail('Old bank cannot replay.'))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.operation_calls, 0)

    def test_armed_checkpoint_failure_never_calls_native_and_retains_full_originals(self):
        real_save = form_bank.save
        count = [0]
        def save(path, data):
            count[0] += 1
            if count[0] == 2:
                raise OSError('fixture armed WAL storage failure')
            return real_save(path, data)
        with patch.object(form_bank, 'save', side_effect=save):
            with self.assertRaisesRegex(OSError, 'armed WAL storage failure'):
                self.invoke(lambda: self.fail('No durable submission arm; no native call.'))
        pending = self.assert_retained()
        self.assertEqual(self.operation_calls, 0)
        self.assertFalse(pending['native_operation_attempted'])
        self.assertEqual(self.writes, [])

    def test_completion_save_failure_retains_full_wal_without_operation_replay(self):
        real_save = form_bank.save
        count = [0]
        def save(path, data):
            count[0] += 1
            if count[0] == 6:
                raise OSError('fixture completion metadata storage failure')
            return real_save(path, data)
        with patch.object(form_bank, 'save', side_effect=save):
            with self.assertRaisesRegex(OSError, 'completion metadata storage failure'):
                self.invoke()
        self.assert_all()
        self.assert_retained()
        self.assertEqual(self.operation_calls, 1)

    def test_history_beyond_old_cutoff_retains_every_row_and_allows_next_switch(self):
        data = form_bank.load(self.path)
        data['records'][self.key]['switch_history'] = [{'retained': i} for i in range(32)]
        form_bank.save(self.path, data)
        self.invoke()
        from apex_core.bank_history import resolve
        rows = self.record()['switch_history']
        self.assertEqual([resolve(self.path, row) for row in rows[:-1]],
                         [{'retained': i} for i in range(32)])
        self.assertEqual(len(rows), 33)
        self.assertEqual(self.operation_calls, 1)

    def test_no_prior_bank_uses_only_current_native_owners_and_latest_live(self):
        data = form_bank.load(self.path)
        del data['records'][self.key]
        form_bank.save(self.path, data)
        self.invoke()
        self.assert_all()
        self.assertEqual(self.record()['switch_history'][-1]['previous_bank'], {})

    def test_zero_native_wrapper_ids_are_preserved_without_inventing_identity(self):
        # Base wrappers may expose unset IDs; distinct retained object/lane
        # identities remain mandatory, and the selected managed Sim stays >0.
        for owner in self.forms.values():
            owner.id = 0
        self.invoke()
        self.assert_all()
        history = self.record()['switch_history'][-1]
        self.assertTrue(all(row['value'] == '0' for row in history['owner_ids'].values()))
        self.assertEqual(history['sim_id']['value'], '9999')

    def test_native_manager_identity_loss_blocks_every_reconciliation_write(self):
        current = [self.sim]
        self.backend.services.sim_info_manager = lambda: Obj(get=lambda identity: current[0])
        def replace_manager():
            current[0] = None
            self.sim.current_occult_types = 64
            return {'ok': True}
        with self.assertRaisesRegex(ValueError, 'manager object'):
            self.invoke(replace_manager)
        pending = self.assert_retained()
        self.assertEqual(self.writes, [])
        self.assertTrue(pending['manager_identity_verified'])
        self.assertFalse(pending['returned_identity_verified'])

    def test_stored_owner_alias_refuses_before_native_or_checkpoint_write(self):
        self.forms[64] = self.forms[1]
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'owners alias'):
            self.invoke(lambda: self.fail('Aliased native lanes cannot be separated by guessing.'))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.operation_calls, 0)


    def test_native_call_observes_durable_issued_identity_and_all_originals(self):
        observed = []
        def operation():
            pending = self.record()['switch_pending']
            observed.append(pending['request_id'])
            self.assertEqual(pending['state'], 'native-operation-issued')
            self.assertTrue(pending['native_operation_attempted'])
            self.assertEqual(pending['stored_originals'], self.original_stored)
            self.assertEqual(pending['active_original'], self.original_live)
            return self.operation(corrupt_source=True)
        result = self.invoke(operation)
        self.assertEqual(observed, [result['switch_request_id']])
        self.assertEqual(self.operation_calls, 1)

    def test_abrupt_operation_exit_leaves_issued_request_blocked_without_replay(self):
        def interrupted():
            self.forms[1].physique = 'partial native hop before abrupt exit'
            raise SystemExit('fixture abrupt native exit')
        with self.assertRaisesRegex(SystemExit, 'abrupt native exit'):
            self.invoke(interrupted)
        pending = self.assert_retained()
        self.assertEqual(pending['state'], 'native-operation-issued')
        self.assertTrue(pending['native_operation_attempted'])
        self.assertEqual(self.operation_calls, 1)

    def test_secondary_diagnostic_storage_failure_preserves_original_native_exception(self):
        real_save = form_bank.save
        def refused_diagnosis(path, data):
            if data['records'][self.key]['switch_pending']['state'] == 'recovery-required':
                raise OSError('fixture failure diagnosis cannot be persisted')
            return real_save(path, data)
        with patch.object(form_bank, 'save', side_effect=refused_diagnosis):
            with self.assertRaisesRegex(ValueError, 'second hop failed'):
                self.invoke(lambda: self.operation(raises=True))
        pending = self.assert_retained()
        self.assertEqual(pending['state'], 'native-operation-issued')
        self.assertTrue(pending['native_operation_attempted'])
        self.assertEqual(self.operation_calls, 1)


class EnabledHairSwitchTests(unittest.TestCase):
    """A fresh appearance must remain fresh when the actual hair guard runs."""
    record = FormSwitchAllOwnerTests.record

    def setUp(self):
        FormSwitchAllOwnerTests.setUp(self)
        self.parse = native_outfit_parser()
        self.backend._studio_parse_snapshot = self.parse
        self.backend._v8_resolve_body_type = lambda name: (2 if name == 'HAIR' else 75, {}, 'native-fixture')
        for lane, owner in self.forms.items():
            fields = native_outfit_fields(self.parse)
            message = self.parse(appearance.decode(fields['__outfits__'])[1])
            for index, item in enumerate(message.outfits):
                item.parts.ids[0] = (1 << 64) - lane - index
                item.parts.ids[1] += lane
                item.part_shifts.color_shift[0] = (1 << 64) - lane - index
            owner.blob = message.SerializeToString()
        self.sim.blob = self.forms[4].blob
        self.original_stored = {str(lane): appearance.packed(self.backend, owner)
                                for lane, owner in self.forms.items()}
        data = form_bank.load(self.path)
        row = data['records'][self.key]
        row['bank'] = copy.deepcopy(self.original_stored)
        row['hair_policy'] = {'enabled': True, 'future_setting': {'revision': 73},
            'forms': {lane: outfit_hair.capture(self.backend, fields)
                      for lane, fields in self.original_stored.items()}}
        self.prior_policy = copy.deepcopy(row['hair_policy'])
        form_bank.save(self.path, data)
        # Source Live hair can itself be newer than its stored/cached wrapper.
        message = self.parse(self.sim.blob)
        message.outfits[1].parts.ids[0] = (1 << 64) - 321
        message.outfits[1].part_shifts.color_shift[0] = (1 << 64) - 123
        self.sim.blob = message.SerializeToString()
        self.original_live = appearance.packed(self.backend, self.sim)
        self.expected = copy.deepcopy(self.original_stored)
        self.expected['4'] = copy.deepcopy(self.original_live)
        self.operation_calls = 0
        self.addCleanup(outfit_hair._BUSY.clear)
        self.addCleanup(outfit_hair._ERRORS.clear)

    def select_human(self):
        self.operation_calls += 1
        self.sim.current_occult_types = 1
        self.backend._restore_siminfo_payload(self.sim, appearance.payload(
            appearance.packed(self.backend, self.forms[1])))
        return {'ok': True}

    def invoke(self):
        return form_bank.switch(self.backend, self.sim, 1, self.select_human)

    def fresh_human_hair(self):
        message = self.parse(self.forms[1].blob)
        message.outfits[0].parts.ids[0] = 1234567890123456789
        message.outfits[0].part_shifts.color_shift[0] = (1 << 64) - 77
        self.forms[1].blob = message.SerializeToString()
        self.original_stored['1'] = appearance.packed(self.backend, self.forms[1])
        self.expected['1'] = copy.deepcopy(self.original_stored['1'])

    def assert_planning_failure(self):
        row = self.record()
        pending = row['switch_pending']
        self.assertEqual(self.operation_calls, 0)
        self.assertEqual(self.writes, [])
        self.assertEqual(row['hair_policy'], self.prior_policy)
        self.assertEqual(pending['prior_hair_policy'], self.prior_policy)
        self.assertEqual(pending['stored_originals'], self.original_stored)
        self.assertEqual(pending['active_original'], self.original_live)
        self.assertFalse(pending['native_operation_attempted'])
        self.assertEqual(pending['state'], 'recovery-required')
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(self.operation_calls, 0)

    def test_new_inactive_hair_and_latest_source_remain_after_real_enforce(self):
        self.fresh_human_hair()
        result = self.invoke()
        row = self.record()
        self.assertTrue(result['hair_policy_synchronized'])
        self.assertEqual(row['hair_policy']['future_setting'], {'revision': 73})
        self.assertEqual(set(row['hair_policy']['forms']), {str(lane) for lane in LANES})
        for lane, fields in self.expected.items():
            self.assertEqual(row['hair_policy']['forms'][lane], outfit_hair.capture(self.backend, fields))
            self.assertEqual(appearance.packed(self.backend, self.forms[int(lane)]), fields)
        self.assertEqual(row['switch_history'][-1]['prior_hair_policy'], self.prior_policy)
        self.assertTrue(row['switch_history'][-1]['hair_policy_synchronized'])
        old = self.prior_policy['forms']['1'][0]['hair'][0]['row']['id']
        self.assertEqual(old, (1 << 64) - 1)
        self.assertEqual(row['hair_policy']['forms']['1'][0]['hair'][0]['row']['id'], 1234567890123456789)
        fields = appearance.packed(self.backend, self.sim)
        before = studio._state_from_fields(self.backend, fields)
        writes = list(self.writes)
        with patch.object(studio, '_context', return_value=(self.sim, before, Obj(data={'pending': None}), None)), \
                patch.object(studio, 'dispatch', side_effect=AssertionError('Fresh hair must need no repair')) as apply:
            self.assertFalse(outfit_hair.enforce(self.backend, self.sim))
        apply.assert_not_called()
        self.assertEqual(self.writes, writes)
        self.assertEqual(appearance.packed(self.backend, self.sim), self.expected['1'])
        self.assertEqual(self.operation_calls, 1)

    def test_capture_failure_after_partial_planning_retains_all_originals_before_native(self):
        real_capture = outfit_hair.capture
        calls = []
        def broken(backend, fields):
            calls.append(fields['physique'])
            if len(calls) == 2:
                raise ValueError('fixture second owner hair capture failed')
            return real_capture(backend, fields)
        with patch.object(outfit_hair, 'capture', side_effect=broken):
            with self.assertRaisesRegex(ValueError, 'second owner hair capture failed'):
                self.invoke()
        self.assertEqual(len(calls), 2)
        self.assert_planning_failure()

    def test_partial_category_number_coverage_cannot_activate_new_policy(self):
        real_capture = outfit_hair.capture
        def partial(backend, fields):
            held = real_capture(backend, fields)
            return held[:1] + held[2:]  # Everyday 2 missing; an empty hair row is different.
        with patch.object(outfit_hair, 'capture', side_effect=partial):
            with self.assertRaisesRegex(ValueError, 'complete intended native owner wardrobe'):
                self.invoke()
        self.assert_planning_failure()

    def test_other_owner_hair_rows_cannot_be_installed_under_matching_slots_and_uids(self):
        real_capture = outfit_hair.capture
        # All seven owners intentionally share these outfit UIDs. Lane identity
        # still matters; a matching UID cannot approve another owner's hair.
        wrong_owner = real_capture(self.backend, self.original_stored['2'])
        def wrong(backend, fields):
            if fields['physique'] == self.original_stored['1']['physique']:
                return copy.deepcopy(wrong_owner)
            return real_capture(backend, fields)
        with patch.object(outfit_hair, 'capture', side_effect=wrong):
            with self.assertRaisesRegex(ValueError, 'complete intended native owner wardrobe'):
                self.invoke()
        self.assert_planning_failure()

    def test_wrong_native_uid_cannot_be_installed_even_with_complete_slot_count(self):
        real_capture = outfit_hair.capture
        def wrong(backend, fields):
            held = real_capture(backend, fields)
            held[0]['outfit_id'] = '123456789'
            return held
        with patch.object(outfit_hair, 'capture', side_effect=wrong):
            with self.assertRaisesRegex(ValueError, 'complete intended native owner wardrobe'):
                self.invoke()
        self.assert_planning_failure()

    def test_disabled_policy_and_unknown_settings_are_retained_without_capture(self):
        data = form_bank.load(self.path)
        data['records'][self.key]['hair_policy']['enabled'] = False
        form_bank.save(self.path, data)
        disabled = copy.deepcopy(self.record()['hair_policy'])
        with patch.object(outfit_hair, 'capture', side_effect=AssertionError('Disabled policy requires no native capture')):
            result = self.invoke()
        self.assertFalse(result['hair_policy_synchronized'])
        self.assertEqual(self.record()['hair_policy'], disabled)
        self.assertEqual(self.record()['switch_history'][-1]['prior_hair_policy'], disabled)

    def test_completion_failure_retains_policy_plan_and_blocks_hair_enforcement(self):
        self.fresh_human_hair()
        real_save, count = form_bank.save, [0]
        def failing(path, data):
            count[0] += 1
            if count[0] == 6:
                raise OSError('fixture completion storage failed')
            return real_save(path, data)
        with patch.object(form_bank, 'save', side_effect=failing):
            with self.assertRaisesRegex(OSError, 'completion storage failed'):
                self.invoke()
        row = self.record()
        pending = row['switch_pending']
        self.assertEqual(pending['prior_hair_policy'], self.prior_policy)
        self.assertEqual(pending['hair_policy_plan'], row['hair_policy'])
        self.assertEqual(pending['stored_originals'], self.original_stored)
        with patch.object(studio, '_context', side_effect=AssertionError('Unresolved switch blocks hair enforcement')):
            self.assertFalse(outfit_hair.enforce(self.backend, self.sim))
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(self.operation_calls, 1)


if __name__ == '__main__':
    unittest.main()
