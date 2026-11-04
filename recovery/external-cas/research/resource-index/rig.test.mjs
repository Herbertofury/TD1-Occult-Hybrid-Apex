// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseRig, bindPalette, bindVertexWeights, computeBindMatrices, deriveSkinMatrices } from './rig.mjs';
import { compareRigReference, compareRigMatrices } from './rig-reference.mjs';

function fixture() {
  const parts = [];
  const u = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); parts.push(b); };
  const i = n => { const b = Buffer.alloc(4); b.writeInt32LE(n); parts.push(b); };
  const f = n => { const b = Buffer.alloc(4); b.writeFloatLE(n); parts.push(b); };
  u(3); u(1); u(2);
  for (let j = 0; j < 2; j++) {
    [j, 0, 0, 0, 0, j ? Math.SQRT1_2 : 0, j ? Math.SQRT1_2 : 1, 1, 1, 1].forEach(f);
    const name = Buffer.from(`bone${j}`); i(name.length); parts.push(name);
    i(j); i(j - 1); u(10 + j); u(0x23);
  }
  u(1); u(1); i(1); i(-1); i(-1); i(0);
  return Buffer.concat(parts);
}
test('bounded rig candidate retains hierarchy, raw transforms and chains', () => {
  const rig = parseRig(fixture());
  assert.equal(rig.status, 'rig-candidate'); assert.equal(rig.bones.length, 2);
  assert.equal(rig.bones[1].parentIndex, 0); assert.deepEqual(rig.bones[1].position, [1, 0, 0]);
  assert.deepEqual(rig.chains[0], { indices: [1], pole: -1, slot: -1, root: 0 });
});
test('rig rejects invalid hierarchy, bounds and data while preserving unsupported versions', () => {
  const data = fixture();
  for (let i = 0; i < data.length; i++) assert.throws(() => parseRig(data.subarray(0, i)));
  const version = Buffer.from(data); version.writeUInt32LE(4); assert.equal(parseRig(version).status, 'unsupported-version');
  const trailing = Buffer.concat([data, Buffer.from([1])]); assert.equal(parseRig(trailing).status, 'unsupported-trailing-data');
  const parent = Buffer.from(data); parent.writeInt32LE(0, 12 + 40 + 4 + 5 + 4); assert.throws(() => parseRig(parent), /hierarchy/);
});
test('palette binding retains missing and duplicate bone hashes without choosing a rig', () => {
  const rig = parseRig(fixture()), palette = { status: 'palette-candidate', hashes: [10, 11, 12] };
  assert.deepEqual(bindPalette(palette, rig).entries.map(e => e.status), ['unique', 'unique', 'missing']);
  rig.bones[1].hash = 10;
  assert.deepEqual(bindPalette(palette, rig).entries.map(e => e.status), ['ambiguous', 'missing', 'missing']);
});
test('vertex weights bind only to uniquely mapped bones and retain raw bytes', () => {
  const rig = parseRig(fixture()), geom = { status: 'geometry-candidate', palette: { status: 'palette-candidate', hashes: [11, 10] },
    vertices: [{ joints: [0, 1, 0, 0], weights: [100, 155, 0, 0] }] };
  const bound = bindVertexWeights(geom, rig);
  assert.equal(bound.status, 'bound-weights-candidate');
  assert.deepEqual(bound.vertices[0], [{ boneHash: 11, boneIndex: 1, weightByte: 100 }, { boneHash: 10, boneIndex: 0, weightByte: 155 }]);
  rig.bones[1].hash = 10;
  assert.equal(bindVertexWeights(geom, rig).status, 'unresolved-palette');
});
test('unit-scale bind matrices preserve hierarchy and have inverse transforms', () => {
  const rig = parseRig(fixture()), matrices = computeBindMatrices(rig);
  assert.equal(matrices.status, 'bind-matrices-candidate');
  assert.equal(matrices.global[1][3], 1);
  const m = matrices.global[1], inv = matrices.inverse[1];
  for (let row = 0; row < 4; row++) for (let col = 0; col < 4; col++) {
    let value = 0; for (let k = 0; k < 4; k++) value += m[row * 4 + k] * inv[k * 4 + col];
    assert.ok(Math.abs(value - (row === col ? 1 : 0)) < 1e-10);
  }
  rig.bones[1].scale[0] = 2; assert.equal(computeBindMatrices(rig).status, 'unsupported-scale');
  rig.bones[1].scale[0] = 1 + 5e-7;
  assert.equal(computeBindMatrices(rig).status, 'unsupported-scale');
  assert.equal(computeBindMatrices(rig, { scaleTolerance: 1e-6 }).status, 'bind-matrices-approximate-unit-scale');
  assert.throws(() => computeBindMatrices(rig, { scaleTolerance: 1e-5 }), /tolerance/);
  rig.bones[1].scale[0] = 1; rig.bones[1].orientation = [1, 0, 0, 1];
  assert.equal(computeBindMatrices(rig).status, 'unsupported-quaternion');
});
test('renderer skin matrices multiply posed globals by inverse bind and reject scale', () => {
  const bind = computeBindMatrices(parseRig(fixture()));
  const rest = deriveSkinMatrices(bind, bind.global);
  assert.equal(rest.status, 'skin-matrices-candidate');
  for (const matrix of rest.matrices) for (let i = 0; i < 12; i++) assert.ok(Math.abs(matrix[i] - (i === 0 || i === 5 || i === 10 ? 1 : 0)) < 1e-6);
  const pose = bind.global.map(matrix => [...matrix]); pose[1][3] += 2;
  assert.ok(Math.abs(deriveSkinMatrices(bind, pose).matrices[1][3] - 2) < 1e-6);
  pose[1][0] *= 2; pose[1][4] *= 2; pose[1][8] *= 2;
  assert.equal(deriveSkinMatrices(bind, pose).status, 'unsupported-nonrigid-pose');
  assert.equal(deriveSkinMatrices(bind, []).status, 'unavailable-input');
});
test('synthetic rig matches TS4CAS Tools reader', { skip: !(process.env.CASP_ORACLE_DLL && process.env.DOTNET_BIN) }, () => {
  assert.deepEqual(compareRigReference(fixture(), process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL), { status: 'reader-matched', bones: 2, chains: 1 });
  assert.deepEqual(compareRigMatrices(fixture(), process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL), { status: 'matrices-matched', bones: 2 });
});
