"""Bounded command-batch inventory lease; every changed file invalidates it."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import threading
from functools import wraps

import reusable_profile

_LOCAL = threading.local()


def scoped(function):
    """Keep one capture's status/poll calls inside its verified batch lease."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        state = args[0] if args else kwargs['state']
        with session(state):
            return function(*args, **kwargs)
    return wrapped


def change_time(path, data):
    # Windows st_ctime is creation time. ChangeTime can coalesce fast writes;
    # pair it with the file USN. A filesystem without that contract must hash
    # the content, never silently trust a restored LastWriteTime.
    if os.name != 'nt': return data.st_ctime_ns
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
    def identity(path):
        data = path.lstat()
        if path.is_symlink() or getattr(data, 'st_file_attributes', 0) & 0x400:
            raise ValueError('A profile lease cannot follow links or reparse points.')
        # Coarse/coalesced ctime on non-NTFS CI filesystems cannot certify a
        # same-size edit followed by utime. Keep the fast ChangeTime lease on
        # Windows; verify file content on platforms without that contract.
        content = hashlib.sha256(path.read_bytes()).hexdigest() if os.name != 'nt' and path.is_file() else None
        return (data.st_dev, data.st_ino, data.st_size, data.st_mtime_ns, data.st_ctime_ns,
                getattr(data, 'st_file_attributes', 0),change_time(path,data),content)
    rows = [('journal',identity(state),hashlib.sha256(state.read_bytes()).hexdigest()),
            ('profile',str(profile),identity(profile)),('original-path',str(original)),('token',journal['token'])]
    mods = profile / 'Mods'
    for root, dirs, files in os.walk(mods, followlinks=False):
        root = Path(root)
        rows.append((str(root.relative_to(profile)),identity(root)))
        for name in sorted(dirs + files):
            path = root / name
            rows.append((str(path.relative_to(profile)),identity(path)))
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
            raise ValueError('Test artifacts or journal changed during this CLI batch; no request sent.')
        return lease['result']
    result = full_check()
    if before != stamp(state):
        raise ValueError('Test artifacts changed during full hash verification; no request sent.')
    lease['stamp'] = before
    lease['result'] = result
    return result
