"""Observe one Windows process lifetime using limited, read-only query rights.

Every call opens and closes its own handle. No PID cache, shell enumeration,
memory access, token changes, or privilege escalation is involved.
"""
import ctypes
from ctypes import wintypes
from pathlib import PureWindowsPath


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
ERROR_INVALID_PARAMETER = 87
MAX_IMAGE_CHARACTERS = 32768


def _filetime(value):
    return value.dwLowDateTime | (value.dwHighDateTime << 32)


def _image_path(value):
    if (not isinstance(value, str) or not value or '\0' in value or
            not PureWindowsPath(value).is_absolute()):
        raise ValueError('Observed executable must have an absolute Windows image path.')
    return str(PureWindowsPath(value)).casefold()


def observe(pid, *, expected_path=None, expected_creation_time=None,
            kernel=None, last_error=None):
    """Return Id/Path/CreationFileTime for a currently observed exact PID.

    Vanished or exited processes return None. Access failures, malformed image
    data, or a changed expected lifetime fail closed. Optional expected values
    are compared with the live handle, never a cached PID observation.
    """
    if type(pid) is not int or not 0 < pid <= 0xffffffff:
        raise ValueError('Use an exact integer Windows process ID within the DWORD range.')
    expected_image = None if expected_path is None else _image_path(expected_path)
    if (expected_creation_time is not None and
            (type(expected_creation_time) is not int or not 0 < expected_creation_time <= 0xffffffffffffffff)):
        raise ValueError('Expected creation FILETIME must be an exact positive 64-bit integer.')
    if kernel is None:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    if last_error is None:
        last_error = lambda: ctypes.get_last_error()
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                               wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL

    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        error = last_error()
        if error == ERROR_INVALID_PARAMETER:
            return None
        raise OSError(error, 'Could not observe the verified process.')
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise OSError(last_error(), 'Could not inspect the verified process exit state.')
        if code.value != STILL_ACTIVE:
            return None
        creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                      ctypes.byref(kernel_time), ctypes.byref(user_time)):
            raise OSError(last_error(), 'Could not inspect the verified process creation FILETIME.')
        # An application can terminate with exit code 259. Never accept a
        # positive exit timestamp as evidence of a live process in that case.
        if _filetime(exit_time):
            return None
        created = _filetime(creation)
        if not 0 < created <= 0xffffffffffffffff:
            raise ValueError('Observed process creation FILETIME is missing or invalid.')
        if expected_creation_time is not None and created != expected_creation_time:
            raise ValueError('Verified PID belongs to a different process lifetime.')
        capacity = wintypes.DWORD(MAX_IMAGE_CHARACTERS)
        name = ctypes.create_unicode_buffer(MAX_IMAGE_CHARACTERS)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(capacity)):
            raise OSError(last_error(), 'Could not inspect the verified executable identity.')
        if not 0 < capacity.value < MAX_IMAGE_CHARACTERS or name[capacity.value] != '\0':
            raise ValueError('Observed executable identity exceeds its terminated image bound.')
        image = name.value
        if len(image.encode('utf-16-le')) // 2 != capacity.value:
            raise ValueError('Observed executable identity has an inconsistent character count.')
        actual_image = _image_path(image)
        if expected_image is not None and actual_image != expected_image:
            raise ValueError('Verified PID belongs to a different executable path.')
        # The process may terminate while its image/times are being read. Use
        # the same live handle again before publishing any identity evidence.
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise OSError(last_error(), 'Could not recheck the verified process exit state.')
        if code.value != STILL_ACTIVE:
            return None
        return {'Id': pid, 'Path': image, 'CreationFileTime': created}
    finally:
        if not kernel.CloseHandle(handle):
            raise OSError(last_error(), 'Could not close the process observation handle.')
