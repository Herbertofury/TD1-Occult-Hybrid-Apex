"""One normal Windows elevation to focus the authenticated disposable game.

The fixed worker focuses one verified Sims Canvas. A separately typed request
may submit one existing game-owned input, with focus and submission in the same
helper. It approves no UAC dialog and installs no persistent helper.
"""
import argparse
import ctypes
from ctypes import wintypes as W
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
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

PINS = ('game_focus.py', 'game_window.py', 'ea_permission_broker.py',
        'apex_cli.py', 'reusable_profile.py', 'test_profile.py', 'game_launch.py', 'windows_process.py',
        'candidate_install.py', 'source_manifest.py')
LEASE = 90


class HelperNotStarted(OSError):
    """Windows positively refused the helper before creating its process."""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pins():
    return {name: digest(TOOLS / name) for name in PINS}


def exclusive(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def validate(request, now, pins, identity, process, state_digest):
    core = {'schema', 'nonce', 'expires_at', 'state', 'state_sha256', 'sources', 'binding', 'game'}
    if (not isinstance(request, dict) or set(request) not in (core, core | {'input'}) or
            type(request['schema']) is not int or request['schema'] != 1 or
            not isinstance(request['nonce'], str) or not re.fullmatch('[0-9a-f]{32}', request['nonce']) or
            type(request['expires_at']) not in (int, float) or
            not now < request['expires_at'] <= now + LEASE or request['sources'] != pins or
            request['state_sha256'] != state_digest):
        raise ValueError('Focus lease, journal or pinned helper sources changed.')
    binding = request['binding']
    if (not isinstance(binding, dict) or set(binding) != {'pid', 'test_token', 'script_sha256'} or
            type(binding['pid']) is not int or not 0 < binding['pid'] <= 0xffffffff or
            any(identity.get(key) != value for key, value in binding.items()) or
            request['game'] != process or process.get('pid') != binding['pid'] or
            Path(process.get('image', '')).name.casefold() != 'ts4_x64.exe'):
        raise ValueError('Focus target process or authenticated disposable bridge changed.')
    if 'input' in request:
        value = request['input']
        if (not isinstance(value, dict) or set(value) != {'request_id', 'argument'} or
                not isinstance(value['request_id'], str) or not re.fullmatch('[0-9a-f]{32}', value['request_id'])):
            raise ValueError('Input helper requires one exact native request ID.')
        argument = value['argument']
        if (not isinstance(argument, dict) or set(argument) != {'command', 'x', 'y', 'width', 'height'} or
                any(type(number) is not int for number in argument.values()) or
                argument['command'] not in (1, 2, 3) or
                not all(1 <= argument[name] <= 8192 for name in ('width', 'height')) or
                (argument['command'] == 2 and (argument['x'] not in (122, 27, 13, 9, 32) or argument['y'] != 0)) or
                (argument['command'] != 2 and not (0 <= argument['x'] < argument['width'] and 0 <= argument['y'] < argument['height']))):
            raise ValueError('Input helper requires the bounded native game-input contract.')
    return binding


def foreground(window):
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetForegroundWindow.restype = W.HWND
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    hwnd = user.GetForegroundWindow(); pid = W.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {'hwnd': int(hwnd or 0), 'pid': pid.value,
            'verified': bool(hwnd == window.get('hwnd') and pid.value == window.get('pid'))}


def worker(path, expected_hash):
    # Verify the worker itself before importing the fixed repository modules.
    if digest(__file__) != expected_hash:
        raise ValueError('Focus worker source hash differs from its invocation.')
    import reusable_profile
    from apex_cli import verified_identity
    from ea_permission_broker import evidence_directory, process_identity
    from game_window import focus
    path = reusable_profile.writable(path)
    work = evidence_directory(path.parent)
    if path.stat().st_size > 65536:
        raise ValueError('Focus request exceeds its bound.')
    request = json.loads(path.read_bytes())
    nonce = request.get('nonce', '')
    if not isinstance(nonce, str) or not re.fullmatch('[0-9a-f]{32}', nonce) or path.name != 'game-focus-' + nonce + '.request.json':
        raise ValueError('Focus request filename differs from its nonce.')
    output = work / ('game-focus-' + nonce + '.receipt.json')
    if output.exists():
        raise ValueError('A one-shot focus receipt already exists; no replay.')
    state = reusable_profile.writable(request.get('state', ''))
    observed = verified_identity(state)
    target = process_identity(observed['pid'])
    validate(request, time.time(), source_pins(), observed, target, digest(state))
    helper = process_identity(os.getpid())
    result = {'schema': 1, 'nonce': nonce, 'request_sha256': digest(path),
              'game': target, 'helper': helper, 'ok': False, 'input_sent': False,
              'windows_uac_automated': False, 'focus_attempted': False}
    try:
        if (helper['integrity'] < target['integrity'] or helper['session_id'] != target['session_id']):
            raise ValueError('Focus helper has no compatible Windows token/session.')
        validate(request, time.time(), source_pins(), verified_identity(state),
                 process_identity(target['pid']), digest(state))
        result['focus_attempted'] = True
        focused = focus(target['pid'], allow_alt_unlock=True)
        result['focus'] = focused
        result['ok'] = bool(focused.get('ok') is True and focused.get('foreground_verified') is True and
                            process_identity(target['pid']) == target)
        if 'input' in request and result['ok']:
            from apex_cli import get
            argument = request['input']['argument']
            if any(focused['window'][name] != argument[name] for name in ('width', 'height')):
                raise ValueError('Focused Canvas dimensions differ from the measured input viewport.')
            if not time.time() < request['expires_at']:
                raise ValueError('Input lease expired before submission.')
            result.update(input_attempted=True, input_sent=None, ok=False)
            query = {'action': 'test_input', 'request_id': request['input']['request_id'],
                     'value': json.dumps({'test_token': request['binding']['test_token'], 'value': argument})}
            # No transport replay. A lost response retains this exact UUID and
            # uncertain submission; the caller must observe it independently.
            native = get('/api/native', query, timeout=min(12, request['expires_at'] - time.time()))
            result['native_input'] = native
            result['ok'] = native.get('ok') is True and native.get('input_state') == 4
            if result['ok']: result['input_sent'] = True
            elif native.get('input_submitted') is False and native.get('native_code') in (-1, -2, -3, -4) and native.get('input_state') == 0:
                result['input_sent'] = False
    except (OSError, ValueError, RuntimeError) as error:
        result['message'] = str(error)
    exclusive(output, result)
    return result


def runas(path, expected_hash):
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [('cbSize', W.DWORD), ('fMask', W.ULONG), ('hwnd', W.HWND),
                    ('lpVerb', W.LPCWSTR), ('lpFile', W.LPCWSTR), ('lpParameters', W.LPCWSTR),
                    ('lpDirectory', W.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', W.HINSTANCE),
                    ('lpIDList', ctypes.c_void_p), ('lpClass', W.LPCWSTR), ('hkeyClass', W.HANDLE),
                    ('dwHotKey', W.DWORD), ('hIcon', W.HANDLE), ('hProcess', W.HANDLE)]
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ExecuteInfo)]
    shell.ShellExecuteExW.restype = W.BOOL
    info = ExecuteInfo(); info.cbSize = ctypes.sizeof(info); info.fMask = 0x140
    info.lpVerb = 'runas'; info.lpFile = str(Path(sys.executable).resolve())
    info.lpParameters = subprocess.list2cmdline(['-I', '-S', str(Path(__file__).resolve()),
                                               '--worker', str(path), '--source-hash', expected_hash])
    info.lpDirectory = str(TOOLS); info.nShow = 0
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        raise HelperNotStarted(ctypes.get_last_error(), 'Normal Windows focus-helper elevation was unavailable.')
    if not info.hProcess:
        # A successful shell dispatch without a process handle does not prove
        # that its worker failed to run. Preserve that uncertainty.
        raise OSError('Windows accepted the helper dispatch without an observable process handle.')
    return info.hProcess


def elevate_once(state, output, native_input=None):
    import reusable_profile
    from apex_cli import verified_identity
    from ea_permission_broker import evidence_directory, process_identity, helper_exited
    state = reusable_profile.writable(state); output = reusable_profile.writable(output)
    work = evidence_directory(output.parent)
    if output.exists() or output.suffix != '.json' or output == state:
        raise ValueError('Focus proof requires a new external JSON output.')
    observed = verified_identity(state); target = process_identity(observed['pid'])
    nonce = uuid.uuid4().hex
    request = {'schema': 1, 'nonce': nonce, 'expires_at': time.time() + LEASE,
               'state': str(state), 'state_sha256': digest(state), 'sources': source_pins(),
               'binding': {key: observed[key] for key in ('pid', 'test_token', 'script_sha256')}, 'game': target}
    if native_input is not None:
        request['input'] = native_input
    validate(request, time.time(), source_pins(), observed, target, digest(state))
    path = work / ('game-focus-' + nonce + '.request.json'); exclusive(path, request)
    receipt_path = work / ('game-focus-' + nonce + '.receipt.json')
    result = {'schema': 1, 'ok': False, 'request_sha256': digest(path),
              'input_sent': False, 'windows_uac_automated': False, 'game': target,
              'helper_launch_attempted': False, 'helper_started': False,
              'helper_launch_refused': False, 'worker_receipt_verified': False,
              'host_binding_verified': False}
    handle = None
    try:
        result['helper_launch_attempted'] = True
        handle = runas(path, request['sources']['game_focus.py'])
        result['helper_started'] = True
        while time.time() < request['expires_at']:
            if receipt_path.exists():
                if not 0 < receipt_path.stat().st_size <= 65536:
                    raise ValueError('Focus worker receipt exceeds its bound.')
                try: receipt = json.loads(receipt_path.read_bytes())
                except json.JSONDecodeError:
                    time.sleep(.05); continue
                if (receipt.get('schema') != 1 or receipt.get('nonce') != nonce or
                        receipt.get('request_sha256') != digest(path) or receipt.get('game') != target or
                        ('input' not in request and receipt.get('input_sent') is not False) or
                        ('input' in request and receipt.get('input_sent') is not None and type(receipt.get('input_sent')) is not bool) or
                        receipt.get('windows_uac_automated') is not False or
                        type(receipt.get('ok')) is not bool):
                    raise ValueError('Focus receipt does not match the fixed one-shot request.')
                result['worker'] = receipt
                result['worker_receipt_verified'] = True
                result['input_sent'] = receipt['input_sent']
                validate(request, time.time(), source_pins(), verified_identity(state), process_identity(target['pid']), digest(state))
                result['host_binding_verified'] = True
                result['foreground'] = foreground(receipt.get('focus', {}).get('window', {}))
                result['ok'] = receipt['ok'] and result['foreground']['verified']
                break
            if helper_exited(handle):
                result['message'] = 'Focus helper exited without a validated receipt.'; break
            time.sleep(.1)
        else:
            result['message'] = 'Focus helper lease expired; no focus is claimed.'
    except HelperNotStarted as error:
        result['helper_launch_refused'] = True
        result['message'] = str(error)
    except (OSError, ValueError, RuntimeError) as error:
        result['message'] = str(error)
    finally:
        if handle:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CloseHandle.argtypes = [W.HANDLE]; kernel.CloseHandle(handle)
    exclusive(output, result)
    return result


def requires_elevated_input(pid):
    if os.name != 'nt': return False
    from ea_permission_broker import process_identity
    try:
        target, host = process_identity(pid), process_identity(os.getpid())
        return target['integrity'] > host['integrity'] and target['session_id'] == host['session_id']
    except (OSError, ValueError):
        return False


def native_input_once(state, value, request_id):
    import reusable_profile
    state_path, journal, _, _ = reusable_profile.load(state)
    payload = json.loads(value)
    if set(payload) != {'test_token', 'value'} or payload.get('test_token') != journal['token']:
        raise ValueError('Input helper payload differs from the disposable token.')
    output = state_path.parent / ('game-input-' + request_id + '.json')
    result = elevate_once(state, output, {'request_id': request_id, 'argument': payload['value']})
    return input_result(result, request_id, output, digest(output))


def input_result(result, request_id, output, proof_sha256):
    """Retain native ACKs while keeping host binding and submission separate."""
    worker = result.get('worker', {}) if result.get('worker_receipt_verified') is True else {}
    native = worker.get('native_input')
    native = native if isinstance(native, dict) else None
    proof = {'elevated_input_proof': str(output), 'elevated_input_proof_sha256': proof_sha256}
    if (result.get('ok') is True and result.get('host_binding_verified') is True and
            native is not None and native.get('ok') is True and
            native.get('input_state') == 4 and worker.get('input_sent') is True):
        return dict(native, **proof)
    # A missing receipt after a dispatched helper is not a pre-input refusal.
    # Nor does a native failure flag rule out a partly submitted input. Only
    # the fixed worker's positive pre-input result or Windows' rejected launch
    # permits a caller to conclude that nothing was submitted.
    sent = worker.get('input_sent')
    if sent is False or result.get('helper_launch_refused') is True:
        submitted, outcome = False, 'refused-before-input'
    else:
        submitted = True if sent is True else None
        outcome = 'unresolved'
    response = dict(native or {}, ok=False, request_id=request_id, outcome=outcome,
                    input_submitted=submitted, host_input_verified=False,
                    message=result.get('message', worker.get('message',
                        'Host input proof did not verify; retain this request ID and do not replay it.')), **proof)
    if native is not None:
        response['native_acknowledgment'] = dict(native)
    return response


def focus_for_input(state, pid, prior):
    """One focus-only fallback after explicit pre-input refusal; no input replay."""
    import reusable_profile
    from apex_cli import verified_identity
    try:
        state_path, _, _, _ = reusable_profile.load(state)
        if not isinstance(state_path, Path):
            raise ValueError('Focus fallback requires a validated external journal path.')
        observed = verified_identity(state)
        if type(pid) is not int or observed['pid'] != pid or prior.get('ok') is not False:
            raise ValueError('Focus fallback requires the same authenticated PID and an explicit pre-input refusal.')
        result = elevate_once(state, state_path.parent / ('game-input-focus-' + uuid.uuid4().hex + '.json'))
        if result.get('ok') is True:
            return dict(result['worker']['focus'], focus_helper_proof=result['request_sha256'],
                        automatic_pre_input_focus=True)
        return dict(prior, ok=False, input_submitted=False, elevated_focus=result)
    except (OSError, ValueError, RuntimeError) as error:
        return dict(prior, ok=False, input_submitted=False, focus_helper_error=str(error))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', required=True, type=Path)
    parser.add_argument('--source-hash', required=True)
    args = parser.parse_args()
    worker(args.worker, args.source_hash)
