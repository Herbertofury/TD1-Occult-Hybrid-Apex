// SPDX-License-Identifier: GPL-3.0-or-later
import { execFileSync } from 'node:child_process';
import { parseRig, computeBindMatrices } from './rig.mjs';

export function compareRigReference(payload, dotnet, dll) {
  const rig = parseRig(payload);
  if (rig.status !== 'rig-candidate') return { status: rig.status };
  const actual = rig.bones.map(({ name, hash, parentIndex, position, scale }) => ({ name, hash, parentIndex, position, scale }));
  const expected = JSON.parse(execFileSync(dotnet, [dll, 'rig'], { input: payload, encoding: 'utf8', maxBuffer: 1024 * 1024, stdio: ['pipe', 'pipe', 'pipe'] }))
    .map(bone => ({ ...bone, position: bone.position.map(Math.fround), scale: bone.scale.map(Math.fround) }));
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error('rig reader disagreement');
  return { status: 'reader-matched', bones: actual.length, chains: rig.chains.length };
}

export function compareRigMatrices(payload, dotnet, dll, scaleTolerance = 0) {
  const result = computeBindMatrices(parseRig(payload), { scaleTolerance });
  if (!['bind-matrices-candidate', 'bind-matrices-approximate-unit-scale'].includes(result.status)) return { status: result.status };
  const expected = JSON.parse(execFileSync(dotnet, [dll, 'rigmat'], { input: payload, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, stdio: ['pipe', 'pipe', 'pipe'] }));
  if (expected.length !== result.local.length) throw new Error('rig matrix count disagreement');
  let maxError = 0;
  for (let i = 0; i < expected.length; i++) for (const kind of ['local', 'global']) {
    if (expected[i][kind].length !== 16) throw new Error('rig matrix count disagreement');
    for (let n = 0; n < 16; n++) maxError = Math.max(maxError, Math.abs(expected[i][kind][n] - result[kind][i][n]));
  }
  if (scaleTolerance) return { status: 'comparison-only', candidateStatus: result.status, bones: expected.length, maxScaleDeviation: result.maxScaleDeviation, maxError };
  if (maxError > 1e-6) throw new Error('rig matrix disagreement');
  return { status: 'matrices-matched', bones: expected.length };
}
