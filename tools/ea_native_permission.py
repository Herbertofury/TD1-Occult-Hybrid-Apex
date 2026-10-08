"""Recognize and acknowledge EA's exact launch dialog when Qt exposes no UIA.

Only verified EA windows, their own captured pixels and the one English game
permission dialog are accepted. Never targets UAC, another app, or access errors.
"""
import ctypes
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import time

from test_profile import unlinked
from reusable_profile import writable
from windows_ocr import recognize
from game_launch import process_image


def dialog_button(observation):
    lines = observation.get('lines', [])
    text = ' '.join(' '.join(str(row.get('text', '')).split()) for row in lines).lower()
    if 'this game requires permissions' not in text or (
        'this game requires administrative privileges. do you want to grant access and launch the game?' not in text):
        raise ValueError('Captured window is not the exact EA game permission dialog.')
    ok = [row for row in lines if row.get('text', '').strip().upper() == 'OK']
    close = [row for row in lines if row.get('text', '').strip().upper() == 'CLOSE']
    if len(ok) != 1 or len(close) != 1 or len(ok[0].get('words', [])) != 1:
        raise ValueError('Exact EA dialog buttons are absent or ambiguous.')
    word = ok[0]['words'][0]
    x, y = word['x'] + word['width'] / 2, word['y'] + word['height'] / 2
    heading = next(row for row in lines if 'this game requires permissions' in row.get('text', '').lower())
    heading_y = max(item['y'] + item['height'] for item in heading['words'])
    if not heading_y < y < observation['height'] or not 0 < x < observation['width']:
        raise ValueError('EA button is not below its verified permission heading.')
    return round(x), round(y)


class NativeEA:
    def __init__(self, pids):
        self.pids = set(pids)
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        specs = {
            'EnumWindows': ([ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM), W.LPARAM], W.BOOL),
            'GetWindowThreadProcessId': ([W.HWND, ctypes.POINTER(W.DWORD)], W.DWORD),
            'IsWindowVisible': ([W.HWND], W.BOOL), 'GetClientRect': ([W.HWND, ctypes.POINTER(W.RECT)], W.BOOL),
            'GetClassNameW': ([W.HWND, W.LPWSTR, ctypes.c_int], ctypes.c_int),
            'GetWindowTextW': ([W.HWND, W.LPWSTR, ctypes.c_int], ctypes.c_int),
            'GetForegroundWindow': ([], W.HWND), 'SetForegroundWindow': ([W.HWND], W.BOOL),
            'GetDC': ([W.HWND], W.HDC), 'ReleaseDC': ([W.HWND, W.HDC], ctypes.c_int),
            'PrintWindow': ([W.HWND, W.HDC, W.UINT], W.BOOL),
            'SendMessageTimeoutW': ([W.HWND, W.UINT, W.WPARAM, W.LPARAM, W.UINT, W.UINT, ctypes.POINTER(ctypes.c_size_t)], W.LPARAM)}
        for name, (args, result) in specs.items():
            func = getattr(self.user, name); func.argtypes = args; func.restype = result
        for name, args, result in (
            ('CreateCompatibleDC', [W.HDC], W.HDC), ('CreateCompatibleBitmap', [W.HDC, ctypes.c_int, ctypes.c_int], W.HBITMAP),
            ('SelectObject', [W.HDC, W.HANDLE], W.HANDLE), ('DeleteObject', [W.HANDLE], W.BOOL),
            ('DeleteDC', [W.HDC], W.BOOL),
            ('GetDIBits', [W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p, ctypes.c_void_p, W.UINT], ctypes.c_int)):
            func = getattr(self.gdi, name); func.argtypes = args; func.restype = result

    def owner(self, hwnd):
        pid = W.DWORD(); self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)); return pid.value

    def identity(self, hwnd):
        pid = self.owner(hwnd)
        name, title, rect = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256), W.RECT()
        self.user.GetClassNameW(hwnd, name, len(name)); self.user.GetWindowTextW(hwnd, title, len(title))
        self.user.GetClientRect(hwnd, ctypes.byref(rect))
        if pid not in self.pids or not self.user.IsWindowVisible(hwnd) or not name.value.startswith('Qt') or title.value != 'EA':
            raise ValueError('Window is not a verified visible EA surface.')
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if not 200 <= width <= 2600 or not 150 <= height <= 2600:
            raise ValueError('EA window dimensions exceed the recognition bound.')
        return {'pid': pid, 'hwnd': int(hwnd), 'width': width, 'height': height, 'class': name.value}

    def windows(self):
        rows = []
        callback = self.user.EnumWindows.argtypes[0]
        @callback
        def visit(hwnd, _value):
            try: rows.append(self.identity(hwnd))
            except ValueError: pass
            return True
        if not self.user.EnumWindows(visit, 0):
            raise OSError('EA window enumeration failed.')
        return rows

    def capture(self, row, output):
        if self.identity(row['hwnd']) != row:
            raise ValueError('EA window changed before capture.')
        hwnd, width, height = row['hwnd'], row['width'], row['height']
        dc = self.user.GetDC(hwnd)
        memory = self.gdi.CreateCompatibleDC(dc)
        bitmap = self.gdi.CreateCompatibleBitmap(dc, width, height)
        if not dc or not memory or not bitmap:
            if bitmap: self.gdi.DeleteObject(bitmap)
            if memory: self.gdi.DeleteDC(memory)
            if dc: self.user.ReleaseDC(hwnd, dc)
            raise OSError('EA capture resources unavailable.')
        prior = self.gdi.SelectObject(memory, bitmap)
        try:
            if not self.user.PrintWindow(hwnd, memory, 3):  # CLIENTONLY | RENDERFULLCONTENT
                raise OSError(ctypes.get_last_error(), 'EA client capture refused.')
            self.gdi.SelectObject(memory, prior); prior = None
            header = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
            info = ctypes.create_string_buffer(header)
            pixels = ctypes.create_string_buffer(width * height * 4)
            if self.gdi.GetDIBits(memory, bitmap, 0, height, pixels, info, 0) != height:
                raise OSError('EA client pixel readback failed.')
            raw = struct.pack('<2sIHHI', b'BM', 54 + len(pixels.raw), 0, 0, 54) + header + pixels.raw
            output = writable(output)
            if output.exists(): raise ValueError('Capture evidence already exists.')
            output.write_bytes(raw)
            return hashlib.sha256(raw).hexdigest()
        finally:
            if prior: self.gdi.SelectObject(memory, prior)
            self.gdi.DeleteObject(bitmap); self.gdi.DeleteDC(memory); self.user.ReleaseDC(hwnd, dc)

    def click(self, row, point):
        hwnd = row['hwnd']
        if self.identity(hwnd) != row:
            raise ValueError('EA window changed before acknowledgement.')
        self.user.SetForegroundWindow(hwnd)
        time.sleep(0.1)
        if self.user.GetForegroundWindow() != hwnd:
            raise ValueError('Windows refused foreground ownership; EA acknowledgement not sent.')
        x, y = point
        if not 0 < x < row['width'] or not 0 < y < row['height']:
            raise ValueError('EA acknowledgement outside the recognized window.')
        packed = x | (y << 16)
        result = ctypes.c_size_t()
        if not self.user.SendMessageTimeoutW(hwnd, 0x201, 1, packed, 2, 1000, ctypes.byref(result)):
            raise OSError('EA mouse down could not be delivered; no acknowledgement claimed.')
        try:
            time.sleep(0.1)
        finally:
            # Always release the same button on the same EA window.
            self.user.SendMessageTimeoutW(hwnd, 0x202, 0, packed, 2, 1000, ctypes.byref(result))


def acknowledge(work):
    work = writable(work)
    if not work.is_dir(): raise ValueError('An existing external evidence directory is required.')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        "@(Get-Process -Name EADesktop -ErrorAction SilentlyContinue | Select-Object Id,Path) | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    rows = json.loads(result.stdout) if result.stdout.strip() else []
    rows = rows if isinstance(rows, list) else [rows]
    for row in rows:
        if not row.get('Path'):
            row['Path'] = process_image(row['Id'])
    expected = Path(r'C:\Program Files\Electronic Arts\EA Desktop\EA Desktop\EADesktop.exe')
    pids = [row['Id'] for row in rows if row.get('Path') and Path(row['Path']).resolve() == expected.resolve()]
    if len(pids) != 1: raise ValueError('Exactly one verified installed EA Desktop process is required.')
    native = NativeEA(pids)
    matched, attempts = [], []
    for row in native.windows():
        output = work / ('ea-permission-' + str(time.time_ns()) + '.bmp')
        try:
            image_hash = native.capture(row, output)
            observed = recognize(output)
        except (OSError, ValueError) as error:
            attempts.append({'window': row, 'capture_error': str(error)})
            continue
        try: point = dialog_button(observed)
        except ValueError as error:
            attempts.append({'window': row, 'sha256': image_hash, 'match_error': str(error)})
            continue
        matched.append((row, point, observed, output, image_hash))
    if len(matched) != 1:
        return {'ok': False, 'acknowledged': False, 'windows_uac_approved': False, 'attempts': attempts,
                'message': 'One exact EA permission dialog was not recognized; no input sent.'}
    row, point, observed, output, image_hash = matched[0]
    # Re-observe immediately: button position and complete dialog wording must match.
    fresh = work / ('ea-permission-' + str(time.time_ns()) + '.bmp')
    fresh_hash = native.capture(row, fresh)
    if dialog_button(recognize(fresh)) != point:
        raise ValueError('EA permission button moved; no input sent.')
    native.click(row, point)
    receipt = {'ok': True, 'acknowledged': True, 'window': row, 'point': point,
               'observed': observed, 'capture_sha256': image_hash, 'fresh_capture_sha256': fresh_hash,
               'windows_uac_approved': False, 'game_start_verified': False,
               'message': 'Clicked the exact recognized EA permission OK; game start requires separate observation.'}
    output.with_suffix('.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt
