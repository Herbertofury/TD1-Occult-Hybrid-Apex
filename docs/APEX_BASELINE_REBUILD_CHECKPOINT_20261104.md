# Baseline-first Apex continuation, 2026-11-04

The game hitch remains unresolved. This checkpoint adds measurement support;
it is not a new playable build, a measured speedup, Maru parity, or permission
to use the candidate on the owner's original save.

## Preserved work and source identity

The desktop repository is on `apex/recover-and-harden`, HEAD
`82961b263b21c970cde8674e40fcd71bfa2b6b14`, two commits ahead of tracked
upstream `58752ca9ab5eef8b7791aac3506beae0d5107ccd`. Initial status contains
929 entries (75 modified tracked paths and 854 untracked entries). It was
neither reset, cleaned, stashed, switched, nor edited by this continuation.

All 2,066 tracked/nonignored source files were copied to the separate task
workspace, totaling 25,833,627 bytes, with source-before/source-after/copy
SHA-256 verification. The local preservation manifest SHA-256 is
`687e283b3711eda2c222c1454147fd21cf56950cec35f649c656eebe77be7964`.
Ignored `.work` experiments and Git history remain at their original locations;
this source checkpoint is not a backup of the user's Sims profile or CC.

New changes are isolated on `apex/hitch-baseline-20261104`, based on the
tracked upstream checkpoint rather than the two unpublished desktop commits.
GitHub independently reported the tracked branch still at `58752ca9...` and
default `main` at `6a0bb2a6012e3ed9895a14a1c73dacbe1555d53e`. No merge,
deployment, external CAS edits, or changes to installed game/mod files occurred.

## Exact Modernize handoff

The supported local app API reached **Modernize Sims 4 mod toolkit**, thread
`01a11397-45c1-7662-94ef-75f96f18d660`, `hostId: local`, in the Foundry project.
A read-only handoff request completed in turn
`01a1a562-15f4-79a1-afe0-be660b7a9005`. The thread was instructed not to resume
tests, install anything, or edit code. Its latest prior turns had failed due
to workspace credits; that does not establish the present workspace's status.

The fresh handoff reports no running `TS4_x64`. The restored disposable bundle
is `.work/patch-1129-bounded-native-disabled-disposable-v3.zip`, SHA-256
`3da0f6f19a96ae1791f8623466af2bea07d87b64184e5fd803b63d09931f02b6`.
Its reported installed identities are:

| Artifact | SHA-256 |
| --- | --- |
| ApexCASBridge.package | c3f70eeef33114b705e8247c6af2bd1f23a51ba9b6e48b40ec95d9b6be6a5a3f |
| ApexCASUnlocks.package | 56d2d96ceba035c5b8e18c730267d3065e60e210c1d843499da717c54dc87f14 |
| ApexOccultHybrid.package | db8d3b8ec49fed2d798f4d061a919b4f8d116ac320a8556fc0b4880a776055c2 |
| ApexOccultHybrid.ts4script | ee50a04424dcdee421647710daaf4d30ade4aafc1ef174a8a06e36e222fda119 |
| ApexOverlay.dll | 7ba25522c0ee6b9c4b8d69e3f7aeed96b48def0c7eb333893d776f83c4b72641 |

These are handoff observations, not fresh loaded-module proof from this worker.
The handoff's disposable Slot 03 hash is
`de5488dd6625536829e6834345814e32d51fcd0e19bdfcc829a5ebab5ad495b6`.
The journal identifies the existing token-marked disposable profile as
`The Sims 4`, and the read/copy-only original as `The Sims 4 DO NOT TOUCH`.
Only the owner restores or renames that original.

The November 1 research targeted 1.129.39.1030. Recheck executable, patch,
package precedence and loaded identity before using any native addresses.
The retained high-column trace reports 2,252 Draw calls, about 11.9 seconds
inclusive, including about 10.1 seconds in overlay navigation. Instrumentation,
nested timings and different generated Sims prevent an equivalent-work speedup
claim. A private card-height candidate changed an initial grid target from
588 to 18, but the 31-column Bottoms-to-Tops freeze still occurred.

Three private timeline-registration probes crashed at game RVA `0xEC001B`;
do not repeat them unchanged. The virtual-registration control observed one
callback but proves neither safe prototype dispatch nor faster gameplay.
Mutable sort/event-array aliasing also invalidates the identity-only bounded
grid shortcut. See the desktop's retained
`docs/CAS_1129_CATEGORY_HITCH_EVIDENCE.md` and
`tests/test_1129_feed_mutation_alias_contract.py`; those uncommitted files are
preserved locally, not silently imported as qualified production code here.

## Access result and runtime boundary

The first read-only command
`Get-ChildItem -LiteralPath 'C:\Users\Owner\Documents\Electronic Arts'`
returned `Access to the path ... is denied` under the default sandbox identity.
After checking the owner's current GoldenOreo authorization, the supported
`require_escalated` execution of that read-only listing succeeded. This was
not an automatic-approval rejection and is no longer an outstanding access
denial. No profile was changed. Repository clone creation also required the
supported escalation; it succeeded in the task workspace.

No new game run or frame capture has been performed. A reproducible no-Apex
control has not yet been prepared or authenticated. Before game testing:
retain a recoverable snapshot of every disposable file that will change,
verify its token and closed process, establish a base-game-compatible matched
household/Sim and settings, account for all game-bin loaders and Mods resources,
and record the same UI workload in both run orders. Do not simply remove the
guard from the saved multi-hybrid household or treat an Apex-enabled capture
as the no-mod control. These are setup/evidence gaps, not proof of a new
game-access failure or a request for additional repository permission.

## Changes and evidence scope

The previously untracked frame collector/comparator and their tests are now
carried forward from the preserved source into this branch. New staged
identities permit partial component combinations without pretending they are
either no mod or the full Apex build. Stage inventories bind feature groups,
artifact hashes, observed component flags, PID and creation time. The staged
comparison requires both run orders against each immediate predecessor and
stops evaluating later stages after any positive tail/action-maximum delta.
Noise still needs fresh repeats and diagnosis; this is not automatic causality
or correctness certification.

Measurement fixes reject mixed zero/nonzero ETW loss reports and duplicate JSON
keys. Action windows use Present timestamps and overlapping present intervals,
so a hitch ending after the action window is not silently omitted. The exact
PresentMon 2.6.0 source distinguishes `TimeInQPC` (Present event) from
`CPUStartQPC` (CPU frame start):
[CsvOutput.cpp](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/PresentMon/CsvOutput.cpp).
The pinned default combined output is retained; legacy output flags change
its column contract. Live collector validation is still required.

Fixture tests exercise synthetic CSV/evidence files and mocked collectors;
they are not game measurements. The canonical performance leaves T048, T092,
T114 and final G009 remain open. No existing feature or preservation check was
removed to obtain these fixture results.

Validation: 36 targeted collector/comparator/stage tests pass on both Python
3.7.9 and the installed Python 3.13. A final independent rehash finds zero
changes in all 2,066 preserved desktop source files and the original 929-entry
Git status is identical. A preliminary broader `test_*frame*.py` discovery on
the upstream clone was not clean: 55 cases, one `test_cas_grid_frame_build`
contract failure, one missing `tests` package import from the external working
directory, and seven skips. Those unrelated UI-build checks were not repaired
or credited as passing; this branch changes no CAS runtime/build implementation.
No full-mod or actual-game regression pass is claimed.

## Feature restoration remains the full accepted scope

The controlling requirements remain `CAS_SHARED_HUMAN_REQUIREMENTS.md`,
`CODEX_MASTER_EXECUTION.md` and R001-R010 in `USER_REPORTED_REGRESSIONS.md`.
Retain one shared Human, independent actual occult/special/alternate owners,
Alien's native portrait arrangement, missing form pairs, exact scoped
link/unlink/directional partial or whole copy, undo, multi-Sim isolation,
gameplay identity/progression and complete CAS/Live/MCCC/F11/save/Tray retention.
F11 must identify equipped items with exact names, images and Studio opening
across skin details and all categories. Shared content indexing, exact slider
identities and full ColorState remain required. Preserve the permanent guard.
The separate external CAS project remains owned by its own worker.

Maru's [creator description](https://www.curseforge.com/sims4/mods/dynamic-cas-columns)
was checked on November 4. Its November 3 release is newer than the local
October 29 donor audit. Required coverage includes resizing and thumbnails,
search, favorites/hide/presets, swatches, history, saved outfits/slot copying,
eye previews, backgrounds, filters, settings, playback, sliders and shortcuts.
Recent additions include per-feature switches and multi-keyword search.
The creator's [license page](https://www.curseforge.com/sims4/mods/dynamic-cas-columns/license)
identifies CC BY 4.0; retain credit, provenance and modification notices for
covered reused material. No donor assets/code are newly redistributed here.
Feature-by-feature actual-game parity with the latest donor remains unproved;
an October snapshot or source-method count must not be presented as parity.
