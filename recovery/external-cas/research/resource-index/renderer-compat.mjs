// SPDX-License-Identifier: GPL-3.0-or-later
// Aggregate compatibility diagnostics; not an authorization to choose a rig.
import { bindPalette } from './rig.mjs';

export function assessMesh(geom, rig, expectedBones = 165) {
  if (geom?.status !== 'geometry-candidate' || rig?.status !== 'rig-candidate') return { status: 'unavailable-input' };
  const binding = bindPalette(geom.palette, rig);
  if (binding.status !== 'bound-candidate') return { status: 'unresolved-palette', bindingStatus: binding.status };
  let minWeightSum = Infinity, maxWeightSum = 0, exact255 = 0, zeroLanes = 0, badZeroLane = 0, invalid = 0;
  for (const v of geom.vertices) {
    if (!v.joints || !v.weights || v.joints.length !== 4 || v.weights.length !== 4) { invalid++; continue; }
    const sum = v.weights.reduce((a, b) => a + b, 0); minWeightSum = Math.min(minWeightSum, sum); maxWeightSum = Math.max(maxWeightSum, sum);
    if (sum === 255) exact255++;
    if (!sum) invalid++;
    for (let i = 0; i < 4; i++) {
      if (!v.weights[i]) { zeroLanes++; if (v.joints[i] >= geom.palette.hashes.length) badZeroLane++; }
      else if (v.joints[i] >= geom.palette.hashes.length) invalid++;
    }
  }
  return { status: invalid ? 'invalid-weights' : rig.bones.length === expectedBones ? 'compatible-shape-candidate' : 'unsupported-bone-count',
    vertices: geom.vertices.length, bones: rig.bones.length, paletteEntries: binding.entries.length,
    minWeightSum: Number.isFinite(minWeightSum) ? minWeightSum : null, maxWeightSum, exact255, zeroLanes, badZeroLane, invalid,
    nonUnitScaleBones: rig.bones.filter(b => b.scale?.some(value => value !== 1)).length,
    maxScaleDeviation: Math.max(0, ...rig.bones.flatMap(b => (b.scale ?? []).map(value => Math.abs(value - 1)))) };
}

export function assessRgba(width, height, pixels) {
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1 || width * height > 16 * 1024 * 1024 ||
      !Buffer.isBuffer(pixels) || pixels.length !== width * height * 4) throw new Error('invalid RGBA extent');
  let transparent = 0, partial = 0, opaque = 0, transparentNonzeroRgb = 0, channelAboveAlpha = 0;
  for (let p = 0; p < pixels.length; p += 4) {
    const a = pixels[p + 3];
    if (!a) { transparent++; if (pixels[p] || pixels[p+1] || pixels[p+2]) transparentNonzeroRgb++; }
    else if (a === 255) opaque++; else partial++;
    if (pixels[p] > a || pixels[p+1] > a || pixels[p+2] > a) channelAboveAlpha++;
  }
  // Evidence only: no alpha association, shader role or transfer function inferred.
  return { pixels: width * height, transparent, partial, opaque, transparentNonzeroRgb, channelAboveAlpha,
    opaqueTextureAccepted: transparent === 0 && partial === 0, alphaAssociation: 'unresolved', transferFunction: 'unresolved' };
}

// Compare sampler text to a caller-supplied parsed binary rig in exact order.
// This does not authenticate either source or prove that the game selects it.
export function compareRigText(rig, text, expectedBones = 165) {
  if (rig?.status !== 'rig-candidate' || !Number.isSafeInteger(expectedBones) || expectedBones < 1 || expectedBones > 4096 ||
      typeof text !== 'string' || text.length > 1024 * 1024) return { status: 'invalid-input' };
  const lines = text.trim().split(/\r?\n/);
  if (lines.length !== expectedBones + 1 || lines[0].trim() !== String(expectedBones) || rig.bones.length !== expectedBones)
    return { status: 'unsupported-bone-count' };
  const hashes = new Set(); let nonUnitScaleBones = 0;
  const number = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
  for (let index = 0; index < expectedBones; index++) {
    const tokens = lines[index + 1].trim().split(/\s+/);
    if (tokens.length !== 12 || tokens.some(t => !number.test(t))) return { status: 'invalid-text', boneIndex: index };
    const [hash, parent, ...values] = tokens.map(Number), bone = rig.bones[index];
    if (!Number.isSafeInteger(hash) || hash < 0 || hash > 0xffffffff || hashes.has(hash) || !Number.isSafeInteger(parent) || parent < -1 || parent >= index || values.some(v => !Number.isFinite(v)))
      return { status: 'invalid-text', boneIndex: index };
    hashes.add(hash);
    const raw = [...bone.position, ...bone.orientation, ...bone.scale];
    if (hash !== bone.hash || parent !== bone.parentIndex || raw.some((value, i) => !Object.is(value, Math.fround(values[i]))))
      return { status: 'binary-text-mismatch', boneIndex: index };
    if (bone.scale.some(v => Math.abs(v - 1) >= 1e-6)) nonUnitScaleBones++;
  }
  return { status: nonUnitScaleBones ? 'unsupported-renderer-scale' : 'float32-fields-match', bones: expectedBones, nonUnitScaleBones };
}

// Produces an in-memory APXMESH1 diagnostic only when the supplied ordered rig
// and text have matching float32 fields. The caller must authenticate sources.
export function projectApxCandidate(geom, rig, rigText) {
  const rigCheck = compareRigText(rig, rigText);
  if (rigCheck.status !== 'float32-fields-match') return { status: 'rig-pair-unverified', rigStatus: rigCheck.status };
  const binding = bindPalette(geom?.palette, rig);
  if (geom?.status !== 'geometry-candidate' || binding.status !== 'bound-candidate') return { status: 'unresolved-geometry-or-palette' };
  const vertices = geom.vertices, indices = geom.indices;
  if (!Array.isArray(vertices) || !vertices.length || vertices.length > 1000000 || !Array.isArray(indices) || !indices.length ||
      indices.length > 6000000 || indices.length % 3 || 16 + vertices.length * 56 + indices.length * 4 > 32 * 1024 * 1024)
    throw new Error('mesh extent');
  const raw = Buffer.alloc(16 + vertices.length * 56 + indices.length * 4);
  raw.write('APXMESH1'); raw.writeUInt32LE(vertices.length, 8); raw.writeUInt32LE(indices.length, 12);
  for (let n = 0; n < vertices.length; n++) {
    const v = vertices[n], fields = [v.position, v.normal, v.uvs?.[0], v.joints, v.weights];
    if (fields.some(value => !Array.isArray(value)) || fields.some((value, i) => value.length !== [3, 3, 2, 4, 4][i])) throw new Error('vertex layout');
    const floats = [...v.position, ...v.normal, ...v.uvs[0]];
    if (floats.some(value => !Number.isFinite(value) || !Number.isFinite(Math.fround(value))) || v.position.some(value => Math.abs(value) > 100) || v.uvs[0].some(value => Math.abs(value) > 100)) throw new Error('vertex bounds');
    if (v.weights.some(value => !Number.isInteger(value) || value < 0 || value > 255)) throw new Error('invalid weight');
    const total = v.weights.reduce((a, b) => a + b, 0); if (!total) throw new Error('zero weights');
    const at = 16 + n * 56;
    floats.forEach((value, i) => raw.writeFloatLE(value, at + i * 4));
    for (let i = 0; i < 4; i++) {
      const p = v.joints[i];
      if (!Number.isInteger(p) || p < 0 || p > 255) throw new Error('invalid joint');
      if (v.weights[i] && p >= binding.entries.length) throw new Error('weighted joint outside palette');
      const joint = v.weights[i] ? binding.entries[p].indices[0] : 0;
      raw.writeUInt16LE(joint, at + 32 + i * 2);
      raw.writeFloatLE(v.weights[i] / total, at + 40 + i * 4);
    }
  }
  const firstIndex = 16 + vertices.length * 56;
  indices.forEach((value, n) => {
    if (!Number.isSafeInteger(value) || value < 0 || value >= vertices.length) throw new Error('mesh index');
    raw.writeUInt32LE(value, firstIndex + n * 4);
  });
  return { status: 'apxmesh-candidate', bytes: raw, provenance: 'caller-must-verify', nativeFidelity: 'unverified' };
}
