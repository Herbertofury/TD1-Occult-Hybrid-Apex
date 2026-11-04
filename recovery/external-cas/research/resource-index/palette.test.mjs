// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parsePalette, mapPaletteWeights } from './palette.mjs';

const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
function fixture() { return Buffer.concat([u32(1), u32(0), u32(1), Buffer.alloc(8), u32(0), u32(2), u32(0x12345678), u32(0x87654321), u32(0)]); }
test('version 12 palette retains bone hashes and bounded stitch counts', () => {
  const raw = fixture(), palette = parsePalette(raw, 0, raw.length, raw.length - 4, 12);
  assert.deepEqual(palette.hashes, [0x12345678, 0x87654321]);
  assert.equal(palette.uvStitches, 1);
  assert.equal(palette.slotIntersections, 0);
  assert.equal(parsePalette(raw, 0, raw.length, raw.length - 4, 13).status, 'unsupported-version');
});
test('palette rejects malformed counts, extents and unexplained data', () => {
  const raw = fixture();
  for (let i = 0; i < raw.length - 4; i++) assert.throws(() => parsePalette(raw.subarray(0, i), 0, i, i, 12));
  const malformed = Buffer.from(raw); malformed.writeUInt32LE(257, 24);
  assert.throws(() => parsePalette(malformed, 0, malformed.length, malformed.length - 4, 12), /count limit/);
  assert.throws(() => parsePalette(raw, 0, raw.length, raw.length, 12), /layout/);
});
test('weighted vertices map to explicit hashes without choosing a skeleton', () => {
  const raw = fixture(), palette = parsePalette(raw, 0, raw.length, raw.length - 4, 12);
  const geom = { status: 'geometry-candidate', palette, vertices: [{ joints: [1, 0, 255, 255], weights: [10, 245, 0, 0] }] };
  assert.deepEqual(mapPaletteWeights(geom), { status: 'mapped-candidate', vertices: [[
    { boneHash: 0x87654321, weightByte: 10 }, { boneHash: 0x12345678, weightByte: 245 },
  ]] });
  assert.throws(() => mapPaletteWeights({ ...geom, vertices: [{ joints: [2, 0, 0, 0], weights: [1, 0, 0, 0] }] }), /outside/);
  assert.throws(() => mapPaletteWeights({ ...geom, vertices: [{ joints: [0, 0, 0, 0], weights: [0, 0, 0, 0] }] }), /no weights/);
  assert.equal(mapPaletteWeights({ ...geom, vertices: [{ joints: null, weights: null }] }).status, 'missing-weights');
});
