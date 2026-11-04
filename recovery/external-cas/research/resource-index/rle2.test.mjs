// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { decodeRle2, decodeRles, decodeBc3 } from './rle2.mjs';
import { compareRleReference } from './rle-reference.mjs';

function fixture(op = 2) {
  const header = Buffer.alloc(36); header.write('DXT5'); header.write('RLE2', 4);
  header.writeUInt16LE(4, 8); header.writeUInt16LE(4, 10); header.writeUInt16LE(1, 12);
  const color = op === 0 ? Buffer.alloc(0) : Buffer.from([0x00, 0xf8, 0, 0]);
  const colorIndices = op === 0 ? Buffer.alloc(0) : Buffer.alloc(4);
  const alphaEndpoints = op === 1 ? Buffer.from([255, 0]) : Buffer.alloc(0);
  const alphaIndices = op === 1 ? Buffer.alloc(6) : Buffer.alloc(0);
  const offsets = [36, 38, 38 + color.length, 38 + color.length + colorIndices.length,
    38 + color.length + colorIndices.length + alphaEndpoints.length];
  offsets.forEach((value, i) => header.writeUInt32LE(value, 16 + i * 4));
  const command = Buffer.alloc(2); command.writeUInt16LE(4 | op);
  return Buffer.concat([header, command, color, colorIndices, alphaEndpoints, alphaIndices]);
}
function rlesFixture(op = 2) {
  const old = fixture(op), header = Buffer.alloc(40);
  old.copy(header, 0, 0, 36); header.write('RLES', 4);
  for (let i = 0; i < 5; i++) header.writeUInt32LE(old.readUInt32LE(16 + i * 4) + 4, 16 + i * 4);
  header.writeUInt32LE(old.length + 4, 36);
  return Buffer.concat([header, old.subarray(36), Buffer.from([7, 8, 9])]);
}
test('RLES retains its uninterpreted stream while producing candidate BC3', () => {
  for (const op of [0, 1, 2]) {
    const decoded = decodeRles(rlesFixture(op));
    assert.equal(decoded.status, 'decoded-bc3-with-uninterpreted-stream');
    assert.deepEqual(decoded.mips[0].bc3, decodeRle2(fixture(op)).mips[0].bc3);
    assert.deepEqual(decoded.mips[0].uninterpretedStreams.map(stream => [...stream]), [[], [], [7, 8, 9]]);
  }
  const bad = rlesFixture(); bad.writeUInt32LE(bad.length + 1, 36);
  assert.throws(() => decodeRles(bad), /extent/);
  const original = rlesFixture(), extraAt = original.readUInt32LE(36);
  const extra = Buffer.concat([original.subarray(0, extraAt), Buffer.from([1, 2, 3, 4, 5, 6, 7, 8]), original.subarray(extraAt)]);
  extra.writeUInt32LE(extraAt + 2, 32); extra.writeUInt32LE(extraAt + 8, 36);
  assert.deepEqual(decodeRles(extra).mips[0].uninterpretedStreams.map(stream => [...stream]), [[1, 2], [3, 4, 5, 6, 7, 8], [7, 8, 9]]);
});
test('RLE2 decodes opaque, translucent and transparent BC3 blocks', () => {
  for (const op of [0, 1, 2]) {
    const decoded = decodeRle2(fixture(op));
    assert.equal(decoded.status, 'decoded-bc3');
    const pixels = decodeBc3(4, 4, decoded.mips[0].bc3);
    assert.equal(pixels.length, 64);
    if (op === 0) assert.equal(pixels[3], 0); // Hidden RGB is preserved, not assumed black.
    else assert.deepEqual([...pixels.subarray(0, 4)], [255, 0, 0, 255]);
  }
});
test('RLE2 and BC3 reject unsupported, truncated, inconsistent and excessive input', () => {
  const bytes = fixture();
  for (let n = 0; n < bytes.length; n++) assert.throws(() => decodeRle2(bytes.subarray(0, n)));
  const unknown = Buffer.from(bytes); unknown.write('RLES', 4);
  assert.equal(decodeRle2(unknown).status, 'unsupported-format');
  const badOp = Buffer.from(bytes); badOp.writeUInt16LE(7, 36);
  assert.throws(() => decodeRle2(badOp), /command/);
  const badCount = Buffer.from(bytes); badCount.writeUInt16LE(10, 36);
  assert.throws(() => decodeRle2(badCount), /command/);
  assert.throws(() => decodeBc3(4, 4, Buffer.alloc(15)), /extent/);
  assert.throws(() => decodeBc3(0, 4, Buffer.alloc(0)), /input/);
});
test('synthetic RLE2 blocks and pixels match independent readers', {
  skip: !(process.env.RLE_ORACLE_PYTHON && process.env.RLE_ORACLE_SOURCE && process.env.PILLOW_ORACLE_ROOT),
}, () => {
  for (const op of [0, 1, 2]) assert.deepEqual(
    compareRleReference(fixture(op), process.env.RLE_ORACLE_PYTHON, process.env.RLE_ORACLE_SOURCE, process.env.PILLOW_ORACLE_ROOT),
    { width: 4, height: 4, mipCount: 1 });
  for (const op of [0, 1, 2]) assert.deepEqual(
    compareRleReference(rlesFixture(op), process.env.RLE_ORACLE_PYTHON, process.env.RLE_ORACLE_SOURCE, process.env.PILLOW_ORACLE_ROOT),
    { width: 4, height: 4, mipCount: 1 });
});
