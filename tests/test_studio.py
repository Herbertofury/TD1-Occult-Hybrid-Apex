from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import studio
from casp_fixture import casp


class OutfitRecords(list):
    def add(self):
        class Record:
            def CopyFrom(self, other):
                import copy
                self.__dict__.update(copy.deepcopy(other.__dict__))
        record=Record();self.append(record);return record


class Message:
    @staticmethod
    def pack(rows):
        # A valid opaque protobuf field lets form-bank byte validation run
        # unchanged; this fixture supplies its own small outfit model.
        raw = json.dumps(rows, sort_keys=True).encode()
        length, count = bytearray(), len(raw)
        while count > 127:
            length.append((count & 127) | 128); count >>= 7
        length.append(count)
        return b'\x12' + bytes(length) + raw

    def __init__(self, raw):
        from apex_core.outfit_snapshot import field
        _, _, _, raw = field(raw, 0)
        self.outfits = OutfitRecords()
        for record in json.loads(raw):
            self.outfits.append(Obj(outfit_id=record['outfit_id'], category=record['category'],
                parts=Obj(ids=record['parts']), body_types_list=Obj(body_types=record['types']),
                part_shifts=Obj(color_shift=record['shifts']), object_ids=Obj(object_id=record['objects']),
                layer_ids=Obj(layer_id=record['layers'])))
    def SerializeToString(self):
        return self.pack([dict(outfit_id=item.outfit_id, category=item.category, parts=item.parts.ids,
            types=item.body_types_list.body_types, shifts=item.part_shifts.color_shift,
            objects=item.object_ids.object_id, layers=item.layer_ids.layer_id) for item in self.outfits])


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        rows = [dict(outfit_id=index+1, category=index, parts=[999, 888], types=[7, 2],
            shifts=[2**64-1 if index == 0 else 0, 19], objects=[3, 4], layers=[5, 6]) for index in range(2)]
        self.sim = Obj(id=1234, flags=32, physique='original shape', skin_tone=41, raw=Message.pack(rows), occult_tracker=Obj())
        self.backend = Obj(_get_sim_info_by_id=lambda value: self.sim, _v8_imports_ready=lambda: True,
            _studio_normalize_snapshot=lambda raw: raw, _studio_parse_snapshot=Message,
            _v8_read_outfit_blob=lambda sim: sim.raw, _v8_parse_outfits=lambda sim: Message(sim.raw),
            _sim_id=lambda sim: sim.id, _get_current_flags=lambda sim: sim.flags,
            _form_map=lambda tracker: {32: self.sim}, _coerce_flags=lambda value: value,
            _data_directory=lambda: self.temp.name, _v8_resolve_body_type=lambda value: (7, {}, 'runtime'),
            _resend_all_visuals=lambda sim: None,
            services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_buff=lambda: Obj(slot_id=42),
                get_save_slot_proto_guid=lambda: 9876)))
        def write(sim, raw):
            sim.raw = raw
            return True
        self.backend._v8_write_outfit_blob = write
        def restore(sim, fields):
            for name, value in fields.items():
                if name == '__outfits__': sim.raw = value[1]
                else: setattr(sim, name, value)
        self.backend._restore_siminfo_payload = restore
        import hashlib
        self.backend._studio_native_record = lambda sim: dict(native_sha256=hashlib.sha256(sim.raw).hexdigest(),
            native_base64=__import__('base64').b64encode(sim.raw).decode(), data={'fields': []}, field_schemas={})
        studio._COLOR_CLIPBOARD = None

    def request(self, action, value=None):
        return studio.dispatch(self.backend, action, self.sim.id, value)

    def stored_request(self, action, value=None, form=4):
        return self.request(action, json.dumps({'form': form, 'value': value}))

    def stored_form(self):
        self.vampire = Obj(id=5678, physique='Vampire face and body', skin_tone=900, raw=self.sim.raw)
        self.backend._form_map = lambda _: {32: self.sim, 4: self.vampire}
        self.backend._studio_casp_bytes = lambda _: casp(body=7)
        changed = Message(self.vampire.raw)
        changed.outfits[1].parts.ids[0] = 1200
        self.vampire.raw = changed.SerializeToString()
        return self.stored_request('studio_status')

    def stored_preview(self, status):
        return self.stored_request('studio_part_preview', json.dumps(dict(
            target='0:7:0', source='1:7:0', lane=status['history_lane'],
            appearance_sha256=status['appearance_sha256'])))

    def test_inactive_native_form_apply_undo_redo_keeps_active_appearance_and_gameplay(self):
        before = self.stored_form()
        active = (self.sim.raw, self.sim.physique, self.sim.skin_tone, self.sim.flags)
        self.sim.progression = 77
        original = self.vampire.raw
        preview = self.stored_preview(before)
        self.assertEqual(self.vampire.raw, original)
        self.stored_request('studio_apply', preview['preview_id'])
        changed = self.vampire.raw
        after = self.stored_request('studio_status')
        self.assertEqual(after['inspected_form_flags'], 4)
        self.assertEqual(after['current_form_flags'], 32)
        self.assertNotEqual(changed, original)
        self.stored_request('studio_apply', self.stored_request('studio_undo')['preview_id'])
        self.assertEqual(self.vampire.raw, original)
        self.stored_request('studio_apply', self.stored_request('studio_redo', after['history_cursor'])['preview_id'])
        self.assertEqual(self.vampire.raw, changed)
        self.assertEqual((self.sim.raw, self.sim.physique, self.sim.skin_tone, self.sim.flags), active)
        self.assertEqual(self.sim.progression, 77)

    def test_bank_only_form_retains_direct_edit_without_generating_or_activating_native_form(self):
        from apex_core import form_bank, form_appearance
        before = self.stored_form()
        form_bank.update(self.backend, self.sim, 4, form_appearance.packed(self.backend, self.vampire), create=True)
        self.backend._form_map = lambda _: {32: self.sim}
        active = self.sim.raw
        preview = self.stored_preview(before)
        self.stored_request('studio_apply', preview['preview_id'])
        after = self.stored_request('studio_status')
        self.assertNotEqual(after['appearance_sha256'], before['appearance_sha256'])
        self.assertEqual(self.sim.raw, active)
        self.assertEqual(self.sim.flags, 32)
        self.stored_request('studio_apply', self.stored_request('studio_undo')['preview_id'])
        self.assertEqual(self.stored_request('studio_status')['appearance_sha256'], before['appearance_sha256'])

    def test_inactive_preview_cannot_apply_to_active_or_absent_form(self):
        before = self.stored_form(); preview = self.stored_preview(before)
        active, stored = self.sim.raw, self.vampire.raw
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.request('studio_apply', preview['preview_id'])
        with self.assertRaisesRegex(ValueError, 'No existing appearance'):
            self.stored_request('studio_status', form=64)
        self.assertEqual((self.sim.raw, self.vampire.raw), (active, stored))

    def test_inactive_bank_failure_rolls_back_native_owner_and_active_state(self):
        from unittest.mock import patch
        before = self.stored_form(); preview = self.stored_preview(before)
        active, stored = self.sim.raw, self.vampire.raw
        with patch.object(studio.form_bank, 'update', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.stored_request('studio_apply', preview['preview_id'])
        self.assertEqual((self.sim.raw, self.vampire.raw), (active, stored))

    def test_skin_jewelry_and_future_runtime_categories_are_present_when_unequipped(self):
        self.backend._V8_CAS_BODYTYPE_DEFS = [dict(key='SKIN', value=20, label='Skin details', group='Skin details'),
                                             dict(key='RING', value=21, label='Ring', group='Jewelry')]
        self.backend._v8_resolve_body_type = lambda value: (20 if value == 'SKIN' else 21, {}, 'runtime')
        class Future(int):
            name = 'NEW_PATCH_EYEBROW_DETAIL'
        self.backend._V8_EA_BODYTYPE = [Future(900)]
        result = self.request('studio_status')
        self.assertEqual([row['body_type'] for row in result['category_catalog']], [20, 21, 900])
        self.assertEqual(result['category_catalog'][-1]['group'], 'Runtime discovered')

    def test_duplicate_numbered_outfit_preview_apply_and_undo_retains_source_and_other_fields(self):
        self.backend._studio_alloc_outfit_id=lambda:2**64-2
        before=self.request('studio_status');original=self.sim.raw
        value=json.dumps(dict(source=1,category=0,lane=before['history_lane'],appearance_sha256=before['appearance_sha256']))
        preview=self.request('studio_outfit_duplicate',value)
        self.assertEqual(preview['destination_ordinal'],1);self.assertEqual(self.sim.raw,original)
        self.request('studio_apply',preview['preview_id'])
        after=test_message=Message(self.sim.raw)
        self.assertEqual(len(after.outfits),3)
        self.assertEqual(after.outfits[-1].outfit_id,2**64-2)
        self.assertEqual(after.outfits[-1].category,0)
        self.assertEqual(after.outfits[-1].parts.ids,after.outfits[1].parts.ids)
        inventory=self.request('studio_status')['outfit_inventory']
        self.assertEqual([(o['category'],o['number']) for o in inventory],[(0,1),(1,1),(0,2)])
        self.assertEqual(self.sim.physique,'original shape')
        self.request('studio_apply',self.request('studio_undo')['preview_id']);self.assertEqual(self.sim.raw,original)

    def test_duplicate_rejects_unknown_category_duplicate_identity_and_sixth_number(self):
        self.backend._studio_alloc_outfit_id=lambda:1
        before=self.request('studio_status')
        value=dict(source=0,category=0,lane=before['history_lane'],appearance_sha256=before['appearance_sha256'])
        with self.assertRaisesRegex(ValueError,'duplicate/reserved'):self.request('studio_outfit_duplicate',json.dumps(value))
        value['category']=999
        with self.assertRaisesRegex(ValueError,'existing category'):self.request('studio_outfit_duplicate',json.dumps(value))
        message=Message(self.sim.raw)
        for index in range(4):
            clone=message.outfits.add();clone.CopyFrom(message.outfits[0]);clone.outfit_id=index+10
        self.sim.raw=message.SerializeToString();value.update(category=0,appearance_sha256=self.request('studio_status')['appearance_sha256'])
        with self.assertRaisesRegex(ValueError,'fewer than five'):self.request('studio_outfit_duplicate',json.dumps(value))

    def test_exact_color_preview_apply_and_undo_are_scoped_and_verified(self):
        before = self.sim.raw
        self.assertEqual(self.request('studio_color_copy', '0:HAIR')['raw_color_hex'], 'FFFFFFFFFFFFFFFF')
        preview = self.request('studio_color_preview', '1:HAIR')
        self.assertEqual(self.sim.raw, before)
        self.request('studio_apply', preview['preview_id'])
        after = Message(self.sim.raw)
        self.assertEqual(after.outfits[1].part_shifts.color_shift, [2**64-1, 19])
        self.assertEqual(after.outfits[1].object_ids.object_id, [3, 4])
        undo = self.request('studio_undo')
        self.request('studio_apply', undo['preview_id'])
        self.assertEqual(self.sim.raw, before)

    def test_external_edit_or_form_change_prevents_preview_application(self):
        self.request('studio_color_copy', '0:HAIR')
        preview = self.request('studio_color_preview', '1:HAIR')
        self.sim.flags = 1
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.request('studio_apply', preview['preview_id'])
        self.sim.flags = 32
        newer = Message(self.sim.raw)
        newer.outfits[0].parts.ids[1] = 777
        self.sim.raw = newer.SerializeToString()
        expected = self.sim.raw
        with self.assertRaisesRegex(ValueError, 'not overwritten'):
            self.request('studio_apply', preview['preview_id'])
        self.assertEqual(self.sim.raw, expected)

    def test_different_cas_part_is_not_silently_replaced(self):
        self.request('studio_color_copy', '0:HAIR')
        other = Message(self.sim.raw)
        other.outfits[1].parts.ids[0] = 1000
        self.sim.raw = other.SerializeToString()
        before = self.sim.raw
        with self.assertRaisesRegex(ValueError, 'identical CAS part'):
            self.request('studio_color_preview', '1:HAIR')
        self.assertEqual(self.sim.raw, before)

    def test_same_sim_and_slot_in_another_save_cannot_use_the_old_preview(self):
        self.request('studio_color_copy', '0:HAIR')
        preview = self.request('studio_color_preview', '1:HAIR')
        before = self.sim.raw
        self.backend.services.get_persistence_service = lambda: Obj(
            get_save_slot_proto_buff=lambda: Obj(slot_id=42), get_save_slot_proto_guid=lambda: 9877)
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.request('studio_apply', preview['preview_id'])
        self.assertEqual(self.sim.raw, before)

    def test_unsaved_world_refuses_history_before_creating_recovery_files(self):
        self.backend.services.get_persistence_service = lambda: Obj(
            get_save_slot_proto_buff=lambda: Obj(slot_id=0), get_save_slot_proto_guid=lambda: None)
        with self.assertRaisesRegex(ValueError, 'Save this disposable game first'):
            self.request('studio_checkpoint', 'Must not persist')
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_inventory_preserves_uint64_identities_and_absent_colors(self):
        message = Message(self.sim.raw)
        message.outfits[0].parts.ids[0] = 2**64-1
        message.outfits[1].part_shifts.color_shift = []
        self.sim.raw = message.SerializeToString()
        before = self.sim.raw
        result = self.request('studio_status')
        first = result['outfit_inventory'][0]['parts'][0]
        second = result['outfit_inventory'][1]['parts'][0]
        self.assertEqual(first['cas_part_id'], str(2**64-1))
        self.assertEqual(first['cas_part_hex'], 'FFFFFFFFFFFFFFFF')
        self.assertEqual(first['target'], '0:7:0')
        self.assertEqual(first['object_id'], '3')
        self.assertEqual(first['layer_id'], 5)
        self.assertIsNone(second['color_hex'])
        self.assertEqual(self.sim.raw, before)
        self.assertIn('9876:42:1234:32', result['history_lane'])

    def test_layered_parts_require_explicit_target_and_preserve_other_rows(self):
        message = Message(self.sim.raw)
        for outfit in message.outfits:
            outfit.body_types_list.body_types = [7, 7]
        self.sim.raw = message.SerializeToString()
        before = self.sim.raw
        with self.assertRaisesRegex(ValueError, 'layered slots'):
            self.request('studio_color_copy', '0:7')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.request('studio_color_copy', '0:7:2')
        self.assertEqual(self.sim.raw, before)
        self.request('studio_color_copy', '0:7:0')
        preview = self.request('studio_color_preview', '1:7:0')
        self.assertEqual(self.sim.raw, before)
        self.request('studio_apply', preview['preview_id'])
        after = Message(self.sim.raw)
        self.assertEqual(after.outfits[1].part_shifts.color_shift, [2**64-1, 19])
        self.assertEqual(after.outfits[1].parts.ids, [999, 888])
        self.assertEqual(after.outfits[1].object_ids.object_id, [3, 4])
        self.assertEqual(after.outfits[1].layer_ids.layer_id, [5, 6])

    def test_unrelated_layered_slot_does_not_block_explicit_color_edit(self):
        message = Message(self.sim.raw)
        for outfit in message.outfits:
            outfit.parts.ids.extend([555])
            outfit.body_types_list.body_types.extend([2])
            outfit.part_shifts.color_shift.extend([37])
            outfit.object_ids.object_id.extend([8])
            outfit.layer_ids.layer_id.extend([9])
        self.sim.raw = message.SerializeToString()
        self.request('studio_color_copy', '0:7')
        preview = self.request('studio_color_preview', '1:7')
        self.request('studio_apply', preview['preview_id'])
        after = Message(self.sim.raw).outfits[1]
        self.assertEqual(after.part_shifts.color_shift, [2**64-1, 19, 37])
        self.assertEqual(after.parts.ids, [999, 888, 555])
        self.assertEqual(after.body_types_list.body_types, [7, 2, 2])

    def test_inventory_blocks_mismatched_patch_sensitive_body_type(self):
        self.backend._v8_resolve_body_type = lambda value: (114, {'label': 'Wings'}, 'runtime enum differs')
        result = self.request('studio_status')
        part = result['outfit_inventory'][0]['parts'][0]
        self.assertFalse(part['target_supported'])
        self.assertEqual(part['target_reason'], 'runtime enum differs')

    def part_request(self):
        message = Message(self.sim.raw)
        message.outfits[1].parts.ids[0] = 1200
        self.sim.raw = message.SerializeToString()
        self.backend._studio_casp_bytes = lambda _id: casp(body=7)
        status = self.request('studio_status')
        editor = self.request('studio_part_inspect', '0:7:0')['part_editor']
        self.assertEqual(editor['candidates'][0]['cas_part_id'], '1200')
        return dict(target='0:7:0', source='1:7:0', lane=status['history_lane'],
                    appearance_sha256=status['appearance_sha256'])

    def test_equipped_part_replacement_keeps_other_parts_and_destination_references(self):
        request = self.part_request()
        before = self.sim.raw
        preview = self.request('studio_part_preview', json.dumps(request))
        self.assertEqual(self.sim.raw, before)
        self.request('studio_apply', preview['preview_id'])
        changed = Message(self.sim.raw)
        self.assertEqual(changed.outfits[0].parts.ids, [1200, 888])
        self.assertEqual(changed.outfits[0].part_shifts.color_shift, [0, 19])
        self.assertEqual(changed.outfits[0].object_ids.object_id, [3, 4])
        self.assertEqual(changed.outfits[0].layer_ids.layer_id, [5, 6])
        self.assertEqual(changed.outfits[1].parts.ids, [1200, 888])
        self.request('studio_apply', self.request('studio_undo')['preview_id'])
        self.assertEqual(self.sim.raw, before)

    def test_replacement_refuses_stale_identity_foreign_body_and_incompatible_layers(self):
        request = self.part_request()
        before = self.sim.raw
        request['lane'] = 'another Sim'
        with self.assertRaisesRegex(ValueError, 'Sim/form/save'):
            self.request('studio_part_preview', json.dumps(request))
        request = self.part_request()
        message = Message(self.sim.raw)
        message.outfits[1].layer_ids.layer_id[0] = 99
        self.sim.raw = message.SerializeToString()
        request['appearance_sha256'] = self.request('studio_status')['appearance_sha256']
        with self.assertRaisesRegex(ValueError, 'layer is incompatible'):
            self.request('studio_part_preview', json.dumps(request))
        self.backend._studio_casp_bytes = lambda _id: casp(body=8)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.request('studio_part_inspect', '0:7:0')

    def test_appearance_history_restores_shape_skin_and_outfits_without_gameplay_reload(self):
        self.sim.progression = 33
        self.request('studio_checkpoint', 'Before CAS preset')
        self.sim.physique, self.sim.skin_tone = 'New CAS preset body', 900
        changed = self.request('studio_checkpoint', 'After CAS preset and skin')
        self.assertIn('physique', changed['history_nodes'][-1]['delta']['changed_fields'])
        undo = self.request('studio_undo')
        self.sim.progression = 99
        self.request('studio_apply', undo['preview_id'])
        self.assertEqual((self.sim.physique, self.sim.skin_tone), ('original shape', 41))
        self.assertEqual(self.sim.progression, 99)
        self.request('studio_apply', self.request('studio_redo')['preview_id'])
        self.assertEqual((self.sim.physique, self.sim.skin_tone), ('New CAS preset body', 900))

    def test_future_native_field_changes_tracked_even_if_appearance_does_not_change(self):
        from apex_core import sim_record
        future = {'native_sha256': 'a' * 64, 'native_base64': 'opaque native bytes',
                  'data': {'fields': [{'name': 'new_patch_eyebrow_preset', 'number': 9000, 'present': False}]},
                  'field_schemas': {'new.game.Sim': [{'name': 'new_patch_eyebrow_preset', 'number': 9000}]}}
        self.backend._studio_native_record = lambda _: future
        first = self.request('studio_status')
        before_appearance = self.sim.raw
        future['data']['fields'][0].update(present=True, value='18446744073709551615')
        future['native_sha256'] = 'b' * 64
        second = self.request('studio_status')
        self.assertEqual(self.sim.raw, before_appearance)
        self.assertEqual(first['history_cursor'], second['history_cursor'])
        self.assertEqual(second['latest_native_observation']['delta']['changed_native_fields'], ['new_patch_eyebrow_preset'])
        _, _, journal, _ = studio._context(self.backend, self.sim.id)
        retained = self.request('studio_record', 'latest-native')
        self.assertEqual(retained['data']['fields'][0]['value'], '18446744073709551615')
        self.assertIn('new.game.Sim', retained['field_schemas'])

    def test_gameplay_observation_after_apply_does_not_consume_appearance_undo_or_redo(self):
        request = self.part_request(); before = self.sim.raw
        preview = self.request('studio_part_preview', json.dumps(request))
        after = self.request('studio_apply', preview['preview_id']); changed = self.sim.raw
        # Real game serialization can change gameplay while appearance remains identical.
        provider = self.backend._studio_native_record
        self.backend._studio_native_record = lambda sim: dict(provider(sim), native_sha256='a' * 64)
        observed = self.request('studio_status')
        self.assertEqual(observed['history_cursor'], after['history_cursor'])
        self.assertGreater(observed['native_observation_count'], 0)
        self.request('studio_apply', self.request('studio_undo')['preview_id'])
        self.assertEqual(self.sim.raw, before)
        self.request('studio_status')
        self.request('studio_apply', self.request('studio_redo', after['history_cursor'])['preview_id'])
        self.assertEqual(self.sim.raw, changed)

    def test_form_bank_storage_failure_rolls_back_accepted_studio_write(self):
        from unittest.mock import patch
        request = self.part_request()
        before = self.sim.raw
        preview = self.request('studio_part_preview', json.dumps(request))
        with patch.object(studio.form_bank, 'update', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.request('studio_apply', preview['preview_id'])
        self.assertEqual(self.sim.raw, before)
        self.assertIsNone(self.request('studio_status')['pending_preview'])

    def numeric_request(self, edits):
        self.backend._studio_casp_bytes = lambda part_id: casp(body=7)
        reply = self.request('studio_color_inspect', '0:7:0')
        editor = reply['color_editor']
        return dict(target=editor['target'], lane=reply['history_lane'], edits=edits,
            **{key: editor[key] for key in ('cas_part_id', 'color_hex', 'appearance_sha256', 'resource_sha256')})

    def test_numeric_color_has_preview_apply_readback_and_undo_without_other_lanes_changing(self):
        before = self.sim.raw
        request = self.numeric_request({'hue': 0.25})
        preview = self.request('studio_color_edit', json.dumps(request))
        self.assertEqual(self.sim.raw, before)
        self.assertIn('FFFF1000FFFFFFFF', preview['preview_diff'])
        self.request('studio_apply', preview['preview_id'])
        after = Message(self.sim.raw)
        self.assertEqual(after.outfits[0].part_shifts.color_shift[0], 0xFFFF1000FFFFFFFF)
        self.assertEqual(after.outfits[0].parts.ids, [999, 888])
        self.assertEqual(after.outfits[0].layer_ids.layer_id, [5, 6])
        undo = self.request('studio_undo')
        self.request('studio_apply', undo['preview_id'])
        self.assertEqual(self.sim.raw, before)

    def test_numeric_rejects_stale_appearance_form_resource_and_disabled_channels(self):
        request = self.numeric_request({'hue': 0.25})
        before = self.sim.raw
        self.backend._studio_casp_bytes = lambda part_id: casp(body=7, step=0)
        with self.assertRaisesRegex(ValueError, 'resource changed'):
            self.request('studio_color_edit', json.dumps(request))
        self.backend._studio_casp_bytes = lambda part_id: casp(body=7)
        self.sim.flags = 1
        with self.assertRaisesRegex(ValueError, 'Sim/form/save'):
            self.request('studio_color_edit', json.dumps(request))
        self.sim.flags = 32
        request['appearance_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'appearance changed'):
            self.request('studio_color_edit', json.dumps(request))
        self.assertEqual(self.sim.raw, before)
