# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the independent Blender add-on's RLE method and Pillow in memory."""
import ast
import contextlib
import hashlib
import io
import json
import pathlib
import struct
import sys

sys.path.insert(0, sys.argv[2])
from PIL import Image

source = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
tree = ast.parse(source)
methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == '_convert_rle_manual']
if not methods:
    raise ValueError('missing reference decoder')
method = methods[0]
method.decorator_list = []
scope = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), '<reference-rle>', 'exec'), scope)
raw = sys.stdin.buffer.read(64 * 1024 * 1024 + 1)
if len(raw) > 64 * 1024 * 1024:
    raise ValueError('input bound')
with contextlib.redirect_stdout(io.StringIO()):
    dds = scope['_convert_rle_manual'](None, raw)
if not dds or len(dds) < 128:
    raise ValueError('reference decode failed')
width, height = struct.unpack_from('<HH', raw, 8)
size = ((width + 3) // 4) * ((height + 3) // 4) * 16
if len(dds) < 128 + size:
    raise ValueError('reference mip truncated')
image = Image.open(io.BytesIO(dds)).convert('RGBA')
if image.size != (width, height):
    raise ValueError('reference dimensions mismatch')
print(json.dumps({'width': width, 'height': height,
    'bc3Hash': hashlib.sha256(dds[128:128 + size]).hexdigest(),
    'rgbaHash': hashlib.sha256(image.tobytes()).hexdigest()}))
