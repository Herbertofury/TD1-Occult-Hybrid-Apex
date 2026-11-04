// Compare one explicit package's first RefPack payload without printing its data or hash.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { indexPackage, readResource } from './dbpf.mjs';

const [filename] = process.argv.slice(2);
if (!filename || process.argv.length !== 3 || !process.env.S4PY_ROOT || !process.env.S4PY_PYTHON) {
  console.error('Set oracle environment and supply one explicit package.'); process.exitCode = 2;
} else {
  try {
    const index = await indexPackage(filename);
    const row = index.rows.find(item => item.compression === 0xffff && !item.deleted);
    if (!row) throw new Error('no RefPack sample');
    const result = await readResource(filename, index, row.ordinal);
    if (result.status !== 'available') throw new Error('unsupported sample');
    const ownHash = createHash('sha256').update(result.payload).digest('hex');
    const bridge = fileURLToPath(new URL('./s4py_oracle.py', import.meta.url));
    const referenceHash = execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, process.env.S4PY_ROOT,
      '--payload-hash', filename, String(row.ordinal)], { encoding: 'utf8', maxBuffer: 1024, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
    if (ownHash !== referenceHash) throw new Error('digest mismatch');
    console.log(JSON.stringify({ samples: 1, matched: true, outputBytes: result.payload.length }));
  } catch {
    console.error('RefPack sample comparison failed; inspect locally without sharing source details.');
    process.exitCode = 1;
  }
}
