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

raw = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
if len(raw) > 32 * 1024 * 1024:
    raise ValueError('input bound')
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
print(json.dumps({'version': geom.version, 'vertices': len(geom.element_data),
                  'triangles': len(geom.faces), 'geometryHash': digest.hexdigest(),
                  'materialReferences': geom.texture_refs}))
