// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseMaterial } from './material.mjs';

function fixture() {
  const data = Buffer.alloc(56); data.write('MTNF'); data.writeUInt32LE(8, 8); data.writeUInt32LE(2, 12);
  data.writeUInt32LE(0x6cc0fd85, 16); data.writeUInt32LE(4, 20); data.writeUInt32LE(4, 24); data.writeUInt32LE(48, 28);
  data.writeUInt32LE(0x1234, 32); data.writeUInt32LE(4, 36); data.writeUInt32LE(4, 40); data.writeUInt32LE(52, 44);
  data.writeUInt32LE(1, 48); data.writeUInt32LE(0, 52);
  return data;
}
test('material retains unknown entries and resolves only known texture-index candidates', () => {
  const result = parseMaterial(fixture(), ['first', 'second']);
  assert.equal(result.status, 'parsed-candidate');
  assert.equal(result.entries[0].role, 'diffuse');
  assert.equal(result.entries[0].status, 'candidate');
  assert.equal(result.entries[0].key, 'second');
  assert.equal(result.entries[1].status, 'opaque');
  assert.equal(result.entries[1].field, 0x1234);
});
test('material preserves missing reference indices and refuses malformed bounds', () => {
  assert.equal(parseMaterial(fixture(), []).entries[0].status, 'unresolved-index');
  const bad = fixture(); bad.writeUInt32LE(0xfffffff0, 28);
  assert.throws(() => parseMaterial(bad, []), /extent/);
  const unknown = fixture(); unknown.write('ABCD');
  assert.equal(parseMaterial(unknown, []).status, 'unsupported-material');
  const count = fixture(); count.writeUInt32LE(1025, 12);
  assert.throws(() => parseMaterial(count, []), /extent/);
});
