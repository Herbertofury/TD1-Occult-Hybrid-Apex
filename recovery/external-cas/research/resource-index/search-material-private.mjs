// SPDX-License-Identifier: GPL-3.0-or-later
// Scan explicitly supplied package indexes for a sampled mesh's material TGIs.
import path from 'node:path';
import os from 'node:os';
import { indexPackage, readResource, resolveReferences, scanPackageIndex } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';
import { parseGeom } from './geom.mjs';

if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);
const args = process.argv.slice(2), [caspPath, meshPath, ...searchPaths] = args;
if (!caspPath || !meshPath || !searchPaths.length || searchPaths.length > 32) {
  console.error('Supply CASP package, mesh package, and one to 32 explicit search packages.'); process.exitCode = 2;
} else {
  try {
    const sources = [await indexPackage(caspPath), await indexPackage(meshPath)];
    const root = sources[0].rows.find(row => row.key.startsWith('034AEECB:') && !row.deleted);
    if (!root) throw new Error('no CASP');
    const payload = await readResource(caspPath, sources[0], root.ordinal);
    if (payload.status !== 'available') throw new Error('unavailable CASP');
    const casp = parseCasp(payload.payload);
    if (casp.status !== 'parsed-candidate') throw new Error('unsupported CASP');
    const meshRole = casp.roles.find(role => role.role === 'mesh');
    const candidate = resolveReferences([meshRole], sources)[0];
    if (candidate.status !== 'unique-in-supplied-indexes') throw new Error('mesh ambiguity');
    const source = sources.findIndex(item => item.source.sha256 === candidate.candidates[0].source.sha256);
    if (source < 0) throw new Error('missing source');
    const mesh = await readResource([caspPath, meshPath][source], sources[source], candidate.candidates[0].row.ordinal);
    if (mesh.status !== 'available') throw new Error('unavailable mesh');
    const geom = parseGeom(mesh.payload);
    if (geom.status !== 'geometry-candidate' || geom.material?.status !== 'parsed-candidate') throw new Error('unsupported material');
    const wanted = geom.material.entries.filter(entry => entry.status === 'candidate');
    if (!wanted.length || wanted.length > 32) throw new Error('no bounded material references');
    const results = wanted.map(entry => ({ role: entry.role, key: entry.key, matches: 0, classes: {}, alternateTypes: {},
      type: entry.key.slice(0, 8), zeroGroup: entry.key.slice(9, 17) === '00000000', zeroInstance: entry.key.slice(18) === '0000000000000000',
      sameGroupInstanceAsCaspRoles: casp.roles.filter(role => !role.empty && role.key.slice(9) === entry.key.slice(9)).map(role => role.role),
      sameGroupInstanceAsMaterialRoles: wanted.filter(other => other !== entry && other.key.slice(9) === entry.key.slice(9)).map(other => other.role) }));
    const seen = new Set();
    let scanned = 0, failed = 0;
    for (const filename of searchPaths) {
      const identity = path.resolve(filename).toLowerCase();
      if (seen.has(identity)) continue;
      seen.add(identity);
      try {
        const index = await scanPackageIndex(filename);
        const normalized = identity.replaceAll('\\', '/');
        const category = /\/data\/client\/clientfullbuild\d+\.package$/.test(normalized) ? 'base-full' :
          /\/data\/client\/clientdeltabuild\d+\.package$/.test(normalized) ? 'base-delta' :
          /\/delta\/[^/]+\//.test(normalized) ? 'pack-delta' :
          /\/(?:ep|gp|sp|fp)\d\d\/clientfullbuild\d+\.package$/.test(normalized) ? 'pack-full' : 'other';
        for (const row of index.rows) for (const item of results) {
          if (row.key === item.key) {
            item.matches++;
            item.classes[category] = (item.classes[category] ?? 0) + 1;
          } else if (row.key.slice(9) === item.key.slice(9)) {
            const type = row.key.slice(0, 8);
            const alt = item.alternateTypes[type] ?? { total: 0, deleted: 0, classes: {}, compression: {} };
            alt.total++;
            if (row.deleted) alt.deleted++;
            const method = row.compression.toString(16).toUpperCase().padStart(4, '0');
            alt.compression[method] = (alt.compression[method] ?? 0) + 1;
            alt.classes[category] = (alt.classes[category] ?? 0) + 1;
            item.alternateTypes[type] = alt;
          }
        }
        scanned++;
      } catch { failed++; }
    }
    console.log(JSON.stringify({ scan: 'index-only-unverified-payloads', scanned, failed,
      references: results.map(({ role, type, zeroGroup, zeroInstance, matches, classes, alternateTypes, sameGroupInstanceAsCaspRoles, sameGroupInstanceAsMaterialRoles }) =>
        ({ role, type, zeroGroup, zeroInstance, matches, classes, alternateTypes, sameGroupInstanceAsCaspRoles, sameGroupInstanceAsMaterialRoles })) }, null, 2));
  } catch {
    console.error('Material discovery failed; inspect privately without sharing source details.'); process.exitCode = 1;
  }
}
