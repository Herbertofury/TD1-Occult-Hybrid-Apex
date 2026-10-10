from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli


class CliTests(unittest.TestCase):
    def test_studio_open_and_failed_preview_output_are_durable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); state = root/'session.json'
            for operation, value in (('open-parts', {'ok': True, 'selected_tab': 'parts'}),
                                     ('part-preview', {'ok': False, 'message': 'Stale appearance'})):
                output = root/(operation + '.json')
                args = apex_cli.parser().parse_args(['studio', operation, '--state', str(state),
                    '--sim-id', '7', '--output', str(output)])
                with patch.object(apex_cli, 'require_isolated'), \
                        patch.object(apex_cli.reusable_profile, 'load', return_value=(state, {'token': 'b'*32}, root/'test', root/'original')), \
                        patch.object(apex_cli, 'owned_request', return_value=value) as request:
                    result = apex_cli.execute(args)
                self.assertEqual(json.loads(output.read_bytes()), value)
                self.assertEqual(result['ok'], value['ok']); request.assert_called_once()

    def test_studio_output_validation_precedes_appearance_mutation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); state = root/'session.json'; output = root/'proof.json'; output.write_bytes(b'prior')
            for target in (output, root/'original'/'no-write.json'):
                args = apex_cli.parser().parse_args(['studio', 'apply', '--state', str(state),
                    '--sim-id', '7', '--value', 'pending-token', '--output', str(target)])
                with patch.object(apex_cli, 'require_isolated'), \
                        patch.object(apex_cli.reusable_profile, 'load', return_value=(state, {'token': 'b'*32}, root/'test', root/'original')), \
                        patch.object(apex_cli, 'owned_request') as request, self.assertRaises(ValueError):
                    apex_cli.execute(args)
                request.assert_not_called()
            self.assertEqual(output.read_bytes(), b'prior')

    def test_submission_evidence_failure_cannot_submit_or_retry_command(self):
        for native in (False, True):
            identity = {'pid': 42, 'alarm_ready': True, 'native_cli_available': native}
            action = 'overlay_status' if native else 'cas_bank_commit'
            def observer(_action, _uuid):
                raise OSError('Durable evidence unavailable')
            with self.subTest(native=native), patch.object(apex_cli, 'verified_identity', return_value=identity), \
                    patch.object(apex_cli.reusable_profile, 'load', return_value=(None, {'token': 'a'*32}, None, None)):
                calls = []
                with self.assertRaises(OSError):
                    apex_cli.owned_request('state', action, submission_observer=observer,
                        transport=lambda *a, **k: calls.append(a) or {'ok': True})
                self.assertEqual(calls, [])

    def test_snapshot_output_is_written_and_failure_receipt_is_retained(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); state = root/'session.json'; output = root/'proof.json'
            args = apex_cli.parser().parse_args(['game', 'snapshot', '--state', str(state), '--sim-id', '7', '--output', str(output)])
            value = {'ok': False, 'request_id': 'a'*32, 'message': 'Readonly snapshot failed'}
            with patch.object(apex_cli, 'require_isolated'), \
                    patch.object(apex_cli.reusable_profile, 'load', return_value=(state, {'token': 'b'*32}, root/'test', root/'original')), \
                    patch.object(apex_cli, 'owned_request', return_value=value) as request:
                result = apex_cli.execute(args)
            self.assertFalse(result['ok']); self.assertEqual(json.loads(output.read_bytes()), value)
            self.assertEqual(result['proof'], str(output)); request.assert_called_once()

    def test_direct_input_output_refuses_existing_file_before_submission(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); state = root/'session.json'; output = root/'proof.json'; output.write_bytes(b'prior')
            args = apex_cli.parser().parse_args(['game', 'click', '--state', str(state), '--x', '3', '--y', '4',
                '--width', '100', '--height', '100', '--output', str(output)])
            with patch.object(apex_cli, 'require_isolated'), \
                    patch.object(apex_cli.reusable_profile, 'load', return_value=(state, {'token': 'b'*32}, root/'test', root/'original')), \
                    patch.object(apex_cli, 'owned_request') as request, self.assertRaises(ValueError):
                apex_cli.execute(args)
            self.assertEqual(output.read_bytes(), b'prior'); request.assert_not_called()

    def test_profile_output_cannot_write_or_submit_native_command(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve(); state = root/'session.json'; original = root/'original'; original.mkdir()
            args = apex_cli.parser().parse_args(['game', 'play', '--state', str(state), '--output', str(original/'untouched.json')])
            with patch.object(apex_cli, 'require_isolated'), \
                    patch.object(apex_cli.reusable_profile, 'load', return_value=(state, {'token': 'b'*32}, root/'test', original)), \
                    patch.object(apex_cli, 'owned_request') as request, self.assertRaises(ValueError):
                apex_cli.execute(args)
            request.assert_not_called(); self.assertEqual(list(original.iterdir()), [])

    def test_early_core_only_allows_readonly_native_snapshot_not_gameplay(self):
        identity = {'pid': 42, 'core_tick_ready': True, 'alarm_ready': False}
        with patch.object(apex_cli, 'verified_identity', return_value=identity):
            for action in ('test_snapshot', 'test_status'):
                self.assertTrue(apex_cli.owned_request('state', action,
                    transport=lambda _path, _query=None: {'ok': True})['ok'])
            for action in ('test_play', 'test_create_sim', 'test_save'):
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'Load the disposable household'):
                    apex_cli.owned_request('state', action,
                        transport=lambda _path, _query=None: self.fail('Gameplay transport before loaded household'))

    def test_exact_load_cli_uses_named_native_target_and_new_proof(self):
        args = apex_cli.parser().parse_args(['game', 'load', '--state', 'state.json', '--sim-id', '7',
            '--household-id', '8', '--save-guid', '9', '--slot-id', '2', '--slot-name', 'My test',
            '--expected-save-sha256', 'b' * 64, '--output', 'load-proof.json'])
        import game_load
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity', return_value={'pid': 42}), \
                patch.object(game_load, 'observe', return_value={'ok': True}) as observe:
            self.assertTrue(apex_cli.execute(args)['ok'])
        self.assertEqual(observe.call_args.args[4:], ('7', '8', '9', 2, 'My test', 'b' * 64))

    def test_equipped_metadata_pages_use_exact_form_envelope_without_pointer_input(self):
        page = json.dumps({'lane': '123:2:7:4:full-appearance-v1', 'appearance_sha256': 'b' * 64,
                           'runtime_pid': 42, 'cursor': 8, 'limit': 8, 'outfit_index': 0})
        args = apex_cli.parser().parse_args(['studio', 'items', '--state', 'state.json', '--sim-id', '7',
                                             '--form', '4', '--value', page])
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'owned_request', return_value={'ok': True}) as request:
            self.assertTrue(apex_cli.execute(args)['ok'])
        self.assertEqual(request.call_args.args, (Path('state.json'), 'studio_items', '7'))
        self.assertEqual(json.loads(request.call_args.kwargs['value']), {'form': 4, 'value': page})

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

    def test_one_pre_input_focus_helper_success_rechecks_identity_before_transport(self):
        identity = {'pid': 42, 'native_cli_available': True, 'test_token': 'a' * 32, 'script_sha256': 'b' * 64}
        import game_window, game_focus
        with patch.object(apex_cli, 'verified_identity', return_value=identity) as verify, \
                patch.object(apex_cli.reusable_profile, 'load', return_value=(None, {'token': 'a' * 32}, None, None)), \
                patch.object(game_window, 'focus', return_value={'ok': False, 'foreground_verified': False}), \
                patch.object(game_focus, 'focus_for_input', return_value={'ok': True, 'foreground_verified': True}) as helper, \
                patch.object(apex_cli, 'get', return_value={'ok': True}) as transport, \
                patch.object(apex_cli.time, 'sleep'):
            self.assertTrue(apex_cli.owned_request('state', 'test_input', transport=transport)['ok'])
        helper.assert_called_once(); self.assertEqual(verify.call_count, 2)
        transport.assert_called_once(); self.assertEqual(transport.call_args.args[0], '/api/native')

    def test_bridge_change_after_focus_cannot_submit_native_input(self):
        identity = {'pid': 42, 'native_cli_available': True, 'test_token': 'a' * 32, 'script_sha256': 'b' * 64}
        import game_window
        with patch.object(apex_cli, 'verified_identity', side_effect=[identity, dict(identity, pid=43)]), \
                patch.object(apex_cli.reusable_profile, 'load', return_value=(None, {'token': 'a' * 32}, None, None)), \
                patch.object(game_window, 'focus', return_value={'ok': True, 'foreground_verified': True}), \
                patch.object(apex_cli, 'get') as transport:
            with self.assertRaisesRegex(ValueError, 'identity changed after focus'):
                apex_cli.owned_request('state', 'test_input', transport=transport)
        transport.assert_not_called()

    def test_elevated_game_input_is_submitted_once_in_fixed_helper_without_host_replay(self):
        import game_focus
        identity = {'pid': 42, 'native_cli_available': True, 'test_token': 'a' * 32, 'script_sha256': 'b' * 64}
        with patch.object(apex_cli, 'verified_identity', return_value=identity), \
                patch.object(apex_cli.reusable_profile, 'load', return_value=(None, {'token': 'a' * 32}, None, None)), \
                patch.object(game_focus, 'requires_elevated_input', return_value=True), \
                patch.object(game_focus, 'native_input_once', return_value={'ok': False, 'outcome': 'unresolved'}) as helper, \
                patch.object(apex_cli, 'get') as transport:
            result = apex_cli.owned_request('state', 'test_input', value='payload', transport=transport)
        self.assertEqual(result['outcome'], 'unresolved'); helper.assert_called_once()
        self.assertEqual(helper.call_args.args[:2], ('state', 'payload'))
        self.assertEqual(len(helper.call_args.args[2]), 32); transport.assert_not_called()

    def test_direct_native_input_response_loss_keeps_original_uuid_without_resubmission(self):
        import game_focus, game_window
        identity = {'pid': 42, 'native_cli_available': True, 'test_token': 'a' * 32,
                    'script_sha256': 'b' * 64}
        payload = json.dumps({'test_token': 'a' * 32, 'value':
            {'command': 1, 'x': 936, 'y': 642, 'width': 1278, 'height': 1376}})
        for error in (OSError('response lost after click'),
                      apex_cli.urllib.error.URLError('game disappeared after submission')):
            with self.subTest(error=error), \
                    patch.object(apex_cli, 'verified_identity', side_effect=[identity, identity]) as verify, \
                    patch.object(apex_cli.reusable_profile, 'load',
                                 return_value=(None, {'token': 'a' * 32}, None, None)), \
                    patch.object(game_focus, 'requires_elevated_input', return_value=False), \
                    patch.object(game_focus, 'native_input_once') as helper, \
                    patch.object(game_window, 'focus', return_value={'ok': True, 'foreground_verified': True}), \
                    patch.object(apex_cli, 'get', side_effect=error) as transport, \
                    patch.object(apex_cli.time, 'sleep') as pause:
                result = apex_cli.owned_request('state', 'test_input', value=payload, transport=transport)
            transport.assert_called_once()
            self.assertEqual(transport.call_args.args[0], '/api/native')
            query = transport.call_args.args[1]
            self.assertEqual(query['value'], payload)
            self.assertEqual(result['request_id'], query['request_id'])
            self.assertEqual(len(result['request_id']), 32)
            self.assertFalse(result['ok'])
            self.assertIsNone(result['input_submitted'])
            self.assertEqual(result['outcome'], 'unresolved')
            self.assertEqual(result['transport_error'], str(error))
            self.assertEqual(verify.call_count, 2)
            helper.assert_not_called(); pause.assert_not_called()

    def test_non_input_native_control_preserves_existing_exact_identity_retry(self):
        identity = {'pid': 42, 'native_cli_available': True}
        with patch.object(apex_cli, 'verified_identity', return_value=identity), \
                patch.object(apex_cli.reusable_profile, 'load',
                             return_value=(None, {'token': 'a' * 32}, None, None)), \
                patch.object(apex_cli, 'get', side_effect=[OSError('response lost'), {'ok': True}]) as transport:
            result = apex_cli.owned_request('state', 'test_capture', transport=transport)
        self.assertTrue(result['ok'])
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(transport.call_args_list[0], transport.call_args_list[1])

    def test_reload_route_binds_exact_save_proof_and_native_identities(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        sim_id = '9223372036854775815'
        args = apex_cli.parser().parse_args(['cas-reload', '--state', 'session.json',
            '--sim-id', sim_id, '--household-id', '9223372036854775817', '--save-guid', '1841692672',
            '--save-exit-proof', 'exit.json', '--expected-proof-sha256', 'b' * 64,
            '--output', 'reload.json'])
        observer = Mock(return_value={'ok': True})
        identity = {'pid': 42, 'test_token': 'a' * 32}
        with patch.object(apex_cli, 'require_isolated'), \
                patch.object(apex_cli, 'verified_identity', return_value=identity), \
                patch.dict(sys.modules, {'cas_reload': SimpleNamespace(observe=observer)}), \
                patch.object(apex_cli, 'owned_request') as request:
            self.assertTrue(apex_cli.execute(args)['ok'])
        self.assertEqual(observer.call_args.args[5:9], ('b' * 64, sim_id, '9223372036854775817', '1841692672'))
        self.assertEqual(observer.call_args.kwargs['settle_ticks'], 750)
        self.assertIsNone(observer.call_args.kwargs['save_proof'])
        self.assertIsNone(observer.call_args.kwargs['expected_save_proof_sha256'])
        self.assertIs(observer.call_args.kwargs['transport'], apex_cli.get)
        request.assert_not_called()

    def test_certified_reload_route_requires_both_controlled_save_identity_inputs(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['cas-reload', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33',
            '--save-exit-proof', 'exit.json', '--expected-proof-sha256', 'b' * 64,
            '--save-proof', 'save.json', '--expected-save-proof-sha256', 'c' * 64,
            '--output', 'reload.json'])
        observer = Mock(return_value={'ok': True})
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity'), \
                patch.dict(sys.modules, {'cas_reload': SimpleNamespace(observe=observer)}):
            apex_cli.execute(args)
        self.assertEqual(observer.call_args.kwargs['save_proof'], Path('save.json'))
        self.assertEqual(observer.call_args.kwargs['expected_save_proof_sha256'], 'c' * 64)
        args.expected_save_proof_sha256 = None
        with patch.object(apex_cli, 'require_isolated'), \
                patch.dict(sys.modules, {'cas_reload': SimpleNamespace(observe=observer)}), self.assertRaises(ValueError):
            apex_cli.execute(args)

    def test_catalog_audit_route_keeps_repeated_panel_intent_and_bounds(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['cas-catalog-audit', '--state', 'session.json',
            '--sim-id', '9223372036854775815', '--output', 'catalog.json',
            '--panel', 'skin_details', '--panel', 'earrings', '--step-budget', '8'])
        runner = Mock(return_value={'ok': True})
        with patch.object(apex_cli, 'require_isolated'), \
                patch.object(apex_cli, 'verified_identity', return_value={'pid': 42}), \
                patch.dict(sys.modules, {'cas_catalog_audit': SimpleNamespace(run=runner)}):
            self.assertTrue(apex_cli.execute(args)['ok'])
        self.assertEqual(runner.call_args.kwargs['panels'], ['skin_details', 'earrings'])
        self.assertEqual(runner.call_args.kwargs['step_budget'], 8)
        self.assertEqual(runner.call_args.kwargs['seconds'], 120)
        self.assertIs(runner.call_args.kwargs['transport'], apex_cli.get)

    def test_cas_wait_defaults_fit_return_and_explicit_limits_are_preserved(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        for operation, extra, expected in (
                ('return', [], 60), ('status', [], 10),
                ('return', ['--seconds', '7.5'], 7.5), ('status', ['--seconds', '21'], 21),
                ('return', ['--seconds', '0'], 0)):
            args = apex_cli.parser().parse_args(['cas', operation, '--state', 'session.json',
                '--sim-id', '9223372036854775815', '--household-id', '9223372036854775817',
                '--output', 'cas-proof.json'] + extra)
            observer, client = Mock(return_value={'ok': True}), Mock(return_value={'ok': True})
            with self.subTest(operation=operation, explicit=extra), \
                    patch.object(apex_cli, 'require_isolated'), \
                    patch.object(apex_cli, 'verified_identity', return_value={'pid': 42}), \
                    patch.dict(sys.modules, {'cas_return': SimpleNamespace(observe=observer),
                                             'cas_client': SimpleNamespace(execute=client)}):
                self.assertTrue(apex_cli.execute(args)['ok'])
            if operation == 'return':
                self.assertEqual(observer.call_args.kwargs['seconds'], expected)
                client.assert_not_called()
            else:
                self.assertEqual(client.call_args.args[0].seconds, expected)
                observer.assert_not_called()

    def test_discard_route_pins_failed_return_proof_and_all_native_ids(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        sim_id, household_id, save_guid = '285159751289798669', '285159751289798668', '1841692672'
        for extra, expected_wait in (([], 60), (['--seconds', '31'], 31)):
            args = apex_cli.parser().parse_args(['game-discard', '--state', 'session.json',
                '--sim-id', sim_id, '--household-id', household_id, '--save-guid', save_guid,
                '--failed-return-proof', 'failed-return.json', '--expected-proof-sha256', 'b' * 64,
                '--output', 'discard-proof.json'] + extra)
            observer = Mock(return_value={'ok': True})
            identity = {'pid': 42, 'test_token': 'a' * 32}
            with patch.object(apex_cli, 'require_isolated'), \
                    patch.object(apex_cli, 'verified_identity', return_value=identity), \
                    patch.dict(sys.modules, {'game_discard': SimpleNamespace(observe=observer)}), \
                    patch.object(apex_cli, 'owned_request') as request:
                self.assertTrue(apex_cli.execute(args)['ok'])
            self.assertEqual(observer.call_args.args[:3], (args.state, args.output, identity))
            self.assertEqual(observer.call_args.args[4:], (args.failed_return_proof, 'b' * 64, sim_id, household_id, save_guid))
            self.assertEqual(observer.call_args.kwargs['seconds'], expected_wait)
            self.assertIs(observer.call_args.kwargs['transport'], apex_cli.get)
            request.assert_not_called()

    def test_abandon_route_pins_failed_proof_save_hash_slot_and_all_native_ids(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        sim_id, household_id, save_guid = '285159751289798669', '285159751289798668', '1841692672'
        for slot, extra, expected_wait in (('0x2', [], 30), ('2', ['--seconds', '9.5'], 9.5)):
            with self.subTest(slot=slot, explicit=extra):
                args = apex_cli.parser().parse_args(['cas-abandon', '--state', 'session.json',
                    '--sim-id', sim_id, '--household-id', household_id, '--save-guid', save_guid,
                    '--slot-id', slot, '--failed-return-proof', 'failed-return.json',
                    '--expected-proof-sha256', 'b' * 64, '--expected-save-sha256', 'c' * 64,
                    '--output', 'abandon-proof.json'] + extra)
                self.assertEqual(args.state, Path('session.json'))
                self.assertEqual(args.failed_return_proof, Path('failed-return.json'))
                self.assertEqual(args.output, Path('abandon-proof.json'))
                self.assertEqual(args.slot_id, 2)
                observer = Mock(return_value={'ok': True, 'outcome': 'archived'})
                identity = {'pid': 42, 'test_token': 'a' * 32}
                with patch.object(apex_cli, 'require_isolated') as isolated, \
                        patch.object(apex_cli, 'verified_identity', return_value=identity) as verified, \
                        patch.dict(sys.modules, {'cas_abandon': SimpleNamespace(observe=observer)}), \
                        patch.object(apex_cli, 'owned_request') as request, \
                        patch.object(apex_cli, 'get') as transport:
                    self.assertEqual(apex_cli.execute(args), {'ok': True, 'outcome': 'archived'})
                    observer.assert_called_once_with(args.state, args.output, identity, request,
                        args.failed_return_proof, 'b' * 64, 'c' * 64, sim_id, household_id, save_guid, 2,
                        seconds=expected_wait, transport=transport, allow_auto_save_slot_metadata_only=False)
                isolated.assert_called_once_with(args.state)
                verified.assert_called_once_with(args.state)
                request.assert_not_called()
                transport.assert_not_called()

    def test_metadata_autosave_permission_is_explicit_and_forwarded(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['cas-abandon', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33', '--slot-id', '2',
            '--failed-return-proof', 'failed.json', '--expected-proof-sha256', 'b' * 64,
            '--expected-save-sha256', 'c' * 64, '--output', 'out.json',
            '--allow-auto-save-slot-metadata-only'])
        observer = Mock(return_value={'ok': True})
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity'), \
                patch.dict(sys.modules, {'cas_abandon': SimpleNamespace(observe=observer)}):
            apex_cli.execute(args)
        self.assertIs(observer.call_args.kwargs['allow_auto_save_slot_metadata_only'], True)

    def test_unsaved_exit_requires_and_forwards_exact_native_identity(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['game', 'exit', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33', '--output', 'out.json'])
        observer = Mock(return_value={'ok': True})
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity'), \
                patch.dict(sys.modules, {'game_lifecycle': SimpleNamespace(shutdown=observer)}):
            apex_cli.execute(args)
        self.assertEqual(observer.call_args.kwargs, {'save': False, 'sim_id': '11',
            'household_id': '22', 'save_guid': '33'})
        args.household_id = None
        with patch.object(apex_cli, 'require_isolated'), self.assertRaises(ValueError):
            apex_cli.execute(args)

    def test_resume_passes_exact_already_live_identity_without_a_second_launch(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['game', 'resume', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33', '--output', 'out.json'])
        observer = Mock(return_value={'ok': True, 'resume_input_accepted': False})
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity'), \
                patch.dict(sys.modules, {'game_lifecycle': SimpleNamespace(resume=observer)}):
            apex_cli.execute(args)
        self.assertEqual(observer.call_args.kwargs, {'sim_id': '11', 'seconds': args.seconds,
            'household_id': '22', 'save_guid': '33'})

    def test_native_human_route_keeps_native_identity_and_current_form_typed(self):
        args = apex_cli.parser().parse_args(['game', 'native-human', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33',
            '--expected-current-form', '64', '--ensure-witch-owner'])
        with patch.object(apex_cli, 'require_isolated'), \
                patch.object(apex_cli.reusable_profile, 'load', return_value=(Path('session.json'),
                    {'token': 'a' * 32}, Path('profile'), Path('original'))), \
                patch.object(apex_cli, 'owned_request', return_value={'ok': True}) as request:
            self.assertTrue(apex_cli.execute(args)['ok'])
        self.assertEqual(request.call_args.args, (args.state, 'test_native_form_select', '11'))
        self.assertEqual(json.loads(request.call_args.kwargs['value']), {'test_token': 'a' * 32, 'value': {
            'form_flags': 1, 'expected_current_form_flags': 64, 'save_guid': '33',
            'household_id': '22', 'ensure_witch_owner': True}})
        self.assertEqual(request.call_args.kwargs['seconds'], 60)
        args.expected_current_form = None
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'owned_request') as request, self.assertRaises(ValueError):
            apex_cli.execute(args)
        request.assert_not_called()


class EaUpdateCliTests(unittest.TestCase):
    def test_paused_live_observation_binds_original_failed_play_proof(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['game', 'live-observe', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33', '--slot-id', '2',
            '--expected-save-sha256', 'a'*64, '--map-play-proof', 'play.json',
            '--map-play-proof-sha256', 'b'*64, '--output', 'live.json'])
        observe = Mock(return_value={'ok': True, 'native_slot_verified': False})
        identity = {'pid': 42}
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity', return_value=identity) as verified, \
                patch.object(apex_cli, 'owned_request') as request, \
                patch.dict(sys.modules, {'game_live_observe': SimpleNamespace(observe=observe)}):
            self.assertTrue(apex_cli.execute(args)['ok'])
        observe.assert_called_once_with(args.state, args.output, identity, request, '11', '22', '33', 2,
            'a'*64, Path('play.json'), 'b'*64, identity_provider=verified)
        request.assert_not_called()

    def test_equipped_inventory_typed_all_form_paging_does_not_send_ui_input(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['studio', 'inventory', '--state', 'session.json',
            '--sim-id', '11', '--all-forms', '--catalog-manifest', 'catalog.json',
            '--catalog-manifest-sha256', 'a'*64, '--output', 'items.json'])
        collect = Mock(return_value={'ok': True})
        identity = {'pid': 42}
        with patch.object(apex_cli, 'require_isolated'), patch.object(apex_cli, 'verified_identity', return_value=identity) as verified, \
                patch.object(apex_cli, 'owned_request') as request, \
                patch.dict(sys.modules, {'studio_inventory': SimpleNamespace(collect=collect)}):
            self.assertTrue(apex_cli.execute(args)['ok'])
        collect.assert_called_once_with(args.state, args.output, identity, request, '11', form=None,
            all_forms=True, catalog_manifest=Path('catalog.json'), catalog_manifest_sha256='a'*64,
            identity_provider=verified, jobs=4)
        request.assert_not_called()

    def test_map_play_forwards_exact_selection_and_wait_without_unbound_input(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['game', 'map-play', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33', '--slot-id', '2',
            '--expected-save-sha256', 'a' * 64, '--selection-proof', 'selection.json',
            '--selection-proof-sha256', 'b' * 64, '--seconds', '40', '--output', 'live.json'])
        observer = Mock(return_value={'ok': True})
        identity = {'pid': 42}
        with patch.object(apex_cli, 'require_isolated'), \
                patch.object(apex_cli, 'verified_identity', return_value=identity) as verified, \
                patch.object(apex_cli, 'owned_request') as request, \
                patch.dict(sys.modules, {'game_map_play': SimpleNamespace(observe=observer)}):
            self.assertTrue(apex_cli.execute(args)['ok'])
        observer.assert_called_once_with(args.state, args.output, identity, request,
            '11', '22', '33', 2, 'a' * 64, Path('selection.json'), 'b' * 64,
            seconds=40, identity_provider=verified)
        request.assert_not_called()

    def test_map_selection_keeps_load_and_original_input_proofs_bound(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        args = apex_cli.parser().parse_args(['game', 'map-select', '--state', 'session.json',
            '--sim-id', '11', '--household-id', '22', '--save-guid', '33', '--slot-id', '2',
            '--expected-save-sha256', 'a' * 64, '--world', 'ONDARION',
            '--load-proof', 'load.json', '--load-proof-sha256', 'b' * 64,
            '--recovered-input-proof', 'receipt.json', '--recovered-input-sha256', 'c' * 64,
            '--output', 'map.json'])
        observer = Mock(return_value={'ok': True, 'native_live_verified': False})
        identity = {'pid': 42}
        with patch.object(apex_cli, 'require_isolated'), \
                patch.object(apex_cli, 'verified_identity', return_value=identity) as verified, \
                patch.object(apex_cli, 'owned_request') as request, \
                patch.dict(sys.modules, {'game_map': SimpleNamespace(select_marker=observer)}):
            result = apex_cli.execute(args)
        observer.assert_called_once_with(args.state, args.output, identity, request,
            '11', '22', '33', 2, 'a' * 64, 'ONDARION', Path('load.json'), 'b' * 64,
            Path('receipt.json'), 'c' * 64, identity_provider=verified, allow_autosave_drift=False)
        self.assertFalse(result['native_live_verified'])
        request.assert_not_called()

    def test_inspection_and_explicit_restart_remain_distinct(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        for explicit in (False, True):
            inspect = Mock(return_value={'ok': True, 'input_sent': False})
            restart = Mock(return_value={'ok': True, 'restart_verified': True})
            args = apex_cli.parser().parse_args(['ea-update', '--state', 'session.json'] +
                                               (['--restart-once'] if explicit else []))
            with patch.dict(sys.modules, {'ea_update': SimpleNamespace(inspect=inspect, restart_once=restart)}):
                result = apex_cli.execute(args)
            chosen, other = (restart, inspect) if explicit else (inspect, restart)
            chosen.assert_called_once_with(work=Path('session.json').resolve().parent, state=Path('session.json'))
            other.assert_not_called()
            self.assertTrue(result['ok'])

    def test_explicit_evidence_directory_is_forwarded(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        inspect = Mock(return_value={'ok': True})
        args = apex_cli.parser().parse_args(['ea-update', '--state', 'session.json', '--work', 'external-evidence'])
        with patch.dict(sys.modules, {'ea_update': SimpleNamespace(inspect=inspect)}):
            apex_cli.execute(args)
        inspect.assert_called_once_with(work=Path('external-evidence'), state=Path('session.json'))


if __name__ == '__main__':
    unittest.main()
