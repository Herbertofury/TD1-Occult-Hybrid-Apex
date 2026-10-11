"""Catalog mutations use the actual appearance journal on synthetic owners."""
import hashlib
import json
import unittest
from unittest.mock import patch
import test_studio as fixtures
Message = fixtures.Message
from casp_fixture import casp
from apex_core import cas_catalog
from apex_core.dresser_parts import NEUTRAL_SHIFT


class CatalogMutationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StudioTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.sim, self.backend = self.fixture.sim, self.fixture.backend
        self.sim.age, self.sim.gender, self.sim.species = 32, 0x2000, 1
        self.backend._v8_resolve_body_type = lambda value: (int(value), {}, '')
        message = Message(self.sim.raw)
        for outfit in message.outfits: outfit.object_ids.object_id[0] = 0
        self.sim.raw = message.SerializeToString()
        self.raw = casp(body=7, age_gender=32 | 0x3000)
        def effective(backend, ident):
            return dict(cas_catalog.slider_metadata(self.raw), resource_tgi='034AEECB:80000000:{:016X}'.format(ident),
                        resource_key_query='native-key')
        mock = patch.object(cas_catalog, 'effective_metadata', side_effect=effective)
        mock.start(); self.addCleanup(mock.stop)
        self.request = self.fixture.request

    def selection(self, **edits):
        status = self.request('studio_status')
        request = dict(outfit_index=0, outfit_id='1', part_index=0, body_type=7, cas_part_id='10000',
            resource_tgi='034AEECB:80000000:0000000000002710', resource_sha256=hashlib.sha256(self.raw).hexdigest(),
            lane=status['history_lane'], appearance_sha256=status['appearance_sha256'])
        request.update(edits)
        return request

    def preview(self, request=None):
        return self.request('studio_catalog_preview', json.dumps(request or self.selection()))

    def test_replacement_never_writes_before_apply_and_undo_redo_is_exact(self):
        original = self.sim.raw
        preview = self.preview()
        self.assertTrue(preview['effective_resource_verified'])
        self.assertEqual(self.sim.raw, original)
        self.request('studio_apply', preview['preview_id'])
        applied = self.sim.raw
        message = Message(applied)
        self.assertEqual(message.outfits[0].parts.ids, [10000, 888])
        self.assertEqual(message.outfits[0].layer_ids.layer_id, [17, 6])
        self.assertEqual(message.outfits[0].part_shifts.color_shift, [NEUTRAL_SHIFT, 19])
        self.assertEqual(message.outfits[1].__dict__, Message(original).outfits[1].__dict__)
        undo = self.request('studio_undo'); self.request('studio_apply', undo['preview_id'])
        self.assertEqual(self.sim.raw, original)
        redo = self.request('studio_redo'); self.request('studio_apply', redo['preview_id'])
        self.assertEqual(self.sim.raw, applied)

    def test_empty_category_add_preserves_all_existing_rows_and_arrays(self):
        original = self.sim.raw
        self.raw = casp(body=35, age_gender=32 | 0x3000, layer=23)
        preview = self.preview(self.selection(body_type=35, part_index=None))
        self.request('studio_apply', preview['preview_id'])
        outfit = Message(self.sim.raw).outfits[0]; before = Message(original).outfits[0]
        self.assertEqual(outfit.parts.ids, before.parts.ids + [10000])
        self.assertEqual(outfit.body_types_list.body_types, before.body_types_list.body_types + [35])
        self.assertEqual(outfit.object_ids.object_id, before.object_ids.object_id + [0])
        self.assertEqual(outfit.layer_ids.layer_id, before.layer_ids.layer_id + [23])
        self.assertEqual(outfit.part_shifts.color_shift, before.part_shifts.color_shift + [NEUTRAL_SHIFT])

    def test_inactive_owner_catalog_edit_leaves_live_sim_and_other_outfit_exact(self):
        self.fixture.stored_form()
        self.backend._v8_resolve_body_type = lambda value: (int(value), {}, '')
        message = Message(self.fixture.vampire.raw); message.outfits[0].object_ids.object_id[0] = 0
        self.fixture.vampire.raw = message.SerializeToString()
        active, inactive = self.sim.raw, self.fixture.vampire.raw
        status = self.fixture.stored_request('studio_status')
        request = self.selection(lane=status['history_lane'], appearance_sha256=status['appearance_sha256'])
        preview = self.fixture.stored_request('studio_catalog_preview', json.dumps(request))
        self.fixture.stored_request('studio_apply', preview['preview_id'])
        self.assertEqual(self.sim.raw, active)
        self.assertNotEqual(self.fixture.vampire.raw, inactive)
        self.assertEqual(Message(self.fixture.vampire.raw).outfits[1].__dict__, Message(inactive).outfits[1].__dict__)
        undo = self.fixture.stored_request('studio_undo')
        self.fixture.stored_request('studio_apply', undo['preview_id'])
        self.assertEqual(self.fixture.vampire.raw, inactive)
        self.assertEqual(self.sim.raw, active)

    def test_stale_resource_outfit_layer_and_extra_fields_refuse_without_changes(self):
        original = self.sim.raw
        for changes in (dict(resource_sha256='0' * 64), dict(resource_tgi='034AEECB:00000000:0000000000002710'),
                        dict(appearance_sha256='0' * 64), dict(outfit_id='99'), dict(part_index=True),
                        dict(part_index=None), dict(body_type=2), dict(path='arbitrary'), dict(cas_part_id='0')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.preview(self.selection(**changes))
            self.assertEqual(self.sim.raw, original)

    def test_age_species_gender_and_frame_restrictions_are_not_guessed(self):
        original = self.sim.raw
        for raw in (casp(body=7, age_gender=4 | 0x3000), casp(body=7, age_gender=32 | 0x3000, species=2),
                    casp(body=7, age_gender=32 | 0x1000, flags=128),
                    casp(body=7, age_gender=32 | 0x3000, flags2=1)):
            self.raw = raw
            with self.subTest(raw=raw), self.assertRaises(ValueError): self.preview()
            self.assertEqual(self.sim.raw, original)

    def test_object_backed_row_refuses_before_journal_preview(self):
        message = Message(self.sim.raw); message.outfits[0].object_ids.object_id[0] = 234
        self.sim.raw = message.SerializeToString(); original = self.sim.raw
        with self.assertRaisesRegex(ValueError, 'attachment'): self.preview()
        self.assertEqual(self.sim.raw, original)
        self.assertIsNone(self.request('studio_status')['pending_preview'])

    def test_reselect_equipped_item_preserves_exact_colors_layers_and_history(self):
        original = self.sim.raw
        result = self.preview(self.selection(cas_part_id='999', resource_tgi='034AEECB:80000000:00000000000003E7'))
        self.assertTrue(result['effective_resource_verified'])
        self.assertIsNone(result['pending_preview'])
        self.assertEqual(self.sim.raw, original)


if __name__ == '__main__': unittest.main()
