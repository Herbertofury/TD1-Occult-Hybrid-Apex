from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli
import ea_permission
import ea_permission_broker as broker
import game_launch


class PermissionLaunchTests(unittest.TestCase):
    def invoke(self, permission, explicit, context_error=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / 'EADesktop.log'
            log.write_text('prior launch evidence')
            plan = {'ok': True, 'url': 'origin2://game/launch?offerIds=1015806&autoDownload=0',
                    'account_launch_identity': {'log': str(log)}}
            os_api = SimpleNamespace(name='nt', startfile=Mock())
            key = Mock()
            key.__enter__ = Mock(return_value=key)
            key.__exit__ = Mock(return_value=None)
            registry = SimpleNamespace(HKEY_CLASSES_ROOT=object(), OpenKey=Mock(return_value=key),
                QueryValueEx=Mock(return_value=('"EALauncher.exe" "%1"', None)))
            with patch.object(game_launch, 'launch_plan', return_value=plan), \
                 patch.object(game_launch.test_profile, 'require_closed') as closed, \
                 patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': True}), \
                 patch.object(game_launch, 'running_game_processes', return_value=[]), \
                 patch.object(game_launch, 'observe_start', return_value={'process_started': False}), \
                 patch.object(game_launch, 'os', os_api), patch.dict(sys.modules, {'winreg': registry}), \
                 patch.object(game_launch.time, 'sleep'), \
                 patch.object(ea_permission, 'acknowledge', return_value=permission), \
                 patch.object(broker, 'wait_launch_context', return_value={'trusted': 'fixture'}, side_effect=context_error) as context, \
                 patch.object(broker, 'elevate_once', return_value={'ok': True, 'acknowledged': True, 'game_start_verified': False}) as elevate:
                result = game_launch.launch(root / 'Game', root / 'state.json', execute=True,
                                           elevate_permission_once=explicit)
            self.assertEqual(os_api.startfile.call_args.args, (plan['url'],))
            self.assertEqual(os_api.startfile.call_count, 1)
            closed.assert_called_once()
            return result, context, elevate

    def test_default_and_already_acknowledged_launch_never_elevate(self):
        for permission, explicit in (({'acknowledged': False}, False), ({'acknowledged': True}, True)):
            result, context, elevate = self.invoke(permission, explicit)
            context.assert_not_called()
            elevate.assert_not_called()
            self.assertNotIn('ea_permission_broker', result)

    def test_explicit_helper_follows_single_handoff_and_passes_trusted_context(self):
        result, context, elevate = self.invoke({'acknowledged': False}, True)
        context.assert_called_once()
        self.assertGreaterEqual(context.call_args.args[2], 1)
        self.assertEqual(elevate.call_args.kwargs, {'launch_context': {'trusted': 'fixture'}})
        self.assertEqual(context.call_args.args[1], result['handoff_evidence']['timestamp'])
        self.assertEqual(context.call_args.args[2], result['handoff_evidence']['ea_log_start_offset'])
        self.assertTrue(result['handoff_evidence']['utc'].endswith('Z'))
        self.assertEqual(result['handoff_evidence']['permission_context_observation_seconds'], 10)
        self.assertTrue(result['ea_permission_broker']['acknowledged'])
        self.assertFalse(result['launched'])
        self.assertFalse(result['ok'])  # A permission receipt cannot prove game start.

    def test_unbound_launch_context_refuses_elevation_without_retry(self):
        result, _context, elevate = self.invoke({'acknowledged': False}, True, ValueError('another game request'))
        elevate.assert_not_called()
        self.assertFalse(result['ea_permission_broker']['acknowledged'])
        self.assertIn('another game', result['ea_permission_broker']['message'])

    def test_cli_flag_defaults_false_and_only_forwards_an_explicit_request(self):
        arguments = ['launch', '--game-root', 'fixture-game', '--state', 'fixture-state']
        for extra, expected in (([], False), (['--elevate-permission-once'], True)):
            parsed = apex_cli.parser().parse_args(arguments + extra)
            with patch.object(game_launch, 'launch', return_value={'ok': True}) as launch:
                apex_cli.execute(parsed)
            self.assertEqual(launch.call_args.kwargs['elevate_permission_once'], expected)


if __name__ == '__main__':
    unittest.main()
