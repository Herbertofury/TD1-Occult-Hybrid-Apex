// Installation metadata only. Never reads package contents or the user profile.
import { readdir, lstat } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const packName = /^(?:EP|GP|SP|FP)\d{2}$/i;
const categories = ['client_full', 'client_delta', 'clip_header', 'simulation', 'strings', 'thumbnails', 'ui', 'other'];

function kind(name) {
  if (/^ClientFullBuild\d+\.package$/i.test(name)) return 'client_full';
  if (/^ClientDeltaBuild\d+\.package$/i.test(name)) return 'client_delta';
  if (/^ClipHeader\.package$/i.test(name)) return 'clip_header';
  if (/^Simulation.*\.package$/i.test(name)) return 'simulation';
  if (/^Strings_.*\.package$/i.test(name)) return 'strings';
  if (/^thumbnails.*\.package$/i.test(name)) return 'thumbnails';
  if (/^UI.*\.package$/i.test(name)) return 'ui';
  return 'other';
}

async function safeDirectory(dir) {
  const stat = await lstat(dir);
  if (stat.isSymbolicLink() || !stat.isDirectory()) throw new Error('Expected a non-link directory');
}

export async function inventory(root) {
  root = path.resolve(root);
  await safeDirectory(root);
  // Require the installation layout, not an arbitrary directory such as Mods.
  for (const rel of ['Data', path.join('Data', 'Client'), 'Game']) await safeDirectory(path.join(root, rel));
  const totals = Object.fromEntries(categories.map(name => [name, { files: 0, bytes: 0 }]));
  const groups = { base: 0, packs: 0, delta: 0 };
  let skippedLinks = 0;
  let errors = 0;
  async function scan(dir, group) {
    try {
      await safeDirectory(dir);
      const entries = await readdir(dir, { withFileTypes: true });
      groups[group]++;
      for (const entry of entries) {
        if (entry.isSymbolicLink()) { skippedLinks++; continue; }
        if (!entry.isFile() || !/\.package$/i.test(entry.name)) continue;
        try {
          // lstat again so a replaced entry is not followed.
          const st = await lstat(path.join(dir, entry.name));
          if (!st.isFile() || st.isSymbolicLink()) { skippedLinks++; continue; }
          const row = totals[kind(entry.name)];
          row.files++;
          row.bytes += st.size;
        } catch { errors++; }
      }
    } catch { errors++; }
  }
  for (const part of ['Client', 'Shared', 'Simulation']) await scan(path.join(root, 'Data', part), 'base');
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (packName.test(entry.name)) {
      if (entry.isSymbolicLink()) skippedLinks++;
      else if (entry.isDirectory()) await scan(path.join(root, entry.name), 'packs');
    }
  }
  const delta = path.join(root, 'Delta');
  try {
    await safeDirectory(delta);
    for (const entry of await readdir(delta, { withFileTypes: true })) {
      if (packName.test(entry.name)) {
        if (entry.isSymbolicLink()) skippedLinks++;
        else if (entry.isDirectory()) await scan(path.join(delta, entry.name), 'delta');
      }
    }
  } catch { errors++; }
  return { schema: 1, scope: 'direct package files in base Data and pack/delta directories', groups, totals, skippedLinks, errors };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  if (process.argv.length !== 3) {
    console.error('Usage: node inventory.mjs <game-install-directory>');
    process.exitCode = 2;
  } else {
    try {
      const result = await inventory(process.argv[2]);
      console.log(JSON.stringify(result, null, 2));
      if (result.errors) process.exitCode = 1;
    } catch (error) {
      console.error(`Inventory failed: ${error.message}`);
      process.exitCode = 1;
    }
  }
}
