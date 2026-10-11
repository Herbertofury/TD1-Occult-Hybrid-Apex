import base64
import copy
import json
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sim_preview_service import Broker, snapshot, digest, canonical


def request():
    fields = {'__outfits__': {'kind': 'protobuf', 'value': 'EgA='}}
    native = b'\x09' + (123).to_bytes(8, 'little') + b'\x12\x00'
    appearance = digest(json.dumps(fields, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode())
    return dict(ok=True, sim_id='123', form=2, fields=fields, native_sim=base64.b64encode(native).decode(),
        native_sha256=digest(native), lane='456:2:123:2:full-appearance-v1', appearance_sha256=appearance,
        render_sha256=appearance, preview_id=None, outfit_index=0, outfit_id='789', appearance_source='test',
        save_guid='456', runtime_pid=1234, save_file_written=False, history_written=False)


class FakeWorker:
    calls = 0
    def assemble(self, value):
        self.calls += 1
        asset = b'encoded bounded texture'
        scene = dict(schema=1, ok=True, sim_id=value['sim_id'], form=value['form'], outfit_id=value['outfit_id'],outfit_index=value['outfit_index'],
            surfaces=[dict(image='body.png', image_sha256=digest(asset), parts=[])])
        manifest = canonical(scene)
        return dict(ok=True, disk_assets_written=False, manifest_json=manifest.decode(),
                    manifest_sha256=digest(manifest), assets={'body.png': base64.b64encode(asset).decode()})


class PreviewServiceTests(unittest.TestCase):
    def test_native_zero_outfit_id_requires_exact_ordinal_and_remains_distinct(self):
        first=request();first['outfit_id']='0';snapshot(first)
        second=copy.deepcopy(first);second['outfit_index']=1
        self.assertNotEqual(snapshot(first),snapshot(second))
        for field in ('sim_id','save_guid'):
            bad=copy.deepcopy(first);bad[field]='0'
            with self.assertRaises(ValueError):snapshot(bad)
    def await_job(self, broker, ident):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status = broker.status(ident)
            if status['state'] != 'assembling': return status
            time.sleep(.005)
        self.fail('Broker did not finish test job')

    def test_exact_snapshot_identity_and_typed_hash_are_required(self):
        snapshot(request())
        for change in (dict(form=3), dict(form=True), dict(outfit_index=True), dict(save_file_written=True),
            dict(sim_id='124'), dict(lane='457:2:123:2'), dict(native_sha256='0'*64),
            dict(render_sha256='0'*64), dict(preview_id='bad')):
            value = request(); value.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): snapshot(value)

    def test_same_request_assembles_once_and_assets_remain_only_in_bounded_memory(self):
        worker = FakeWorker(); broker = Broker(worker)
        ident = broker.prepare(request())['request_id']; ready = self.await_job(broker, ident)
        self.assertTrue(ready['ok']); self.assertFalse(ready['disk_assets_written'])
        self.assertEqual(broker.prepare(request())['request_id'], ident)
        self.assertEqual(worker.calls, 1)
        self.assertEqual(broker.asset(ready['scene_id'], 'body.png'), b'encoded bounded texture')
        self.assertEqual(broker.bytes, sum(len(v) for v in broker.scenes[ready['scene_id']]['assets'].values()))
        self.assertLessEqual(broker.bytes, broker.budget)

    def test_corrupt_asset_is_not_cached_or_replayed(self):
        worker = FakeWorker(); original = worker.assemble
        def corrupt(value):
            result = original(value); result['assets']['body.png'] = base64.b64encode(b'changed').decode(); return result
        worker.assemble = corrupt; broker = Broker(worker)
        ident = broker.prepare(request())['request_id']; failed = self.await_job(broker, ident)
        self.assertFalse(failed['ok']); self.assertIn('hash differs', failed['reason'])
        broker.prepare(request()); self.assertEqual(worker.calls, 1); self.assertEqual(broker.bytes, 0)

    def test_lru_eviction_cannot_return_an_old_ready_scene(self):
        broker = Broker(FakeWorker())
        broker.scenes['0'*64] = {'bytes': broker.budget, 'assets': {}}; broker.bytes = broker.budget
        broker.jobs['1'*64] = dict(ok=True, state='ready', scene_id='0'*64)
        ident = broker.prepare(request())['request_id']; self.await_job(broker, ident)
        self.assertNotIn('0'*64, broker.scenes); self.assertLessEqual(broker.bytes, broker.budget)
        self.assertEqual(broker.status('1'*64)['state'], 'evicted')

    def test_prepared_cc_fields_require_their_separate_render_hash(self):
        value = request(); value['fields']['skin_tone'] = dict(kind='value', value=321)
        with self.assertRaisesRegex(ValueError, 'render hash'): snapshot(value)
        value['render_sha256'] = digest(json.dumps(value['fields'], sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode())
        with self.assertRaisesRegex(ValueError, 'Unprepared'): snapshot(value)
        value['preview_id'] = 'a'*32; snapshot(value)
