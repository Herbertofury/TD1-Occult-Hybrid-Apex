import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import overlay_loader as loader


class OverlayLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.apex = Path(self.temp.name) / 'Mods' / 'Apex'
        (self.apex / 'Native').mkdir(parents=True)
        self.archive = self.apex / 'ApexOccultHybrid.ts4script'
        self.archive.write_bytes(b'archive fixture')
        self.dll = self.apex / 'Native' / 'ApexOverlay.dll'
        self.dll.write_bytes(b'MZ' + bytes(8190))
        self.manifest = self.dll.parent / 'overlay-manifest.json'
        self.manifest.write_text(json.dumps({'schema': 1, 'protocol': 1,
            'file': self.dll.name, 'sha256': hashlib.sha256(self.dll.read_bytes()).hexdigest()}))
        self.module = str(self.archive / 'td1_occult_hybrid_apex.pyc')

    def test_shipped_archive_and_matching_sidecar_are_resolved_without_loading(self):
        path, info = loader.sidecar_paths(self.module)
        self.assertEqual(path, self.dll)
        self.assertEqual(info['protocol'], 1)

    def test_tamper_and_protocol_mismatch_are_rejected_before_native_calls(self):
        self.dll.write_bytes(b'MZ' + bytes(8191))
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            loader.sidecar_paths(self.module)
        with patch.object(loader, '_game_ctypes', side_effect=AssertionError('must not load')):
            result = loader.start(self.module, 'unused')
            self.assertFalse(result['ok'])
        info = json.loads(self.manifest.read_text()); info['protocol'] = 2
        self.manifest.write_text(json.dumps(info))
        with self.assertRaisesRegex(ValueError, 'protocol'):
            loader.sidecar_paths(self.module)

    def test_source_and_wrong_mod_directory_and_protected_profile_refused(self):
        with self.assertRaisesRegex(ValueError, 'loose source'):
            loader.sidecar_paths(__file__)
        with self.assertRaisesRegex(ValueError, 'protected original'):
            loader.sidecar_paths(str(Path(self.temp.name) / 'The Sims 4 DO NOT FUCKING TOUCH!!!' /
                'Mods' / 'Apex' / 'ApexOccultHybrid.ts4script' / 'td1_occult_hybrid_apex.pyc'))
        self.apex.rename(self.apex.with_name('Other'))
        with self.assertRaisesRegex(ValueError, 'Mods/Apex'):
            loader.sidecar_paths(self.module.replace(str(self.apex), str(self.apex.with_name('Other'))))

    def test_config_can_disable_autostart_without_a_native_load(self):
        self.assertTrue(loader.auto_start_enabled(self.module))
        (self.dll.parent / 'ApexOverlay.ini').write_text('[Overlay]\nAutoStart=0\nToggleKey=F11\n')
        self.assertFalse(loader.auto_start_enabled(self.module))

    def test_absent_dll_or_unbounded_manifest_fails_before_load(self):
        self.manifest.write_bytes(bytes(16385))
        with self.assertRaisesRegex(ValueError, 'bound'):
            loader.sidecar_paths(self.module)
        self.dll.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            loader.sidecar_paths(self.module)

    def test_linked_sidecar_is_never_followed(self):
        original = self.dll.with_name('other.dll'); original.write_bytes(self.dll.read_bytes())
        self.dll.unlink()
        try:
            self.dll.symlink_to(original)
        except OSError:
            self.skipTest('Host does not permit symlink creation.')
        with self.assertRaisesRegex(ValueError, 'Linked'):
            loader.sidecar_paths(self.module)

    def test_cached_native_handle_cannot_be_relabelled_as_a_new_build(self):
        with patch.object(loader, '_HANDLE', object()), patch.object(loader, '_LOADED_SHA', 'f' * 64), \
             patch.object(loader, '_LOADED_PATH', str(self.dll)), \
             patch.object(loader, '_game_ctypes', side_effect=AssertionError('must not load')):
            result = loader.start(self.module, 'unused')
        self.assertFalse(result['ok'])
        self.assertIn('already loaded', result['message'])


if __name__ == '__main__':
    unittest.main()
