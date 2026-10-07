from pathlib import Path
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


if __name__ == '__main__':
    unittest.main()
