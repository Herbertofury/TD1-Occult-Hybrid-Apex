"""Restart only the installed EA client; keep its account and game files intact.

An optional reversible HKCU change removes only its RUNASADMIN compatibility
token. A normal UAC close-only helper may close the pinned old EA lifetime; the
new client always starts from the original non-elevated medium user process.
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
from xml.etree import ElementTree

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import ea_permission_broker as broker
import game_lifecycle
import launch_compatibility as compatibility
import reusable_profile
import test_profile
import windows_process
from source_manifest import sha256, write_json

EA_IMAGE = broker.EA_IMAGE
PINS = ('ea_restart.py', 'ea_permission_broker.py', 'game_lifecycle.py',
        'launch_compatibility.py', 'reusable_profile.py', 'test_profile.py',
        'windows_process.py', 'source_manifest.py', 'game_launch.py')
MAX_RECEIPT_BYTES = 128 * 1024


def _manifest_level(raw):
    """EA-only absent-privilege distinction; the strict Sims parser is unchanged."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1024 * 1024:
        raise ValueError('EA manifest is absent or oversized.')
    plain = raw.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in plain or b'<!ENTITY' in plain:
        raise ValueError('EA manifest declarations are unsupported.')
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError as error:
        raise ValueError('EA manifest is malformed.') from error
    if root.tag not in ('assembly', '{urn:schemas-microsoft-com:asm.v1}assembly'):
        raise ValueError('EA manifest does not have its assembly root.')
    nodes = list(root.iter())
    local = lambda node: node.tag.rsplit('}', 1)[-1]
    levels = [node for node in nodes if local(node) == 'requestedExecutionLevel']
    if not levels:
        if any(local(node) in ('trustInfo', 'requestedPrivileges') for node in nodes):
            raise ValueError('EA privilege declaration lacks an execution level.')
        return 'legacy-default'
    if len(levels) != 1 or levels[0].get('level') not in ('asInvoker', 'highestAvailable', 'requireAdministrator'):
        raise ValueError('EA execution level is ambiguous or unsupported.')
    if levels[0].get('uiAccess', 'false').lower() != 'false':
        raise ValueError('EA requests a UIAccess token; no normal-permissions override.')
    return levels[0].get('level')


def ea_execution_level(path):
    """Read installed EA RT_MANIFEST id1 as data without executing its image."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LoadLibraryExW.argtypes = [W.LPCWSTR, W.HANDLE, W.DWORD]; kernel.LoadLibraryExW.restype = W.HMODULE
    kernel.FindResourceW.argtypes = [W.HMODULE, ctypes.c_void_p, ctypes.c_void_p]; kernel.FindResourceW.restype = W.HANDLE
    kernel.SizeofResource.argtypes = [W.HMODULE, W.HANDLE]; kernel.SizeofResource.restype = W.DWORD
    kernel.LoadResource.argtypes = [W.HMODULE, W.HANDLE]; kernel.LoadResource.restype = W.HANDLE
    kernel.LockResource.argtypes = [W.HANDLE]; kernel.LockResource.restype = ctypes.c_void_p
    kernel.FreeLibrary.argtypes = [W.HMODULE]; kernel.FreeLibrary.restype = W.BOOL
    module = kernel.LoadLibraryExW(str(path), None, 0x22)
    if not module: raise OSError('Cannot read exact installed EA resources.')
    try:
        resource = kernel.FindResourceW(module, ctypes.c_void_p(1), ctypes.c_void_p(24))
        size = kernel.SizeofResource(module, resource) if resource else 0
        if not 0 < size <= 1024 * 1024: raise ValueError('Missing or oversized EA RT_MANIFEST id1.')
        pointer = kernel.LockResource(kernel.LoadResource(module, resource))
        if not pointer: raise OSError('Cannot read exact EA manifest data.')
        return _manifest_level(ctypes.string_at(pointer, size))
    finally:
        kernel.FreeLibrary(module)


def machine_layer(executable):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, compatibility.LAYERS) as key:
            value, kind = winreg.QueryValueEx(key, executable)
    except FileNotFoundError:
        return None
    if kind != winreg.REG_SZ or not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Unsupported machine EA compatibility value.')
    return value


def _identity(value, image):
    keys = {'pid', 'image', 'creation_time', 'session_id', 'elevated', 'ui_access', 'integrity'}
    if (not isinstance(value, dict) or set(value) != keys or
            any(type(value[k]) is not int or value[k] < 0 for k in
                ('pid', 'creation_time', 'session_id', 'integrity')) or
            not 0 < value['pid'] <= 0xffffffff or not 0 < value['creation_time'] <= 0xffffffffffffffff or
            any(type(value[k]) is not bool for k in ('elevated', 'ui_access')) or
            not isinstance(value['image'], str) or Path(value['image']).resolve() != Path(image).resolve()):
        raise ValueError('EA process must have its exact installed image and typed lifetime/token identity.')
    return value


def _live(target, probe=broker.process_identity, observe=windows_process.observe):
    row = observe(target['pid'], expected_path=target['image'],
                  expected_creation_time=target['creation_time'])
    if row is None:
        return False
    if probe(target['pid']) != target:
        raise ValueError('EA process lifetime or token changed; no action repeated.')
    return True


def _main_windows(pid):
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user.EnumWindows.argtypes = [callback, W.LPARAM]; user.EnumWindows.restype = W.BOOL
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    user.IsWindowVisible.argtypes = [W.HWND]; user.IsWindowVisible.restype = W.BOOL
    user.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]; user.GetClientRect.restype = W.BOOL
    rows = []
    @callback
    def visit(hwnd, _):
        owner, rect = W.DWORD(), W.RECT()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user.IsWindowVisible(hwnd) and user.GetClientRect(hwnd, ctypes.byref(rect)):
            if rect.right - rect.left >= 200 and rect.bottom - rect.top >= 150:
                rows.append(int(hwnd))
        return len(rows) <= 8
    if not user.EnumWindows(visit, 0) or len(rows) > 8:
        raise ValueError('Exact EA visible-window inventory is unavailable or oversized.')
    return rows


def _normal_close(target, guard, windows=_main_windows):
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    user.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM,
                                       W.UINT, W.UINT, ctypes.POINTER(ctypes.c_size_t)]
    user.SendMessageTimeoutW.restype = W.LPARAM
    rows = windows(target['pid']); sent = []
    for hwnd in rows:
        guard()
        owner = W.DWORD(); user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != target['pid']:
            raise ValueError('EA HWND changed owner before normal close.')
        result = ctypes.c_size_t()
        if not user.SendMessageTimeoutW(hwnd, 0x0010, 0, 0, 2, 1000, ctypes.byref(result)):
            raise OSError(ctypes.get_last_error(), 'Exact EA WM_CLOSE was not acknowledged.')
        sent.append(hwnd)
    return {'normal_close_requested': bool(sent), 'window_ids': sent}


def _terminate_exact(target, guard):
    """Terminate only the same verified EA lifetime on its opened handle."""
    guard()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]; kernel.OpenProcess.restype = W.HANDLE
    kernel.GetProcessTimes.argtypes = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4
    kernel.GetProcessTimes.restype = W.BOOL
    kernel.TerminateProcess.argtypes = [W.HANDLE, W.UINT]; kernel.TerminateProcess.restype = W.BOOL
    kernel.CloseHandle.argtypes = [W.HANDLE]; kernel.CloseHandle.restype = W.BOOL
    handle = kernel.OpenProcess(0x1001, False, target['pid'])
    if not handle:
        raise OSError(ctypes.get_last_error(), 'Cannot open the exact old EA process for explicit tray shutdown.')
    try:
        times = [W.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(x) for x in times]):
            raise OSError('Cannot recheck exact EA creation time on termination handle.')
        created = times[0].dwLowDateTime | times[0].dwHighDateTime << 32
        if created != target['creation_time'] or times[1].dwLowDateTime or times[1].dwHighDateTime:
            raise ValueError('EA termination handle is not the exact live old lifetime.')
        guard()
        if _main_windows(target['pid']):
            raise ValueError('Visible EA main window remains; explicit tray shutdown cannot terminate it.')
        if not kernel.TerminateProcess(handle, 0):
            raise OSError(ctypes.get_last_error(), 'Exact old EA tray shutdown failed.')
    finally:
        kernel.CloseHandle(handle)


def _normal_start(executable):
    # No elevated helper launches a client. The caller's medium token is checked
    # immediately before this fixed command and the new token is observed later.
    subprocess.Popen([str(executable)], cwd=str(Path(executable).parent),
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _exclusive(path, value):
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError('EA restart receipt exceeds its bound.')
    with reusable_profile.writable(path).open('xb') as stream:
        stream.write(raw)


def close_once(target, force, guard, deadline, live=_live, close=_normal_close,
               terminate=_terminate_exact, windows=_main_windows, clock=time.monotonic, pause=time.sleep):
    guard()
    if not live(target):
        return {'ok': True, 'closed': True, 'already_exited': True, 'forced': False}
    class OldEaExited(Exception):
        pass
    def action_guard():
        guard()
        if not live(target): raise OldEaExited()
    try:
        normal = close(target, action_guard)
    except OldEaExited:
        return {'ok': True, 'closed': True, 'already_exited': True, 'forced': False}
    wait_until = min(deadline, clock() + 3)
    while clock() < wait_until and live(target):
        guard(); pause(min(.1, max(0, wait_until - clock())))
    if not live(target):
        return dict(normal, ok=True, closed=True, forced=False)
    if not force:
        return dict(normal, ok=False, closed=False, forced=False,
                    message='EA remains alive after normal close; no force option was supplied.')
    guard()
    if clock() >= deadline or windows(target['pid']):
        raise ValueError('EA is not verified tray-only within the lease; no termination sent.')
    try:
        terminate(target, action_guard)
    except OldEaExited:
        return dict(normal, ok=True, closed=True, forced=False)
    while clock() < deadline and live(target):
        guard(); pause(min(.1, max(0, deadline - clock())))
    closed = not live(target)
    return dict(normal, ok=closed, closed=closed, forced=True)


def _runas(request_path, source_hash):
    if os.name != 'nt':
        raise RuntimeError('Normal Windows approval requires Windows.')
    class Info(ctypes.Structure):
        _fields_ = [('cbSize', W.DWORD), ('fMask', W.ULONG), ('hwnd', W.HWND),
            ('lpVerb', W.LPCWSTR), ('lpFile', W.LPCWSTR), ('lpParameters', W.LPCWSTR),
            ('lpDirectory', W.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', W.HINSTANCE),
            ('lpIDList', ctypes.c_void_p), ('lpClass', W.LPCWSTR), ('hkeyClass', W.HANDLE),
            ('dwHotKey', W.DWORD), ('hIcon', W.HANDLE), ('hProcess', W.HANDLE)]
    info = Info(); info.cbSize = ctypes.sizeof(info); info.fMask = 0x140
    info.lpVerb = 'runas'; info.lpFile = str(Path(sys.executable).resolve())
    info.lpParameters = subprocess.list2cmdline(['-I', '-S', str(Path(__file__).resolve()),
        '--worker', str(request_path), '--source-hash', source_hash])
    info.lpDirectory = str(TOOLS); info.nShow = 0
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(Info)]; shell.ShellExecuteExW.restype = W.BOOL
    if not shell.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
        raise OSError(ctypes.get_last_error(), 'Normal UAC approval was declined or unavailable.')
    return info.hProcess


def worker(request_path, source_hash, probe=broker.process_identity, clock=time.time,
           monotonic=time.monotonic, action=close_once):
    if source_hash != sha256(__file__):
        raise ValueError('EA close-only helper source changed.')
    request_path = reusable_profile.writable(request_path)
    if not 0 < request_path.stat().st_size <= MAX_RECEIPT_BYTES:
        raise ValueError('EA close request is absent or oversized.')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    keys = {'schema','nonce','expires_at','state','token','profile','target','image_sha256','force_if_tray','source_sha256'}
    if (not isinstance(request, dict) or set(request) != keys or type(request['schema']) is not int or request['schema'] != 1 or
            not isinstance(request['nonce'], str) or not re.fullmatch('[0-9a-f]{32}', request['nonce']) or
            request_path.name != 'ea-restart-' + request['nonce'] + '.request.json' or
            type(request['expires_at']) not in (int,float) or not math.isfinite(request['expires_at']) or
            not clock() < request['expires_at'] <= clock() + 90 or type(request['force_if_tray']) is not bool or
            request['source_sha256'] != {name:sha256(TOOLS/name) for name in PINS}):
        raise ValueError('EA close-only capability is untyped, expired or has changed source.')
    target = _identity(request['target'], EA_IMAGE)
    _, journal, profile, original = reusable_profile.load(request['state'])
    if journal['token'] != request['token'] or str(profile) != request['profile'] or request_path.parent in (profile, original) or profile in request_path.parents or original in request_path.parents:
        raise ValueError('EA close-only capability does not belong to the exact external test profile.')
    helper = probe(os.getpid())
    if helper.get('elevated') is not True or helper.get('integrity',0) < target['integrity'] or helper.get('session_id') != target['session_id']:
        raise ValueError('Normal UAC approval did not produce a same-session close-only helper.')
    def guard():
        test_profile.require_closed()
        if clock() >= request['expires_at'] or sha256(EA_IMAGE) != request['image_sha256']:
            raise ValueError('EA close-only lease or executable changed.')
        _, fresh_journal, fresh_profile, fresh_original = reusable_profile.load(request['state'])
        if (fresh_journal['token'] != journal['token'] or fresh_profile != profile or fresh_original != original or
                not test_profile.status(request['state']).get('ready_to_launch')):
            raise ValueError('Disposable profile changed before EA close-only operation.')
    guard()
    _exclusive(request_path.with_name('ea-restart-' + request['nonce'] + '.claim.json'),
               {'schema':1,'nonce':request['nonce'],'pid':os.getpid()})
    result = {'schema':1,'nonce':request['nonce'],'request_sha256':sha256(request_path),
              'target':target,'helper':helper,'ok':False,'closed':False,'ea_started':False,'windows_uac_automated':False}
    try:
        result['close'] = action(target, request['force_if_tray'], guard,
            monotonic()+max(0,request['expires_at']-clock()))
        result.update(ok=result['close'].get('ok') is True, closed=result['close'].get('closed') is True)
    except (OSError,ValueError,RuntimeError) as error:
        result['error'] = str(error)
    _exclusive(request_path.with_name('ea-restart-' + request['nonce'] + '.receipt.json'),result)
    return result


def _elevated_close(state, journal, profile, target, image_hash, force, output, deadline,
                    clock=time.monotonic, pause=time.sleep, runas=_runas):
    nonce = uuid.uuid4().hex
    request = {'schema':1,'nonce':nonce,'expires_at':time.time()+min(90,max(0,deadline-clock())),
        'state':str(Path(state).resolve()),'token':journal['token'],'profile':str(profile),
        'target':target,'image_sha256':image_hash,'force_if_tray':force,
        'source_sha256':{name:sha256(TOOLS/name) for name in PINS}}
    path=output.parent/('ea-restart-'+nonce+'.request.json');_exclusive(path,request)
    handle=None
    try:
        handle=runas(path,request['source_sha256']['ea_restart.py'])
        receipt=path.with_name('ea-restart-'+nonce+'.receipt.json')
        while clock()<deadline:
            if receipt.exists():
                if not 0<receipt.stat().st_size<=MAX_RECEIPT_BYTES: raise ValueError('EA close receipt exceeds its bound.')
                result=json.loads(receipt.read_text(encoding='utf-8'))
                if not isinstance(result,dict) or not isinstance(result.get('helper'),dict):
                    raise ValueError('EA close receipt is not a typed object.')
                helper=result.get('helper',{})
                if (result.get('schema')!=1 or result.get('nonce')!=nonce or result.get('request_sha256')!=sha256(path) or result.get('target')!=target or
                        result.get('ea_started') is not False or result.get('windows_uac_automated') is not False or
                        type(result.get('ok')) is not bool or type(result.get('closed')) is not bool or
                        helper.get('elevated') is not True or helper.get('session_id')!=target['session_id'] or helper.get('integrity',0)<target['integrity']):
                    raise ValueError('EA close receipt does not match its exact one-shot capability.')
                return result
            if broker.helper_exited(handle): raise ValueError('EA close-only helper exited without a receipt; never repeat it.')
            pause(min(.1,max(0,deadline-clock())))
        raise TimeoutError('EA close-only lease expired; no new client was launched.')
    finally:
        if handle:
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle(handle)


def run(state, operation, output, *, normal_permissions=False, force_if_tray=False,
        elevate_close_once=False, recovery=None, expected_recovery_sha256=None, seconds=45,
        layers=None, machine=machine_layer, manifest=ea_execution_level,
        image=EA_IMAGE, probe=broker.process_identity, diagnostic=broker.diagnose,
        live=_live, close=close_once, elevated_close=_elevated_close, start=_normal_start,
        inventory=broker.ea_pids, clock=time.monotonic, pause=time.sleep):
    if operation not in ('status','restart','restore') or any(type(x) is not bool for x in (normal_permissions,force_if_tray,elevate_close_once)) or type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=90:
        raise ValueError('Use a typed EA restart operation and bounded lease.')
    if operation!='restart' and (normal_permissions or force_if_tray or elevate_close_once):
        raise ValueError('EA mutation options require the explicit restart operation.')
    if operation=='restore' and (recovery is None or not isinstance(expected_recovery_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_recovery_sha256)):
        raise ValueError('EA restoration requires its exact previous recovery receipt hash.')
    if operation!='restore' and (recovery is not None or expected_recovery_sha256 is not None):
        raise ValueError('Recovery inputs apply only to the explicit restore operation.')
    state_path,journal,profile,original=reusable_profile.load(state)
    # EA's updater uses its installed canonical path as a version junction.
    # Keep that exact registry value name; pin the resolved file separately.
    output=reusable_profile.writable(output);image=Path(image).absolute()
    if (output.exists() or output.suffix.lower()!='.json' or not output.parent.is_dir() or output==state_path or
            any(root==output or root in output.parents for root in (profile,original,image.parent,image.resolve().parent))):
        raise ValueError('EA restart proof must be a new external JSON outside profiles and EA installation.')
    layers=layers or compatibility.UserLayers();canonical=str(image);executable_hash=sha256(image)
    level=manifest(image);before_layer=layers.read(canonical);after_layer=compatibility.without_forced_admin(before_layer);machine_before=machine(canonical)
    before_saves=game_lifecycle.all_save_files(profile)
    receipt={'schema':1,'operation':'ea-client-'+operation,'ok':False,'phase':'planned','token':journal['token'],
        'executable':canonical,'resolved_executable':str(image.resolve()),'executable_sha256':executable_hash,'execution_level':level,
        'hkcu_layer_before':before_layer,'hkcu_layer_after':after_layer if normal_permissions else before_layer,
        'hklm_layer_observed':machine_before,'normal_permissions_requested':normal_permissions,
        'before_saves':before_saves,'ea_start_submitted':False,'ea_started_verified':False,
        'account_files_written_by_tool':False,'executable_changed':False,'windows_uac_changed':False,
        'windows_uac_automated':False,'game_launch_submitted':False,'force_if_tray_authorized':force_if_tray}
    _exclusive(output,receipt);deadline=clock()+seconds
    def persist(): write_json(output,receipt)
    def guard():
        if clock()>=deadline: raise TimeoutError('EA restart lease expired; no action repeated.')
        test_profile.require_closed()
        _, fresh_journal, fresh_profile, fresh_original = reusable_profile.load(state)
        if (fresh_journal['token'] != journal['token'] or fresh_profile != profile or fresh_original != original or
                not test_profile.status(state).get('ready_to_launch') or sha256(image)!=executable_hash or machine(canonical)!=machine_before):
            raise ValueError('Test profile, EA executable or machine compatibility changed.')
    try:
        with reusable_profile.mutation_lock(state):
            guard()
            if operation=='restore':
                recovery=reusable_profile.writable(recovery)
                if recovery==output or any(root==recovery or root in recovery.parents for root in (profile,original,image.parent)) or not 0<recovery.stat().st_size<=MAX_RECEIPT_BYTES or sha256(recovery)!=expected_recovery_sha256:
                    raise ValueError('EA recovery proof is unsafe, changed or oversized.')
                prior=json.loads(recovery.read_text(encoding='utf-8'))
                if (prior.get('schema')!=1 or prior.get('operation')!='ea-client-restart' or prior.get('token')!=journal['token'] or
                        prior.get('executable')!=canonical or prior.get('executable_sha256')!=executable_hash or level not in ('asInvoker','legacy-default') or
                        prior.get('normal_permissions_requested') is not True or prior.get('hkcu_layer_after')!=compatibility.without_forced_admin(prior.get('hkcu_layer_before')) or
                        layers.read(canonical)!=prior['hkcu_layer_after']):
                    raise ValueError('EA compatibility recovery identity or current user flags differ.')
                receipt.update(recovery={'path':str(recovery),'sha256':expected_recovery_sha256},
                    restore_before=prior['hkcu_layer_after'],restore_after=prior['hkcu_layer_before'],phase='restoring');persist();guard()
                if layers.read(canonical)!=prior['hkcu_layer_after']: raise ValueError('EA flags changed before restore.')
                layers.write(canonical,prior['hkcu_layer_before'])
                if layers.read(canonical)!=prior['hkcu_layer_before']: raise OSError('EA restored registry readback failed.')
                receipt.update(ok=True,phase='restored')
            else:
                observed=diagnostic();receipt['diagnostic']=observed
                if operation=='status':
                    receipt.update(ok=True,phase='observed')
                else:
                    host=probe(os.getpid());receipt['host']=host
                    if host.get('elevated') is not False or host.get('ui_access') is not False or host.get('integrity')!=8192:
                        raise ValueError('Normal EA startup requires the original non-elevated medium user process.')
                    targets=observed.get('targets',[])
                    if (not isinstance(targets,list) or len(targets)>1 or observed.get('failures') or
                            targets and observed.get('ok') is not True or not targets and inventory()):
                        raise ValueError('Restart requires one exact EA main lifetime or verified complete absence.')
                    target=_identity(targets[0],image) if targets else None;receipt['prior_ea']=target
                    if target is not None and (target['session_id']!=host.get('session_id') or not live(target)):
                        raise ValueError('EA restart target is not the same live user session.')
                    if normal_permissions:
                        if level not in ('asInvoker','legacy-default') or compatibility.without_forced_admin(machine_before)!=machine_before:
                            raise ValueError('EA manifest or machine flags request elevation; no HKCU override.')
                        receipt['phase']='applying-normal-permissions';persist();guard()
                        if layers.read(canonical)!=before_layer: raise ValueError('EA compatibility flags changed externally.')
                        layers.write(canonical,after_layer)
                        if layers.read(canonical)!=after_layer: raise OSError('EA compatibility registry readback failed.')
                        receipt['normal_permissions_applied']=True;persist()
                    receipt['phase']='closing-old-ea';persist()
                    if target is not None:
                        try:
                            result=close(target,force_if_tray,guard,deadline)
                        except OSError as error:
                            result={'ok':False,'closed':False,'error':str(error)}
                        receipt['normal_close']=result;persist()
                        if result.get('closed') is not True and elevate_close_once:
                            receipt['elevated_close_submitted']=True;persist();guard()
                            receipt['elevated_close']=elevated_close(state,journal,profile,target,executable_hash,force_if_tray,output,deadline,clock=clock,pause=pause)
                        if live(target): raise ValueError('Old EA process remains alive; no second client started.')
                    else:
                        receipt['normal_close']={'ok':True,'closed':True,'already_absent':True,'forced':False};persist()
                    while inventory() and clock()<deadline:
                        guard();pause(min(.1,max(0,deadline-clock())))
                    if inventory(): raise ValueError('EA main/compatibility process remains; no new client started.')
                    guard()
                    if probe(os.getpid())!=host or layers.read(canonical)!=receipt['hkcu_layer_after']:
                        raise ValueError('Original medium host or EA compatibility changed before normal startup.')
                    receipt.update(phase='starting-new-ea',ea_start_submitted=True);persist()
                    start(image)
                    while clock()<deadline:
                        guard();current=diagnostic()
                        if current.get('ok') and len(current.get('targets',[]))==1:
                            fresh=_identity(current['targets'][0],image)
                            if (target is not None and (fresh['pid']==target['pid'] or fresh['creation_time']==target['creation_time']) or
                                    fresh['session_id']!=host['session_id'] or fresh['elevated'] is not False or
                                    fresh['ui_access'] is not False or fresh['integrity']!=8192 or not live(fresh)):
                                raise ValueError('New EA lifetime is not verified medium in the original user session.')
                            receipt.update(new_ea=fresh,ok=True,phase='restarted',ea_started_verified=True);break
                        pause(min(.1,max(0,deadline-clock())))
                    if not receipt['ok']: raise TimeoutError('New medium EA process was not verified; launch was not repeated.')
    except (OSError,ValueError,RuntimeError,TimeoutError,subprocess.TimeoutExpired) as error:
        receipt.update(ok=False,error=str(error))
    receipt['after_saves']=game_lifecycle.all_save_files(profile)
    receipt['all_save_files_unchanged']=receipt['after_saves']==before_saves
    if not receipt['all_save_files_unchanged']:receipt['ok']=False;receipt['error']='Save inventory changed during EA operation.'
    receipt['finalized']=True;persist()
    return {'ok':receipt['ok'],'phase':receipt['phase'],'proof':str(output),'proof_sha256':sha256(output),
        'ea_started_verified':receipt['ea_started_verified'],'all_save_files_unchanged':receipt['all_save_files_unchanged'],
        'message':receipt.get('error','EA operation verified; account and all test saves were retained.')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',required=True,type=Path);parser.add_argument('--source-hash',required=True)
    args=parser.parse_args();result=worker(args.worker,args.source_hash)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['ok'] else 1)
