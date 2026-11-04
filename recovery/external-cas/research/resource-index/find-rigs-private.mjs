// SPDX-License-Identifier: GPL-3.0-or-later
// Index-only discovery; output aggregates only and never selects a rig.
import { scanPackageIndex } from './dbpf.mjs';
import os from 'node:os';
if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);
const paths = process.argv.slice(2);
if (!paths.length || paths.length > 32) throw new Error('supply 1-32 explicit packages');
const counts = [];
for (const path of paths) {
  const index = await scanPackageIndex(path);
  counts.push(index.rows.filter(row => row.key.startsWith('8EAF13DE:') && !row.deleted).length);
}
console.log(JSON.stringify({ packageCountsInArgumentOrder: counts, packages: counts.length, candidates: counts.reduce((a, b) => a + b, 0) }));
