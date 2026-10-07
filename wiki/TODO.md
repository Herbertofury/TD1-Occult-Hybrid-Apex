# Full TODO — Apex Occult Hybrid

The canonical executable checklist is [docs/CODEX_MASTER_EXECUTION.md](../docs/CODEX_MASTER_EXECUTION.md). This page is the human-readable wiki view.

## Execution checkpoint — 2026-10-07

T001–T004, T006, T146 and T199 are proven to their stated source/acquisition/validator scope in the canonical master. Exact V9.6 source was preserved before edits. Queue-owner, deterministic script build and reversible profile-isolation tooling now exist; 24 targeted fixtures pass. The native overlay builds on this Windows machine. No live save/mod/profile or game-bin file has been changed by this checkpoint. All runtime/regression/release gates remain open. This is a repository wiki mirror, not a claim that GitHub's live Wiki has been published.

## P0 — standalone Apex Occult Hybrid Core

- Ship `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script` as the canonical hybrid engine.
- Start from the newest authorized working TD1/LordPercival hybrid package/script set; import/inventory and work upward from it.
- Owner confirms full author permission to use the hybrid baseline material in Apex.
- No TD1/TwelfthDoctor1/IcedCream/LordPercival hybrid runtime dependency in the final install.
- Preserve/port useful working 1.13.7 behavior first, then improve it.
- Support compatible multiple-occult membership and normal transformation paths.
- Safe Add/Remove Occult.
- Verified form switching without stuck/snap-back states.
- Switch occult gameplay/perk/motive panels without changing membership.
- Preserve Spellcaster charge / Werewolf Fury and other occult progression.
- Replace remove-all-occults-before-CAS with targeted state/form reconciliation.
- Patch-aware current-game tuning/resource generation.
- Clean Mods profile proof with Apex + official EA packs only.
- Full details: [Apex Occult Hybrid Core](Apex-Occult-Hybrid-Core).

## P0 — behavioral reference and safety

- Independently close every verified useful 1.13.7 behavior/fix without depending on upstream files.
- Reconcile authoritative SimInfo/OccultTracker state versus transient caches.
- Prove no native render-thread gameplay mutation.
- Prove save/reload/restart on representative hybrids.
- Fail closed on unknown game/native hook surfaces.

## P0 — original-mod regression closure

- CAS and MC Command Center edits must actually persist to the intended occult form.
- CAS must never delete secondary hybrid forms.
- Hybrids must never get stuck in one form.
- Werewolf hair/headwear/body/CAS parts and custom content must survive category/outfit/form changes.
- CAS entered while already in werewolf form must save correctly.
- Skin details, makeup, hair, tattoos, accessories and clothing must not bleed across forms or disappear.
- Stale CAS/MCCC/recovery snapshots must not overwrite newer intentional edits.
- Human and occult forms must remain independently editable.
- Every repair/commit must verify success after switching away/back and after save/reload.
- Full details: [Original Mod Regressions](Original-Mod-Regressions).

## P0 — Apex Live CAS Studio

- Owner confirms full author permission to study/use MCCC CAS-related implementation material.
- Start from current authorized MC CAS + MC Dresser + shared CAS helpers; preserve/port strong working behavior before replacing it.
- Make CAS-grade appearance editing available from Live Mode/F11 wherever the game exposes a safe runtime or non-UI CAS-service path.
- Body/face values and presets outside CAS.
- Searchable CAS-part browser outside CAS.
- Copy outfit category/slot within one Sim.
- Copy outfit Sim A -> Sim B.
- Copy **all outfits** Sim A -> Sim B.
- Copy Face / Body / selected CAS categories / full appearance between Sims.
- Searchable Tray/household source browser with preview.
- Saved appearance/outfit libraries.
- Visual include/exclude/lock/custom-definition rules.
- Safe randomize by outfit/category/body type.
- Exact human/occult form targeting.
- Missing CC/pack diagnostics.
- Bulk selected-Sim appearance operations.
- Every change previewable and Undo/Redo through CAS History.
- Current MCCC occult copy/body-part persistence fixes are permanent regression tests.
- Final clean-profile proof with no MCCC installed.
- Full details: [Apex Live CAS Studio](Live-CAS-Studio).

## P0 — Apex Color Studio

- Owner confirms full permission from thepancake1 for relevant Color Sliders baseline material.
- Start from current authorized Color Sliders v4f package/tooling and work upward.
- Preserve full compatible ColorState: base swatch + Hue + Saturation + Brightness/Value + Opacity.
- Every part/category/outfit/all-outfits/Sim/form copy must preserve exact custom color by default.
- Add explicit Part+Color, Part-only, Color-only and base-swatch-only copy modes.
- F11 Color Studio works without the original Color Sliders mod installed.
- Native CAS slider support is first-party Apex, patch-aware and optional.
- Automatic current-game/installed-pack texture conversion coverage.
- More CAS Columns and original Color Sliders coexistence/conflict diagnostics.
- Saved colors/palettes and color-aware randomization.
- CAS History/Undo/Redo/Saved Forms preserve exact ColorState.
- Human/occult form colors remain independent.
- Full details: [Apex Color Studio](Color-Studio).

## P1 — make F11 the best way to use the mod

- Selected-Sim dashboard with active occults/current form/health.
- One-click occult enable/disable with safe confirmations.
- Form switching with target preview.
- Searchable/renameable Saved Forms.
- Category-scoped copy/paste/commit/apply-all.
- Undo for the latest safe reversible appearance operation.
- Keyboard/focus/accessibility pass.

## P0 — Apex CAS Unlock Core

- Start from the newest authorized Crilender CASUnlocks v1.9h package/addons; import/inventory and work upward from them.
- Owner confirms full author permission to use Crilender baseline material in Apex.
- Own the final unlock behavior instead of permanently depending on the old package.
- Keep supported CAS categories unlocked through CAS entry, form switch, outfit switch, MCCC CAS and UI rebuilds.
- Default hybrid-aware Werewolf/Vampire/Mermaid/Fairy/Alien category expansion.
- Optional hidden/locked/debug/reward/occult item catalog.
- Installed-pack detection; no manual deleting pack files the user does not own.
- Preserve authorized working Crilender resources where strongest; replace only when Apex has a demonstrably better path.
- Patch fingerprint + current-game resource scan + deterministic regenerated unlock package/manifest.
- F11 Unlock Matrix explaining exactly why a category/item is available or blocked.
- Detect overlap/conflicts with other CAS unlocker overrides without deleting them.
- Werewolf faces/hair/headwear/base-layers/category regressions are P0.
- Full details: [Apex CAS Unlock Core](CAS-Unlock-Core).

## P1 — CAS History Studio

- Live Photoshop-style CAS history while edits happen.
- Undo / Redo / jump to any prior state.
- Preserve redo branches when editing after undo.
- Named checkpoints and Compare-with-current.
- Inspect exactly which CAS parts/resources/values were added, removed or replaced.
- Separate history lanes for human and every occult/custom form.
- Revert one change or category without damaging unrelated data.
- Safe cross-form cherry-pick with compatibility checks.
- Optional Reference Shot images at checkpoints, not every micro-change.
- Interrupted-session journal recovery.
- Reuse the same F11 overlay/injection, snapshot/diff engine and game-thread mutation queue.
- MCCC Shield, Drift Guard, Post-CAS Commit and Saved Forms all use the same CAS Change Journal.
- Full details: [CAS History Studio](CAS-History-Studio).

## P1 — CAS/MCCC/Drift

- Explicit MCCC Shield state machine.
- Lot51 event path + manual fallback.
- Stale-snapshot prevention.
- Drift diff before repair.
- Repair category / occult / explicit all separately.
- Persist minimal recovery state across interruption.

## P1 — diagnostics

- Selected-Sim cache view.
- Global cache view.
- CAS-session cache view.
- Explain why each occult/form is present/pending/inconsistent.
- Structured export suitable for bug reports/Codex.

## P2 — performance

- Zero hidden HTTP polling.
- Zero idle continuous Sim scans.
- Request coalescing while overlay is visible.
- Stale-response cancellation/generation IDs.
- PresentMon/WPR proof of non-regressive frame time.

## Release gate

Do not call Apex finished until R001–R010 in the original-mod regression ledger are no longer reproducible and the current Sims 4 build has exercised the actual F11 workflows including the standalone Apex Occult Hybrid Core, Apex Live CAS Studio, Apex Color Studio/full ColorState copy, CAS Unlock Core/Unlock Matrix and CAS History/Undo/Redo, representative hybrid combinations, CAS/MCCC recovery, Drift Guard, diagnostics, persistence, upgrade path and measured overlay overhead.
