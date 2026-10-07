"""Verify fixed native exports with private Python 3.7, outside the game."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from fetch_build_python import DEFAULT_OUTPUT
from build_script import build as build_script

ROOT = Path(__file__).resolve().parents[1]
CODE = '''
import json, sys, _ctypes
sys.path.insert(0, sys.argv[1])
from apex_core.overlay_loader import _bind, _integer
handle = _ctypes.LoadLibrary(sys.argv[2])
try:
    calls = _bind(_ctypes, handle)
    result = {name: _integer(call) for name, call in calls.items()}
    assert result == {'ApexOverlayProtocolVersion': 1, 'ApexOverlayStart': -1, 'ApexOverlayStatus': 0}, result
    print(json.dumps(result, sort_keys=True))
finally:
    _ctypes.FreeLibrary(handle)
'''

LOADER_CODE = '''
import builtins, hashlib, json, os, shutil, sys
from pathlib import Path
original_import = builtins.__import__
def game_import(name, *args, **kwargs):
    if name == 'ctypes' or name.startswith('ctypes.'):
        raise ImportError('Game fixture: pure ctypes is unavailable')
    return original_import(name, *args, **kwargs)
builtins.__import__ = game_import
def run():
    base = Path(sys.argv[4])
    apex, dlls = base / 'Mods' / 'Apex', base / 'Python' / 'DLLs'
    native = apex / 'Native'
    native.mkdir(parents=True); dlls.mkdir(parents=True)
    archive = apex / 'ApexOccultHybrid.ts4script'
    shutil.copyfile(sys.argv[3], str(archive))
    target = native / 'ApexOverlay.dll'
    shutil.copyfile(sys.argv[2], str(target))
    shutil.copyfile(str(Path(sys.executable).parent / '_ctypes.pyd'), str(dlls / '_ctypes_x64.pyd'))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (native / 'overlay-manifest.json').write_text(json.dumps({'schema':1, 'protocol':1, 'file':target.name, 'sha256':digest}))
    sys.path.insert(0, str(archive))
    import td1_occult_hybrid_apex as backend
    assert backend.ctypes is None and not backend._SERVER_RUNNING and backend._DATA_DIR is None
    from apex_core import overlay_loader
    result = overlay_loader.start(backend.__file__, str(dlls))
    assert result.get('native_code') == -1, result
    assert Path(sys.modules['_ctypes'].__file__).name == '_ctypes_x64.pyd'
    assert '.ts4script' in backend.__file__
    # Protocol accepted and production extension-loader path ran, but the
    # actual DLL must refuse rendering hooks in this independent Python host.
    print(json.dumps({'packaged_python37_import':True, 'pure_ctypes_absent':True,
        'explicit_extension_loader':True, 'production_loader_host_rejected':True,
        'game_started':False, 'game_files_modified':False}))
    # Production loader retains its handle, as required for game hooks. The
    # host guard installed none, so releasing here permits temporary cleanup.
    sys.modules['_ctypes'].FreeLibrary(overlay_loader._HANDLE)
    overlay_loader._CALLS = None; overlay_loader._HANDLE = None
run()
'''


def verify(dll=None, python37=None, script=None):
    dll = Path(dll or ROOT / 'NativeOverlay/build/Release/ApexOverlay.dll').resolve(strict=True)
    if ROOT not in dll.parents or dll.is_symlink():
        raise ValueError('Verification can only load the native build inside this checkout.')
    compiler = Path(python37 or DEFAULT_OUTPUT / 'python.exe').resolve(strict=True)
    env = os.environ.copy()
    env['PYTHONHOME'] = str(compiler.parent)
    env.pop('PYTHONPATH', None)
    result = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', CODE, str(ROOT / 'Source'), str(dll)],
        cwd=str(compiler.parent), env=env, text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise ValueError('Private Python 3.7 native ABI check failed: ' + result.stderr.strip())
    # Use the actual built script, not source imports or a fabricated API stub.
    if script is None:
        script = ROOT / 'dist/dev/ApexOccultHybrid.ts4script'
        build_script(ROOT / 'Source', script)
    script = Path(script).resolve(strict=True)
    if ROOT not in script.parents or script.is_symlink():
        raise ValueError('Verify only an exact built script inside this checkout.')
    work = ROOT / '.work'
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='loader-host-', dir=str(work)) as temporary:
        if Path(temporary).resolve().parent != work.resolve():
            raise ValueError('Native host fixture must stay inside private checkout work.')
        # CPython retains loaded extension modules until process exit. Parent
        # cleanup runs only after the child releases the _ctypes file mapping.
        loader = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', LOADER_CODE,
            str(ROOT / 'Source'), str(dll), str(script), temporary], cwd=str(compiler.parent), env=env,
            text=True, capture_output=True, timeout=20)
    if loader.returncode:
        raise ValueError('Packaged production extension-loader check failed: ' + loader.stderr.strip())
    return {'schema': 1, 'file': 'ApexOverlay.dll', 'protocol': 1,
        'sha256': hashlib.sha256(dll.read_bytes()).hexdigest(), 'bytes': dll.stat().st_size,
        'python37_export_checks': json.loads(result.stdout), 'game_files_modified': False,
        'production_loader_checks': json.loads(loader.stdout),
        'verified_script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
        'game_runtime_verified': False,
        'minhook': {'repository': 'https://github.com/TsudaKageyu/minhook', 'tag': 'v1.3.4',
                    'commit': 'c3fcafdc10146beb5919319d0683e44e3c30d537', 'license': 'BSD-2-Clause'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.dll), indent=2))
