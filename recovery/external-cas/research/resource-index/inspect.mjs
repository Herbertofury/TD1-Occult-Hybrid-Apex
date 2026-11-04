// Explicit package set only; prints private metadata to stdout, never asset bytes.
import { indexPackage, readResource, caspReferences, resolveReferences } from './dbpf.mjs';

const [key, ...paths] = process.argv.slice(2);
if (!/^034AEECB:[0-9A-F]{8}:[0-9A-F]{16}$/.test(key ?? '') || !paths.length || paths.length > 16) {
  console.error('Usage: node inspect.mjs <uppercase-CASP-TGI> <package> [package ...] (maximum 16)');
  process.exitCode = 2;
} else {
  try {
    const indexes = [];
    let rowCount = 0;
    for (const filename of paths) {
      const index = await indexPackage(filename);
      rowCount += index.rows.length;
      if (rowCount > 250_000) throw new Error('combined index limit');
      indexes.push(index);
    }
    const candidates = [];
    for (let i = 0; i < indexes.length; i++) for (const row of indexes[i].rows) {
      if (row.key === key) candidates.push({ packageIndex: i, row });
    }
    if (candidates.length !== 1) throw new Error(`CASP selection is ${candidates.length ? 'ambiguous' : 'missing'} in supplied indexes`);
    const { packageIndex, row } = candidates[0];
    const result = await readResource(paths[packageIndex], indexes[packageIndex], row.ordinal);
    if (result.status !== 'available') throw new Error(`CASP payload ${result.status}`);
    const table = caspReferences(result.payload);
    console.log(JSON.stringify({ source: indexes[packageIndex].source, casp: row, table: {
      status: table.status, version: table.version, references: resolveReferences(table.references, indexes),
    } }, null, 2));
  } catch (error) {
    console.error(`Inspection failed: ${error.message}`);
    process.exitCode = 1;
  }
}
