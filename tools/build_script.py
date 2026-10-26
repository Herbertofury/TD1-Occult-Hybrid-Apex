"""Build an exact deterministic development script archive; no live install."""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
from source_manifest import write_json
from fetch_build_python import DEFAULT_OUTPUT


COMPILER = r'''
import base64, importlib.util, importlib._bootstrap_external, json, marshal, sys
if sys.version_info[:2] != (3, 7) or importlib.util.MAGIC_NUMBER != b'\x42\x0d\x0d\x0a':
    raise RuntimeError('The Sims 4 build requires Python 3.7 bytecode magic 420d0d0a.')
result = []
for item in json.load(sys.stdin):
    raw = base64.b64decode(item['source'], validate=True)
    code = compile(raw, item['module'], 'exec', dont_inherit=True, optimize=0)
    payload = importlib._bootstrap_external._code_to_hash_pyc(code, importlib.util.source_hash(raw), checked=True)
    # Verify serialized code without executing the mod.
    restored = marshal.loads(payload[16:])
    if restored.co_filename != item['module']:
        raise RuntimeError('Compiler embedded a machine-specific filename.')
    result.append({'module': item['module'][:-3] + '.pyc', 'payload': base64.b64encode(payload).decode('ascii')})
print(json.dumps({'python': sys.version.split()[0], 'magic': importlib.util.MAGIC_NUMBER.hex(), 'modules': result}))
'''


def compile_payloads(payloads, python37):
    compiler = Path(python37).resolve(strict=True)
    if (compiler.parent / 'python37._pth').exists():
        raise ValueError('Compiler _pth isolation ignores deterministic hash seed; run fetch_build_python.py for the configured private compiler.')
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env['PYTHONHOME'] = str(compiler.parent)
    env['PYTHONHASHSEED'] = '0'
    data = [{'module': name, 'source': base64.b64encode(payload).decode('ascii')} for name, payload in payloads]
    process = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', COMPILER],
                             input=json.dumps(data), text=True, capture_output=True,
                             cwd=str(compiler.parent), env=env, timeout=60)
    if process.returncode:
        raise ValueError('Python 3.7 compilation failed: ' + process.stderr.strip())
    result = json.loads(process.stdout)
    compiled = []
    expected = {name[:-3] + '.pyc' for name, _ in payloads}
    for item in result['modules']:
        raw = base64.b64decode(item['payload'], validate=True)
        if item['module'] not in expected or raw[:8] != b'\x42\x0d\x0d\x0a\x03\x00\x00\x00' or len(raw) <= 16:
            raise ValueError('Invalid compiled module/header: ' + item['module'])
        expected.remove(item['module'])
        compiled.append((item['module'], raw))
    if expected:
        raise ValueError('Compiler omitted required modules.')
    return compiled, {'version': result['python'], 'magic': result['magic'],
                      'python_executable_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
                      'invalidation': 'PEP 552 checked source hash', 'hash_seed': 0}


def build(source, output, python37=None, hybrid_baseline=None):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Build outputs must be outside source inputs.')
    if any(part.casefold().startswith('the sims 4') for part in output.parts):
        raise ValueError('Build outputs must be outside every Sims user profile.')
    paths = [source / 'td1_occult_hybrid_apex.py'] + sorted((source / 'apex_core').rglob('*.py'))
    if hybrid_baseline is not None:
        paths += sorted((source / 'apex_hybrid').rglob('*.py'))
    records, payloads = [], []
    for path in paths:
        if path.is_symlink() or source not in path.resolve().parents:
            raise ValueError('Linked/outside source input.')
        payload = path.read_bytes()
        name = path.relative_to(source).as_posix()
        ast.parse(payload.decode('utf-8-sig'), filename=name, feature_version=(3, 7))
        records.append({'module': name, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
        payloads.append((name, payload))
    compiled, compiler_info = compile_payloads(payloads, python37 or DEFAULT_OUTPUT / 'python.exe')
    payloads.extend(compiled)
    baseline_records = []
    if hybrid_baseline is not None:
        from port_baseline_scripts import port
        baseline = Path(hybrid_baseline).read_bytes()
        if hashlib.sha256(baseline).hexdigest() != '012e1a04eeaf15c3a6bd78bd05171724a0514ae369c7a3fd32bc114d7e1a9124':
            raise ValueError('Authorized hybrid archive identity changed.')
        with zipfile.ZipFile(hybrid_baseline) as archive:
            script = archive.read('TwelfthDoctor1_OccultHybridHandler.ts4script')
        adapted, baseline_records = port(script, python37)
        if {name for name, _ in payloads} & {name for name, _ in adapted}:
            raise ValueError('Duplicate script ownership.')
        payloads.extend(adapted)
        compiled.extend(adapted)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(output.parent), delete=False) as stream:
            temporary = stream.name
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, payload in sorted(payloads):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, payload, compresslevel=9)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or sorted(archive.namelist()) != sorted(name for name, _ in payloads):
                raise RuntimeError('Archive verification failed.')
            for name, payload in payloads:
                if archive.read(name) != payload:
                    raise RuntimeError('Embedded module mismatch: ' + name)
        os.replace(temporary, str(output))
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    manifest = {'schema': 1, 'artifact': output.name, 'status': 'development-not-runtime-accepted',
                'python_source_syntax': '3.7', 'compiler': compiler_info, 'modules': records,
                'compiled_modules': [{'module': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in compiled],
                'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'authorized_hybrid_modules': baseline_records,
                'build': 'python tools/build_script.py --output dist/dev/ApexOccultHybrid.ts4script',
                'limitations': ['Script build only; standalone package/core/CAS/color parity and all runtime gates remain open.']}
    write_json(output.with_name(output.name + '.manifest.json'), manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / 'Source')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--python37', type=Path, default=DEFAULT_OUTPUT / 'python.exe')
    parser.add_argument('--hybrid-baseline', type=Path, help='Pinned authorized 1.13.7 ZIP to adapt into apex_hybrid.')
    args = parser.parse_args()
    result = build(args.source, args.output, args.python37, args.hybrid_baseline)
    print(json.dumps({'artifact': result['artifact'], 'sha256': result['sha256'], 'compiled_modules': len(result['compiled_modules']), 'authorized_hybrid_modules': len(result['authorized_hybrid_modules'])}, indent=2))
