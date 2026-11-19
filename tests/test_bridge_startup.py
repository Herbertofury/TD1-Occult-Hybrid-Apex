import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.bridge_startup import StartupRetry


class BridgeStartupTests(unittest.TestCase):
    def test_only_known_windows_refusals_arm_spaced_bounded_retries(self):
        retry = StartupRetry()
        for code in (None, 22, 10049):
            retry.arm(10, code)
            self.assertFalse(retry.take_due(20))
        retry.arm(10, 10013)
        self.assertFalse(retry.take_due(11.999))
        self.assertTrue(retry.take_due(12))
        self.assertFalse(retry.take_due(12.01))
        for now in (14, 16, 18, 20):
            self.assertTrue(retry.take_due(now))
        self.assertFalse(retry.take_due(22))
        self.assertFalse(retry.take_due(100))

    def test_expired_startup_or_explicit_stop_never_restarts_listener(self):
        retry = StartupRetry()
        retry.arm(0, 10048)
        self.assertFalse(retry.take_due(16))
        retry.arm(20, 10013)
        retry.cancel()
        self.assertFalse(retry.take_due(23))

    def test_success_cancels_future_attempts(self):
        retry = StartupRetry()
        retry.arm(0, 10013)
        self.assertTrue(retry.take_due(2))
        retry.cancel()
        self.assertFalse(retry.take_due(4))


if __name__ == '__main__':
    unittest.main()
