"""One-shot EA consent helper using normal Windows administrator approval.

The default command only diagnoses process integrity. --elevate-once requests
normal UAC consent with ShellExecuteEx/runas, then acknowledges one exact EA
game-permission dialog at compatible integrity. It never approves UAC, launches
a game, changes EA/registry settings, or installs a persistent broker.
The nonce/receipt lease is 90 seconds. Windows may wait longer for normal UAC
consent; late approval expires without sending EA input. The overall ShellExecute
call is not claimed to have a verified 90-second bound.

Primary platform contracts:
https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-securityoverview
https://learn.microsoft.com/en-us/windows/win32/shell/launch
"""
import argparse
import ctypes
from ctypes import wintypes as W
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


TOOLS = Path(__file__).resolve().parent
# The isolated elevated interpreter imports only this repository's pinned tools.
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from reusable_profile import writable

EA_IMAGE = Path(r'C:\Program Files\Electronic Arts\EA Desktop\EA Desktop\EADesktop.exe')
SOURCE_FILES = (
    'ea_permission_broker.py', 'ea_permission.py', 'ea_native_permission.py',
    'windows_ocr.py', 'windows_ocr.ps1', 'reusable_profile.py', 'test_profile.py',
    'game_launch.py', 'windows_process.py', 'source_manifest.py',
)
MAX_BYTES = 65536
LEASE_SECONDS = 90
EA_LOG = Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'EA Desktop' / 'Logs' / 'EADesktop.log'
LAUNCH_RECORD_WAIT_SECONDS = 10


class LaunchRecordPending(ValueError):
    """The bounded post-handoff bytes contain no launch record yet."""


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_identity():
    return {name: _digest(TOOLS / name) for name in SOURCE_FILES}


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 0xffffffffffffffff


def process_identity(pid):
    """Read executable, creation time, session and token; never process memory."""
    if os.name != 'nt' or not _integer(pid, 1) or pid > 0xffffffff:
        raise ValueError('Use one exact Windows process ID.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.CloseHandle.restype = W.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = W.BOOL
    kernel.GetProcessTimes.argtypes = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4
    kernel.GetProcessTimes.restype = W.BOOL
    kernel.ProcessIdToSessionId.argtypes = [W.DWORD, ctypes.POINTER(W.DWORD)]
    kernel.ProcessIdToSessionId.restype = W.BOOL
    advapi.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE)]
    advapi.OpenProcessToken.restype = W.BOOL
    advapi.GetTokenInformation.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD)]
    advapi.GetTokenInformation.restype = W.BOOL
    advapi.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    advapi.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi.GetSidSubAuthority.argtypes = [ctypes.c_void_p, W.DWORD]
    advapi.GetSidSubAuthority.restype = ctypes.POINTER(W.DWORD)
    process = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not process:
        raise OSError(ctypes.get_last_error(), 'Cannot inspect exact process identity.')
    try:
        capacity = W.DWORD(32768)
        image = ctypes.create_unicode_buffer(capacity.value)
        times = [W.FILETIME() for _ in range(4)]
        session = W.DWORD()
        if not kernel.QueryFullProcessImageNameW(process, 0, image, ctypes.byref(capacity)) or not kernel.GetProcessTimes(process, *[ctypes.byref(v) for v in times]) or not kernel.ProcessIdToSessionId(pid, ctypes.byref(session)):
            raise OSError(ctypes.get_last_error(), 'Cannot read exact process lifecycle identity.')
        result = {'pid': pid, 'image': str(Path(image.value).resolve()),
                  'creation_time': times[0].dwLowDateTime | (times[0].dwHighDateTime << 32),
                  'session_id': session.value}
        token = W.HANDLE()
        if not advapi.OpenProcessToken(process, 0x8, ctypes.byref(token)):  # TOKEN_QUERY
            raise OSError(ctypes.get_last_error(), 'Cannot inspect process token.')
        try:
            for information, name in ((20, 'elevated'), (26, 'ui_access'), (25, 'integrity')):
                length = W.DWORD()
                advapi.GetTokenInformation(token, information, None, 0, ctypes.byref(length))
                if not 0 < length.value <= 65536:
                    raise ValueError('Unsupported Windows token metadata size.')
                data = ctypes.create_string_buffer(length.value)
                if not advapi.GetTokenInformation(token, information, data, length, ctypes.byref(length)):
                    raise OSError(ctypes.get_last_error(), 'Cannot read process token metadata.')
                if information == 25:
                    sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
                    count = advapi.GetSidSubAuthorityCount(sid)[0]
                    if count < 1:
                        raise ValueError('Unsupported Windows integrity SID.')
                    result[name] = advapi.GetSidSubAuthority(sid, count - 1)[0]
                else:
                    result[name] = bool(ctypes.cast(data, ctypes.POINTER(W.DWORD))[0])
        finally:
            kernel.CloseHandle(token)
        return result
    finally:
        kernel.CloseHandle(process)


def ea_pids():
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        "@(Get-Process -Name EADesktop -ErrorAction SilentlyContinue | Select-Object Id) | ConvertTo-Json -Compress"],
        capture_output=True, text=True, check=True, timeout=10,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    rows = json.loads(result.stdout) if result.stdout.strip() else []
    rows = rows if isinstance(rows, list) else [rows]
    return [row['Id'] for row in rows]


def diagnose(probe=process_identity, inventory=ea_pids, expected=EA_IMAGE):
    client = probe(os.getpid())
    expected = Path(expected).resolve()
    compatibility = expected.parent / 'compatibility32' / 'EADesktop.exe'
    targets, failures, workers, ignored = [], [], [], []
    pids = inventory()
    if not isinstance(pids, list) or len(pids) > 16:
        raise ValueError('EA process inventory is untyped or exceeds the bounded main/worker inspection.')
    seen = set()
    for pid in pids:
        try:
            if not _integer(pid, 1) or pid > 0xffffffff or pid in seen:
                raise ValueError('EA inventory contains an invalid or duplicate process ID.')
            seen.add(pid)
            target = probe(pid)
            if not isinstance(target, dict) or target.get('pid') != pid or type(target.get('session_id')) is not int:
                raise ValueError('EA process inspection returned another or untyped identity.')
            image = Path(target['image']).resolve()
            if image == compatibility.resolve():
                workers.append(target)
                continue
            if image != expected:
                raise ValueError('EA process does not match the installed executable.')
            targets.append(target)
        except (OSError, ValueError) as error:
            failures.append({'pid': pid, 'error': str(error)})
    main = targets[0] if len(targets) == 1 else None
    for worker in workers:
        if main is not None and worker['session_id'] == main['session_id']:
            ignored.append({'identity': worker, 'reason': 'Verified same-install compatibility32 worker; not the EA main window owner.'})
        else:
            failures.append({'pid': worker['pid'], 'error': 'Compatibility worker has no unique same-session installed EA main process.'})
    exact = targets[0] if len(targets) == 1 and not failures else None
    compatible = bool(exact and client['session_id'] == exact['session_id'] and client['integrity'] >= exact['integrity'])
    return {'ok': exact is not None, 'diagnostic_only': True, 'input_sent': False,
            'client': client, 'targets': targets, 'ignored_processes': ignored, 'failures': failures,
            'compatible_integrity': compatible, 'normal_elevation_may_help': bool(exact and not compatible),
            'message': 'Normal UAC approval is required for the explicit helper; no approval is automated.'}


def evidence_directory(path, root=None):
    path = writable(path)
    root = writable(root or TOOLS.parent / '.work')
    if not path.is_dir() or not path.is_relative_to(root) or any(part.casefold().startswith('the sims 4') for part in path.parts):
        raise ValueError('Use an existing external repository .work evidence directory.')
    return path


def processing_record(log, offset=None):
    """Read only the latest bounded EA launch request, excluding prior handoffs."""
    from test_profile import unlinked
    log = unlinked(log)
    size = log.stat().st_size
    if offset is not None and (not _integer(offset) or size < offset or size - offset > 2 * 1024 * 1024):
        raise ValueError('EA launch log rotated or exceeded the handoff evidence bound.')
    with log.open('rb') as stream:
        stream.seek(offset if offset is not None else max(0, size - 2 * 1024 * 1024))
        text = stream.read(2 * 1024 * 1024 + 1).decode('utf-8', 'replace')
    raw_lines = text.splitlines()
    starts = [i for i, line in enumerate(raw_lines) if 'Handling game launch request' in line]
    legacy_starts = [i for i, line in enumerate(raw_lines) if 'Processing launch request:' in line]
    def header(line):
        matches = re.findall(r'\[([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z)\]\s+PID:\s*([0-9]+)\s+TID:\s*([0-9]+)\s+', line)
        if len(matches) != 1 or '\ufffd' in line:
            raise ValueError('Unsupported fresh EA launch pipeline header.')
        timestamp, pid, tid = matches[0]
        pid, tid = int(pid), int(tid)
        if not 0 < pid <= 0xffffffff or not 0 < tid <= 0xffffffff:
            raise ValueError('Invalid fresh EA launch pipeline process/thread identity.')
        return pid, tid, datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()


    # Worker revalidation has no offset: select the newest request boundary,
    # not a previous pipeline elsewhere in the bounded history. Its digest must
    # still match the exact context captured by the fresh-offset observation.
    if offset is None and starts and legacy_starts and legacy_starts[-1] > starts[-1]:
        try:
            initial_time = header(raw_lines[starts[-1]])[2]
            legacy_time = header(raw_lines[legacy_starts[-1]])[2]
        except ValueError:
            starts = []
        else:
            if not 0 <= legacy_time - initial_time <= 2:
                starts = []
        # A recent legacy record can be the pipeline's final serialization.
        # Keep it in the strict parser below; only an exact match is deduped.
    if starts:
        start = starts[-1]
        if offset is not None and (len(starts) != 1 or any(i < start for i in legacy_starts)):
            raise ValueError('Competing fresh EA launch requests; no permission acknowledgement is authorized.')


        first = raw_lines[start]
        pid, tid, timestamp = header(first)
        initial = re.search(r'Handling game launch request \(InitialRequest\): IDs=\[offerKey\.offerId=\[\], offerId=\[\], contentIds=\[([0-9]{1,10})\], slug=\[\]\], offerKey\.externalType=\[\], requestOwner=\[EA\], requestSource=\[RTP\], gameArguments=\[\]$', first)
        if initial is None:
            raise ValueError('Unsupported fresh EA InitialRequest; no permission acknowledgement is authorized.')
        content_id = initial[1]
        selected = [first]
        launcher = offer_id = None
        stage = 1
        serialization_seen = False
        last_timestamp = timestamp
        for line in raw_lines[start + 1:]:
            if 'Handling game launch request' in line:
                raise ValueError('Competing fresh EA launch requests; no permission acknowledgement is authorized.')
            kind = next((kind for kind, marker in (
                ('exe', '[GAME] Got exePath='), ('issue', '[GAME] Issuing launch:'),
                ('success', 'Successful launch. IDs:'),
                ('serialization', 'Processing launch request:')) if marker in line), None)
            if kind is None:
                continue
            line_pid, line_tid, line_timestamp = header(line)
            if (line_pid, line_tid) != (pid, tid) or not last_timestamp <= line_timestamp <= timestamp + 2:
                raise ValueError('Fresh EA launch pipeline has mixed identity or timestamps.')
            last_timestamp = line_timestamp
            if kind == 'exe':
                match = re.search(r'\[GAME\] Got exePath=\[([^\]]+)\] cmdArgs=\[\] from defaultLauncher\.$', line)
                if match is None or not Path(match[1]).is_absolute() or Path(match[1]).name.casefold() != 'ts4_launcher_x64.exe':
                    raise ValueError('Fresh EA launch pipeline has unsupported launcher/arguments.')
                observed_launcher = str(Path(match[1]).resolve())
                if stage == 1:
                    launcher = observed_launcher
                    selected.append(line)
                    stage = 2
                elif observed_launcher != launcher:
                    raise ValueError('Fresh EA launch pipeline changed its default launcher.')
                # EA repeats the same defaultLauncher lookup after success.
            elif kind == 'issue':
                match = re.search(r'\[GAME\] Issuing launch: workingDirectory\[([^\]]+)\] offer\[([A-Za-z0-9:_-]+)\] content\[([0-9]{1,10})\] gameArgs \[\]$', line)
                if match is None or stage != 2 or match[3] != content_id or not Path(match[1]).is_absolute() or Path(match[1]).resolve() != Path(launcher).parent:
                    raise ValueError('Fresh EA launch pipeline has mismatched launch identity/arguments.')
                offer_id = match[2]
                selected.append(line)
                stage = 3
            elif kind == 'serialization':
                match = re.search(r'Processing launch request: offerId\[([A-Za-z0-9:_-]+)\] contentId\[([0-9]{1,10})\] exe\[([^\]]+)\] cwd\[([^\]]+)\] args\[\] locale\[[A-Za-z]{2}_[A-Za-z]{2}\] isTrial\[(?:true|false)\] isElevated\[(?:true|false)\] requestSource\[RTP\] isLauncherElevated\[(?:true|false)\]$', line)
                if (match is None or stage != 4 or serialization_seen or
                        (match[1], match[2]) != (offer_id, content_id) or
                        not Path(match[3]).is_absolute() or str(Path(match[3]).resolve()) != launcher or
                        not Path(match[4]).is_absolute() or Path(match[4]).resolve() != Path(launcher).parent):
                    raise ValueError('Competing or mismatched EA launch serialization; no acknowledgement is authorized.')
                serialization_seen = True
                # This one matching same-thread postlude serializes the already
                # validated intent. Keep the four-line digest stable if it is
                # appended after the original observation; do not hash a new intent.
            else:
                match = re.search(r'Successful launch\. IDs: offerKey\.offerId=\[([A-Za-z0-9:_-]+)\], offerId=\[\], contentIds=\[([0-9]{1,10})\], slug=\[the-sims-4\]$', line)
                if match is None or stage != 3 or (match[1], match[2]) != (offer_id, content_id):
                    raise ValueError('Fresh EA launch pipeline has mismatched success identity.')
                selected.append(line)
                stage = 4
        if stage != 4:
            raise LaunchRecordPending('Fresh EA launch pipeline is incomplete for this handoff.')
        return {'offer_id': offer_id, 'content_id': content_id, 'launcher': launcher,
                'source': 'RTP', 'ea_pid': pid, 'timestamp': timestamp,
                'record_sha256': hashlib.sha256('\n'.join(selected).encode('utf-8')).hexdigest()}

    lines = [line for line in raw_lines if 'Processing launch request:' in line]
    if not lines:
        raise LaunchRecordPending('No fresh EA launch request exists for this handoff.')
    line = lines[-1]
    identity = re.search(r'offerId\[([A-Za-z0-9:_-]+)\] contentId\[([0-9]{1,10})\] exe\[([^\]]+)\]', line)
    source = re.search(r'requestSource\[([A-Za-z]+)\]', line)
    pid = re.search(r'PID:\s*([0-9]+)', line)
    timestamp = re.search(r'\[([0-9]{4}-[0-9]{2}-[0-9]{2}T[^\]]+Z)\]', line)
    if not all((identity, source, pid, timestamp)):
        raise ValueError('Unsupported fresh EA launch record; no permission acknowledgement is authorized.')
    return {'offer_id': identity[1], 'content_id': identity[2], 'launcher': str(Path(identity[3]).resolve()),
            'source': source[1], 'ea_pid': int(pid[1]),
            'timestamp': datetime.fromisoformat(timestamp[1].replace('Z', '+00:00')).timestamp(),
            'record_sha256': hashlib.sha256(line.encode('utf-8')).hexdigest()}


def make_launch_context(plan, handoff_at, offset, now=None):
    identity = plan['account_launch_identity']
    log = Path(identity['log']).resolve()
    record = processing_record(log, offset)
    context = {'offer_id': identity['offer_id'], 'content_id': identity['content_id'],
               'launcher': str(Path(identity['executable']).resolve()), 'handoff_at': handoff_at,
               'log': str(log), 'record_sha256': record['record_sha256'], 'ea_pid': record['ea_pid']}
    if record['offer_id'] != context['offer_id'] or record['content_id'] != context['content_id'] or record['launcher'] != context['launcher'] or record['source'] != 'RTP' or record['timestamp'] < handoff_at - 2:
        raise ValueError('Fresh EA request differs from this account-specific Sims launch handoff.')
    validate_launch_context(context, time.time() if now is None else now, {'pid': record['ea_pid']})
    return context


def wait_launch_context(plan, handoff_at, offset, seconds=LAUNCH_RECORD_WAIT_SECONDS,
                        read_context=None, monotonic=time.monotonic, pause=time.sleep):
    """Observe this single handoff; only an absent record permits another read.

    EA's processing record precedes its permission dialog, but it can become
    visible after the launcher's first read. The original offset and timestamp
    are preserved on every attempt. Malformed/other-game records, rotation,
    stale identity or expiry fail immediately; this never launches or sends UI
    input. The eventual context is revalidated by the elevated worker as usual.
    """
    if type(seconds) not in (int, float) or not 0 < seconds <= LAUNCH_RECORD_WAIT_SECONDS:
        raise ValueError('EA launch-record observation must be between 0 and 10 seconds.')
    read_context = read_context or make_launch_context
    deadline = monotonic() + seconds
    while True:
        try:
            return read_context(plan, handoff_at, offset)
        except LaunchRecordPending as error:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise LaunchRecordPending('No fresh EA launch request appeared within the bounded handoff observation.') from error
            pause(min(0.2, remaining))


def validate_launch_context(context, now, target, read_record=processing_record, expected_log=EA_LOG):
    if context is None:
        return
    if not isinstance(context, dict) or set(context) != {'offer_id', 'content_id', 'launcher', 'handoff_at', 'log', 'record_sha256', 'ea_pid'}:
        raise ValueError('Unexpected trusted Sims launch context.')
    if not isinstance(context['offer_id'], str) or not re.fullmatch('[A-Za-z0-9:_-]+', context['offer_id']) or not isinstance(context['content_id'], str) or not re.fullmatch('[0-9]{1,10}', context['content_id']) or not isinstance(context['record_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', context['record_sha256']):
        raise ValueError('Invalid typed Sims launch context.')
    if not isinstance(context['log'], str) or Path(context['log']).resolve() != Path(expected_log).resolve() or not isinstance(context['launcher'], str) or Path(context['launcher']).name.casefold() != 'ts4_launcher_x64.exe' or not _integer(context['ea_pid'], 1) or context['ea_pid'] != target['pid']:
        raise ValueError('Trusted Sims launch context is not bound to the verified EA process.')
    if type(context['handoff_at']) not in (int, float) or not now - LEASE_SECONDS <= context['handoff_at'] <= now + 2:
        raise ValueError('Trusted Sims launch context expired.')
    record = read_record(context['log'])
    if any(record[key] != context[key] for key in ('offer_id', 'content_id', 'launcher', 'record_sha256', 'ea_pid')) or record['source'] != 'RTP' or not context['handoff_at'] - 2 <= record['timestamp'] <= now + 2:
        raise ValueError('EA has another or changed launch request; no acknowledgement is authorized.')


def validate_request(request, work, now, pins=None, probe=process_identity, expected=EA_IMAGE):
    if not isinstance(request, dict) or set(request) != {'schema', 'nonce', 'expires_at', 'ea', 'source_sha256', 'launch_context'} or type(request['schema']) is not int or request['schema'] != 1:
        raise ValueError('Unexpected one-shot helper request schema.')
    if not isinstance(request['nonce'], str) or not re.fullmatch('[0-9a-f]{32}', request['nonce']):
        raise ValueError('Invalid one-shot helper nonce.')
    expires = request['expires_at']
    if type(expires) not in (int, float) or not now < expires <= now + LEASE_SECONDS:
        raise ValueError('One-shot helper request is expired or exceeds its lease.')
    if request['source_sha256'] != (source_identity() if pins is None else pins):
        raise ValueError('Helper source changed after the normal elevation request.')
    target = request['ea']
    if not isinstance(target, dict) or set(target) != {'pid', 'image', 'creation_time', 'session_id', 'elevated', 'ui_access', 'integrity'}:
        raise ValueError('Unexpected EA process identity schema.')
    if not all(_integer(target[key], 1 if key in ('pid', 'creation_time') else 0) for key in ('pid', 'creation_time', 'session_id', 'integrity')) or target['pid'] > 0xffffffff or not all(type(target[key]) is bool for key in ('elevated', 'ui_access')) or not isinstance(target['image'], str):
        raise ValueError('Invalid typed EA process identity.')
    if Path(target['image']).resolve() != Path(expected).resolve() or probe(target['pid']) != target:
        raise ValueError('Exact EA process changed; no acknowledgement is authorized.')
    validate_launch_context(request['launch_context'], now, target)
    return target


def acknowledge_exact(target, work, deadline, launch_context=None, clock=time.time):
    """Reuse existing exact dialog matchers, restricted to the pinned EA PID."""
    import ea_permission
    import ea_native_permission as native_module
    if clock() >= deadline or process_identity(target['pid']) != target:
        raise ValueError('EA permission request expired or its process changed.')
    validate_launch_context(launch_context, clock(), target)
    old = '$eaProcesses = @(Get-Process -Name EADesktop -ErrorAction SilentlyContinue)'
    if ea_permission.SCRIPT.count(old) != 1:
        raise ValueError('Exact UIA consent handler changed its process contract.')
    script = ea_permission.SCRIPT.replace(old,
        "$eaProcesses = @(Get-Process -Id " + str(target['pid']) + " -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -ceq 'EADesktop' -and $_.StartTime.ToUniversalTime().ToFileTimeUtc() -eq " + str(target['creation_time']) + " })")
    if script.count('$pattern.Invoke()') != 1:
        raise ValueError('Exact UIA handler changed its invocation contract.')
    script = script.replace('$pattern.Invoke()',
        "if ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() -ge " + str(int(deadline * 1000)) + ") { throw 'EA acknowledgement lease expired; no input sent.' }; $pattern.Invoke()")
    # The worker is already elevated by the normal runas request. This is not UAC.
    # A Sims handoff uses pixel recognition followed by a fresh log-ownership
    # check immediately before input; its generic EA dialog exposes no game ID.
    if launch_context is None:
        response = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True, text=True, timeout=min(15, max(1, deadline - clock())),
            creationflags=subprocess.CREATE_NO_WINDOW)
        if response.returncode == 0:
            receipt = json.loads(response.stdout)
            if receipt.get('acknowledged') is True:
                return receipt
    native = native_module.NativeEA([target['pid']])
    windows = native.windows()
    if len(windows) > 4:
        raise ValueError('EA window inventory exceeds the one-shot recognition bound.')
    matched, attempts = [], []
    for row in windows:
        if clock() >= deadline:
            raise ValueError('EA permission recognition lease expired; no input sent.')
        output = work / ('ea-broker-' + str(time.time_ns()) + '.bmp')
        try:
            image_hash = native.capture(row, output)
            observation = native_module.recognize(output)
            point = native_module.dialog_button(observation)
        except (OSError, ValueError) as error:
            attempts.append({'window': row, 'error': str(error)})
            continue
        matched.append((row, point, image_hash))
    if len(matched) != 1:
        return {'ok': False, 'acknowledged': False, 'attempts': attempts,
                'message': 'One exact EA permission dialog was not recognized; no input sent.'}
    row, point, image_hash = matched[0]
    if clock() >= deadline or process_identity(target['pid']) != target:
        raise ValueError('Exact EA process changed or recognition expired; no input sent.')
    fresh = work / ('ea-broker-' + str(time.time_ns()) + '.bmp')
    fresh_hash = native.capture(row, fresh)
    if native_module.dialog_button(native_module.recognize(fresh)) != point or clock() >= deadline or process_identity(target['pid']) != target:
        raise ValueError('EA permission recognition changed or expired; no input sent.')
    validate_launch_context(launch_context, clock(), target)
    native.click(row, point)
    return {'ok': True, 'acknowledged': True, 'window': row, 'point': point,
            'capture_sha256': image_hash, 'fresh_capture_sha256': fresh_hash,
            'message': 'Delivered OK to the exact EA permission dialog; game readiness is unverified.'}


def _json_exclusive(path, value):
    raw = json.dumps(value, sort_keys=True, indent=2).encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('One-shot helper receipt exceeds its bound.')
    with writable(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def worker(request_path, expected_hash, probe=process_identity, acknowledge=acknowledge_exact, clock=time.time):
    if expected_hash != _digest(__file__):
        raise ValueError('Elevated helper code differs from the requested source.')
    request_path = writable(request_path)
    work = evidence_directory(request_path.parent)
    if request_path.stat().st_size > MAX_BYTES:
        raise ValueError('One-shot request exceeds its bound.')
    raw = request_path.read_bytes()
    request = json.loads(raw)
    target = validate_request(request, work, clock(), probe=probe)
    nonce = request['nonce']
    if request_path.name != 'ea-broker-' + nonce + '.request.json':
        raise ValueError('Request filename is not bound to its nonce.')
    _json_exclusive(work / ('ea-broker-' + nonce + '.claim.json'), {'schema': 1, 'nonce': nonce, 'pid': os.getpid()})
    helper = probe(os.getpid())
    result = {'schema': 1, 'nonce': nonce, 'request_sha256': hashlib.sha256(raw).hexdigest(),
              'ea': target, 'helper': helper, 'launch_context': request['launch_context'], 'ok': False, 'acknowledged': False,
              'game_start_verified': False, 'windows_uac_automated': False,
              'elevated_helper_started': helper['elevated']}
    try:
        if not helper['elevated'] or helper['integrity'] < target['integrity'] or helper['session_id'] != target['session_id']:
            raise ValueError('Normal UAC approval did not produce a compatible helper token.')
        permission = acknowledge(target, work, request['expires_at'], request['launch_context'])
        if not isinstance(permission, dict) or type(permission.get('ok')) is not bool or type(permission.get('acknowledged')) is not bool:
            raise ValueError('Exact EA handler returned invalid proof flags.')
        result.update(permission=permission, ok=permission['ok'], acknowledged=permission['acknowledged'], message=permission.get('message', ''))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        result.update(ok=False, acknowledged=False, message=str(error))
    _json_exclusive(work / ('ea-broker-' + nonce + '.receipt.json'), result)
    return result


def shell_runas(request, source_hash):
    if os.name != 'nt':
        raise RuntimeError('Normal Windows elevation requires Windows.')
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [('cbSize', W.DWORD), ('fMask', W.ULONG), ('hwnd', W.HWND),
                    ('lpVerb', W.LPCWSTR), ('lpFile', W.LPCWSTR), ('lpParameters', W.LPCWSTR),
                    ('lpDirectory', W.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', W.HINSTANCE),
                    ('lpIDList', ctypes.c_void_p), ('lpClass', W.LPCWSTR), ('hkeyClass', W.HANDLE),
                    ('dwHotKey', W.DWORD), ('hIcon', W.HANDLE), ('hProcess', W.HANDLE)]
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ExecuteInfo)]
    shell.ShellExecuteExW.restype = W.BOOL
    info = ExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40 | 0x100  # NOCLOSEPROCESS | NOASYNC, normal UAC route.
    info.lpVerb = 'runas'
    info.lpFile = str(Path(sys.executable).resolve())
    info.lpParameters = subprocess.list2cmdline(['-I', '-S', str(Path(__file__).resolve()),
        '--worker', str(request), '--source-hash', source_hash])
    info.lpDirectory = str(TOOLS)
    info.nShow = 0  # The helper has no console; Windows still displays normal UAC.
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), 'Normal Windows elevation was declined or unavailable.')
    if not info.hProcess:
        raise OSError('Windows did not return an elevated helper process handle.')
    return info.hProcess


def validate_receipt(receipt, request, request_hash):
    if not isinstance(receipt, dict) or type(receipt.get('schema')) is not int or receipt.get('schema') != 1 or receipt.get('nonce') != request['nonce'] or receipt.get('request_sha256') != request_hash or receipt.get('ea') != request['ea'] or receipt.get('launch_context') != request['launch_context']:
        raise ValueError('Elevated receipt does not match the exact one-shot request.')
    helper = receipt.get('helper', {})
    if not isinstance(helper, dict) or set(helper) != set(request['ea']) or not all(_integer(helper[key], 1 if key in ('pid', 'creation_time') else 0) for key in ('pid', 'creation_time', 'session_id', 'integrity')) or not all(type(helper[key]) is bool for key in ('elevated', 'ui_access')) or not isinstance(helper['image'], str):
        raise ValueError('Elevated receipt has invalid typed helper identity.')
    if receipt.get('game_start_verified') is not False or receipt.get('windows_uac_automated') is not False or type(receipt.get('acknowledged')) is not bool or type(receipt.get('ok')) is not bool:
        raise ValueError('Elevated receipt has invalid proof flags.')
    if receipt['acknowledged'] and (not receipt['ok'] or helper.get('elevated') is not True or helper.get('integrity', 0) < request['ea']['integrity'] or helper.get('session_id') != request['ea']['session_id']):
        raise ValueError('Elevated receipt lacks compatible token evidence.')
    return receipt


def helper_exited(handle):
    if not handle:
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.WaitForSingleObject.restype = W.DWORD
    result = kernel.WaitForSingleObject(handle, 0)
    if result == 0xffffffff:
        raise OSError(ctypes.get_last_error(), 'Cannot observe one-shot elevated helper.')
    return result == 0


def elevate_once(work, diagnostic=diagnose, runas=shell_runas, clock=time.time, pause=time.sleep, nonce=None,
                 launch_context=None, exited=helper_exited):
    work = evidence_directory(work)
    observed = diagnostic()
    if not observed.get('ok') or len(observed.get('targets', [])) != 1:
        raise ValueError('Exactly one verified EA process is required for the one-shot helper.')
    nonce = nonce or uuid.uuid4().hex
    if not re.fullmatch('[0-9a-f]{32}', nonce):
        raise ValueError('Invalid one-shot helper nonce.')
    validate_launch_context(launch_context, clock(), observed['targets'][0])
    request = {'schema': 1, 'nonce': nonce, 'expires_at': clock() + LEASE_SECONDS,
               'ea': observed['targets'][0], 'source_sha256': source_identity(), 'launch_context': launch_context}
    request_path = work / ('ea-broker-' + nonce + '.request.json')
    _json_exclusive(request_path, request)
    request_hash = _digest(request_path)
    receipt_path = work / ('ea-broker-' + nonce + '.receipt.json')
    def host_failure(message):
        result = {'schema': 1, 'nonce': nonce, 'request_sha256': request_hash,
                  'ea': request['ea'], 'launch_context': launch_context,
                  'ok': False, 'acknowledged': False, 'worker_receipt_verified': False,
                  'game_start_verified': False, 'windows_uac_automated': False,
                  'message': message}
        _json_exclusive(work / ('ea-broker-' + nonce + '.host-result.json'), result)
        return result
    handle = None
    try:
        handle = runas(request_path, request['source_sha256']['ea_permission_broker.py'])
        while clock() < request['expires_at']:
            if receipt_path.exists():
                if not 0 < receipt_path.stat().st_size <= MAX_BYTES:
                    raise ValueError('Elevated receipt exceeds its bound.')
                try:
                    receipt = json.loads(receipt_path.read_bytes())
                except json.JSONDecodeError:
                    pause(0.05)  # A bounded exclusively created receipt may still be flushing.
                    continue
                return validate_receipt(receipt, request, request_hash)
            if exited(handle):
                return host_failure('Elevated helper exited without a validated receipt; no acknowledgement is claimed.')
            pause(min(0.1, request['expires_at'] - clock()))
        return host_failure('One-shot helper lease expired; no acknowledgement or game start is claimed.')
    except (OSError, ValueError) as error:
        return host_failure(str(error))
    finally:
        if handle and os.name == 'nt':
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CloseHandle.argtypes = [W.HANDLE]
            kernel.CloseHandle.restype = W.BOOL
            kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--diagnose', action='store_true')
    group.add_argument('--elevate-once', action='store_true', help='Request normal UAC approval for one exact EA dialog.')
    group.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--source-hash', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        result = worker(args.worker, args.source_hash)
    elif args.elevate_once:
        if args.work is None:
            parser.error('--elevate-once requires an existing external --work directory.')
        result = elevate_once(args.work)
    else:
        result = diagnose()
    print(json.dumps(result, indent=2))
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
