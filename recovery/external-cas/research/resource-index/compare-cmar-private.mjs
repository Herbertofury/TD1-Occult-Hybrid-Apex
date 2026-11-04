// SPDX-License-Identifier: GPL-3.0-or-later
// Compare two explicit package CASPs; print aggregate counts only.
import { indexPackage, readResource } from './dbpf.mjs';
import { compareCaspReference } from './casp-reference.mjs';

const [filename] = process.argv.slice(2);
if (!filename || process.argv.length !== 3 || !process.env.CASP_ORACLE_DLL || !process.env.DOTNET_BIN) {
  console.error('Set CASP_ORACLE_DLL and DOTNET_BIN, and supply one package.'); process.exitCode = 2;
} else {
  try {
    const index = await indexPackage(filename);
    const rows = index.rows.filter(row => row.key.startsWith('034AEECB:') && !row.deleted).slice(0, 2);
    if (!rows.length) throw new Error('no CASP');
    let meshReferences = 0;
    for (const row of rows) {
      const resource = await readResource(filename, index, row.ordinal);
      if (resource.status !== 'available') throw new Error('unsupported payload');
      meshReferences += compareCaspReference(resource.payload, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).meshReferences;
    }
    console.log(JSON.stringify({ samples: rows.length, matched: rows.length, meshReferences }));
  } catch {
    console.error('Reference comparison failed; inspect privately without sharing source details.'); process.exitCode = 1;
  }
}
