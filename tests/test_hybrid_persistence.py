from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.hybrid_persistence import save_with_retention, load_with_retention
from apex_core import form_appearance
from test_outfit_snapshot import outfit


class Record:
    def __init__(self, kind=0, raw=b''):
        self.occult_type, self.raw = kind, raw
    def CopyFrom(self, other):
        self.occult_type, self.raw = other.occult_type, other.raw


class Records(list):
    def add(self):
        record = Record()
        self.append(record)
        return record


class PersistencePortTests(unittest.TestCase):
    def tracker(self):
        sim = Obj(occult_types=1|4|128, current_occult_types=1)
        return Obj(sim_info=sim, _sim_info=sim, _occult_form_available=False, OCCULT_DATA={4: object()})

    def test_save_exception_restores_every_temporary_flag(self):
        tracker = self.tracker()
        utils = Obj(get_occult_types_for_save=lambda item: 5,
                    recalc_occult_form_availability=lambda item, saving: setattr(item, '_occult_form_available', True))
        def failing(item):
            raise RuntimeError('disk save failed')
        with self.assertRaises(RuntimeError):
            save_with_retention(failing, tracker, utils)
        self.assertEqual(tracker.sim_info.occult_types, 133)
        self.assertFalse(tracker._occult_form_available)

    def test_unknown_saved_record_and_membership_are_retained(self):
        tracker = self.tracker()
        tracker._apex_unresolved_occult_records = (Record(128, b'unknown-form-with-CC'),)
        utils = Obj(get_occult_types_for_save=lambda item: 5, recalc_occult_form_availability=lambda *a, **kw: None)
        result = save_with_retention(lambda item: Obj(occult_types=5, occult_sim_infos=Records()), tracker, utils)
        self.assertEqual(result.occult_types, 133)
        self.assertEqual(result.occult_sim_infos[0].raw, b'unknown-form-with-CC')

    def test_current_unknown_record_is_never_overwritten_by_retained_copy(self):
        tracker = self.tracker()
        tracker._apex_unresolved_occult_records = (Record(128, b'older'),)
        utils = Obj(get_occult_types_for_save=lambda item: 5, recalc_occult_form_availability=lambda *a, **kw: None)
        result = save_with_retention(lambda item: Obj(occult_types=133, occult_sim_infos=Records([Record(128, b'new intentional state')])), tracker, utils)
        self.assertEqual(len(result.occult_sim_infos), 1)
        self.assertEqual(result.occult_sim_infos[0].raw, b'new intentional state')

    def test_load_retains_unrecognized_record_without_form_generation(self):
        class Enum:
            HUMAN = 1
            def __iter__(self):
                return iter((1, 4, 128))
        tracker = self.tracker()
        tracker._generate_sim_info = Mock(side_effect=AssertionError('unexpected generation'))
        tracker.has_occult_type = lambda value: False
        data = Obj(occult_types=133, current_occult_types=1, pending_occult_type=128,
                   occult_form_available=True, occult_sim_infos=[Record(128, b'opaque-form')])
        cache = Obj(OccultDataCache=Obj(process_custom_occults=lambda: None))
        result = load_with_retention(lambda *a: 'original-return', tracker, data, cache, None, Enum(), None)
        self.assertEqual(result, 'original-return')
        self.assertEqual(tracker._sim_info.occult_types, 133)
        self.assertEqual(tracker._apex_unresolved_occult_records[0].raw, b'opaque-form')
        self.assertEqual(tracker._pending_occult_type, 128)


class AppearanceSerializationTests(unittest.TestCase):
    def setUp(self):
        self.stored = Obj(id=1, physique='stored independent', genetic_data=b'\x0a\x03old',
                          blob=outfit(0, 11) + outfit(7, 12), gameplay_progress=45)
        self.live = Obj(id=2, physique='live independent', genetic_data=b'\x0a\x04live',
                        blob=outfit(0, 13), occult_types=5, current_occult_types=1, gameplay_progress=99)
        self.tracker = Obj(sim_info=self.live, _sim_info=self.live, _sim_info_map={1: self.stored},
                           _occult_form_available=False, OCCULT_DATA={4: object()})
        def restore(owner, values):
            for name, value in values.items():
                if name == '__outfits__': owner.blob = value[1]
                else: setattr(owner, name, value)
        self.backend = Obj(_v8_read_outfit_blob=lambda owner: owner.blob, _restore_siminfo_payload=restore)
        self.utils = Obj(get_occult_types_for_save=lambda owner: 5,
                         recalc_occult_form_availability=lambda *a, **k: None)
        self.enterContext(patch('apex_core.hybrid_persistence._appearance_backend', return_value=self.backend))

    def record(self):
        class Message:
            def __init__(self, raw): self.raw, self.clears = raw, 0
            def Clear(self): self.raw = b''; self.clears += 1
            def MergeFromString(self, raw): self.raw += raw
            def SerializeToString(self): return self.raw
        return Obj(occult_type=1, future_unknown=b'opaque future data', gameplay_progress=123,
                   physique='native overwritten', genetic_data=Message(b'\x0a\x05extra'),
                   outfits=Message(outfit(0, 77)), DESCRIPTOR=Obj(fields_by_name={
                       'physique': Obj(label=1, type=9), 'genetic_data': Obj(label=1, type=11),
                       'outfits': Obj(label=1, type=11)}))

    def mutate(self):
        for owner in (self.stored, self.live):
            owner.physique = 'native shared rewrite'; owner.blob = outfit(0, 99)

    def test_native_hidden_clothing_rewrite_is_replaced_in_output_and_owners_restored_separately(self):
        expected_stored = form_appearance.packed(self.backend, self.stored)
        expected_live = form_appearance.packed(self.backend, self.live)
        record = self.record()
        def original(_tracker):
            self.mutate()
            return Obj(occult_types=5, occult_sim_infos=Records([record]))
        observed = save_with_retention(original, self.tracker, self.utils)
        self.assertIs(observed.occult_sim_infos[0], record)
        self.assertEqual(record.physique, 'stored independent')
        self.assertEqual(record.outfits.raw, outfit(0, 11) + outfit(7, 12))
        self.assertEqual(record.genetic_data.raw, b'\x0a\x03old')
        self.assertEqual(record.genetic_data.clears, 1)
        self.assertEqual(record.future_unknown, b'opaque future data')
        self.assertEqual(record.gameplay_progress, 123)
        self.assertEqual(form_appearance.packed(self.backend, self.stored), expected_stored)
        self.assertEqual(form_appearance.packed(self.backend, self.live), expected_live)
        self.assertEqual((self.stored.id, self.stored.gameplay_progress, self.live.id, self.live.gameplay_progress), (1, 45, 2, 99))

    def test_original_serializer_failure_survives_while_appearance_rollback_failure_is_retained(self):
        def original(_tracker):
            self.mutate()
            raise RuntimeError('original serializer failure')
        self.backend._restore_siminfo_payload = Mock(side_effect=ValueError('appearance write failed'))
        with self.assertRaisesRegex(RuntimeError, 'original serializer failure'):
            save_with_retention(original, self.tracker, self.utils)
        failure = self.tracker._apex_serialization_appearance_failure
        self.assertFalse(failure['ok'])
        self.assertEqual(failure['serializer_error'], 'original serializer failure')
        self.assertIn('preservation readback failed', failure['appearance_retention_error'])
        self.assertEqual([row['restore_error'] for row in failure['owners']],
                         ['appearance write failed', 'appearance write failed'])
        self.assertEqual(self.backend._restore_siminfo_payload.call_count, 2)
        self.assertEqual(self.live.occult_types, 5)
        self.assertFalse(self.tracker._occult_form_available)

    def test_one_failed_owner_does_not_prevent_remaining_owner_restoration(self):
        expected_live = form_appearance.packed(self.backend, self.live)
        restore = self.backend._restore_siminfo_payload
        def restore_independently(owner, values):
            if owner is self.stored:
                raise ValueError('first owner failed')
            restore(owner, values)
        self.backend._restore_siminfo_payload = Mock(side_effect=restore_independently)
        def original(_tracker):
            self.mutate()
            return Obj(occult_types=5, occult_sim_infos=Records([self.record()]))
        with self.assertRaisesRegex(ValueError, 'preservation readback failed'):
            save_with_retention(original, self.tracker, self.utils)
        self.assertEqual(form_appearance.packed(self.backend, self.live), expected_live)
        self.assertEqual(self.backend._restore_siminfo_payload.call_count, 2)
        self.assertEqual(len(self.tracker._apex_serialization_appearance_failure['owners']), 1)

    def test_native_bytes_outfits_receive_raw_protobuf_without_tuple_or_identity_replacement(self):
        record = self.record()
        record.DESCRIPTOR.fields_by_name['outfits'].type = 12
        record.outfits = b'native rewritten bytes'
        record.DESCRIPTOR.fields_by_name['facial_attributes'] = Obj(label=1, type=12)
        record.facial_attributes = b'native rewritten face'
        self.stored.facial_attributes = b'original opaque face'
        save_with_retention(lambda tracker: Obj(occult_types=5, occult_sim_infos=Records([record])), self.tracker, self.utils)
        self.assertEqual(record.outfits, outfit(0, 11) + outfit(7, 12))
        self.assertIsInstance(record.outfits, bytes)
        self.assertEqual(record.facial_attributes, b'original opaque face')
        self.assertEqual(record.future_unknown, b'opaque future data')
        self.assertEqual(record.gameplay_progress, 123)

    def test_failed_restore_cannot_return_successful_serialized_data(self):
        def original(_tracker):
            self.mutate()
            return Obj(occult_types=5, occult_sim_infos=Records([self.record()]))
        self.backend._restore_siminfo_payload = Mock(return_value=False)
        with self.assertRaisesRegex(ValueError, 'preservation readback failed'):
            save_with_retention(original, self.tracker, self.utils)

    def test_duplicate_serialized_form_ids_refuse_without_guessing_and_still_restore_native_owner(self):
        expected = form_appearance.packed(self.backend, self.stored)
        def original(_tracker):
            self.mutate()
            return Obj(occult_types=5, occult_sim_infos=Records([self.record(), self.record()]))
        with self.assertRaisesRegex(ValueError, 'Duplicate serialized'):
            save_with_retention(original, self.tracker, self.utils)
        self.assertEqual(form_appearance.packed(self.backend, self.stored), expected)
