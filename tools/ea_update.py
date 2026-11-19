"""Inspect EA, or request one exact pending-update restart with normal runas.

The default is read-only. --restart-once permits one native RESTART REQUIRED
invocation after EA's complete English pending-update banner. Normal Windows consent remains
manual; this never targets UAC, kills services, launches a game or edits a
profile. A delivered click and an observed restart/update are separate proofs.
"""
import argparse
import ctypes
from ctypes import wintypes as W
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import ea_permission_broker as broker
import reusable_profile
import test_profile

DEFAULT_WORK = TOOLS.parent / '.work'
DEFAULT_STATE = DEFAULT_WORK / 'reusable-profile-session.json'
OPERATION = 'normal-ea-pending-update-restart'
LEASE_SECONDS = 60
MAX_OBSERVE_SECONDS = 60
MAX_BYTES = 65536
SOURCE_FILES = tuple(dict.fromkeys(('ea_update.py',) + broker.SOURCE_FILES))
BANNER_PREFIX = 'The EA app requires an update. To access the latest features, restart the app within '
IDENTITY_KEYS = {'pid', 'image', 'creation_time', 'session_id', 'elevated', 'ui_access', 'integrity'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_identity():
    return {name: digest(TOOLS / name) for name in SOURCE_FILES}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_identity(identity):
    if (not isinstance(identity, dict) or set(identity) != IDENTITY_KEYS or
            not isinstance(identity['image'], str) or not identity['image'] or
            not all(broker._integer(identity[name], 1 if name in ('pid', 'creation_time') else 0)
                    for name in ('pid', 'creation_time', 'session_id', 'integrity')) or
            identity['pid'] > 0xffffffff or
            not all(type(identity[name]) is bool for name in ('elevated', 'ui_access'))):
        raise ValueError('Invalid typed Windows process lifecycle identity.')
    return identity


def profile_binding(state=DEFAULT_STATE):
    """Bind only the fixed reusable journal; protected original stays read-only."""
    state = reusable_profile.writable(state)
    if state != reusable_profile.writable(DEFAULT_STATE):
        raise ValueError('EA update requires the fixed reusable test-profile journal.')
    if not 0 < state.stat().st_size <= 1024 * 1024:
        raise ValueError('Reusable profile journal exceeds its bound.')
    before = digest(state)
    _state, journal, profile, original = reusable_profile.load(state)
    status = test_profile.status(state)
    if status.get('ready_to_launch') is not True or status.get('mode') != 'reusable-test-only':
        raise ValueError('The active profile is not the exact isolated reusable test profile.')
    marker = reusable_profile.writable(profile / test_profile.MARKER)
    binding = {'state': str(state), 'state_sha256': before, 'token': journal['token'],
               'profile': str(profile), 'protected_original': str(original), 'marker_sha256': digest(marker)}
    if digest(state) != before:
        raise ValueError('Reusable profile journal changed during inspection.')
    return binding


def validate_request(request, now, *, pins=None, probe=None, profile_check=None, expected=None):
    fields = {'schema', 'operation', 'nonce', 'expires_at', 'ea', 'source_sha256', 'profile', 'ea_version'}
    if (not isinstance(request, dict) or set(request) != fields or type(request['schema']) is not int or
            request['schema'] != 1 or request['operation'] != OPERATION or
            not isinstance(request['nonce'], str) or not re.fullmatch('[0-9a-f]{32}', request['nonce'])):
        raise ValueError('Unexpected fixed EA update request schema or nonce.')
    if not _finite(now) or not _finite(request['expires_at']) or not now < request['expires_at'] <= now + LEASE_SECONDS:
        raise ValueError('EA update request expired or exceeds its 60-second lease.')
    actual_pins = source_identity() if pins is None else pins
    if request['source_sha256'] != actual_pins:
        raise ValueError('EA update helper source changed after the request.')
    target = validate_identity(request['ea'])
    expected = broker.EA_IMAGE if expected is None else expected
    probe = probe or broker.process_identity
    if Path(target['image']).resolve() != Path(expected).resolve() or probe(target['pid']) != target:
        raise ValueError('Exact installed EA process changed; no restart input is authorized.')
    version = request['ea_version']
    if version is not None and (not isinstance(version, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){3}', version)):
        raise ValueError('EA executable version is not typed.')
    profile = request['profile']
    profile_fields = {'state', 'state_sha256', 'token', 'profile', 'protected_original', 'marker_sha256'}
    if (not isinstance(profile, dict) or set(profile) != profile_fields or
            not all(isinstance(profile[key], str) for key in profile_fields) or
            not re.fullmatch('[0-9a-f]{32}', profile['token']) or
            not all(re.fullmatch('[0-9a-f]{64}', profile[key]) for key in ('state_sha256', 'marker_sha256'))):
        raise ValueError('Unexpected exact isolated profile binding.')
    profile_check = profile_check or profile_binding
    if profile_check(profile['state']) != profile:
        raise ValueError('Exact isolated profile changed after the EA restart request.')
    return target


def restart_point(observation, window):
    """Accept measured native coordinates only after the complete banner text."""
    if (not isinstance(observation, dict) or observation.get('ok') is not True or
            type(observation.get('width')) is not int or type(observation.get('height')) is not int or
            (observation['width'], observation['height']) != (window['width'], window['height'])):
        raise ValueError('EA update OCR viewport differs from the captured window.')
    transform = observation.get('preprocessing', {})
    if (not isinstance(transform, dict) or transform.get('coordinates') != 'original-viewport' or
            type(transform.get('requested_scale')) is not int or transform['requested_scale'] != 2 or
            type(transform.get('scale')) is not int or transform['scale'] not in (1, 2) or
            (transform.get('ocr_width'), transform.get('ocr_height')) !=
            (observation['width'] * transform['scale'], observation['height'] * transform['scale'])):
        raise ValueError('EA update OCR requires verified scale-two native coordinates.')
    lines = observation.get('lines')
    if not isinstance(lines, list) or not 0 < len(lines) <= 256:
        raise ValueError('EA update text inventory is untyped or oversized.')
    for line in lines:
        if (not isinstance(line, dict) or not isinstance(line.get('text'), str) or
                not isinstance(line.get('words'), list) or not 0 < len(line['words']) <= 128):
            raise ValueError('EA update text line is untyped or oversized.')
        for word in line['words']:
            if not isinstance(word, dict) or not isinstance(word.get('text'), str):
                raise ValueError('EA update word is untyped.')
            values = [word.get(name) for name in ('x', 'y', 'width', 'height')]
            if any(not _finite(value) for value in values):
                raise ValueError('EA update words require finite measured coordinates.')
            x, y, width, height = values
            if not (0 <= x < x + width <= observation['width'] and
                    0 <= y < y + height <= observation['height']):
                raise ValueError('EA update word exceeds the native viewport.')
    def restart_heading(line):
        words = [word['text'] for word in line['words']]
        # Native OCR can read EA's leading circular-arrow icon as C or e.
        # Only one known icon token may precede the exact two heading words;
        # the separate native UIA button name still must match exactly.
        return (line['text'] == ' '.join(words) and words[-2:] == ['RESTART', 'REQUIRED'] and
                (len(words) == 2 or (len(words) == 3 and words[0] in ('C', 'e', '↻', '⟳'))))
    if sum(restart_heading(line) for line in lines) != 1:
        raise ValueError('No unique exact RESTART REQUIRED indicator.')
    banners = [line for line in lines if line['text'].startswith(BANNER_PREFIX) and line['text'].endswith(' Restart app')]
    if len(banners) != 1:
        raise ValueError('No unique complete EA pending-update banner.')
    banner = banners[0]
    if ' '.join(word['text'] for word in banner['words']) != banner['text']:
        raise ValueError('EA banner text differs from its measured word inventory.')
    words = banner['words']
    if len(words) < 3 or [word['text'] for word in words[-2:]] != ['Restart', 'app']:
        raise ValueError('Exact measured Restart app link differs.')
    a, b = words[-2:]
    if (not a['x'] + a['width'] <= b['x'] or
            abs((a['y'] + a['height'] / 2) - (b['y'] + b['height'] / 2)) > max(a['height'], b['height']) or
            any(word['y'] + word['height'] >= observation['height'] / 4 for word in words)):
        raise ValueError('Restart app is not a distinct link within the upper update banner.')
    x = (a['x'] + b['x'] + b['width']) / 2
    y = (min(a['y'], b['y']) + max(a['y'] + a['height'], b['y'] + b['height'])) / 2
    if not 0 < round(x) < observation['width'] or not 0 < round(y) < observation['height'] / 4:
        raise ValueError('Restart link is outside the native upper banner.')
    return round(x), round(y)


UIA_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$r = [Console]::In.ReadToEnd() | ConvertFrom-Json
function Assert-Lifecycle {
    if ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() -ge [double]$r.deadline_ms) { throw 'EA update lease expired' }
    $p = Get-Process -Id $r.ea.pid -ErrorAction Stop
    if ($p.ProcessName -cne 'EADesktop' -or $p.StartTime.ToUniversalTime().ToFileTimeUtc() -ne [long]$r.ea.creation_time -or
        $p.SessionId -ne $r.ea.session_id -or $p.Path -ine $r.ea.image) { throw 'Exact EA lifecycle changed' }
}
function Read-Restart {
    Assert-Lifecycle
    $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$r.hwnd)
    if ($root.Current.ProcessId -ne $r.ea.pid -or $root.Current.NativeWindowHandle -ne $r.hwnd -or
        $root.Current.Name -cne 'EA' -or $root.Current.IsOffscreen) { throw 'Exact EA root differs' }
    $all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    if ($all.Count -gt 4096) { throw 'EA update UIA inventory exceeds its bound' }
    $buttons = @($all | Where-Object { $_.Current.Name -ceq 'RESTART REQUIRED' })
    if ($buttons.Count -ne 1) { throw 'EA restart UIA button is absent or ambiguous' }
    $e = $buttons[0]; $c = $e.Current
    if ($c.ProcessId -ne $r.ea.pid -or -not $c.IsEnabled -or $c.IsOffscreen -or
        $c.ControlType -ne [System.Windows.Automation.ControlType]::Button) { throw 'Exact enabled EA restart button differs' }
    $pattern = $e.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $rect = $c.BoundingRectangle
    $identity = @{pid=[int]$c.ProcessId; hwnd=[long]$r.hwnd; name='RESTART REQUIRED'; type='ControlType.Button';
                  enabled=$true; offscreen=$false; invoke_available=$true; runtime_id=@($e.GetRuntimeId());
                  bounds=@([double]$rect.X,[double]$rect.Y,[double]$rect.Width,[double]$rect.Height)}
    return @{identity=$identity; pattern=$pattern}
}
function Assert-SameSurface($actual, $expected) {
    foreach ($name in @('pid','hwnd','name','type','enabled','offscreen','invoke_available')) {
        if ($actual[$name] -cne $expected.$name) { throw 'Fresh EA restart UIA identity differs' }
    }
    foreach ($name in @('runtime_id','bounds')) {
        $a = @($actual[$name]); $b = @($expected.$name)
        if ($a.Count -ne $b.Count) { throw 'Fresh EA restart UIA geometry differs' }
        for ($i=0; $i -lt $a.Count; $i++) {
            if ($a[$i] -cne $b[$i]) { throw 'Fresh EA restart UIA geometry differs' }
        }
    }
}
$first = Read-Restart
if ($r.invoke -eq $true) {
    Assert-SameSurface $first.identity $r.expected
    $second = Read-Restart
    Assert-SameSurface $second.identity $r.expected
    Assert-Lifecycle
    if (@(Get-Process -ErrorAction Stop | Where-Object {
        $_.ProcessName -in @('TS4_x64','TS4_DX9_x64','TS4','TS4_Launcher_x64') }).Count -ne 0) {
        throw 'The Sims 4 must remain closed before the exact EA restart invocation'
    }
    $second.pattern.Invoke()
}
@{identity=$first.identity; input_sent=[bool]$r.invoke; restart_verified=$false; update_verified=$false} | ConvertTo-Json -Compress -Depth 8
'''


def uia_request(target, window, deadline, *, invoke=False, expected=None):
    """The script has one fixed native EA button; JSON cannot choose commands."""
    if os.name != 'nt':
        raise RuntimeError('Native EA update accessibility requires Windows.')
    payload = {'ea': target, 'hwnd': window['hwnd'], 'deadline_ms': deadline * 1000,
               'invoke': invoke, 'expected': expected}
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', UIA_SCRIPT],
        input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError('Exact EA restart UIA invocation is unsupported or changed: ' + result.stderr[-1000:])
    response = json.loads(result.stdout)
    if (not isinstance(response, dict) or response.get('input_sent') is not invoke or
            response.get('restart_verified') is not False or response.get('update_verified') is not False):
        raise ValueError('EA update accessibility returned invalid proof flags.')
    return response['identity']


def validate_uia(identity, target, window):
    fields = {'pid', 'hwnd', 'name', 'type', 'enabled', 'offscreen', 'invoke_available', 'runtime_id', 'bounds'}
    if (not isinstance(identity, dict) or set(identity) != fields or type(identity['pid']) is not int or
            identity['pid'] != target['pid'] or type(identity['hwnd']) is not int or identity['hwnd'] != window['hwnd'] or
            identity['name'] != 'RESTART REQUIRED' or identity['type'] != 'ControlType.Button' or
            identity['enabled'] is not True or identity['offscreen'] is not False or identity['invoke_available'] is not True or
            not isinstance(identity['runtime_id'], list) or not 0 < len(identity['runtime_id']) <= 32 or
            any(type(value) is not int for value in identity['runtime_id']) or
            not isinstance(identity['bounds'], list) or len(identity['bounds']) != 4 or
            any(not _finite(value) for value in identity['bounds']) or
            not 0 < identity['bounds'][2] <= window['width'] or not 0 < identity['bounds'][3] <= window['height']):
        raise ValueError('EA restart accessibility identity is untyped, ambiguous or unsupported.')
    return identity


def executable_version(image):
    """Read fixed file-version metadata, without executing EA or a subprocess."""
    if os.name != 'nt':
        return None
    version = ctypes.WinDLL('version', use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [W.LPCWSTR, ctypes.POINTER(W.DWORD)]
    version.GetFileVersionInfoSizeW.restype = W.DWORD
    version.GetFileVersionInfoW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = W.BOOL
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, W.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(W.UINT)]
    version.VerQueryValueW.restype = W.BOOL
    ignored = W.DWORD()
    size = version.GetFileVersionInfoSizeW(str(image), ctypes.byref(ignored))
    if not 0 < size <= 1024 * 1024:
        return None
    data, pointer, length = ctypes.create_string_buffer(size), ctypes.c_void_p(), W.UINT()
    if (not version.GetFileVersionInfoW(str(image), 0, size, data) or
            not version.VerQueryValueW(data, '\\', ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52):
        return None
    values = ctypes.cast(pointer, ctypes.POINTER(W.DWORD))
    if values[0] != 0xfeef04bd:
        return None
    return '.'.join(str(value) for value in (values[2] >> 16, values[2] & 0xffff, values[3] >> 16, values[3] & 0xffff))


def _window(window, target):
    if (not isinstance(window, dict) or set(window) != {'pid', 'hwnd', 'width', 'height', 'class'} or
            window['pid'] != target['pid'] or not broker._integer(window['hwnd'], 1) or
            type(window['width']) is not int or not 200 <= window['width'] <= 2600 or
            type(window['height']) is not int or not 150 <= window['height'] <= 2600 or
            not isinstance(window['class'], str) or not window['class'].startswith('Qt')):
        raise ValueError('Unexpected exact native EA window identity.')
    return window


def _capture(native, window, path):
    sha256 = native.capture(window, path)
    if not isinstance(sha256, str) or not re.fullmatch('[0-9a-f]{64}', sha256) or digest(path) != sha256:
        raise ValueError('EA captured pixels differ from their evidence hash.')
    return sha256


def restart_exact(request, work, result, *, probe=None, profile_check=None, closed_guard=None,
                  native_factory=None, recognize=None, uia=None, clock=None):
    import ea_native_permission
    import windows_ocr
    probe, profile_check = probe or broker.process_identity, profile_check or profile_binding
    closed_guard, clock = closed_guard or test_profile.require_closed, clock or time.time
    native_factory, recognize = native_factory or ea_native_permission.NativeEA, recognize or windows_ocr.recognize
    uia = uia or uia_request
    def guard():
        closed_guard()
        validate_request(request, clock(), probe=probe, profile_check=profile_check)
    guard()
    native = native_factory([request['ea']['pid']])
    windows = native.windows()
    if not isinstance(windows, list) or len(windows) != 1:
        raise ValueError('Exactly one visible EA window is required for a pending-update restart.')
    window = _window(windows[0], request['ea'])
    captures = []
    points = []
    for suffix in ('initial', 'fresh'):
        guard()
        if native.windows() != [window]:
            raise ValueError('EA window inventory changed before fresh update recognition.')
        path = work / ('ea-update-' + request['nonce'] + '.' + suffix + '.bmp')
        sha256 = _capture(native, window, path)
        observation = recognize(path, scale=2)
        if digest(path) != sha256:
            raise ValueError('EA captured pixels changed during update OCR.')
        points.append(restart_point(observation, window))
        captures.append({'window': window, 'capture': str(path), 'sha256': sha256})
        guard()
    if points[0] != points[1]:
        raise ValueError('EA Restart app link changed between fresh captures.')
    def input_guard():
        guard()
        if native.windows() != [window]:
            raise ValueError('EA window inventory changed immediately before restart input.')
    input_guard()
    surfaces = []
    for _index in range(2):
        input_guard()
        surfaces.append(validate_uia(uia(request['ea'], window, request['expires_at']), request['ea'], window))
    if surfaces[0] != surfaces[1]:
        raise ValueError('EA RESTART REQUIRED accessibility surface changed between fresh observations.')
    input_guard()
    result.update(windows=captures, point=list(points[1]), uia=surfaces[1], input_attempted=True)
    broker._json_exclusive(work / ('ea-update-' + request['nonce'] + '.intent.json'), result)
    invoked = uia(request['ea'], window, request['expires_at'], invoke=True, expected=surfaces[1])
    if invoked != surfaces[1]:
        raise ValueError('EA UIA invocation returned another identity; restart is not claimed.')
    result.update(ok=True, input_sent=True,
                  message='The exact EA RESTART REQUIRED button was invoked once; restart and update require separate observation.')
    return result


def worker(request_path, expected_hash, request_hash, *, probe=None, profile_check=None,
           closed_guard=None, native_factory=None, recognize=None, uia=None, clock=None):
    if expected_hash != digest(__file__):
        raise ValueError('EA update worker source differs from the requested source.')
    request_path = reusable_profile.writable(request_path)
    work = broker.evidence_directory(request_path.parent)
    if not 0 < request_path.stat().st_size <= MAX_BYTES:
        raise ValueError('EA update request exceeds its bound.')
    raw = request_path.read_bytes()
    if not 0 < len(raw) <= MAX_BYTES or not isinstance(request_hash, str) or hashlib.sha256(raw).hexdigest() != request_hash:
        raise ValueError('EA update request bytes differ from the normal elevation request.')
    request = json.loads(raw)
    probe, clock = probe or broker.process_identity, clock or time.time
    target = validate_request(request, clock(), probe=probe, profile_check=profile_check)
    prefix = 'ea-update-' + request['nonce']
    if request_path.name != prefix + '.request.json':
        raise ValueError('EA update request filename is not bound to its nonce.')
    broker._json_exclusive(work / (prefix + '.claim.json'), {'schema': 1, 'nonce': request['nonce'], 'pid': os.getpid()})
    helper = validate_identity(probe(os.getpid()))
    result = {'schema': 1, 'operation': OPERATION, 'nonce': request['nonce'], 'request_sha256': request_hash,
              'source_sha256': request['source_sha256'], 'ea': target, 'helper': helper,
              'profile': request['profile'], 'ea_version': request['ea_version'], 'ok': False,
              'input_attempted': False, 'input_sent': False, 'restart_verified': False,
              'update_verified': False, 'windows_uac_automated': False}
    try:
        if not helper['elevated'] or helper['ui_access'] or helper['integrity'] < target['integrity'] or helper['session_id'] != target['session_id']:
            raise ValueError('Normal Windows approval did not produce a compatible helper token.')
        restart_exact(request, work, result, probe=probe, profile_check=profile_check,
                      closed_guard=closed_guard, native_factory=native_factory, recognize=recognize, uia=uia, clock=clock)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result.update(ok=False, input_sent=False, message=str(error))
    broker._json_exclusive(work / (prefix + '.receipt.json'), result)
    return result


def shell_runas(request, source_hash, request_hash):
    if os.name != 'nt':
        raise RuntimeError('Normal EA update elevation requires Windows.')
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [('cbSize', W.DWORD), ('fMask', W.ULONG), ('hwnd', W.HWND),
                    ('lpVerb', W.LPCWSTR), ('lpFile', W.LPCWSTR), ('lpParameters', W.LPCWSTR),
                    ('lpDirectory', W.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', W.HINSTANCE),
                    ('lpIDList', ctypes.c_void_p), ('lpClass', W.LPCWSTR), ('hkeyClass', W.HANDLE),
                    ('dwHotKey', W.DWORD), ('hIcon', W.HANDLE), ('hProcess', W.HANDLE)]
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteExW.argtypes, shell.ShellExecuteExW.restype = [ctypes.POINTER(ExecuteInfo)], W.BOOL
    info = ExecuteInfo()
    info.cbSize, info.fMask, info.lpVerb = ctypes.sizeof(info), 0x140, 'runas'
    info.lpFile = str(Path(sys.executable).resolve())
    info.lpParameters = subprocess.list2cmdline(['-I', '-S', str(Path(__file__).resolve()),
        '--worker', str(request), '--source-hash', source_hash, '--request-hash', request_hash])
    info.lpDirectory, info.nShow = str(TOOLS), 0
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), 'Normal Windows elevation was declined or unavailable.')
    if not info.hProcess:
        raise OSError('Windows returned no one-shot EA update helper handle.')
    return info.hProcess


def validate_receipt(receipt, request, request_hash):
    if not isinstance(receipt, dict):
        raise ValueError('EA update receipt is not typed.')
    for name in ('schema', 'operation', 'nonce', 'ea', 'profile', 'ea_version', 'source_sha256'):
        if receipt.get(name) != request[name] or (name == 'schema' and type(receipt.get(name)) is not int):
            raise ValueError('EA update receipt differs from its exact request.')
    if receipt.get('request_sha256') != request_hash:
        raise ValueError('EA update receipt differs from its request bytes.')
    helper = validate_identity(receipt.get('helper'))
    if (not all(type(receipt.get(name)) is bool for name in ('ok', 'input_attempted', 'input_sent')) or
            receipt.get('windows_uac_automated') is not False or receipt.get('restart_verified') is not False or
            receipt.get('update_verified') is not False):
        raise ValueError('EA update worker receipt has invalid or unobserved proof flags.')
    if receipt['input_sent'] and (not receipt['input_attempted'] or not receipt['ok'] or not helper['elevated'] or
            helper['ui_access'] or helper['integrity'] < request['ea']['integrity'] or
            helper['session_id'] != request['ea']['session_id']):
        raise ValueError('EA restart receipt lacks exact compatible input evidence.')
    if receipt['ok'] != receipt['input_sent']:
        raise ValueError('EA update worker success must mean a delivered single input only.')
    if receipt['input_sent']:
        captures = receipt.get('windows')
        if not isinstance(captures, list) or len(captures) != 2 or any(not isinstance(row, dict) for row in captures):
            raise ValueError('EA restart receipt lacks the two fresh capture records.')
        window = _window(captures[0].get('window'), request['ea'])
        for capture, suffix in zip(captures, ('initial', 'fresh')):
            if (not isinstance(capture, dict) or set(capture) != {'window', 'capture', 'sha256'} or
                    capture['window'] != window or not isinstance(capture['capture'], str) or
                    not isinstance(capture['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', capture['sha256'])):
                raise ValueError('EA restart receipt has invalid captured-window evidence.')
            path = reusable_profile.writable(capture['capture'])
            broker.evidence_directory(path.parent)
            if path.name != 'ea-update-' + request['nonce'] + '.' + suffix + '.bmp' or digest(path) != capture['sha256']:
                raise ValueError('EA restart receipt pixels differ from the exact leased evidence.')
        validate_uia(receipt.get('uia'), request['ea'], window)
        point = receipt.get('point')
        if (not isinstance(point, list) or len(point) != 2 or any(type(value) is not int for value in point) or
                not 0 < point[0] < window['width'] or not 0 < point[1] < window['height'] / 4):
            raise ValueError('EA restart receipt has no exact native banner point.')
        work = Path(captures[0]['capture']).parent
        if Path(captures[1]['capture']).parent != work:
            raise ValueError('EA restart capture records belong to different evidence directories.')
        intent_path = reusable_profile.writable(work / ('ea-update-' + request['nonce'] + '.intent.json'))
        if not 0 < intent_path.stat().st_size <= MAX_BYTES:
            raise ValueError('EA update intent exceeds its bound.')
        intent = json.loads(intent_path.read_bytes())
        if (not isinstance(intent, dict) or intent.get('input_attempted') is not True or
                intent.get('input_sent') is not False or intent.get('ok') is not False or
                any(intent.get(name) != receipt.get(name) for name in
                    ('schema', 'operation', 'nonce', 'request_sha256', 'source_sha256', 'ea', 'helper',
                     'profile', 'ea_version', 'windows', 'point', 'uia', 'restart_verified',
                     'update_verified', 'windows_uac_automated'))):
            raise ValueError('EA restart receipt differs from its durable single-input intent.')
    return receipt


def observe_restart(target, before_version, seconds=MAX_OBSERVE_SECONDS, *, diagnostic=None,
                    probe=None, version=None, monotonic=None, pause=None):
    if not _finite(seconds) or not 0 < seconds <= MAX_OBSERVE_SECONDS:
        raise ValueError('EA restart observation must be between zero and 60 seconds.')
    validate_identity(target)
    diagnostic, probe = diagnostic or broker.diagnose, probe or broker.process_identity
    version, monotonic, pause = version or executable_version, monotonic or time.monotonic, pause or time.sleep
    deadline = monotonic() + seconds
    old_gone = False
    while True:
        try:
            current = validate_identity(probe(target['pid']))
            old_gone = (current['pid'], current['creation_time']) != (target['pid'], target['creation_time'])
        except OSError as error:
            if getattr(error, 'winerror', None) not in (87, 1168) and error.errno not in (87, 1168):
                return {'restart_verified': False, 'update_verified': False, 'old_process_gone': False,
                        'message': 'Old EA lifecycle could not be observed: ' + str(error)}
            old_gone = True
        observed = diagnostic()
        if old_gone and observed.get('ok') is True and len(observed.get('targets', [])) == 1:
            new = validate_identity(observed['targets'][0])
            if (new['session_id'] == target['session_id'] and new['creation_time'] > target['creation_time'] and
                    (new['pid'], new['creation_time']) != (target['pid'], target['creation_time']) and
                    Path(new['image']).resolve() == broker.EA_IMAGE.resolve()):
                after_version = version(new['image'])
                typed_version = isinstance(after_version, str) and re.fullmatch(r'[0-9]+(?:\.[0-9]+){3}', after_version)
                changed = bool(before_version and typed_version and before_version != after_version)
                return {'restart_verified': True, 'update_verified': changed, 'old_process_gone': True,
                        'new_ea': new, 'before_version': before_version, 'after_version': after_version,
                        'message': 'EA restarted with a changed executable version.' if changed else
                                   'EA restart was observed; a changed executable version was not proved.'}
        remaining = deadline - monotonic()
        if remaining <= 0:
            return {'restart_verified': False, 'update_verified': False, 'old_process_gone': old_gone,
                    'message': 'No exact new EA lifecycle appeared within the bounded observation; invocation is not restart proof.'}
        pause(min(0.2, remaining))


def inspect(work=DEFAULT_WORK, state=DEFAULT_STATE, *, diagnostic=None, native_factory=None, recognize=None):
    """Read identity/profile and, when token permits, retain one EA screenshot."""
    diagnostic = diagnostic or broker.diagnose
    result = dict(diagnostic(), operation='read-only-ea-pending-update-inspection',
                  diagnostic_only=True, input_sent=False, pending_update_confirmed=False,
                  restart_verified=False, update_verified=False, windows_uac_automated=False)
    try:
        result['profile'] = profile_binding(state)
        if result.get('ok') is not True or len(result.get('targets', [])) != 1:
            raise ValueError('Exactly one installed EA main process is required for update inspection.')
        if result.get('compatible_integrity') is not True:
            result['message'] = 'EA capture requires compatible integrity; inspection sends no input or elevation request.'
            return result
        import ea_native_permission
        import windows_ocr
        native_factory, recognize = native_factory or ea_native_permission.NativeEA, recognize or windows_ocr.recognize
        work = broker.evidence_directory(work)
        target = validate_identity(result['targets'][0])
        native = native_factory([target['pid']])
        windows = native.windows()
        if not isinstance(windows, list) or len(windows) != 1:
            raise ValueError('Exactly one visible EA window is required for update inspection.')
        window = _window(windows[0], target)
        path = work / ('ea-update-' + uuid.uuid4().hex + '.inspect.bmp')
        sha256 = _capture(native, window, path)
        observation = recognize(path, scale=2)
        if digest(path) != sha256:
            raise ValueError('EA inspection capture changed during OCR.')
        result.update(point=list(restart_point(observation, window)), pending_update_confirmed=True,
                      capture=str(path), capture_sha256=sha256,
                      message='The exact EA pending-update banner was observed; no input was sent.')
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result.update(message=str(error))
    return result


def restart_once(work=DEFAULT_WORK, state=DEFAULT_STATE, *, diagnostic=None, runas=None,
                 closed_guard=None, profile_check=None, clock=None, pause=None, nonce=None,
                 exited=None, version=None, observe=None, observe_seconds=MAX_OBSERVE_SECONDS):
    work = broker.evidence_directory(work)
    diagnostic, runas = diagnostic or broker.diagnose, runas or shell_runas
    closed_guard, profile_check = closed_guard or test_profile.require_closed, profile_check or profile_binding
    clock, pause = clock or time.time, pause or time.sleep
    exited, version, observe = exited or broker.helper_exited, version or executable_version, observe or observe_restart
    if not _finite(observe_seconds) or not 0 < observe_seconds <= MAX_OBSERVE_SECONDS:
        raise ValueError('EA restart observation must be between zero and 60 seconds.')
    closed_guard()
    profile = profile_check(state)
    diagnostic_result = diagnostic()
    if diagnostic_result.get('ok') is not True or len(diagnostic_result.get('targets', [])) != 1:
        raise ValueError('Exactly one verified installed EA process is required for a restart request.')
    target = validate_identity(diagnostic_result['targets'][0])
    nonce = nonce or uuid.uuid4().hex
    if not isinstance(nonce, str) or not re.fullmatch('[0-9a-f]{32}', nonce):
        raise ValueError('Invalid one-shot EA update nonce.')
    request = {'schema': 1, 'operation': OPERATION, 'nonce': nonce, 'expires_at': clock() + LEASE_SECONDS,
               'ea': target, 'ea_version': version(target['image']), 'source_sha256': source_identity(), 'profile': profile}
    prefix = 'ea-update-' + nonce
    request_path, receipt_path = work / (prefix + '.request.json'), work / (prefix + '.receipt.json')
    broker._json_exclusive(request_path, request)
    request_hash = digest(request_path)
    def host_result(message, **fields):
        result = {'schema': 1, 'operation': OPERATION, 'nonce': nonce, 'request_sha256': request_hash,
                  'ea': target, 'ok': False, 'input_sent': False, 'restart_verified': False,
                  'update_verified': False, 'worker_receipt_verified': False, 'windows_uac_automated': False,
                  'message': message}
        result.update(fields)
        broker._json_exclusive(work / (prefix + '.host-result.json'), result)
        return result
    handle = None
    try:
        handle = runas(request_path, request['source_sha256']['ea_update.py'], request_hash)
        while clock() < request['expires_at']:
            if receipt_path.exists():
                if not 0 < receipt_path.stat().st_size <= MAX_BYTES:
                    raise ValueError('EA update receipt exceeds its bound.')
                try:
                    receipt = json.loads(receipt_path.read_bytes())
                except json.JSONDecodeError:
                    pause(0.05)
                    continue
                validate_receipt(receipt, request, request_hash)
                if not receipt['input_sent']:
                    return host_result(receipt.get('message', 'No EA restart input was delivered.'),
                                       worker_receipt_verified=True, receipt=receipt)
                observation = observe(target, request['ea_version'], seconds=observe_seconds)
                return host_result(observation['message'], worker_receipt_verified=True, input_sent=True,
                                   ok=observation['restart_verified'], restart_verified=observation['restart_verified'],
                                   update_verified=observation['update_verified'], observation=observation, receipt=receipt)
            if exited(handle):
                return host_result('EA update helper exited without a validated receipt; no restart is claimed.')
            pause(min(0.1, request['expires_at'] - clock()))
        return host_result('EA update helper lease expired; no input or restart is claimed.')
    except (OSError, ValueError, RuntimeError) as error:
        return host_result(str(error))
    finally:
        if handle and os.name == 'nt':
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [W.HANDLE], W.BOOL
            kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--inspect', action='store_true', help='Read-only inspection (default).')
    group.add_argument('--restart-once', action='store_true', help='Normal Windows approval for one exact native EA pending-update restart invocation.')
    group.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--state', type=Path, default=DEFAULT_STATE)
    parser.add_argument('--observe-seconds', type=float, default=MAX_OBSERVE_SECONDS)
    parser.add_argument('--source-hash', help=argparse.SUPPRESS)
    parser.add_argument('--request-hash', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        result = worker(args.worker, args.source_hash, args.request_hash)
    elif args.restart_once:
        result = restart_once(args.work, args.state, observe_seconds=args.observe_seconds)
    else:
        result = inspect(args.work, args.state)
    print(json.dumps(result, indent=2))
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
