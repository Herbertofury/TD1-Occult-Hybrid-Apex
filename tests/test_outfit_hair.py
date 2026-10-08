import copy
import sys
from pathlib import Path
from types import SimpleNamespace as Obj
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import outfit_hair, studio, form_bank, form_appearance as appearance
import test_studio


def native_outfit_parser():
    """Small real proto2 schema with the installed field numbers/wire types."""
    from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
    file = descriptor_pb2.FileDescriptorProto(name='apex_hair_fixture.proto',
        package='EA.Sims4.Persistence', syntax='proto2')
    def message(name): return file.message_type.add(name=name)
    def field(owner, name, number, kind, repeated=False, nested=None):
        item = owner.field.add(name=name, number=number, type=kind, label=3 if repeated else 1)
        if nested: item.type_name = '.EA.Sims4.Persistence.' + nested
        if repeated: item.options.packed = True
        return item
    field(message('IdList'), 'ids', 1, 6, repeated=True)  # packed fixed64
    field(message('BodyTypesList'), 'body_types', 1, 13, repeated=True)
    field(message('ColorShiftList'), 'color_shift', 1, 4, repeated=True)
    field(message('ObjectIdsList'), 'object_id', 1, 4, repeated=True)
    field(message('LayerIdsList'), 'layer_id', 1, 13, repeated=True)
    data = message('OutfitData')
    field(data, 'outfit_id', 1, 4)
    field(data, 'category', 2, 13)
    field(data, 'parts', 5, 11, nested='IdList')
    field(data, 'created', 6, 4)
    field(data, 'body_types_list', 7, 11, nested='BodyTypesList')
    field(data, 'match_hair_style', 9, 8).default_value = 'false'
    field(data, 'outfit_flags', 10, 4)
    field(data, 'outfit_flags_high', 11, 4)
    field(data, 'part_shifts', 12, 11, nested='ColorShiftList')
    field(data, 'title', 13, 9)
    field(data, 'object_ids', 14, 11, nested='ObjectIdsList')
    field(data, 'layer_ids', 15, 11, nested='LayerIdsList')
    field(data, 'outfitflags_array', 16, 4, repeated=True)
    field(message('OutfitList'), 'outfits', 1, 11, repeated=True, nested='OutfitData').options.packed = False
    pool = descriptor_pool.DescriptorPool(); pool.Add(file)
    cls = message_factory.GetMessageClass(pool.FindMessageTypeByName('EA.Sims4.Persistence.OutfitList'))
    def parse(raw):
        result = cls(); result.ParseFromString(raw); return result
    return parse


def native_outfit_fields(parse):
    from test_outfit_snapshot import varint
    message = parse(b'')
    for index, category in enumerate((0, 0, 1, 2, 3, 4, 5, 6, 7)):
        outfit = message.outfits.add(outfit_id=2**64-20+index, category=category,
            created=123+index, title='Numbered outfit ' + str(index),
            outfit_flags=2**64-1, outfit_flags_high=2**63+index)
        outfit.parts.ids.extend((2**64-1-index, 414264+index))
        outfit.body_types_list.body_types.extend((2, 75))
        outfit.part_shifts.color_shift.extend((2**64-1-index, 4611686018427387904+index))
        outfit.object_ids.object_id.extend((2**64-2-index, 0))
        outfit.layer_ids.layer_id.extend((9, 17))
        outfit.outfitflags_array.extend((0, 2**64-1))
        if index != 2: outfit.match_hair_style = index % 2 == 0
        # Unknown nested fields emulate a newer patch's values.
        raw = outfit.SerializeToString() + varint(100 << 3) + varint(2**64-2)
        raw += varint((101 << 3) | 2) + b'\x04\x00\xff\x01\x02'
        outfit.ParseFromString(raw)
    raw = message.SerializeToString() + varint((110 << 3) | 2) + b'\x06future'
    return {'__outfits__': appearance.encode(('protobuf', raw)),
            'genetic_data': appearance.encode(b'\x00genetic hair stays owned\xff'),
            'skin_tone': appearance.encode(999), 'physique': appearance.encode('unchanged shape')}


class NativeHairPreparationTests(unittest.TestCase):
    def setUp(self):
        self.parse = native_outfit_parser()
        self.backend = Obj(_studio_parse_snapshot=self.parse)
        self.fields = native_outfit_fields(self.parse)

    def test_all_categories_and_numbered_outfits_keep_parts_exact_colors_unknowns_and_other_flags(self):
        before = copy.deepcopy(self.fields)
        desired = outfit_hair.independent_style_fields(self.backend, self.fields)
        original = self.parse(appearance.decode(self.fields['__outfits__'])[1])
        prepared = self.parse(appearance.decode(desired['__outfits__'])[1])
        self.assertEqual(self.fields, before)  # Pure planning, no original mutation.
        self.assertEqual({key: value for key, value in desired.items() if key != '__outfits__'},
                         {key: value for key, value in before.items() if key != '__outfits__'})
        self.assertEqual(outfit_hair.style_match_status(self.backend, desired),
                         {'outfit_count': 9, 'matching_outfit_count': 0})
        for left, right in zip(original.outfits, prepared.outfits):
            self.assertFalse(right.match_hair_style)
            self.assertTrue(right.HasField('match_hair_style'))
            self.assertEqual(list(left.parts.ids), list(right.parts.ids))
            self.assertEqual(list(left.part_shifts.color_shift), list(right.part_shifts.color_shift))
            left.ClearField('match_hair_style'); right.ClearField('match_hair_style')
            self.assertEqual(left.SerializeToString(), right.SerializeToString())
        self.assertEqual(original.SerializeToString(), prepared.SerializeToString())

    def test_missing_schema_wrong_type_or_missing_native_assignment_refuses_preparation(self):
        with self.assertRaisesRegex(ValueError, 'field 9 is unavailable'):
            outfit_hair.independent_style_fields(Obj(_studio_parse_snapshot=lambda _: Obj(outfits=[])), self.fields)
        message = self.parse(appearance.decode(self.fields['__outfits__'])[1])
        descriptor = message.DESCRIPTOR.fields_by_name['outfits'].message_type
        with patch.object(outfit_hair, '_message', return_value=Obj(DESCRIPTOR=message.DESCRIPTOR,
                outfits=[Obj(DESCRIPTOR=descriptor, match_hair_style=1)])):
            with self.assertRaisesRegex(ValueError, 'API is unavailable'):
                outfit_hair.independent_style_fields(self.backend, self.fields)
        class ReadOnly:
            DESCRIPTOR = descriptor
            @property
            def match_hair_style(self): return True
        with patch.object(outfit_hair, '_message', return_value=Obj(DESCRIPTOR=message.DESCRIPTOR, outfits=[ReadOnly()])):
            with self.assertRaisesRegex(ValueError, 'cannot set'):
                outfit_hair.independent_style_fields(self.backend, self.fields)


class OutfitHairTests(unittest.TestCase):
    def setUp(self):
        test_studio.StudioTests.setUp(self)
        message = test_studio.Message(self.sim.raw)
        message.outfits[1].category = 0  # Everyday 2, a distinct numbered outfit.
        message.outfits[1].parts.ids[0] = 1200
        formal = copy.deepcopy(message.outfits[1]); formal.category=1; formal.outfit_id=3
        formal.parts.ids[0]=1500; formal.part_shifts.color_shift[0]=2**64-2
        message.outfits.append(formal); self.sim.raw=message.SerializeToString()
        self.sim.on_outfit_changed=[]
        self.sim.register_for_outfit_changed_callback=self.sim.on_outfit_changed.append
        self.sim.get_current_outfit=lambda: (0, 0)
        self.backend._APEX_GAME_THREAD_IDENT=threading.current_thread().ident
        self.backend._log=lambda *_: None
        self.backend._v8_resolve_body_type=lambda value: (7 if value=='HAIR' else None if value=='HAIRCOLOR_OVERRIDE' else int(value), {}, 'runtime')
        self.backend._studio_casp_bytes=lambda _: test_studio.casp(body=7)
        self.addCleanup(outfit_hair._BUSY.clear)
        self.addCleanup(outfit_hair._ERRORS.clear)

    def request(self, action, value=None):
        return studio.dispatch(self.backend, action, self.sim.id, value)

    def change_all_hair(self):
        message=test_studio.Message(self.sim.raw)
        for outfit in message.outfits:
            outfit.parts.ids[0]=9999; outfit.part_shifts.color_shift[0]=123456789
            outfit.parts.ids[1]=3333  # An unrelated legitimate clothing edit.
        self.sim.raw=message.SerializeToString()

    def test_event_restores_every_category_and_outfit_number_preserving_other_changes(self):
        original=outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim))
        policy=self.request('studio_hair_enable')['hair_policy']
        self.assertEqual(policy['outfit_count'],3)
        self.assertEqual(len(self.sim.on_outfit_changed),1)
        self.change_all_hair(); self.sim.skin_tone=999; self.sim.progression=77
        self.sim.on_outfit_changed[0](self.sim,(0,1),(0,0))
        self.assertEqual(outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim)),original)
        self.assertEqual([row.parts.ids[1] for row in test_studio.Message(self.sim.raw).outfits],[3333]*3)
        self.assertEqual((self.sim.skin_tone,self.sim.progression),(999,77))
        self.assertIn('Keep independent outfit hairstyle',self.request('studio_history')['history_nodes'][-1]['label'])

    def test_accepted_live_hair_edit_updates_only_selected_number_and_survives_propagation(self):
        self.request('studio_hair_enable'); before=self.request('studio_status')
        preview=self.request('studio_part_preview',__import__('json').dumps(dict(target='0:7:0',source='1:7:0',
            lane=before['history_lane'],appearance_sha256=before['appearance_sha256'])))
        self.request('studio_apply',preview['preview_id'])
        held=outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim))
        self.assertEqual([row['hair'][0]['row']['id'] for row in held],[1200,1200,1500])
        self.change_all_hair(); self.assertTrue(outfit_hair.enforce(self.backend,self.sim))
        self.assertEqual(outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim)),held)

    def test_cas_accepts_target_hair_but_reverses_propagation_to_other_numbers_and_categories(self):
        self.request('studio_hair_enable')
        path,key=form_bank.context(self.backend,self.sim);record=form_bank.load(path)['records'][key]
        original=outfit_hair.capture(self.backend,appearance.packed(self.backend,self.sim))
        self.change_all_hair();returned=appearance.packed(self.backend,self.sim)
        chosen=outfit_hair.accept_cas(self.backend,record,'32',returned,[0,1])
        rows=outfit_hair.capture(self.backend,chosen)
        self.assertEqual(rows[0],original[0]);self.assertEqual(rows[2],original[2])
        self.assertEqual(rows[1]['hair'][0]['row']['id'],9999)
        self.assertEqual(rows[1]['hair'][0]['row']['color_shift'],123456789)
        self.assertEqual([row.parts.ids[1] for row in test_studio.Message(appearance.decode(chosen['__outfits__'])[1]).outfits],[3333]*3)
        self.assertEqual(self.sim.raw,appearance.decode(returned['__outfits__'])[1]) # Preview/repair planning is pure.
        with self.assertRaisesRegex(ValueError,'explicit CAS hair target'):
            outfit_hair.accept_cas(self.backend,record,'32',returned,None)

    def test_disabled_policy_and_unknown_outfit_identity_do_not_overwrite_new_wardrobe(self):
        self.request('studio_hair_enable');self.request('studio_hair_disable');self.change_all_hair()
        before=self.sim.raw;self.assertFalse(outfit_hair.enforce(self.backend,self.sim));self.assertEqual(self.sim.raw,before)
        self.request('studio_hair_enable');message=test_studio.Message(self.sim.raw)
        message.outfits[0].outfit_id=9000;self.sim.raw=message.SerializeToString();before=self.sim.raw
        with self.assertRaisesRegex(ValueError,'Outfit identity changed'):
            outfit_hair.enforce(self.backend,self.sim)
        self.assertEqual(self.sim.raw,before)

    def test_pending_cas_or_studio_preview_blocks_event_repair_and_bank_failure_rolls_back(self):
        self.request('studio_hair_enable');self.change_all_hair();before=self.sim.raw
        with patch.object(form_bank,'save',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):outfit_hair.enforce(self.backend,self.sim)
        self.assertEqual(self.sim.raw,before)
        path,key=form_bank.context(self.backend,self.sim);data=form_bank.load(path)
        data['records'][key]['pending']={'state':'captured'};form_bank.save(path,data)
        self.assertFalse(outfit_hair.enforce(self.backend,self.sim));self.assertEqual(self.sim.raw,before)

    def test_restart_hook_chains_original_once_and_does_not_scan_on_ticks(self):
        self.request('studio_hair_enable');self.sim.on_outfit_changed.clear();self.change_all_hair()
        calls=[]
        class Wrapper:
            def set_current_outfit(info,value):
                calls.append(value)
                for callback in list(info.on_outfit_changed):callback(info,value,(0,0))
                return True
        outfit_hair.install(self.backend,Wrapper);wrapped=Wrapper.set_current_outfit
        outfit_hair.install(self.backend,Wrapper);self.assertIs(Wrapper.set_current_outfit,wrapped)
        self.assertTrue(Wrapper.set_current_outfit(self.sim,(0,1)))
        self.assertEqual(calls,[(0,1)]);self.assertEqual(len(self.sim.on_outfit_changed),1)
        self.assertEqual(test_studio.Message(self.sim.raw).outfits[2].parts.ids[0],1500)
