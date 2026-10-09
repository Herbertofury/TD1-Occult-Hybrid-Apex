"""Bounded native equipped metadata pages retain every explicit outfit row."""
import copy
import json
import os
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

import test_studio
from casp_fixture import casp
from apex_core import studio, cas_catalog, form_bank, form_appearance


class StudioItemsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_studio.StudioTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.bodies = {}
        rows = []
        for outfit in range(2):
            ids = [1000 + outfit * 10 + index for index in range(10)]
            bodies = [20, 21, 21, 900, 7, 2, 3, 4, 5, 6]
            self.bodies.update(zip(ids, bodies))
            rows.append(dict(outfit_id=outfit + 11, category=900, parts=ids, types=bodies,
                shifts=[0] * 10, objects=[], layers=list(range(10))))
        self.fixture.sim.raw = test_studio.Message.pack(rows)
        # Unknown runtime BodyTypes must still be inspected from actual rows.
        self.fixture.backend._v8_resolve_body_type = lambda _: (None, None, 'unknown runtime enum')
        self.fixture.sim.get_outfit = Mock(side_effect=AssertionError('Generating outfit getter was called'))
        self.resources = Obj(Types=Obj(CASPART=0x034AEECB),
            get_resource_key=Mock(side_effect=lambda instance, _: Obj(type=0x034AEECB, group=0x1234, instance=instance)),
            ResourceLoader=Mock(side_effect=lambda key: Obj(load_raw=Mock(return_value=casp(body=self.bodies[key.instance])))))
        self.module_patch = patch.dict(sys.modules, {'sims4': Obj(resources=self.resources)})
        self.module_patch.start(); self.addCleanup(self.module_patch.stop)
        self.status = self.fixture.request('studio_status')

    def arguments(self, **changes):
        return dict(lane=self.status['history_lane'], appearance_sha256=self.status['appearance_sha256'],
            runtime_pid=self.status['runtime_pid'], cursor=0, limit=8, outfit_index=None, **changes)

    def page(self, **changes):
        value = self.arguments(); value.update(changes)
        return self.fixture.request('studio_items', json.dumps(value))

    def test_all_skin_jewelry_layered_and_unknown_categories_page_without_whitelist(self):
        original = (self.fixture.sim.raw, self.fixture.sim.physique, self.fixture.sim.skin_tone, self.fixture.sim.flags)
        receipts = []
        cursor = 0
        while True:
            page = self.page(cursor=cursor)
            self.assertLessEqual(len(page['items']), 8)
            self.assertLessEqual(page['resource_inspection_count'], 8)
            self.assertLess(len(json.dumps(page).encode()), 512 * 1024)
            self.assertEqual(page['total'], 20)
            receipts.extend(page['items'])
            if page['complete']:
                self.assertIsNone(page['next_cursor']); break
            cursor = page['next_cursor']
        self.assertEqual([row['cas_part_id'] for row in receipts], [str(value) for value in self.bodies])
        self.assertTrue(all(row['status'] == 'resolved' for row in receipts))
        self.assertTrue(all(row['display_name'] == 'Apex test part' for row in receipts))
        self.assertEqual([row['body_type'] for row in receipts[:4]], [20, 21, 21, 900])
        self.assertEqual([row['target'] for row in receipts[:4]], ['0:20:0', '0:21:1', '0:21:2', '0:900:3'])
        for row in receipts:
            self.assertEqual(row['part_editor']['resource_tgi'], '034AEECB:00001234:' + row['cas_part_hex'])
            self.assertEqual(row['part_editor']['body_type'], row['body_type'])
        self.assertEqual(original, (self.fixture.sim.raw, self.fixture.sim.physique, self.fixture.sim.skin_tone, self.fixture.sim.flags))
        self.fixture.sim.get_outfit.assert_not_called()

    def test_exact_outfit_filter_retains_category_ordinal_and_row_cursor(self):
        page = self.page(outfit_index=1, cursor=7, limit=3)
        self.assertEqual(page['total'], 10); self.assertTrue(page['complete'])
        self.assertEqual([row['cas_part_id'] for row in page['items']], ['1017', '1018', '1019'])
        self.assertTrue(all(row['outfit_index'] == 1 and row['category'] == 900 and row['ordinal'] == 1 and
                            row['outfit_id'] == '12' for row in page['items']))

    def test_metadata_chunk_never_loads_or_serializes_the_full_history_graph(self):
        with patch.object(studio, 'ChangeJournal', side_effect=AssertionError('History graph was loaded')):
            with patch.object(studio.sim_record, 'capture', side_effect=AssertionError('Full gameplay record was captured')):
                self.assertEqual(len(self.page()['items']), 8)

    def test_transient_slot_metadata_keeps_exact_pid_and_creates_no_history_graph(self):
        before = self.fixture.sim.raw
        for slot in (0, 0xffffffff):
            self.fixture.backend.services.get_persistence_service = lambda: Obj(
                get_save_slot_proto_buff=lambda: Obj(slot_id=slot), get_save_slot_proto_guid=lambda: 9876)
            with patch.object(studio, 'ChangeJournal', side_effect=AssertionError('History graph was loaded')):
                _, state, _, lane = studio._context(self.fixture.backend, self.fixture.sim.id, history=False)
                page = self.page(lane=lane, appearance_sha256=studio.fingerprint(state))
            self.assertEqual(page['owner']['slot_id'], slot)
            self.assertEqual(page['owner']['runtime_pid'], os.getpid())
            self.assertFalse(page['stable_save_slot_verified'])
            self.assertTrue(page['history_runtime_only'])
            self.assertIn(':runtime-{}:'.format(os.getpid()), page['history_lane'])
            self.assertEqual(len(page['items']), 8)
        self.assertEqual(self.fixture.sim.raw, before)

    def test_unavailable_truncated_or_wrong_body_resources_remain_explicit_rows(self):
        def resource(key):
            if key.instance == 1000: raise OSError('Effective resource unavailable')
            raw = b'broken CASP' if key.instance == 1001 else casp(body=99 if key.instance == 1002 else self.bodies[key.instance])
            return Obj(load_raw=Mock(return_value=raw))
        self.resources.ResourceLoader.side_effect = resource
        page = self.page(limit=4)
        self.assertEqual(len(page['items']), 4); self.assertEqual(page['next_cursor'], 4)
        self.assertEqual([row['status'] for row in page['items']], ['unresolved'] * 3 + ['resolved'])
        self.assertIn('unavailable', page['items'][0]['reason'])
        self.assertIn('bounded resource', page['items'][1]['reason'])
        self.assertIn('body type differs', page['items'][2]['reason'])
        self.assertTrue(all(row['display_name'] is None for row in page['items'][:3]))

    def test_stale_pid_lane_form_or_appearance_refuses_before_any_resource_read(self):
        values = [dict(runtime_pid=os.getpid() + 100), dict(runtime_pid=True), dict(lane='other'),
                  dict(appearance_sha256='0' * 64)]
        for changes in values:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'changed'):
                self.page(**changes)
        value = json.dumps(self.arguments())
        with self.assertRaises(ValueError):
            self.fixture.stored_request('studio_items', value, form=4)
        self.resources.ResourceLoader.assert_not_called()

    def test_boolean_oversized_absent_or_invalid_paging_fields_refuse(self):
        for changes in (dict(cursor=True), dict(cursor=-1), dict(cursor=21), dict(limit=True), dict(limit=9),
                        dict(limit=0), dict(limit='8'), dict(outfit_index=True), dict(outfit_index=2), dict(outfit_index=128)):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.page(**changes)
        value = self.arguments(); value.pop('runtime_pid')
        with self.assertRaisesRegex(ValueError, 'protocol'): self.fixture.request('studio_items', json.dumps(value))
        self.resources.ResourceLoader.assert_not_called()

    def test_duplicate_resource_reads_are_page_local_but_receipts_pin_each_target(self):
        message = test_studio.Message(self.fixture.sim.raw)
        message.outfits[0].parts.ids[2] = 1001
        self.fixture.sim.raw = message.SerializeToString()
        self.status = self.fixture.request('studio_status')
        first = self.page(limit=3)
        self.assertEqual(first['resource_inspection_count'], 2)
        self.assertNotEqual(first['items'][1]['cache_key'], first['items'][2]['cache_key'])
        second = self.page(limit=3)
        self.assertEqual([row['cache_key'] for row in first['items']], [row['cache_key'] for row in second['items']])
        # The effective bytes are read again on a new request, so a changed
        # provider cannot be hidden behind an old process/appearance cache.
        self.resources.ResourceLoader.side_effect = lambda key: Obj(load_raw=Mock(return_value=casp(body=self.bodies[key.instance], step=0.125)))
        changed = self.page(limit=3)
        self.assertNotEqual(first['items'][0]['cache_key'], changed['items'][0]['cache_key'])

    def test_fixture_bytes_never_invent_native_tgi_but_preserve_genuine_name(self):
        self.fixture.backend._studio_casp_bytes = lambda part: casp(body=self.bodies[part])
        item = self.page(limit=1)['items'][0]
        self.assertEqual(item['status'], 'unresolved')
        self.assertIn('unavailable', item['reason'])
        self.assertIsNone(item['part_editor']['resource_tgi'])
        self.assertEqual(item['display_name'], 'Apex test part')

    def test_response_and_traversal_bounds_fail_without_partial_page(self):
        metadata = cas_catalog.slider_metadata(casp(body=20))
        metadata.update(resource_tgi='034AEECB:00001234:00000000000003E8', resource_key_query='native-key',
                        diagnostic='x' * (501 * 1024))
        with patch.object(studio.cas_catalog, 'effective_metadata', return_value=metadata):
            with self.assertRaisesRegex(ValueError, 'transport response'): self.page(limit=1)
        message = test_studio.Message(self.fixture.sim.raw)
        message.outfits.extend([copy.deepcopy(message.outfits[0])] * 127)
        self.fixture.sim.raw = message.SerializeToString(); self.status = self.fixture.request('studio_status')
        with self.assertRaisesRegex(ValueError, 'Outfit inventory'): self.page()

    def test_prior_process_stored_bank_cannot_replace_fresh_native_item_owner(self):
        self.fixture.stored_form()
        self.bodies.update({999: 7, 888: 2, 1200: 7, 1337: 7})
        # stored_form installs a fixture byte provider; use actual key mocks.
        del self.fixture.backend._studio_casp_bytes
        form_bank.update(self.fixture.backend, self.fixture.sim, 4,
                         form_appearance.packed(self.fixture.backend, self.fixture.vampire), create=True)
        path, key = form_bank.context(self.fixture.backend, self.fixture.sim)
        bank = form_bank.load(path); bank['records'][key]['runtime_pid'] = os.getpid() + 100
        form_bank.save(path, bank); original_bank = path.read_bytes()
        message = test_studio.Message(self.fixture.vampire.raw); message.outfits[0].parts.ids[0] = 1337
        self.fixture.vampire.raw = message.SerializeToString()
        self.status = self.fixture.stored_request('studio_status')
        page = self.fixture.stored_request('studio_items', json.dumps(self.arguments()))
        self.assertEqual(page['appearance_source'], 'Native stored form')
        self.assertEqual(page['items'][0]['cas_part_id'], '1337')
        self.assertEqual(path.read_bytes(), original_bank)


if __name__ == '__main__': unittest.main()
