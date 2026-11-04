import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm, symlink } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { inventory } from './inventory.mjs';

test('counts direct installation packages without following nested content', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'cas-inventory-'));
  try {
    for (const dir of ['Data/Client', 'Data/Shared', 'Data/Simulation', 'Game', 'EP01/nested', 'Delta/EP01']) {
      await mkdir(path.join(root, dir), { recursive: true });
    }
    for (const [name, content] of [
      ['Data/Client/ClientFullBuild0.package', 'abc'],
      ['Data/Client/UI.package', 'ui'],
      ['EP01/Strings_ENG_US.package', 'word'],
      ['EP01/nested/ClientFullBuild1.package', 'ignored'],
      ['Delta/EP01/ClientDeltaBuild0.package', 'd'],
      ['Data/Client/not-a-package.txt', 'ignored'],
    ]) await writeFile(path.join(root, name), content);
    const result = await inventory(root);
    assert.deepEqual(result.groups, { base: 3, packs: 1, delta: 1 });
    assert.deepEqual(result.totals.client_full, { files: 1, bytes: 3 });
    assert.deepEqual(result.totals.client_delta, { files: 1, bytes: 1 });
    assert.deepEqual(result.totals.ui, { files: 1, bytes: 2 });
    assert.deepEqual(result.totals.strings, { files: 1, bytes: 4 });
    assert.equal(result.errors, 0);
    assert.equal(JSON.stringify(result).includes(root), false);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test('rejects a directory lacking an installation layout', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'cas-inventory-'));
  try { await assert.rejects(inventory(root)); }
  finally { await rm(root, { recursive: true, force: true }); }
});

test('does not follow a linked pack directory where links are supported', async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'cas-inventory-'));
  try {
    for (const dir of ['Data/Client', 'Data/Shared', 'Data/Simulation', 'Game', 'Delta', 'outside']) {
      await mkdir(path.join(root, dir), { recursive: true });
    }
    await writeFile(path.join(root, 'outside', 'ClientFullBuild0.package'), 'secret');
    try { await symlink(path.join(root, 'outside'), path.join(root, 'EP01'), 'dir'); }
    catch (error) { if (['EPERM', 'EACCES', 'ENOTSUP'].includes(error.code)) return t.skip('symlink unavailable'); throw error; }
    const result = await inventory(root);
    assert.equal(result.skippedLinks, 1);
    assert.equal(result.totals.client_full.files, 0);
  } finally { await rm(root, { recursive: true, force: true }); }
});
