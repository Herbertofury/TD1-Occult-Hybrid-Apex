// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded CASP role parser; research only, not a compatibility decision.
import { caspReferences } from './dbpf.mjs';

export function parseCasp(payload) {
  const table = caspReferences(payload);
  if (table.status !== 'table-only') return table;
  const version = table.version, end = payload.readUInt32LE(4) + 8;
  let at = 8;
  function take(n) { if (!Number.isSafeInteger(n) || n < 0 || at + n > end) throw new Error('truncated CASP fields'); const p = at; at += n; return p; }
  const u8 = () => payload.readUInt8(take(1));
  const u16 = () => payload.readUInt16LE(take(2));
  const u32 = () => payload.readUInt32LE(take(4));
  const i32 = () => payload.readInt32LE(take(4));
  const skip = n => { take(n); };
  function count32(limit) { const n = i32(); if (n < 0 || n > limit) throw new Error('CASP count limit'); return n; }
  function nameBytes() {
    let n = 0, multiplier = 1;
    for (let i = 0; i < 5; i++) {
      const b = u8(); n += (b & 0x7f) * multiplier;
      if (!(b & 0x80)) {
        if (n > 65536 || n % 2) throw new Error('invalid CASP name length');
        return n;
      }
      multiplier *= 128;
    }
    throw new Error('invalid CASP name length');
  }
  const presetCount = i32();
  if (presetCount !== 0) throw new Error('unsupported CASP preset data');
  const nameLength = nameBytes();
  const name = new TextDecoder('utf-16be', { fatal: true }).decode(payload.subarray(at, at + nameLength));
  skip(nameLength);
  const sortPriority = payload.readFloatLE(take(4));
  if (!Number.isFinite(sortPriority)) throw new Error('invalid CASP priority');
  const swatchOrder = u16(), outfitId = u32(), materialHash = u32(), flags1 = u8();
  const flags2 = version >= 39 ? u8() : null;
  const layerId = version >= 50 ? u16() : null;
  if (version >= 51) skip(count32(1024) * 8);
  else { skip(8); if (version >= 41) skip(8); }
  skip(version > 36 ? 8 : 4);
  const tagCount = count32(4096);
  skip(tagCount * (version >= 37 ? 6 : 4));
  const price = u32(), titleKey = u32(), descriptionKey = u32();
  const createDescriptionKey = version > 42 ? u32() : null;
  const textureSpace = u8(), bodyType = u32(), bodySubType = u32();
  const age = u8(), gender = u8(), ageGenderReserved = u16();
  const species = version >= 32 ? u32() : null;
  let packId = null, packFlags = null;
  if (version >= 34) { packId = u16(); packFlags = u8(); skip(9); }
  else if (u8()) skip(1);
  const colorCount = u8(), colors = [];
  for (let i = 0; i < colorCount; i++) colors.push(u32());
  const pending = [];
  const reference = (role, index, extra = {}) => pending.push({ role, index, ...extra });
  reference('buff', u8()); reference('swatch', u8());
  if (version >= 28) skip(8);
  if (version >= 30 && u8() > 0) skip(12);
  const occultMask = version >= 31 ? u32() : null;
  if (version >= 46) skip(8);
  if (version >= 38) skip(8);
  if (version >= 39) skip(8);
  if (version >= 44) skip(44);
  if (version >= 46) { const n = u8(); for (let i = 0; i < n; i++) reference('hair-color', u8()); }
  reference('naked', u8()); reference('parent', u8());
  const sortLayer = i32(), lodCount = u8();
  for (let i = 0; i < lodCount; i++) {
    const lod = u8(); skip(4); const assetCount = u8(); skip(assetCount * 12);
    const meshCount = u8();
    for (let j = 0; j < meshCount; j++) reference('mesh', u8(), { lod });
  }
  const slotCount = u8(); for (let i = 0; i < slotCount; i++) reference('slot', u8());
  reference('diffuse', u8()); reference('shadow', u8());
  const compositionMethod = u8(); reference('region-map', u8());
  const overrideCount = u8(); skip(overrideCount * 5);
  reference('normal', u8()); reference('specular', u8());
  if (version >= 27) skip(4);
  if (version >= 29) reference('emission', u8());
  if (version >= 42) reference('blend-geometry', u8());
  if (version >= 49) reference('color-shift-mask', u8());
  if (version >= 52) reference('new-image', u8());
  if (at !== end) throw new Error('unsupported CASP field layout');
  const roles = pending.map(item => {
    if (item.index >= table.references.length) throw new Error('CASP reference index out of range');
    return { ...item, key: table.references[item.index].key, empty: table.references[item.index].empty };
  });
  return { status: 'parsed-candidate', version, name, sortPriority, swatchOrder, outfitId, materialHash,
    flags1, flags2, layerId, tagCount, price, titleKey, descriptionKey, createDescriptionKey,
    textureSpace, bodyType, bodySubType, age, gender, ageGenderReserved, species, packId, packFlags,
    colors, occultMask, sortLayer, compositionMethod, roles, references: table.references };
}
