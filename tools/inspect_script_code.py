"""Passive matching-bytecode inspection; never import/execute a game module."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
from fetch_build_python import DEFAULT_OUTPUT

INSPECT = r'''
import base64, dis, hashlib, importlib.util, json, marshal, sys, types
item = json.load(sys.stdin)
raw = base64.b64decode(item['payload'], validate=True)
if raw[:4] != importlib.util.MAGIC_NUMBER or sys.version_info[:2] != (3, 7):
    raise RuntimeError('Wrong bytecode generation.')
code = marshal.loads(raw[16:])
rows = []
def primitives(value):
    if isinstance(value, (tuple, frozenset)):
        return [item for nested in value for item in primitives(nested)]
    if isinstance(value, (str, int, float, bool)) and (not isinstance(value, str) or len(value) < 3000):
        return [value]
    return []
def visit(code, prefix):
    name = prefix + code.co_name
    rows.append({'name': name, 'args': list(code.co_varnames[:code.co_argcount]),
        'filename': code.co_filename, 'instruction_sha256': hashlib.sha256(code.co_code).hexdigest(),
        'names': list(code.co_names),
        'constants': [item for value in code.co_consts for item in primitives(value)]})
    if item.get('function') and (name == item['function'] or code.co_name == item['function']):
        stream = io.StringIO()
        dis.dis(code, file=stream)
        rows[-1]['disassembly'] = stream.getvalue()
    for nested in code.co_consts:
        if isinstance(nested, types.CodeType):
            visit(nested, name + '.')
visit(code, '')
print(json.dumps(rows))
'''
# io is deliberately part of the compiler-side program, not a game dependency.
INSPECT = 'import io\n' + INSPECT


def inspect(script, module, function=None):
    with zipfile.ZipFile(io.BytesIO(script)) as archive:
        raw = archive.read(module)
    compiler = DEFAULT_OUTPUT / 'python.exe'
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment['PYTHONHOME'] = str(compiler.parent)
    environment['PYTHONHASHSEED'] = '0'
    result = subprocess.run([str(compiler), '-B', '-S', '-s', '-c', INSPECT],
        input=json.dumps({'payload': base64.b64encode(raw).decode('ascii'), 'function': function}),
        text=True, capture_output=True, cwd=str(compiler.parent), env=environment, timeout=60)
    if result.returncode:
        raise ValueError(result.stderr[-2000:])
    return json.loads(result.stdout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('module')
    parser.add_argument('--script-member')
    parser.add_argument('--function')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.archive.read_bytes()
    if args.script_member:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            raw = archive.read(args.script_member)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inspect(raw, args.module, args.function), indent=2), encoding='utf-8')
