"""Bounded, uniquely owned file-backed ETW capture for a verified Sims process.

The game, profile, action input and recorder are managed elsewhere. This tool
does not launch or control Sims and does not stop any session except the exact
one that it successfully starts. Offline game qualification remains required.
"""
import argparse
import ctypes
import csv
from decimal import Decimal, localcontext
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

import capture_frame_intervals as base
import compare_frame_runs as comparison
import reusable_profile

XPERF=Path(r'C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\xperf.exe')
PROVIDERS=('802ec45a-1e99-4b83-9920-87c98277ba9d:0x90FFFF:5+'
    'ca11c036-0102-4a2d-a6ad-f03cfed5d3c9:0xf:6+'
    '783ACA0A-790E-4d7f-8451-AA850511C6B9:0xf:6+'
    '9e9bba3c-2e38-40cb-99f4-9e8281425164:0xffff:6+'
    '8c416c79-d49b-4f01-a467-e56d3aa8234c:0x8400000440c01000:4')
MAX_MB=1024
# The immediately preceding adapter had no parse-log hash.  Preserve its
# previously accepted evidence as explicitly unverified, never as new proof.
LEGACY_ADAPTER_SHA256='825345eb895da3280c653b28d8792e22c1d370740e00c03c1720d2e146d350fb'
OPTIONS=['-BufferSize','1024','-MinBuffers','30','-MaxBuffers','120',
         '-MaxFile',str(MAX_MB),'-FileMode','Sequential','-ClockType','PerfCounter']
PROVIDER_NAMES={
    'microsoft-windows-dxgkrnl':'802ec45a-1e99-4b83-9920-87c98277ba9d',
    'microsoft-windows-dxgi':'ca11c036-0102-4a2d-a6ad-f03cfed5d3c9',
    'microsoft-windows-d3d9':'783aca0a-790e-4d7f-8451-aa850511c6b9',
    'microsoft-windows-dwm-core':'9e9bba3c-2e38-40cb-99f4-9e8281425164',
    'microsoft-windows-win32k':'8c416c79-d49b-4f01-a467-e56d3aa8234c'}

def provider_set(text):
    """Parse xperf's actual GUID-or-system-name, keyword and level triples."""
    result={}
    for item in text.split('+'):
        parts=item.strip().rsplit(':',2)
        if len(parts)!=3:raise ValueError('ETW provider triple unavailable')
        name=parts[0].strip().strip('"').strip('{}').casefold()
        name=PROVIDER_NAMES.get(name,name)
        if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name) or name in result:
            raise ValueError('ETW provider identity missing, unknown or duplicated')
        try:result[name]=(int(parts[1],0),int(parts[2],0))
        except ValueError:raise ValueError('ETW provider keyword or level invalid')
    return result

def validate_header(text,expected_etl=None):
    for label in ('Total # Lost Buffers','Total # Lost Events'):
        found=re.findall(r'^\s*'+re.escape(label)+r'\s*:\s*(\d+)\s*$',text,re.M)
        if found!=['0']:raise ValueError('ETL header must explicitly report zero '+label)
    if not re.search(r'^\s*Clock type\s*:\s*PerfCounter\s*$',text,re.M):
        raise ValueError('ETL must use the performance counter clock')
    if not re.search(r'^\s*Number of Traces\s*:\s*1\s*$',text,re.M):
        raise ValueError('Exactly one ETL trace is required')
    if not re.search(r'^\s*Log file mode\s*:\s*Sequential\b',text,re.M):
        raise ValueError('ETL must report sequential file mode; circular overwrite is refused')
    if expected_etl is not None:
        names=re.findall(r'^\s*Trace name:\s*(.+?)\s*$',text,re.M)
        if len(names)!=1 or Path(names[0]).resolve()!=Path(expected_etl).resolve():
            raise ValueError('ETL header names a different trace')
    return True

def qpc_clock():
    counter=ctypes.c_longlong();frequency=ctypes.c_longlong()
    if not ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(counter)) or not ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(frequency)) or frequency.value<=0:
        raise RuntimeError('Windows performance counter unavailable')
    return counter.value,frequency.value

def own_session_running(session):
    result=subprocess.run(['logman','query',session,'-ets'],capture_output=True,text=True,timeout=5,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return (result.returncode==0 and re.search(r'^\s*Name:\s*'+re.escape(session)+r'\s*$',result.stdout,re.M|re.I) is not None and
            re.search(r'^\s*Status:\s*Running\s*$',result.stdout,re.M|re.I) is not None)

def validate_logger(text,session,etl):
    def value(field):
        hits=re.findall(r'^\s*'+re.escape(field)+r'\s*:\s*(.+?)\s*$',text,re.M|re.I)
        if len(hits)!=1:raise ValueError('Owned logger field missing or ambiguous: '+field)
        return hits[0]
    if value('Logger Name')!=session or Path(value('Log Filename')).resolve()!=Path(etl).resolve():
        raise ValueError('ETW logger identity or output path differs')
    if value('Buffer Size')!='1024' or value('Maximum File Size')!=str(MAX_MB):
        raise ValueError('ETW did not honor the requested buffer or file limit')
    mode=value('Log File Mode').split()
    if 'Sequential' not in mode or 'Circular' in mode:raise ValueError('ETW logger is not sequential')
    if provider_set(value('Trace Flags'))!=provider_set(PROVIDERS):
        raise ValueError('ETW actual provider GUIDs, keywords or levels differ')
    try:minimum=int(value('Minimum Buffers'));maximum=int(value('Maximum Buffers'))
    except ValueError:raise ValueError('ETW actual buffer counts are invalid')
    if not 0<minimum<=maximum:raise ValueError('ETW actual buffer counts are invalid')
    return [minimum,maximum]

def snapshot_logger(session,etl,destination):
    result=subprocess.run([str(XPERF),'-loggers'],capture_output=True,text=True,timeout=20,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('Cannot inspect owned ETW logger')
    blocks=re.split(r'(?=^\s*Logger Name\s*:)',result.stdout,flags=re.M)
    matches=[b for b in blocks if re.search(r'^\s*Logger Name\s*:\s*'+re.escape(session)+r'\s*$',b,re.M|re.I)]
    if len(matches)!=1:raise ValueError('Owned ETW logger was not uniquely observed')
    actual=validate_logger(matches[0],session,etl)
    with Path(destination).open('x',encoding='utf-8') as stream:stream.write(matches[0])
    return actual

def validate_coverage(capture,clocks):
    evidence=capture['offline_etw'];start=evidence.get('ready_qpc');end=evidence.get('end_qpc');freq=evidence.get('qpc_frequency')
    duration=capture.get('configured_seconds')
    if (type(duration) not in (int,float) or not math.isfinite(duration) or duration<=0 or
            any(type(n) is not int for n in (start,end,freq)) or freq<=0 or start<=0 or end<=start or
            not duration*freq<=end-start<=(duration+10)*freq or
            not clocks or clocks[0]>start+freq or clocks[-1]<end-freq):
        raise ValueError('Target presents do not cover the capture boundaries within one second')
    polls=evidence.get('session_polls_qpc')
    if (not isinstance(polls,list) or len(polls)<2 or any(type(n) is not int for n in polls) or
            polls[0]>start or polls[-1]<end or any(a>=b or b-a>3*freq for a,b in zip(polls,polls[1:]))):
        raise ValueError('Owned session continuity was not checked throughout the capture')
    return True

def paths_for(paths):
    prefix=str(paths['metadata'])[:-5]
    extra={key:Path(prefix+suffix) for key,suffix in [('etl','.etl'),('header','.header.txt'),
        ('startlog','.start.log'),('stoplog','.stop.log'),('parselog','.parse.log'),('logger','.logger.txt'),
        ('raw_csv','.presentmon.raw.csv'),('logger_end','.logger-end.txt')]}
    if any(p.exists() for p in extra.values()):raise ValueError('Preserve all existing trace evidence')
    return dict(paths,**extra)

def validate_qpc_interval(text,ticks,frequency):
    """Check pinned PresentMon's 14-place interval against exact QPC ticks.

    v2.6.0 computes float(ticks) * (1000.0 / float(frequency)) in binary64,
    then prints 14 fractional decimal digits. Four binary64 epsilons cover the
    input conversions, division and multiplication; half a 10^-14-ms output
    quantum covers fixed-decimal rounding. This is not a clock-tick tolerance.
    """
    if (type(ticks) is not int or not 0<ticks<=2**64-1 or type(frequency) is not int or
            not 0<frequency<=2**63-1 or not isinstance(text,str) or
            len(text)>64 or not re.fullmatch(r'[0-9]+\.[0-9]{14}',text)):
        raise ValueError('Invalid pinned PresentMon interval or QPC frequency')
    with localcontext() as ctx:
        ctx.prec=80
        exact=Decimal(ticks)*Decimal(1000)/Decimal(frequency)
        allowance=Decimal('5e-15')+exact*Decimal(4)/Decimal(2**52)
        if abs(Decimal(text)-exact)>allowance:
            raise ValueError('Present interval differs from adjacent QPC timestamps')
    return True

def bounded_csv(raw,pid,ready_qpc,end_qpc,frequency):
    """Derive only intervals wholly within the observed QPC recording window."""
    if type(ready_qpc) is not int or type(end_qpc) is not int or not 0<ready_qpc<end_qpc:
        raise ValueError('Valid QPC recording boundaries required')
    if type(frequency) is not int or not 0<frequency<=2**63-1:
        raise ValueError('Positive QPC frequency required')
    raw=Path(raw);raw_sha=base.sha(raw)
    comparison.read_frames(raw,pid,raw_sha)  # Validate the entire unfiltered PID and swapchain.
    with raw.open('r',encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);fieldnames=reader.fieldnames;rows=[];previous=None
        for row in reader:
            try:current=int(row['TimeInQPC'])
            except (ValueError,TypeError,KeyError):raise ValueError('Raw present clock unavailable')
            if not 0<current<=2**64-1:raise ValueError('Raw present clock outside uint64 range')
            if previous is not None:
                validate_qpc_interval(row.get('MsBetweenPresents'),current-previous,frequency)
            if previous is not None and previous>=ready_qpc and current<=end_qpc:
                rows.append(row)
            previous=current
    if len(rows)<120:raise ValueError('Recording window contains fewer than 120 complete present intervals')
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=fieldnames,lineterminator='\r\n')
    writer.writeheader();writer.writerows(rows)
    return output.getvalue().encode('utf-8')

def parse_log_observation(path):
    """Hash and decode the same bounded bytes; do not reopen between checks."""
    with Path(path).open('rb') as stream:
        raw=stream.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:
        raise ValueError('PresentMon parse log exceeds bounded read size')
    encoding='utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
    try:
        text=raw.decode(encoding)
        if '\x00' in text:raise ValueError('PresentMon parse log contains NUL')
    except (UnicodeError,ValueError):
        raise ValueError('PresentMon parse log encoding could not be validated')
    return hashlib.sha256(raw).hexdigest(),text

def validate_offline_capture(capture,command,pid,duration,csv_path):
    """Recheck the retained ETL/header and exact command provenance for comparison."""
    # Marked fixtures cannot be promoted by accidentally changing only state.
    # Absence of these markers is not independent evidence of a real game run.
    if (capture.get('state')=='synthetic_probe_only' or 'synthetic_identity_stubs' in capture or
            'synthetic_probe_only' in capture or capture.get('game_measured') is False):
        raise ValueError('Synthetic or stubbed capture cannot be used for game comparison')
    if capture.get('collector_sha256')!=base.PRESENTMON_SHA:
        raise ValueError('Offline PresentMon collector fingerprint differs from the pinned version')
    evidence=capture.get('offline_etw')
    if not isinstance(evidence,dict) or evidence.get('stop_succeeded') is not True or evidence.get('header_zero_loss') is not True:
        raise ValueError('Offline ETW cleanup and zero-loss evidence required')
    session=evidence.get('session')
    if not isinstance(session,str) or not re.fullmatch(r'ApexOffline[0-9a-f]{32}',session):raise ValueError('Invalid owned trace name')
    elapsed=capture.get('capture_elapsed_ns')
    if type(elapsed) is not int or not duration*1e9<=elapsed<=(duration+10)*1e9:
        raise ValueError('Offline capture duration is inconsistent')
    adapter=evidence.get('adapter_sha256')
    if (not comparison._hash(evidence.get('xperf_sha256')) or
            not comparison._hash(adapter) or adapter not in (base.sha(__file__),LEGACY_ADAPTER_SHA256)):
        raise ValueError('Xperf or adapter fingerprint differs')
    etl=Path(evidence.get('etl_path','')).resolve();header=Path(evidence.get('header_path','')).resolve()
    logger=Path(evidence.get('logger_path','')).resolve();logger_end=Path(evidence.get('logger_end_path','')).resolve()
    raw=Path(evidence.get('raw_csv_path','')).resolve()
    work=(base.ROOT/'.work').resolve()
    if any(work not in p.parents for p in (etl,header,logger,logger_end,raw)):raise ValueError('ETL, header, logger and raw CSV must stay in private work area')
    if evidence.get('max_file_mb')!=MAX_MB or not all(p.is_file() for p in (etl,header,logger,logger_end,raw)):raise ValueError('Bounded ETL, header, logger or raw CSV absent')
    log_fields=('parse_log_path','parse_log_sha256')
    if adapter==LEGACY_ADAPTER_SHA256:
        if any(k in evidence for k in log_fields):raise ValueError('Legacy adapter cannot attest a parse log')
        log_status='legacy_unverified'
    else:
        if not all(k in evidence for k in log_fields) or not comparison._hash(evidence.get('parse_log_sha256')):
            raise ValueError('Parse-log identity and hash are required')
        log_value=evidence.get('parse_log_path')
        if not isinstance(log_value,str) or not log_value:raise ValueError('Parse-log path is required')
        parse_log=Path(log_value).resolve()
        if work not in parse_log.parents or parse_log!=Path(str(etl)[:-4]+'.parse.log'):
            raise ValueError('Parse log must belong to the retained ETL')
        actual_hash,parse_text=parse_log_observation(parse_log)
        if actual_hash!=evidence['parse_log_sha256'] or base.event_loss(parse_text):
            raise ValueError('PresentMon parse log differs or reports loss')
        log_status='sha256_loss_checked'
    size=etl.stat().st_size
    if not 0<size<(MAX_MB-1)*1024**2 or evidence.get('etl_bytes')!=size:raise ValueError('ETL size differs or is near limit')
    if (base.sha(etl)!=evidence.get('etl_sha256') or base.sha(header)!=evidence.get('header_sha256') or
            base.sha(logger)!=evidence.get('logger_sha256') or base.sha(logger_end)!=evidence.get('logger_end_sha256') or
            base.sha(raw)!=evidence.get('raw_csv_sha256')):
        raise ValueError('Retained ETL/header/logger/raw CSV digest differs')
    validate_header(base.read_collector_log(header),etl)
    actual_buffers=validate_logger(base.read_collector_log(logger),session,etl)
    final_buffers=validate_logger(base.read_collector_log(logger_end),session,etl)
    if actual_buffers!=evidence.get('actual_buffers') or final_buffers!=actual_buffers:
        raise ValueError('Actual ETW buffer counts differ')
    expected_start=[str(XPERF),'-start',session,'-on',PROVIDERS]+OPTIONS+['-f',str(etl)]
    if evidence.get('start_command')!=expected_start or evidence.get('stop_command')!=[str(XPERF),'-stop',session]:
        raise ValueError('Offline trace command or ownership differs')
    expected_parse=[str(base.PRESENTMON),'--etl_file',str(etl),'--process_id',str(pid),
        '--qpc_time','--no_track_input','--no_track_gpu','--no_track_display','--no_console_stats',
        '--output_file',str(raw)]
    if command!=expected_parse:raise ValueError('Offline parsing command or target differs')
    if (not csv_path.is_file() or csv_path.stat().st_size>comparison.MAX_CSV or
            bounded_csv(raw,pid,evidence.get('ready_qpc'),evidence.get('end_qpc'),evidence.get('qpc_frequency'))!=csv_path.read_bytes()):
        raise ValueError('Comparison CSV does not match the exact QPC-window subset')
    return ['backend=xperf_etl','parse_log='+log_status,'xperf_sha256='+evidence['xperf_sha256'],
        'adapter_sha256='+evidence['adapter_sha256'],'actual_buffers='+str(actual_buffers),PROVIDERS]+OPTIONS+expected_parse[5:10]

def run_to_log(command,path,timeout):
    # Raw bytes are retained. A timeout may leave a start outcome uncertain;
    # the caller does not issue a blind stop for an unconfirmed start.
    with path.open('xb') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Owned trace command failed: '+str(result.returncode))

def capture(args):
    profile,paths,before,mods,mods_sha=base.verify_start(args)
    state_sha=base.sha(args.state)
    paths=paths_for(paths)
    if not comparison._hash(args.xperf_sha256) or not XPERF.is_file() or base.sha(XPERF)!=args.xperf_sha256:
        raise ValueError('Xperf executable differs from its explicit SHA-256')
    if shutil.disk_usage(paths['etl'].parent).free < 2*1024**3:
        raise ValueError('At least 2 GiB free space is required for the bounded trace')
    session='ApexOffline'+uuid.uuid4().hex
    start=[str(XPERF),'-start',session,'-on',PROVIDERS]+OPTIONS+['-f',str(paths['etl'])]
    stop=[str(XPERF),'-stop',session]
    parse=[str(base.PRESENTMON),'--etl_file',str(paths['etl']),'--process_id',str(args.pid),
        '--qpc_time','--no_track_input','--no_track_gpu','--no_track_display','--no_console_stats',
        '--output_file',str(paths['raw_csv'])]
    # Persist uncertainty before launching xperf. If this process is killed at
    # any point while the trace may exist, the journal remains conservative.
    record=dict(schema=1,state='starting',start_outcome='uncertain',manual_inspection_required=True,
        mode='actions',benchmark_mode=args.mode,
        capture_backend='xperf_etl',capture_kind=base.CAPTURE_KIND,configured_seconds=args.seconds,
        profile=str(profile),target_pid=args.pid,game_exe_sha256=args.exe_sha256,window_before=before,
        collector_sha256=base.PRESENTMON_SHA,collector_command=parse,mod_state_sha256=mods_sha,
        mod_state_evidence_declared=True,independently_verified_mod_state=False,appearance_write_requested=False,
        save_requested=False,game_commands_submitted=0,ui_input_submitted=0,performance_pass=False,
        displayed_fps_measured=False,offline_etw=dict(session=session,start_command=start,stop_command=stop,
            xperf_sha256=args.xperf_sha256,adapter_sha256=base.sha(__file__),etl_path=str(paths['etl']),header_path=str(paths['header']),
            logger_path=str(paths['logger']),logger_end_path=str(paths['logger_end']),max_file_mb=MAX_MB))
    if args.mode=='stage':record.update(stage_sha256=mods['stage_sha256'],stage_id=mods['stage']['id'])
    base._write(paths['metadata'],record,True)
    started=False;stop_attempted=False
    try:
        try:
            run_to_log(start,paths['startlog'],30)
            started=True
        except BaseException as error:
            if not started and isinstance(error,Exception):
                raise RuntimeError('Trace start failed or timed out; inspect exact owned session and path before any stop') from error
            raise
        record['start_outcome']='confirmed_started'
        actual_buffers=snapshot_logger(session,paths['etl'],paths['logger'])
        record['offline_etw'].update(actual_buffers=actual_buffers,logger_sha256=base.sha(paths['logger']))
        current=base.window_snapshot(args.pid,Path(args.exe).resolve(),before['process_creation_filetime'])
        if not base.same_window(before,current):raise ValueError('Window changed before capture readiness')
        if not own_session_running(session):raise ValueError('Owned trace session is not running')
        first_poll,freq=qpc_clock();ready_qpc,ready_freq=qpc_clock()
        if ready_freq!=freq:raise ValueError('Performance counter frequency changed')
        polls=[first_poll];ready=time.perf_counter_ns()
        record.update(state='recording',ready_seen=True,ready_perf_counter_ns=ready)
        base._write(paths['metadata'],record)
        print(json.dumps({'state':'READY','metadata':str(paths['metadata']),'pid':args.pid}),flush=True)
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            time.sleep(min(1,max(0,deadline-time.monotonic())))
            if not own_session_running(session):raise ValueError('Owned trace stopped during recording')
            poll,poll_freq=qpc_clock()
            if poll_freq!=freq:raise ValueError('Performance counter frequency changed')
            polls.append(poll)
        after=base.window_snapshot(args.pid,Path(args.exe).resolve(),before['process_creation_filetime'])
        finished=time.perf_counter_ns();end_qpc,end_freq=qpc_clock()
        if end_freq!=freq or not own_session_running(session):raise ValueError('Owned trace missing at capture end')
        final_poll,poll_freq=qpc_clock()
        if poll_freq!=freq:raise ValueError('Performance counter frequency changed')
        polls.append(final_poll)
        record['offline_etw'].update(ready_qpc=ready_qpc,end_qpc=end_qpc,qpc_frequency=freq,session_polls_qpc=polls)
        record.update(window_after=after,window_identity_and_geometry_unchanged=base.same_window(before,after),
                      capture_elapsed_ns=finished-ready,game_exe_hash_unchanged=base.sha(args.exe)==args.exe_sha256)
        if not record['window_identity_and_geometry_unchanged'] or not record['game_exe_hash_unchanged']:
            raise ValueError('Game identity or window changed during trace')
        _,_,profile_after,_=reusable_profile.load(args.state)
        _,mods_sha_after=comparison.load_json(args.mod_state)
        if (profile_after!=profile or base.sha(args.state)!=state_sha or mods_sha_after!=mods_sha or
                base.sha(XPERF)!=args.xperf_sha256 or base.sha(base.PRESENTMON)!=base.PRESENTMON_SHA):
            raise ValueError('Profile, mod evidence or collector executable changed')
        if snapshot_logger(session,paths['etl'],paths['logger_end'])!=actual_buffers:
            raise ValueError('Actual ETW buffer configuration changed')
        record['offline_etw']['logger_end_sha256']=base.sha(paths['logger_end'])
        stop_attempted=True;run_to_log(stop,paths['stoplog'],30);started=False
        record['stop_outcome']='confirmed_stopped';record['manual_inspection_required']=False
        if not paths['etl'].is_file() or not 0<paths['etl'].stat().st_size<(MAX_MB-1)*1024**2:
            raise ValueError('ETL missing, empty or near its fixed size limit')
        run_to_log([str(XPERF),'-i',str(paths['etl']),'-a','tracestats','-timespan'],paths['header'],30)
        header=base.read_collector_log(paths['header']);validate_header(header,paths['etl'])
        run_to_log(parse,paths['parselog'],120)
        parse_hash,log=parse_log_observation(paths['parselog'])
        if base.event_loss(log):raise ValueError('PresentMon reported loss while parsing')
        record['offline_etw'].update(parse_log_path=str(paths['parselog']),parse_log_sha256=parse_hash)
        filtered=bounded_csv(paths['raw_csv'],args.pid,ready_qpc,end_qpc,freq)
        with paths['csv'].open('xb') as stream:stream.write(filtered)
        csv_sha=base.sha(paths['csv']);values,clocks,runtime=comparison.read_frames(paths['csv'],args.pid,csv_sha)
        validate_coverage(record,clocks)
        record['offline_etw'].update(etl_sha256=base.sha(paths['etl']),header_sha256=base.sha(paths['header']),
            etl_bytes=paths['etl'].stat().st_size,stop_succeeded=True,header_zero_loss=True,
            raw_csv_path=str(paths['raw_csv']),raw_csv_sha256=base.sha(paths['raw_csv']))
        record['analysis']=dict(valid=True,event_loss_warning=False,csv_sha256=csv_sha,
            swapchains=[dict(present_runtime=runtime,frames=len(values),first_qpc=clocks[0],last_qpc=clocks[-1])])
        validate_offline_capture(record,parse,args.pid,args.seconds,paths['csv'].resolve())
        record['state']='completed';base._write(paths['metadata'],record)
        print(json.dumps({'state':'completed','metadata':str(paths['metadata']),'performance_pass':False}),flush=True)
        return record
    except BaseException as error:
        if started and not stop_attempted:
            try:
                run_to_log(stop,paths['stoplog'],30);started=False
                record.update(start_outcome='confirmed_started',stop_outcome='confirmed_stopped',
                              cleanup_stop_succeeded=True,manual_inspection_required=False)
            except BaseException as cleanup:
                record['cleanup_error']=str(cleanup);record['cleanup_error_type']=type(cleanup).__name__;record['manual_inspection_required']=True
        elif started:
            record['cleanup_error']='Owned stop failed or timed out; outcome uncertain; no blind retry'
            record['manual_inspection_required']=True
        record.update(state='invalid',capture_error=str(error)[:1000],capture_error_type=type(error).__name__,performance_pass=False)
        base._write(paths['metadata'],record)
        raise

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True);parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--exe-sha256',required=True)
    parser.add_argument('--xperf-sha256',required=True);parser.add_argument('--mode',choices=('baseline','apex','stage'),required=True)
    parser.add_argument('--mod-state',type=Path,required=True);parser.add_argument('--seconds',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--parent-ready',action='store_true')
    parser.add_argument('--run',action='store_true');capture(parser.parse_args())

if __name__=='__main__':main()
