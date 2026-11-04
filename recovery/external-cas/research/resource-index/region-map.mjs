// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded RMAP metadata; no renderer visibility or ordering is inferred.
import { tgi } from './dbpf.mjs';

export function parseRegionMap(data) {
  if (!Buffer.isBuffer(data) || data.length < 28 || data.length > 1024 * 1024) throw new Error('invalid RMAP input');
  let at = 0, totalKeys = 0;
  function take(n) { if (!Number.isSafeInteger(n) || n < 0 || at + n > data.length) throw new Error('truncated RMAP'); const p = at; at += n; return p; }
  const u8 = () => data.readUInt8(take(1));
  const u32 = () => data.readUInt32LE(take(4));
  function count(limit) { const n = u32(); if (n > limit) throw new Error('RMAP count limit'); return n; }
  function keys(n) {
    totalKeys += n;
    if (totalKeys > 4096) throw new Error('RMAP key limit');
    const result = [];
    for (let i = 0; i < n; i++) {
      const instance = data.readBigUInt64LE(take(8)), type = u32(), group = u32();
      result.push(tgi(type, group, instance));
    }
    return result;
  }
  const contextVersion = u32();
  if (contextVersion !== 3) return { status: 'unsupported-context', contextVersion };
  const publicCount = count(1024), externalCount = count(1024), delayedCount = count(1024), objectCount = count(1024);
  const publicKeys = keys(publicCount), externalKeys = keys(externalCount), delayedKeys = keys(delayedCount);
  // Object offsets are retained as opaque metadata; their interpretation is not assumed.
  const objects = [];
  for (let i = 0; i < objectCount; i++) objects.push({ offset: u32(), size: u32() });
  const version = u32();
  if (version !== 1) return { status: 'unsupported-version', contextVersion, version };
  const blockCount = count(4096), blocks = [];
  for (let i = 0; i < blockCount; i++) {
    const region = u32(), layer = data.readFloatLE(take(4)), replacement = u8();
    if (!Number.isFinite(layer)) throw new Error('invalid RMAP layer');
    blocks.push({ region, layer, replacement, keys: keys(count(4096)) });
  }
  if (at !== data.length) throw new Error('unsupported RMAP trailing data');
  return { status: 'parsed-candidate', contextVersion, version, publicKeys, externalKeys, delayedKeys, objects, blocks };
}

// Provide a renderer-facing mapping without inferring which surfaces to hide.
export function mapMeshRegions(casp, regionMap) {
  if (casp?.status !== 'parsed-candidate' || regionMap?.status !== 'parsed-candidate') throw new Error('unavailable region inputs');
  const meshes = casp.roles.filter(role => role.role === 'mesh');
  if (meshes.length > 4096) throw new Error('mesh binding limit');
  return meshes.map(mesh => {
    const regions = [];
    for (const block of regionMap.blocks) if (block.keys.includes(mesh.key)) {
      regions.push({ region: block.region, layer: block.layer, replacement: block.replacement });
    }
    return { key: mesh.key, lod: mesh.lod, state: regions.length ? 'matched' : 'unmapped', regions };
  });
}
