// SPDX-License-Identifier: GPL-3.0-or-later
// Compare explicit fixtures to bounded 165-bone source candidates, in memory.
import os from 'node:os';
import { readFile, stat } from 'node:fs/promises';
import { indexPackage, readResourceBatch } from './dbpf.mjs';
import { parseRig } from './rig.mjs';
import { compareRigReference } from './rig-reference.mjs';
if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);
const [fullPath, deltaPath, ...fixturePaths] = process.argv.slice(2);
if (!fullPath || !deltaPath || !fixturePaths.length || fixturePaths.length > 8 || !process.env.DOTNET_BIN || !process.env.CASP_ORACLE_DLL)
  throw new Error('supply full package, delta package, 1-8 fixtures and independent reader');
const fixtures = [];
for (const filename of fixturePaths) {
  const info = await stat(filename); if (!info.isFile() || info.size > 16 * 1024 * 1024) throw new Error('fixture bound');
  const raw = await readFile(filename), rig = parseRig(raw);
  if (rig.status !== 'rig-candidate' || rig.bones.length !== 165 || compareRigReference(raw, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status !== 'reader-matched')
    throw new Error('fixture unsupported or reader disagreement');
  fixtures.push({ raw, rig });
}
const full = await indexPackage(fullPath), delta = await indexPackage(deltaPath);
// A v3.1 rig needs at least 60 bytes per bone plus a 16-byte header/trailer.
const rows = full.rows.filter(row => row.key.startsWith('8EAF13DE:') && !row.deleted && row.memorySize >= 16 + 165 * 60);
if (!rows.length || rows.length > 128) throw new Error('candidate bound');
const keys = new Set(rows.map(row => row.key));
const overrides = delta.rows.filter(row => keys.has(row.key) && !row.deleted);
if (overrides.length > 128) throw new Error('override bound');
const fullResources = await readResourceBatch(fullPath, full, rows.map(row => row.ordinal));
const deltaResources = overrides.length ? await readResourceBatch(deltaPath, delta, overrides.map(row => row.ordinal)) : [];
function compare(resources) {
  const results = fixtures.map(() => ({ samePayload: 0, sameOrder: 0, sameHierarchy: 0 }));
  let available = 0, readerMatched = 0, unsupported = 0;
  for (const item of resources) {
    if (item.status !== 'available') { unsupported++; continue; }
    const rig = parseRig(item.payload);
    if (rig.status !== 'rig-candidate' || rig.bones.length !== 165) { unsupported++; continue; }
    available++;
    if (compareRigReference(item.payload, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).status === 'reader-matched') readerMatched++;
    fixtures.forEach((fixture, i) => {
      if (fixture.raw.equals(item.payload)) results[i].samePayload++;
      const sameOrder = rig.bones.every((bone, n) => bone.hash === fixture.rig.bones[n].hash);
      if (sameOrder) results[i].sameOrder++;
      if (sameOrder && rig.bones.every((bone, n) => bone.parentIndex === fixture.rig.bones[n].parentIndex)) results[i].sameHierarchy++;
    });
  }
  return { available, readerMatched, unsupported, fixturesInArgumentOrder: results };
}
console.log(JSON.stringify({ fullCandidates: rows.length, exactDeltaRows: overrides.length,
  full: compare(fullResources), delta: compare(deltaResources), precedence: 'unresolved' }));
