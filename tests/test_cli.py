from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli


class CliTests(unittest.TestCase):
    def test_identity_uses_exact_native_pid_observation_without_process_enumeration(self):
        journal = {'token': 'a' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'b' * 64}]}
        identity = {'test_token': 'a' * 32, 'script_sha256': 'b' * 64, 'pid': 42}
        with patch.object(apex_cli, 'require_isolated') as isolated, \
                patch.object(apex_cli.reusable_profile, 'load', return_value=(None, journal, None, None)), \
                patch.object(apex_cli.game_launch, 'observe_game_process', return_value={'Id': 42, 'Path': r'C:\Game\Bin\TS4_x64.exe'}) as observe, \
                patch.object(apex_cli.game_launch, 'running_game_processes', side_effect=AssertionError('slow enumeration')):
            self.assertEqual(apex_cli.verified_identity('state', transport=lambda *_: identity), identity)
        isolated.assert_called_once_with('state')
        observe.assert_called_once_with(42)

    def test_invalid_bridge_pid_never_reaches_native_process_observation(self):
        journal = {'token': 'a' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'b' * 64}]}
        for pid in (None, True, False, 0, -1, 1 << 32, 42.0, '42'):
            identity = {'test_token': 'a' * 32, 'script_sha256': 'b' * 64, 'pid': pid}
            with self.subTest(pid=pid), patch.object(apex_cli, 'require_isolated'), \
                    patch.object(apex_cli.reusable_profile, 'load', return_value=(None, journal, None, None)), \
                    patch.object(apex_cli.game_launch, 'observe_game_process') as observe:
                with self.assertRaisesRegex(ValueError, 'Windows process identity'):
                    apex_cli.verified_identity('state', transport=lambda *_: identity)
                observe.assert_not_called()

    def test_wrong_pid_reused_non_sims_and_exited_observation_refuse_identity(self):
        journal = {'token': 'a' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'b' * 64}]}
        identity = {'test_token': 'a' * 32, 'script_sha256': 'b' * 64, 'pid': 42}
        for observation in (None, {'Id': 43, 'Path': 'TS4_x64.exe'}, {'Id': 42, 'Path': 'EADesktop.exe'},
                            {'Id': 42, 'Path': None}):
            with self.subTest(observation=observation), patch.object(apex_cli, 'require_isolated'), \
                    patch.object(apex_cli.reusable_profile, 'load', return_value=(None, journal, None, None)), \
                    patch.object(apex_cli.game_launch, 'observe_game_process', return_value=observation):
                with self.assertRaisesRegex(ValueError, 'observed Sims'):
                    apex_cli.verified_identity('state', transport=lambda *_: identity)

    def test_identity_approval_is_rechecked_for_every_request_without_cache(self):
        journal = {'token': 'a' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'b' * 64}]}
        bridge = [{'test_token': 'a' * 32, 'script_sha256': 'b' * 64, 'pid': 42, 'core_tick_ready': True},
                  {'test_token': 'wrong token', 'script_sha256': 'b' * 64, 'pid': 42, 'core_tick_ready': True}]
        commands = []
        def transport(path, query=None):
            if path == '/api/bridge':
                return bridge.pop(0)
            commands.append(query)
            return {'ok': True}
        with patch.object(apex_cli, 'require_isolated') as isolated, \
                patch.object(apex_cli.reusable_profile, 'load', return_value=(None, journal, None, None)) as load, \
                patch.object(apex_cli.game_launch, 'observe_game_process', return_value={'Id': 42, 'Path': 'TS4_x64.exe'}) as observe:
            self.assertTrue(apex_cli.owned_request('state', 'cas_ui_diagnostics', transport=transport)['ok'])
            with self.assertRaisesRegex(ValueError, 'does not match'):
                apex_cli.owned_request('state', 'cas_ui_diagnostics', transport=transport)
        self.assertEqual(isolated.call_count, 2)
        self.assertEqual(load.call_count, 2)
        self.assertEqual(observe.call_count, 1)
        self.assertEqual(len(commands), 1)

    def test_native_cas_view_uses_fixed_native_selection_without_pointer_input(self):
        for operation, tab in [('open-cas-history','cas_history'),('open-cas-parts','cas_parts')]:
            args = apex_cli.parser().parse_args(['studio',operation,'--state','state.json','--sim-id','772674414928396571'])
            with patch.object(apex_cli,'require_isolated'), \
                    patch.object(apex_cli.reusable_profile,'load',return_value=(None,{'token':'a'*32},None,None)), \
                    patch.object(apex_cli,'owned_request',return_value={'ok':True}) as request:
                self.assertTrue(apex_cli.execute(args)['ok'])
            self.assertEqual(request.call_args.args[1], 'test_studio_ui')
            self.assertEqual(json.loads(request.call_args.kwargs['value'])['value'],
                             {'sim_id':'772674414928396571','tab':tab})

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

    def test_lost_response_polls_same_identity_without_resubmitting(self):
        journal = {'token': 'a' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'b' * 64}]}
        calls = []
        def transport(path, query=None):
            calls.append((path, query))
            if path == '/api/bridge':
                return {'test_token': 'a' * 32, 'script_sha256': 'b' * 64, 'alarm_ready': True, 'pid': 42}
            if path == '/api/command':
                raise OSError('lost response')
            return {'state': 'completed', 'result': {'ok': True, 'observed': 1}}
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli.reusable_profile, 'load', return_value=(None, journal, None, None)), patch.object(apex_cli.game_launch, 'observe_game_process', return_value={'Id': 42, 'Path': 'TS4_x64.exe'}):
            result = apex_cli.owned_request('state', 'test_create_sim', transport=transport)
        self.assertTrue(result['ok'])
        commands = [row for row in calls if row[0] == '/api/command']
        polls = [row for row in calls if row[0] == '/api/requests/status']
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][1]['request_id'], polls[0][1]['request_id'])

    def test_unknown_completion_never_counts_as_success(self):
        ticks = [0]
        result = apex_cli.poll_request('a' * 32, 1, transport=lambda *a, **k: {'state': 'unknown'},
            monotonic=lambda: ticks[0], pause=lambda seconds: ticks.__setitem__(0, ticks[0] + seconds))
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'], 'unresolved')

    def test_mismatched_runtime_cannot_execute_any_command(self):
        journal = {'token': 'a' * 32, 'artifacts': [{'name': 'ApexOccultHybrid.ts4script', 'sha256': 'b' * 64}]}
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli.reusable_profile, 'load', return_value=(None, journal, None, None)), patch.object(apex_cli, 'get') as transport:
            with self.assertRaises(ValueError):
                apex_cli.owned_request('state', 'test_create_sim', transport=lambda *a, **k: {'test_token': 'wrong'})
            transport.assert_not_called()

    def test_native_click_cannot_reach_transport_when_foreground_focus_is_refused(self):
        identity = {'pid': 42, 'native_cli_available': True}
        import game_window
        with patch.object(apex_cli, 'verified_identity', return_value=identity), \
                patch.object(apex_cli.reusable_profile, 'load', return_value=(None, {'token': 'a' * 32}, None, None)), \
                patch.object(game_window, 'focus', return_value={'ok': False, 'foreground_verified': False}), \
                patch.object(apex_cli, 'get') as transport:
            result = apex_cli.owned_request('state', 'test_input', transport=transport)
        self.assertFalse(result['input_submitted'])
        transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()
