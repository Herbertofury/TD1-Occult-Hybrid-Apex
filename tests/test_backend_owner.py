from pathlib import Path
import builtins
import importlib.util
import sys
import threading
import unittest
from unittest.mock import patch
import weakref

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
import td1_occult_hybrid_apex as backend


class BackendOwnerTests(unittest.TestCase):
    def test_external_import_does_not_start_server_or_touch_sims(self):
        self.assertFalse(backend._SERVER_RUNNING)
        self.assertFalse(backend._ALARM_READY)
        self.assertFalse(backend.run_action('status')['ok'])

    def test_alarm_owner_supports_actual_game_weakref_contract(self):
        self.assertIs(weakref.ref(backend._ALARM_OWNER)(), backend._ALARM_OWNER)

    def test_http_unready_path_cannot_fall_back_to_direct_sim_inspection(self):
        with patch.object(backend, 'run_action', side_effect=AssertionError('direct execution')):
            result = backend._submit_action('status', wait_seconds=0)
            self.assertFalse(result['ok'])
            self.assertEqual(result['state'], 'rejected')

    def test_worker_never_arms_alarm_even_when_sims_apis_exist(self):
        results = []
        with patch.object(backend, 'services', object()), patch.object(backend, 'alarms', object()):
            worker = threading.Thread(target=lambda: results.append(backend._setup_alarm()))
            worker.start()
            worker.join()
        self.assertEqual(results, [False])

    def test_worker_cannot_execute_dispatcher_with_services_available(self):
        results = []
        with patch.object(backend, 'services', object()), patch.object(backend, '_APEX_PRE_OWNER_RUN_ACTION', side_effect=AssertionError('legacy execution')):
            worker = threading.Thread(target=lambda: results.append(backend.run_action('status')))
            worker.start()
            worker.join()
        self.assertFalse(results[0]['ok'])

    def test_actual_compact_status_preserves_selected_identity_and_drift_summary(self):
        with patch.object(backend, '_list_saved_forms', return_value=[]):
            result = backend._overlay_compact_from_status_payload({'ok': True, 'data': {
                'sim_id': str(2**64-1), 'drift_warning_count': 2,
                'drift_warnings': [{'form': 'WEREWOLF'}, {'form': 'VAMPIRE'}]}})
        self.assertEqual(result['sim_id'], str(2**64-1))
        self.assertEqual(result['drift_warning_count'], 2)
        self.assertEqual(len(result['drift_warnings']), 2)

    def test_game_without_ctypes_keeps_verified_python_mask_operations(self):
        with patch.object(backend, 'ctypes', None), patch.object(backend, '_NATIVE', None):
            self.assertFalse(backend._load_native())
            self.assertIn('omits ctypes', backend._NATIVE_STATUS)
            self.assertEqual(backend._mask_add(3, 4), 7)
            self.assertEqual(backend._mask_remove(7, 2), 5)
            self.assertTrue(backend._mask_has(7, 4))

    def test_production_module_import_survives_actual_missing_ctypes_failure(self):
        original_import = builtins.__import__
        def game_import(name, *args, **kwargs):
            if name == 'ctypes':
                raise ModuleNotFoundError("No module named 'ctypes'")
            return original_import(name, *args, **kwargs)
        spec = importlib.util.spec_from_file_location('apex_missing_ctypes_fixture', backend.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.object(builtins, '__import__', side_effect=game_import), patch.object(backend.os, 'makedirs', side_effect=AssertionError('offline filesystem write')):
            spec.loader.exec_module(module)
        self.assertIsNone(module.ctypes)
        self.assertFalse(module._load_native())
        self.assertFalse(module._SERVER_RUNNING)
        self.assertIsNone(module._DATA_DIR)


if __name__ == '__main__':
    unittest.main()
