# SPDX-License-Identifier: GPL-3.0-or-later
"""Use the recovered GPL CASP research patch as a private in-memory test oracle."""
import json
import pathlib
import struct
import sys
import types

# The recovered parser imports a Reader from a separately retained helper that
# is absent from this checkout. Supply only its bounded read/format interface;
# the independent versioned CASP traversal remains the recovered patch's code.
class Reader:
    def __init__(self, raw):
        self.raw, self.position, self.limit = raw, 0, len(raw)
    def take(self, n):
        if n < 0 or self.position + n > self.limit:
            raise ValueError('bounded read')
        value = self.raw[self.position:self.position + n]
        self.position += n
        return value
    def value(self, kind):
        return struct.unpack('<' + kind, self.take(struct.calcsize('<' + kind)))[0]
    def count(self, limit):
        n = self.value('i')
        if n < 0 or n > limit:
            raise ValueError('count bound')
        return n
def tgi(value):
    return '{:08X}:{:08X}:{:016X}'.format(*value)
shim = types.ModuleType('cas_resource_catalog')
shim.Reader, shim.tgi = Reader, tgi
sys.modules['cas_resource_catalog'] = shim

patch = pathlib.Path(sys.argv[1])
with patch.open('r', encoding='utf-8') as handle:
    text = handle.read()
marker = '+++ b/tools/research/casp_material.py\n'
section = text.replace('\r\n', '\n').split(marker, 1)[1]
source = '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+'))
scope = {'__file__': str(patch)}
exec(compile(source, str(patch), 'exec'), scope)
data = sys.stdin.buffer.read(1024 * 1024 + 1)
if len(data) > 1024 * 1024:
    raise ValueError('input bound')
value = scope['casp_material'](data)
print(json.dumps({key: value[key] for key in ['version', 'internal_name', 'body_type', 'species', 'texture', 'shadow', 'normal', 'specular', 'region_map', 'lods']}))
