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

    def record(self):
        path, key = form_bank.context(self.backend, self.sim)
        return form_bank.load(path)['records'][key]

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

    def test_real_cas_changes_preserved_and_other_form_corruption_repaired(self):
        before = appearance.evidence(self.backend, self.vampire)
        self.begin()
        self.sim.physique, self.sim.blob = 'CAS accepted shape', outfit(0, 99)
        self.vampire.physique = 'CAS accidentally clobbered inactive form'
        edited = appearance.evidence(self.backend, self.sim)
        result = form_bank.finish(self.backend, self.sim)
        self.assertTrue(result['edited'])
        self.assertEqual(appearance.evidence(self.backend, self.sim), edited)
        self.assertEqual(appearance.evidence(self.backend, self.vampire), before)
        self.assertEqual((self.sim.perks, self.sim.fury), ((10, 20), 45))
        self.assertIsNone(self.record()['pending'])
        self.assertIn('returned', self.record()['history'][0])
        self.assertEqual(self.record()['history'][0]['native_returned']['native_base64'], 'complete native CAS accepted shape')
        self.assertEqual(self.record()['history'][0]['native_after']['native_base64'], 'complete native CAS accepted shape')

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

    def test_switch_restores_every_accepted_byte_and_stale_restart_does_not_erase_bank(self):
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
        self.assertTrue(form_bank.switch(self.backend, self.sim, 1, human_switch)['ok'])
        self.assertEqual(appearance.evidence(self.backend, self.sim), accepted)
        self.assertEqual(len(self.record()['restart_observations']), 1)

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
