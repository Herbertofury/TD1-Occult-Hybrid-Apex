from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cas_transition
import game_launch


class ProcessIdentityTests(unittest.TestCase):
    def kernel(self, image=r'C:\Games\The Sims 4\Game\Bin\TS4_x64.exe', code=259,
               handle=12345, exit_success=True, image_success=True):
        def exit_code(_handle, pointer):
            pointer._obj.value = code
            return exit_success
        def query_image(_handle, flags, buffer, capacity):
            self.assertEqual(flags, 0)
            self.assertEqual(capacity._obj.value, 32768)
            self.assertEqual(buffer._length_, 32768)
            if image_success:
                buffer.value = image
                capacity._obj.value = len(image)
            return image_success
        return SimpleNamespace(OpenProcess=Mock(return_value=handle),
                GetExitCodeProcess=Mock(side_effect=exit_code),
                QueryFullProcessImageNameW=Mock(side_effect=query_image), CloseHandle=Mock(return_value=True))

    def test_live_exact_pid_image_and_exit_state_share_one_read_only_handle_without_shell(self):
        kernel = self.kernel()
        error = Mock(return_value=0)
        with patch.object(game_launch.subprocess, 'run', side_effect=AssertionError('no shell')):
            result = game_launch.observe_game_process(42, kernel=kernel, last_error=error)
        self.assertEqual(result, {'Id': 42, 'Path': r'C:\Games\The Sims 4\Game\Bin\TS4_x64.exe'})
        kernel.OpenProcess.assert_called_once_with(0x1000, False, 42)
        self.assertEqual(kernel.GetExitCodeProcess.call_args.args[0], 12345)
        self.assertEqual(kernel.QueryFullProcessImageNameW.call_args.args[0], 12345)
        kernel.CloseHandle.assert_called_once_with(12345)
        error.assert_not_called()

    def test_invalid_pid_is_refused_before_binding_or_opening_any_process(self):
        for pid in (True, False, None, '42', 42.0, -1, 0, 1 << 32):
            kernel = self.kernel()
            with self.subTest(pid=pid), patch.object(game_launch.ctypes, 'WinDLL', create=True) as dll:
                with self.assertRaisesRegex(ValueError, 'DWORD'):
                    game_launch.observe_game_process(pid, kernel=kernel)
                dll.assert_not_called()
            kernel.OpenProcess.assert_not_called()
            kernel.CloseHandle.assert_not_called()

    def test_maximum_dword_is_not_silently_wrapped_or_rewritten(self):
        kernel = self.kernel(handle=0)
        self.assertIsNone(game_launch.observe_game_process(0xffffffff, kernel=kernel, last_error=lambda: 87))
        kernel.OpenProcess.assert_called_once_with(0x1000, False, 0xffffffff)

    def test_missing_pid_returns_none_without_querying_or_closing_nonexistent_handle(self):
        kernel = self.kernel(handle=0)
        self.assertIsNone(game_launch.observe_game_process(42, kernel=kernel, last_error=lambda: 87))
        kernel.GetExitCodeProcess.assert_not_called()
        kernel.QueryFullProcessImageNameW.assert_not_called()
        kernel.CloseHandle.assert_not_called()

    def test_access_denied_is_not_mislabeled_as_process_exit(self):
        kernel = self.kernel(handle=0)
        with self.assertRaises(OSError) as caught:
            game_launch.observe_game_process(42, kernel=kernel, last_error=lambda: 5)
        self.assertEqual(caught.exception.errno, 5)
        kernel.CloseHandle.assert_not_called()

    def test_exited_process_returns_none_and_closes_handle_without_image_read(self):
        kernel = self.kernel(code=1)
        self.assertIsNone(game_launch.observe_game_process(42, kernel=kernel))
        kernel.QueryFullProcessImageNameW.assert_not_called()
        kernel.CloseHandle.assert_called_once_with(12345)

    def test_pid_reused_for_non_sims_or_dx9_is_refused_and_handle_is_closed(self):
        for image in (r'C:\EA\EADesktop.exe', r'C:\Game\TS4_DX9_x64.exe', r'C:\Game\TS4.exe', ''):
            kernel = self.kernel(image=image)
            with self.subTest(image=image), self.assertRaisesRegex(ValueError, 'different executable'):
                game_launch.observe_game_process(42, kernel=kernel)
            kernel.CloseHandle.assert_called_once_with(12345)

    def test_native_exit_or_image_query_failure_closes_handle_and_refuses_authorization(self):
        for kwargs, expected in (({'exit_success': False}, 'exit state'), ({'image_success': False}, 'executable identity')):
            kernel = self.kernel(**kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(OSError, expected):
                game_launch.observe_game_process(42, kernel=kernel, last_error=lambda: 5)
            kernel.CloseHandle.assert_called_once_with(12345)

    def test_default_native_binding_uses_verified_prototypes_and_no_real_host_process(self):
        kernel = self.kernel()
        with patch.object(game_launch.ctypes, 'WinDLL', return_value=kernel, create=True) as factory:
            self.assertEqual(game_launch.observe_game_process(42)['Id'], 42)
        factory.assert_called_once_with('kernel32', use_last_error=True)
        self.assertEqual(len(kernel.OpenProcess.argtypes), 3)
        self.assertEqual(len(kernel.QueryFullProcessImageNameW.argtypes), 4)
        kernel.CloseHandle.assert_called_once_with(12345)

    def test_cas_entry_observer_reuses_central_process_identity_check(self):
        with patch.object(game_launch, 'observe_game_process', return_value={'Id': 42, 'Path': 'TS4_x64.exe'}) as observe:
            self.assertTrue(cas_transition.process_alive(42))
            observe.assert_called_once_with(42)
        with patch.object(game_launch, 'observe_game_process', return_value=None):
            self.assertFalse(cas_transition.process_alive(42))
        with patch.object(game_launch, 'observe_game_process', side_effect=ValueError('reused PID')):
            with self.assertRaisesRegex(ValueError, 'reused PID'):
                cas_transition.process_alive(42)


if __name__ == '__main__':
    unittest.main()
