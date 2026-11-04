# Bounded installation comparison, 2026-11-04

Ten explicitly selected, small installed base, pack and delta packages were
opened read-only. They had 29,879 indexed rows in total. Every row's key,
offset, stored and memory size, compression marker, committed marker and
deleted state matched the independently obtained s4py reader at the revision
named in the README. No package bytes, resource keys, hashes, generated content
or user profile data are included here.

Observed markers across those ten indexes were 29,729 zlib (`5A42`), 148
tombstones (`FFE0`), one uncompressed (`0000`) and one RefPack (`FFFF`). A
bounded decoder for `FFFF` was added. One installed RefPack payload of 4,307,230
decoded bytes had the same SHA-256 as s4py's output in a private comparison; the
payload and digest were not saved or printed. Synthetic tests exercise four
literal/backreference forms, compare output to s4py, and reject malformed input.
Other RefPack streams and `FFFE` remain unverified; `FFFE` is reported as
unsupported, not decoded by assumption.

Two actual CASP reference tables were structurally read. Within their deliberately
small set of four supplied package indexes, their entries produced 2 empty and
34 missing references. This does not prove the game lacks those resources: the
base/pack catalog is incomplete, and the table reader does not distinguish used
dependencies from other reference entries. No independent CASP semantic parser
or rendered output was used to validate those tables at that stage. A subsequent
bounded role parser compared four records (two each from overlapping client and
simulation delta packages) against the separately recovered CASP research parser.
All four comparisons agreed on selected body/species and texture-related fields,
and on 48 mesh-reference observations. The packages share many keys, so the
records may overlap; this is not four independent asset families. In the two
sampled records from those indexes, all 24 mesh-reference observations were
missing from the deliberately incomplete two-package set. No geometry was read
or rendered by that comparison.

One small pack's full and delta indexes shared 434 resource keys. Their installed
client configuration declares delta at priority -20 and full at -30; the base
client configuration also declares -20 for delta and -30 for full. This is
evidence that conflicts must be retained, not proof of the game's complete
winner selection, conditional pack loading, mod ordering or tombstone behavior.
The resolver continues to report candidates and never silently selects a winner.

The comparison harnesses emit aggregate counts only and read a maximum of four
explicit package paths per index run. `inspect.mjs`, by contrast, emits private
resource identities and source fingerprints and should not have its output
published. Full package hashing and strict index limits remain costly and need
redesign and measurement before scanning a full installation. One separately
downloaded CAS-related third-party package outside the profile had 88 rows, all
matching the independent DBPF reader. It contained no CASP rows, so appearance
CC dependency compatibility remains untested. The protected original profile
remained off limits. The running game,
saves and live state were not contacted. No in-game behavior, visual fidelity,
save correctness or game-load precedence was validated.

## Further bounded checks

Four additional small simulation packages contained 4,191 rows in total; each
index matched s4py. The sample exposed CASP version 31, previously rejected by
the candidate, so bounded support was added. Six installed CASP records from
three small packages matched selected fields and 106 mesh-reference observations
against independently compiled TS4CAS Tools source. For version 31, no species
field is present, so no species value was inferred. Synthetic versions 31, 32
and 52 also matched that reader. This remains a small sample.

Two CASPs each resolved a unique region-map candidate within their own package.
The candidate parser's four total region blocks and 13 mesh references matched
the independent reader. All 13 corresponding CASP mesh observations mapped to
region entries. The inspection path now exposes those bindings for later renderer
work and keeps unmatched or ambiguous cases explicit. It does not load mesh
geometry, decide visibility, or render the scene. Game/live state and the protected
profile were not accessed for these checks.

## Cross-package resource chain

In one small installed pack, a selected CASP's mesh, diffuse, shadow and specular
references each had a unique candidate across the supplied simulation and client
indexes. Their expanded-payload SHA-256 values matched s4py. The sampled mesh was
GEOM version 12 with 66 vertices and 72 triangles; positions, normals, first UVs
and indices matched the independent Blender GEOM reader by private digest. This
does not validate bone mapping, remaining vertex attributes or rendered output.

The same mesh's recognized material fields yielded two candidate references,
diffuse and alpha. Their indices matched the independent GEOM reader; both
resource keys were missing from that deliberately limited package pair. The CASP's
own diffuse and shadow used RLE2 resources and its specular used RLES. Their
package payloads were verified; subsequent decoding is described below.
The CASP's region map remained ambiguous across the two indexes, so no load-order
winner was selected. The samples are small and do not establish general CAS or
custom-content compatibility. No game or creator assets are included here.

## Expanded material search and decoding

A discovery-only scan of 21 selected base and pack full/delta indexes found no
exact DDS-key match for either material reference. Fourteen further selected
base indexes also had no exact match. The two material references share a group
and instance; two same-group-and-instance RLE2 entries appeared in the pack full
and delta indexes. These are alternate-type leads, not established aliases, and
no source winner was selected. The discovery digest covers index bytes only;
reading a candidate requires separate whole-file verification. The search does
not prove absence from the full installation, authorized CC, or other sources.

One CASP diffuse RLE2 payload was decoded in memory: 1024 by 2048 pixels with
12 mip levels. Its first mip's BC3 blocks matched the independent Blender add-on
converter, and its RGBA pixels matched Pillow 11.3.0 by private digest. This is
one texture, not rendering or shader validation. The shadow texture and RLES
specular were not decoded in this comparison. Neither pixels nor their digests
were published.

The sampled version 12 GEOM has a three-bone palette. Its raw weights matched
the independent Blender reader, but its palette did not match that reader
unmodified: the reader expects a seam count that the versioned TS4CAS Tools
reader omits for version 12. Inserting a zero seam count into an in-memory copy
and adjusting offsets produced a matching palette. That normalized comparison
supports the candidate layout but is not independent validation of the original
bytes. Bone selection, skeleton binding, weights in a renderer, poses and visual
correctness remain unverified. No game process, live state or protected profile
was accessed during these checks.
