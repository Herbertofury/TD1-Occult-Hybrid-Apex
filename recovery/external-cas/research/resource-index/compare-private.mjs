// SPDX-License-Identifier: GPL-3.0-or-later
// Local aggregate-only comparison. The oracle's per-resource output stays in memory.
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';
import { indexPackage, readResource, caspReferences, resolveReferences } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';

const paths = process.argv.slice(2);
if (!process.env.S4PY_ROOT || !process.env.S4PY_PYTHON || paths.length < 1 || paths.length > 4) {
  console.error('Set S4PY_ROOT and S4PY_PYTHON, and supply one to four explicit packages.');
  process.exitCode = 2;
} else {
  try {
    const bridge = fileURLToPath(new URL('./s4py_oracle.py', import.meta.url));
    const report = [], indexes = [], tables = [], roleSets = [];
    for (const [number, filename] of paths.entries()) {
      const index = await indexPackage(filename);
      indexes.push(index);
      const oracle = JSON.parse(execFileSync(process.env.S4PY_PYTHON,
        ['-B', bridge, process.env.S4PY_ROOT, filename], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] }));
      const rows = index.rows.map(({ key, offset, storedSize, memorySize, compression, committed, deleted }) =>
        ({ key, offset, storedSize, memorySize, compression, committed, deleted }));
      if (!isDeepStrictEqual(rows, oracle)) throw new Error(`reader disagreement at package ${number + 1}`);
      const methods = {};
      for (const row of rows) methods[row.compression.toString(16).toUpperCase().padStart(4, '0')] =
        (methods[row.compression.toString(16).toUpperCase().padStart(4, '0')] ?? 0) + 1;
      const casps = index.rows.filter(row => row.key.startsWith('034AEECB:') && !row.deleted);
      let caspSample = 'none';
      if (casps.length) {
        const read = await readResource(filename, index, casps[0].ordinal);
        if (read.status !== 'available') caspSample = read.status;
        else {
          try {
            const table = caspReferences(read.payload);
            caspSample = table.status;
            if (table.status === 'table-only') tables.push(table);
            const parsed = parseCasp(read.payload);
            if (parsed.status === 'parsed-candidate') roleSets.push(parsed.roles);
          }
          catch { caspSample = 'invalid-or-unsupported-table'; }
        }
      }
      report.push({ entries: rows.length, methods, caspCount: casps.length, caspSample, oracleMatched: true });
    }
    const referenceResults = {};
    for (const table of tables) for (const result of resolveReferences(table.references, indexes)) {
      referenceResults[result.status] = (referenceResults[result.status] ?? 0) + 1;
    }
    const roleResults = {};
    for (const roles of roleSets) for (const result of resolveReferences(roles, indexes)) {
      const summary = `${result.role}:${result.status}`;
      roleResults[summary] = (roleResults[summary] ?? 0) + 1;
    }
    const sharedKeyPairs = [];
    for (let a = 0; a < indexes.length; a++) for (let b = a + 1; b < indexes.length; b++) {
      const left = new Set(indexes[a].rows.map(row => row.key));
      const right = new Set(indexes[b].rows.map(row => row.key));
      let shared = 0;
      for (const key of right) if (left.has(key)) shared++;
      sharedKeyPairs.push({ packageA: a + 1, packageB: b + 1, sharedKeys: shared });
    }
    console.log(JSON.stringify({ packages: report, sharedKeyPairs, sampledTables: tables.length, referenceResults, roleResults }, null, 2));
  } catch (error) {
    // Paths, resource IDs, source hashes and oracle data are intentionally omitted.
    const known = ['unsupported DBPF version', 'index limit', 'invalid index extent', 'invalid index header',
      'unsupported index flags', 'index count exceeds extent', 'truncated index', 'resource outside file',
      'unsupported trailing index bytes', 'reader disagreement', 'payload limit'];
    const detail = known.find(value => error.message.includes(value)) ?? 'unclassified error';
    console.error(`Comparison failed: ${detail}.`);
    process.exitCode = 1;
  }
}
