// SPDX-License-Identifier: GPL-3.0-or-later
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { parseGeom } from './geom.mjs';

export function compareGeomReference(payload, python, root) {
  const geom = parseGeom(payload);
  if (geom.status !== 'geometry-candidate') throw new Error('unsupported GEOM');
  const digest = createHash('sha256'), packed = Buffer.alloc(32);
  for (const vertex of geom.vertices) {
    const values = [...vertex.position, ...vertex.normal, ...vertex.uvs[0]];
    values.forEach((value, i) => packed.writeFloatLE(value, i * 4));
    digest.update(packed);
  }
  const packedIndex = Buffer.alloc(4);
  for (const index of geom.indices) { packedIndex.writeUInt32LE(index); digest.update(packedIndex); }
  const bridge = fileURLToPath(new URL('./geom_oracle.py', import.meta.url));
  const oracle = JSON.parse(execFileSync(python, ['-B', bridge, root],
    { input: payload, encoding: 'utf8', maxBuffer: 1024, stdio: ['pipe', 'pipe', 'pipe'] }));
  if (oracle.version !== geom.version || oracle.vertices !== geom.vertices.length || oracle.triangles !== geom.indices.length / 3 ||
      oracle.geometryHash !== digest.digest('hex')) throw new Error('GEOM disagreement');
  let materialMatched = null;
  if (geom.material.status === 'parsed-candidate') {
    const known = {};
    for (const entry of geom.material.entries) if (entry.role && entry.type === 4 && entry.length === 4) {
      if (Object.hasOwn(known, entry.role)) throw new Error('duplicate material role');
      known[entry.role] = entry.index;
    }
    const expected = oracle.materialReferences ?? {};
    materialMatched = Object.keys(known).length === Object.keys(expected).length &&
      Object.entries(known).every(([role, index]) => expected[role] === index);
    if (!materialMatched) throw new Error('material reference disagreement');
  }
  return { version: geom.version, vertices: geom.vertices.length, triangles: geom.indices.length / 3, materialMatched };
}
