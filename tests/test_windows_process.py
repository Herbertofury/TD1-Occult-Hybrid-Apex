import ctypes
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_launch
import windows_process


class WindowsProcessTests(unittest.TestCase):
    CREATED = 134359714148505702
    IMAGE = r'C:\Games\The Sims 4\Game\Bin\TS4_x64.exe'
    HANDLE = 0x12345678abcdef01

    def kernel(self, *, image=None, created=None, exit_time=0, exit_codes=(259, 259),
               handle=None, image_success=True, times_success=True, count=None,
               close_success=True):
        image = self.IMAGE if image is None else image
        created = self.CREATED if created is None else created
        codes = iter(exit_codes)
        def exit_code(_handle, pointer):
            pointer._obj.value = next(codes)
            return True
        def times(_handle, creation, exited, cpu_kernel, cpu_user):
            for target, value in ((creation, created), (exited, exit_time)):
                target._obj.dwLowDateTime = value & 0xffffffff
                target._obj.dwHighDateTime = value >> 32
            return times_success
        def query(_handle, flags, buffer, capacity):
            self.assertEqual(flags, 0)
            self.assertEqual(capacity._obj.value, 32768)
            if image_success:
                buffer.value = image
                capacity._obj.value = len(image.encode('utf-16-le')) // 2 if count is None else count
            return image_success
        return SimpleNamespace(
            OpenProcess=Mock(return_value=self.HANDLE if handle is None else handle),
            GetExitCodeProcess=Mock(side_effect=exit_code),
            GetProcessTimes=Mock(side_effect=times),
            QueryFullProcessImageNameW=Mock(side_effect=query),
            CloseHandle=Mock(return_value=close_success))

    def test_live_identity_uses_limited_rights_and_one_64bit_handle_for_every_query(self):
        kernel = self.kernel()
        result = windows_process.observe(27788, kernel=kernel, last_error=lambda: 0)
        self.assertEqual(result, {'Id': 27788, 'Path': self.IMAGE, 'CreationFileTime': self.CREATED})
        kernel.OpenProcess.assert_called_once_with(0x1000, False, 27788)
        for function in (kernel.GetExitCodeProcess, kernel.GetProcessTimes, kernel.QueryFullProcessImageNameW):
            for call in function.call_args_list:
                self.assertEqual(call.args[0], self.HANDLE)
        self.assertEqual(kernel.GetExitCodeProcess.call_count, 2)
        kernel.CloseHandle.assert_called_once_with(self.HANDLE)
        self.assertEqual(kernel.OpenProcess.restype, ctypes.c_void_p)

    def test_reused_sims_pid_new_creation_time_is_refused_without_image_or_replay(self):
        kernel = self.kernel(created=self.CREATED + 1)
        with self.assertRaisesRegex(ValueError, 'different process lifetime'):
            windows_process.observe(27788, expected_creation_time=self.CREATED, kernel=kernel)
        kernel.OpenProcess.assert_called_once()
        kernel.QueryFullProcessImageNameW.assert_not_called()
        kernel.CloseHandle.assert_called_once_with(self.HANDLE)

    def test_each_observation_reopens_live_pid_and_never_reuses_prior_identity(self):
        original = self.kernel()
        replacement = self.kernel(created=self.CREATED + 1)
        first = windows_process.observe(27788, kernel=original)
        second = windows_process.observe(27788, kernel=replacement)
        self.assertNotEqual(first['CreationFileTime'], second['CreationFileTime'])
        original.OpenProcess.assert_called_once()
        replacement.OpenProcess.assert_called_once()
        original.CloseHandle.assert_called_once()
        replacement.CloseHandle.assert_called_once()

    def test_exact_path_guard_accepts_case_and_separator_equivalence_but_refuses_other_installation(self):
        self.assertIsNotNone(windows_process.observe(27788,
            expected_path='c:/GAMES/The Sims 4/Game/Bin/TS4_X64.EXE', kernel=self.kernel()))
        kernel = self.kernel(image=r'D:\Other Sims\Game\Bin\TS4_x64.exe')
        with self.assertRaisesRegex(ValueError, 'different executable path'):
            windows_process.observe(27788, expected_path=self.IMAGE, kernel=kernel)
        kernel.CloseHandle.assert_called_once()

    def test_unicode_64bit_filetime_and_image_are_preserved_exactly(self):
        image = r'C:\遊戲\Моды\🎮\Game\Bin\TS4_x64.exe'
        created = 0xfedcba9876543210
        row = windows_process.observe(42, kernel=self.kernel(image=image, created=created))
        self.assertEqual(row['Path'], image)
        self.assertEqual(row['CreationFileTime'], created)

    def test_disappearance_and_access_failure_do_not_close_a_nonexistent_handle(self):
        missing = self.kernel(handle=0)
        self.assertIsNone(windows_process.observe(42, kernel=missing, last_error=lambda: 87))
        missing.CloseHandle.assert_not_called()
        inaccessible = self.kernel(handle=0)
        with self.assertRaises(OSError) as caught:
            windows_process.observe(42, kernel=inaccessible, last_error=lambda: 5)
        self.assertEqual(caught.exception.errno, 5)
        inaccessible.CloseHandle.assert_not_called()

    def test_exit_before_queries_or_during_queries_returns_none_and_closes_once(self):
        before = self.kernel(exit_codes=(1,))
        self.assertIsNone(windows_process.observe(42, kernel=before))
        before.GetProcessTimes.assert_not_called()
        before.QueryFullProcessImageNameW.assert_not_called()
        before.CloseHandle.assert_called_once()
        during = self.kernel(exit_codes=(259, 1))
        self.assertIsNone(windows_process.observe(42, kernel=during))
        during.GetProcessTimes.assert_called_once()
        during.QueryFullProcessImageNameW.assert_called_once()
        during.CloseHandle.assert_called_once()

    def test_exit_code_259_with_positive_exit_timestamp_is_not_live(self):
        kernel = self.kernel(exit_time=self.CREATED + 10)
        self.assertIsNone(windows_process.observe(42, kernel=kernel))
        kernel.QueryFullProcessImageNameW.assert_not_called()
        kernel.CloseHandle.assert_called_once()

    def test_missing_or_invalid_creation_time_never_publishes_identity(self):
        kernel = self.kernel(created=0)
        with self.assertRaisesRegex(ValueError, 'creation FILETIME'):
            windows_process.observe(42, kernel=kernel)
        kernel.QueryFullProcessImageNameW.assert_not_called()
        kernel.CloseHandle.assert_called_once()

    def test_query_failure_and_exception_always_close_observation_handle(self):
        for field in ('GetProcessTimes', 'QueryFullProcessImageNameW', 'GetExitCodeProcess'):
            for exception in (None, OSError(5, 'fixture failure')):
                kernel = self.kernel()
                function = getattr(kernel, field)
                function.side_effect = exception
                function.return_value = False
                with self.subTest(api=field, exception=bool(exception)), self.assertRaises(OSError):
                    windows_process.observe(42, kernel=kernel, last_error=lambda: 5)
                kernel.CloseHandle.assert_called_once_with(self.HANDLE)

    def test_second_exit_read_failure_never_publishes_partial_identity(self):
        kernel = self.kernel()
        first = kernel.GetExitCodeProcess.side_effect
        calls = [0]
        def exit_code(*args):
            calls[0] += 1
            return first(*args) if calls[0] == 1 else False
        kernel.GetExitCodeProcess.side_effect = exit_code
        with self.assertRaisesRegex(OSError, 'recheck'):
            windows_process.observe(42, kernel=kernel, last_error=lambda: 5)
        kernel.CloseHandle.assert_called_once()

    def test_image_count_bounds_and_termination_are_checked_before_use(self):
        for count in (0, 32768, 0xffffffff, len(self.IMAGE) - 1, len(self.IMAGE) + 1):
            kernel = self.kernel(count=count)
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'bound|character count'):
                windows_process.observe(42, kernel=kernel)
            kernel.CloseHandle.assert_called_once()
        kernel = self.kernel(image='C:\\' + 'a' * (32767 - 3))
        self.assertEqual(len(windows_process.observe(42, kernel=kernel)['Path']), 32767)

    def test_relative_or_embedded_null_image_is_refused_and_handle_is_closed(self):
        for image in ('TS4_x64.exe', r'C:TS4_x64.exe', r'\Game\TS4_x64.exe', '', 'C:\\Game\0TS4_x64.exe'):
            kernel = self.kernel(image=image)
            with self.subTest(image=image), self.assertRaises(ValueError):
                windows_process.observe(42, kernel=kernel)
            kernel.CloseHandle.assert_called_once()

    def test_handle_close_failure_is_not_reported_as_verified_identity(self):
        kernel = self.kernel(close_success=False)
        with self.assertRaisesRegex(OSError, 'close'):
            windows_process.observe(42, kernel=kernel, last_error=lambda: 5)
        kernel.CloseHandle.assert_called_once_with(self.HANDLE)

    def test_invalid_arguments_do_not_open_any_process_or_load_windows_bindings(self):
        for pid in (True, False, None, '42', 42.0, -1, 0, 1 << 32):
            with self.subTest(pid=pid), patch.object(windows_process.ctypes, 'WinDLL', create=True) as dll:
                with self.assertRaisesRegex(ValueError, 'DWORD'):
                    windows_process.observe(pid)
                dll.assert_not_called()
        for creation in (True, False, 0, -1, 1 << 64, '1', 1.0):
            kernel = self.kernel()
            with self.subTest(creation=creation), self.assertRaisesRegex(ValueError, 'FILETIME'):
                windows_process.observe(42, expected_creation_time=creation, kernel=kernel)
            kernel.OpenProcess.assert_not_called()

    def test_game_wrapper_preserves_observed_fields_and_forwards_exact_lifetime_guards(self):
        kernel = self.kernel()
        row = game_launch.observe_game_process(42, kernel=kernel, expected_path=self.IMAGE,
                                              expected_creation_time=self.CREATED)
        self.assertEqual(row['CreationFileTime'], self.CREATED)
        self.assertEqual(row['Id'], 42)
        self.assertEqual(row['Path'], self.IMAGE)
        kernel.CloseHandle.assert_called_once()


if __name__ == '__main__':
    unittest.main()
