// Read-only, bounded DBPF 2.1 index. No source content is persisted.
import { open } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { inflateSync } from 'node:zlib';

const HEADER = 96, MAX_INDEX = 128 * 1024 * 1024, MAX_ENTRIES = 250_000;
const MAX_PAYLOAD = 64 * 1024 * 1024, HASH_CHUNK = 1024 * 1024;
const hex = (n, width) => n.toString(16).toUpperCase().padStart(width, '0');
export function tgi(type, group, instance) {
  return `${hex(type, 8)}:${hex(group, 8)}:${hex(instance, 16)}`;
}
function invalid(message) { throw new Error(message); }
async function readExactly(file, offset, length) {
  const result = Buffer.alloc(length);
  let done = 0;
  while (done < length) {
    const { bytesRead } = await file.read(result, done, length - done, offset + done);
    if (!bytesRead) invalid('truncated file');
    done += bytesRead;
  }
  return result;
}
function sameStat(a, b) {
  return a.size === b.size && a.mtimeMs === b.mtimeMs && a.ctimeMs === b.ctimeMs && a.ino === b.ino && a.dev === b.dev;
}
async function fingerprint(file, size) {
  const hash = createHash('sha256');
  const buf = Buffer.alloc(HASH_CHUNK);
  for (let pos = 0; pos < size;) {
    const { bytesRead } = await file.read(buf, 0, Math.min(buf.length, size - pos), pos);
    if (!bytesRead) invalid('file changed during fingerprint');
    hash.update(buf.subarray(0, bytesRead));
    pos += bytesRead;
  }
  return hash.digest('hex');
}

// RefPack streams use literal and backward-copy commands. Fail closed on
// unsupported headers, truncation, impossible distances and extra input.
export function decodeRefpack(input, expectedSize) {
  if (!Buffer.isBuffer(input) || input.length < 5 || !Number.isSafeInteger(expectedSize) || expectedSize < 0 || expectedSize > MAX_PAYLOAD)
    invalid('invalid RefPack input');
  let pos = 0;
  const byte = () => { if (pos >= input.length) invalid('truncated RefPack'); return input[pos++]; };
  const flags = byte();
  if (byte() !== 0xfb) invalid('unsupported RefPack header');
  let declared = 0;
  for (let i = 0; i < ((flags & 0x80) ? 4 : 3); i++) declared = declared * 256 + byte();
  if (declared !== expectedSize) invalid('RefPack declared size mismatch');
  const output = Buffer.alloc(expectedSize);
  let written = 0, ended = false;
  while (pos < input.length && !ended) {
    const op = byte();
    let literals, length = 0, distance = 0;
    if (op <= 0x7f) {
      const b = byte(); literals = op & 3; length = ((op & 0x1c) >> 2) + 3;
      distance = ((op & 0x60) << 3) + b + 1;
    } else if (op <= 0xbf) {
      const b = byte(), c = byte(); literals = b >> 6; length = (op & 0x3f) + 4;
      distance = ((b & 0x3f) << 8) + c + 1;
    } else if (op <= 0xdf) {
      const b = byte(), c = byte(), d = byte(); literals = op & 3; length = ((op & 0x0c) << 6) + d + 5;
      distance = ((op & 0x10) << 12) + (b << 8) + c + 1;
    } else if (op <= 0xfb) literals = ((op & 0x1f) << 2) + 4;
    else { literals = op & 3; ended = true; }
    if (pos + literals > input.length || written + literals + length > output.length) invalid('invalid RefPack extent');
    input.copy(output, written, pos, pos + literals); pos += literals; written += literals;
    if (length && distance > written) invalid('invalid RefPack distance');
    for (let i = 0; i < length; i++) { output[written] = output[written - distance]; written++; }
  }
  if (!ended || written !== output.length || pos !== input.length) invalid('incomplete RefPack stream');
  return output;
}

async function inspectPackage(filename, hashPayload) {
  const file = await open(filename, 'r');
  try {
    const before = await file.stat();
    if (!before.isFile() || !Number.isSafeInteger(before.size) || before.size < HEADER) invalid('invalid package file');
    const header = await readExactly(file, 0, HEADER);
    const indexHash = createHash('sha256').update(header);
    if (header.toString('ascii', 0, 4) !== 'DBPF') invalid('invalid DBPF magic');
    if (header.readUInt32LE(4) !== 2 || header.readUInt32LE(8) !== 1) invalid('unsupported DBPF version');
    const count = header.readUInt32LE(36), indexSize = header.readUInt32LE(44);
    const offset = header.readUInt32LE(64) || header.readUInt32LE(40);
    if (count > MAX_ENTRIES || indexSize > MAX_INDEX) invalid('index limit');
    if ((count && !offset) || offset + indexSize > before.size) invalid('invalid index extent');
    let rows = [];
    if (count || indexSize) {
      if (indexSize < 4 || offset < HEADER) invalid('invalid index header');
      const data = await readExactly(file, offset, indexSize);
      indexHash.update(data);
      let cursor = 0;
      function u32() { if (cursor + 4 > data.length) invalid('truncated index'); const n = data.readUInt32LE(cursor); cursor += 4; return n; }
      function u16() { if (cursor + 2 > data.length) invalid('truncated index'); const n = data.readUInt16LE(cursor); cursor += 2; return n; }
      const flags = u32();
      if (flags & ~7) invalid('unsupported index flags');
      const shared = [0, 1, 2].map(i => flags & (1 << i) ? u32() : null);
      // The smallest supported entry contains low instance, offset and two sizes.
      if (count * 16 > data.length - cursor) invalid('index count exceeds extent');
      rows = new Array(count);
      for (let ordinal = 0; ordinal < count; ordinal++) {
        const type = shared[0] ?? u32(), group = shared[1] ?? u32(), hi = shared[2] ?? u32();
        const lo = u32(), resourceOffset = u32(), sizeBits = u32(), memorySize = u32();
        const extended = !!(sizeBits & 0x80000000), storedSize = sizeBits & 0x7fffffff;
        const compression = extended ? u16() : 0, committed = extended ? u16() : 1;
        const deleted = compression === 0xffe0;
        if (!deleted && resourceOffset + storedSize > before.size) invalid('resource outside file');
        rows[ordinal] = { key: tgi(type, group, (BigInt(hi) << 32n) | BigInt(lo)), ordinal,
          offset: resourceOffset, storedSize, memorySize, compression, committed, extended, deleted };
      }
      if (cursor !== data.length) invalid('unsupported trailing index bytes');
    }
    const source = hashPayload ? { sha256: await fingerprint(file, before.size), size: before.size }
      : { verification: 'index-only', indexSha256: indexHash.digest('hex'), size: before.size };
    if (!sameStat(before, await file.stat())) invalid('file changed during indexing');
    return { schema: 1, source, rows };
  } finally { await file.close(); }
}
export async function indexPackage(filename) { return inspectPackage(filename, true); }
// Discovery only: does not authenticate payload bytes and cannot authorize reads.
export async function scanPackageIndex(filename) { return inspectPackage(filename, false); }

// Re-index and hash once per bounded group to amortize source verification.
// Locators and all returned bytes belong to the same verified, open file.
export async function readResourceBatch(filename, indexed, ordinals) {
  if (!indexed || !/^[0-9a-f]{64}$/.test(indexed.source?.sha256 ?? '') || !Array.isArray(ordinals) || ordinals.length === 0 || ordinals.length > 128 || new Set(ordinals).size !== ordinals.length ||
      ordinals.some(ordinal => !Number.isSafeInteger(ordinal) || ordinal < 0 || !indexed.rows?.[ordinal])) invalid('invalid locator');
  const current = await indexPackage(filename);
  if (current.source.sha256 !== indexed.source?.sha256 || current.source.size !== indexed.source?.size || ordinals.some(ordinal =>
      JSON.stringify(current.rows[ordinal]) !== JSON.stringify(indexed.rows[ordinal]))) invalid('stale source or locator');
  const rows = ordinals.map(ordinal => current.rows[ordinal]);
  let storedTotal = 0, memoryTotal = 0;
  for (const row of rows) {
    if (row.deleted || row.committed !== 1 || ![0, 0x5a42, 0xffff].includes(row.compression)) continue;
    storedTotal += row.storedSize; memoryTotal += row.memorySize;
    if (storedTotal > MAX_PAYLOAD || memoryTotal > MAX_PAYLOAD) invalid('payload limit');
  }
  const file = await open(filename, 'r');
  try {
    const before = await file.stat();
    if (before.size !== current.source.size || await fingerprint(file, before.size) !== current.source.sha256) invalid('source changed');
    const results = [];
    for (const row of rows) {
      if (row.deleted) { results.push({ status: 'deleted', row }); continue; }
      if (row.committed !== 1) { results.push({ status: 'unsupported-storage-marker', row }); continue; }
      if (![0, 0x5a42, 0xffff].includes(row.compression)) { results.push({ status: 'unsupported-compression', row }); continue; }
      const bytes = await readExactly(file, row.offset, row.storedSize);
      const payload = row.compression === 0 ? bytes : row.compression === 0x5a42
        ? inflateSync(bytes, { maxOutputLength: MAX_PAYLOAD }) : decodeRefpack(bytes, row.memorySize);
      if (payload.length !== row.memorySize) invalid('decompressed size mismatch');
      results.push({ status: 'available', row, payload });
    }
    if (!sameStat(before, await file.stat())) invalid('source changed during read');
    return results;
  } finally { await file.close(); }
}
export async function readResource(filename, indexed, ordinal) {
  return (await readResourceBatch(filename, indexed, [ordinal]))[0];
}

// This reads the CASP reference table only, not semantic roles or applicability.
export function caspReferences(payload) {
  if (!Buffer.isBuffer(payload) || payload.length < 32) invalid('truncated CASP');
  const version = payload.readUInt32LE(0);
  if (version < 0x1f || version > 0x34) return { status: 'unsupported-version', version, references: [] };
  const pos = payload.readUInt32LE(4) + 8;
  if (pos < 12 || pos >= payload.length) invalid('invalid CASP reference table');
  const count = payload[pos];
  if (pos + 1 + count * 16 !== payload.length) invalid('invalid CASP reference extent');
  const references = [];
  for (let i = 0; i < count; i++) {
    const at = pos + 1 + i * 16;
    const instance = payload.readBigUInt64LE(at), group = payload.readUInt32LE(at + 8), type = payload.readUInt32LE(at + 12);
    references.push({ tableIndex: i, key: tgi(type, group, instance), empty: type === 0 && group === 0 && instance === 0n });
  }
  return { status: 'table-only', version, references };
}

// No implicit load-order rule: even one match is only unique within supplied indexes.
export function resolveReferences(references, indexes) {
  if (!Array.isArray(references) || references.length > 255 || !Array.isArray(indexes) || indexes.length > 16) invalid('resolution limit');
  let total = 0;
  for (const index of indexes) {
    if (!Array.isArray(index?.rows)) invalid('invalid index');
    total += index.rows.length;
    if (total > MAX_ENTRIES) invalid('resolution row limit');
  }
  const byKey = new Map();
  for (const index of indexes) for (const row of index.rows) {
    const values = byKey.get(row.key) ?? [];
    values.push({ source: index.source, row });
    byKey.set(row.key, values);
  }
  return references.map(ref => {
    const candidates = ref.empty ? [] : (byKey.get(ref.key) ?? []);
    const status = ref.empty ? 'empty' : candidates.length === 0 ? 'missing' : candidates.length === 1 ? 'unique-in-supplied-indexes' : 'ambiguous';
    return { ...ref, status, candidates };
  });
}
