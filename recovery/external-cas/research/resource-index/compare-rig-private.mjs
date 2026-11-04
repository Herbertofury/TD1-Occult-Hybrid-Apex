// SPDX-License-Identifier: GPL-3.0-or-later
// Compare a bounded candidate set, without claiming that hash match picks a rig.
import os from 'node:os';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { indexPackage, readResource, readResourceBatch, resolveReferences } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';
import { parseGeom } from './geom.mjs';
import { parseRig, bindPalette, bindVertexWeights } from './rig.mjs';
import { compareRigReference, compareRigMatrices } from './rig-reference.mjs';

if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);
const paths = process.argv.slice(2);
if (paths.length !== 3 || !process.env.DOTNET_BIN || !process.env.CASP_ORACLE_DLL || !process.env.S4PY_ROOT || !process.env.S4PY_PYTHON)
  throw new Error('supply CASP package, mesh package, rig package and oracle environment');
const indexes = [];
for (const path of paths) indexes.push(await indexPackage(path));
const root = indexes[0].rows.find(row => row.key.startsWith('034AEECB:') && !row.deleted);
const casp = parseCasp((await readResource(paths[0], indexes[0], root.ordinal)).payload);
const meshRef = casp.roles.find(entry => entry.role === 'mesh');
const resolved = resolveReferences([meshRef], indexes.slice(0, 2))[0];
if (resolved.status !== 'unique-in-supplied-indexes') throw new Error('mesh reference not unique in supplied set');
const candidate = resolved.candidates[0];
const source = indexes.slice(0, 2).findIndex(index => index.source.sha256 === candidate.source.sha256);
const geom = parseGeom((await readResource(paths[source], indexes[source], candidate.row.ordinal)).payload);
if (geom.palette?.status !== 'palette-candidate') throw new Error('palette unavailable');
const offset = Number(process.env.CAS_RIG_OFFSET ?? 0);
const limit = Number(process.env.CAS_RIG_LIMIT ?? 128);
if (!Number.isSafeInteger(offset) || offset < 0 || offset > 100000 || !Number.isSafeInteger(limit) || limit < 1 || limit > 128) throw new Error('invalid candidate bound');
const rows = indexes[2].rows.filter(row => row.key.startsWith('8EAF13DE:') && !row.deleted).slice(offset, offset + limit);
if (!rows.length) throw new Error('no rig resources');
const resources = await readResourceBatch(paths[2], indexes[2], rows.map(row => row.ordinal));
const report = { sampled: rows.length, available: 0, parsed: 0, unsupported: 0, invalid: 0, fullHashMatch: 0, partialHashMatch: 0, readerMatched: 0, readerDisagreed: 0, payloadMatched: 0, matrixCheck: null };
for (let n = 0; n < resources.length; n++) {
  const resource = resources[n]; if (resource.status !== 'available') { report.unsupported++; continue; }
  report.available++;
  try {
    const rig = parseRig(resource.payload);
    if (rig.status !== 'rig-candidate') { report.unsupported++; continue; }
    report.parsed++;
    const binding = bindPalette(geom.palette, rig), matched = binding.entries.filter(entry => entry.status === 'unique').length;
    if (binding.status === 'bound-candidate') report.fullHashMatch++;
    else if (matched) report.partialHashMatch++;
    try {
      if (compareRigReference(resource.payload, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status === 'reader-matched') report.readerMatched++;
      else report.readerDisagreed++;
    } catch { report.readerDisagreed++; }
    if (report.matrixCheck === null) {
      try { report.matrixCheck = compareRigMatrices(resource.payload, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status; }
      catch { report.matrixCheck = 'reader-disagreed-or-failed'; }
    }
    if (!report.payloadMatched) {
      const bridge = fileURLToPath(new URL('./s4py_oracle.py', import.meta.url));
      const expected = execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, process.env.S4PY_ROOT, '--payload-hash', paths[2], String(rows[n].ordinal)], { encoding: 'utf8', maxBuffer: 1024, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
      if (createHash('sha256').update(resource.payload).digest('hex') !== expected) throw new Error('rig payload disagreement');
      report.payloadMatched++;
    }
  } catch { report.invalid++; }
}
if (process.env.CAS_RIG_FILE) {
  const raw = await readFile(process.env.CAS_RIG_FILE);
  const external = parseRig(raw), binding = bindPalette(geom.palette, external);
  const weights = bindVertexWeights(geom, external);
  report.explicitRig = { status: external.status, bindingStatus: binding.status,
    paletteMatches: binding.entries?.filter(entry => entry.status === 'unique').length ?? 0,
    vertexWeightStatus: weights.status, vertices: weights.vertices?.length ?? 0,
    nonUnitScaleBones: external.bones?.filter(bone => bone.scale.some(value => value !== 1)).length ?? 0,
    readerStatus: compareRigReference(raw, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status,
    matrixStatus: compareRigMatrices(raw, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status };
}
console.log(JSON.stringify(report));
