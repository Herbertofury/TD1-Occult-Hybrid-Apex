"""Read-only, bounded before/after evidence for a separately managed test run.

This does not launch the game, install mods, read saves, or prove which profile
the game opened or what package content it loaded. Use before/after the timed
interval: full hashing and module enumeration can themselves be expensive.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import ntpath
import os
from pathlib import Path, PurePosixPath
import stat
import time

MAX_FILES=200000
MAX_BYTES=1024**4
MAX_EVIDENCE=128*1024**2
CHUNK=1024*1024
MAX_MODULES=4096
REPARSE=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)

def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()

def _lstat(path):
    value=Path(path).lstat()
    if stat.S_ISLNK(value.st_mode) or getattr(value,'st_file_attributes',0)&REPARSE:
        raise ValueError('Symbolic links and reparse entries are refused: '+str(path))
    return value

def _unlinked(path):
    path=Path(os.path.abspath(str(path)))
    for entry in reversed((path,)+tuple(path.parents)):
        _lstat(entry)
    return path

def _inside(path,root):
    try:return ntpath.commonpath([str(path).casefold(),str(root).casefold()])==str(root).casefold()
    except ValueError:return False

class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_=[('dwFileAttributes',wintypes.DWORD),('ftCreationTime',wintypes.FILETIME),
        ('ftLastAccessTime',wintypes.FILETIME),('ftLastWriteTime',wintypes.FILETIME),
        ('dwVolumeSerialNumber',wintypes.DWORD),('nFileSizeHigh',wintypes.DWORD),
        ('nFileSizeLow',wintypes.DWORD),('nNumberOfLinks',wintypes.DWORD),
        ('nFileIndexHigh',wintypes.DWORD),('nFileIndexLow',wintypes.DWORD)]

def _handle_info(kernel,handle):
    info=BY_HANDLE_FILE_INFORMATION()
    if not kernel.GetFileInformationByHandle(handle,ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(),'Cannot identify file handle')
    if info.dwFileAttributes & (REPARSE|0x10):
        raise ValueError('Opened file is a reparse entry or directory')
    return (info.dwVolumeSerialNumber,info.nFileIndexHigh,info.nFileIndexLow,
        info.nFileSizeHigh,info.nFileSizeLow,info.ftLastWriteTime.dwHighDateTime,
        info.ftLastWriteTime.dwLowDateTime,info.ftCreationTime.dwHighDateTime,info.ftCreationTime.dwLowDateTime,
        info.nNumberOfLinks)

def _final_name(kernel,handle):
    size=kernel.GetFinalPathNameByHandleW(handle,None,0,0)
    if not 0<size<32768:raise OSError(ctypes.get_last_error(),'Cannot identify final file path')
    name=ctypes.create_unicode_buffer(size+1)
    used=kernel.GetFinalPathNameByHandleW(handle,name,len(name),0)
    if not 0<used<len(name):raise OSError(ctypes.get_last_error(),'Final file path unavailable')
    value=name.value
    if value.startswith('\\\\?\\UNC\\'):return '\\\\'+value[8:]
    if value.startswith('\\\\?\\'):return value[4:]
    return value

def hash_file(path,root=None,capture_bytes=False,capture_limit=1024*1024):
    """Hash through a non-following file handle, after final-path containment.

    Windows final handle identity, not merely a pre-open path check, is pinned.
    On other systems use O_NOFOLLOW and fstat; production game capture is Windows.
    """
    path=_unlinked(path)
    if root is not None:
        root=_unlinked(root)
        if not _inside(path,root):raise ValueError('Path is outside the expected root')
    if os.name=='nt':
        import msvcrt
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.GetFileInformationByHandle.argtypes=[wintypes.HANDLE,ctypes.POINTER(BY_HANDLE_FILE_INFORMATION)]
        kernel.GetFileInformationByHandle.restype=wintypes.BOOL
        kernel.GetFinalPathNameByHandleW.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
        kernel.GetFinalPathNameByHandleW.restype=wintypes.DWORD
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        handle=kernel.CreateFileW(str(path),0x80000000,7,None,3,0x00200000|0x08000000,None)
        if handle==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'Cannot open file without following its final reparse point')
        try:
            before=_handle_info(kernel,handle);final=_final_name(kernel,handle)
            if root is not None and before[-1]!=1:raise ValueError('Hardlinked profile file is refused')
            known_size=(before[3]<<32)|before[4]
            if known_size>MAX_BYTES:raise ValueError('File exceeds the bounded inventory size')
            if capture_bytes and known_size>capture_limit:raise ValueError('Evidence exceeds its size bound')
            if ntpath.normcase(ntpath.normpath(final))!=ntpath.normcase(ntpath.normpath(str(path))):
                raise ValueError('Opened file resolves to a different path')
            if root is not None and not _inside(final,root):raise ValueError('Opened file escaped its root')
            fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY);handle=None
            try:
                with os.fdopen(fd,'rb') as stream:
                    fd=None;digest=hashlib.sha256();size=0;captured=[]
                    for chunk in iter(lambda:stream.read(CHUNK),b''):
                        size+=len(chunk)
                        if size>MAX_BYTES:raise ValueError('File exceeds the bounded inventory size')
                        if capture_bytes:
                            if size>capture_limit:raise ValueError('Evidence exceeds its size bound')
                            captured.append(chunk)
                        digest.update(chunk)
                    after=_handle_info(kernel,msvcrt.get_osfhandle(stream.fileno()))
            finally:
                if fd is not None:os.close(fd)
            if before!=after or size!=((before[3]<<32)|before[4]):raise ValueError('File changed while hashing')
        finally:
            if handle is not None:kernel.CloseHandle(handle)
    else:
        flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)
        fd=os.open(str(path),flags)
        try:
            before=os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or (root is not None and before.st_nlink!=1):
                raise ValueError('Only regular unlinked profile files are allowed')
            if before.st_size>MAX_BYTES:raise ValueError('File exceeds the bounded inventory size')
            if capture_bytes and before.st_size>capture_limit:raise ValueError('Evidence exceeds its size bound')
            with os.fdopen(fd,'rb') as stream:
                fd=None;digest=hashlib.sha256();size=0;captured=[]
                for chunk in iter(lambda:stream.read(CHUNK),b''):
                    size+=len(chunk)
                    if size>MAX_BYTES:raise ValueError('File exceeds the bounded inventory size')
                    if capture_bytes:
                        if size>capture_limit:raise ValueError('Evidence exceeds its size bound')
                        captured.append(chunk)
                    digest.update(chunk)
                after=os.fstat(stream.fileno())
                if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                    raise ValueError('File changed while hashing')
        finally:
            if fd is not None:os.close(fd)
    _unlinked(path)
    result={'bytes':size,'sha256':digest.hexdigest()}
    if capture_bytes:result['content']=b''.join(captured)
    return result

def _entries(root):
    root=_unlinked(root)
    if not root.is_dir():raise ValueError('Mods directory is missing')
    result=[];seen=set();stack=[root]
    while stack:
        current=stack.pop();_unlinked(current)
        with os.scandir(str(current)) as entries:
            for entry in entries:
                path=Path(entry.path);info=_lstat(path)
                relative=path.relative_to(root).as_posix()
                folded=relative.casefold()
                if folded in seen:raise ValueError('Case-insensitive inventory path collision')
                seen.add(folded)
                if len(seen)>MAX_FILES:raise ValueError('Mod inventory exceeds its entry bound')
                if stat.S_ISDIR(info.st_mode):stack.append(path)
                elif stat.S_ISREG(info.st_mode):result.append(relative)
                else:raise ValueError('Non-regular inventory entry refused')
        _unlinked(current)
    return sorted(result,key=lambda s:(s.casefold(),s))

def inventory_mods(root):
    started=time.perf_counter();root=_unlinked(root);names=_entries(root);total=0;rows=[]
    for relative in names:
        item=hash_file(root/relative,root);total+=item['bytes']
        if total>MAX_BYTES:raise ValueError('Mod inventory exceeds its byte bound')
        rows.append(dict(path=relative,**item))
    if _entries(root)!=names:raise ValueError('Mod files changed during inventory')
    for row in rows:
        if hash_file(root/row['path'],root)!={'bytes':row['bytes'],'sha256':row['sha256']}:
            raise ValueError('Mod file changed between full hash passes')
    if _entries(root)!=names:raise ValueError('Mod files changed during inventory')
    return {'files':rows,'files_count':len(rows),'bytes':total,'full_hash_passes':2,'seconds':time.perf_counter()-started}

def read_json_file(path,root=None,limit=1024*1024):
    # Read the small file through the same guarded Windows handle; hash twice to
    # detect changes across the short parse window. Refuse malformed evidence.
    if type(limit) is not int or not 0<limit<=MAX_EVIDENCE:raise ValueError('Invalid evidence size bound')
    before=hash_file(path,root,capture_bytes=True,capture_limit=limit)
    raw=before.pop('content')
    if sha_bytes(raw)!=before['sha256'] or hash_file(path,root)!=before:
        raise ValueError('Evidence changed during parsing')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('Duplicate JSON field: '+k)
            out[k]=v
        return out
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique),before['sha256']

def validate_profile(journal,expected_profile,expected_token):
    state_path=_unlinked(journal);profile=_unlinked(expected_profile)
    if _inside(state_path,profile):raise ValueError('Journal must be outside the test profile')
    state,state_sha=read_json_file(state_path)
    if (not isinstance(state,dict) or type(state.get('schema')) is not int or state.get('schema')!=2 or state.get('mode')!='reusable-test-only' or
        state.get('phase')!='active' or state.get('token')!=expected_token or
        not isinstance(expected_token,str) or len(expected_token)!=32 or
        any(c not in '0123456789abcdef' for c in expected_token) or
        ntpath.normcase(ntpath.normpath(str(state.get('profile',''))))!=ntpath.normcase(ntpath.normpath(str(profile))) or
        profile.name!='The Sims 4'):
        raise ValueError('Exact active marked disposable profile and token required')
    marker,marker_sha=read_json_file(profile/'.apex-disposable-profile.json',profile)
    if not isinstance(marker,dict) or marker.get('token')!=expected_token or marker.get('disposable') is not True:
        raise ValueError('Disposable profile marker does not match')
    return {'profile':str(profile),'token':expected_token,'journal_sha256':state_sha,'marker_sha256':marker_sha}

class MODULEENTRY32W(ctypes.Structure):
    _fields_=[('dwSize',wintypes.DWORD),('th32ModuleID',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),
        ('GlblcntUsage',wintypes.DWORD),('ProccntUsage',wintypes.DWORD),('modBaseAddr',ctypes.POINTER(ctypes.c_ubyte)),
        ('modBaseSize',wintypes.DWORD),('hModule',wintypes.HMODULE),('szModule',wintypes.WCHAR*256),('szExePath',wintypes.WCHAR*260)]

def windows_modules(pid):
    if os.name!='nt':raise RuntimeError('Module enumeration requires Windows')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Module32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MODULEENTRY32W)];kernel.Module32FirstW.restype=wintypes.BOOL
    kernel.Module32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MODULEENTRY32W)];kernel.Module32NextW.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    handle=kernel.CreateToolhelp32Snapshot(0x8|0x10,pid)
    if handle==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'Module snapshot unavailable')
    try:
        item=MODULEENTRY32W();item.dwSize=ctypes.sizeof(item);rows=[]
        if not kernel.Module32FirstW(handle,ctypes.byref(item)):
            raise OSError(ctypes.get_last_error(),'Module enumeration unavailable')
        while True:
            path=item.szExePath
            if not path or len(path)>=259 or item.th32ProcessID!=pid or not item.modBaseSize:
                raise ValueError('Invalid or potentially truncated module identity')
            rows.append({'path':path,'base':ctypes.cast(item.modBaseAddr,ctypes.c_void_p).value,'size':int(item.modBaseSize)})
            if len(rows)>MAX_MODULES:raise ValueError('Module inventory exceeds its bound')
            if not kernel.Module32NextW(handle,ctypes.byref(item)):
                if ctypes.get_last_error()!=18:raise OSError(ctypes.get_last_error(),'Module enumeration incomplete')
                break
        rows.sort(key=lambda x:(x['path'].casefold(),x['base']))
        if len({(x['path'].casefold(),x['base']) for x in rows})!=len(rows):raise ValueError('Duplicate loaded module')
        return rows
    finally:kernel.CloseHandle(handle)

def qpc_clock():
    if os.name!='nt':raise RuntimeError('QPC observation requires Windows')
    value=ctypes.c_longlong();frequency=ctypes.c_longlong()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    if not kernel.QueryPerformanceCounter(ctypes.byref(value)) or not kernel.QueryPerformanceFrequency(ctypes.byref(frequency)) or frequency.value<=0:
        raise OSError(ctypes.get_last_error(),'QPC unavailable')
    return int(value.value),int(frequency.value)

def observe(journal,profile,token,pid,exe,exe_sha,creation,window_observer,module_observer,clock=qpc_clock):
    start=time.perf_counter();start_qpc,frequency=clock();identity=validate_profile(journal,profile,token)
    if (Path(exe).name.casefold()!='ts4_x64.exe' or not Path(exe).is_absolute() or
            not isinstance(exe_sha,str) or len(exe_sha)!=64 or any(c not in '0123456789abcdef' for c in exe_sha)):
        raise ValueError('Exact executable SHA-256 required')
    if type(pid) is not int or pid<=0 or type(creation) is not int or creation<=0:
        raise ValueError('Exact PID and creation time required')
    if hash_file(exe)['sha256']!=exe_sha:raise ValueError('Executable fingerprint differs')
    window=window_observer(pid,Path(exe),creation)
    if window.get('process_id')!=pid or window.get('process_creation_filetime')!=creation:
        raise ValueError('Process/window identity differs')
    before=module_observer(pid)
    if (not before or not any(ntpath.normcase(ntpath.normpath(x.get('path','')))==
            ntpath.normcase(ntpath.normpath(str(exe))) for x in before)):
        raise ValueError('Loaded module enumeration must include the exact executable')
    mods=inventory_mods(Path(profile)/'Mods')
    modules=[]
    for item in before:
        if set(item)!={'path','base','size'} or type(item['base']) is not int or item['base']<=0 or type(item['size']) is not int or item['size']<=0:
            raise ValueError('Malformed module identity')
        modules.append(dict(item,**{'file':hash_file(item['path'])}))
    if before!=module_observer(pid) or window!=window_observer(pid,Path(exe),creation):
        raise ValueError('Process, window or modules changed during observation')
    for item in modules:
        if hash_file(item['path'])!=item['file']:raise ValueError('Loaded module file changed during observation')
    if before!=module_observer(pid) or window!=window_observer(pid,Path(exe),creation):
        raise ValueError('Process, window or modules changed during final observation')
    if identity!=validate_profile(journal,profile,token) or hash_file(exe)['sha256']!=exe_sha:
        raise ValueError('Journal, marker or executable changed during observation')
    end_qpc,end_frequency=clock()
    if type(start_qpc) is not int or type(end_qpc) is not int or type(frequency) is not int or not 0<start_qpc<end_qpc or frequency<=0 or end_frequency!=frequency:
        raise ValueError('Stable, increasing QPC observation bounds required')
    return dict(schema=1,state='observed',identity=identity,process_id=pid,process_creation_filetime=creation,
        exe_path=str(Path(exe)),exe_sha256=exe_sha,window=window,mods=mods,modules=modules,
        start_qpc=start_qpc,end_qpc=end_qpc,qpc_frequency=frequency,
        scan_seconds=time.perf_counter()-start,game_profile_opened_proven=False,package_load_proven=False,
        loaded_memory_bytes_proven=False,transient_changes_between_observations_ruled_out=False,
        observation_scope='filesystem and loaded module snapshots only; no saves or game input')

def _hash(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def validate_observation(row):
    if (not isinstance(row,dict) or type(row.get('schema')) is not int or row.get('schema')!=1 or row.get('state')!='observed' or
            any(type(row.get(k)) is not int for k in ('start_qpc','end_qpc','qpc_frequency','process_id','process_creation_filetime')) or
            not 0<row['start_qpc']<row['end_qpc'] or row['qpc_frequency']<=0 or row['process_id']<=0 or row['process_creation_filetime']<=0):
        raise ValueError('Observation identity or QPC bounds incomplete')
    identity=row.get('identity');window=row.get('window');modules=row.get('modules');mods=row.get('mods')
    if (not isinstance(identity,dict) or set(identity)!={'profile','token','journal_sha256','marker_sha256'} or
            not isinstance(identity['profile'],str) or not ntpath.isabs(identity['profile']) or
            ntpath.basename(identity['profile'])!='The Sims 4' or not isinstance(identity['token'],str) or
            len(identity['token'])!=32 or any(c not in '0123456789abcdef' for c in identity['token']) or
            not _hash(identity['journal_sha256']) or not _hash(identity['marker_sha256']) or
            not isinstance(row.get('exe_path'),str) or not ntpath.isabs(row['exe_path']) or
            ntpath.basename(row['exe_path']).casefold()!='ts4_x64.exe' or not _hash(row.get('exe_sha256'))):
        raise ValueError('Observation profile or executable identity incomplete')
    if (not isinstance(window,dict) or window.get('process_id')!=row['process_id'] or
            window.get('process_creation_filetime')!=row['process_creation_filetime'] or
            not isinstance(window.get('image_path'),str) or
            ntpath.normcase(window['image_path'])!=ntpath.normcase(row['exe_path']) or
            type(window.get('hwnd')) is not int or window['hwnd']<=0 or
            type(window.get('ui_thread')) is not int or window['ui_thread']<=0 or
            not isinstance(window.get('window_class'),str) or not window['window_class'].startswith('Canvas-') or
            not isinstance(window.get('client_size'),list) or len(window['client_size'])!=2 or
            any(type(v) is not int or v<=0 for v in window['client_size']) or
            not isinstance(window.get('window_rect'),list) or len(window['window_rect'])!=4 or
            any(type(v) is not int for v in window['window_rect']) or
            type(window.get('dpi')) is not int or window['dpi']<=0 or
            type(window.get('foreground_hwnd')) is not int or window['foreground_hwnd']<0):
        raise ValueError('Observation window identity incomplete')
    if not isinstance(modules,list) or not 0<len(modules)<=MAX_MODULES:raise ValueError('Loaded module inventory incomplete')
    module_keys=set();has_exe=False
    for item in modules:
        if (not isinstance(item,dict) or set(item)!={'path','base','size','file'} or
                not isinstance(item['path'],str) or not ntpath.isabs(item['path']) or
                type(item['base']) is not int or item['base']<=0 or type(item['size']) is not int or item['size']<=0 or
                not isinstance(item['file'],dict) or set(item['file'])!={'bytes','sha256'} or
                type(item['file']['bytes']) is not int or item['file']['bytes']<0 or not _hash(item['file']['sha256'])):
            raise ValueError('Loaded module identity or file hash incomplete')
        key=(ntpath.normcase(item['path']),item['base'])
        if key in module_keys:raise ValueError('Duplicate loaded module identity')
        module_keys.add(key)
        if ntpath.normcase(item['path'])==ntpath.normcase(row['exe_path']):
            has_exe=item['file']['sha256']==row['exe_sha256']
    if not has_exe:raise ValueError('Executable is absent from loaded module evidence')
    if (not isinstance(mods,dict) or not isinstance(mods.get('files'),list) or
            type(mods.get('files_count')) is not int or mods['files_count']!=len(mods['files']) or
            not 0<=mods['files_count']<=MAX_FILES or type(mods.get('bytes')) is not int or
            not 0<=mods['bytes']<=MAX_BYTES or type(mods.get('full_hash_passes')) is not int or mods.get('full_hash_passes')!=2):
        raise ValueError('Mod inventory is incomplete')
    paths=[];total=0
    for item in mods['files']:
        if (not isinstance(item,dict) or set(item)!={'path','bytes','sha256'} or
                not isinstance(item['path'],str) or not item['path'] or '\\' in item['path'] or
                len(item['path'])>=32768 or PurePosixPath(item['path']).is_absolute() or
                any(v in ('','.','..') for v in item['path'].split('/')) or ':' in item['path'] or
                type(item['bytes']) is not int or item['bytes']<0 or not _hash(item['sha256'])):
            raise ValueError('Mod file path, size or SHA-256 incomplete')
        paths.append(item['path']);total+=item['bytes']
    if (len({p.casefold() for p in paths})!=len(paths) or paths!=sorted(paths,key=lambda s:(s.casefold(),s)) or
            total!=mods['bytes']):raise ValueError('Mod inventory ordering, uniqueness or total differs')
    return row

def compare(before,after,capture):
    validate_observation(before);validate_observation(after)
    fields=('identity','process_id','process_creation_filetime','exe_path','exe_sha256','window','modules')
    if any(before.get(k)!=after.get(k) for k in fields):raise ValueError('Profile, process, window or modules changed')
    a=before['mods'];b=after['mods']
    if any(a.get(k)!=b.get(k) for k in ('files','files_count','bytes','full_hash_passes')):
        raise ValueError('Mod contents changed or inventory is incomplete')
    etw=capture.get('offline_etw') if isinstance(capture,dict) else None
    if (not isinstance(etw,dict) or capture.get('capture_backend')!='xperf_etl' or capture.get('state')!='completed' or
            'synthetic_identity_stubs' in capture or 'synthetic_probe_only' in capture or capture.get('game_measured') is False or
            type(capture.get('target_pid')) is not int or capture.get('target_pid')!=before['process_id'] or capture.get('game_exe_sha256')!=before['exe_sha256'] or
            capture.get('profile')!=before['identity'].get('profile') or
            capture.get('window_before')!=before['window'] or capture.get('window_after')!=after['window'] or
            any(type(etw.get(k)) is not int for k in ('ready_qpc','end_qpc','qpc_frequency')) or
            etw['qpc_frequency']!=before['qpc_frequency'] or after['qpc_frequency']!=before['qpc_frequency'] or
            not before['end_qpc']<=etw['ready_qpc']<etw['end_qpc']<=after['start_qpc']):
        raise ValueError('Offline capture identity or before/after QPC ordering differs')
    return dict(schema=1,state='matching_observed_snapshots',files_count=a['files_count'],bytes=a['bytes'],
        game_profile_opened_proven=False,package_load_proven=False,loaded_memory_bytes_proven=False,
        transient_changes_between_observations_ruled_out=False,capture_metadata_bound=True,
        etl_validity_independently_proven=False,performance_pass=False)

def main():
    import sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True);parser.add_argument('--token',required=True)
    parser.add_argument('--pid',type=int,required=True);parser.add_argument('--creation',type=int,required=True)
    parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--exe-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--compare-to',type=Path)
    parser.add_argument('--capture-metadata',type=Path)
    parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if not args.run:raise ValueError('Explicit --run required')
    if (args.compare_to is None)!=(args.capture_metadata is None):
        raise ValueError('A prior observation and offline capture metadata are required together')
    tools=Path(__file__).resolve().parent;sys.path.insert(0,str(tools))
    import capture_frame_intervals as frame
    work=_unlinked(tools.parent/'.work').resolve(strict=True);_unlinked(args.output.parent);output=args.output.resolve()
    if work not in output.parents or not output.parent.is_dir() or output.exists():raise ValueError('Fresh output inside the checkout private .work required')
    result=observe(args.state,args.profile,args.token,args.pid,args.exe,args.exe_sha256,args.creation,
        frame.window_snapshot,windows_modules)
    if args.compare_to is not None:
        prior=_unlinked(args.compare_to)
        if not _inside(prior,work):raise ValueError('Prior evidence must remain inside this checkout private .work')
        other,other_sha=read_json_file(prior,work,MAX_EVIDENCE)
        capture_path=_unlinked(args.capture_metadata)
        if not _inside(capture_path,work):raise ValueError('Capture metadata must remain inside this checkout private .work')
        capture,capture_sha=read_json_file(capture_path,work,4*1024*1024)
        result['comparison']=compare(other,result,capture)
        result['comparison'].update(prior_sha256=other_sha,capture_metadata_sha256=capture_sha)
    raw=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode('utf-8')
    if len(raw)>MAX_EVIDENCE:raise ValueError('Observation exceeds its bounded evidence size')
    with output.open('xb') as stream:stream.write(raw)
    print(json.dumps({'state':result['state'],'output':str(output),'mods_files':result['mods']['files_count'],
        'comparison':result.get('comparison',{}).get('state'),'package_load_proven':False}))

if __name__=='__main__':main()
