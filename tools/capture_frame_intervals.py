"""Capture PresentMon QPC intervals for a separately prepared test process.

This never launches or controls Sims, switches profiles, changes focus, edits a
Sim or saves. Baseline and Apex states both require caller-supplied, PID-bound
mod-state evidence. The tool does not independently prove those declarations.
Capture starts only with --run and --parent-ready, and is never retried.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

import compare_frame_runs as comparison
import reusable_profile
import windows_process
import hitch_stage

ROOT = Path(__file__).resolve().parents[1]
PRESENTMON = ROOT / '.work/research/PresentMon-2.6.0-x64.exe'
PRESENTMON_SHA = 'b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af'
CAPTURE_KIND = 'PresentMon 2.6.0 ETW DXGI present intervals (MsBetweenPresents); QPC-aligned; not displayed FPS'


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_mod_state(value, mode, pid, creation):
    if mode == 'stage':
        hitch_stage.validate_mod_state(value, pid, creation)
        return True
    expected=mode=='apex'
    if (mode not in ('baseline','apex') or not isinstance(value,dict) or type(value.get('schema')) is not int or value['schema']!=1 or
            value.get('target_pid')!=pid or value.get('process_creation_filetime')!=creation or
            value.get('inventory_and_loaded_modules_observed') is not True or
            not isinstance(value.get('observation_method'),str) or not value['observation_method'].strip() or
            not comparison._hash(value.get('other_mods_sha256')) or
            any(value.get(name) is not expected for name in
                ('apex_script_loaded','apex_cas_package_loaded','apex_overlay_loaded'))):
        raise ValueError('PID-bound observed mod state must match the chosen run mode.')
    artifact=value.get('apex_candidate_sha256')
    if (expected and not comparison._hash(artifact)) or (not expected and artifact is not None):
        raise ValueError('Apex artifact identity differs from the requested mode.')
    if expected:
        service=value.get('native_service_profile');gfx=value.get('native_gfx_snapshot_profile')
        if (not isinstance(service,dict) or service.get('enabled') is not False or
                type(service.get('inflight')) is not int or service['inflight']!=0 or
                service.get('installed') is not False or not isinstance(gfx,dict) or
                gfx.get('enabled') is not False or type(gfx.get('inflight')) is not int or
                gfx['inflight']!=0 or gfx.get('prepared') is not False or gfx.get('active_heap_hooks') is not False):
            raise ValueError('Apex diagnostic profilers must be observed inactive and uninstalled.')
    return True


def window_snapshot(pid, executable, creation=None):
    if os.name!='nt':
        raise RuntimeError('Window observation requires Windows.')
    process=windows_process.observe(pid,expected_path=str(executable),expected_creation_time=creation)
    if process is None:
        raise ValueError('The selected Sims process is no longer running.')
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.EnumWindows.argtypes=[callback,wintypes.LPARAM];user.EnumWindows.restype=wintypes.BOOL
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user.IsWindowVisible.argtypes=[wintypes.HWND];user.IsIconic.argtypes=[wintypes.HWND]
    user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];user.GetAncestor.restype=wintypes.HWND
    user.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.GetForegroundWindow.restype=wintypes.HWND
    if hasattr(user,'GetDpiForWindow'):
        user.GetDpiForWindow.argtypes=[wintypes.HWND];user.GetDpiForWindow.restype=wintypes.UINT
    rows=[]
    @callback
    def visit(hwnd,_):
        owner=wintypes.DWORD();thread=user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        name=ctypes.create_unicode_buffer(256);client=wintypes.RECT();rect=wintypes.RECT()
        if (owner.value==pid and user.IsWindowVisible(hwnd) and not user.IsIconic(hwnd) and
                user.GetAncestor(hwnd,2)==hwnd and user.GetClassNameW(hwnd,name,len(name)) and
                name.value.startswith('Canvas-') and user.GetClientRect(hwnd,ctypes.byref(client)) and
                client.right>client.left and client.bottom>client.top and user.GetWindowRect(hwnd,ctypes.byref(rect))):
            rows.append(dict(hwnd=int(hwnd),window_class=name.value,ui_thread=int(thread),
                client_size=[client.right-client.left,client.bottom-client.top],
                window_rect=[rect.left,rect.top,rect.right,rect.bottom],
                dpi=int(user.GetDpiForWindow(hwnd)) if hasattr(user,'GetDpiForWindow') else None))
        return True
    if not user.EnumWindows(visit,0) or len(rows)!=1:
        raise ValueError('The PID must have one visible, non-minimized Sims Canvas window.')
    rows[0].update(process_id=pid,image_path=str(executable),process_creation_filetime=process['CreationFileTime'],
        foreground_hwnd=int(user.GetForegroundWindow() or 0))
    return rows[0]


def same_window(before, after):
    keys=('process_id','image_path','process_creation_filetime','hwnd','window_class','ui_thread',
          'client_size','window_rect','dpi','foreground_hwnd')
    return all(before.get(key)==after.get(key) for key in keys)


def event_loss(log):
    # Check each clause: a zero-events report cannot conceal dropped buffers
    # later on the same line. Unknown loss counts remain conservatively invalid.
    for line in log.splitlines():
        # Optional PresentMon 2.6.0 real-time status. These snapshots are not
        # proof of complete or timely sampling; absence is not zero-loss proof.
        if re.match(r'^\s*\[ETW\b', line, re.I):
            sample=re.fullmatch(r'\s*\[ETW Status\]\s+BufferFillPct=([0-9]{1,3}\.[0-9])%\s+'
                r'BuffersInUse=([0-9]{1,10})\s+TotalBuffers=([0-9]{1,10})\s+'
                r'EventsLost=([0-9]{1,10})\s+BuffersLost=([0-9]{1,10}),\s+'
                r'OverflowedPresents=([0-9]{1,10})\s*',line,re.I)
            if sample is None:return True
            fill=float(sample.group(1)); used,total,events,buffers,overflow=map(int,sample.groups()[1:])
            if (fill>100 or used>total or any(x>0xffffffff for x in (used,total,events,buffers,overflow)) or
                    events or buffers or overflow):return True
            continue
        # PresentMon 2.6.0 reports its own ring overflow separately from ETW
        # loss, and only emits this warning when the overflow count is positive.
        if re.search(r'\bwarning:\s*0*[1-9][0-9]*\s+overflowed\s+present\s+events\s+detected\b', line, re.I):
            return True
        if not re.search(r'\b(lost|dropped|missed)\b', line, re.I):
            continue
        remainder = re.sub(r'\b(?:0|no)\s+(?:events?|buffers?)\s+(?:were\s+)?(?:lost|dropped|missed)\b|'
            r'\b(?:lost|dropped|missed)\s+0\s+(?:events?|buffers?)\b', '', line, flags=re.I)
        if re.search(r'\b(events?|buffers?)\b', remainder, re.I):
            return True
    return False


def read_collector_log(path, partial=False):
    # Actual 2.6.0 stdout-mode diagnostics can carry a UTF-16 BOM. Preserve
    # the raw bytes and never let an unrecognized encoding conceal a loss.
    with Path(path).open('rb') as stream:
        raw=stream.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:
        raise ValueError('Collector log exceeds its bounded read size.')
    encoding='utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
    try:
        text=raw.decode(encoding)
        if '\x00' in text:
            raise ValueError('Collector diagnostics contain undecoded NUL bytes.')
        return text
    except (UnicodeError,ValueError):
        if partial:
            return ''  # A concurrent write may end inside a code unit.
        raise ValueError('Collector diagnostic encoding could not be validated.')


def outputs(prefix):
    prefix=Path(prefix).resolve()
    work=(ROOT/'.work').resolve()
    if work not in prefix.parents or prefix.suffix or not prefix.parent.is_dir():
        raise ValueError('Use a fresh extension-free prefix inside this checkout’s .work directory.')
    paths={key:Path(str(prefix)+suffix) for key,suffix in
           (('csv','.csv'),('log','.etw.log'),('metadata','.json'))}
    if any(p.exists() for p in paths.values()):
        raise ValueError('Capture evidence already exists; never overwrite a recording.')
    return paths


def verify_start(args):
    if not args.run or not args.parent_ready:
        raise ValueError('Capture requires explicit --run and --parent-ready.')
    if os.name!='nt' or type(args.pid) is not int or args.pid<=0:
        raise ValueError('Capture requires Windows and one exact Sims PID.')
    if type(args.seconds) is not int or not 5<=args.seconds<=60:
        raise ValueError('Capture duration must be 5–60 seconds.')
    if (Path(args.exe).name.casefold()!='ts4_x64.exe' or not comparison._hash(args.exe_sha256) or
            not Path(args.exe).is_file() or sha(args.exe)!=args.exe_sha256):
        raise ValueError('Game executable differs from the explicit SHA-256.')
    if not PRESENTMON.is_file() or sha(PRESENTMON)!=PRESENTMON_SHA:
        raise ValueError('The pinned PresentMon executable differs.')
    _,_,profile,_=reusable_profile.load(args.state)
    paths=outputs(args.output)
    before=window_snapshot(args.pid,Path(args.exe).resolve())
    mod_state,mod_sha=comparison.load_json(args.mod_state)
    validate_mod_state(mod_state,args.mode,args.pid,before['process_creation_filetime'])
    return profile,paths,before,mod_state,mod_sha


def _write(path,value,initial=False):
    raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode('utf-8')
    if initial:
        with path.open('xb') as stream:stream.write(raw)
    else:
        temp=path.with_name(path.name+'.tmp')
        with temp.open('xb') as stream:stream.write(raw)
        os.replace(temp,path)


def capture(args):
    profile,paths,before,mods,mods_sha=verify_start(args)
    session='ApexFrame'+uuid.uuid4().hex
    # Pinned 2.6.0 default combined output has TimeInQPC, CPUStartQPC and
    # MsBetweenPresents. --v1_metrics uses different legacy column names.
    command=[str(PRESENTMON),'--process_id',str(args.pid),'--qpc_time','--timed',str(args.seconds),
        '--terminate_after_timed','--no_console_stats','--no_track_input','--no_track_gpu','--no_track_display','--session_name',session,
        '--set_circular_buffer_size','16384','--output_file',str(paths['csv'])]
    record=dict(schema=1,state='prepared',mode='actions',benchmark_mode=args.mode,
        capture_kind=CAPTURE_KIND,configured_seconds=args.seconds,profile=str(profile),target_pid=args.pid,
        game_exe_sha256=args.exe_sha256,window_before=before,collector_sha256=PRESENTMON_SHA,
        collector_command=command,mod_state_sha256=mods_sha,mod_state_evidence_declared=True,
        independently_verified_mod_state=False,appearance_write_requested=False,save_requested=False,
        game_commands_submitted=0,ui_input_submitted=0,performance_pass=False,displayed_fps_measured=False)
    if args.mode == 'stage':
        record['stage_sha256'] = mods['stage_sha256']
        record['stage_id'] = mods['stage']['id']
    _write(paths['metadata'],record,True)
    process=None
    try:
        with paths['log'].open('x',encoding='utf-8') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            record.update(state='recording',collector_pid=process.pid,launch_perf_counter_ns=time.perf_counter_ns())
            _write(paths['metadata'],record);ready=False;start=time.monotonic();next_query=start
            while process.poll() is None:
                if not ready:
                    text=read_collector_log(paths['log'],partial=True)
                    observed='Started recording.' in text
                    if not observed and time.monotonic()>=next_query:
                        next_query=time.monotonic()+1
                        query=subprocess.run(['logman','query','-ets'],capture_output=True,text=True,timeout=5,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                        observed=query.returncode==0 and any(re.fullmatch(re.escape(session)+r'\s+Trace\s+Running\s*',
                                                                         line.strip()) for line in query.stdout.splitlines())
                    if observed:
                        current=window_snapshot(args.pid,Path(args.exe).resolve(),before['process_creation_filetime'])
                        if not same_window(before,current):raise ValueError('Sims window changed before capture readiness.')
                        ready=True;record.update(ready_seen=True,ready_perf_counter_ns=time.perf_counter_ns())
                        _write(paths['metadata'],record)
                        print(json.dumps({'state':'READY','metadata':str(paths['metadata']),'pid':args.pid}),flush=True)
                if time.monotonic()-start>args.seconds+20:
                    process.terminate();process.wait(timeout=5)
                    raise TimeoutError('Only this private PresentMon collector was stopped after timeout.')
                time.sleep(.1)
            record['collector_exit_code']=process.returncode
        after=window_snapshot(args.pid,Path(args.exe).resolve(),before['process_creation_filetime'])
        record['window_after']=after;record['window_identity_and_geometry_unchanged']=same_window(before,after)
        record['ready_seen']=ready
        if sha(args.exe)!=args.exe_sha256:
            raise ValueError('Game executable changed during the capture.')
        record['game_exe_hash_unchanged']=True
        log_text=read_collector_log(paths['log'])
        lost=event_loss(log_text)
        record.update(collector_log_sha256=sha(paths['log']),collector_event_loss_warning=lost)
        if not paths['csv'].is_file():raise ValueError('PresentMon produced no CSV.')
        csv_sha=sha(paths['csv']);values,clocks,runtime=comparison.read_frames(paths['csv'],args.pid,csv_sha)
        record['analysis']=dict(valid=not lost,event_loss_warning=lost,csv_sha256=csv_sha,
            swapchains=[dict(present_runtime=runtime,frames=len(values),first_qpc=clocks[0],last_qpc=clocks[-1])])
        record['state']='completed' if process.returncode==0 and ready and same_window(before,after) and not lost else 'invalid'
        _write(paths['metadata'],record)
        if record['state']!='completed':raise ValueError('Capture did not satisfy its evidence checks.')
        print(json.dumps({'state':'completed','metadata':str(paths['metadata']),'csv':str(paths['csv']),
            'performance_pass':False}),flush=True)
        return record
    except Exception as error:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:pass
        record.update(state='invalid',capture_error=str(error)[:1000],performance_pass=False)
        _write(paths['metadata'],record)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True,help='Existing isolated-profile journal')
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--exe-sha256',required=True)
    parser.add_argument('--mode',choices=('baseline','apex','stage'),required=True)
    parser.add_argument('--mod-state',type=Path,required=True)
    parser.add_argument('--seconds',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--parent-ready',action='store_true')
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args();capture(args)


if __name__=='__main__':main()
