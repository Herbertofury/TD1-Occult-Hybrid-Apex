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
