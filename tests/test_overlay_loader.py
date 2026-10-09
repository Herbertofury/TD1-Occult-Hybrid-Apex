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

    def test_input_rejects_unbounded_or_malformed_values_before_native_binding(self):
        with patch.object(loader, '_CALLS', object()), patch.object(loader, '_bind_input') as native:
            for value in ({'arbitrary': 'function'}, {'command': 1, 'x': True, 'y': 0, 'width': 100, 'height': 100},
                          {'command': 1, 'x': 0, 'y': 0, 'width': 8193, 'height': 100}):
                with self.assertRaises(ValueError):
                    loader.input_event(self.module, 'unused', value)
            native.assert_not_called()

    def test_optional_metrics_preserve_hwnd_bits_without_input_or_old_export_requirement(self):
        class Integer:
            _type_ = 'i'
        values = [1278, 1376, -4, 10, 34600, 34600, -2147483647, -2147483647, 1]
        class Function:
            def __init__(self, symbol):
                self.name = symbol[0]
            def __call__(self, index):
                return values[index]
        class Native:
            _SimpleCData = Integer
            CFuncPtr = Function
            FUNCFLAG_STDCALL = 0
        metrics = loader._input_metrics(Native, 123)
        self.assertTrue(metrics['available'])
        self.assertEqual(metrics['overlay_hwnd'], 0x80000001)
        self.assertEqual(metrics['screen_x'], -4)
        self.assertTrue(metrics['root_match'])
        class Missing(Function):
            def __init__(self, symbol):
                raise AttributeError('missing export')
        with patch.object(Native, 'CFuncPtr', Missing):
            self.assertEqual(loader._input_metrics(Native, 123), {'available': False})

    def test_status_updates_startup_runtime_evidence_only_after_renderer_and_frame(self):
        native = {'status': 2, 'frames': 0}
        calls = {'ApexOverlayStatus': lambda: native['status'],
                 'ApexOverlayRenderedFrames': lambda: native['frames'],
                 'ApexOverlayVisible': lambda: 0, 'ApexOverlayToggleEvents': lambda: 0,
                 'ApexCaptureCompleted': lambda: 0}
        startup = {'ok': True, 'runtime_verified': False, 'message': 'F11 overlay hook is ready; press F11 in the game window.'}
        with patch.object(loader, '_CALLS', calls), patch.object(loader, '_STATUS', startup):
            status = loader.status()
            self.assertFalse(status['runtime_verified'])
            self.assertIn('visible overlay frame', status['message'])
            native['status'] = 3
            status = loader.status()
            self.assertFalse(status['runtime_verified'])
            self.assertIn('first submitted frame', status['message'])
            native['frames'] = 7
            status = loader.status()
            self.assertTrue(status['runtime_verified'])
            self.assertIn('UI actions require their own acknowledgements', status['message'])
            native['status'] = 2  # Historical frames alone do not verify the current renderer.
            self.assertFalse(loader.status()['runtime_verified'])
        self.assertFalse(startup['runtime_verified'])  # No stale cached status is mutated.

    def test_status_preserves_loader_failure_and_does_not_claim_unloaded_runtime(self):
        failure = {'ok': False, 'message': 'F11 loader: build mismatch', 'runtime_verified': False}
        with patch.object(loader, '_CALLS', None), patch.object(loader, '_STATUS', failure):
            self.assertEqual(loader.status(), failure)
        calls = {name: lambda: 3 for name in ('ApexOverlayStatus', 'ApexOverlayRenderedFrames',
                    'ApexOverlayVisible', 'ApexOverlayToggleEvents', 'ApexCaptureCompleted')}
        with patch.object(loader, '_CALLS', calls), patch.object(loader, '_STATUS', failure):
            status = loader.status()
            self.assertFalse(status['runtime_verified'])
            self.assertEqual(status['message'], failure['message'])


if __name__ == '__main__':
    unittest.main()
