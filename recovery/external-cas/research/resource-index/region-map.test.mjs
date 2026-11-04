// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseRegionMap, mapMeshRegions } from './region-map.mjs';
import { compareRegionReference } from './region-reference.mjs';

const dword = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n); return b; };
const flt = n => { const b = Buffer.alloc(4); b.writeFloatLE(n); return b; };
const key = (instance, type, group) => { const b = Buffer.alloc(16); b.writeBigUInt64LE(instance); b.writeUInt32LE(type, 8); b.writeUInt32LE(group, 12); return b; };
function fixture() {
  return Buffer.concat([dword(3), dword(0), dword(0), dword(0), dword(0), dword(1), dword(2),
    dword(7), flt(1.25), Buffer.from([1]), dword(1), key(0x1122334455667788n, 0x015a1849, 0x12345678),
    dword(8), flt(-0.5), Buffer.from([0]), dword(0)]);
}
test('region map retains all block metadata and unsigned mesh keys', () => {
  const parsed = parseRegionMap(fixture());
  assert.equal(parsed.status, 'parsed-candidate');
  assert.deepEqual(parsed.blocks, [
    { region: 7, layer: 1.25, replacement: 1, keys: ['015A1849:12345678:1122334455667788'] },
    { region: 8, layer: -0.5, replacement: 0, keys: [] },
  ]);
});
test('region map rejects truncation, excessive counts and nonfinite layers', () => {
  const bytes = fixture();
  for (let i = 0; i < bytes.length; i++) assert.throws(() => parseRegionMap(bytes.subarray(0, i)));
  const excessive = Buffer.from(bytes); excessive.writeUInt32LE(1025, 4);
  assert.throws(() => parseRegionMap(excessive), /count limit/);
  const badLayer = Buffer.from(bytes); badLayer.writeFloatLE(Infinity, 32);
  assert.throws(() => parseRegionMap(badLayer), /layer/);
  assert.throws(() => parseRegionMap(Buffer.concat([bytes, Buffer.from([1])])), /trailing/);
  const other = Buffer.from(bytes); other.writeUInt32LE(4, 0);
  assert.equal(parseRegionMap(other).status, 'unsupported-context');
  const version = Buffer.from(bytes); version.writeUInt32LE(2, 20);
  assert.equal(parseRegionMap(version).status, 'unsupported-version');
});
test('synthetic region blocks match the independent C# reader', { skip: !(process.env.CASP_ORACLE_DLL && process.env.DOTNET_BIN) }, () => {
  assert.deepEqual(compareRegionReference(fixture(), process.env.DOTNET_BIN, process.env.CASP_ORACLE_DLL), { blocks: 2, meshReferences: 1 });
});
test('renderer-facing bindings preserve all matches and leave unknown meshes unmapped', () => {
  const map = parseRegionMap(fixture());
  map.blocks.push({ region: 9, layer: 2, replacement: 0, keys: [...map.blocks[0].keys] });
  const casp = { status: 'parsed-candidate', roles: [
    { role: 'mesh', lod: 0, key: map.blocks[0].keys[0] },
    { role: 'mesh', lod: 1, key: 'missing' },
  ] };
  const bindings = mapMeshRegions(casp, map);
  assert.deepEqual(bindings[0].regions, [
    { region: 7, layer: 1.25, replacement: 1 }, { region: 9, layer: 2, replacement: 0 },
  ]);
  assert.equal(bindings[0].state, 'matched');
  assert.equal(bindings[1].state, 'unmapped');
  assert.throws(() => mapMeshRegions(casp, { status: 'unsupported' }), /unavailable/);
});
