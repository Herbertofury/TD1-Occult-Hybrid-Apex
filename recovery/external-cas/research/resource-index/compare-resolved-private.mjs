// SPDX-License-Identifier: GPL-3.0-or-later
// Resolve one CASP against two explicit indexes and compare selected payload hashes.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { indexPackage, readResource, readResourceBatch, resolveReferences } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';
import { parseGeom } from './geom.mjs';
import { compareGeomReference } from './geom-reference.mjs';
import { compareRleReference } from './rle-reference.mjs';
import { mapPaletteWeights } from './palette.mjs';
import os from 'node:os';

if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);

const paths = process.argv.slice(2);
if (paths.length !== 2 || !process.env.S4PY_ROOT || !process.env.S4PY_PYTHON) {
  console.error('Set oracle environment and supply CASP source plus one dependency package.'); process.exitCode = 2;
} else {
  try {
    const indexes = [];
    for (const path of paths) indexes.push(await indexPackage(path));
    const root = indexes[0].rows.find(row => row.key.startsWith('034AEECB:') && !row.deleted);
    if (!root) throw new Error('no CASP');
    const casp = await readResource(paths[0], indexes[0], root.ordinal);
    if (casp.status !== 'available') throw new Error('unavailable CASP');
    const parsed = parseCasp(casp.payload);
    if (parsed.status !== 'parsed-candidate') throw new Error('unsupported CASP');
    const requested = ['mesh', 'diffuse', 'shadow', 'normal', 'specular', 'emission', 'blend-geometry', 'color-shift-mask'];
    const selected = requested.map(role => parsed.roles.find(entry => entry.role === role)).filter(Boolean);
    const resolved = resolveReferences(selected, indexes);
    const report = {}, groups = new Map();
    for (const entry of resolved) {
      report[entry.role] = { status: entry.status };
      if (entry.status !== 'unique-in-supplied-indexes') continue;
      const candidate = entry.candidates[0];
      const source = indexes.findIndex(index => index.source.sha256 === candidate.source.sha256 && index.source.size === candidate.source.size);
      if (source < 0) throw new Error('missing source');
      const key = `${source}:${candidate.row.ordinal}`;
      if (!groups.has(key)) groups.set(key, { source, row: candidate.row, roles: [] });
      groups.get(key).roles.push(entry.role);
    }
    const bridge = fileURLToPath(new URL('./s4py_oracle.py', import.meta.url));
    for (let source = 0; source < indexes.length; source++) {
      const entries = [...groups.values()].filter(group => group.source === source);
      if (!entries.length) continue;
      const resources = await readResourceBatch(paths[source], indexes[source], entries.map(entry => entry.row.ordinal));
      for (let i = 0; i < entries.length; i++) {
        const resource = resources[i], entry = entries[i];
        if (resource.status !== 'available') {
          for (const role of entry.roles) report[role] = { status: resource.status };
          continue;
        }
        const actual = createHash('sha256').update(resource.payload).digest('hex');
        const expected = execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, process.env.S4PY_ROOT,
          '--payload-hash', paths[source], String(entry.row.ordinal)], { encoding: 'utf8', maxBuffer: 1024, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
        if (actual !== expected) throw new Error('payload digest mismatch');
        for (const role of entry.roles) {
          report[role] = { status: 'payload-digest-matched', type: entry.row.key.slice(0, 8), bytes: resource.payload.length };
          if (['diffuse', 'shadow', 'specular', 'normal', 'emission', 'color-shift-mask'].includes(role) && resource.payload.length >= 16) {
            report[role].textureHeader = { fourcc: resource.payload.toString('ascii', 0, 4), format: resource.payload.toString('ascii', 4, 8),
              width: resource.payload.readUInt16LE(8), height: resource.payload.readUInt16LE(10), mipCount: resource.payload.readUInt16LE(12) };
            if (['diffuse', 'specular'].includes(role) && process.env.RLE_ORACLE_PYTHON && process.env.RLE_ORACLE_SOURCE && process.env.PILLOW_ORACLE_ROOT) {
              try {
                compareRleReference(resource.payload, process.env.RLE_ORACLE_PYTHON, process.env.RLE_ORACLE_SOURCE, process.env.PILLOW_ORACLE_ROOT);
                report[role].textureDecode = 'rle-and-rgba-oracles-matched';
              } catch (error) {
                const known = ['invalid RLE', 'RLE output limit', 'truncated RLE', 'unsupported RLE', 'incomplete RLE', 'RLE block disagreement', 'BC3 pixel disagreement'];
                report[role].textureDecode = known.find(value => error.message.includes(value)) ?? 'unsupported-or-oracle-failed';
              }
            }
          }
          if (role === 'mesh') {
            try {
              const geom = parseGeom(resource.payload);
              report[role].geometry = { status: geom.status, version: geom.version ?? null,
                vertices: geom.vertices?.length ?? null, triangles: geom.indices ? geom.indices.length / 3 : null,
                materialStatus: geom.material?.status ?? null,
                materialReferences: geom.material?.entries?.filter(entry => entry.status === 'candidate').length ?? null,
                paletteStatus: geom.palette?.status ?? null, paletteBones: geom.palette?.hashes?.length ?? null };
              if (geom.status === 'geometry-candidate') {
                try { report[role].geometry.weightMapping = mapPaletteWeights(geom).status; }
                catch { report[role].geometry.weightMapping = 'invalid-or-unsupported-weights'; }
              }
              if (geom.material?.status === 'parsed-candidate') {
                const refs = geom.material.entries.filter(entry => entry.status === 'candidate').map(entry => ({
                  role: entry.role, key: entry.key, empty: entry.key === '00000000:00000000:0000000000000000',
                }));
                report[role].geometry.materialRoles = resolveReferences(refs, indexes).map(ref => ({ role: ref.role, status: ref.status }));
              }
              if (geom.status === 'geometry-candidate' && process.env.GEOM_ORACLE_PYTHON && process.env.GEOM_ORACLE_ROOT) {
                try {
                  const check = compareGeomReference(resource.payload, process.env.GEOM_ORACLE_PYTHON, process.env.GEOM_ORACLE_ROOT);
                  report[role].geometry.oracleMatched = true; report[role].geometry.materialOracleMatched = check.materialMatched;
                  report[role].geometry.paletteOracleMatched = check.paletteMatched; report[role].geometry.weightsOracleMatched = check.weightsMatched;
                  if (geom.version === 12 && check.paletteMatched === false) {
                    const normalized = compareGeomReference(resource.payload, process.env.GEOM_ORACLE_PYTHON, process.env.GEOM_ORACLE_ROOT, true);
                    report[role].geometry.paletteNormalizedOracleMatched = normalized.paletteMatched;
                  }
                }
                catch { report[role].geometry.oracleMatched = false; }
              }
            } catch { report[role].geometry = { status: 'invalid-or-unsupported' }; }
          }
        }
      }
    }
    console.log(JSON.stringify({ caspSamples: 1, roles: report }, null, 2));
  } catch {
    console.error('Dependency comparison failed; inspect privately without sharing source details.'); process.exitCode = 1;
  }
}
