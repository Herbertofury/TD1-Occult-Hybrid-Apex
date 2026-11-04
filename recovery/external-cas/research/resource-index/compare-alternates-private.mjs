// SPDX-License-Identifier: GPL-3.0-or-later
// Compare explicitly supplied cross-type leads; never choose an alias or winner.
import os from 'node:os';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { indexPackage, readResource, resolveReferences } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';
import { parseGeom } from './geom.mjs';
import { compareRleReference } from './rle-reference.mjs';

if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);
const paths = process.argv.slice(2);
if (paths.length !== 4 || !process.env.S4PY_ROOT || !process.env.S4PY_PYTHON) throw new Error('supply four explicit sources and s4py environment');
const indexes = [];
for (const path of paths) indexes.push(await indexPackage(path));
const root = indexes[0].rows.find(row => row.key.startsWith('034AEECB:') && !row.deleted);
const casp = parseCasp((await readResource(paths[0], indexes[0], root.ordinal)).payload);
const mesh = resolveReferences([casp.roles.find(role => role.role === 'mesh')], indexes.slice(0, 2))[0];
if (mesh.status !== 'unique-in-supplied-indexes') throw new Error('mesh is not unique');
const source = indexes.slice(0, 2).findIndex(index => index.source.sha256 === mesh.candidates[0].source.sha256);
const geom = parseGeom((await readResource(paths[source], indexes[source], mesh.candidates[0].row.ordinal)).payload);
const refs = geom.material?.entries?.filter(entry => entry.status === 'candidate') ?? [];
if (!refs.length || refs.some(entry => entry.key.slice(9) !== refs[0].key.slice(9))) throw new Error('material references differ');
const bridge = fileURLToPath(new URL('./s4py_oracle.py', import.meta.url));
const hashes = [], reports = [];
for (let i = 2; i < 4; i++) {
  const rows = indexes[i].rows.filter(row => !row.deleted && row.key.slice(9) === refs[0].key.slice(9) && row.key.slice(0, 8) === '3453CF95');
  if (rows.length !== 1) { reports.push({ status: 'missing-or-ambiguous', count: rows.length }); continue; }
  const resource = await readResource(paths[i], indexes[i], rows[0].ordinal);
  if (resource.status !== 'available') { reports.push({ status: resource.status }); continue; }
  const digest = createHash('sha256').update(resource.payload).digest('hex');
  const oracle = execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, process.env.S4PY_ROOT, '--payload-hash', paths[i], String(rows[0].ordinal)], { encoding: 'utf8', maxBuffer: 1024, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
  const record = { status: 'payload-read', s4pyMatched: digest === oracle, textureComparison: 'not-requested' };
  if (process.env.RLE_ORACLE_PYTHON && process.env.RLE_ORACLE_SOURCE && process.env.PILLOW_ORACLE_ROOT) {
    try { compareRleReference(resource.payload, process.env.RLE_ORACLE_PYTHON, process.env.RLE_ORACLE_SOURCE, process.env.PILLOW_ORACLE_ROOT); record.textureComparison = 'first-mip-matched'; }
    catch { record.textureComparison = 'unsupported-or-disagreed'; }
  }
  reports.push(record); hashes.push(digest);
}
console.log(JSON.stringify({ roles: refs.map(ref => ref.role), sourcesInArgumentOrder: reports,
  payloadsIdentical: hashes.length === 2 ? hashes[0] === hashes[1] : null, aliasOrPrecedence: 'unresolved' }));
