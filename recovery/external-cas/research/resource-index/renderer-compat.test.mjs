// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { assessMesh, assessRgba, compareRigText, projectApxCandidate } from './renderer-compat.mjs';
import { computeBindMatrices, deriveSkinMatrices } from './rig.mjs';

function apxFixture() {
  const bones = Array.from({ length: 165 }, (_, i) => ({ hash: 1000 + i, parentIndex: i ? 0 : -1,
    position: [0, 0, 0], orientation: [0, 0, 0, 1], scale: [1, 1, 1] }));
  const rig = { status: 'rig-candidate', bones };
  const text = `165\n${bones.map(b => [b.hash, b.parentIndex, ...b.position, ...b.orientation, ...b.scale].join(' ')).join('\n')}\n`;
  const vertex = position => ({ position, normal: [0, 0, 1], uvs: [[0.25, 0.75]], joints: [0, 255, 1, 0], weights: [128, 0, 127, 0] });
  const geom = { status: 'geometry-candidate', palette: { status: 'palette-candidate', hashes: [1003, 1012] },
    vertices: [vertex([0, 0, 0]), vertex([1, 0, 0]), vertex([0, 1, 0])], indices: [0, 1, 2] };
  return { geom, rig, text };
}

test('compatibility reports zero-weight invalid palette lanes without mapping them', () => {
  const rig = { status: 'rig-candidate', bones: [{ hash: 42 }] };
  const geom = { status: 'geometry-candidate', palette: { status: 'palette-candidate', hashes: [42] },
    vertices: [{ joints: [0, 255, 0, 0], weights: [200, 0, 0, 0] }] };
  const result = assessMesh(geom, rig, 1);
  assert.equal(result.status, 'compatible-shape-candidate'); assert.equal(result.badZeroLane, 1);
  assert.equal(result.minWeightSum, 200); assert.equal(result.exact255, 0);
  assert.equal(assessMesh(geom, rig).status, 'unsupported-bone-count');
  geom.vertices[0].weights[1] = 1; assert.equal(assessMesh(geom, rig).status, 'invalid-weights');
  rig.bones[0].hash = 7; assert.equal(assessMesh(geom, rig).status, 'unresolved-palette');
});
test('rig text must match ordered hashes, parents and raw float32 fields', () => {
  const rig = { status: 'rig-candidate', bones: [
    { hash: 2, parentIndex: -1, position: [0, 0, 0], orientation: [0, 0, 0, 1], scale: [1, 1, 1] },
    { hash: 4, parentIndex: 0, position: [1, 2, 3], orientation: [0, 0, 0, 1], scale: [1, 1, 1] },
  ] };
  const text = '2\n2 -1 0 0 0 0 0 0 1 1 1 1\n4 0 1 2 3 0 0 0 1 1 1 1\n';
  assert.equal(compareRigText(rig, text, 2).status, 'float32-fields-match');
  assert.equal(compareRigText(rig, text.replace('4 0 1', '4 0 2'), 2).status, 'binary-text-mismatch');
  assert.equal(compareRigText(rig, text.replace('4 0 1', '2 0 1'), 2).status, 'invalid-text');
  assert.equal(compareRigText(rig, text).status, 'unsupported-bone-count');
});
test('APXMESH projection requires matching rig text and maps weighted palette lanes', () => {
  const { geom, rig, text } = apxFixture(), projected = projectApxCandidate(geom, rig, text);
  assert.equal(projected.status, 'apxmesh-candidate');
  assert.equal(projected.bytes.toString('ascii', 0, 8), 'APXMESH1');
  assert.equal(projected.bytes.length, 16 + 3 * 56 + 3 * 4);
  assert.deepEqual([0, 1, 2, 3].map(i => projected.bytes.readUInt16LE(48 + i * 2)), [3, 0, 12, 0]);
  assert.ok(Math.abs(projected.bytes.readFloatLE(56) - 128 / 255) < 1e-7);
  assert.equal(projectApxCandidate(geom, rig, text.replace('1003 0', '1003 -1')).status, 'rig-pair-unverified');
  geom.vertices[0].joints[0] = 255; assert.throws(() => projectApxCandidate(geom, rig, text), /outside palette/);
});
test('APXMESH candidate passes the renderer mesh validator', { skip: !process.env.APX_VALIDATOR_BIN }, () => {
  const { geom, rig, text } = apxFixture(), projected = projectApxCandidate(geom, rig, text);
  const result = execFileSync(process.env.APX_VALIDATOR_BIN, [], { input: projected.bytes, encoding: 'utf8', maxBuffer: 1024 });
  assert.equal(result.trim(), 'accepted 3 3');
});
test('APXMESH candidate survives renderer identity skinning', { skip: !process.env.APX_SKIN_VALIDATOR_BIN }, () => {
  const { geom, rig, text } = apxFixture(), projected = projectApxCandidate(geom, rig, text);
  const header = Buffer.alloc(4); header.writeUInt32LE(projected.bytes.length);
  const bind = computeBindMatrices(rig), skin = deriveSkinMatrices(bind, bind.global);
  assert.equal(skin.status, 'skin-matrices-candidate');
  const matrix = Buffer.alloc(165 * 48);
  skin.matrices.forEach((values, i) => values.forEach((value, j) => matrix.writeFloatLE(value, i * 48 + j * 4)));
  const output = execFileSync(process.env.APX_SKIN_VALIDATOR_BIN, [], { input: Buffer.concat([header, projected.bytes, matrix]), encoding: 'utf8', maxBuffer: 1024 });
  assert.equal(output.trim(), 'accepted 3 0 0');
});
test('RGBA evidence distinguishes alpha classes without assigning material semantics', () => {
  const r = assessRgba(3, 1, Buffer.from([10, 0, 0, 0, 128, 4, 2, 127, 8, 9, 10, 255]));
  assert.deepEqual([r.transparent, r.partial, r.opaque, r.transparentNonzeroRgb, r.channelAboveAlpha], [1, 1, 1, 1, 2]);
  assert.equal(r.opaqueTextureAccepted, false); assert.equal(r.transferFunction, 'unresolved');
  assert.throws(() => assessRgba(2, 1, Buffer.alloc(4)), /extent/);
});
