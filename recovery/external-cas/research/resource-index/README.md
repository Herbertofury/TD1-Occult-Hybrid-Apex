# Read-only resource index and CASP reference candidate

This is isolated research code, not an integrated CAS loader. It opens only
explicitly supplied files and writes no files. It can index DBPF 2.1 package
metadata, read bounded uncompressed, zlib or RefPack payloads, inspect a CASP reference
table, and report matching candidates from an explicitly supplied package
set. It does not modify the source packages or contact the game.

```powershell
node --test dbpf.test.mjs casp.test.mjs region-map.test.mjs
node inspect.mjs 034AEECB:00000000:0123456789ABCDEF C:\private\first.package C:\private\second.package
```

The second command is an example syntax, not a request to inspect those paths.
The caller must provide an uppercase CASP TGI and 1–16 explicit packages.
Results on stdout include resource keys, package SHA-256 fingerprints, source
sizes and index metadata. Treat that output as private; do not publish game or
creator data. No payload bytes are printed. A full package fingerprint is
computed by streaming, and selected-resource retrieval reindexes and hashes
again before reading and rehashes once more on the reopened handle. This is
intentionally expensive for safety and has not been performance-qualified for
large installation scans. Use only stable, trusted source files. The stat and
hash checks detect ordinary changes but do not create an atomic filesystem
snapshot against concurrent mutation.

## Scope and conservative behavior

- The index retains full unsigned type/group/instance keys, ordinal, byte
  extents, declared sizes, compression and storage markers, tombstone status,
  and content-derived package identity. Duplicate keys are retained.
- Index flags 0–7 are supported, with 250,000 entries, 128 MiB index and 64 MiB
  stored/decompressed payload limits per read. Resolution is also limited to
  250,000 total rows across the supplied package set. Other DBPF versions, unknown
  flags, malformed extents, trailing index data and exceeded limits fail closed.
  Unknown compression or storage markers remain indexed and return an explicit
  unsupported status. Tombstones are reported instead of loaded.
- CASP versions `0x1F` through `0x34` can receive a bounded role-bearing
  inspection for mesh LODs and texture, material-related and other references.
  The older table-only view is retained. Reference roles and metadata remain
  candidates; they are not proof of renderer readiness or applicability. Future
  versions, unexplained fields, malformed offsets and bad indexes fail closed.
- A bounded region-map parser retains mesh keys, region IDs, layers and raw
  replacement flags. The inspection command maps all matching region entries
  to each CASP mesh, retaining multiple matches and marking unmapped meshes.
  This is a renderer-facing data candidate, not visibility, layer precedence,
  replacement semantics or proof of an actual rendered scene. Region-map object
  offset metadata is retained without claiming to validate its meaning.
- Resolution returns `empty`, `missing`, `ambiguous`, or
  `unique-in-supplied-indexes`, including all source candidates. A unique match
  only describes the explicitly supplied set. This code does not claim the set
  is complete, apply game or mod load precedence, interpret tombstone overrides,
  or establish that a resource is compatible or renderable.

## Verification and source basis

On Windows with Node 22.23.2, twenty-three tests passed. They cover all eight index
shared-field masks, both index offset fields, large unsigned instances, mixed
compression and deletion markers, bad extents/flags, changed package bytes,
forged locators, ambiguous/missing/empty references, and a synthetic CLI flow.
One test compared the generated package indexes against the independently
obtained [s4py DBPF reader](https://github.com/thequux/s4py/blob/892150e78cfd0b6ca51258d5e0d740eb9adffcd1/lib/s4py/package/dbpf.py)
at commit `892150e78cfd0b6ca51258d5e0d740eb9adffcd1`. Its unused YAML
representer registration was stubbed in the test bridge; no reference parser
logic was substituted. To repeat the optional comparison, set `S4PY_ROOT` to
that checkout's `lib` directory and `S4PY_PYTHON` to a Python executable before
running the tests. Without these variables the comparison is skipped.

The CASP table location and I64/group/type ordering were researched against
[TS4CAS Tools' CASP implementation](https://github.com/CmarNYC-Tools/TS4CASTools/blob/main/src/XmodsDataLib/CASP.cs).
The CASP role parser and its integration/test bridges are GPL-3.0-or-later
research code, with provenance from that implementation and the already retained
`examples/pinned-casp-resource-candidate.patch`. The oracle bridge executes the
retained GPL patch and supplies a bounded reader shim. Retain the applicable GPL
license and notices when integrating; see `examples/LICENSE-GPL-3.0-POSE-TOOLS.txt`.
Synthetic checks alone do not establish CASP role correctness. See
`INSTALLED-SAMPLE.md` for the narrowly bounded installed-package comparison.

For an additional independent comparison, `reference-bridge/` builds against
separately obtained TS4CAS Tools source at commit
`67d00ebb9016092b8f64ef94ec7ffb5329cf3342`; the upstream GPL source is not
vendored here. Supply its `src/XmodsDataLib` directory as the MSBuild property
`CaspToolsSrc`, use the included `NuGet.Config` to avoid package feeds, and direct
the build output and intermediate files to an isolated temporary directory. Set
`CASP_ORACLE_DLL` to the resulting `oracle.dll` and `DOTNET_BIN` to `dotnet` to
enable the C# oracle tests. These compare parsed fields and region blocks in
memory. They do not compare the final game rendering.

## Next gates

Compare broader samples from the installed version against independent tools,
including authorized CC outside the protected original profile. Confirm resource
extents, compression, CASP table layout and reference semantics across versions.
Resolve priority and source coverage from actual configured game/mod loading,
with explicit conflict handling. Broaden validation of role-bearing CASP fields,
then decode cross-package geometry, textures, rigs,
morphs, materials and poses before feeding the renderer. The present prototype
does not implement those decoders, game synchronization, a native Tray writer,
or in-game visual validation.
