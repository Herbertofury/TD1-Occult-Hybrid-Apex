// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseGeom } from './geom.mjs';
import { compareGeomReference } from './geom-reference.mjs';

const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
const u16 = n => { const b = Buffer.alloc(2); b.writeUInt16LE(n); return b; };
const f32 = n => { const b = Buffer.alloc(4); b.writeFloatLE(n); return b; };
const element = (usage, subtype, size) => Buffer.concat([u32(usage), u32(subtype), Buffer.from([size])]);
function fixture() {
  const vertices = [[0, 0, 0, 0, 0, 1, 0, 0], [1, 0, 0, 0, 0, 1, 1, 0], [0, 1, 0, 0, 0, 1, 0, 1]];
  const chunk = Buffer.concat([Buffer.from('GEOM'), u32(12), u32(0), u32(4), u32(0), u32(0), u32(0), u32(3), u32(3),
    element(1, 1, 12), element(2, 1, 12), element(3, 1, 8), ...vertices.flat().map(f32),
    u32(1), Buffer.from([2]), u32(3), u16(0), u16(1), u16(2), u32(0), u32(0), u32(0), u32(0), u32(0)]);
  chunk.writeUInt32LE(chunk.length - 16, 8);
  return Buffer.concat([u32(3), u32(0), u32(0), u32(0), u32(1), Buffer.alloc(16), u32(44), u32(chunk.length), chunk]);
}
test('GEOM candidate retains positions, normals, UVs and triangle indices', () => {
  const geom = parseGeom(fixture());
  assert.equal(geom.status, 'geometry-candidate');
  assert.equal(geom.version, 12);
  assert.equal(geom.vertices.length, 3);
  assert.deepEqual(geom.vertices[1].position, [1, 0, 0]);
  assert.deepEqual(geom.vertices[2].uvs[0], [0, 1]);
  assert.deepEqual(geom.indices, [0, 1, 2]);
  assert.ok(geom.limitations.includes('rig-palette-unparsed'));
});
test('GEOM refuses truncation, impossible extents, invalid values and indices', () => {
  const bytes = fixture();
  for (let n = 0; n < bytes.length; n++) assert.throws(() => parseGeom(bytes.subarray(0, n)));
  const badChunk = Buffer.from(bytes); badChunk.writeUInt32LE(0xffffffff, 40);
  assert.throws(() => parseGeom(badChunk), /extent/);
  const badVertex = Buffer.from(bytes); badVertex.writeFloatLE(NaN, 44 + 36 + 27);
  assert.throws(() => parseGeom(badVertex), /numeric/);
  const badIndex = Buffer.from(bytes); badIndex.writeUInt16LE(3, 44 + 36 + 27 + 96 + 9);
  assert.throws(() => parseGeom(badIndex), /outside/);
});
test('GEOM reports unsupported versions and missing essential vertex formats', () => {
  const bytes = fixture();
  const future = Buffer.from(bytes); future.writeUInt32LE(99, 48);
  assert.equal(parseGeom(future).status, 'unsupported-version');
  const unknown = Buffer.from(bytes); unknown.writeUInt32LE(20, 44 + 36);
  assert.equal(parseGeom(unknown).status, 'unsupported-vertex-layout');
});
test('synthetic geometry agrees with independent Blender GEOM reader', { skip: !(process.env.GEOM_ORACLE_PYTHON && process.env.GEOM_ORACLE_ROOT) }, () => {
  assert.deepEqual(compareGeomReference(fixture(), process.env.GEOM_ORACLE_PYTHON, process.env.GEOM_ORACLE_ROOT), { version: 12, vertices: 3, triangles: 1, materialMatched: null });
});
