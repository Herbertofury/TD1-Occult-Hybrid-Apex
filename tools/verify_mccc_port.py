"""Compare authorized pure Dresser helpers against the source port, offline.

Only the four dependency-free functions are executed against plain list objects;
the original MCCC module, game imports, dialogs and hooks are never executed.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
from fetch_build_python import DEFAULT_OUTPUT
from source_manifest import write_json

ROOT = Path(__file__).resolve().parents[1]
VERIFY = r'''
import base64, hashlib, importlib.util, json, marshal, types, sys
item = json.load(sys.stdin)
raw = base64.b64decode(item['bytecode'], validate=True)
if sys.version_info[:2] != (3, 7) or raw[:4] != importlib.util.MAGIC_NUMBER:
    raise RuntimeError('Wrong bytecode generation.')
module = marshal.loads(raw[16:])
owner = next(code for code in module.co_consts if isinstance(code, types.CodeType) and code.co_name == 'DresserOutfitObject')
names = ('add_part_shift', 'remove_body_type', 'get_part_id', 'get_color_shift')
allowed = {'_body_types', 'index', '_part_ids', '_color_shifts', 'append', 'remove', 'len'}
methods = {}
records = []
for name in names:
    code = next(code for code in owner.co_consts if isinstance(code, types.CodeType) and code.co_name == name)
    if code.co_freevars or set(code.co_names) - allowed:
        raise RuntimeError('Helper acquired a dependency outside the verified pure surface.')
    methods[name] = types.FunctionType(code, {'__builtins__': __builtins__})
    records.append({'function': 'DresserOutfitObject.' + name, 'instruction_sha256': hashlib.sha256(code.co_code).hexdigest()})
namespace = {}
source = base64.b64decode(item['source'], validate=True)
exec(compile(source, 'apex_core/dresser_parts.py', 'exec'), namespace)
left = types.SimpleNamespace(_body_types=[7, 2], _part_ids=[99, 88], _color_shifts=[2**64-1, 0])
right = namespace['DresserParts']([7, 2], [99, 88], [2**64-1, 0])
cases = [('get_part_id', (7,)), ('get_color_shift', (7,)), ('add_part_shift', (7, 99, 2**64-1)),
         ('add_part_shift', (7, 99, 2**63+9)), ('add_part_shift', (9, 12345, 2**64-3)),
         ('remove_body_type', (2,)), ('remove_body_type', (2,)), ('get_part_id', (2,)), ('get_color_shift', (9,))]
for name, args in cases:
    if methods[name](left, *args) != getattr(right, name)(*args):
        raise RuntimeError('Ported result diverged from the authorized helper: ' + name)
    if (left._body_types, left._part_ids, left._color_shifts) != (right._body_types, right._part_ids, right._color_shifts):
        raise RuntimeError('Ported state diverged from the authorized helper: ' + name)
print(json.dumps({'functions': records, 'matching_cases': len(cases), 'game_modules_executed': False}))
'''


def verify():
    archive = ROOT / '.work' / 'baselines' / 'MCCC-2026.5.0.zip'
    raw = archive.read_bytes()
    identity = hashlib.sha256(raw).hexdigest()
    if identity != '5596e47a5d4dab0c4800e80426caf17d28d15508cd711848f083b9c9f63672c9':
        raise ValueError('MCCC baseline changed.')
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read('mc_cmd_center.ts4script'))) as inner:
            bytecode = inner.read('mc_utils.pyc')
    source = (ROOT / 'Source' / 'apex_core' / 'dresser_parts.py').read_bytes()
    compiler = DEFAULT_OUTPUT / 'python.exe'
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment.update({'PYTHONHOME': str(compiler.parent), 'PYTHONHASHSEED': '0'})
    result = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', VERIFY],
        input=json.dumps({'bytecode': base64.b64encode(bytecode).decode('ascii'), 'source': base64.b64encode(source).decode('ascii')}),
        text=True, capture_output=True, cwd=str(compiler.parent), env=environment, timeout=60)
    if result.returncode:
        raise ValueError(result.stderr[-2000:])
    proof = dict(json.loads(result.stdout), schema=1, baseline='MCCC 2026.5.0', author='Deaderpool',
        archive_sha256=identity, module='mc_cmd_center.ts4script/mc_utils.pyc', module_sha256=hashlib.sha256(bytecode).hexdigest(),
        port='Source/apex_core/dresser_parts.py', port_raw_sha256=hashlib.sha256(source).hexdigest(),
        limitations=['Pure helper behavior only; full MC CAS/Dresser feature parity and live persistence remain open.'])
    write_json(ROOT / 'manifests' / 'mccc-dresser-port.json', proof)
    return proof


if __name__ == '__main__':
    proof = verify()
    print(json.dumps({'matching_cases': proof['matching_cases'], 'ported_helpers': len(proof['functions']), 'game_modules_executed': False}))
