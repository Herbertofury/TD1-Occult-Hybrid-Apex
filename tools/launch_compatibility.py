"""Undo forced administrator compatibility for the selected game, with recovery.

Only HKCU's RUNASADMIN token on three exact Sims executables is changed.
Executable manifests, machine policy, EA authentication and UAC stay intact.
"""
import ctypes
import json
import re
from pathlib import Path
from xml.etree import ElementTree
import reusable_profile
import test_profile
from source_manifest import sha256, write_json

LAYERS = r'Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
EXECUTABLES = ('TS4_Launcher_x64.exe', 'TS4_x64.exe', 'TS4_DX9_x64.exe')


def execution_level(path):
    """Read RT_MANIFEST as data; never execute or load game imports."""
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LoadLibraryExW.argtypes = [w.LPCWSTR, w.HANDLE, w.DWORD]
    kernel.LoadLibraryExW.restype = w.HMODULE
    kernel.FindResourceW.argtypes = [w.HMODULE, ctypes.c_void_p, ctypes.c_void_p]
    kernel.FindResourceW.restype = w.HANDLE
    kernel.SizeofResource.argtypes = [w.HMODULE, w.HANDLE]
    kernel.SizeofResource.restype = w.DWORD
    kernel.LoadResource.argtypes = [w.HMODULE, w.HANDLE]
    kernel.LoadResource.restype = w.HANDLE
    kernel.LockResource.argtypes = [w.HANDLE]
    kernel.LockResource.restype = ctypes.c_void_p
    kernel.FreeLibrary.argtypes = [w.HMODULE]
    kernel.FreeLibrary.restype = w.BOOL
    module = kernel.LoadLibraryExW(str(path), None, 0x22)
    if not module:
        raise OSError('Cannot read executable resources: ' + str(path))
    try:
        resource = kernel.FindResourceW(module, ctypes.c_void_p(1), ctypes.c_void_p(24))
        size = kernel.SizeofResource(module, resource) if resource else 0
        if not 0 < size <= 1024 * 1024:
            raise ValueError('Missing or oversized executable manifest.')
        pointer = kernel.LockResource(kernel.LoadResource(module, resource))
        if not pointer:
            raise OSError('Cannot read executable manifest.')
        raw = ctypes.string_at(pointer, size)
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('Unsupported executable manifest.')
        root = ElementTree.fromstring(raw)
        levels = [node.get('level') for node in root.iter() if node.tag.rsplit('}', 1)[-1] == 'requestedExecutionLevel']
        if len(levels) != 1:
            raise ValueError('Ambiguous requested execution level.')
        return levels[0]
    finally:
        kernel.FreeLibrary(module)


class UserLayers:
    def read(self, executable):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LAYERS) as key:
                value, kind = winreg.QueryValueEx(key, executable)
        except FileNotFoundError:
            return None
        if kind != winreg.REG_SZ or not isinstance(value, str) or len(value) > 4096:
            raise ValueError('Unsupported compatibility registry value.')
        return value

    def write(self, executable, value):
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, LAYERS, 0, winreg.KEY_SET_VALUE) as key:
            if value is None:
                try:
                    winreg.DeleteValue(key, executable)
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(key, executable, 0, winreg.REG_SZ, value)


def without_forced_admin(value):
    if value is None or not re.search(r'(?<!\S)RUNASADMIN(?!\S)', value, re.IGNORECASE):
        return value
    remaining = [token for token in value.split() if token.upper() != 'RUNASADMIN']
    return ' '.join(remaining) if any(token != '~' for token in remaining) else None


def plan(game_root, layers=None, manifest=execution_level):
    layers = layers or UserLayers()
    root = test_profile.unlinked(game_root)
    rows = []
    for name in EXECUTABLES:
        executable = test_profile.unlinked(root / 'Game' / 'Bin' / name)
        if not executable.is_file() or executable.parent != root / 'Game' / 'Bin':
            raise ValueError('Missing exact Sims executable.')
        before = layers.read(str(executable))
        after = without_forced_admin(before)
        level = manifest(executable)
        if before != after and level != 'asInvoker':
            raise ValueError('The executable requests elevation; its privilege requirement will not be overridden.')
        rows.append({'executable': str(executable), 'sha256': sha256(executable),
                     'execution_level': level, 'before': before, 'after': after})
    return {'schema': 1, 'game_root': str(root), 'phase': 'planned', 'entries': rows}


def configure(state, game_root, receipt, restore=False, layers=None, manifest=execution_level):
    layers = layers or UserLayers()
    _, _, profile, original = reusable_profile.load(state)
    root = test_profile.unlinked(game_root)
    receipt = reusable_profile.writable(receipt)
    if any(receipt == path or path in receipt.parents for path in (profile, original, root)):
        raise ValueError('Compatibility recovery must remain outside both profiles and the game installation.')
    test_profile.require_closed()
    with reusable_profile.mutation_lock(receipt):
        if receipt.exists():
            if receipt.stat().st_size > 32768:
                raise ValueError('Oversized compatibility recovery journal.')
            data = json.loads(receipt.read_text(encoding='utf-8'))
            if data.get('schema') != 1 or data.get('game_root') != str(root) or len(data.get('entries', [])) != len(EXECUTABLES):
                raise ValueError('Recovery journal belongs to a different installation.')
            # Reconstruct the exact allowlist and validate all data before writes.
            for row, name in zip(data['entries'], EXECUTABLES):
                path = test_profile.unlinked(root / 'Game' / 'Bin' / name)
                if row['executable'] != str(path) or row['sha256'] != sha256(path) or manifest(path) != 'asInvoker':
                    raise ValueError('Executable identity changed since compatibility preparation.')
                if row['after'] != without_forced_admin(row['before']):
                    raise ValueError('Invalid compatibility recovery transition.')
        else:
            if restore:
                raise ValueError('No compatibility recovery journal to restore.')
            data = plan(root, layers, manifest)
            write_json(receipt, data)
        if data.get('phase') == 'restored' and not restore:
            raise ValueError('This recovery journal was restored; preserve it and use a new receipt.')
        # A newer user edit must never be silently overwritten, even on recovery.
        for row in data['entries']:
            if layers.read(row['executable']) not in (row['before'], row['after']):
                raise ValueError('Compatibility flags changed externally; refusing to overwrite the new settings.')
        data['phase'] = 'restoring' if restore else 'applying'
        write_json(receipt, data)
        for row in data['entries']:
            destination = row['before'] if restore else row['after']
            observed = layers.read(row['executable'])
            if observed != destination:
                # Recheck directly before each registry mutation.
                if observed not in (row['before'], row['after']):
                    raise ValueError('Compatibility flags changed while applying.')
                layers.write(row['executable'], destination)
            if layers.read(row['executable']) != destination:
                raise OSError('Compatibility registry readback failed.')
        data['phase'] = 'restored' if restore else 'applied'
        write_json(receipt, data)
    return {'ok': True, 'phase': data['phase'], 'receipt': str(receipt),
            'changed_executables': sum(row['before'] != row['after'] for row in data['entries']),
            'launch_verified': False, 'windows_uac_changed': False}
