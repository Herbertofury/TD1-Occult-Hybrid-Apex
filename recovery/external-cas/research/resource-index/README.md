# Read-only resource index and CASP reference candidate

This is isolated research code, not an integrated CAS loader. It opens only
explicitly supplied files and writes no files. It can index DBPF 2.1 package
metadata, read bounded uncompressed or zlib payloads, inspect a CASP reference
table, and report matching candidates from an explicitly supplied package
set. It does not modify the source packages or contact the game.

```powershell
node --test dbpf.test.mjs
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
- CASP versions `0x20` through `0x34` receive a **table-only** inspection. Its
  TGI entries are candidates, not proven required dependencies: the parser does
  not decode version-specific fields that assign mesh, texture, LOD, material,
  age or species roles. A future version is reported as unsupported. Table
  extent mismatches fail closed.
- Resolution returns `empty`, `missing`, `ambiguous`, or
  `unique-in-supplied-indexes`, including all source candidates. A unique match
  only describes the explicitly supplied set. This code does not claim the set
  is complete, apply game or mod load precedence, interpret tombstone overrides,
  or establish that a resource is compatible or renderable.

## Verification and source basis

On Windows with Node 22.23.2, nine tests passed. They cover all eight index
shared-field masks, both index offset fields, large unsigned instances, mixed
compression and deletion markers, bad extents/flags, changed package bytes,
forged locators, ambiguous/missing/empty references, and a synthetic CLI flow.
The last test compared the generated package indexes against the independently
obtained [s4py DBPF reader](https://github.com/thequux/s4py/blob/892150e78cfd0b6ca51258d5e0d740eb9adffcd1/lib/s4py/package/dbpf.py)
at commit `892150e78cfd0b6ca51258d5e0d740eb9adffcd1`. Its unused YAML
representer registration was stubbed in the test bridge; no reference parser
logic was substituted. To repeat the optional comparison, set `S4PY_ROOT` to
that checkout's `lib` directory and `S4PY_PYTHON` to a Python executable before
running the tests. Without these variables the comparison is skipped.

The CASP table location and I64/group/type ordering were researched against
[TS4CAS Tools' CASP implementation](https://github.com/CmarNYC-Tools/TS4CASTools/blob/main/src/XmodsDataLib/CASP.cs).
The implementation here is separately written and retains no third-party source
or assets. The comparison uses synthetic packages only: it establishes neither
current-game compatibility nor CASP role correctness. No running game, user
profile or installed package was accessed for this candidate.

## Next gates

After the parent coordinates access, compare bounded samples from the installed
version against independent tools, including real base/pack/delta and authorized
CC sources. Confirm resource extents, compression, CASP table layout and
reference semantics across versions. Resolve priority and source coverage from
actual configured game/mod loading, with explicit conflict handling. Decode
and validate role-bearing CASP fields, cross-package geometry, textures, rigs,
morphs, materials and poses before feeding the renderer. The present prototype
does not implement those decoders, game synchronization, a native Tray writer,
or in-game visual validation.
