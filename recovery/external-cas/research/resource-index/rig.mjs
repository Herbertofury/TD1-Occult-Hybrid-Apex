// SPDX-License-Identifier: GPL-3.0-or-later
// Candidate RIG reader based on C. Marinetti's GPL TS4CAS Tools RIG.cs.
// Does not choose a skeleton or apply animation.
import { mapPaletteWeights } from './palette.mjs';
export function parseRig(data) {
  if (!Buffer.isBuffer(data) || data.length > 16 * 1024 * 1024) throw new Error('invalid rig input');
  let at = 0;
  function take(n) { if (!Number.isSafeInteger(n) || n < 0 || at + n > data.length) throw new Error('truncated rig'); const p = at; at += n; return p; }
  function u32() { return data.readUInt32LE(take(4)); }
  function i32() { return data.readInt32LE(take(4)); }
  function floats(n) { return Array.from({ length: n }, () => { const f = data.readFloatLE(take(4)); if (!Number.isFinite(f)) throw new Error('invalid rig float'); return f; }); }
  const version = u32(), minorVersion = u32();
  if (version !== 3 || minorVersion !== 1) return { status: 'unsupported-version', version, minorVersion };
  const count = u32(); if (!count || count > 4096) throw new Error('rig bone count');
  const bones = [];
  for (let i = 0; i < count; i++) {
    const position = floats(3), orientation = floats(4), scale = floats(3), length = i32();
    if (length < 0 || length > 1024) throw new Error('rig name length');
    const raw = data.subarray(take(length), at);
    if ([...raw].some(byte => byte < 32 || byte > 126)) throw new Error('unsupported rig name encoding');
    const name = raw.toString('ascii'), opposingIndex = i32(), parentIndex = i32(), hash = u32(), flags = u32();
    if (opposingIndex < 0 || opposingIndex >= count || parentIndex < -1 || parentIndex >= i) throw new Error('unsupported rig hierarchy');
    bones.push({ name, opposingIndex, parentIndex, hash, flags, position, orientation, scale });
  }
  const chainCount = u32(); if (chainCount > 4096) throw new Error('rig chain count');
  const chains = [];
  for (let i = 0; i < chainCount; i++) {
    const n = u32(); if (n > count) throw new Error('rig chain length');
    const indices = Array.from({ length: n }, i32), pole = i32(), slot = i32(), root = i32();
    if ([...indices, pole, slot, root].some(v => v < -1 || v >= count)) throw new Error('rig chain index');
    chains.push({ indices, pole, slot, root });
  }
  if (at !== data.length) return { status: 'unsupported-trailing-data', version, minorVersion, bones, chains, trailingBytes: data.length - at };
  return { status: 'rig-candidate', version, minorVersion, bones, chains };
}

// Map exact palette hashes to all matches, preserving missing and duplicate hashes.
export function bindPalette(palette, rig) {
  if (palette?.status !== 'palette-candidate' || rig?.status !== 'rig-candidate') return { status: 'unavailable-input' };
  const entries = palette.hashes.map(hash => {
    const indices = [];
    rig.bones.forEach((bone, i) => { if (bone.hash === hash) indices.push(i); });
    return { hash, status: indices.length === 0 ? 'missing' : indices.length === 1 ? 'unique' : 'ambiguous', indices };
  });
  return { status: entries.every(e => e.status === 'unique') ? 'bound-candidate' : 'unresolved', entries };
}

// Connect raw vertex influences to an explicitly supplied rig; never normalize.
export function bindVertexWeights(geom, rig) {
  const weights = mapPaletteWeights(geom);
  if (weights.status !== 'mapped-candidate') return { status: weights.status };
  const binding = bindPalette(geom.palette, rig);
  if (binding.status !== 'bound-candidate') return { status: 'unresolved-palette', binding };
  const indices = new Map(binding.entries.map(entry => [entry.hash, entry.indices[0]]));
  return { status: 'bound-weights-candidate', vertices: weights.vertices.map(vertex => vertex.map(influence => ({
    boneHash: influence.boneHash, boneIndex: indices.get(influence.boneHash), weightByte: influence.weightByte,
  }))) };
}

// Narrow transform candidate: unit scale and normalized (or empty) quaternions.
// Row-major matrices act on column vectors. No animation or renderer conversion.
export function computeBindMatrices(rig, { scaleTolerance = 0 } = {}) {
  if (rig?.status !== 'rig-candidate') return { status: 'unavailable-rig' };
  if (!Number.isFinite(scaleTolerance) || scaleTolerance < 0 || scaleTolerance > 1e-6) throw new Error('invalid scale tolerance');
  let maxScaleDeviation = 0;
  const local = [], global = [], inverse = [];
  const multiply = (a, b) => Array.from({ length: 16 }, (_, i) => {
    const r = Math.floor(i / 4), c = i % 4;
    return [0, 1, 2, 3].reduce((sum, k) => sum + a[r * 4 + k] * b[k * 4 + c], 0);
  });
  for (let index = 0; index < rig.bones.length; index++) {
    const bone = rig.bones[index];
    const deviation = Math.max(...bone.scale.map(v => Math.abs(v - 1)));
    maxScaleDeviation = Math.max(maxScaleDeviation, deviation);
    if (deviation > scaleTolerance) return { status: 'unsupported-scale', boneIndex: index };
    let [x, y, z, w] = bone.orientation;
    if (x === 0 && y === 0 && z === 0 && w === 0) w = 1;
    if (Math.abs(x*x + y*y + z*z + w*w - 1) > 1e-6) return { status: 'unsupported-quaternion', boneIndex: index };
    const [px, py, pz] = bone.position;
    const matrix = [1-2*y*y-2*z*z, 2*x*y-2*z*w, 2*x*z+2*y*w, px,
      2*x*y+2*z*w, 1-2*x*x-2*z*z, 2*y*z-2*x*w, py,
      2*x*z-2*y*w, 2*y*z+2*x*w, 1-2*x*x-2*y*y, pz, 0, 0, 0, 1];
    local.push(matrix);
    const world = bone.parentIndex < 0 ? matrix : multiply(global[bone.parentIndex], matrix);
    global.push(world);
    // Invert the affine 3x3 rather than assuming exact orthonormality.
    const [a,b,c,tx,d,e,f,ty,g,h,i,tz] = world;
    const det = a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
    if (!Number.isFinite(det) || Math.abs(det) < 1e-12) return { status: 'singular-transform', boneIndex: index };
    const r = [(e*i-f*h)/det, (c*h-b*i)/det, (b*f-c*e)/det,
      (f*g-d*i)/det, (a*i-c*g)/det, (c*d-a*f)/det,
      (d*h-e*g)/det, (b*g-a*h)/det, (a*e-b*d)/det];
    inverse.push([r[0],r[1],r[2],-(r[0]*tx+r[1]*ty+r[2]*tz),
      r[3],r[4],r[5],-(r[3]*tx+r[4]*ty+r[5]*tz),
      r[6],r[7],r[8],-(r[6]*tx+r[7]*ty+r[8]*tz),0,0,0,1]);
  }
  return { status: maxScaleDeviation ? 'bind-matrices-approximate-unit-scale' : 'bind-matrices-candidate',
    maxScaleDeviation, local, global, inverse };
}

// Renderer matrices are posed-global * inverse-bind, not the raw bind globals.
// Caller supplies pose globals in the same rig order and coordinate convention.
export function deriveSkinMatrices(bind, posedGlobals) {
  if (!['bind-matrices-candidate', 'bind-matrices-approximate-unit-scale'].includes(bind?.status) ||
      !Array.isArray(bind.inverse) || !Array.isArray(posedGlobals) || !bind.inverse.length ||
      bind.inverse.length > 256 || posedGlobals.length !== bind.inverse.length) return { status: 'unavailable-input' };
  const matrices = [];
  for (let i = 0; i < posedGlobals.length; i++) {
    const pose = posedGlobals[i], inv = bind.inverse[i];
    if (!Array.isArray(pose) || pose.length !== 16 || pose.some(v => !Number.isFinite(v)) ||
        !Array.isArray(inv) || inv.length !== 16 || inv.some(v => !Number.isFinite(v)) ||
        [12, 13, 14, 15].some((n, j) => pose[n] !== [0, 0, 0, 1][j])) return { status: 'invalid-matrix', boneIndex: i };
    const m = Array.from({ length: 12 }, (_, n) => {
      const row = Math.floor(n / 4), col = n % 4;
      return Math.fround([0, 1, 2, 3].reduce((sum, k) => sum + pose[row * 4 + k] * inv[k * 4 + col], 0));
    });
    if (m.some(v => !Number.isFinite(v))) return { status: 'invalid-matrix', boneIndex: i };
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
      let dot = 0; for (let k = 0; k < 3; k++) dot += m[r * 4 + k] * m[c * 4 + k];
      if (Math.abs(dot - (r === c ? 1 : 0)) > 1e-4) return { status: 'unsupported-nonrigid-pose', boneIndex: i };
    }
    const determinant = m[0]*(m[5]*m[10]-m[6]*m[9])-m[1]*(m[4]*m[10]-m[6]*m[8])+m[2]*(m[4]*m[9]-m[5]*m[8]);
    if (Math.abs(determinant - 1) > 1e-4) return { status: 'unsupported-nonrigid-pose', boneIndex: i };
    matrices.push(m);
  }
  return { status: bind.status === 'bind-matrices-candidate' ? 'skin-matrices-candidate' : 'skin-matrices-approximate', matrices };
}
