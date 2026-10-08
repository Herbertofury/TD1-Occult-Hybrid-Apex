"""Focus only the window owned by the verified disposable Sims bridge.

No input injection, guessed coordinates, process-memory access or elevation.
Windows can refuse foreground ownership; that is an explicit failed result.
"""
import os
import time


def select_window(rows, pid):
    candidates = [row for row in rows if row['pid'] == pid and row['visible']
                  and row['class'].startswith('Canvas-') and row['width'] > 0 and row['height'] > 0]
    if len(candidates) != 1:
        raise ValueError('Exactly one visible Sims Canvas window must belong to the verified game PID.')
    return candidates[0]


def focus(pid):
    if os.name != 'nt':
        raise RuntimeError('Sims window focus requires Windows.')
    import ctypes
    from ctypes import wintypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsWindowVisible.restype = wintypes.BOOL
    user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetClientRect.restype = wintypes.BOOL
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.restype = ctypes.c_int
    user.GetForegroundWindow.restype = wintypes.HWND
    user.IsIconic.argtypes = [wintypes.HWND]
    user.IsIconic.restype = wintypes.BOOL
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.ShowWindow.restype = wintypes.BOOL
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    user.SetForegroundWindow.restype = wintypes.BOOL
    user.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user.AttachThreadInput.restype = wintypes.BOOL
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentThreadId.restype = wintypes.DWORD
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumWindows.restype = wintypes.BOOL
    rows = []

    def owner(hwnd):
        value = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(value))
        return value.value

    @callback_type
    def collect(hwnd, _parameter):
        if owner(hwnd) != pid:
            return True
        rect, class_name = wintypes.RECT(), ctypes.create_unicode_buffer(256)
        user.GetClientRect(hwnd, ctypes.byref(rect))
        user.GetClassNameW(hwnd, class_name, len(class_name))
        rows.append({'hwnd': int(hwnd), 'pid': pid, 'class': class_name.value,
                     'visible': bool(user.IsWindowVisible(hwnd)),
                     'width': rect.right - rect.left, 'height': rect.bottom - rect.top})
        return True

    if not user.EnumWindows(collect, 0):
        raise OSError(ctypes.get_last_error(), 'Window inventory failed.')
    row = select_window(rows, pid)
    hwnd = row['hwnd']
    if owner(hwnd) != pid:
        raise ValueError('The Sims window owner changed before focus.')
    if user.IsIconic(hwnd):
        user.ShowWindow(hwnd, 9)  # SW_RESTORE
    accepted = bool(user.SetForegroundWindow(hwnd))
    attached = []
    # Temporary same-desktop input-queue attachment supports an explicitly
    # requested CLI focus change. Detach before any native input is submitted;
    # this does not inject keys or acknowledge another application's dialogs.
    if not accepted and user.GetForegroundWindow() != hwnd:
        current_thread = kernel.GetCurrentThreadId()
        foreground_thread = user.GetWindowThreadProcessId(user.GetForegroundWindow(), None)
        game_thread = user.GetWindowThreadProcessId(hwnd, None)
        try:
            for thread in dict.fromkeys((foreground_thread, game_thread)):
                if thread and thread != current_thread and user.AttachThreadInput(current_thread, thread, True):
                    attached.append(thread)
            if owner(hwnd) == pid:
                accepted = bool(user.SetForegroundWindow(hwnd))
        finally:
            for thread in reversed(attached):
                user.AttachThreadInput(current_thread, thread, False)
    deadline = time.monotonic() + 2
    foreground = user.GetForegroundWindow()
    while foreground != hwnd and time.monotonic() < deadline:
        time.sleep(0.05)
        foreground = user.GetForegroundWindow()
    verified = foreground == hwnd and owner(foreground) == pid
    return {'ok': verified, 'window': row, 'focus_request_accepted': accepted,
            'temporary_input_queue_attachment': bool(attached),
            'foreground_verified': verified, 'foreground_pid': owner(foreground),
            'message': 'Verified Sims window is foreground.' if verified else 'Windows refused Sims foreground ownership; no input was sent.'}
