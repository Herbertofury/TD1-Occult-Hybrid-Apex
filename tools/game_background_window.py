"""Restore only a minimized verified Sims window without requesting focus.

No keyboard/mouse input, foreground handoff, other-window changes or elevation.
The caller authenticates the disposable bridge before and after this operation.
"""
import ctypes
from ctypes import wintypes as W
import os
import time


class Native:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('Background window restoration requires Windows.')
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        for name, args, result in (
            ('GetWindowThreadProcessId', [W.HWND, ctypes.POINTER(W.DWORD)], W.DWORD),
            ('GetForegroundWindow', [], W.HWND), ('IsIconic', [W.HWND], W.BOOL),
            ('IsWindowVisible', [W.HWND], W.BOOL), ('GetClientRect', [W.HWND, ctypes.POINTER(W.RECT)], W.BOOL),
            ('GetClassNameW', [W.HWND, W.LPWSTR, ctypes.c_int], ctypes.c_int),
            ('ShowWindowAsync', [W.HWND, ctypes.c_int], W.BOOL)):
            function = getattr(self.user, name)
            function.argtypes, function.restype = args, result

    def owner(self, hwnd):
        pid = W.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def windows(self, pid):
        rows = []
        callback = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        @callback
        def collect(hwnd, _argument):
            if self.owner(hwnd) == pid:
                name, rect = ctypes.create_unicode_buffer(256), W.RECT()
                self.user.GetClassNameW(hwnd, name, len(name))
                self.user.GetClientRect(hwnd, ctypes.byref(rect))
                rows.append(dict(hwnd=int(hwnd), pid=pid, class_name=name.value,
                    visible=bool(self.user.IsWindowVisible(hwnd)),
                    width=rect.right-rect.left, height=rect.bottom-rect.top))
            return True
        self.user.EnumWindows.argtypes = [callback, W.LPARAM]
        self.user.EnumWindows.restype = W.BOOL
        if not self.user.EnumWindows(collect, 0):
            raise OSError('Could not enumerate the verified game windows.')
        return rows

    def foreground(self):
        return int(self.user.GetForegroundWindow() or 0)

    def minimized(self, hwnd):
        return bool(self.user.IsIconic(hwnd))

    def restore_without_activation(self, hwnd):
        return bool(self.user.ShowWindowAsync(hwnd, 4)) # SW_SHOWNOACTIVATE


def restore(pid, native=None, pause=time.sleep):
    if type(pid) is not int or not 0 < pid <= 0xffffffff:
        raise ValueError('Use the exact authenticated disposable game process.')
    native = native or Native()
    matches = [row for row in native.windows(pid) if row['pid']==pid and row['visible'] and
               row['class_name'].startswith('Canvas-') and type(row['hwnd']) is int and row['hwnd']>0]
    if len(matches)!=1:
        raise ValueError('Exactly one process-owned Sims Canvas is required; no window changed.')
    window = matches[0]; hwnd = window['hwnd']; foreground = native.foreground()
    proof = dict(ok=False, window=window, restore_attempted=False, foreground_unchanged=True,
                 no_focus_request=True, input_sent=False)
    if native.owner(hwnd)!=pid:
        raise ValueError('The game window owner changed before background restoration.')
    if not native.minimized(hwnd):
        return dict(proof, ok=True, initially_minimized=False)
    proof.update(initially_minimized=True, restore_attempted=True)
    if not native.restore_without_activation(hwnd):
        return dict(proof, message='Windows refused the no-activation restore; no fallback input.')
    for _ in range(20):
        if native.owner(hwnd)!=pid:
            return dict(proof, message='The game window owner changed; no further action.')
        if native.foreground()!=foreground:
            return dict(proof, foreground_unchanged=False,
                        message='Foreground changed during restoration; further automation stopped.')
        if not native.minimized(hwnd):
            return dict(proof, ok=True)
        pause(.05)
    return dict(proof, message='The game stayed minimized; no activation fallback.')


def restore_for_capture(state, pid):
    """Use the existing pinned one-shot worker only after explicit OS refusal."""
    result=restore(pid)
    if result['ok']:
        return result
    from game_focus import requires_elevated_input, elevate_once, digest
    if (result.get('foreground_unchanged') is not True or result.get('restore_attempted') is not True or
            result.get('message')!='Windows refused the no-activation restore; no fallback input.' or
            not requires_elevated_input(pid)):
        return result
    from pathlib import Path
    import uuid
    output=Path(state).resolve().parent/('game-background-'+uuid.uuid4().hex+'.json')
    helper=elevate_once(state,output,background_restore=True)
    observed=helper.get('worker',{}).get('background_restore',{})
    return dict(result,ok=helper.get('ok') is True,
        foreground_unchanged=observed.get('foreground_unchanged') is True,
        no_focus_request=observed.get('no_focus_request') is True,
        input_sent=helper.get('input_sent'),helper_proof=str(output),helper_proof_sha256=digest(output),
        helper_restore=observed,worker_receipt_verified=helper.get('worker_receipt_verified') is True,
        message='Verified no-activation game restore.' if helper.get('ok') is True else
                'Background helper could not verify game restoration; no focus fallback.')
