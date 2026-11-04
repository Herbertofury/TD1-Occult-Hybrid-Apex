# SPDX-License-Identifier: GPL-3.0-or-later
"""Read an in-memory mesh through a separately obtained Blender GEOM reader."""
import contextlib
import hashlib
import io
import json
import struct
import sys
import types

package = types.ModuleType('io_simgeom')
package.__path__ = [sys.argv[1]]
sys.modules['io_simgeom'] = package
from io_simgeom.util.globals import Globals
Globals.HASHMAP = {'bones': {}, 'shader': {}}
from io_simgeom.io.geom_load import GeomLoader
from io_simgeom.util.bytereader import ByteReader

raw = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
if len(raw) > 32 * 1024 * 1024:
    raise ValueError('input bound')
# This reader assumes a seam-count field even for v12. For a separately
# reported comparison, insert an empty count in memory and adjust both offsets.
if len(sys.argv) > 2 and sys.argv[2] == '--normalize-v12':
    reader = ByteReader(raw)
    reader.skip(12)
    external, internal = reader.getUint32(), reader.getUint32()
    if internal != 1 or external > 128:
        raise ValueError('unsupported wrapper')
    reader.skip((external + internal) * 16)
    chunkpos = reader.getUint32()
    chunk_size_field = reader.getOffset()
    reader.getUint32()
    if reader.getOffset() != chunkpos or reader.getString(4) != 'GEOM' or reader.getUint32() != 12:
        raise ValueError('not v12')
    tgi_offset_field = reader.getOffset()
    reader.skip(8)
    shader = reader.getUint32()
    if shader:
        reader.skip(reader.getUint32())
    reader.skip(8)
    vertex_count, format_count = reader.getUint32(), reader.getUint32()
    with contextlib.redirect_stdout(io.StringIO()):
        GeomLoader.getElementData(reader, format_count, vertex_count)
        GeomLoader.getGroupData(reader)
    stitches = reader.getUint32()
    if stitches > 250000:
        raise ValueError('stitch bound')
    for _ in range(stitches):
        reader.skip(4)
        count = reader.getUint32()
        if count > 250000:
            raise ValueError('stitch bound')
        reader.skip(count * 8)
    offset = reader.getOffset()
    patched = bytearray(raw[:offset] + b'\x00\x00\x00\x00' + raw[offset:])
    struct.pack_into('<I', patched, chunk_size_field, struct.unpack_from('<I', raw, chunk_size_field)[0] + 4)
    struct.pack_into('<I', patched, tgi_offset_field, struct.unpack_from('<I', raw, tgi_offset_field)[0] + 4)
    raw = bytes(patched)
# The reference tool emits debug text with private asset details; keep it local.
with contextlib.redirect_stdout(io.StringIO()):
    geom = GeomLoader.readGeomFromBytes(raw)
digest = hashlib.sha256()
for vertex in geom.element_data:
    if vertex.position is None or vertex.normal is None or not vertex.uv:
        raise ValueError('incomplete reference vertex')
    digest.update(struct.pack('<8f', *(vertex.position + vertex.normal + vertex.uv[0])))
for face in geom.faces:
    digest.update(struct.pack('<3I', *face))
palette = [int(value, 16) for value in (geom.bones or [])]
palette_digest = hashlib.sha256(b''.join(struct.pack('<I', value) for value in palette)).hexdigest()
weights_digest = hashlib.sha256()
weighted = all(vertex.assignment is not None and vertex.weights is not None for vertex in geom.element_data)
if weighted:
    for vertex in geom.element_data:
        weights_digest.update(bytes(vertex.assignment))
        weights_digest.update(bytes(round(value * 255) for value in vertex.weights))
print(json.dumps({'version': geom.version, 'vertices': len(geom.element_data),
                  'triangles': len(geom.faces), 'geometryHash': digest.hexdigest(),
                  'materialReferences': geom.texture_refs, 'paletteCount': len(palette), 'paletteHash': palette_digest,
                  'weightsHash': weights_digest.hexdigest() if weighted else None}))
