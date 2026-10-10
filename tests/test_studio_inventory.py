"""Adversarial equipped inventory fixtures; never launch or edit the game."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import studio_inventory as inventory
from source_manifest import sha256, write_json


def fixture(form=1, count=10):
    parts = [{'index': n, 'body_type': 900 if n == 3 else 20 + n,
              'cas_part_id': str(1000 + n), 'target': '0:{}:{}'.format(900 if n == 3 else 20 + n, n),
              'object_id': str(2**63 + n), 'layer_id': n, 'color_hex': '4000000000000000',
              'color_values': {'opacity': 1}, 'label': 'Unknown' if n == 3 else 'Skin detail'} for n in range(count)]
    return {'ok': True, 'runtime_pid': 42, 'inspected_form_flags': form,
            'history_lane': '11:0:7:{}:runtime-42:full-appearance-v1'.format(form),
            'appearance_sha256': 'a' * 64, 'stable_save_slot_verified': False,
            'category_catalog': [{'body_type': 900}], 'readable_appearance_fields': ['__outfits__', 'genetic_data'],
            'form_inventory': [{'flags': form}], 'outfit_inventory': [
                {'index': 0, 'category': 950, 'ordinal': 0, 'outfit_id': '22', 'parts': parts}]}


def page(status, cursor=0):
    _, expected = inventory._inventory(status, {'pid': 42}, '7', status['inspected_form_flags'])
    rows = []
    for native in expected[cursor:cursor+8]:
        row = copy.deepcopy(native)
        row['object_id'] = int(row['object_id']); row['color_shift'] = int(row.pop('color_hex'), 16)
        row.update(display_name='Native code', name_status='casp-internal-name', part_editor=None)
        rows.append(row)
    end = cursor + len(rows)
    return {'ok': True, 'runtime_pid': 42, 'history_lane': status['history_lane'],
        'appearance_sha256': status['appearance_sha256'], 'inspected_form_flags': status['inspected_form_flags'],
        'owner': {'runtime_pid': 42, 'sim_id': '7', 'form_flags': status['inspected_form_flags'], 'save_guid': '11', 'slot_id': 0},
        'cursor': cursor, 'total': len(expected), 'items': rows,
        'next_cursor': end if end < len(expected) else None, 'complete': end == len(expected)}


class PageTests(unittest.TestCase):
    def setUp(self):
        self.status = fixture()
        _, self.rows = inventory._inventory(self.status, {'pid': 42}, '7', 1)

    def read(self, data):
        return inventory._page(data, self.status, self.rows, 0, 1, '7', {'pid': 42})

    def test_unknown_skin_layer_category_and_uint64_objects_retained(self):
        items, cursor = self.read(page(self.status))
        self.assertEqual(cursor, 8)
        self.assertEqual(items[3]['body_type'], 900)
        self.assertTrue(all(row['category'] == 950 for row in items))
        self.assertEqual(items[0]['object_id'], 2**63)

    def test_stale_owner_hash_counts_and_skip_cursor_refused(self):
        for key, value in [('history_lane', 'wrong'), ('appearance_sha256', 'b'*64),
                           ('runtime_pid', 43), ('total', 11), ('next_cursor', 9)]:
            data = page(self.status); data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.read(data)

    def test_cross_outfit_resource_color_and_layer_row_refused(self):
        for key, value in [('outfit_index', 1), ('category', 0), ('ordinal', 1), ('outfit_id', '23'),
                           ('cas_part_id', '1100'), ('layer_id', 500), ('object_id', 1), ('color_shift', 2)]:
            data = page(self.status); data['items'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.read(data)

    def test_truncated_page_does_not_claim_complete(self):
        data = page(self.status); data['items'].pop()
        with self.assertRaises(ValueError): self.read(data)

    def test_unresolved_catalog_does_not_invent_package_thumbnail(self):
        item = page(self.status)['items'][0]
        result = inventory.enrich(item, self.rows[0], Obj(records={}))
        self.assertFalse(result['catalog_match_verified'])
        self.assertIsNone(result['names']['package']); self.assertNotIn('thumbnail', result)

    def test_catalog_match_requires_exact_hash_and_preserves_distinct_names(self):
        item = page(self.status)['items'][0]
        item['part_editor'] = {'resource_tgi': '034AEECB:00000000:00000000000003E8', 'resource_sha256': 'b'*64}
        entry = {'row': {'status': 'resolved', 'resource_id': 'c'*64, 'cache_proof': 'd'*64,
            'resource_tgi': item['part_editor']['resource_tgi'], 'effective_resource_sha256': 'b'*64,
            'body_type': item['body_type'], 'display_name': 'Creator Eyeliner.package',
            'name_status': 'cc-package-filename', 'provenance': {'origin': 'mod', 'package_filename': 'Creator Eyeliner.package'},
            'thumbnail': {'status': 'resolved'}, 'studio_open': {'selection': 'containing-package'}}}
        catalog = Obj(records={'c'*64: entry}, thumbnail=Mock(return_value=b'verified png'))
        result = inventory.enrich(item, self.rows[0], catalog)
        self.assertEqual(result['names'], {'code': 'Native code', 'package': 'Creator Eyeliner.package',
            'preferred': 'Creator Eyeliner.package', 'preferred_source': 'cc-package-filename'})
        self.assertTrue(result['thumbnail']['cache_bytes_verified']); catalog.thumbnail.assert_called_once()
        entry['row']['effective_resource_sha256'] = 'e'*64
        self.assertFalse(inventory.enrich(item, self.rows[0], catalog)['catalog_match_verified'])


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.state = self.root / 'state.json'
        self.state.write_text('{}'); self.output = self.root / 'inventory.json'
        self.profile = self.root / 'test'; self.original = self.root / 'original'
        self.identity = {'pid': 42, 'test_token': 'a'*32, 'script_sha256': 'b'*64}
        self.journal = {'artifacts': [{'name': 'script', 'sha256': 'b'*64}]}
        self.status = fixture(); self.calls = []

    def request(self, state, action, sim_id, value=None):
        self.calls.append(action)
        envelope = json.loads(value) if value is not None else None
        form = envelope['form'] if envelope else 1
        status = fixture(form)
        status['form_inventory'] = [{'flags': 1}, {'flags': 64}]
        if action == 'studio_status': return status
        if action != 'studio_items': self.fail('Mutation action used')
        request = json.loads(envelope['value'])
        return page(status, request['cursor'])

    def run_inventory(self, **kwargs):
        with patch.object(inventory.reusable_profile, 'load', return_value=(self.state, self.journal, self.profile, self.original)):
            return inventory.collect(self.state, self.output, self.identity, self.request, '7', **kwargs)

    def test_every_row_in_all_existing_forms_without_activation(self):
        result = self.run_inventory(all_forms=True)
        self.assertTrue(result['ok']); self.assertEqual(result['equipped_rows'], 20)
        proof = json.loads(self.output.read_bytes())
        self.assertEqual([row['flags'] for row in proof['forms']], [1, 64])
        self.assertFalse(proof['native_manual_slot_verified'])
        self.assertEqual(set(self.calls), {'studio_status', 'studio_items'})

    def test_identity_drift_stops_before_next_page(self):
        self.assertFalse(self.run_inventory(identity_provider=lambda _: dict(self.identity, pid=43))['ok'])
        self.assertEqual(self.calls, [])

    def test_overlapping_read_pages_remain_in_exact_native_order(self):
        import threading
        original = self.request; barrier = threading.Barrier(2)
        def overlap(*args, **kwargs):
            if args[1] == 'studio_items': barrier.wait(timeout=3)
            return original(*args, **kwargs)
        self.request = overlap
        result = self.run_inventory(jobs=2)
        self.assertTrue(result['ok'])
        rows = json.loads(self.output.read_bytes())['forms'][0]['items']
        self.assertEqual([r['cas_part_id'] for r in rows], [str(1000+n) for n in range(10)])

    def test_concurrent_stale_page_does_not_certify_form(self):
        original = self.request
        def stale(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[1] == 'studio_items' and result['cursor'] == 8: result['appearance_sha256'] = 'e'*64
            return result
        self.request = stale
        result = self.run_inventory(jobs=4)
        self.assertFalse(result['ok']); self.assertEqual(result['forms'], 0)

    def test_unbounded_or_boolean_parallelism_refused_before_reads(self):
        for jobs in (0, 5, True):
            with self.subTest(jobs=jobs), self.assertRaises(ValueError): self.run_inventory(jobs=jobs)
        self.assertEqual(self.calls, [])

    def test_appearance_drift_does_not_certify_partial_inventory(self):
        original = self.request
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            if self.calls.count('studio_status') > 1: result['appearance_sha256'] = 'c'*64
            return result
        self.request = changed
        result = self.run_inventory()
        self.assertFalse(result['ok']); self.assertEqual(result['forms'], 0)

    def test_existing_output_and_profile_path_never_overwritten(self):
        self.output.write_bytes(b'prior')
        with self.assertRaises(ValueError): self.run_inventory()
        self.assertEqual(self.output.read_bytes(), b'prior'); self.assertEqual(self.calls, [])


if __name__ == '__main__': unittest.main()
