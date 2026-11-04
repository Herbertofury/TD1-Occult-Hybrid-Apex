# Native Tray appearance completion validation candidate

2026-11-04. Isolated source candidate. No desktop, game profile, save, installation, active source tree or original asset was changed during the experiment.

## Useful result

The recovered native appearance-completion command now runs without importing
game-side Python modules. It rejects wrong-wire and duplicate singular appearance
owners rather than copying them into a household. Selected message owners are
validated recursively against the supplied descriptor catalog, including repeated
packed/unpacked numeric fields. Entire outfit bytes, including native flags and
unknown future fields, are retained exactly. No preview-only outfit schema is used.

Completion remains an external, unverified candidate operation based on an
existing native v2 household. This is not a new native household writer or a proven
game-visible save feature.

## Changes

- `tools/tray_native_wire.py`: bounded, pure-Python wire parsing/replacement and
  descriptor validation. No game imports, process contact, or file IO. Rejects
  malformed tags/extents/varints, wrong known wire types, duplicate singular
  owners, invalid descriptor shapes, missing nested descriptors, and excessive
  recursion/field counts. Unknown valid supported wire is retained, not decoded
  under guessed schemas. Unsupported protobuf groups fail closed.
- `tools/tray_complete_appearance.py`: uses the standalone helpers, validates
  source/template/result owners, bounds the roster before decoding, and checks
  exact retention of unrelated attribute owners. Active appearance owner scope
  and the existing `native_library_load_verified: false` gate stay unchanged.
- `tools/tray_library.py`: rejects an additional wrong-wire household field even
  when one correct household field exists. Previously it was ignored and a later
  owner replacement could silently discard it.
- Two new test/oracle files. Other source/test files are copied unchanged only to
  make this isolated candidate runnable with the recovered dependencies.

## Evidence

- Baseline: 25 recovered tests pass (`evidence/baseline-tests.log`).
- Final: **51 tests pass**, comprising all 25 recovered tests plus 26 new tests
  (`evidence/candidate-tests.log`). No skipped tests in this Linux run.
- New coverage includes multi-member mapping and template order, optional-owner
  removal, every active owner's wrong-wire/duplicate cases, nested outfit
  corruption, exact flags/unknown-field preservation, wrong-wire household
  ambiguity, input bounds and hashes, descriptor corruption, malformed protobuf,
  packed scalar boundaries, recursion and aggregate limits, and UTF-8 validation.
- Fresh-process CLI coverage produces an external fixture archive and receipt,
  retains untouched metadata/portrait/footer bytes, preserves original files,
  refuses existing/game-profile destinations, and emits no candidate or receipt
  for malformed appearance data or mismatched input hashes.
- **64 deterministic randomized fixture cases** pass an independent generated
  descriptor oracle using official `protobuf` 7.36.2. Each completed Sim is parsed
  by the official runtime; selected fields, outfit flags, optional presence and
  retained identities are compared (`evidence/protobuf-oracle.json`). These are
  generated schemas, not recovered installed-game descriptors.
- Untouched recovered completion accepts both wrong-wire active flags and a
  duplicate singular active flags field. The candidate rejects both
  (`evidence/incumbent-reproduction.json`). The reproduction substitutes only
  pure blob/replace/chunks helpers to make the old source importable, not a game
  simulator. The old unmodified import itself fails on missing `apex_core`
  (`evidence/baseline-offline-import.log`).
- Python compile checks pass for changed source and candidate tests.

## Reproduce

From this directory:

```sh
PYTHONPATH=tools python -m unittest discover -s tests -v
python evidence/reproduce_incumbent.py
python -m compileall -q tools/tray_native_wire.py tools/tray_complete_appearance.py tools/tray_library.py tests
```

For the independent oracle, install `protobuf==7.36.2` from the official package
registry into an isolated dependency directory, then:

```sh
PYTHONPATH=/path/to/protobuf:tools:tests python tests/check_protobuf_oracle.py
```

`candidate.patch` contains only the three source changes and two new test files.
Apply against the recovered scale/durability Tray-library baseline plus recovered
appearance-completion source. Review integration against the actual current tree.

## Remaining gates

1. No real native household/installed current descriptor pair was available for
   this run. Real current-version data and an isolated game Library load must
   verify semantics, outfit appearance and persistence. Fixture success does not
   prove game acceptance or CC availability.
2. Completion retains existing identities, metadata and portraits. It does not
   regenerate those, create a new roster, author a new household, or refresh
   portraits. The source's `household export-tray` restriction remains untouched.
3. No standalone UI-to-native-record edit serialization or UI save integration was
   added. Native records must already contain the intended canonical edits, and
   callers must supply the matching current descriptor catalog and exact hashes.
4. Staged publication tests are Linux fixture evidence only. Group atomicity,
   game-reader coordination, Windows/NTFS, power-loss behavior and storage
   retention remain separate unresolved gates. Unsupported directory fsync still
   fails closed, so this does not establish a usable Windows Tray write path.
5. Validation establishes protobuf structure and bounded ownership, not all game
   semantic constraints or descriptor freshness. Unsupported schemas fail closed.

Do not publish private game/creator inputs. None were added to this candidate.
