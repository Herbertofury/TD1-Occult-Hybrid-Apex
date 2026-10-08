from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_appearance as appearance, human_werewolf, form_bank
from test_outfit_snapshot import outfit


class AppearanceTests(unittest.TestCase):
    def test_typed_snapshot_retains_native_bytes_and_rejects_executable_values(self):
        value = {'dna': b'\x00\xff', 'pelt': [1, 2, (1 << 64) - 1]}
        self.assertEqual(appearance.decode(appearance.encode(value)), value)
        for item in (object(), float('nan')):
            with self.assertRaises(ValueError):
                appearance.encode(item)
        with self.assertRaises(ValueError):
            appearance.decode({'kind': 'pickle', 'value': 'arbitrary'})
        with self.assertRaises(ValueError):
            appearance.payload({'occult_types': appearance.encode(32)})

    def test_snapshot_detects_shape_shift_tattoo_and_every_outfit_color(self):
        fields = {'physique': appearance.encode('0.1,0.2'), 'skin_tone_val_shift': appearance.encode(0.15),
                  'parts_custom_tattoos': appearance.encode(b'tattoo'),
                  '__outfits__': appearance.encode(('protobuf', outfit(0, 1) + outfit(9, 2)))}
        initial = appearance.fingerprint(fields)
        for name, value in (('skin_tone_val_shift', 0.25), ('physique', '0.2,0.2'), ('parts_custom_tattoos', b'new')):
            self.assertNotEqual(appearance.fingerprint(dict(fields, **{name: appearance.encode(value)}))['appearance_sha256'], initial['appearance_sha256'])
        permuted = dict(fields, __outfits__=appearance.encode(('protobuf', outfit(9, 2) + outfit(0, 1))))
        self.assertEqual(appearance.fingerprint(permuted), initial)


class HumanWerewolfTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.human = Obj(id=1, physique='Human', skin_tone=123, skin_tone_val_shift=0.2, blob=outfit(0, 10))
        self.wolf = Obj(id=2, physique='Wolf', skin_tone=456, skin_tone_val_shift=0.4, blob=outfit(0, 20))
        self.sim = Obj(id=3, occult_types=33, current_occult_types=32, physique='Wolf', skin_tone=456,
                       skin_tone_val_shift=0.4, blob=outfit(0, 20), fury=75, perks=(7, 9))
        self.sim.occult_tracker = Obj(get_occult_sim_info=lambda kind: {1: self.human, 32: self.wolf}.get(kind))
        def restore(target, fields):
            for name, value in fields.items():
                if name == '__outfits__':
                    target.blob = value[1]
                else:
                    setattr(target, name, value)
        self.backend = Obj(_data_directory=lambda: self.directory.name, OccultType=Obj(HUMAN=1),
            _occult_by_name=lambda _: 32, _has_occult=lambda *_: True,
            _get_current_flags=lambda sim: sim.current_occult_types, _v8_read_outfit_blob=lambda sim: sim.blob,
            _restore_siminfo_payload=restore,
            services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 99)))

    def test_enable_active_form_restores_original_and_preserves_gameplay(self):
        before = appearance.evidence(self.backend, self.wolf)
        result = human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_on')
        self.assertTrue(result['enabled'])
        self.assertEqual(self.sim.current_occult_types, 32)
        self.assertEqual((self.sim.fury, self.sim.perks, self.sim.occult_types), (75, (7, 9), 33))
        self.assertEqual(appearance.evidence(self.backend, self.wolf), appearance.evidence(self.backend, self.human))
        result = human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_off')
        self.assertFalse(result['enabled'])
        self.assertEqual(appearance.evidence(self.backend, self.wolf), before)
        self.assertEqual(self.sim.physique, 'Wolf')
        self.assertIn('99:3', human_werewolf.load(human_werewolf.storage(self.backend))['retired'])

    def test_later_cas_edit_is_never_overwritten_by_reenable_or_disable(self):
        human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_on')
        self.wolf.skin_tone_val_shift = 0.7
        self.assertTrue(human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_on')['ok'])
        with self.assertRaisesRegex(ValueError, 'newer edits'):
            human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_off')
        self.assertEqual(self.wolf.skin_tone_val_shift, 0.7)

    def test_failed_readback_has_durable_recovery_and_restores_before_state(self):
        original = self.backend._restore_siminfo_payload
        calls = []
        def partial(target, fields):
            calls.append(target)
            if len(calls) <= 2:
                return True
            return original(target, fields)
        self.backend._restore_siminfo_payload = partial
        with self.assertRaisesRegex(ValueError, 'readback'):
            human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_on')
        self.assertEqual(self.wolf.physique, 'Wolf')
        data = human_werewolf.load(human_werewolf.storage(self.backend))
        self.assertEqual(data['records']['99:3']['state'], 'recovery-required')

    def test_accepted_form_bank_follows_explicit_human_werewolf_enable_and_disable(self):
        path, key = form_bank.context(self.backend, self.sim)
        original = appearance.packed(self.backend, self.wolf)
        form_bank.save(path, {'schema': 1, 'records': {key: {'bank': {'32': original}, 'history': []}}})
        human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_on')
        self.assertEqual(form_bank.load(path)['records'][key]['bank']['32'], appearance.packed(self.backend, self.human))
        human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_off')
        self.assertEqual(form_bank.load(path)['records'][key]['bank']['32'], original)

    def test_failed_form_bank_write_rolls_back_appearance_and_retains_original_receipt(self):
        with patch.object(form_bank, 'update', side_effect=OSError('storage full')):
            with self.assertRaisesRegex(OSError, 'storage full'):
                human_werewolf.dispatch(self.backend, self.sim, 'werewolf_human_on')
        self.assertEqual((self.wolf.physique, self.sim.physique), ('Wolf', 'Wolf'))
        self.assertEqual((self.sim.fury, self.sim.perks, self.sim.current_occult_types), (75, (7, 9), 32))
        self.assertEqual(human_werewolf.load(human_werewolf.storage(self.backend))['records']['99:3']['state'], 'recovery-required')
