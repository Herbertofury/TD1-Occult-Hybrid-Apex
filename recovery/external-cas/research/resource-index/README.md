# Read-only resource index and CASP reference candidate

This is isolated research code, not an integrated CAS loader. It opens only
explicitly supplied files and writes no files. It can index DBPF 2.1 package
metadata, read bounded uncompressed, zlib or RefPack payloads, inspect a CASP reference
table, and report matching candidates from an explicitly supplied package
set. It does not modify the source packages or contact the game.

```powershell
node --test dbpf.test.mjs casp.test.mjs region-map.test.mjs geom.test.mjs material.test.mjs palette.test.mjs rle2.test.mjs rig.test.mjs
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
- `scanPackageIndex` reads headers and indexes for discovery only. Its index
  digest does not identify all package bytes and cannot authorize payload reads;
  a selected file must be fully indexed and verified. Discovery establishes
  neither package precedence nor equivalence between resource types.
- Bounded batch reads verify one indexed source for up to 128 distinct selected
  records, retaining order and limiting total stored and expanded bytes to 64 MiB.
  All locators are checked before payloads are returned; an invalid record aborts
  the batch. This reduces repeated hashing but is not a whole-installation cache.
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
- The GEOM candidate reads bounded positions, normals, UVs, raw bone assignment
  and byte-weight fields, and triangle indices for supported RCOL layouts and
  GEOM versions 12-15. Version 12 also exposes candidate stitch metadata, bone
  palettes and raw weight mappings; palettes in versions 13-15 are unsupported.
  No skeleton or transforms are selected. Known MTNF/MTRL texture fields yield
  candidate TGI references; unknown fields and missing indices remain explicit.
- `decodeRle2` and `decodeRles` produce bounded BC3 candidates, and `decodeBc3`
  produces RGBA pixels. RLES preserves unused stream bytes, whose purpose is
  unverified; the candidate is not a complete material interpretation. Other
  texture formats remain unsupported. Decoding does not establish shader,
  color-space or in-game appearance equivalence.
- `parseRig` reads bounded version 3.1 rig candidates, retaining raw transforms,
  hierarchy and chains. `bindPalette` maps hashes to all matches without choosing
  a skeleton; `bindVertexWeights` links raw weights only after unique mapping.
  `computeBindMatrices` produces row-major local, global and inverse
  matrices only for unit scales and sufficiently normalized (or empty)
  quaternions; other inputs are explicit unsupported cases. These are research
  candidates, not validated game-space skinning or animation.
- Resolution returns `empty`, `missing`, `ambiguous`, or
  `unique-in-supplied-indexes`, including all source candidates. A unique match
  only describes the explicitly supplied set. This code does not claim the set
  is complete, apply game or mod load precedence, interpret tombstone overrides,
  or establish that a resource is compatible or renderable.

## Verification and source basis

On Windows with Node 22.23.2, 46 tests passed with optional independent readers enabled. They cover all eight index
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
enable the C# oracle tests. These compare parsed fields, region blocks, rig
fields and supported local/global matrix candidates in memory. The rig reader
and bridge retain GPL-3.0-or-later provenance from `XmodsDataLib/RIG.cs` and
`Rotations.cs`. They do not compare final game rendering.

The geometry oracle bridge imports the independently obtained
[Blender GEOM reader](https://github.com/blancodagoat/blender-sims4-geom/tree/551b560e9e3929a9f840f787be3cfba91da149d7)
at commit `551b560e9e3929a9f840f787be3cfba91da149d7` without loading Blender.
It compares in-memory positions, normals, first UVs and indices via a private
digest, and compares recognized material reference indices. The reader's source
is GPL-3.0-or-later; the GEOM, material and comparison files retain that
provenance. Set `GEOM_ORACLE_ROOT` to its `io_simgeom` directory and
`GEOM_ORACLE_PYTHON` to a compatible Python executable to enable the optional
geometry oracle test. The unmodified Blender reader expects a seam count in
version 12 and disagreed on the sample palette. Inserting a zero seam count in
an in-memory copy and adjusting offsets yielded a matching palette; this is not
an unmodified-reader validation. Raw weights agree without normalization.
Neither game assets nor oracle source are vendored here.

The RLE bridge independently executes the Blender add-on converter at the commit
above and Pillow 11.3.0's BC3 decoder. Set `RLE_ORACLE_SOURCE` to its
`io_simgeom/io/package_import.py`, `RLE_ORACLE_PYTHON` to Python, and
`PILLOW_ORACLE_ROOT` to a private Pillow installation. Synthetic blocks and
selected installed textures matched by private digest. The RLE and palette research code
retains GPL-3.0-or-later provenance; retain license notices when integrating.

## Next gates

Compare broader samples from the installed version against independent tools,
including authorized CC outside the protected original profile. Confirm resource
extents, compression, CASP table layout and reference semantics across versions.
Resolve priority and source coverage from actual configured game/mod loading,
with explicit conflict handling. Broaden validation of role-bearing CASP and
GEOM fields and supported texture and palette decoding; validate skeleton
selection and binding, remaining texture semantics, morphs and poses before renderer parity.
The present prototype does not provide a complete renderer,
game synchronization, a native Tray writer, or in-game visual validation.
