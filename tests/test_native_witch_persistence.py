"""Real protobuf wire fixtures and native owner fakes; no game/profile access."""
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_appearance, hybrid_persistence as persistence
from test_outfit_snapshot import outfit


def native_messages():
    # Numbers/types are the inspected native SimObjectAttributes/Outfits
    # descriptors; unneeded nested fields remain wire-preserved unknowns.
    file = descriptor_pb2.FileDescriptorProto(name='witch_native_fixture.proto',
                                            package='EA.Sims4.Persistence', syntax='proto2')
    def message(name, fields):
        item = file.message_type.add(name=name)
        for name, number, kind, label, type_name in fields:
            field = item.field.add(name=name, number=number, type=kind, label=label)
            if type_name:
                field.type_name = '.EA.Sims4.Persistence.' + type_name
    message('OutfitData', [('outfit_id', 1, 4, 2, ''), ('category', 2, 13, 1, '')])
    message('OutfitList', [('outfits', 1, 11, 3, 'OutfitData')])
    message('GeneticData', [('sculpts_and_mods_attr', 1, 12, 1, ''), ('physique', 2, 9, 1, '')])
    message('SimPartCustomTattooData', [('body_type', 1, 13, 2, ''), ('texture_id', 2, 4, 2, '')])
    message('OccultSimData', [('occult_type', 1, 13, 1, ''), ('physique', 11, 9, 1, ''),
        ('facial_attributes', 12, 12, 1, ''), ('voice_pitch', 13, 2, 1, ''),
        ('voice_actor', 14, 13, 1, ''), ('voice_effect', 15, 4, 1, ''),
        ('skin_tone', 16, 4, 1, ''), ('genetic_data', 17, 11, 1, 'GeneticData'),
        ('flags', 18, 13, 1, ''), ('outfits', 21, 11, 1, 'OutfitList'),
        ('skin_tone_val_shift', 22, 2, 1, ''),
        ('parts_custom_tattoos', 23, 11, 3, 'SimPartCustomTattooData')])
    message('PersistableOccultTracker', [('occult_types', 1, 13, 1, ''),
        ('current_occult_types', 2, 13, 1, ''), ('occult_sim_infos', 3, 11, 3, 'OccultSimData'),
        ('pending_occult_type', 4, 13, 1, ''), ('occult_form_available', 5, 8, 1, '')])
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file)
    return tuple(message_factory.GetMessageClass(pool.FindMessageTypeByName('EA.Sims4.Persistence.' + name))
                 for name in ('OccultSimData', 'PersistableOccultTracker'))


NativeRecord, NativeData = native_messages()


class Owner:
    def __init__(self, identity, label, outfit_id):
        self.id, self._base = identity, self
        self.physique, self.facial_attributes = label, label.encode('ascii')
        self.voice_pitch, self.voice_actor, self.voice_effect = .75, 3, 5
        self.skin_tone, self.skin_tone_val_shift = (1 << 63) + identity, -.25
        self.genetic_data = b'\x0a\x03' + b'abc'
        self.flags, self.blob = identity, outfit(0, outfit_id) + outfit(7, outfit_id + 1)
        self.parts_custom_tattoos = {73: (1 << 64) - 1}
        self.pelt_layers, self.custom_texture = b'not-an-occult-proto-field', 123
        self.gameplay_progress = 345
    def load_outfits(self, value):
        self.blob = value.SerializeToString()
    def save_outfits(self):
        return self.blob


class BaseWrapper:
    @staticmethod
    def copy_physical_attributes(destination, source):
        # Exact inspected destination/source direction and protobuf genetics
        # merge behavior. Outfits and repeated tattoos are separate native APIs.
        for name in persistence._CORE_FIELDS + ('flags',):
            value = getattr(source, name)
            if name == 'genetic_data':
                raw = value.SerializeToString() if hasattr(value, 'SerializeToString') else value
                target = destination.genetic_data
                if hasattr(target, 'MergeFromString'):
                    target.MergeFromString(raw)
                else:
                    destination.genetic_data = raw
            else:
                setattr(destination, name, value)


class Occults:
    HUMAN = 1
    def __iter__(self):
        return iter((1, 16, 128))


class WitchPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.live, self.witch = Owner(19, 'canonical main', 100), Owner(29, 'independent Witch', 200)
        self.live.occult_types, self.live.current_occult_types = 1 | 16 | 128, 1
        self.tracker = Obj(sim_info=self.live, _sim_info=self.live, _sim_info_map={16: self.witch},
                           OCCULT_DATA={16: object()}, _occult_form_available=False)
        self.tracker.has_occult_type = lambda kind: bool(self.live.occult_types & kind)
        self.tracker._generate_sim_info = Mock(side_effect=self.generate)
        def restore(owner, fields):
            for name, value in fields.items():
                if name == '__outfits__': owner.blob = value[1]
                elif isinstance(value, tuple) and value[0] == 'protobuf': setattr(owner, name, value[1])
                else: setattr(owner, name, value)
        self.backend = Obj(_v8_read_outfit_blob=lambda owner: owner.blob, _restore_siminfo_payload=restore)
        self.cache = Obj(OccultDataCache=Obj(process_custom_occults=lambda: None))
        self.utils = Obj(get_occult_types_for_save=lambda tracker: 17,
                         recalc_occult_form_availability=lambda *args, **kw: None)
        self.enterContext(patch.object(persistence, '_appearance_backend', return_value=self.backend))
        self.base = self.enterContext(patch.object(persistence, '_native_base_wrapper', return_value=BaseWrapper))
        self.enterContext(patch('apex_core.form_bank_seal.note_loaded'))

    def generate(self, kind, generate_new):
        self.assertEqual((kind, generate_new), (16, False))
        owner = Owner(39, 'generated canonical defaults', 300)
        self.tracker._sim_info_map[kind] = owner
        return owner

    def record(self, owner=None):
        owner = owner or self.witch
        record = NativeRecord(occult_type=16)
        BaseWrapper.copy_physical_attributes(record, owner)
        record.outfits.MergeFromString(owner.blob)
        for body, texture in owner.parts_custom_tattoos.items():
            record.parts_custom_tattoos.add(body_type=body, texture_id=texture)
        # Future unknown top-level and tattoo-row data must survive cloning.
        record.MergeFromString(b'\xa2\x06\x03new')
        record.parts_custom_tattoos[0].MergeFromString(b'\x98\x06\x07')
        return record

    def data(self, record=None, current=1):
        data = NativeData(occult_types=145, current_occult_types=current,
                          pending_occult_type=128, occult_form_available=True)
        if record is not None:
            data.occult_sim_infos.add().CopyFrom(record)
        return data

    def save(self, data=None, original=None):
        return persistence.save_with_retention(original or (lambda tracker: data or self.data()),
                                               self.tracker, self.utils)

    def load(self, data, original=None):
        def native(tracker, value):
            for record in value.occult_sim_infos:
                if record.occult_type != 16 or 16 not in tracker.OCCULT_DATA:
                    continue
                if 16 not in tracker._sim_info_map:
                    tracker._generate_sim_info(16, generate_new=False)
                if value.current_occult_types == 16:
                    # Actual native active branch mutates proto <- main Sim.
                    BaseWrapper.copy_physical_attributes(record, self.live)
            return 'unchanged native return'
        return persistence.load_with_retention(original or native, self.tracker, data, self.cache,
                                              None, Occults(), BaseWrapper)

    def core(self, owner):
        values = form_appearance.packed(self.backend, owner)
        return {name: values[name] for name in persistence._CORE_FIELDS +
                ('__outfits__', 'parts_custom_tattoos')}

    def test_forward_save_appends_existing_tuned_witch_and_real_wire_roundtrips(self):
        expected, active = self.core(self.witch), form_appearance.packed(self.backend, self.live)
        saved = self.save()
        self.assertEqual([record.occult_type for record in saved.occult_sim_infos], [16])
        record = saved.occult_sim_infos[0]
        self.assertEqual((record.flags, record.physique), (29, 'independent Witch'))
        self.assertEqual(record.outfits.SerializeToString(), self.witch.blob)
        self.assertEqual(record.genetic_data.SerializeToString(), self.witch.genetic_data)
        self.assertEqual(saved.occult_types, 145)
        reopened = NativeData.FromString(saved.SerializeToString())
        self.tracker._sim_info_map.clear()
        self.assertEqual(self.load(reopened), 'unchanged native return')
        self.assertEqual(self.core(self.tracker._sim_info_map[16]), expected)
        self.assertEqual(form_appearance.packed(self.backend, self.live), active)

    def test_native_outfit_rebuild_cannot_replace_retained_witch_genetics(self):
        record = self.record()
        expected = self.core(self.witch)
        native_load = self.witch.load_outfits
        def rebuilding_outfits(outfits):
            native_load(outfits)
            self.witch.genetic_data = b'\x0a\x03new'
            self.witch.physique = 'native wardrobe rebuild'
        self.witch.load_outfits = rebuilding_outfits
        self.assertEqual(self.load(self.data(record)), 'unchanged native return')
        self.assertEqual(self.core(self.witch), expected)

    def test_readback_failure_reports_exact_fields_without_weakening_validation(self):
        record = self.record()
        self.witch.genetic_data = b'\x0a\x03new'
        with self.assertRaises(ValueError) as raised:
            persistence._stored_core(self.backend, self.witch, record)
        self.assertEqual(raised.exception.appearance_diagnostics['changed_fields'], ['genetic_data'])
        self.assertIn('genetic_data', str(raised.exception))

    def test_native_merge_cannot_retain_stale_unknown_genetics_in_message_owner(self):
        record = self.record()
        record.genetic_data.MergeFromString(b'\xa2\x06\x03new')
        target = NativeRecord().genetic_data
        target.MergeFromString(b'\x0a\x03old\xa2\x06\x05stale')
        self.witch.genetic_data = target
        self.assertEqual(self.load(self.data(record)), 'unchanged native return')
        self.assertIs(self.witch.genetic_data,target)
        self.assertEqual(target.SerializeToString(), record.genetic_data.SerializeToString())

    def test_native_known_genetic_wire_order_preserves_every_field_and_unknown(self):
        record = self.record()
        record.genetic_data.physique = 'shape'
        record.genetic_data.MergeFromString(b'\xa2\x06\x03new')
        # Native C++ emits known field 2 before field 1. Protobuf presence,
        # complete values and the future unknown field are identical.
        self.witch.genetic_data = b'\x12\x05shape\x0a\x03abc\xa2\x06\x03new'
        projection = persistence._stored_core(self.backend, self.witch, record)
        self.assertTrue(projection['complete_message_equal'])
        self.assertFalse(projection['native_wire_equal'])
        self.assertEqual(self.witch.genetic_data, b'\x12\x05shape\x0a\x03abc\xa2\x06\x03new')
        # Dropping the future field still refuses. No known-field-only filter.
        self.witch.genetic_data = b'\x12\x05shape\x0a\x03abc'
        with self.assertRaises(ValueError) as raised:
            persistence._stored_core(self.backend, self.witch, record)
        self.assertFalse(raised.exception.appearance_diagnostics['genetics_projection']['complete_message_equal'])

    def test_native_genetic_presence_difference_is_still_rejected(self):
        record = self.record()
        self.assertFalse(record.genetic_data.HasField('physique'))
        self.witch.genetic_data += b'\x12\x00'
        with self.assertRaises(ValueError):
            persistence._stored_core(self.backend, self.witch, record)

    def test_custom_witch_projection_without_human_bit_orders_real_save_and_restores_all_owners(self):
        # Installed custom-Witch utility can leave flags16 unchanged while
        # Human is active. The original EA serializer copies that mask and
        # omits Witch, so the adapter must order its appended owner without
        # adding a Human membership bit or discarding any secondary record.
        self.live.occult_types = 16
        self.utils.get_occult_types_for_save = lambda tracker: tracker.sim_info.occult_types
        owners = {kind: Owner(100 + kind, 'independent {}'.format(kind), 1000 + kind)
                  for kind in (1, 2, 4, 8, 32, 64)}
        owners[16] = self.witch
        self.tracker._sim_info_map = owners
        self.tracker.OCCULT_DATA = {kind: object() for kind in (2, 4, 8, 16, 32, 64)}
        before = {kind: form_appearance.packed(self.backend, owner) for kind, owner in owners.items()}
        active = form_appearance.packed(self.backend, self.live)
        cached_witch = self.record()
        self.tracker._apex_native_witch_record = (self.witch, cached_witch)
        expected = {}
        calls = []

        def complete_record(kind, owner):
            record = NativeRecord(occult_type=kind)
            BaseWrapper.copy_physical_attributes(record, owner)
            record.outfits.MergeFromString(owner.blob)
            for body, texture in owner.parts_custom_tattoos.items():
                row = record.parts_custom_tattoos.add(body_type=body, texture_id=texture)
                row.MergeFromString(b'\x98\x06\x07')
            record.MergeFromString(b'\xa2\x06\x03new')
            return record

        def native(tracker):
            calls.append(tracker.sim_info.occult_types)
            data = NativeData(occult_types=tracker.sim_info.occult_types,
                              current_occult_types=tracker.sim_info.current_occult_types,
                              pending_occult_type=32, occult_form_available=True)
            data.MergeFromString(b'\xaa\x06\x04root')
            for kind, owner in tracker._sim_info_map.items():
                expected[kind] = complete_record(kind, owner).SerializeToString()
                if kind == 16:
                    continue  # Native save explicitly omits this kind.
                owner.physique, owner.blob = 'native shared rewrite', outfit(0, 9000 + kind)
                data.occult_sim_infos.add().CopyFrom(complete_record(kind, owner))
            self.live.physique, self.live.blob = 'native active rewrite', outfit(0, 9999)
            return data

        saved = self.save(original=native)
        self.assertEqual(calls, [16])
        self.assertEqual(saved.occult_types, 16)
        self.assertEqual((saved.current_occult_types, saved.pending_occult_type,
                          saved.occult_form_available), (1, 32, True))
        self.assertEqual([row.occult_type for row in saved.occult_sim_infos], [1, 16, 2, 4, 8, 32, 64])
        self.assertEqual({row.occult_type: row.SerializeToString() for row in saved.occult_sim_infos}, expected)
        self.assertIn(b'\xaa\x06\x04root', saved.SerializeToString())
        for row in saved.occult_sim_infos:
            self.assertIn(b'\xa2\x06\x03new', row.SerializeToString())
            self.assertIn(b'\x98\x06\x07', row.parts_custom_tattoos[0].SerializeToString())
        self.assertEqual({kind: form_appearance.packed(self.backend, owner)
                          for kind, owner in owners.items()}, before)
        self.assertEqual(form_appearance.packed(self.backend, self.live), active)
        self.assertEqual((self.live.occult_types, self.tracker._occult_form_available), (16, False))
        self.tracker._generate_sim_info.assert_not_called()
        diagnostic = self.tracker._apex_native_pair_order
        self.assertEqual((diagnostic['projected_mask'], diagnostic['alternate']), (16, 16))
        self.assertEqual(diagnostic['before_order'], [1, 2, 4, 8, 32, 64, 16])
        self.assertEqual(diagnostic['after_order'], [1, 16, 2, 4, 8, 32, 64])
        self.assertTrue(diagnostic['record_bytes_unchanged'])

    def test_current_witch_restores_saved_stored_clone_and_preserves_distinct_active(self):
        self.live.current_occult_types = 16
        original = self.record()
        data = self.data(original, current=16)
        expected = self.core(self.witch)
        active = form_appearance.packed(self.backend, self.live)
        self.witch.physique, self.witch.blob = 'new native defaults', outfit(0, 400)
        self.assertEqual(self.load(data), 'unchanged native return')
        self.assertEqual(data.occult_sim_infos[0].physique, self.live.physique)
        self.assertEqual(self.core(self.witch), expected)
        self.assertEqual(form_appearance.packed(self.backend, self.live), active)
        self.tracker._generate_sim_info.assert_not_called()
        self.assertEqual(self.tracker._apex_native_witch_record[1].SerializeToString(), original.SerializeToString())

    def test_cached_native_record_preserves_unknown_top_level_and_tattoo_row_fields(self):
        original = self.record()
        self.load(self.data(original))
        self.witch.parts_custom_tattoos[73] = 777
        saved = self.save().occult_sim_infos[0]
        self.assertIn(b'\xa2\x06\x03new', saved.SerializeToString())
        self.assertIn(b'\x98\x06\x07', saved.parts_custom_tattoos[0].SerializeToString())
        self.assertEqual(saved.parts_custom_tattoos[0].texture_id, 777)

    def test_already_present_witch_is_updated_without_duplicate_or_native_builder(self):
        data = self.data(self.record())
        data.occult_sim_infos[0].physique = 'native rewrite'
        saved = self.save(data)
        self.assertEqual(len(saved.occult_sim_infos), 1)
        self.assertEqual(saved.occult_sim_infos[0].physique, self.witch.physique)
        self.base.assert_not_called()

    def test_no_tuning_or_no_captured_wrapper_never_fabricates_a_save_record(self):
        self.tracker.OCCULT_DATA.clear()
        self.assertEqual(len(self.save().occult_sim_infos), 0)
        self.tracker._sim_info_map.clear()
        self.tracker.OCCULT_DATA[16] = object()
        self.assertEqual(len(self.save().occult_sim_infos), 0)
        self.base.assert_not_called()
        self.tracker._generate_sim_info.assert_not_called()

    def test_old_native_save_without_witch_does_not_invent_or_restore_history(self):
        self.tracker._sim_info_map.clear()
        self.load(self.data())
        self.assertEqual(self.tracker._sim_info_map, {})
        self.tracker._generate_sim_info.assert_not_called()

    def test_unsupported_saved_witch_is_retained_raw_without_generation(self):
        original = self.record()
        self.tracker.OCCULT_DATA.clear()
        self.tracker._sim_info_map.clear()
        self.load(self.data(original))
        self.assertEqual(self.tracker._apex_unresolved_occult_records[0].SerializeToString(), original.SerializeToString())
        self.tracker._generate_sim_info.assert_not_called()

    def test_identical_complete_native_records_load_and_save_once_without_rewriting_input(self):
        data = self.data(self.record())
        data.occult_sim_infos.add().CopyFrom(data.occult_sim_infos[0])
        data.MergeFromString(b'\xa2\x06\x04root')
        before = data.SerializeToString()
        seen = []
        def native(tracker, value):
            seen.append(value)
            self.assertIsNot(value, data)
            self.assertEqual(len(value.occult_sim_infos), 1)
            self.assertEqual(value.occult_sim_infos[0].SerializeToString(), self.record().SerializeToString())
            return 'native loaded'
        self.assertEqual(self.load(data, native), 'native loaded')
        self.assertEqual(data.SerializeToString(), before)
        self.assertIn(b'\xa2\x06\x04root', seen[0].SerializeToString())
        self.assertEqual([row.SerializeToString() for row in self.tracker._apex_identical_duplicate_occult_records],
                         [row.SerializeToString() for row in data.occult_sim_infos])
        saved = self.save(data)
        self.assertIsNot(saved, data)
        self.assertEqual(len(saved.occult_sim_infos), 1)
        self.assertEqual(data.SerializeToString(), before)
        self.assertIn(b'\xa2\x06\x04root', saved.SerializeToString())
        self.assertIn(b'\xa2\x06\x03new', saved.occult_sim_infos[0].SerializeToString())
        self.assertIn(b'\x98\x06\x07', saved.occult_sim_infos[0].SerializeToString())
        self.assertTrue(self.tracker._apex_occult_duplicate_diagnostics['exact_duplicate_verified'])

    def test_conflicting_outfits_refuse_before_load_and_retain_every_complete_source(self):
        data = self.data(self.record())
        duplicate = data.occult_sim_infos.add()
        duplicate.CopyFrom(data.occult_sim_infos[0])
        duplicate.outfits.Clear()
        duplicate.outfits.outfits.add(outfit_id=0, category=0)
        unrelated = data.occult_sim_infos.add(occult_type=128)
        unrelated.MergeFromString(b'\xa2\x06\x04kept')
        before = data.SerializeToString()
        expected = [row.SerializeToString() for row in data.occult_sim_infos]
        original, cache = Mock(), self.cache.OccultDataCache.process_custom_occults
        self.cache.OccultDataCache.process_custom_occults = Mock()
        with self.assertRaisesRegex(ValueError, 'Duplicate saved'):
            self.load(data, original)
        original.assert_not_called()
        self.cache.OccultDataCache.process_custom_occults.assert_not_called()
        self.tracker._generate_sim_info.assert_not_called()
        self.assertEqual(data.SerializeToString(), before)
        self.assertEqual([row.SerializeToString() for row in self.tracker._apex_conflicting_occult_records], expected)
        failure = self.tracker._apex_occult_record_failure
        self.assertEqual((failure['phase'], failure['occult_type'], failure['first_index'], failure['duplicate_index']),
                         ('load', 16, 0, 1))
        self.assertTrue(failure['complete_sources_retained'])
        self.assertFalse(failure['conflict_resolved'])
        self.assertNotEqual(failure['records'][0]['native_sha256'], failure['records'][1]['native_sha256'])
        self.assertEqual(self.live.occult_types, 145)
        self.cache.OccultDataCache.process_custom_occults = cache
        with self.assertRaisesRegex(ValueError, 'Duplicate serialized'):
            self.save(data)
        self.assertEqual(data.SerializeToString(), before)
        self.assertEqual([row.SerializeToString() for row in self.tracker._apex_conflicting_occult_records], expected)

    def test_unknown_field_only_duplicate_conflict_cannot_be_folded_by_appearance_equality(self):
        data = self.data(self.record())
        duplicate = data.occult_sim_infos.add()
        duplicate.CopyFrom(data.occult_sim_infos[0])
        duplicate.MergeFromString(b'\xaa\x06\x06future')
        original = Mock()
        with self.assertRaisesRegex(ValueError, 'Duplicate saved'):
            self.load(data, original)
        original.assert_not_called()
        retained = self.tracker._apex_conflicting_occult_records
        self.assertIn(b'\xaa\x06\x06future', retained[1].SerializeToString())
        self.assertNotIn(b'\xaa\x06\x06future', retained[0].SerializeToString())

    def test_missing_identical_unresolved_records_emit_one_complete_unknown_owner(self):
        record = NativeRecord(occult_type=128)
        record.MergeFromString(b'\xa2\x06\x04kept')
        copy = NativeRecord(); copy.CopyFrom(record)
        self.tracker._apex_unresolved_occult_records = (record, copy)
        saved = self.save()
        unknown = [row for row in saved.occult_sim_infos if row.occult_type == 128]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0].SerializeToString(), record.SerializeToString())
        self.assertEqual(len(self.tracker._apex_unresolved_occult_records), 2)

    def test_identical_unknown_load_then_save_preserves_unique_unrelated_native_records(self):
        unknown = NativeRecord(occult_type=128)
        unknown.MergeFromString(b'\xa2\x06\x04kept')
        incoming = self.data(unknown)
        incoming.occult_sim_infos.add().CopyFrom(unknown)
        before = incoming.SerializeToString()
        self.load(incoming, original=lambda tracker, data: None)
        self.tracker._generate_sim_info.assert_not_called()
        self.assertEqual(len(self.tracker._apex_unresolved_occult_records), 1)
        unrelated = NativeRecord(occult_type=4)
        unrelated.MergeFromString(b'\xaa\x06\x06future')
        native = self.data(unrelated)
        saved = self.save(native)
        rows = {row.occult_type: row.SerializeToString() for row in saved.occult_sim_infos}
        self.assertEqual(rows[128], unknown.SerializeToString())
        self.assertEqual(rows[4], unrelated.SerializeToString())
        self.assertEqual(incoming.SerializeToString(), before)
        self.assertEqual(len(rows), len(saved.occult_sim_infos))

    def test_missing_conflicting_unresolved_records_refuse_before_any_output_record_is_appended(self):
        first, second = NativeRecord(occult_type=128), NativeRecord(occult_type=128)
        first.MergeFromString(b'\xa2\x06\x05first')
        second.MergeFromString(b'\xa2\x06\x06second')
        self.tracker._apex_unresolved_occult_records = (first, second)
        data = self.data()
        before = data.SerializeToString()
        with self.assertRaisesRegex(ValueError, 'Duplicate serialized'):
            self.save(data)
        self.assertEqual(data.SerializeToString(), before)
        self.base.assert_not_called()
        self.assertEqual(self.tracker._apex_occult_record_failure['phase'], 'save-unresolved')
        self.assertEqual([row.SerializeToString() for row in self.tracker._apex_conflicting_occult_records],
                         [first.SerializeToString(), second.SerializeToString()])

    def test_original_load_exception_never_triggers_witch_post_writes(self):
        original = Mock(side_effect=RuntimeError('native load failed'))
        before = form_appearance.packed(self.backend, self.witch)
        with self.assertRaisesRegex(RuntimeError, 'native load failed'):
            self.load(self.data(self.record()), original)
        self.assertEqual(form_appearance.packed(self.backend, self.witch), before)
        self.tracker._generate_sim_info.assert_not_called()

    def test_original_save_exception_is_preserved_and_flags_are_restored(self):
        with self.assertRaisesRegex(RuntimeError, 'native save failed'):
            self.save(original=Mock(side_effect=RuntimeError('native save failed')))
        self.assertEqual((self.live.occult_types, self.tracker._occult_form_available), (145, False))
        self.base.assert_not_called()

    def test_owner_replacement_during_original_save_is_refused(self):
        def original(tracker):
            tracker._sim_info_map[16] = Owner(49, 'replacement', 500)
            return self.data()
        with self.assertRaisesRegex(ValueError, 'owner changed during serialization'):
            self.save(original=original)

    def test_native_save_builder_failure_cannot_return_a_partial_witch_record(self):
        self.base.return_value = Obj(copy_physical_attributes=Mock())
        before = form_appearance.packed(self.backend, self.witch)
        with self.assertRaisesRegex(ValueError, 'identity/flags failed readback'):
            self.save()
        self.assertEqual(form_appearance.packed(self.backend, self.witch), before)
        self.assertEqual(self.live.occult_types, 145)

    def test_load_readback_failure_restores_original_payload_and_keeps_active(self):
        data = self.data(self.record())
        self.witch.blob = outfit(0, 600)
        before = form_appearance.packed(self.backend, self.witch)
        active = form_appearance.packed(self.backend, self.live)
        self.witch.load_outfits = Mock()  # Native ignored the requested bytes.
        with self.assertRaisesRegex(ValueError, 'failed exact readback'):
            self.load(data)
        self.assertEqual(form_appearance.packed(self.backend, self.witch), before)
        self.assertEqual(form_appearance.packed(self.backend, self.live), active)
        self.assertTrue(self.tracker._apex_native_witch_appearance_failure['rollback_verified'])

    def test_failed_new_wrapper_readback_never_claims_full_owner_map_rollback(self):
        data = self.data(self.record())
        self.tracker._sim_info_map.clear()
        generate = self.tracker._generate_sim_info.side_effect
        def ignored(kind, generate_new):
            owner = generate(kind, generate_new)
            owner.load_outfits = Mock()
            return owner
        self.tracker._generate_sim_info.side_effect = ignored
        with self.assertRaisesRegex(ValueError, 'failed exact readback'):
            self.load(data, original=lambda tracker, value: None)
        failure = self.tracker._apex_native_witch_appearance_failure
        self.assertTrue(failure['created_wrapper'])
        self.assertTrue(failure['original_payloads_restored_verified'])
        self.assertFalse(failure['rollback_verified'])

    def test_malformed_saved_outfits_and_tattoos_refuse_before_post_creation(self):
        data = self.data(self.record())
        data.occult_sim_infos[0].outfits.Clear()
        self.tracker._sim_info_map.clear()
        with self.assertRaises(ValueError):
            self.load(data, original=lambda tracker, value: None)
        self.tracker._generate_sim_info.assert_not_called()
        data = self.data(self.record())
        data.occult_sim_infos[0].parts_custom_tattoos[0].ClearField('texture_id')
        with self.assertRaisesRegex(ValueError, 'incomplete or ambiguous'):
            self.load(data, original=lambda tracker, value: None)
        self.tracker._generate_sim_info.assert_not_called()

    def test_active_alias_and_changed_tracker_are_refused_without_stored_writes(self):
        data = self.data(self.record())
        self.tracker._sim_info_map[16] = self.live
        with self.assertRaisesRegex(ValueError, 'aliases the active Sim'):
            self.load(data)
        def original(tracker, value):
            tracker._sim_info_map = dict(tracker._sim_info_map)
        with self.assertRaisesRegex(ValueError, 'ownership changed'):
            self.load(data, original)

    def test_tattoo_mapping_is_exact_bounded_uint32_to_uint64_and_preserves_wire_unknowns(self):
        record = self.record()
        persistence._write_tattoos(record, {73: (1 << 64) - 1, 0: 0})
        self.assertEqual(persistence._read_tattoos(record), {73: (1 << 64) - 1, 0: 0})
        for value in ({True: 1}, {1: True}, {-1: 1}, {1 << 32: 1}, {1: 1 << 64}, [(73, 1)]):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'mapping contract'):
                persistence._write_tattoos(record, value)
        record.parts_custom_tattoos.add().CopyFrom(record.parts_custom_tattoos[0])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            persistence._write_tattoos(record, {})

    def test_similar_field_names_with_other_native_schema_are_refused(self):
        fields = dict(NativeRecord.DESCRIPTOR.fields_by_name)
        fields['flags'] = Obj(number=99, type=13, label=1)
        with self.assertRaisesRegex(ValueError, 'protobuf contract differs'):
            persistence._core_contract(Obj(DESCRIPTOR=Obj(fields_by_name=fields)))
        fields = dict(NativeRecord.DESCRIPTOR.fields_by_name)
        fields['parts_custom_tattoos'] = Obj(number=23, type=11, label=3,
            message_type=Obj(fields_by_name={'body_type': Obj(number=1, type=13, label=2),
                                             'texture_id': Obj(number=2, type=13, label=2)}))
        with self.assertRaisesRegex(ValueError, 'tattoo protobuf schema differs'):
            persistence._tattoo_field(Obj(DESCRIPTOR=Obj(fields_by_name=fields)))

    def test_absent_pelt_and_custom_texture_are_not_invented_as_native_fields(self):
        record = self.save().occult_sim_infos[0]
        self.assertNotIn('pelt_layers', record.DESCRIPTOR.fields_by_name)
        self.assertNotIn('custom_texture', record.DESCRIPTOR.fields_by_name)
        self.assertEqual((self.witch.pelt_layers, self.witch.custom_texture),
                         (b'not-an-occult-proto-field', 123))


if __name__ == '__main__':
    unittest.main()
