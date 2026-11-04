// SPDX-License-Identifier: GPL-3.0-or-later
// Read-only in-memory aggregate comparison against an explicit binary rig.
import os from 'node:os';
import { readFile, stat } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { indexPackage, readResource, resolveReferences } from './dbpf.mjs';
import { parseCasp } from './casp.mjs';
import { parseGeom } from './geom.mjs';
import { parseRig, computeBindMatrices, deriveSkinMatrices } from './rig.mjs';
import { decodeRle2, decodeBc3 } from './rle2.mjs';
import { assessMesh, assessRgba, projectApxCandidate } from './renderer-compat.mjs';
if (process.env.CAS_LOW_PRIORITY === '1') os.setPriority(0, os.constants.priority.PRIORITY_LOW);
const paths = process.argv.slice(2);
if (paths.length !== 3) throw new Error('supply CASP package, mesh/texture package and explicit rig');
const info = await stat(paths[2]); if (!info.isFile() || info.size > 16 * 1024 * 1024) throw new Error('rig extent');
const rig = parseRig(await readFile(paths[2])), indexes = [await indexPackage(paths[0]), await indexPackage(paths[1])];
const root = indexes[0].rows.find(row => row.key.startsWith('034AEECB:') && !row.deleted);
const casp = parseCasp((await readResource(paths[0], indexes[0], root.ordinal)).payload);
const roles = ['mesh', 'diffuse'].map(role => casp.roles.find(item => item.role === role));
const refs = resolveReferences(roles, indexes);
const payloads = [];
for (const ref of refs) {
  if (ref.status !== 'unique-in-supplied-indexes') throw new Error('reference not uniquely resolved');
  const c = ref.candidates[0], n = indexes.findIndex(index => index.source.sha256 === c.source.sha256);
  payloads.push((await readResource(paths[n], indexes[n], c.row.ordinal)).payload);
}
const geom = parseGeom(payloads[0]), texture = decodeRle2(payloads[1]);
if (texture.status !== 'decoded-bc3') throw new Error('unsupported diffuse texture');
const rgba = decodeBc3(texture.width, texture.height, texture.mips[0].bc3);
const report = { mesh: assessMesh(geom, rig), diffuse: assessRgba(texture.width, texture.height, rgba) };
if (process.env.APX_VALIDATOR_BIN) {
  const text = `${rig.bones.length}\n${rig.bones.map(bone => [bone.hash, bone.parentIndex, ...bone.position, ...bone.orientation, ...bone.scale].join(' ')).join('\n')}\n`;
  const candidate = projectApxCandidate(geom, rig, text);
  report.meshProjection = { status: candidate.status, textSource: 'derived-from-explicit-fixture', gameFidelity: 'unverified' };
  if (candidate.status === 'apxmesh-candidate') {
    const result = execFileSync(process.env.APX_VALIDATOR_BIN, [], { input: candidate.bytes, encoding: 'utf8', maxBuffer: 1024 }).trim();
    report.meshProjection.rendererValidator = result === `accepted ${geom.vertices.length} ${geom.indices.length}` ? 'accepted' : 'unexpected-response';
    if (process.env.APX_SKIN_VALIDATOR_BIN) {
      const bind = computeBindMatrices(rig, { scaleTolerance: 1e-6 });
      const skin = deriveSkinMatrices(bind, bind.global);
      report.restSkinning = { bindStatus: bind.status, skinStatus: skin.status, nativeFidelity: 'unverified' };
      if (skin.matrices) {
        const header = Buffer.alloc(4); header.writeUInt32LE(candidate.bytes.length);
        function runSkin(matrices) {
          const matrix = Buffer.alloc(matrices.length * 48);
          matrices.forEach((values, i) => values.forEach((v, j) => matrix.writeFloatLE(v, i * 48 + j * 4)));
          const result = execFileSync(process.env.APX_SKIN_VALIDATOR_BIN, [], { input: Buffer.concat([header, candidate.bytes, matrix]), encoding: 'utf8', maxBuffer: 1024 }).trim().split(' ');
          if (result.length !== 4 || result[0] !== 'accepted' || Number(result[1]) !== geom.vertices.length || !Number.isFinite(Number(result[2])) || !Number.isFinite(Number(result[3]))) throw new Error('skin bridge response');
          return result;
        }
        const result = runSkin(skin.matrices);
        report.restSkinning.rendererValidator = 'accepted';
        report.restSkinning.maxPositionDelta = Number(result[2]); report.restSkinning.maxNormalDelta = Number(result[3]);
        const movedGlobals = bind.global.map(world => { const next = [...world]; next[3] += 0.0125; next[7] -= 0.025; next[11] += 0.05; return next; });
        const moved = deriveSkinMatrices(bind, movedGlobals);
        if (moved.matrices) {
          const movedResult = runSkin(moved.matrices), delta = Number(movedResult[2]);
          report.translationProbe = { kind: 'synthetic-whole-rig-translation', status: Math.abs(delta - 0.05) < 1e-6 ? 'matched-expected-displacement' : 'disagreed',
            maxPositionDelta: delta, maxNormalDelta: Number(movedResult[3]), nativeFidelity: 'unverified' };
        }
      }
    }
  }
}
console.log(JSON.stringify(report));
