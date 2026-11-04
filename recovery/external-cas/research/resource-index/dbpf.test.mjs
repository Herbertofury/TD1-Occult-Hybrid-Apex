import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { deflateSync } from 'node:zlib';
import path from 'node:path';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { indexPackage, readResource, caspReferences, resolveReferences, decodeRefpack } from './dbpf.mjs';

const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n >>> 0); return b; };
const u16 = n => { const b = Buffer.alloc(2); b.writeUInt16LE(n); return b; };
// Independent synthetic package writer, with I64 split into high/low words.
function fixture(rows, flags = 0, useLowOffset = false) {
  const header = Buffer.alloc(96); header.write('DBPF'); header.writeUInt32LE(2, 4); header.writeUInt32LE(1, 8);
  const chunks = [], entries = [], shared = [0x034aeecb, 0x12345678, 0x87654321];
  let offset = 96;
  for (const [ordinal, row] of rows.entries()) {
    const content = row.payload ?? Buffer.from('abc');
    const stored = row.stored ?? (row.compression === 0x5a42 ? deflateSync(content) : content);
    chunks.push(stored);
    const values = [row.type ?? shared[0], row.group ?? shared[1], row.hi ?? shared[2]];
    const entry = [];
    for (let i = 0; i < 3; i++) if (!(flags & (1 << i))) entry.push(u32(values[i]));
    entry.push(u32(row.lo ?? ordinal + 1), u32(offset));
    entry.push(u32(stored.length + (row.extended ? 0x80000000 : 0)), u32(content.length));
    if (row.extended) entry.push(u16(row.compression ?? 0), u16(row.committed ?? 1));
    entries.push(...entry); offset += stored.length;
  }
  const index = Buffer.concat([u32(flags), ...shared.filter((_, i) => flags & (1 << i)).map(u32), ...entries]);
  header.writeUInt32LE(rows.length, 36); header.writeUInt32LE(offset, useLowOffset ? 40 : 64); header.writeUInt32LE(index.length, 44);
  return Buffer.concat([header, ...chunks, index]);
}
async function withFile(bytes, fn) {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'cas-dbpf-'));
  const filename = path.join(dir, 'fixture.package');
  try { await writeFile(filename, bytes); return await fn(filename); }
  finally { await rm(dir, { recursive: true, force: true }); }
}
function casp(keys, version = 0x34) {
  const out = Buffer.alloc(32 + 1 + keys.length * 16);
  out.writeUInt32LE(version, 0); out.writeUInt32LE(24, 4); out[32] = keys.length;
  for (const [i, key] of keys.entries()) {
    const at = 33 + i * 16;
    out.writeBigUInt64LE(key.instance, at); out.writeUInt32LE(key.group, at + 8); out.writeUInt32LE(key.type, at + 12);
  }
  return out;
}

test('all shared-field masks retain unsigned 64-bit keys and index provenance', async () => {
  for (let flags = 0; flags < 8; flags++) await withFile(fixture([{ lo: 0xfedcba98 }], flags, flags % 2 === 1), async filename => {
    const index = await indexPackage(filename);
    assert.equal(index.rows[0].key, '034AEECB:12345678:87654321FEDCBA98');
    assert.match(index.source.sha256, /^[0-9a-f]{64}$/);
    assert.equal((await readResource(filename, index, 0)).payload.toString(), 'abc');
  });
});

test('mixed plain, zlib, unknown and tombstone rows remain distinguishable', async () => {
  const bytes = fixture([{ payload: Buffer.from('plain') }, { payload: Buffer.from('compressed'), extended: true, compression: 0x5a42 },
    { extended: true, compression: 0xbeef }, { extended: true, compression: 0xffe0 }], 7);
  await withFile(bytes, async filename => {
    const index = await indexPackage(filename);
    assert.equal((await readResource(filename, index, 1)).payload.toString(), 'compressed');
    assert.equal((await readResource(filename, index, 2)).status, 'unsupported-compression');
    assert.equal((await readResource(filename, index, 3)).status, 'deleted');
    assert.equal(index.rows[2].compression, 0xbeef);
  });
});

test('refuses stale source and forged locators', async () => {
  await withFile(fixture([{}]), async filename => {
    const index = await indexPackage(filename);
    const forged = structuredClone(index); forged.rows[0].offset++;
    await assert.rejects(readResource(filename, forged, 0), /stale/);
    const changed = fixture([{ payload: Buffer.from('xyz') }]);
    await writeFile(filename, changed);
    await assert.rejects(readResource(filename, index, 0), /stale/);
  });
});

test('malformed index and resource extents fail closed', async () => {
  const original = fixture([{}]);
  for (const mutate of [
    b => b.write('NOPE'), b => b.writeUInt32LE(3, 4), b => b.writeUInt32LE(250001, 36),
    b => b.writeUInt32LE(0xffffffff, 44), b => b.writeUInt32LE(0xffffffff, 64),
    b => b.writeUInt32LE(8, b.readUInt32LE(64)), // unknown flags
    b => b.writeUInt32LE(0xffffffff, b.readUInt32LE(64) + 4 + 16), // payload offset
  ]) {
    const bytes = Buffer.from(original); mutate(bytes);
    await withFile(bytes, filename => assert.rejects(indexPackage(filename)));
  }
  await withFile(original.subarray(0, original.length - 1), filename => assert.rejects(indexPackage(filename)));
});

test('CASP table candidates preserve ambiguity, missing and empty links', async () => {
  const keys = [{ type: 0x034aeecb, group: 0x12345678, instance: 0x8765432100000001n },
    { type: 1, group: 2, instance: 3n }, { type: 0, group: 0, instance: 0n }];
  await withFile(fixture([{}]), async filename => {
    const index = await indexPackage(filename);
    const table = caspReferences(casp(keys));
    assert.equal(table.status, 'table-only');
    assert.deepEqual(resolveReferences(table.references, [index, index]).map(x => x.status), ['ambiguous', 'missing', 'empty']);
    assert.equal(resolveReferences(table.references, [index])[0].status, 'unique-in-supplied-indexes');
    assert.equal(resolveReferences(table.references, [index])[0].candidates[0].source.sha256, index.source.sha256);
  });
  assert.equal(caspReferences(casp([], 0x35)).status, 'unsupported-version');
  assert.throws(() => caspReferences(casp(keys).subarray(0, 40)), /extent/);
});

test('inspect command resolves a synthetic CASP to an independently indexed dependency', async () => {
  const key = { type: 0x015a1849, group: 0x12345678, instance: 0x8765432100000002n };
  const bytes = fixture([{ payload: casp([key]), extended: true, compression: 0x5a42 },
    { type: key.type, lo: 2, payload: Buffer.from('mesh-placeholder') }]);
  await withFile(bytes, async filename => {
    const cli = fileURLToPath(new URL('./inspect.mjs', import.meta.url));
    const output = execFileSync(process.execPath, [cli, '034AEECB:12345678:8765432100000001', filename], { encoding: 'utf8' });
    const result = JSON.parse(output);
    assert.equal(result.table.status, 'table-only');
    assert.equal(result.table.references[0].status, 'unique-in-supplied-indexes');
    assert.equal(result.table.references[0].candidates[0].row.key, '015A1849:12345678:8765432100000002');
    assert.equal(output.includes('mesh-placeholder'), false);
    assert.equal(output.includes(filename), false);
  });
});

test('unrecognized storage markers remain indexed but cannot be read as ordinary payload', async () => {
  await withFile(fixture([{ extended: true, compression: 0, committed: 7 }]), async filename => {
    const index = await indexPackage(filename);
    assert.equal(index.rows[0].committed, 7);
    assert.equal((await readResource(filename, index, 0)).status, 'unsupported-storage-marker');
  });
});

test('resolution rejects unbounded or invalid supplied indexes before traversal', () => {
  assert.throws(() => resolveReferences([], [{ rows: Array(250001) }]), /row limit/);
  assert.throws(() => resolveReferences([], [{}]), /invalid index/);
  assert.throws(() => resolveReferences(Array(256), []), /resolution limit/);
});

test('bounded RefPack handles literal and overlapping backreferences and rejects malformed streams', async () => {
  const streams = [
    [Buffer.from('10fb000005e061626364fd65', 'hex'), 'abcde'],
    [Buffer.from('10fb000007e0616263640003fc', 'hex'), 'abcdabc'],
    [Buffer.from('10fb000008e061626364800003fc', 'hex'), 'abcdabcd'],
    [Buffer.from('10fb000009e061626364c0000300fc', 'hex'), 'abcdabcda'],
  ];
  for (const [stream, expected] of streams) {
    assert.equal(decodeRefpack(stream, expected.length).toString(), expected);
    await withFile(fixture([{ payload: Buffer.from(expected), stored: stream, extended: true, compression: 0xffff }]), async filename => {
      const index = await indexPackage(filename);
      assert.equal((await readResource(filename, index, 0)).payload.toString(), expected);
    });
  }
  for (const [bytes, size] of [
    ['10fb0000040000fc', 4], ['10fb000004e06162', 4], ['10fb000004e061626364', 4],
    ['10fb000004e061626364fc00', 4], ['10fa000004e061626364fc', 4],
  ]) assert.throws(() => decodeRefpack(Buffer.from(bytes, 'hex'), size));
  if (process.env.S4PY_ROOT && process.env.S4PY_PYTHON) {
    const bridge = fileURLToPath(new URL('./s4py_oracle.py', import.meta.url));
    for (const [stream, expected] of streams) {
      const actual = execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, process.env.S4PY_ROOT, '--refpack', stream.toString('hex')], { encoding: 'utf8' }).trim();
      assert.equal(Buffer.from(actual, 'hex').toString(), expected);
    }
  }
});

test('synthetic indexes agree with independently obtained s4py', { skip: !(process.env.S4PY_ROOT && process.env.S4PY_PYTHON) }, async () => {
  const bridge = fileURLToPath(new URL('./s4py_oracle.py', import.meta.url));
  for (let flags = 0; flags < 8; flags++) {
    const bytes = fixture([{ lo: 0xfedcba98 }, { lo: 2, extended: true, compression: 0x5a42, payload: Buffer.from('oracle') },
      { lo: 3, extended: true, compression: 0xffe0 }], flags, flags % 2 === 1);
    await withFile(bytes, async filename => {
      const index = await indexPackage(filename);
      const actual = index.rows.map(({ key, offset, storedSize, memorySize, compression, committed, deleted }) =>
        ({ key, offset, storedSize, memorySize, compression, committed, deleted }));
      const oracle = JSON.parse(execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, process.env.S4PY_ROOT, filename], { encoding: 'utf8' }));
      assert.deepEqual(actual, oracle);
    });
  }
});

test('private comparison reports counts without source keys, hashes or paths', { skip: !(process.env.S4PY_ROOT && process.env.S4PY_PYTHON) }, async () => {
  const key = { type: 0x015a1849, group: 0x12345678, instance: 0x8765432100000002n };
  const data = fixture([{ payload: casp([key]), extended: true, compression: 0x5a42 }, { type: key.type, lo: 2 }]);
  await withFile(data, async one => withFile(data, async two => {
    const cli = fileURLToPath(new URL('./compare-private.mjs', import.meta.url));
    const output = execFileSync(process.execPath, [cli, one, two], { encoding: 'utf8' });
    const report = JSON.parse(output);
    assert.equal(report.sharedKeyPairs[0].sharedKeys, 2);
    assert.equal(report.referenceResults.ambiguous, 2);
    assert.equal(output.includes(one), false);
    assert.equal(output.includes('015A1849'), false);
    assert.equal(output.includes('sha256'), false);
  }));
});

test('private RefPack comparison reports a match without publishing payload or hash', { skip: !(process.env.S4PY_ROOT && process.env.S4PY_PYTHON) }, async () => {
  const stream = Buffer.from('10fb000005e061626364fd65', 'hex');
  await withFile(fixture([{ payload: Buffer.from('abcde'), stored: stream, extended: true, compression: 0xffff }]), async filename => {
    const cli = fileURLToPath(new URL('./compare-refpack-private.mjs', import.meta.url));
    const output = execFileSync(process.execPath, [cli, filename], { encoding: 'utf8' });
    assert.deepEqual(JSON.parse(output), { samples: 1, matched: true, outputBytes: 5 });
    assert.equal(output.includes(filename), false);
    assert.equal(output.includes('abcde'), false);
  });
});
