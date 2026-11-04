// SPDX-License-Identifier: GPL-3.0-or-later
// GEOM v12 bone-palette candidate. Rig skeleton and transforms are separate.
export function parsePalette(data, start, end, tgiPosition, version) {
  if (version !== 12) return { status: 'unsupported-version', version };
  if (!Buffer.isBuffer(data) || !Number.isSafeInteger(start) || !Number.isSafeInteger(end) || !Number.isSafeInteger(tgiPosition) ||
      start < 0 || start > tgiPosition || tgiPosition > end || end > data.length) throw new Error('invalid palette extent');
  let at = start;
  function take(n) { if (!Number.isSafeInteger(n) || n < 0 || at + n > tgiPosition) throw new Error('truncated palette'); const pos = at; at += n; return pos; }
  function count(max) { const n = data.readUInt32LE(take(4)); if (n > max) throw new Error('palette count limit'); return n; }
  const uvStitches = count(250000);
  let uvPairs = 0;
  for (let i = 0; i < uvStitches; i++) {
    take(4);
    const pairs = count(250000);
    uvPairs += pairs;
    if (uvPairs > 250000) throw new Error('palette count limit');
    take(pairs * 8);
  }
  const slotIntersections = count(250000);
  take(slotIntersections * 63);
  const boneCount = count(256), hashes = [];
  for (let i = 0; i < boneCount; i++) hashes.push(data.readUInt32LE(take(4)));
  if (at !== tgiPosition) throw new Error('unsupported palette layout');
  return { status: 'palette-candidate', version, uvStitches, slotIntersections, hashes };
}

// Preserve raw byte weights; no skeleton choice, transforms or normalization.
export function mapPaletteWeights(geom) {
  if (geom?.status !== 'geometry-candidate' || geom.palette?.status !== 'palette-candidate') return { status: 'unavailable-palette' };
  if (geom.vertices.some(vertex => !vertex.joints || !vertex.weights)) return { status: 'missing-weights' };
  const vertices = [];
  for (const vertex of geom.vertices) {
    if (vertex.joints.length !== 4 || vertex.weights.length !== 4) throw new Error('invalid vertex weights');
    const influences = [];
    for (let i = 0; i < 4; i++) {
      if (!vertex.weights[i]) continue;
      const index = vertex.joints[i];
      if (index >= geom.palette.hashes.length) throw new Error('bone index outside palette');
      influences.push({ boneHash: geom.palette.hashes[index], weightByte: vertex.weights[i] });
    }
    if (!influences.length) throw new Error('vertex has no weights');
    vertices.push(influences);
  }
  return { status: 'mapped-candidate', vertices };
}
