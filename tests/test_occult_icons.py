"""Installed-resource identities, phone ownership, and bounded session caching."""
import base64
from pathlib import Path
import struct
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import occult_icons as icons
from apex_core import installed_icon_resources as installed


class OccultIconTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(icons, '_CACHE', None))
        self.identity = Obj(type=0x2f7d0004, group=0, instance=55)
        self.backend = Obj(_occult_by_name=lambda name: name,
            _get_tuning=lambda kind: Obj(occult_trait=Obj(icon=self.identity)))
        self.raw = b'\x89PNG\r\n\x1a\n' + b'\0\0\0\rIHDR' + struct.pack('>II', 64, 64) + b'\0' * 9

    def test_actual_trait_key_and_spellcaster_alias_no_guessed_artwork(self):
        self.assertIs(icons.key(self.backend, 'SPELLCASTER'), self.identity)
        for name in (None, 'HUMAN', 'unknown', 'Vampire'):
            self.assertIsNone(icons.key(self.backend, name))
        self.backend._get_tuning = lambda kind: None
        self.assertIsNone(icons.key(self.backend, 'FAIRY'))

    def test_all_native_phone_form_tags_retain_their_exact_owner(self):
        for lane, name in (('2', 'ALIEN'), ('4', 'VAMPIRE'), ('8', 'MERMAID'), ('16', 'WITCH'), ('32', 'WEREWOLF'), ('64', 'FAIRY')):
            for tag in ('page:cas_form:' + lane, 'page:cas_form:' + lane + ':hair:0',
                        'cas:decision:nonce:' + lane + ':accept-returned', 'cas:hair:nonce:' + lane + ':digest:0:0:11:keep',
                        'cas:hair-none:nonce:' + lane + ':digest', 'cas:hair-page:nonce:' + lane + ':digest:16'):
                self.assertEqual(icons.choice_name(tag), name)
        self.assertIsNone(icons.choice_name('page:cas_form:1'))
        self.assertIsNone(icons.choice_name('cas:info:VAMPIRE'))
        self.assertEqual(icons.choice_name('occult:add:ALIEN'), 'ALIEN')
        self.assertEqual(icons.choice_name('action:werewolf_human_on'), 'WEREWOLF')

    def test_png_bounds_reject_unknown_formats_and_unbounded_gpu_dimensions(self):
        for raw in (b'DDS '+self.raw, self.raw[:23], self.raw*5000,
                    self.raw[:16]+struct.pack('>II', 100000, 64)+self.raw[24:]):
            with self.assertRaises(ValueError): icons.png(raw)

    def test_cached_artwork_reads_native_keys_once_and_returns_detached_receipts(self):
        loader = Mock(return_value=Obj(load_raw=Mock(return_value=self.raw)))
        with patch.dict(sys.modules, {'sims4': Obj(resources=Obj(ResourceLoader=loader))}):
            first = icons.catalog(self.backend)
            self.assertEqual(loader.call_count, 6)
            self.assertTrue(all(row['status'] == 'resolved' for row in first['items']))
            self.assertEqual(base64.b64decode(first['items'][0]['image_base64']), self.raw)
            first['items'][0]['status'] = 'changed-by-caller'
            self.assertEqual(icons.catalog(self.backend)['items'][0]['status'], 'resolved')
            self.assertEqual(loader.call_count, 6)

    def test_missing_artwork_is_explicit_and_other_controls_remain_available(self):
        loader = Mock(return_value=Obj(load_raw=Mock(return_value=b'DDS unsupported')))
        with patch.dict(sys.modules, {'sims4': Obj(resources=Obj(ResourceLoader=loader))}):
            result = icons.catalog(self.backend)
        self.assertEqual(len(result['items']), 6)
        self.assertTrue(all(row['status'] == 'unavailable' and 'reason' in row and 'image_base64' not in row for row in result['items']))

    def dst(self):
        raw = bytearray(144); raw[:8] = b'DDS |\0\0\0'
        struct.pack_into('<II', raw, 12, 4, 4); struct.pack_into('<I', raw, 28, 1)
        struct.pack_into('<I', raw, 76, 32); raw[84:88] = b'DST5'
        return bytes(raw)

    def test_actual_png_reference_alias_uses_same_instance_and_group_of_installed_dst(self):
        dst = self.dst(); aliases = []
        def key(kind, instance, group):
            aliases.append((kind, instance, group)); return Obj(type=kind, instance=instance, group=group)
        def loader(identity):
            return Obj(load_raw=lambda **kw: dst if identity.type == 0x00b2d882 else None)
        with patch.dict(sys.modules, {'sims4': Obj(resources=Obj(ResourceLoader=loader, Key=key))}):
            result = icons.catalog(self.backend)
        self.assertEqual(aliases, [(0x00b2d882, 55, 0)] * 6)
        self.assertTrue(all(row['format'] == 'dst5' and row['status'] == 'resolved' for row in result['items']))
        self.assertEqual(result['items'][0]['reference_tgi'], '2F7D0004:00000000:0000000000000037')
        self.assertEqual(result['items'][0]['resource_tgi'], '00B2D882:00000000:0000000000000037')

    def test_dst_rejects_truncation_mips_unknown_fourcc_and_impossible_dimensions(self):
        good = self.dst(); self.assertEqual(icons.image_metadata(good)['format'], 'dst5')
        for offset, change in ((28, struct.pack('<I', 2)), (16, struct.pack('<I', 512)), (84, b'DST3')):
            bad = bytearray(good); bad[offset:offset+len(change)] = change
            with self.assertRaises(ValueError): icons.image_metadata(bytes(bad))
        with self.assertRaises(ValueError): icons.image_metadata(good[:-1])

    def test_native_unshuffled_bc3_variant_is_explicitly_classified(self):
        raw=bytearray(self.dst());raw[84:88]=b'DXT5'
        self.assertEqual(icons.image_metadata(bytes(raw))['format'],'dxt5')

    def test_missing_native_bytes_start_one_worker_and_publish_only_complete_art(self):
        loader = Mock(return_value=Obj(load_raw=lambda **kw: None))
        worker = Mock()
        resources = Obj(ResourceLoader=loader, Key=lambda t, i, g: Obj(type=t, instance=i, group=g))
        # The game exports paths as a top-level module, never sims4.paths.
        with patch.dict(sys.modules, {'sims4': Obj(resources=resources), 'paths': Obj(DLL_PATH='actual path')}), \
             patch.object(installed, 'game_root', return_value=Path('installed game')), \
             patch.object(icons.threading, 'Thread', return_value=worker) as thread:
            first = icons.catalog(self.backend)
            self.assertTrue(first['loading'])
            self.assertTrue(all(row['status'] == 'loading' for row in first['items']))
            icons.catalog(self.backend)
            thread.assert_called_once()
            worker.start.assert_called_once()
            args = thread.call_args.kwargs['args']
            with patch.object(installed, 'read', return_value={(0x00b2d882, 0, 55):
                    dict(raw=self.dst(), sources=[dict(container='exact installed container')])}):
                thread.call_args.kwargs['target'](*args)
            final = icons.catalog(self.backend)
            self.assertFalse(final['loading'])
            self.assertTrue(all(row['status'] == 'resolved' for row in final['items']))
            self.assertTrue(all(row['status'] == 'loading' for row in first['items']))
            self.assertEqual(loader.call_count, 12)

    def test_worker_conflict_or_failure_never_returns_an_image_or_restarts_forever(self):
        rows = [dict(name='ALIEN', status='loading')]
        for result in ({}, {(1, 0, 55): dict(conflict=True)}):
            with patch.object(installed, 'read', return_value=result):
                icons._installed_worker(Path('game'), [(0, (1, 0, 55))], [dict(row) for row in rows])
            self.assertFalse(icons._CACHE['loading'])
            self.assertEqual(icons._CACHE['items'][0]['status'], 'unavailable')
            self.assertNotIn('image_base64', icons._CACHE['items'][0])
        with patch.object(installed, 'read', side_effect=OSError('no access')):
            icons._installed_worker(Path('game'), [(0, (1, 0, 55))], rows)
        self.assertEqual(icons._CACHE['items'][0]['reason'], 'no access')
