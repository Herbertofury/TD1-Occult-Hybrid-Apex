"""Bounded artifact lease; known runtime logs are not executable authority."""
from contextlib import contextmanager
import hashlib
import os
import stat
from pathlib import Path
import threading
from functools import wraps, lru_cache

import reusable_profile

_LOCAL = threading.local()
_RUNTIME_LOGS = frozenset(('mccc/mc_cmd_center.log', 'mccc/mc_lastexception.html'))


def scoped(function):
    """Keep one capture's status/poll calls inside its verified batch lease."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        state = args[0] if args else kwargs['state']
        with session(state):
            return function(*args, **kwargs)
    return wrapped


@lru_cache(maxsize=1)
def _windows_api():
    """Bind the read-only metadata API once, not for every installed package."""
    import ctypes
    from ctypes import wintypes as W
    class Basic(ctypes.Structure):
        _fields_=[('created',ctypes.c_longlong),('accessed',ctypes.c_longlong),
                  ('written',ctypes.c_longlong),('changed',ctypes.c_longlong),('attributes',W.DWORD)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE]
    kernel.CreateFileW.restype=W.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes=[W.HANDLE,ctypes.c_int,W.LPVOID,W.DWORD]
    kernel.GetFileInformationByHandleEx.restype=W.BOOL
    kernel.DeviceIoControl.argtypes=[W.HANDLE,W.DWORD,W.LPVOID,W.DWORD,W.LPVOID,W.DWORD,
                                    ctypes.POINTER(W.DWORD),W.LPVOID]
    kernel.DeviceIoControl.restype=W.BOOL
    kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
    return ctypes, W, Basic, kernel


def change_time(path, data):
    # Windows st_ctime is creation time. ChangeTime can coalesce fast writes;
    # pair it with the file USN. A filesystem without that contract must hash
    # the content, never silently trust a restored LastWriteTime.
    if os.name != 'nt': return data.st_ctime_ns
    ctypes, W, Basic, kernel = _windows_api()
    handle=kernel.CreateFileW(str(path),0x80,7,None,3,0x02200000,None)
    if handle==W.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        basic=Basic()
        if not kernel.GetFileInformationByHandleEx(handle,0,ctypes.byref(basic),ctypes.sizeof(basic)):
            raise ctypes.WinError(ctypes.get_last_error())
        if getattr(data,'st_file_attributes',0)&0x10:
            return (basic.changed, 'directory')
        versions=(W.WORD*2)(2,2)
        record=ctypes.create_string_buffer(4096)
        returned=W.DWORD()
        if kernel.DeviceIoControl(handle,0x000900EB,ctypes.byref(versions),ctypes.sizeof(versions),
                                  record,ctypes.sizeof(record),ctypes.byref(returned),None):
            raw=record.raw[:returned.value]
            if (len(raw)>=60 and int.from_bytes(raw[:4],'little')==len(raw) and
                    int.from_bytes(raw[4:6],'little')==2):
                usn=int.from_bytes(raw[24:32],'little',signed=True)
                if usn>0:
                    return (basic.changed, 'usn-v2', usn)
        return (basic.changed,'content-sha256',hashlib.sha256(path.read_bytes()).hexdigest())
    finally:kernel.CloseHandle(handle)


def stamp(state):
    state, journal, profile, original = reusable_profile.load(state)
    def identity(path, data=None):
        if data is None: data = path.lstat()
        if stat.S_ISLNK(data.st_mode) or getattr(data, 'st_file_attributes', 0) & 0x400:
            raise ValueError('A profile lease cannot follow links or reparse points.')
        # Coarse/coalesced ctime on non-NTFS CI filesystems cannot certify a
        # same-size edit followed by utime. Keep the fast ChangeTime lease on
        # Windows; verify file content on platforms without that contract.
        content = hashlib.sha256(path.read_bytes()).hexdigest() if os.name != 'nt' and stat.S_ISREG(data.st_mode) else None
        return (data.st_dev, data.st_ino, data.st_size, data.st_mtime_ns, data.st_ctime_ns,
                getattr(data, 'st_file_attributes', 0),change_time(path,data),content)
    # Normal Live/CAS operations create cache/log/save entries in this folder.
    # Its physical identity and reparse status matter; directory timestamps and
    # size are not mod or journal authority. Still enumerate and stamp every
    # Mods entry below, including unknown names and each file's USN/content.
    profile_data = profile.lstat()
    if stat.S_ISLNK(profile_data.st_mode) or getattr(profile_data, 'st_file_attributes', 0) & 0x400:
        raise ValueError('A profile lease cannot follow links or reparse points.')
    profile_identity = (profile_data.st_dev, profile_data.st_ino,
                        getattr(profile_data, 'st_file_attributes', 0))
    rows = [('journal',identity(state),hashlib.sha256(state.read_bytes()).hexdigest()),
            ('profile',str(profile),profile_identity),('original-path',str(original)),('token',journal['token'])]
    pinned = {str(row.get('relative', '')).replace('\\', '/').casefold()
              for row in journal.get('artifacts', [])}
    mods = profile / 'Mods'
    def entry(path, data):
        if stat.S_ISLNK(data.st_mode) or getattr(data, 'st_file_attributes', 0) & 0x400:
            raise ValueError('A profile lease cannot follow links or reparse points.')
        relative = str(path.relative_to(mods)).replace('\\', '/').casefold()
        if relative in _RUNTIME_LOGS and relative not in pinned:
            if not stat.S_ISREG(data.st_mode):
                raise ValueError('Known MCCC runtime log is not an ordinary file.')
            return  # Content/rotation of these two diagnostic files is expected.
        # Directory writes are not executable content. All children are still
        # enumerated; additions/removals and replaced directories remain gated.
        value = ((data.st_dev, data.st_ino, getattr(data, 'st_file_attributes', 0))
                 if stat.S_ISDIR(data.st_mode) else identity(path, data))
        rows.append((str(path.relative_to(profile)), value))
    def directory(path):
        with os.scandir(path) as stream:
            for child in stream:
                child_path = Path(child.path)
                # Windows DirEntry.stat() supplies zero st_dev/st_ino. Read
                # lstat once there so replacement-file identity remains exact.
                data = child_path.lstat() if os.name == 'nt' else child.stat(follow_symlinks=False)
                entry(child_path, data)
                if stat.S_ISDIR(data.st_mode): directory(child_path)
    entry(mods, mods.lstat())
    directory(mods)
    return tuple(sorted(rows,key=lambda row:row[0]))


@contextmanager
def session(state):
    """Nested status/submission/result calls share only one current batch."""
    key = str(Path(state).resolve())
    prior = getattr(_LOCAL,'lease',None)
    if prior is not None:
        if prior['key'] != key: raise ValueError('A CLI batch cannot change profiles.')
        yield
        return
    _LOCAL.lease = {'key':key,'stamp':None}
    try: yield
    finally: _LOCAL.lease = None


def validate(state, full_check):
    lease = getattr(_LOCAL,'lease',None)
    if lease is None:
        return full_check()
    if lease['key'] != str(Path(state).resolve()):
        raise ValueError('CLI inventory lease belongs to another profile.')
    before = stamp(state)
    if lease['stamp'] is not None:
        if before != lease['stamp']:
            old, new = dict((row[0], row[1:]) for row in lease['stamp']), dict((row[0], row[1:]) for row in before)
            changed = sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))
            raise ValueError('Test artifacts or journal changed during this CLI batch; no request sent. Changed entries: ' +
                             ', '.join(changed[:8]))
        return lease['result']
    result = full_check()
    if before != stamp(state):
        raise ValueError('Test artifacts changed during full hash verification; no request sent.')
    lease['stamp'] = before
    lease['result'] = result
    return result
