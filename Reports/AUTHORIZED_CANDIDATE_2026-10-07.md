# Authorized-baseline candidate checkpoint

The owner requested actual packages/scripts/F11 development and took over game
testing. All work in this checkpoint is source/build/offline verification.
The candidate is not deployed, and no game interaction or original-profile
mutation was performed for its build.

## Concrete contents

Six DBPF packages contain 204 resources total: hybrid 159, consolidated CAS
unlocks 39, merged color UI 2, and optional policy packages containing 2/1/1.
The matching script contains 44 Python 3.7 compiled modules: all 36 actual
authorized hybrid modules adapted into `apex_hybrid`, seven Apex entry/helper
modules, and one real picker adapter replacing a missing baseline module.

Both manifest filenames retain their artifact extensions, so the hybrid
`.package` and `.ts4script` manifests cannot overwrite one another. Every input,
resource owner, overlap decision, embedded module and artifact is hashed.
Baseline tuning IDs and unmodified resource payloads are preserved for save
compatibility. Remaining first-party policy/current-game regeneration is open.

The candidate builder verifies every custom XML module reference against the
actual embedded script inventory. This caught two orphaned baseline picker
resources pointing at a module absent from both the release script and the
[published upstream source at commit 036d363](https://github.com/L-P-TD1/ts4-occulthybrid/tree/036d36307f6e3709aba56ff037eeb9dc703c87c9).
The adapter inherits the actual authorized picker base, lists already-owned
forms using current tuning/pack availability and dispatches explicit form
switches through Apex. The two tunings also contained contradictory online
predicates and a blank species enum; these are repaired without removing age
restrictions. Runtime selection/tuning compatibility still needs owner testing.

## Safety improvements

The baseline tracker save hook now restores temporary membership/form-availability
flags in `finally`, including original-save failure. Unknown saved form records
and membership bits are retained rather than pruned when tuning is absent. A
newer original serialized record wins over a retained older copy. The disabled
stabilization callback preserves its original return value and its source is
made valid for Python 3.7. The legacy whole-library automatic CAS restore
callback is retired; the existing explicitly armed Apex shield owns that path.
Full CAS/MCCC preservation and every R001–R010 regression remain unproven.

Deaderpool's actual MCCC 2026.5.0 `DresserOutfitObject` helpers supply the part/color
port. Their instruction streams were inspected passively, then only four pure
functions were executed against ordinary list state for nine bounded comparison
cases. Original MCCC/game modules and hooks were not executed. The source port
matches those cases and adds strict uint bounds and parallel-array checks.

Current-game `Outfits.proto` descriptors identify per-part `color_shift` as uint64.
Outfit editing preserves exact integers, absent optional arrays, original part
order, object/layer IDs, existing flags and unrelated protobuf fields. The older
zero-padding/sorting/composite-clearing implementation is replaced. No unverified
HSV bit layout is invented. Full numeric slider decoding/texture conversion
and broad cross-Sim/form copy integration remain tracked requirements.

## Journal and F11

Studio commands share the canonical game-thread dispatcher. Exact-color copy,
compatible color-paste Preview/Apply/Cancel, named checkpoints, previewed
Undo/Redo/Jump, preserved branches and interrupted-write reconciliation are
implemented. Recovery snapshots are persisted before mutation; a changed
revision is rejected; failed readback attempts rollback. Journal lanes include
save GUID/slot, Sim ID and active form. Observed state and readback proof are kept
distinct from save/reload proof.

The F11 overlay rebuilds with a vertical sidebar, retained last-command results,
CAS History/Color Studio tabs, destructive legacy-action confirmation and a
persisted F1–F24 configuration (default F11). Worker response handling waits for
game-thread completion and rejects truncated/malformed transport responses.
History entries are now directly selectable and searchable, showing the current
state, preserved branch parent and capture timestamp. Color Studio lists the
actual serialized outfits/parts, exact resource/color identities and optional
object/layer metadata. Layered BodyTypes require an explicit part row rather
than an ambiguous dictionary lookup; unrelated layered slots are preserved.
Absent colors and unresolved patch-sensitive BodyTypes have disabled controls
with a reason. Apply/Cancel clear the old preview token, and an applied color
invalidates the pre-write inventory until explicit inspection refreshes it.

The actual native reader uses a pinned MIT JSON library rather than substring
matching. Eighteen compiled production-reader checks cover exact uint64 IDs,
Unicode, quoted log delimiters, top-level field ownership, typed Studio data,
bounded malformed/nested responses and independent status/result caches.
Hidden mode does not issue status polling. The current executable's static
imports still do not justify installing the proxy. No DLL was installed; live
F11 loading/input/render/performance proof remains open. The console command
`apex.studio ACTION [VALUE] [SIM_ID]` exposes these source paths for owner tests
without requiring a native overlay to load first.

## Verification and limits

87 production/offline fixtures and 18 native transport/data checks pass. MSVC
x64 Release builds the actual overlay and CTest runs its production data reader.
Foundry's independent Rust DBPF reader validates all six indexes and extracts
all 204 resources; every decompressed content SHA matches the builder's output.
Package/script and bundle CRC/inventory checks pass. The source/script/package
builds are deterministic for identical inputs; the native binary has an exact
artifact identity, without a claim of cross-toolchain reproducibility.

`tools/build_candidate.py --foundry PATH_TO_FOUNDRY_EXE` builds the single bundle
in `dist/candidate`. `docs/CANDIDATE_INSTALL_AND_TEST.md` is embedded as its README.
The signed private matching compiler and authorized inputs remain private;
public CI validates source/fixtures/native compilation without publishing them.

The merged v4f color UI is deliberately a separate experimental install step:
it predates the target patch and lacks converted texture/catalog coverage.
MCCC superset features, all-legacy canonical history integration, Tray editing,
current-resource regeneration, the native loader and all live/regression/release
gates remain open. The owner retains runtime testing. No task is closed merely
because a package file exists.
