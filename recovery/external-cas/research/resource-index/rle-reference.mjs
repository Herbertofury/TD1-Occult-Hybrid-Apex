// SPDX-License-Identifier: GPL-3.0-or-later
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { decodeRle2, decodeRles, decodeBc3 } from './rle2.mjs';

const hash = bytes => createHash('sha256').update(bytes).digest('hex');
export function compareRleReference(payload, python, referenceSource, pillowPath) {
  const texture = payload.toString('ascii', 4, 8) === 'RLES' ? decodeRles(payload) : decodeRle2(payload);
  if (!['decoded-bc3', 'decoded-bc3-with-uninterpreted-stream'].includes(texture.status)) throw new Error('unsupported texture');
  const rgba = decodeBc3(texture.width, texture.height, texture.mips[0].bc3);
  const bridge = fileURLToPath(new URL('./rle_oracle.py', import.meta.url));
  const oracle = JSON.parse(execFileSync(python, ['-B', bridge, referenceSource, pillowPath], {
    input: payload, encoding: 'utf8', maxBuffer: 1024, stdio: ['pipe', 'pipe', 'pipe'],
  }));
  if (oracle.width !== texture.width || oracle.height !== texture.height || oracle.bc3Hash !== hash(texture.mips[0].bc3)) throw new Error('RLE block disagreement');
  if (oracle.rgbaHash !== hash(rgba)) throw new Error('BC3 pixel disagreement');
  return { width: texture.width, height: texture.height, mipCount: texture.mipCount };
}
