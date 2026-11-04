"""Focus only the window owned by the verified disposable Sims bridge.

Default focus sends no keyboard input. An authenticated helper may explicitly
enable one fixed ALT down/up foreground unlock on the normal input desktop.
No guessed coordinates, process-memory access or elevation is performed here.
"""
import os
import time
from pathlib import PureWindowsPath


def interfering_steam_window(row, game_pid):
    """Only the observed Steam main window may be minimized for CLI focus."""
    return (isinstance(row, dict) and type(row.get('pid')) is int and row['pid'] > 0 and row['pid'] != game_pid
            and type(row.get('hwnd')) is int and row['hwnd'] > 0 and row.get('title') == 'Steam'
            and isinstance(row.get('image'), str)
            and PureWindowsPath(row['image']) == PureWindowsPath(r'C:\Games\Steam\bin\cef\cef.win64\steamwebhelper.exe'))


def select_window(rows, pid):
    candidates = [row for row in rows if row['pid'] == pid and row['visible']
                  and row['class'].startswith('Canvas-') and row['width'] > 0 and row['height'] > 0]
    if len(candidates) != 1:
        raise ValueError('Exactly one visible Sims Canvas window must belong to the verified game PID.')
    return candidates[0]


def minimize_steam_foreground(user, kernel, owner, game_hwnd, game_pid):
    """Observe/recheck one known Steam foreground, then request SW_MINIMIZE once."""
    import ctypes
    from ctypes import wintypes
    other = user.GetForegroundWindow()
    other_pid = owner(other)
    if not other or not other_pid or other_pid == game_pid:
        return None
    title = ctypes.create_unicode_buffer(256)
    user.GetWindowTextW(other, title, len(title))
    if title.value != 'Steam':
        return None
    image = ctypes.create_unicode_buffer(32768)
    handle = kernel.OpenProcess(0x1000, False, other_pid)
    length = wintypes.DWORD(len(image))
    try:
        if not handle or not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)):
            return None
        observed = {'hwnd': int(other), 'pid': other_pid, 'title': title.value, 'image': image.value}
        if (not interfering_steam_window(observed, game_pid) or user.GetForegroundWindow() != other or
                owner(other) != other_pid or owner(game_hwnd) != game_pid):
            return None
        return dict(observed, action='minimize-interfering-steam',
                    accepted=bool(user.ShowWindowAsync(other, 6)))
    finally:
        if handle:
            kernel.CloseHandle(handle)


def default_input_desktop(user, kernel):
    """Read the current and helper desktop names; never switch desktops."""
    import ctypes
    from ctypes import wintypes
    user.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user.OpenInputDesktop.restype = wintypes.HANDLE
    user.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user.GetThreadDesktop.restype = wintypes.HANDLE
    user.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    user.GetUserObjectInformationW.restype = wintypes.BOOL
    user.CloseDesktop.argtypes = [wintypes.HANDLE]
    user.CloseDesktop.restype = wintypes.BOOL
    desktop = user.OpenInputDesktop(0, False, 1)  # DESKTOP_READOBJECTS only.
    result = {'ok': False, 'input_name': None, 'helper_name': None}
    if not desktop:
        return result
    try:
        helper = user.GetThreadDesktop(kernel.GetCurrentThreadId())
        for name, handle in (('input_name', desktop), ('helper_name', helper)):
            if not handle:
                return result
            value, needed = ctypes.create_unicode_buffer(256), wintypes.DWORD()
            if not user.GetUserObjectInformationW(handle, 2, value, ctypes.sizeof(value), ctypes.byref(needed)):
                return result
            result[name] = value.value
        result['ok'] = result['input_name'] == result['helper_name'] == 'Default'
        return result
    finally:
        user.CloseDesktop(desktop)


def unlock_foreground_alt(user, kernel, owner, hwnd, pid, pause):
    """One fixed ALT pair, never an arbitrary key or secure-desktop action."""
    import ctypes
    from ctypes import wintypes
    class Mouse(ctypes.Structure):
        _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
            ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
            ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
    class Keyboard(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
            ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
            ('dwExtraInfo', ctypes.c_size_t)]
    class Hardware(ctypes.Structure):
        _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]
    class Data(ctypes.Union):
        _fields_ = [('mi', Mouse), ('ki', Keyboard), ('hi', Hardware)]
    class Input(ctypes.Structure):
        _anonymous_ = ('data',)
        _fields_ = [('type', wintypes.DWORD), ('data', Data)]
    user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    user.SendInput.restype = wintypes.UINT
    user.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user.GetAsyncKeyState.restype = wintypes.SHORT
    modifiers = (0x10, 0x11, 0x12, 0x5b, 0x5c, 0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5)
    held = lambda: [key for key in modifiers if user.GetAsyncKeyState(key) & 0x8000]
    result = {'ok': False, 'attempted': False, 'sent_count': 0,
        'release_attempted': False, 'release_sent_count': 0, 'release_verified': False}
    result['desktop_before'] = default_input_desktop(user, kernel)
    if not result['desktop_before']['ok']:
        result['message'] = 'ALT recovery requires the normal Default input desktop.'
        return result
    result['held_modifiers_before'] = held()
    if result['held_modifiers_before'] or owner(hwnd) != pid:
        result['message'] = 'ALT recovery refused held modifiers or a changed Sims window owner.'
        return result
    events = (Input * 2)()
    for index, flags in enumerate((0, 2)):  # VK_MENU, KEYEVENTF_KEYUP.
        events[index].type = 1
        events[index].ki = Keyboard(0x12, 0, flags, 0, 0)
    result['attempted'] = True
    result['sent_count'] = int(user.SendInput(2, events, ctypes.sizeof(Input)))
    if result['sent_count'] == 1:
        result['desktop_release'] = default_input_desktop(user, kernel)
        if result['desktop_release']['ok']:
            release = (Input * 1)(); release[0] = events[1]
            result['release_attempted'] = True
            result['release_sent_count'] = int(user.SendInput(1, release, ctypes.sizeof(Input)))
    pause(.02)
    result['desktop_after'] = default_input_desktop(user, kernel)
    if result['desktop_after']['ok']:
        result['held_modifiers_after'] = held()
        result['release_verified'] = not any(key in result['held_modifiers_after'] for key in (0x12, 0xa4, 0xa5))
    else:
        result['held_modifiers_after'] = None
    result['ok'] = (result['sent_count'] == 2 and result['desktop_after']['ok'] and
                    not result['held_modifiers_after'] and result['release_verified'] and owner(hwnd) == pid)
    result['message'] = ('Fixed ALT pair released; foreground retry may proceed.' if result['ok'] else
                         'ALT recovery did not complete safely; no game input may follow.')
    return result


def focus(pid, *, user=None, kernel=None, pause=None, monotonic=None, allow_alt_unlock=False):
    if os.name != 'nt':
        raise RuntimeError('Sims window focus requires Windows.')
    if type(allow_alt_unlock) is not bool:
        raise ValueError('ALT foreground recovery requires an explicit boolean opt-in.')
    import ctypes
    from ctypes import wintypes
    user = user or ctypes.WinDLL('user32', use_last_error=True)
    pause, monotonic = pause or time.sleep, monotonic or time.monotonic
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
    kernel = kernel or ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentThreadId.restype = wintypes.DWORD
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    user.ShowWindowAsync.restype = wintypes.BOOL
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
    # Steam's observed main window can reclaim the foreground immediately
    # after SetForegroundWindow succeeds. Minimize that exact interferer before
    # focusing Sims, rather than treating the initial accepted call as durable.
    recovery = minimize_steam_foreground(user, kernel, owner, hwnd, pid)
    if recovery is not None:
        pause(0.1)
    if owner(hwnd) != pid:
        raise ValueError('The selected Sims window owner changed before focus.')
    if user.IsIconic(hwnd):
        user.ShowWindow(hwnd, 9)  # SW_RESTORE
    if owner(hwnd) != pid:
        raise ValueError('The selected Sims window owner changed before foreground input.')
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
    if recovery is None and not accepted and user.GetForegroundWindow() != hwnd:
        recovery = minimize_steam_foreground(user, kernel, owner, hwnd, pid)
        if recovery is not None:
            pause(0.1)
            if owner(hwnd) == pid:
                accepted = bool(user.SetForegroundWindow(hwnd))
    alt_unlock = None
    if allow_alt_unlock and user.GetForegroundWindow() != hwnd:
        alt_unlock = unlock_foreground_alt(user, kernel, owner, hwnd, pid, pause)
        if alt_unlock['ok']:
            class_name = ctypes.create_unicode_buffer(256)
            user.GetClassNameW(hwnd, class_name, len(class_name))
            if owner(hwnd) == pid and user.IsWindowVisible(hwnd) and class_name.value == row['class']:
                accepted = bool(user.SetForegroundWindow(hwnd))
            else:
                alt_unlock.update(ok=False, message='Selected Sims Canvas changed after ALT recovery.')
    deadline = monotonic() + 2
    foreground = user.GetForegroundWindow()
    while foreground != hwnd and monotonic() < deadline:
        pause(0.05)
        foreground = user.GetForegroundWindow()
    verified = foreground == hwnd and owner(foreground) == pid
    ready = verified and (alt_unlock is None or alt_unlock['ok'])
    return {'ok': ready, 'window': row, 'focus_request_accepted': accepted,
            'temporary_input_queue_attachment': bool(attached),
            'foreground_verified': verified, 'foreground_pid': owner(foreground),
            'foreground_recovery': recovery,
            'foreground_alt_unlock': alt_unlock,
            'message': ('Verified Sims window is foreground.' if ready else
                'ALT recovery failed; no game input may follow.' if verified else
                'Windows refused Sims foreground ownership; no game input was submitted.')}
