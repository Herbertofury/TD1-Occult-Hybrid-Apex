"""EA launch handoff using installed metadata and the registered origin2 handler.

Only an exact isolated test session may launch. This cannot silently approve an
EA/Windows administrator prompt and does not implement a headless game engine.
"""
import ctypes
from datetime import datetime, timezone
import os
from pathlib import Path, PureWindowsPath
import re
import json
import math
import subprocess
import time
import urllib.parse
from xml.etree import ElementTree
from source_manifest import sha256
import test_profile
import windows_process


def account_launch_identity(game_root, log=None):
    """Read a successful local account's Play record; never guess edition IDs."""
    explicit_log = log is not None
    log = test_profile.unlinked(log or Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'EA Desktop' / 'Logs' / 'EADesktop.log')
    # EA rotates this exact file at 4 MiB. A new empty/current log must not
    # discard the account's verified Client Play identity. Keep the bounded
    # backup/current stream in chronological order, including rotation seams.
    logs = [log] if explicit_log else [test_profile.unlinked(log.with_suffix('.bak')), log]
    lines, sources = [], []
    for source in logs:
        if not source.is_file():
            continue
        with source.open('rb') as stream:
            stream.seek(max(0, source.stat().st_size - 2 * 1024 * 1024))
            current = stream.read().decode('utf-8', 'replace').splitlines()
        lines.extend(current); sources.extend([source] * len(current))
    if not lines:
        raise ValueError('No local EA launch history; use EA Play once to establish this account\'s launch identity.')
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
                'log': str(log), 'record_log': str(sources[index]),
                'record_sha256': __import__('hashlib').sha256(line.encode('utf-8')).hexdigest()}
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


def observe_game_process(pid, kernel=None, last_error=None, *, expected_path=None, expected_creation_time=None):
    """Observe one exact live DX11 Sims PID through a single read-only handle.

    No shell, enumeration, process memory or elevation is needed. A vanished or
    exited PID returns None; inaccessible and reused non-Sims PIDs fail closed.
    Native bindings may be supplied for tests without inspecting host processes.
    Optional path and creation FILETIME guards reject a reused Sims PID too.
    """
    observed = windows_process.observe(pid, expected_path=expected_path,
        expected_creation_time=expected_creation_time, kernel=kernel, last_error=last_error)
    if observed and PureWindowsPath(observed['Path']).name.casefold() != 'ts4_x64.exe':
        raise ValueError('Verified PID belongs to a different executable; no game command is authorized.')
    return observed


def observe_start(executable, prior_ids, seconds, probe=running_game_processes, monotonic=time.monotonic, pause=time.sleep):
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise ValueError('Launch observation must be between 0 and 60 seconds.')
    started = monotonic(); deadline = started + seconds
    observations = 0
    while True:
        rows = probe(); observations += 1
        if not isinstance(rows, list) or len(rows) > 64:
            raise ValueError('Sims launch process inventory exceeds its passive observation bound.')
        final = []
        for row in rows:
            if (not isinstance(row, dict) or type(row.get('Id')) is not int or not 0 < row['Id'] <= 0xffffffff or
                    row.get('Path') is not None and not isinstance(row['Path'], str)):
                raise ValueError('Sims launch process inventory has no exact typed identity.')
            final.append({'Id': row['Id'], 'Path': row.get('Path')})
            if row['Id'] not in prior_ids and row.get('Path') and Path(row['Path']).resolve() == executable.resolve():
                return {'process_started': True, 'pid': row['Id'], 'executable': row['Path'],
                    'observation_limit_seconds': seconds, 'elapsed_seconds': max(0, monotonic() - started),
                    'process_observation_count': observations, 'retry_attempted': False}
        remaining = deadline - monotonic()
        if remaining <= 0:
            return {'process_started': False, 'outcome': 'start-unresolved', 'final_process_inventory': final,
                'observation_limit_seconds': seconds, 'elapsed_seconds': max(0, monotonic() - started),
                'process_observation_count': observations, 'retry_attempted': False,
                'message': 'No verified Sims process was observed within this limit. The existing handoff may still complete; no retry was attempted.'}
        pause(min(1, remaining))


def launch(game_root, state, execute=False, headless=False, observe_seconds=60, offer_id=None, elevate_permission_once=False):
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
        if elevate_permission_once:
            # This read offset excludes all old/other account launch attempts.
            ea_log = test_profile.unlinked(plan['account_launch_identity']['log'])
            log_offset = ea_log.stat().st_size
        handoff_at = time.time()
        plan['handoff_evidence'] = {
            'timestamp': handoff_at,
            'utc': datetime.fromtimestamp(handoff_at, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        }
        if elevate_permission_once:
            plan['handoff_evidence']['ea_log_start_offset'] = log_offset
        os.startfile(plan['url'])
        plan['handed_off'] = True
        import ea_permission
        time.sleep(1)
        plan['ea_permission'] = ea_permission.acknowledge(Path(state).resolve().parent)
        if elevate_permission_once and not plan['ea_permission'].get('acknowledged'):
            import ea_permission_broker
            try:
                if not test_profile.status(state)['ready_to_launch']:
                    raise ValueError('Test profile changed before the explicit permission helper.')
                plan['handoff_evidence']['permission_context_observation_seconds'] = ea_permission_broker.LAUNCH_RECORD_WAIT_SECONDS
                context = ea_permission_broker.wait_launch_context(plan, handoff_at, log_offset)
                plan['ea_permission_broker'] = ea_permission_broker.elevate_once(
                    Path(state).resolve().parent, launch_context=context)
            except (OSError, ValueError, RuntimeError) as error:
                plan['ea_permission_broker'] = {'ok': False, 'acknowledged': False,
                    'game_start_verified': False, 'windows_uac_automated': False, 'message': str(error)}
        plan['observation'] = observe_start(Path(game_root) / 'Game' / 'Bin' / 'TS4_x64.exe', prior_ids, observe_seconds)
        plan['launched'] = plan['observation']['process_started']
        plan['ok'] = plan['launched']
        plan['proof_scope'] = 'EA handoff and process-start observation only; packaged bridge/household readiness is a separate check.'
    return plan
