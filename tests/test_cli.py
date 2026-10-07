from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli


class CliTests(unittest.TestCase):
    def test_not_ready_bridge_never_counts_as_runtime_success(self):
        ticks = [0]
        def clock():
            return ticks[0]
        def pause(seconds):
            ticks[0] += seconds
        result = apex_cli.wait_for_bridge(2, probe=lambda *a, **k: {'ok': True, 'alarm_ready': False}, monotonic=clock, pause=pause)
        self.assertFalse(result['ok'])

    def test_ready_bridge_returns_without_retrying_game_commands(self):
        result = apex_cli.wait_for_bridge(2, probe=lambda *a, **k: {'ok': True, 'alarm_ready': True})
        self.assertTrue(result['alarm_ready'])

    def test_command_refuses_nonisolated_profile_before_transport(self):
        args = apex_cli.parser().parse_args(['request', 'add', '--state', 'fake.json'])
        with patch.object(apex_cli.test_profile, 'status', return_value={'ready_to_launch': False}), patch.object(apex_cli, 'get') as transport:
            with self.assertRaisesRegex(ValueError, 'isolated'):
                apex_cli.execute(args)
            transport.assert_not_called()

    def test_remote_redirect_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'redirects'):
            apex_cli.LocalRedirectGuard().redirect_request(None, None, 302, '', {}, 'https://example.invalid')


if __name__ == '__main__':
    unittest.main()
