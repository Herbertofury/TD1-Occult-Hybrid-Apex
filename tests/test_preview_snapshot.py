import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_studio
from apex_core import studio


class PreviewSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_studio.StudioTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.status = self.fixture.request('studio_status')

    def request(self, **changes):
        value = dict(lane=self.status['history_lane'], appearance_sha256=self.status['appearance_sha256'],
                     outfit_index=0, outfit_id='1'); value.update(changes)
        return self.fixture.request('studio_preview_snapshot', json.dumps(value))

    def test_snapshot_reads_native_record_once_and_creates_no_history_or_save_write(self):
        before = {p: p.read_bytes() for p in Path(self.fixture.temp.name).rglob('*') if p.is_file()}
        with patch.object(studio, 'ChangeJournal', side_effect=AssertionError('History loaded')):
            result = self.request()
        self.assertEqual(result['render_sha256'], result['appearance_sha256'])
        self.assertIsNone(result['preview_id'])
        self.assertFalse(result['save_file_written']); self.assertFalse(result['history_written'])
        self.assertEqual(before, {p: p.read_bytes() for p in Path(self.fixture.temp.name).rglob('*') if p.is_file()})

    def test_stale_outfit_hash_lane_and_boolean_index_refuse_before_serializing(self):
        with patch.object(studio, '_capture_native_record', side_effect=AssertionError('Metadata read')):
            for value in (dict(outfit_id='2'), dict(outfit_index=True), dict(appearance_sha256='0'*64), dict(lane='wrong')):
                with self.subTest(value=value), self.assertRaises(ValueError): self.request(**value)

    def test_prepared_replacement_renders_after_fields_without_applying_or_rewriting_journal(self):
        self.fixture.backend._studio_casp_bytes = lambda _: __import__('casp_fixture').casp(body=7)
        message = test_studio.Message(self.fixture.sim.raw); message.outfits[1].parts.ids[0] = 1200
        self.fixture.sim.raw = message.SerializeToString(); self.status = self.fixture.request('studio_status')
        prepared = self.fixture.request('studio_part_preview', json.dumps(dict(target='0:7:0', source='1:7:0',
            lane=self.status['history_lane'], appearance_sha256=self.status['appearance_sha256'])))
        before = self.fixture.sim.raw
        files = {p: p.read_bytes() for p in Path(self.fixture.temp.name).rglob('*') if p.is_file()}
        result = self.request(preview_id=prepared['preview_id'])
        raw = studio.appearance.decode(result['fields']['__outfits__'])[1]
        self.assertEqual(test_studio.Message(raw).outfits[0].parts.ids[0], 1200)
        self.assertNotEqual(result['render_sha256'], result['appearance_sha256'])
        self.assertEqual(self.fixture.sim.raw, before)
        self.assertEqual(files, {p: p.read_bytes() for p in Path(self.fixture.temp.name).rglob('*') if p.is_file()})
        with self.assertRaisesRegex(ValueError, 'changed'): self.request(preview_id='0'*32)

    def test_serialization_change_in_an_unselected_occult_refuses_scene(self):
        self.fixture.stored_form()
        prior = self.fixture.backend._studio_native_record
        def corrupt(sim):
            result = prior(sim); self.fixture.vampire.skin_tone += 1; return result
        self.fixture.backend._studio_native_record = corrupt
        with self.assertRaisesRegex(ValueError, 'serialization changed'): self.request()
