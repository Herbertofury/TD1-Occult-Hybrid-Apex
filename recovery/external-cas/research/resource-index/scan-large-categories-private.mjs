// SPDX-License-Identifier: GPL-3.0-or-later
// Index-only package category counts; never authenticates payloads or selects sources.
import os from 'node:os';
import { scanPackageIndex } from './dbpf.mjs';
if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);
const paths = process.argv.slice(2);
if (!paths.length || paths.length > 32) throw new Error('supply 1-32 explicit packages');
const types = { '034AEECB': 'casp', '015A1849': 'geom', '3453CF95': 'rle2', 'BA856C78': 'rles', '8EAF13DE': 'rig' };
const packages = [];
for (const path of paths) {
  const index = await scanPackageIndex(path), counts = { casp: 0, geom: 0, rle2: 0, rles: 0, rig: 0 };
  for (const row of index.rows) if (!row.deleted && types[row.key.slice(0, 8)]) counts[types[row.key.slice(0, 8)]]++;
  packages.push({ bytes: index.source.size, rows: index.rows.length, counts });
}
console.log(JSON.stringify({ verification: 'index-only', packagesInArgumentOrder: packages }));
