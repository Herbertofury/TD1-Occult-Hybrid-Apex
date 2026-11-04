// SPDX-License-Identifier: GPL-3.0-or-later
// One or two explicitly selected package CASPs; no keys, names or payload printed.
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { indexPackage, readResource } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';

const [filename] = process.argv.slice(2);
if (!filename || process.argv.length !== 3 || !process.env.S4PY_PYTHON) {
  console.error('Set S4PY_PYTHON and supply one explicit package.'); process.exitCode = 2;
} else {
  try {
    const index = await indexPackage(filename);
    const rows = index.rows.filter(r => r.key.startsWith('034AEECB:') && !r.deleted).slice(0, 2);
    if (!rows.length) throw new Error('no CASP');
    const bridge = fileURLToPath(new URL('./casp_oracle.py', import.meta.url));
    const patch = fileURLToPath(new URL('../../examples/pinned-casp-resource-candidate.patch', import.meta.url));
    let matched = 0, meshReferences = 0;
    for (const row of rows) {
      const item = await readResource(filename, index, row.ordinal);
      if (item.status !== 'available') throw new Error('unsupported CASP');
      const ours = parseCasp(item.payload);
      if (ours.status !== 'parsed-candidate') throw new Error('unsupported CASP version');
      const oracle = JSON.parse(execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, patch],
        { input: item.payload, encoding: 'utf8', maxBuffer: 1024 * 1024, stdio: ['pipe', 'pipe', 'pipe'] }));
      const role = name => ours.roles.find(r => r.role === name)?.key;
      if (ours.version !== oracle.version || (ours.name || null) !== oracle.internal_name || ours.bodyType !== oracle.body_type ||
          ours.species !== oracle.species || role('diffuse') !== oracle.texture || role('shadow') !== oracle.shadow ||
          role('normal') !== oracle.normal || role('specular') !== oracle.specular || role('region-map') !== oracle.region_map)
        throw new Error('CASP field disagreement');
      const meshes = ours.roles.filter(r => r.role === 'mesh').map(r => `${r.lod}:${r.key}`);
      const expected = oracle.lods.flatMap(lod => lod.geometries.map(key => `${lod.lod}:${key}`));
      if (JSON.stringify(meshes) !== JSON.stringify(expected)) throw new Error('CASP mesh disagreement');
      matched++; meshReferences += meshes.length;
    }
    console.log(JSON.stringify({ samples: rows.length, matched, meshReferences }));
  } catch (error) {
    const known = ['unsupported CASP', 'CASP reference index out of range', 'truncated CASP fields',
      'invalid CASP', 'CASP count limit', 'CASP field disagreement', 'CASP mesh disagreement'];
    const reason = known.find(value => error.message.includes(value)) ?? 'oracle or unclassified failure';
    console.error(`CASP comparison failed: ${reason}.`); process.exitCode = 1;
  }
}
