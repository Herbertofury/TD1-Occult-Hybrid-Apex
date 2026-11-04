// SPDX-License-Identifier: GPL-3.0-or-later
// Compare in-memory CASP fields against a locally built TS4CAS Tools bridge.
import { execFileSync } from 'node:child_process';
import { parseCasp } from './casp.mjs';

export function compareCaspReference(payload, dotnet, oracleDll) {
  const ours = parseCasp(payload);
  if (ours.status !== 'parsed-candidate') throw new Error('unsupported CASP');
  const reference = JSON.parse(execFileSync(dotnet, [oracleDll], {
    input: payload, encoding: 'utf8', maxBuffer: 1024 * 1024, stdio: ['pipe', 'pipe', 'pipe'],
  }));
  const role = name => ours.roles.find(item => item.role === name)?.key;
  if (ours.version !== reference.version || ours.bodyType !== reference.body || ours.age !== reference.age ||
      (ours.gender >> 4) !== reference.gender || (ours.species !== null && ours.species !== reference.species) ||
      role('diffuse') !== reference.diffuse || role('shadow') !== reference.shadow || role('region-map') !== reference.region ||
      role('normal') !== reference.normal || role('specular') !== reference.specular) throw new Error('CASP field disagreement');
  const actual = ours.roles.filter(item => item.role === 'mesh').map(item => `${item.lod}:${item.key}`).sort();
  const expected = reference.meshes.map(item => `${item.lod}:${item.key}`).sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error('CASP mesh disagreement');
  return { meshReferences: actual.length };
}
