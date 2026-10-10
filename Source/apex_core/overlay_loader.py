"""Load the shipped F11 sidecar using the game's existing _ctypes extension.

No executable patches, game-directory deployment, external injection, or input
automation. Importing this module performs no native load or filesystem writes.
The canonical Sims owner calls start after the household loading signal.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

_LOAD_LOCK = threading.RLock()


def serialized(function):
    def wrapped(*args, **kwargs):
        with _LOAD_LOCK:
            return function(*args, **kwargs)
    return wrapped

PROTOCOL = 1
_HANDLE = None
_CALLS = None
_LOADED_SHA = None
_LOADED_PATH = None
_STATUS = {'ok': False, 'message': 'F11 sidecar has not been started.'}
_ERRORS = {-1: 'Native start refused: requires the actual x64 Sims 4 process and game Python/Simulation modules.',
           -2: 'DX11 is not active. Select DirectX 11 and load a household before starting the overlay.',
           -3: 'Cannot create the private DX11 bootstrap device/window.',
           -4: 'DXGI hook failed or another overlay owns the swapchain implementation; no foreign hook was replaced.'}


def _unlinked(path):
    """Reject junctions/symlinks before opening any native input."""
    absolute = Path(os.path.abspath(str(path)))
    if any(part.casefold() == 'the sims 4 do not fucking touch!!!' for part in absolute.parts):
        raise ValueError('The protected original profile cannot host the Apex loader.')
    for entry in (absolute,) + tuple(absolute.parents):
        if entry.exists():
            info = entry.lstat()
            if entry.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Linked/reparse-point native input is not allowed.')
    return absolute


def sidecar_paths(module_file):
    # zipimport assigns module.__file__ relative to the actual archive even
    # though checked bytecode embeds a portable, machine-independent filename.
    filename = os.path.abspath(str(module_file))
    marker = '.ts4script'
    boundary = filename.casefold().find(marker)
    if boundary < 0 or filename[boundary + len(marker):boundary + len(marker) + 1] not in ('/', '\\'):
        raise ValueError('F11 requires the installed script archive, not a loose source checkout.')
    archive = _unlinked(filename[:boundary + len(marker)])
    if archive.name.casefold() != 'apexocculthybrid.ts4script' or not archive.is_file():
        raise ValueError('The shipped ApexOccultHybrid.ts4script archive was not found.')
    directory = archive.parent
    if directory.name.casefold() != 'apex' or directory.parent.name.casefold() != 'mods':
        raise ValueError('Keep the script and Native folder together under Mods/Apex.')
    native = _unlinked(directory / 'Native' / 'ApexOverlay.dll')
    manifest = _unlinked(native.parent / 'overlay-manifest.json')
    if not native.is_file() or not manifest.is_file():
        raise ValueError('The matching Native/ApexOverlay.dll and overlay-manifest.json are missing.')
    if not 4096 <= native.stat().st_size <= 16 * 1024 * 1024 or manifest.stat().st_size > 16384:
        raise ValueError('Sidecar input exceeds its bound.')
    info = json.loads(manifest.read_text(encoding='utf-8'))
    if info.get('schema') != 1 or info.get('protocol') != PROTOCOL or info.get('file') != native.name:
        raise ValueError('Sidecar manifest/protocol does not match this script.')
    raw = native.read_bytes()
    if raw[:2] != b'MZ' or hashlib.sha256(raw).hexdigest() != info.get('sha256'):
        raise ValueError('Sidecar SHA-256 differs from its build manifest; native loading was refused.')
    return native, info


def _game_ctypes(dll_path):
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 7):
        raise ValueError('The native loader requires the Windows game Python 3.7 runtime.')
    directory = _unlinked(dll_path)
    if directory.name.casefold() != 'dlls' or directory.parent.name.casefold() != 'python':
        raise ValueError('The game did not provide its Python/DLLs path.')
    extension = _unlinked(directory / '_ctypes_x64.pyd')
    if not extension.is_file():
        raise ValueError('The installed game _ctypes_x64.pyd extension is missing.')
    existing = sys.modules.get('_ctypes')
    if existing is not None:
        if os.path.normcase(os.path.abspath(existing.__file__)) != os.path.normcase(str(extension)):
            raise ValueError('A different _ctypes extension already owns this Python process.')
        return existing
    # The game finder rewrites extension names and excludes pure ctypes.
    # Invoke the standard extension loader directly, preserving the PyInit name.
    loader = importlib.machinery.ExtensionFileLoader('_ctypes', str(extension))
    spec = importlib.util.spec_from_file_location('_ctypes', str(extension), loader=loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    sys.modules['_ctypes'] = module
    return module


def _bind(native, handle):
    class Integer(native._SimpleCData):
        _type_ = 'i'
    class NoArguments(native.CFuncPtr):
        _flags_ = native.FUNCFLAG_STDCALL
        _restype_ = Integer
        _argtypes_ = ()
    class Library:
        _handle = handle
    # Only these fixed exports can be invoked by this loader. There is
    # no configurable arbitrary procedure, address, argument list, or DLL path.
    return {name: NoArguments((name, Library())) for name in
            ('ApexOverlayProtocolVersion', 'ApexOverlayStart', 'ApexOverlayStatus',
             'ApexOverlayShow', 'ApexOverlayHide', 'ApexOverlayRenderedFrames',
             'ApexOverlayVisible', 'ApexOverlayToggleEvents', 'ApexCaptureCompleted', 'ApexCaptureFull',
             'ApexCaptureOverlay', 'ApexGameInputVersion', 'ApexGameInputState', 'ApexGameCursorX', 'ApexGameCursorY')}


def _bind_input(native, handle):
    class Integer(native._SimpleCData):
        _type_ = 'i'
    class InputCall(native.CFuncPtr):
        _flags_ = native.FUNCFLAG_STDCALL
        _restype_ = Integer
        _argtypes_ = (Integer, Integer, Integer, Integer, Integer)
    class Library:
        _handle = handle
    return InputCall(('ApexGameInput', Library()))


def _input_metrics(native, handle):
    """Read optional diagnostics; older loaded DLLs remain usable."""
    class Integer(native._SimpleCData):
        _type_ = 'i'
    class MetricCall(native.CFuncPtr):
        _flags_ = native.FUNCFLAG_STDCALL
        _restype_ = Integer
        _argtypes_ = (Integer,)
    class Library:
        _handle = handle
    try:
        call = MetricCall(('ApexGameInputMetric', Library()))
    except (AttributeError, OSError):
        return {'available': False}
    names = ('width', 'height', 'screen_x', 'screen_y', 'foreground_pid',
             'overlay_pid', 'overlay_hwnd', 'foreground_hwnd', 'root_match')
    result = {'available': True}
    for index, name in enumerate(names):
        value = call(index)
        result[name] = int(getattr(value, 'value', value))
        if 4 <= index <= 7:
            result[name] &= 0xffffffff
    result['root_match'] = bool(result['root_match'])
    return result


def _integer(call):
    value = call()
    return int(getattr(value, 'value', value))


@serialized
def start(module_file, dll_path):
    global _HANDLE, _CALLS, _STATUS, _LOADED_SHA, _LOADED_PATH
    try:
        native_path, info = sidecar_paths(module_file)
        if _HANDLE is not None and (_LOADED_SHA != info['sha256'] or _LOADED_PATH != str(native_path)):
            raise ValueError('A different sidecar is already loaded; close the game normally before replacing it.')
        if _HANDLE is None:
            native = _game_ctypes(dll_path)
            handle = native.LoadLibrary(str(native_path))
            try:
                calls = _bind(native, handle)
                if _integer(calls['ApexOverlayProtocolVersion']) != PROTOCOL:
                    raise ValueError('Native export protocol differs from the script.')
            except Exception:
                native.FreeLibrary(handle)
                raise
            _HANDLE, _CALLS = handle, calls
            _LOADED_SHA, _LOADED_PATH = info['sha256'], str(native_path)
        result = _integer(_CALLS['ApexOverlayStart'])
        _STATUS = {'ok': result == 0, 'native_code': result, 'protocol': PROTOCOL,
            'dll_sha256': info['sha256'], 'message':
            'F11 overlay hook is ready; press F11 in the game window.' if result == 0 else
            _ERRORS.get(result, 'Native start failed with code {}.'.format(result)),
            'game_window_verified': False, 'runtime_verified': False}
    except Exception as exc:
        _STATUS = {'ok': False, 'message': 'F11 loader: {}'.format(exc), 'runtime_verified': False}
    return dict(_STATUS)


@serialized
def status():
    result = dict(_STATUS)
    if _CALLS is not None:
        result['native_status'] = _integer(_CALLS['ApexOverlayStatus'])
        result['game_window_verified'] = result['native_status'] >= 2
        result['renderer_initialized'] = result['native_status'] >= 3
        result['rendered_frames'] = _integer(_CALLS['ApexOverlayRenderedFrames'])
        result['frame_submission_verified'] = result['rendered_frames'] > 0
        result['visible'] = bool(_integer(_CALLS['ApexOverlayVisible']))
        result['toggle_events'] = _integer(_CALLS['ApexOverlayToggleEvents'])
        result['captures_completed'] = _integer(_CALLS['ApexCaptureCompleted'])
        result['runtime_verified'] = (result.get('ok') is True and result['game_window_verified'] and
                                      result['renderer_initialized'] and result['frame_submission_verified'])
        if result.get('ok') is True:
            result['message'] = ('F11 renderer is initialized and has submitted frames; UI actions require their own acknowledgements.'
                                 if result['runtime_verified'] else
                                 'F11 renderer is initialized; waiting for its first submitted frame.'
                                 if result['renderer_initialized'] else
                                 'F11 hook found the game window; renderer initialization requires a visible overlay frame.'
                                 if result['game_window_verified'] else
                                 'F11 hook is ready; waiting to observe the game window.')
    return result


@serialized
def show(visible=True):
    if _CALLS is None:
        return {'ok': False, 'message': 'Start the matching F11 sidecar first.'}
    result = _integer(_CALLS['ApexOverlayShow' if visible else 'ApexOverlayHide'])
    return dict(status(), ok=result == 0, visibility_requested=bool(visible),
                message='Visibility requested; verify actual rendered frames separately.' if result == 0 else 'F11 hook is not ready.')


@serialized
def capture(overlay=False):
    if not _CALLS:
        raise ValueError('The game overlay has not initialized.')
    before = status()
    code = _integer(_CALLS['ApexCaptureOverlay' if overlay else 'ApexCaptureFull'])
    return dict(before, ok=code == 0, native_code=code, capture_requested=code == 0,
                capture_completed_verified=False)


@serialized
def input_event(module_file, dll_path, argument):
    if not _CALLS or not isinstance(argument, dict) or set(argument) != {'command', 'x', 'y', 'width', 'height'}:
        raise ValueError('Use the bounded game-input contract.')
    values = [argument[name] for name in ('command', 'x', 'y', 'width', 'height')]
    if any(type(value) is not int for value in values) or any(not -1 <= value <= 8192 for value in values):
        raise ValueError('Game-input values must be bounded integers.')
    native_path, info = sidecar_paths(module_file)
    if info['sha256'] != _LOADED_SHA or str(native_path) != _LOADED_PATH:
        raise ValueError('The native build changed while the game runs.')
    native = _game_ctypes(dll_path)
    call = _bind_input(native, _HANDLE)
    result = call(*values)
    code = int(getattr(result, 'value', result))
    import time
    state = 0
    if code == 0:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            state = _integer(_CALLS['ApexGameInputState'])
            if state == 4 or state < 0:
                break
            time.sleep(0.02)
    completed = code == 0 and state == 4
    return {'ok': completed, 'native_code': code, 'input_state': state,
            'window_metrics': _input_metrics(native, _HANDLE),
            'input_version': _integer(_CALLS['ApexGameInputVersion']),
            'cursor_client': {'x': _integer(_CALLS['ApexGameCursorX']), 'y': _integer(_CALLS['ApexGameCursorY'])},
            'pointer_verified': completed and argument['command'] in (1, 3),
            'window_messages_accepted': completed if argument['command'] == 4 else None,
            'foreground_required': argument['command'] != 4,
            'os_cursor_moved': False if argument['command'] == 4 else None,
            'input_submitted': completed, 'ui_transition_verified': False,
            'message': ('Window-addressed click queued without moving the OS cursor or changing foreground. Verify the UI transition separately.'
            if argument['command'] == 4 else 'Game-owned input released; cursor readback verified for pointer commands. Verify the UI transition separately.')
            if completed else 'Native input did not complete (code {}, state {}); no UI completion claimed.'.format(code, state)}


def auto_start_enabled(module_file):
    native, _ = sidecar_paths(module_file)
    config = _unlinked(native.parent / 'ApexOverlay.ini')
    if not config.is_file():
        return True
    if config.stat().st_size > 16384:
        raise ValueError('Overlay config exceeds its bound.')
    import configparser
    settings = configparser.ConfigParser()
    settings.read(str(config), encoding='utf-8')
    return settings.getboolean('Overlay', 'AutoStart', fallback=True)


@serialized
def studio_ui(module_file, dll_path, argument):
    if not _CALLS or not isinstance(argument, dict) or set(argument) != {'sim_id', 'tab'}:
        raise ValueError('Use the fixed Studio UI selection contract.')
    sim_id, tab = argument['sim_id'], argument['tab']
    if not isinstance(sim_id, str) or not sim_id.isdigit() or not 0 < int(sim_id) < 1 << 64 or tab not in ('history', 'parts', 'cas_history', 'cas_parts'):
        raise ValueError('Invalid Studio Sim or tab.')
    path, info = sidecar_paths(module_file)
    if info['sha256'] != _LOADED_SHA or str(path) != _LOADED_PATH:
        raise ValueError('The native build changed while the game runs.')
    native = _game_ctypes(dll_path)
    class UInt64(native._SimpleCData): _type_ = 'Q'
    class Integer(native._SimpleCData): _type_ = 'i'
    class StudioCall(native.CFuncPtr):
        _flags_ = native.FUNCFLAG_STDCALL
        _restype_ = Integer
        _argtypes_ = (UInt64, Integer)
    class Library: _handle = _HANDLE
    result = StudioCall(('ApexOverlayStudio', Library()))(int(sim_id),
        {'history': 11, 'parts': 12, 'cas_history': 13, 'cas_parts': 14}[tab])
    code = int(getattr(result, 'value', result))
    return dict(status(), ok=code == 0, studio_ui_requested=code == 0, selected_sim=sim_id, selected_tab=tab)
