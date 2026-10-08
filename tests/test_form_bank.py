import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_bank, form_appearance as appearance, sim_data
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
