// SPDX-License-Identifier: GPL-3.0-or-later
// Compare a bounded candidate set, without claiming that hash match picks a rig.
import os from 'node:os';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readFile, stat } from 'node:fs/promises';
import { indexPackage, readResource, readResourceBatch, resolveReferences, scanPackageIndex } from './dbpf.mjs';
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
const minBytes = Number(process.env.CAS_RIG_MIN_BYTES ?? 0);
if (!Number.isSafeInteger(offset) || offset < 0 || offset > 100000 || !Number.isSafeInteger(limit) || limit < 1 || limit > 128 ||
    !Number.isSafeInteger(minBytes) || minBytes < 0 || minBytes > 16 * 1024 * 1024) throw new Error('invalid candidate bound');
const eligible = indexes[2].rows.filter(row => row.key.startsWith('8EAF13DE:') && !row.deleted && row.memorySize >= minBytes);
const rows = eligible.slice(offset, offset + limit);
if (!rows.length) throw new Error('no rig resources');
let externalRaw = null, external = null;
if (process.env.CAS_RIG_FILE) {
  const info = await stat(process.env.CAS_RIG_FILE);
  if (!info.isFile() || info.size > 16 * 1024 * 1024) throw new Error('rig extent');
  externalRaw = await readFile(process.env.CAS_RIG_FILE); external = parseRig(externalRaw);
}
const resources = await readResourceBatch(paths[2], indexes[2], rows.map(row => row.ordinal));
const report = { eligible: eligible.length, sampled: rows.length, available: 0, parsed: 0, unsupported: 0, invalid: 0, fullHashMatch: 0, partialHashMatch: 0,
  boneCounts: { upTo16: 0, upTo64: 0, upTo164: 0, exactly165: 0, above165: 0 },
  readerMatched: 0, readerDisagreed: 0, payloadMatched: 0, matrixCheck: null };
if (external?.status === 'rig-candidate') report.explicitRigComparison = { sameHashOrder: 0, sameHierarchy: 0, sameRawTransforms: 0, samePayload: 0 };
let conflictIndex = null;
if (process.env.CAS_RIG_CONFLICT_PACKAGE) {
  const other = await scanPackageIndex(process.env.CAS_RIG_CONFLICT_PACKAGE); conflictIndex = other;
  const keys = new Set(rows.map(row => row.key));
  const found = other.rows.filter(row => keys.has(row.key));
  report.conflicts = { source: 'index-only', exactRows: found.length, tombstones: found.filter(row => row.deleted).length, precedence: 'unresolved' };
}
for (let n = 0; n < resources.length; n++) {
  const resource = resources[n]; if (resource.status !== 'available') { report.unsupported++; continue; }
  report.available++;
  try {
    const rig = parseRig(resource.payload);
    if (rig.status !== 'rig-candidate') { report.unsupported++; continue; }
    report.parsed++;
    const count = rig.bones.length;
    report.boneCounts[count <= 16 ? 'upTo16' : count <= 64 ? 'upTo64' : count <= 164 ? 'upTo164' : count === 165 ? 'exactly165' : 'above165']++;
    if (report.explicitRigComparison && count === external.bones.length) {
      const sameOrder = rig.bones.every((bone, i) => bone.hash === external.bones[i].hash);
      const sameHierarchy = sameOrder && rig.bones.every((bone, i) => bone.parentIndex === external.bones[i].parentIndex);
      const sameTransforms = sameHierarchy && rig.bones.every((bone, i) => ['position', 'orientation', 'scale'].every(field => bone[field].every((v, j) => Object.is(v, external.bones[i][field][j]))));
      if (sameOrder) report.explicitRigComparison.sameHashOrder++;
      if (sameHierarchy) report.explicitRigComparison.sameHierarchy++;
      if (sameTransforms) report.explicitRigComparison.sameRawTransforms++;
      if (resource.payload.equals(externalRaw)) report.explicitRigComparison.samePayload++;
    }
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
if (conflictIndex && process.env.CAS_VERIFY_RIG_CONFLICT === '1') {
  const full = await indexPackage(process.env.CAS_RIG_CONFLICT_PACKAGE);
  const keys = new Set(rows.map(row => row.key));
  const conflicts = full.rows.filter(row => keys.has(row.key) && !row.deleted);
  if (conflicts.length > 128) throw new Error('conflict limit');
  const loaded = conflicts.length ? await readResourceBatch(process.env.CAS_RIG_CONFLICT_PACKAGE, full, conflicts.map(row => row.ordinal)) : [];
  const verified = { source: 'whole-file-verified', rows: conflicts.length, available: 0, sameAsFull: 0, sameAsExplicit: 0,
    sameHashOrderAsExplicit: 0, sameHierarchyAsExplicit: 0, sameTransformsAsExplicit: 0,
    maxRawTransformDelta: 0, readerMatched: 0, readerDisagreed: 0, precedence: 'unresolved' };
  for (let i = 0; i < conflicts.length; i++) {
    const item = loaded[i]; if (item.status !== 'available') continue;
    verified.available++;
    const sourceIndex = rows.findIndex(row => row.key === conflicts[i].key);
    if (sourceIndex >= 0 && resources[sourceIndex].status === 'available' && resources[sourceIndex].payload.equals(item.payload)) verified.sameAsFull++;
    if (externalRaw?.equals(item.payload)) verified.sameAsExplicit++;
    const rig = parseRig(item.payload);
    if (rig.status === 'rig-candidate' && external?.status === 'rig-candidate' && rig.bones.length === external.bones.length) {
      const sameOrder = rig.bones.every((bone, n) => bone.hash === external.bones[n].hash);
      if (sameOrder) verified.sameHashOrderAsExplicit++;
      if (sameOrder && rig.bones.every((bone, n) => bone.parentIndex === external.bones[n].parentIndex)) {
        verified.sameHierarchyAsExplicit++;
        let max = 0, same = true;
        for (let b = 0; b < rig.bones.length; b++) for (const field of ['position', 'orientation', 'scale'])
          for (let j = 0; j < rig.bones[b][field].length; j++) {
            const x = rig.bones[b][field][j], y = external.bones[b][field][j];
            max = Math.max(max, Math.abs(x - y)); if (!Object.is(x, y)) same = false;
          }
        verified.maxRawTransformDelta = Math.max(verified.maxRawTransformDelta, max);
        if (same) verified.sameTransformsAsExplicit++;
      }
    }
    try { if (compareRigReference(item.payload, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status === 'reader-matched') verified.readerMatched++; else verified.readerDisagreed++; }
    catch { verified.readerDisagreed++; }
  }
  report.verifiedConflicts = verified;
}
if (externalRaw) {
  const binding = bindPalette(geom.palette, external);
  const weights = bindVertexWeights(geom, external);
  report.explicitRig = { status: external.status, bindingStatus: binding.status,
    paletteMatches: binding.entries?.filter(entry => entry.status === 'unique').length ?? 0,
    vertexWeightStatus: weights.status, vertices: weights.vertices?.length ?? 0,
    nonUnitScaleBones: external.bones?.filter(bone => bone.scale.some(value => value !== 1)).length ?? 0,
    readerStatus: compareRigReference(externalRaw, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status,
    matrixStatus: compareRigMatrices(externalRaw, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status,
    approximateMatrixComparison: compareRigMatrices(externalRaw, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL, 1e-6) };
}
console.log(JSON.stringify(report));
