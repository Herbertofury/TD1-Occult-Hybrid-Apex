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

export function compareRigMatrices(payload, dotnet, dll) {
  const result = computeBindMatrices(parseRig(payload));
  if (result.status !== 'bind-matrices-candidate') return { status: result.status };
  const expected = JSON.parse(execFileSync(dotnet, [dll, 'rigmat'], { input: payload, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, stdio: ['pipe', 'pipe', 'pipe'] }));
  if (expected.length !== result.local.length) throw new Error('rig matrix count disagreement');
  for (let i = 0; i < expected.length; i++) for (const kind of ['local', 'global']) {
    if (expected[i][kind].length !== 16 || expected[i][kind].some((value, n) => Math.abs(value - result[kind][i][n]) > 1e-6)) throw new Error('rig matrix disagreement');
  }
  return { status: 'matrices-matched', bones: expected.length };
}
