// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded RLE2 to BC3 blocks and BC3 to RGBA. RLES is deliberately unsupported.
const LIMIT = 64 * 1024 * 1024;
export function decodeRle2(data) {
  if (!Buffer.isBuffer(data) || data.length < 36 || data.length > LIMIT) throw new Error('invalid RLE input');
  const fourcc = data.toString('ascii', 0, 4), version = data.toString('ascii', 4, 8);
  if (fourcc !== 'DXT5' || version !== 'RLE2') return { status: 'unsupported-format', fourcc, version };
  const width = data.readUInt16LE(8), height = data.readUInt16LE(10), mipCount = data.readUInt16LE(12);
  if (!width || !height || width * height > LIMIT / 4 || !mipCount || mipCount > 16 || 16 + mipCount * 20 > data.length)
    throw new Error('invalid RLE dimensions');
  const headerEnd = 16 + mipCount * 20, headers = [];
  for (let i = 0; i < mipCount; i++) {
    const at = 16 + i * 20;
    headers.push([0, 1, 2, 3, 4].map(n => data.readUInt32LE(at + n * 4)));
  }
  const first = headers[0];
  headers.push([first[1], first[2], first[3], first[4], data.length]);
  const transparent = Buffer.from([0, 5, 0, 0, 0, 0, 0, 0]), opaque = Buffer.from([0, 5, 255, 255, 255, 255, 255, 255]);
  let total = 0;
  const mips = [];
  for (let i = 0; i < mipCount; i++) {
    const start = headers[i], end = headers[i + 1];
    for (let n = 0; n < 5; n++) if (start[n] < headerEnd || end[n] < start[n] || end[n] > data.length) throw new Error('invalid RLE stream extent');
    const w = Math.max(1, width >> i), h = Math.max(1, height >> i), blocks = Math.ceil(w / 4) * Math.ceil(h / 4);
    total += blocks * 16;
    if (total > LIMIT || (end[0] - start[0]) % 2) throw new Error('RLE output limit');
    const output = Buffer.alloc(blocks * 16), offsets = [...start];
    let count = 0;
    function copy(stream, length, target) {
      if (offsets[stream] + length > end[stream]) throw new Error('truncated RLE stream');
      data.copy(output, target, offsets[stream], offsets[stream] + length); offsets[stream] += length;
    }
    while (offsets[0] < end[0]) {
      const command = data.readUInt16LE(offsets[0]); offsets[0] += 2;
      const op = command & 3, run = command >>> 2;
      if (op === 3 || count + run > blocks) throw new Error('unsupported RLE command');
      for (let j = 0; j < run; j++) {
        const dst = count++ * 16;
        if (op === 0) { transparent.copy(output, dst); transparent.copy(output, dst + 8); }
        else if (op === 1) { copy(3, 2, dst); copy(4, 6, dst + 2); copy(1, 4, dst + 8); copy(2, 4, dst + 12); }
        else { opaque.copy(output, dst); copy(1, 4, dst + 8); copy(2, 4, dst + 12); }
      }
    }
    if (count !== blocks || offsets.some((position, n) => position !== end[n])) throw new Error('incomplete RLE mip');
    mips.push({ width: w, height: h, bc3: output });
  }
  return { status: 'decoded-bc3', width, height, mipCount, mips };
}

export function decodeBc3(width, height, blocks) {
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1 || width * height > LIMIT / 4 || !Buffer.isBuffer(blocks))
    throw new Error('invalid BC3 input');
  const across = Math.ceil(width / 4), down = Math.ceil(height / 4);
  if (blocks.length !== across * down * 16) throw new Error('invalid BC3 extent');
  const rgba = Buffer.alloc(width * height * 4);
  const rgb = value => { const r = (value >> 11) & 31, g = (value >> 5) & 63, b = value & 31;
    return [(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)]; };
  for (let by = 0; by < down; by++) for (let bx = 0; bx < across; bx++) {
    const pos = (by * across + bx) * 16, a0 = blocks[pos], a1 = blocks[pos + 1];
    const alpha = [a0, a1];
    if (a0 > a1) for (let k = 1; k <= 6; k++) alpha.push(Math.floor(((7 - k) * a0 + k * a1) / 7));
    else { for (let k = 1; k <= 4; k++) alpha.push(Math.floor(((5 - k) * a0 + k * a1) / 5)); alpha.push(0, 255); }
    let alphaBits = 0n;
    for (let k = 0; k < 6; k++) alphaBits |= BigInt(blocks[pos + 2 + k]) << BigInt(8 * k);
    const c0 = rgb(blocks.readUInt16LE(pos + 8)), c1 = rgb(blocks.readUInt16LE(pos + 10));
    const colors = [c0, c1, c0.map((v, k) => Math.floor((2 * v + c1[k]) / 3)), c0.map((v, k) => Math.floor((v + 2 * c1[k]) / 3))];
    const colorBits = blocks.readUInt32LE(pos + 12);
    for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) {
      const px = bx * 4 + x, py = by * 4 + y;
      if (px >= width || py >= height) continue;
      const bit = y * 4 + x, color = colors[(colorBits >>> (2 * bit)) & 3], opacity = alpha[Number((alphaBits >> BigInt(3 * bit)) & 7n)];
      const target = (py * width + px) * 4;
      rgba[target] = color[0]; rgba[target + 1] = color[1]; rgba[target + 2] = color[2]; rgba[target + 3] = opacity;
    }
  }
  return rgba;
}
