// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded MTNF/MTRL metadata and candidate texture references.
const fields = new Map([
  [0x6cc0fd85, 'diffuse'], [0x6e56548a, 'normal'], [0xad528a60, 'specular'],
  [0xc3faac4f, 'alpha'], [0xf303d152, 'emission'], [0x6e067554, 'selfillum'],
]);
export function parseMaterial(data, tgis) {
  if (!Buffer.isBuffer(data) || data.length < 16 || data.length > 1024 * 1024 || !Array.isArray(tgis) || tgis.length > 4096)
    throw new Error('invalid material input');
  const magic = data.toString('ascii', 0, 4);
  if (!['MTNF', 'MTRL'].includes(magic)) return { status: 'unsupported-material', magic };
  const marker = data.readUInt32LE(4), dataLength = data.readUInt32LE(8), count = data.readUInt32LE(12);
  if (count > 1024 || 16 + count * 16 > data.length) throw new Error('material entry extent');
  const entries = [];
  for (let i = 0; i < count; i++) {
    const at = 16 + i * 16;
    const field = data.readUInt32LE(at), type = data.readUInt32LE(at + 4), length = data.readUInt32LE(at + 8), offset = data.readUInt32LE(at + 12);
    const entry = { field, type, length, offset, role: fields.get(field) ?? null, status: 'opaque' };
    if (entry.role && type === 4 && length === 4) {
      if (offset < 16 + count * 16 || offset + 4 > data.length) throw new Error('material reference extent');
      entry.index = data.readUInt32LE(offset);
      if (entry.index >= tgis.length) entry.status = 'unresolved-index';
      else { entry.status = 'candidate'; entry.key = tgis[entry.index]; }
    }
    entries.push(entry);
  }
  return { status: 'parsed-candidate', magic, marker, dataLength, entries };
}
