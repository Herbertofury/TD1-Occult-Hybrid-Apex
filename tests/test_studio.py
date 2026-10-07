from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import studio
from casp_fixture import casp


class Message:
    def __init__(self, raw):
        self.outfits = []
        for record in json.loads(raw):
            self.outfits.append(Obj(outfit_id=record['outfit_id'], category=record['category'],
                parts=Obj(ids=record['parts']), body_types_list=Obj(body_types=record['types']),
                part_shifts=Obj(color_shift=record['shifts']), object_ids=Obj(object_id=record['objects']),
                layer_ids=Obj(layer_id=record['layers'])))
    def SerializeToString(self):
        return json.dumps([dict(outfit_id=item.outfit_id, category=item.category, parts=item.parts.ids,
            types=item.body_types_list.body_types, shifts=item.part_shifts.color_shift,
            objects=item.object_ids.object_id, layers=item.layer_ids.layer_id) for item in self.outfits], sort_keys=True).encode()


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        rows = [dict(outfit_id=index+1, category=index, parts=[999, 888], types=[7, 2],
            shifts=[2**64-1 if index == 0 else 0, 19], objects=[3, 4], layers=[5, 6]) for index in range(2)]
        self.sim = Obj(id=1234, flags=32, raw=json.dumps(rows, sort_keys=True).encode())
        self.backend = Obj(_get_sim_info_by_id=lambda value: self.sim, _v8_imports_ready=lambda: True,
            _v8_read_outfit_blob=lambda sim: sim.raw, _v8_parse_outfits=lambda sim: Message(sim.raw),
            _sim_id=lambda sim: sim.id, _get_current_flags=lambda sim: sim.flags,
            _data_directory=lambda: self.temp.name, _v8_resolve_body_type=lambda value: (7, {}, 'runtime'),
            _resend_all_visuals=lambda sim: None,
            services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_buff=lambda: Obj(slot_id=42),
                get_save_slot_proto_guid=lambda: 9876)))
        def write(sim, raw):
            sim.raw = raw
            return True
        self.backend._v8_write_outfit_blob = write
        studio._COLOR_CLIPBOARD = None

    def request(self, action, value=None):
        return studio.dispatch(self.backend, action, self.sim.id, value)

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
