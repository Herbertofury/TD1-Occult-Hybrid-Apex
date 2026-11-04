# Bounded large-package reader

`large_package.py` is an isolated Python integration candidate. It reads DBPF
2.1 headers and indexes from one open descriptor and retrieves only explicitly
selected resources. It does not read the entire package into memory or write
assets, and it does not choose between package sources or resource types.

```python
from large_package import PinnedPackage, parse_tgi

# The caller supplies a previously verified catalog digest and exact TGI.
key = parse_tgi(catalog_row['resource_tgi'])
with PinnedPackage(package_path, expected_sha256) as package:
    matches = package.resolve_many([key])[key]
    # The caller must retain ambiguity and resolve source precedence separately.
    if len(matches) != 1:
        raise ValueError('resource missing or ambiguous')
    payload = package.read_many([key])[key]
```

This is **not** a drop-in replacement for the preview worker's existing
`Package(path, 'mod')` or its `.entries` dictionary. The worker must pass the
catalog's whole-file digest and known TGI, replace whole-index enumeration with
streamed `iter_rows` or bounded exact-key resolution, and retain its own
source-selection and provenance checks. A large package is accepted by this
module only; existing preview preflight and preparation stages still contain
64 MiB package-file checks and need coordinated changes before the user-facing
pipeline supports it. No renderer-worker files were changed here.

Limits are 8 GiB per package, 250,000 index rows, 128 MiB declared index size,
128 selected keys, and 32 candidate rows per key. Index rows are scanned rather
than materialized; duplicate keys remain visible and `read_many` refuses them.
The selected-resource accounting budget is 64 MiB, charging stored bytes plus
one expanded copy for uncompressed data, or two for zlib/RefPack. The latter
accounts for observed temporary Python zlib allocation and RefPack conversion.
This accounting bound is not an RSS limit: interpreter, allocator, zlib, OS
cache and caller-retained buffers consume additional memory. Every hash read is
at most 1 MiB; an individual selected stored payload read may be larger within
the selected budget. Unknown compression, unsupported storage, tombstones,
trailing/malformed streams, truncated input and oversized selections fail
explicitly. RefPack and zlib are bounded; DBPF versions and index flags not
implemented here remain unsupported.

The reader requires a caller-provided, lowercase whole-file SHA-256, hashes the
open descriptor at initialization and again before returning each selected
batch, and checks file metadata around operations. This can be expensive on
multi-gigabyte files and is not performance-qualified for interactive use.
Only one operation can use a package instance at once; an `iter_rows` consumer
must exhaust or close the iterator before another operation. The checks detect
ordinary replacement and modification but do not create an atomic filesystem
snapshot against a malicious concurrent writer that restores state. Use stable,
trusted files and do not treat an index-only discovery digest as payload identity.

## Verification

On Windows, 13 Python regression tests passed with the independent s4py reader
enabled. They cover all index sharing masks, a 70 MiB sparse package, a 200,000
row index, a 24 MiB expanded zlib resource, duplicate/missing keys, unsupported
compression and tombstones, changed source, concurrent cursor access, malformed
index extents, truncated and oversized compressed streams, and overlapping
RefPack backreferences. Python `tracemalloc` peak was below 8 MiB for the sparse
package and 200,000-row index tests, and below 56 MiB while extracting the
24 MiB zlib sample. These figures do not include total process RSS or OS cache.

For a 754,360,553-byte installed package containing 105,457 rows, one CASP,
one GEOM and one RIG record matched s4py's exact key, offsets, sizes,
compression, storage marker and decoded-payload SHA-256. For a separate
1,011,045,915-byte installed package containing 14,589 rows, one RLE2 and one
RLES record matched the same fields and payload hashes. In those small-selection
comparisons Python traced peaks were approximately 2.3 MiB and the largest
individual read was 1 MiB. One separate third-party tuning package outside the
protected profile also yielded a matching record; it is not an appearance-CC
compatibility test. The samples do not validate every resource or compression
variant. No resource bytes, private identities or source paths are included here.

`compare-large-private.py` accepts one explicit path, compares bounded selected
rows against the independent s4py bridge and prints aggregate evidence only.
Set `S4PY_ROOT`, `S4PY_PYTHON` and, on Windows, `CAS_LOW_PRIORITY=1`. Run
`python -B -m unittest -v test_large_package` from this directory to repeat the
synthetic tests. `scan-large-categories-private.mjs` performs index-only
discovery and must not authorize payload retrieval.

## Rig and precedence gate

The previously compared installed rigs remain ambiguous: multiple human-age
fixtures share bone order and hierarchy, while their full/delta package entries
differ. TS4CAS Tools' own [age/species selection code](https://github.com/CmarNYC-Tools/TS4CASTools/blob/67d00ebb9016092b8f64ef94ec7ffb5329cf3342/src/CASTools/Form1.cs)
selects distinct human infant, toddler, child and adult fixtures; it is
third-party tool behavior, not proof of the running game's selected source.
The installation configuration records full and delta priorities, but this
work does not establish game winner semantics or current Sim age/species.
Keep all candidates until both source precedence and applicable rig are
independently established. The game/live state and protected profile were not
accessed for these checks.
