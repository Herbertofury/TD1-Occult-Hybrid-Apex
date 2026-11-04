// SPDX-License-Identifier: GPL-3.0-or-later
import { execFileSync } from 'node:child_process';
import { isDeepStrictEqual } from 'node:util';
import { parseRegionMap } from './region-map.mjs';

export function compareRegionReference(payload, dotnet, oracleDll) {
  const ours = parseRegionMap(payload);
  if (ours.status !== 'parsed-candidate') throw new Error('unsupported RMAP');
  const reference = JSON.parse(execFileSync(dotnet, [oracleDll, 'region'], {
    input: payload, encoding: 'utf8', maxBuffer: 1024 * 1024, stdio: ['pipe', 'pipe', 'pipe'],
  }));
  if (!isDeepStrictEqual(ours.blocks, reference)) throw new Error('RMAP block disagreement');
  return { blocks: ours.blocks.length, meshReferences: ours.blocks.reduce((n, block) => n + block.keys.length, 0) };
}
