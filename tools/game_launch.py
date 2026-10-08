"""EA launch handoff using installed metadata and the registered origin2 handler.

Only an exact isolated test session may launch. This cannot silently approve an
EA/Windows administrator prompt and does not implement a headless game engine.
"""
import ctypes
import os
from pathlib import Path, PureWindowsPath
import re
import json
import subprocess
import time
import urllib.parse
from xml.etree import ElementTree
from source_manifest import sha256
import test_profile


def account_launch_identity(game_root, log=None):
    """Read a successful local account's Play record; never guess edition IDs."""
    log = test_profile.unlinked(log or Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'EA Desktop' / 'Logs' / 'EADesktop.log')
    if not log.is_file():
        raise ValueError('No local EA launch history; use EA Play once to establish this account\'s launch identity.')
    with log.open('rb') as stream:
        stream.seek(max(0, log.stat().st_size - 2 * 1024 * 1024))
        lines = stream.read().decode('utf-8', 'replace').splitlines()
    executable = str(Path(game_root).resolve() / 'Game' / 'Bin' / 'TS4_Launcher_x64.exe')
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        if 'Processing launch request:' not in line or 'requestSource[Client]' not in line:
            continue
        match = re.search(r'offerId\[([A-Za-z0-9:_-]+)\] contentId\[([0-9]{1,10})\] exe\[([^\]]+)\]', line)
        if not match or os.path.normcase(match[3]) != os.path.normcase(executable):
            continue
        if not any('Successful launch.' in prior and 'offerKey.offerId=[' + match[1] + ']' in prior and
                   'slug=[the-sims-4]' in prior for prior in lines[max(0, index - 30):index]):
            continue
        return {'offer_id': match[1], 'content_id': match[2], 'executable': executable,
                'evidence': 'Successful EA Client Play request for this exact installation',
                'log': str(log), 'record_sha256': __import__('hashlib').sha256(line.encode('utf-8')).hexdigest()}
    raise ValueError('No verified successful EA Client Play record for this Sims installation; no launch ID will be guessed.')


def launch_plan(game_root, state, offer_id=None):
    isolation = test_profile.status(state)
    if not isolation['ready_to_launch']:
        raise ValueError('Launch requires an exact isolated test profile.')
    root = test_profile.unlinked(game_root)
    launcher = test_profile.unlinked(root / 'Game' / 'Bin' / 'TS4_Launcher_x64.exe')
    executable = test_profile.unlinked(root / 'Game' / 'Bin' / 'TS4_x64.exe')
    manifest = test_profile.unlinked(root / '__Installer' / 'installerdata.xml')
    if not all(path.is_file() for path in (launcher, executable, manifest)):
        raise ValueError('The selected installation lacks the Sims 4 launcher/executable/EA manifest.')
    raw = manifest.read_bytes()
    if len(raw) > 1024 * 1024 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Unsupported EA installation manifest.')
    try:
        metadata = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise ValueError('Malformed EA installation manifest.') from error
    version = metadata.find('./buildMetaData/gameVersion')
    ids = [node.text for node in metadata.findall('./contentIDs/contentID')]
    if not ids or len(ids) > 64 or any(not re.fullmatch(r'[0-9]{1,10}', value or '') for value in ids):
        raise ValueError('EA manifest content IDs are missing or unsafe; no launch URL will be guessed.')
    # This EA version's legacy offerIds URL parameter means CONTENT IDs.
    # Pick the single edition actually launched by the owner's EA account.
    identity = account_launch_identity(root)
    if offer_id is not None and offer_id != identity['offer_id']:
        raise ValueError('Requested storefront ID differs from this account\'s successful Play record.')
    if identity['content_id'] not in ids:
        raise ValueError('Account launch content ID is not in this installation manifest.')
    url = 'origin2://game/launch?' + urllib.parse.urlencode({'offerIds': identity['content_id'], 'autoDownload': '0'})
    return {'ok': True, 'launched': False, 'mode': 'ea-client-handoff',
            'url': url, 'account_launch_identity': identity, 'installer_content_ids': ids,
            'game_version': version.get('version') if version is not None else None,
            'executable_sha256': sha256(executable), 'installer_manifest_sha256': sha256(manifest),
            'isolation': isolation, 'headless_game_runtime': False,
            'permission_prompts': 'EA/Windows may still require the owner to approve an administrator prompt.',
            'proof_scope': 'Validated launch plan only; success requires observed process and packaged bridge readiness.'}


def running_game_processes():
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                             "@(Get-Process -ErrorAction Stop | Where-Object { $_.ProcessName -in @('TS4_x64','TS4_DX9_x64','TS4') } | Select-Object Id,Path) | ConvertTo-Json -Compress"],
                            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    rows = json.loads(result.stdout) if result.stdout.strip() else []
    rows = rows if isinstance(rows, list) else [rows]
    for row in rows:
        if not row.get('Path'):
            row['Path'] = process_image(row['Id'])
    return rows


def process_image(pid):
    # Get-Process.Path can require more access than image-name inspection.
    # Query only the executable identity; no process memory/injection or elevation.
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        capacity = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(capacity)):
            return buffer.value
        return None
    finally:
        kernel.CloseHandle(handle)


def observe_game_process(pid, kernel=None, last_error=None):
    """Observe one exact live DX11 Sims PID through a single read-only handle.

    No shell, enumeration, process memory or elevation is needed. A vanished or
    exited PID returns None; inaccessible and reused non-Sims PIDs fail closed.
    Native bindings may be supplied for tests without inspecting host processes.
    """
    if type(pid) is not int or not 0 < pid <= 0xffffffff:
        raise ValueError('Use an exact integer Windows process ID within the DWORD range.')
    from ctypes import wintypes
    if kernel is None:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    if last_error is None:
        last_error = lambda: ctypes.get_last_error()
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                               wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION only.
    if not handle:
        error = last_error()
        if error == 87:
            return None
        raise OSError(error, 'Could not observe the verified Sims process.')
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise OSError(last_error(), 'Could not inspect the verified Sims process exit state.')
        if code.value != 259:  # STILL_ACTIVE
            return None
        capacity = wintypes.DWORD(32768)
        name = ctypes.create_unicode_buffer(capacity.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(capacity)):
            raise OSError(last_error(), 'Could not inspect the verified Sims executable identity.')
        image = name.value
        if not image or PureWindowsPath(image).name.casefold() != 'ts4_x64.exe':
            raise ValueError('Verified PID belongs to a different executable; no game command is authorized.')
        return {'Id': pid, 'Path': image}
    finally:
        kernel.CloseHandle(handle)


def observe_start(executable, prior_ids, seconds, probe=running_game_processes, monotonic=time.monotonic, pause=time.sleep):
    if not 0 < seconds <= 60:
        raise ValueError('Launch observation must be between 0 and 60 seconds.')
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        for row in probe():
            if row['Id'] not in prior_ids and row.get('Path') and Path(row['Path']).resolve() == executable.resolve():
                return {'process_started': True, 'pid': row['Id'], 'executable': row['Path']}
        pause(min(1, max(0, deadline - monotonic())))
    return {'process_started': False, 'message': 'EA handoff did not produce a verified Sims process. Check the EA client result; no retry was attempted.'}


def launch(game_root, state, execute=False, headless=False, observe_seconds=20, offer_id=None):
    if headless:
        raise ValueError('A headless Sims 4 runtime is not implemented. Use the real-game bridge for CLI testing.')
    plan = launch_plan(game_root, state, offer_id)
    if execute:
        test_profile.require_closed()
        # Recheck immediately before handoff so no launch can use a restored/live profile.
        if not test_profile.status(state)['ready_to_launch']:
            raise ValueError('Test profile changed before launch.')
        if os.name != 'nt':
            raise RuntimeError('EA registered-protocol launch is supported only on Windows.')
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r'origin2\shell\open\command') as key:
            registered = winreg.QueryValueEx(key, None)[0]
        if not registered or 'EALauncher.exe' not in registered or '%1' not in registered:
            raise ValueError('The origin2 handler is not the expected installed EA launcher.')
        prior_ids = {row['Id'] for row in running_game_processes()}
        os.startfile(plan['url'])
        plan['handed_off'] = True
        import ea_permission
        time.sleep(1)
        plan['ea_permission'] = ea_permission.acknowledge(Path(state).resolve().parent)
        plan['observation'] = observe_start(Path(game_root) / 'Game' / 'Bin' / 'TS4_x64.exe', prior_ids, observe_seconds)
        plan['launched'] = plan['observation']['process_started']
        plan['ok'] = plan['launched']
        plan['proof_scope'] = 'EA handoff and process-start observation only; packaged bridge/household readiness is a separate check.'
    return plan
