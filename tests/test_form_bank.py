import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_bank, form_appearance as appearance, sim_data, outfit_hair
from test_outfit_snapshot import outfit


class FormBankTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.human = Obj(id=1, physique='Human original', blob=outfit(0, 1))
        self.vampire = Obj(id=2, physique='Vampire independent', blob=outfit(0, 2))
        self.sim = Obj(id=3, physique=self.human.physique, blob=self.human.blob, current_occult_types=1,
                       perks=(10, 20), fury=45)
        self.forms = {1: self.human, 4: self.vampire}
        self.sim.occult_tracker = Obj()
        def restore(target, fields):
            for name, value in fields.items():
                if name == '__outfits__': target.blob = value[1]
                else: setattr(target, name, value)
        self.backend = Obj(_data_directory=lambda: self.temp.name, _form_map=lambda _: self.forms,
            _get_current_flags=lambda sim: sim.current_occult_types, _v8_read_outfit_blob=lambda sim: sim.blob,
            _coerce_flags=lambda flags: flags, _all_occults=lambda: (4,), _has_occult=lambda *_: True,
            _disk_trait_snapshot=lambda _: [], _restore_disk_trait_snapshot=lambda *_: None,
            _ensure_human_form=lambda _: self.forms.get(1), _ensure_form=lambda _, kind, **_k: self.forms.get(kind),
            _restore_siminfo_payload=restore, _resend_all_visuals=lambda _: None,
            services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 99)))
        self.native_snapshot = self.enterContext(patch.object(sim_data, 'snapshot',
            side_effect=lambda _backend, sim: {'native_base64': 'complete native ' + sim.physique}))

    def begin(self):
        return form_bank.begin(self.backend, self.sim)

    def test_native_serializer_side_effect_is_repaired_before_final_completed_receipt(self):
        self.begin()
        self.sim.physique = 'accepted Human edit'
        calls = [0]
        def serialize(_backend, _sim):
            calls[0] += 1
            if calls[0] == 2:
                self.human.physique = 'native serializer shared rewrite'
                self.vampire.blob = outfit(0, 999)
                self.sim.physique = 'native active rewrite'
            return {'native_base64': 'complete native serializer buffer'}
        with patch.object(sim_data, 'snapshot', side_effect=serialize):
            result = form_bank.finish(self.backend, self.sim)
        self.assertTrue(result['ok'])
        self.assertEqual(self.human.physique, 'accepted Human edit')
        self.assertEqual(self.sim.physique, 'accepted Human edit')
        self.assertEqual(self.vampire.blob, outfit(0, 2))
        receipt = self.record()['history'][-1]
        self.assertEqual(receipt['state'], 'completed')
        self.assertTrue(receipt['final_native_appearance']['verified'])
        self.assertEqual(set(receipt['final_native_appearance']['stored']), {'1', '4'})
        self.assertIn('before final', receipt['native_after_scope'])

    def record(self):
        path, key = form_bank.context(self.backend, self.sim)
        return form_bank.load(path)['records'][key]

    def observe_restore_writes(self):
        writes, resends = [], []
        native_restore = self.backend._restore_siminfo_payload
        def write(target, fields):
            writes.append(target)
            native_restore(target, fields)
        self.backend._restore_siminfo_payload = write
        self.backend._resend_all_visuals = resends.append
        return writes, resends

    def complete_human_appearance(self):
        fields = dict(physique=self.human.physique, facial_attributes=b'face and unknown bytes',
                      skin_tone=(1 << 64) - 11, skin_tone_val_shift=0.37,
                      pelt_layers=b'pelt', genetic_data=b'genetics', custom_texture=b'texture',
                      parts_custom_tattoos=(123456789, 987654321), voice_pitch=0.41,
                      voice_actor=13, voice_effect=2)
        for target in (self.human, self.sim):
            for name, value in fields.items(): setattr(target, name, value)
            target.blob = outfit(0, 1) + outfit(0, 2, (1 << 64) - 3) + outfit(7, 3) + b'\x42\x03top'
        return appearance.packed(self.backend, self.human)

    def test_unchanged_complete_appearance_skips_native_writes_and_visual_resends(self):
        desired = self.complete_human_appearance()
        self.assertEqual(set(desired), set(appearance.FIELDS + ('__outfits__',)))
        # The native loader may reorder category groups without changing any
        # category-relative outfit, unknown field, or exact uint64 color.
        self.sim.blob = outfit(7, 3) + outfit(0, 1) + outfit(0, 2, (1 << 64) - 3) + b'\x42\x03top'
        writes, resends = self.observe_restore_writes()
        form_bank.restore(self.backend, self.sim, '1', desired)
        self.assertEqual(writes, [])
        self.assertEqual(resends, [])

    def test_matching_stored_wrapper_does_not_hide_changed_live_fields_or_unknown_outfit_bytes(self):
        desired = self.complete_human_appearance()
        self.sim.voice_effect = 7
        self.sim.blob = self.sim.blob[:-3] + b'new'
        writes, resends = self.observe_restore_writes()
        form_bank.restore(self.backend, self.sim, '1', desired)
        self.assertEqual(writes, [self.sim])
        self.assertEqual(resends, [self.sim])
        self.assertEqual(appearance.packed(self.backend, self.sim), desired)
        self.assertEqual(appearance.packed(self.backend, self.human), desired)

    def test_changed_stored_wrapper_does_not_reload_matching_live_sim(self):
        desired = self.complete_human_appearance()
        self.human.facial_attributes = b'changed native facial attributes'
        self.human.blob = self.human.blob[:-3] + b'new'
        writes, resends = self.observe_restore_writes()
        form_bank.restore(self.backend, self.sim, '1', desired)
        self.assertEqual(writes, [self.human])
        self.assertEqual(resends, [])
        self.assertEqual(appearance.packed(self.backend, self.human), desired)
        self.assertEqual(appearance.packed(self.backend, self.sim), desired)

    def test_inactive_matching_form_does_not_write_unrelated_live_appearance(self):
        desired = appearance.packed(self.backend, self.vampire)
        live_before = appearance.packed(self.backend, self.sim)
        writes, resends = self.observe_restore_writes()
        form_bank.restore(self.backend, self.sim, '4', desired)
        self.assertEqual(writes, [])
        self.assertEqual(resends, [])
        self.assertEqual(appearance.packed(self.backend, self.sim), live_before)

    def test_changed_stored_form_requires_exact_readback_before_live_write(self):
        desired = self.complete_human_appearance()
        self.human.skin_tone -= 1
        self.sim.physique = 'Different live appearance too'
        attempted = []
        self.backend._restore_siminfo_payload = lambda target, fields: attempted.append(target)
        self.backend._resend_all_visuals = lambda _: self.fail('failed stored readback must stop reconciliation')
        with self.assertRaisesRegex(ValueError, 'Stored form failed exact appearance readback'):
            form_bank.restore(self.backend, self.sim, '1', desired)
        self.assertEqual(attempted, [self.human])

    def test_changed_live_form_requires_exact_readback_when_wrapper_already_matches(self):
        desired = self.complete_human_appearance()
        self.sim.genetic_data = b'Unaccepted live genetics'
        attempted, resends = [], []
        self.backend._restore_siminfo_payload = lambda target, fields: attempted.append(target)
        self.backend._resend_all_visuals = resends.append
        with self.assertRaisesRegex(ValueError, 'Live form failed exact appearance readback'):
            form_bank.restore(self.backend, self.sim, '1', desired)
        self.assertEqual(attempted, [self.sim])
        self.assertEqual(resends, [self.sim])

    def test_alias_of_stored_and_live_form_is_written_only_once(self):
        desired = self.complete_human_appearance()
        self.forms[1] = self.sim
        self.sim.physique = 'Native form and Sim share one object'
        writes, resends = self.observe_restore_writes()
        form_bank.restore(self.backend, self.sim, '1', desired)
        self.assertEqual(writes, [self.sim])
        self.assertEqual(resends, [])
        self.assertEqual(appearance.packed(self.backend, self.sim), desired)

    def native_hair_policy(self):
        from test_outfit_hair import native_outfit_parser, native_outfit_fields
        parse = native_outfit_parser()
        self.sim.blob = self.human.blob = appearance.decode(native_outfit_fields(parse)['__outfits__'])[1]
        self.backend._studio_parse_snapshot = parse
        self.backend._v8_resolve_body_type = lambda name: (2 if name == 'HAIR' else 75, {}, 'runtime')
        self.sim.get_current_outfit = lambda: (0, 1)
        path, key = form_bank.context(self.backend, self.sim)
        data = form_bank.load(path)
        fields = form_bank.capture(self.backend, self.sim)
        data['records'][key] = {'bank': fields, 'history': [],
            'hair_policy': {'enabled': True, 'forms': {'1': outfit_hair.capture(self.backend, fields['1'])}}}
        form_bank.save(path, data)
        return parse

    def test_opted_in_preparation_retains_originals_before_writes_and_changes_only_selected_lane(self):
        parse = self.native_hair_policy()
        original, vampire = self.sim.blob, self.vampire.blob
        writes = []
        native_restore = self.backend._restore_siminfo_payload
        def write(target, fields):
            pending = self.record()['pending']
            self.assertEqual(appearance.decode(pending['originals']['1']['__outfits__'])[1], original)
            self.assertEqual(pending['hair_preparation']['state'], 'preparing')
            self.assertIn('native_original', pending)
            writes.append(target.id); native_restore(target, fields)
        self.backend._restore_siminfo_payload = write
        result = form_bank.begin(self.backend, self.sim, [0, 1])
        self.assertTrue(result['ok'])
        preparation = result['hair_preparation']
        self.assertEqual((preparation['outfit_count'], preparation['matching_before'], preparation['matching_after']), (9, 4, 0))
        self.assertFalse(preparation['native_cas_propagation_verified'])
        self.assertEqual(writes, [self.human.id, self.sim.id])
        self.assertEqual(self.vampire.blob, vampire)
        self.assertTrue(all(not row.match_hair_style for row in parse(self.sim.blob).outfits))
        pending = self.record()['pending']
        self.assertEqual(pending['hair_target'], [0, 1])
        self.assertEqual(pending['state'], 'captured')
        self.assertEqual(pending['hair_preparation'], preparation)
        self.assertEqual(appearance.decode(pending['originals']['1']['__outfits__'])[1], original)
        self.assertEqual(outfit_hair.style_match_status(self.backend, pending['originals']['1'])['matching_outfit_count'], 4)

    def test_missing_native_flag_retains_originals_and_refuses_ready_without_writing(self):
        self.native_hair_policy(); original = self.sim.blob
        self.backend._studio_parse_snapshot = lambda _: Obj(outfits=[])
        self.backend._restore_siminfo_payload = lambda *_: self.fail('unsupported native flag must not write')
        with patch.object(outfit_hair, 'cas_target', return_value=[0, 1]):
            with self.assertRaisesRegex(ValueError, 'field 9 is unavailable'):
                form_bank.begin(self.backend, self.sim, [0, 1])
        pending = self.record()['pending']
        self.assertEqual(pending['state'], 'recovery-required')
        self.assertEqual(pending['hair_preparation']['state'], 'failed')
        self.assertEqual(appearance.decode(pending['originals']['1']['__outfits__'])[1], original)
        self.assertEqual(self.sim.blob, original)
        with self.assertRaisesRegex(ValueError, 'retained'):
            form_bank.begin(self.backend, self.sim)

    def test_failed_native_readback_keeps_originals_in_recovery_instead_of_claiming_prepared(self):
        self.native_hair_policy(); original = self.sim.blob
        self.backend._restore_siminfo_payload = lambda *_: None
        with self.assertRaisesRegex(ValueError, 'exact appearance readback'):
            form_bank.begin(self.backend, self.sim, [0, 1])
        pending = self.record()['pending']
        self.assertEqual(pending['state'], 'recovery-required')
        self.assertEqual(pending['hair_preparation']['state'], 'failed')
        self.assertNotIn('matching_after', pending['hair_preparation'])
        self.assertEqual(appearance.decode(pending['originals']['1']['__outfits__'])[1], original)
        self.assertEqual(self.sim.blob, original)

    def test_failed_durable_preparation_intent_prevents_any_native_write(self):
        self.native_hair_policy(); original = self.sim.blob
        save = form_bank.save
        calls = []
        def journal(path, data):
            calls.append(data['records'][next(iter(data['records']))]['pending'].get('hair_preparation'))
            if len(calls) == 2: raise OSError('preparation intent disk full')
            save(path, data)
        self.backend._restore_siminfo_payload = lambda *_: self.fail('journal must precede native writes')
        with patch.object(form_bank, 'save', side_effect=journal):
            with self.assertRaisesRegex(OSError, 'disk full'):
                form_bank.begin(self.backend, self.sim, [0, 1])
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.sim.blob, original)
        self.assertEqual(appearance.decode(self.record()['pending']['originals']['1']['__outfits__'])[1], original)
        with self.assertRaisesRegex(ValueError, 'retained'):
            form_bank.begin(self.backend, self.sim)

    def test_legacy_cas_retains_simultaneous_edits_instead_of_guessing_corruption(self):
        self.begin()
        self.sim.physique, self.sim.blob = 'CAS accepted shape', outfit(0, 99)
        self.vampire.physique = 'CAS second deliberate edit or propagation: intent unknown'
        edited = appearance.evidence(self.backend, self.sim)
        other = appearance.evidence(self.backend, self.vampire)
        writes, _resends = self.observe_restore_writes()
        with self.assertRaisesRegex(ValueError, 'another form'):
            form_bank.finish(self.backend, self.sim)
        self.assertEqual(writes, [])
        self.assertEqual(appearance.evidence(self.backend, self.sim), edited)
        self.assertEqual(appearance.evidence(self.backend, self.vampire), other)
        self.assertEqual((self.sim.perks, self.sim.fury), ((10, 20), 45))
        pending = self.record()['pending']
        self.assertIn('returned', pending)
        self.assertEqual(pending['returned']['4'], appearance.packed(self.backend, self.vampire))
        self.assertEqual(pending['returned']['1'], appearance.packed(self.backend, self.sim))
        self.assertNotIn('native_returned', pending)
        self.assertEqual(self.native_snapshot.call_count, 1)  # Only original legacy capture.

    def test_wrong_form_edit_retains_both_states_without_overwriting_or_guessing(self):
        self.sim.current_occult_types = 4
        self.sim.physique, self.sim.blob = self.vampire.physique, self.vampire.blob
        self.begin()
        self.sim.current_occult_types = 1
        self.sim.physique, self.sim.blob = 'Wrong lane CAS edit', outfit(0, 77)
        with self.assertRaisesRegex(ValueError, 'another form'):
            form_bank.finish(self.backend, self.sim)
        self.assertEqual(self.sim.physique, 'Wrong lane CAS edit')
        self.assertEqual(self.vampire.physique, 'Vampire independent')
        self.assertIn('returned', self.record()['pending'])
        with self.assertRaisesRegex(ValueError, 'Pending'):
            form_bank.switch(self.backend, self.sim, 4, lambda: self.fail('must not mutate'))

    def test_switch_restores_current_accepted_bytes_but_uncertified_restart_refuses_replay(self):
        self.begin()
        self.sim.physique = 'Accepted new Human'
        form_bank.finish(self.backend, self.sim)
        accepted = appearance.evidence(self.backend, self.sim)
        def native_switch():
            self.sim.current_occult_types = 4
            self.sim.physique, self.sim.blob = 'Native copied wrong shape', outfit(0, 123)
            return {'ok': True}
        self.assertTrue(form_bank.switch(self.backend, self.sim, 4, native_switch)['ok'])
        path, key = form_bank.context(self.backend, self.sim)
        data = form_bank.load(path); data['records'][key]['runtime_pid'] = -1; form_bank.save(path, data)
        self.sim.physique = 'EA restart changed shape'
        def human_switch():
            self.sim.current_occult_types = 1
            return {'ok': True}
        before = appearance.packed(self.backend, self.sim)
        with patch('apex_core.form_bank_seal.current_runtime_bank_verified', return_value=False), self.assertRaisesRegex(ValueError, 'uncertified'):
            form_bank.switch(self.backend, self.sim, 1, lambda: self.fail('uncertified native switch must not run'))
        self.assertEqual(appearance.packed(self.backend, self.sim), before)
        self.assertEqual(self.record(), data['records'][key])

    def test_fresh_cas_checkpoint_replaces_lane_map_and_retains_prior_missing_owner_as_history(self):
        self.begin(); form_bank.finish(self.backend, self.sim)
        path, key = form_bank.context(self.backend, self.sim)
        data = form_bank.load(path); old = data['records'][key]
        old['bank']['16'] = appearance.packed(self.backend, self.vampire)
        old['runtime_pid'] = -1
        retained = json.loads(json.dumps(old['bank']))
        form_bank.save(path, data)
        self.human.physique = self.sim.physique = 'fresh native Human after reload'
        self.begin()
        pending = self.record()['pending']
        self.assertTrue(pending['fresh_runtime_checkpoint'])
        self.assertEqual(pending['prior_bank'], retained)
        self.assertNotIn('16', pending['originals'])
        self.sim.physique = 'fresh CAS accepted Human'
        form_bank.finish(self.backend, self.sim)
        final = self.record()
        self.assertEqual(set(final['bank']), {'1', '4'})
        self.assertEqual(final['history'][-1]['prior_bank'], retained)
        self.assertNotIn(16, self.forms)
        self.assertEqual(self.sim.physique, 'fresh CAS accepted Human')

    def test_certified_current_runtime_switch_preserves_new_unsaved_source_appearance(self):
        self.begin(); form_bank.finish(self.backend, self.sim)
        path, key = form_bank.context(self.backend, self.sim)
        data = form_bank.load(path); data['records'][key]['runtime_pid'] = -1
        form_bank.save(path, data)
        self.sim.physique = 'latest unsaved Human edit after certified reload'
        source = appearance.packed(self.backend, self.sim)
        def native_switch():
            self.sim.current_occult_types = 4
            self.sim.physique = 'native target shared rewrite'
            return {'ok': True}
        with patch('apex_core.form_bank_seal.current_runtime_bank_verified', return_value=True):
            self.assertTrue(form_bank.switch(self.backend, self.sim, 4, native_switch)['ok'])
        self.assertEqual(self.record()['bank']['1'], source)
        self.assertEqual(self.sim.physique, self.vampire.physique)

    def test_fresh_cas_hair_baseline_uses_current_originals_and_retains_old_policy(self):
        self.native_hair_policy()
        path, key = form_bank.context(self.backend, self.sim)
        data = form_bank.load(path)
        old = data['records'][key]
        old['runtime_pid'] = -1
        old['hair_policy']['forms']['1'][0]['id'] = 999999
        old_policy = json.loads(json.dumps(old['hair_policy']))
        current = outfit_hair.capture(self.backend, appearance.packed(self.backend, self.sim))
        form_bank.save(path, data)
        form_bank.begin(self.backend, self.sim, [0, 1])
        self.assertEqual(self.record()['pending']['prior_hair_policy'], old_policy)
        self.assertEqual(self.record()['hair_policy']['forms']['1'], current)

    def test_explicit_one_lane_update_rebases_all_stale_lanes_before_current_pid_stamp(self):
        self.begin(); form_bank.finish(self.backend, self.sim)
        path, key = form_bank.context(self.backend, self.sim)
        data = form_bank.load(path); data['records'][key]['runtime_pid'] = -1
        old_bank = json.loads(json.dumps(data['records'][key]['bank']))
        form_bank.save(path, data)
        self.vampire.physique = 'Fresh reload Vampire must survive'
        self.sim.physique = self.human.physique = 'Explicit current-runtime Human edit'
        form_bank.update(self.backend, self.sim, 1, appearance.packed(self.backend, self.sim))
        record = self.record()
        self.assertTrue(record['native_rebase_requires_cas_completion'])
        self.assertEqual(appearance.decode(record['bank']['4']['physique']), 'Fresh reload Vampire must survive')
        self.assertEqual(record['bank_rebase_history'][-1]['prior_bank'], old_bank)
        def native_switch():
            self.sim.current_occult_types = 4
            self.sim.physique, self.sim.blob = self.vampire.physique, self.vampire.blob
            return {'ok': True}
        self.assertTrue(form_bank.switch(self.backend, self.sim, 4, native_switch)['ok'])
        self.assertEqual(self.sim.physique, 'Fresh reload Vampire must survive')
        self.assertEqual(self.vampire.physique, 'Fresh reload Vampire must survive')
        self.begin(); form_bank.finish(self.backend, self.sim)
        self.assertFalse(self.record()['native_rebase_requires_cas_completion'])

    def test_prior_or_unknown_pending_runtime_cannot_finish_or_touch_native_appearance(self):
        self.begin()
        path, key = form_bank.context(self.backend, self.sim)
        for prior in (-1, None, True):
            data = form_bank.load(path); data['records'][key]['pending']['runtime_pid'] = prior
            form_bank.save(path, data)
            original_file = path.read_bytes()
            self.human.physique = self.sim.physique = 'fresh reload Human'
            self.vampire.physique = 'fresh reload Vampire'
            fields = appearance.packed(self.backend, self.sim)
            with self.subTest(pid=prior), self.assertRaisesRegex(ValueError, 'another or unknown runtime'):
                form_bank.finish(self.backend, self.sim)
            self.assertEqual(path.read_bytes(), original_file)
            self.assertEqual(appearance.packed(self.backend, self.sim), fields)
            self.assertEqual(self.vampire.physique, 'fresh reload Vampire')

    def test_interrupted_restore_preserves_edits_and_refuses_second_transition(self):
        self.begin()
        self.sim.physique = 'New CAS edit'
        self.backend._restore_siminfo_payload = lambda *_: None
        with self.assertRaisesRegex(ValueError, 'readback'):
            form_bank.finish(self.backend, self.sim)
        self.assertEqual(self.sim.physique, 'New CAS edit')
        self.assertEqual(self.record()['pending']['state'], 'recovery-required')
        with self.assertRaisesRegex(ValueError, 'Pending'):
            form_bank.switch(self.backend, self.sim, 4, lambda: self.fail('must not mutate'))

    def test_failed_membership_recovery_retains_native_cas_return_before_restoring_any_appearance(self):
        self.begin()
        self.sim.physique = 'Accepted edit with missing Vampire'
        self.backend._has_occult = lambda *_: False
        self.backend._add_occult = lambda *_a, **_k: None
        self.backend._restore_siminfo_payload = lambda *_: self.fail('appearance must not change')
        with self.assertRaisesRegex(ValueError, 'membership recovery failed'):
            form_bank.finish(self.backend, self.sim)
        record = self.record()
        self.assertEqual(record['pending']['state'], 'recovery-required')
        self.assertIn('missing Vampire', record['pending']['native_returned']['native_base64'])
        self.assertFalse(form_bank.status(self.backend, self.sim)['switch_pending'])

    def test_new_cas_session_cannot_overwrite_interrupted_switch_original(self):
        self.begin()
        form_bank.finish(self.backend, self.sim)
        def failed_transition():
            return {'ok': False}
        self.assertFalse(form_bank.switch(self.backend, self.sim, 4, failed_transition)['ok'])
        with self.assertRaisesRegex(ValueError, 'retained'):
            self.begin()
        self.assertTrue(form_bank.status(self.backend, self.sim)['switch_pending'])

    def test_occult_trait_loss_is_not_hidden_by_cached_membership(self):
        self.backend._disk_trait_snapshot = lambda _: [{'trait_id': 123, 'occult': 'VAMPIRE'}]
        self.begin()
        self.sim.physique = 'New accepted CAS shape'
        self.backend._disk_trait_snapshot = lambda _: []
        self.backend._restore_siminfo_payload = lambda *_: self.fail('appearance must not change')
        with self.assertRaisesRegex(ValueError, 'trait recovery failed'):
            form_bank.finish(self.backend, self.sim)
        self.assertEqual(self.record()['pending']['state'], 'recovery-required')
        self.assertEqual(self.sim.physique, 'New accepted CAS shape')
