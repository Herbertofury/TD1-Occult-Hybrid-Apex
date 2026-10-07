"""Adapt authorized 1.13.7 bytecode into an Apex-owned package namespace.

Deserialize/transform/serialize with the pinned matching compiler. Baseline game
modules are never imported or executed by this tool. Exact instruction bytes,
integer tuning IDs and non-namespace constants remain intact. Decompiler output
is research only and is never silently shipped as recovered source.
"""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
from dbpf_build import digest
from fetch_build_python import DEFAULT_OUTPUT

PATCHES = {
    'save': '''def save(original, self, *args, **kwargs):
    from apex_core.hybrid_persistence import save_with_retention
    return save_with_retention(original, self, occult_utils, *args, **kwargs)
''',
    'load': '''def load(original, self, data):
    from apex_core.hybrid_persistence import load_with_retention
    return load_with_retention(original, self, data, occult_cache, occult_utils, OccultType, SimInfoBaseWrapper)
'''}

TRANSFORM = r'''
import base64, importlib.util, json, marshal, sys, types
if sys.version_info[:2] != (3, 7) or importlib.util.MAGIC_NUMBER != b'\x42\x0d\x0d\x0a':
    raise RuntimeError('Matching private Python 3.7 compiler required.')
def rename(value):
    if isinstance(value, str):
        if value == 'OccultHybrid' or value.startswith('OccultHybrid.') or value.startswith('OccultHybrid/'):
            return 'apex_hybrid' + value[len('OccultHybrid'):]
    return value
def constant(value, filename):
    if isinstance(value, types.CodeType):
        return transform(value, filename)
    if isinstance(value, tuple):
        return tuple(constant(item, filename) for item in value)
    if isinstance(value, frozenset):
        return frozenset(constant(item, filename) for item in value)
    return rename(value)
def transform(code, filename):
    if filename.endswith('/IC_Hybrid/_occult_tracker.py') and code.co_name in patches:
        replacement = compile(patches[code.co_name], filename, 'exec', dont_inherit=True)
        updated = next(item for item in replacement.co_consts if isinstance(item, types.CodeType))
        if code.co_freevars or updated.co_freevars:
            raise RuntimeError('Persistence port cannot replace closure-backed functions.')
        return updated
    updated = types.CodeType(code.co_argcount, code.co_kwonlyargcount, code.co_nlocals,
        code.co_stacksize, code.co_flags, code.co_code,
        tuple(constant(value, filename) for value in code.co_consts),
        tuple(rename(value) for value in code.co_names), code.co_varnames,
        filename, code.co_name, code.co_firstlineno, code.co_lnotab,
        code.co_freevars, code.co_cellvars)
    if updated.co_code != code.co_code:
        raise RuntimeError('Baseline instructions changed unexpectedly.')
    return updated
request = json.load(sys.stdin)
patches = request['patches']
rows = []
for item in request['modules']:
    raw = base64.b64decode(item['payload'], validate=True)
    name = item['name']
    if name.endswith('.pyc'):
        if raw[:4] != importlib.util.MAGIC_NUMBER or len(raw) <= 16:
            raise RuntimeError('Incompatible baseline bytecode.')
        code = marshal.loads(raw[16:])
        if not isinstance(code, types.CodeType):
            raise RuntimeError('Baseline contains a non-code bytecode payload.')
        code = transform(code, name[:-1])
        payload = importlib.util.MAGIC_NUMBER + b'\0' * 12 + marshal.dumps(code)
    else:
        source = raw.decode('utf-8-sig').replace('from OccultHybrid.', 'from apex_hybrid.').replace('import OccultHybrid.', 'import apex_hybrid.')
        if name.endswith('/Modules/TD1_OccultHybrid_StabilizeFix.py'):
            source = source.replace('        global RAN_FIX\n', '')
            source = source.replace('    result = original(self, *args, **kwargs)', '    global RAN_FIX\n    result = original(self, *args, **kwargs)')
            source = source.replace('        return\n', '        return result\n')
            source = source.replace('\ndef get_current_occult_trait', '    return result\n\ndef get_current_occult_trait')
        code = compile(source, name, 'exec', dont_inherit=True, optimize=0)
        payload = importlib.util.MAGIC_NUMBER + b'\0' * 12 + marshal.dumps(code)
        name += 'c'
    marshal.loads(payload[16:])
    rows.append({'name': name, 'payload': base64.b64encode(payload).decode('ascii')})
print(json.dumps(rows))
'''


def port(script, python37=None):
    compiler = Path(python37 or DEFAULT_OUTPUT / 'python.exe').resolve(strict=True)
    rows, records = [], []
    with zipfile.ZipFile(io.BytesIO(script)) as archive:
        names = set()
        for info in sorted(archive.infolist(), key=lambda row: row.filename):
            if info.is_dir():
                continue
            old = info.filename
            if not old.startswith('OccultHybrid/') or not old.endswith(('.py', '.pyc')) or '..' in Path(old).parts or info.file_size > 4 * 1024 * 1024:
                raise ValueError('Unexpected baseline module: ' + old)
            name = 'apex_hybrid/' + old[len('OccultHybrid/'):]
            compiled_name = name + 'c' if name.endswith('.py') else name
            if compiled_name in names:
                raise ValueError('Duplicate migrated module.')
            names.add(compiled_name)
            raw = archive.read(info)
            if name.endswith('/Modules/occult_cas_restore.pyc'):
                name = name[:-1]
                effective = b'"""Legacy automatic CAS restoration retired; use the explicit Apex shield."""\n'
                adaptation = 'Retired stale whole-library auto-restore callback; canonical Apex shield owns restoration.'
            else:
                effective = raw
                adaptation = 'Apex namespace and portable filenames; compiled instruction stream preserved.'
            if name.endswith('/IC_Hybrid/_occult_tracker.pyc'):
                adaptation = 'Apex namespace; load/save port retains unresolved forms and restores transient flags in finally.'
            if name.endswith('/Modules/TD1_OccultHybrid_StabilizeFix.py'):
                adaptation = 'Apex namespace; valid global declaration and original callback return preserved.'
            rows.append({'name': name, 'payload': base64.b64encode(effective).decode('ascii')})
            records.append({'source_module': old, 'apex_module': compiled_name, 'source_sha256': digest(raw),
                            'adaptation': adaptation})
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment['PYTHONHOME'] = str(compiler.parent)
    environment['PYTHONHASHSEED'] = '0'
    if (compiler.parent / 'python37._pth').exists():
        raise ValueError('Unconfigured compiler isolation; use fetch_build_python.py.')
    result = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', TRANSFORM], input=json.dumps({'modules': rows, 'patches': PATCHES}),
                            text=True, capture_output=True, env=environment, cwd=str(compiler.parent), timeout=60)
    if result.returncode:
        raise ValueError('Authorized bytecode adaptation failed: ' + result.stderr[-2000:])
    payloads = [(row['name'], base64.b64decode(row['payload'], validate=True)) for row in json.loads(result.stdout)]
    if {name for name, _ in payloads} != names:
        raise ValueError('Migrated module inventory mismatch.')
    for record, (name, payload) in zip(records, payloads):
        if record['apex_module'] != name:
            raise ValueError('Migrated module order mismatch.')
        record['sha256'] = digest(payload)
    return payloads, records
