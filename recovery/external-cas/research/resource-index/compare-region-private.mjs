// SPDX-License-Identifier: GPL-3.0-or-later
// Resolve a first CASP's unique region-map candidate within one selected package.
import { indexPackage, readResource, resolveReferences } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';
import { compareRegionReference } from './region-reference.mjs';
import { parseRegionMap, mapMeshRegions } from './region-map.mjs';

const [filename] = process.argv.slice(2);
if (!filename || process.argv.length !== 3 || !process.env.CASP_ORACLE_DLL || !process.env.DOTNET_BIN) {
  console.error('Set CASP_ORACLE_DLL and DOTNET_BIN, and supply one package.'); process.exitCode = 2;
} else {
  try {
    const index = await indexPackage(filename);
    const casp = index.rows.find(row => row.key.startsWith('034AEECB:') && !row.deleted);
    if (!casp) throw new Error('no CASP');
    const caspData = await readResource(filename, index, casp.ordinal);
    if (caspData.status !== 'available') throw new Error('unsupported CASP');
    const parsed = parseCasp(caspData.payload);
    if (parsed.status !== 'parsed-candidate') throw new Error('unsupported CASP fields');
    const role = parsed.roles.find(ref => ref.role === 'region-map');
    const found = resolveReferences([role], [index])[0];
    if (found.status !== 'unique-in-supplied-indexes') throw new Error('unresolved region');
    const resource = await readResource(filename, index, found.candidates[0].row.ordinal);
    if (resource.status !== 'available') throw new Error('unsupported region');
    const result = compareRegionReference(resource.payload, process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL);
    const bindings = mapMeshRegions(parsed, parseRegionMap(resource.payload));
    console.log(JSON.stringify({ caspSamples: 1, resolvedRegionMaps: 1, matched: 1, ...result,
      boundMeshes: bindings.filter(item => item.state === 'matched').length,
      unmappedMeshes: bindings.filter(item => item.state === 'unmapped').length }));
  } catch {
    console.error('Region comparison failed; inspect privately without sharing source details.'); process.exitCode = 1;
  }
}
