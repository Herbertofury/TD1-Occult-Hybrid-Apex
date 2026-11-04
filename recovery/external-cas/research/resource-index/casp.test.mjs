// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { parseCasp } from './casp.mjs';
import { compareCaspReference } from './casp-reference.mjs';

const byte = n => Buffer.from([n]);
const word = n => { const b = Buffer.alloc(2); b.writeUInt16LE(n); return b; };
const dword = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
const blank = n => Buffer.alloc(n);
function sample(version, meshIndex = 1, regionIndex = 0) {
  const p = [dword(version), dword(0), dword(0), byte(0), blank(4), word(2), dword(3), dword(4), byte(5)];
  if (version >= 39) p.push(byte(6));
  if (version >= 50) p.push(word(7));
  if (version >= 51) p.push(dword(0));
  else { p.push(blank(8)); if (version >= 41) p.push(blank(8)); }
  p.push(blank(version > 36 ? 8 : 4), dword(0), dword(1), dword(2), dword(3));
  if (version > 42) p.push(dword(4));
  p.push(byte(9), dword(5), dword(11), byte(4), byte(0x20), word(0));
  if (version >= 32) p.push(dword(1));
  if (version >= 34) p.push(word(10), byte(0), blank(9)); else p.push(byte(0));
  p.push(byte(0), byte(0), byte(0), blank(8), byte(0), dword(0));
  if (version >= 46) p.push(blank(8));
  if (version >= 38) p.push(blank(8));
  if (version >= 39) p.push(blank(8));
  if (version >= 44) p.push(blank(44));
  if (version >= 46) p.push(byte(0));
  p.push(byte(0), byte(0), dword(0), byte(1), byte(0), dword(0), byte(0), byte(1), byte(meshIndex));
  p.push(byte(0), byte(2), byte(0), byte(0), byte(regionIndex), byte(0), byte(0), byte(0), dword(0), byte(0));
  if (version >= 42) p.push(byte(0));
  if (version >= 49) p.push(byte(0));
  if (version >= 52) p.push(byte(0));
  const fields = Buffer.concat(p); fields.writeUInt32LE(fields.length - 8, 4);
  const table = Buffer.alloc(1 + 4 * 16); table[0] = 4;
  table.writeBigUInt64LE(0x11n, 17); table.writeUInt32LE(0x22, 25); table.writeUInt32LE(0x015a1849, 29);
  table.writeBigUInt64LE(0x33n, 33); table.writeUInt32LE(0x44, 41); table.writeUInt32LE(0x2f7d0004, 45);
  table.writeBigUInt64LE(0x55n, 49); table.writeUInt32LE(0x66, 57); table.writeUInt32LE(0x1234, 61);
  return Buffer.concat([fields, table]);
}

for (const version of [31, 32, 52]) test(`CASP v${version} resolves role-bearing indexes`, () => {
  const parsed = parseCasp(sample(version));
  assert.equal(parsed.status, 'parsed-candidate');
  assert.equal(parsed.bodyType, 5);
  assert.equal(parsed.species, version >= 32 ? 1 : null);
  const mesh = parsed.roles.find(item => item.role === 'mesh');
  assert.equal(mesh.key, '015A1849:00000022:0000000000000011');
  assert.equal(mesh.lod, 0);
  assert.equal(parsed.roles.find(item => item.role === 'diffuse').key, '2F7D0004:00000044:0000000000000033');
});

test('CASP rejects truncated, misplaced, malformed and invalid reference data', () => {
  const bytes = sample(52);
  for (let n = 0; n < bytes.length; n++) assert.throws(() => parseCasp(bytes.subarray(0, n)));
  assert.throws(() => parseCasp(sample(52, 4)), /reference index/);
  const malformed = Buffer.from(bytes); malformed[12] = 0xff;
  assert.throws(() => parseCasp(malformed));
  const future = Buffer.from(bytes); future.writeUInt32LE(53, 0);
  assert.equal(parseCasp(future).status, 'unsupported-version');
});

test('version 52 roles agree with the recovered independent CASP parser', { skip: !process.env.S4PY_PYTHON }, () => {
  const bytes = sample(52), ours = parseCasp(bytes);
  const bridge = fileURLToPath(new URL('./casp_oracle.py', import.meta.url));
  const patch = fileURLToPath(new URL('../../examples/pinned-casp-resource-candidate.patch', import.meta.url));
  const oracle = JSON.parse(execFileSync(process.env.S4PY_PYTHON, ['-B', bridge, patch],
    { input: bytes, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }));
  assert.equal(ours.bodyType, oracle.body_type);
  assert.equal(ours.species, oracle.species);
  assert.equal(ours.roles.find(item => item.role === 'diffuse').key, oracle.texture);
  assert.equal(ours.roles.find(item => item.role === 'mesh').key, oracle.lods[0].geometries[0]);
});

test('inspection CLI connects parsed mesh and texture roles to package candidates', async () => {
  const caspBytes = sample(52, 1, 3), geom = Buffer.from('mesh'), texture = Buffer.from('texture');
  const meshKey = Buffer.alloc(16); meshKey.writeBigUInt64LE(0x11n); meshKey.writeUInt32LE(0x015a1849, 8); meshKey.writeUInt32LE(0x22, 12);
  const region = Buffer.concat([dword(3), dword(0), dword(0), dword(0), dword(0), dword(1), dword(1),
    dword(7), dword(0), byte(1), dword(1), meshKey]);
  const payloads = [caspBytes, geom, texture, region];
  const keys = [[0x034aeecb, 0, 0, 1], [0x015a1849, 0x22, 0, 0x11], [0x2f7d0004, 0x44, 0, 0x33], [0x1234, 0x66, 0, 0x55]];
  let pos = 96;
  const rows = [];
  for (let i = 0; i < keys.length; i++) {
    rows.push(...keys[i].map(dword), dword(pos), dword(payloads[i].length), dword(payloads[i].length));
    pos += payloads[i].length;
  }
  const index = Buffer.concat([dword(0), ...rows]);
  const header = Buffer.alloc(96); header.write('DBPF'); header.writeUInt32LE(2, 4); header.writeUInt32LE(1, 8);
  header.writeUInt32LE(4, 36); header.writeUInt32LE(index.length, 44); header.writeUInt32LE(pos, 64);
  const dir = await mkdtemp(path.join(os.tmpdir(), 'cas-role-integration-'));
  try {
    const filename = path.join(dir, 'synthetic.package');
    await writeFile(filename, Buffer.concat([header, ...payloads, index]));
    const cli = fileURLToPath(new URL('./inspect.mjs', import.meta.url));
    const output = JSON.parse(execFileSync(process.execPath, [cli, '034AEECB:00000000:0000000000000001', filename], { encoding: 'utf8' }));
    assert.equal(output.parsed.status, 'parsed-candidate');
    assert.equal(output.parsed.roleCandidates.find(item => item.role === 'mesh').status, 'unique-in-supplied-indexes');
    assert.equal(output.parsed.roleCandidates.find(item => item.role === 'diffuse').status, 'unique-in-supplied-indexes');
    assert.equal(output.parsed.regionBinding.status, 'parsed-candidate');
    assert.equal(output.parsed.regionBinding.meshes[0].state, 'matched');
    assert.equal(output.parsed.regionBinding.meshes[0].regions[0].region, 7);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('old and recent synthetic CASPs agree with the independent C# reader', { skip: !(process.env.CASP_ORACLE_DLL && process.env.DOTNET_BIN) }, () => {
  for (const version of [31, 32, 52]) {
    assert.equal(compareCaspReference(sample(version), process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL).meshReferences, 1);
  }
});
