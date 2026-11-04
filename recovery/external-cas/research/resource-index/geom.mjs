// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded RCOL/GEOM vertex and index extraction; skin and material remain unqualified.
import { tgi } from './dbpf.mjs';
import { parseMaterial } from './material.mjs';
export function parseGeom(data) {
  if (!Buffer.isBuffer(data) || data.length < 60 || data.length > 32 * 1024 * 1024) throw new Error('invalid GEOM extent');
  let at = 0, limit = data.length;
  function take(n) { if (!Number.isSafeInteger(n) || n < 0 || at + n > limit) throw new Error('truncated GEOM'); const p = at; at += n; return p; }
  const u8 = () => data.readUInt8(take(1));
  const u16 = () => data.readUInt16LE(take(2));
  const u32 = () => data.readUInt32LE(take(4));
  const bytes4 = () => { const start = take(4); return Array.from(data.subarray(start, start + 4)); };
  const f32 = () => { const f = data.readFloatLE(take(4)); if (!Number.isFinite(f)) throw new Error('invalid GEOM numeric value'); return f; };
  const wrapperVersion = u32();
  if (wrapperVersion !== 3) return { status: 'unsupported-wrapper', wrapperVersion };
  take(8);
  const externalCount = u32(), internalCount = u32();
  if (externalCount > 128 || internalCount !== 1) return { status: 'unsupported-chunk-layout', wrapperVersion };
  take((externalCount + internalCount) * 16);
  const chunkOffset = u32(), chunkSize = u32();
  if (chunkOffset !== at || chunkSize < 24 || chunkOffset + chunkSize > data.length) throw new Error('invalid GEOM chunk extent');
  limit = chunkOffset + chunkSize;
  if (data.toString('ascii', take(4), at) !== 'GEOM') throw new Error('invalid GEOM magic');
  const version = u32();
  if (version < 12 || version > 15) return { status: 'unsupported-version', wrapperVersion, version };
  const tgiFieldOffset = at, tgiOffset = u32(), tgiSize = u32(), shader = u32();
  let materialBytes = 0, materialAt = null;
  if (shader !== 0) { materialBytes = u32(); materialAt = take(materialBytes); }
  const mergeGroup = u32(), sortOrder = u32(), vertexCount = u32(), formatCount = u32();
  if (!vertexCount || vertexCount > 250000 || !formatCount || formatCount > 32) throw new Error('GEOM count limit');
  let stride = 0;
  const formats = [];
  for (let i = 0; i < formatCount; i++) {
    const usage = u32(), subtype = u32(), size = u8();
    if (!size) throw new Error('invalid GEOM format');
    stride += size;
    if (stride > 256) throw new Error('GEOM stride limit');
    formats.push({ usage, subtype, size });
  }
  const fields = formats.map(format => format.usage);
  if (fields.filter(value => value === 1).length !== 1 || fields.filter(value => value === 2).length !== 1 ||
      fields.filter(value => value === 3).length < 1 || fields.filter(value => value === 4).length > 1 ||
      fields.filter(value => value === 5).length > 1) return { status: 'unsupported-vertex-layout', wrapperVersion, version, formats };
  for (const format of formats) {
    if ((format.usage === 1 || format.usage === 2 || format.usage === 6) && format.size !== 12 ||
        format.usage === 3 && format.size !== 8 || (format.usage === 4 || format.usage === 5 || format.usage === 7 || format.usage === 10) && format.size !== 4 ||
        format.usage === 5 && format.subtype !== 2)
      return { status: 'unsupported-vertex-layout', wrapperVersion, version, formats };
  }
  if (vertexCount * stride > limit - at) throw new Error('truncated GEOM vertices');
  const vertices = [];
  for (let i = 0; i < vertexCount; i++) {
    const vertex = { position: null, normal: null, uvs: [], joints: null, weights: null };
    for (const format of formats) {
      if (format.usage === 1) vertex.position = [f32(), f32(), f32()];
      else if (format.usage === 2) vertex.normal = [f32(), f32(), f32()];
      else if (format.usage === 3) vertex.uvs.push([f32(), f32()]);
      else if (format.usage === 4) vertex.joints = bytes4();
      else if (format.usage === 5) vertex.weights = bytes4();
      else take(format.size);
    }
    vertices.push(vertex);
  }
  const groups = u32(), indexSize = u8(), indexCount = u32();
  if (groups !== 1 || ![2, 4].includes(indexSize)) return { status: 'unsupported-index-layout', wrapperVersion, version };
  if (!indexCount || indexCount > 3000000 || indexCount % 3 || indexCount * indexSize > limit - at) throw new Error('invalid GEOM indices');
  const indices = [];
  for (let i = 0; i < indexCount; i++) { const value = indexSize === 2 ? u16() : u32(); if (value >= vertexCount) throw new Error('GEOM index outside vertices'); indices.push(value); }
  // The rest contains version-dependent stitches, rig palette and references.
  // Keep its extent explicit and never claim a rigged or material-complete mesh.
  let material = { status: 'none' };
  if (shader !== 0) {
    try {
      const position = tgiFieldOffset + 4 + tgiOffset;
      if (position < at || position + 4 > limit) throw new Error('invalid GEOM TGI table');
      const count = data.readUInt32LE(position);
      if (count > 4096 || position + 4 + count * 16 > limit) throw new Error('invalid GEOM TGI extent');
      const keys = [];
      for (let i = 0; i < count; i++) {
        const p = position + 4 + i * 16;
        keys.push(tgi(data.readUInt32LE(p), data.readUInt32LE(p + 4), data.readBigUInt64LE(p + 8)));
      }
      material = parseMaterial(data.subarray(materialAt, materialAt + materialBytes), keys);
    } catch { material = { status: 'invalid-or-unsupported-material' }; }
  }
  const limitations = ['rig-palette-unparsed', 'material-semantics-unqualified', 'stitches-unparsed'];
  if (formats.some(format => ![1, 2, 3, 4, 5].includes(format.usage))) limitations.push('vertex-attributes-unparsed');
  return { status: 'geometry-candidate', wrapperVersion, version, chunkOffset, chunkSize, tgiOffset, tgiSize,
    shader, materialBytes, material, mergeGroup, sortOrder, formats, vertices, indices, unparsedTailBytes: limit - at,
    limitations };
}
