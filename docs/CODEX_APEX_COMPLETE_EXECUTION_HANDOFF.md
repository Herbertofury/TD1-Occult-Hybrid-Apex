# APEX OCCULT HYBRID — COMPLETE CODEX EXECUTION HANDOFF

**Repository:** https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex  
**Canonical branch:** resolve the repository's current default working branch during preflight; do not assume a stale local copy.  
**Last handoff reconciliation:** 2026-10-06  
**Purpose:** give this entire file to Codex and have it execute the complete accepted Apex scope without restarting, shrinking, re-planning, or silently dropping requirements.

## Objective

Finish **Apex Occult Hybrid** as one cohesive, standalone, first-party Sims 4 hybrid/CAS workstation that is materially better than the authorized baseline mods it evolves from.

Apex is not merely a hybrid stabilizer. The finished product combines and improves:

- a complete first-party occult-hybrid engine;
- a first-party CAS unlocker;
- a full Live CAS editor usable outside Create-a-Sim;
- Photoshop-style CAS history, undo/redo, branches and recovery;
- full color-slider support with exact color preservation through copy/paste;
- F11 diagnostics/control UX;
- safe CAS/MCCC/occult recovery;
- patch-aware package/resource generation;
- strong runtime, save/reload, performance and regression proof.

**Do not stop after writing a plan. Begin implementation from the earliest ready canonical task and continue through convergence.**

## Canonical source of truth

This handoff is an execution wrapper. It does **not** replace or reduce the detailed repository specs. The repository files below are binding and must be read before implementation. Their prose remains authoritative; their task IDs are the canonical execution state.

Read in this order:

1. `docs/AUTHORIZED_BASELINE_STRATEGY.md`
2. `SOURCE_RECOVERY_STATUS.md`
3. `docs/CODEX_MASTER_EXECUTION.md`
4. `docs/USER_REPORTED_REGRESSIONS.md`
5. `docs/APEX_OCCULT_HYBRID_CORE.md`
6. `docs/APEX_CAS_UNLOCK_CORE.md`
7. `docs/APEX_LIVE_CAS_STUDIO.md`
8. `docs/CAS_HISTORY_STUDIO.md`
9. `docs/APEX_COLOR_STUDIO.md`
10. `docs/MCCC_CAS_BASELINE_MATRIX.md`
11. `docs/PANCAKE_COLOR_SLIDER_BASELINE.md`
12. `docs/CAS_UNLOCKER_REFERENCE_MATRIX.md`
13. `docs/UPSTREAM_1.13.7_DELTA.md`
14. `docs/DEVELOPER_TOOLBOX.md`
15. `THIRD_PARTY_NOTICES.md`

Then continue the canonical checklist in `docs/CODEX_MASTER_EXECUTION.md`.

At this handoff, the master contract contains **T001 through T196** and **G001 through G015**, with **G009 · FINAL COMPLETION GATE** as the last executable checkbox. Never renumber existing IDs. New accepted work discovered during execution receives the next unused `T###` in the nearest relevant section.

## Owner-authorized implementation baselines

The project owner states they have full author permission to use the relevant material from all four baselines below. Treat them as **concrete implementation/code/resource bases**, not merely inspiration.

### 1. TD1 / LordPercival hybrid baseline

Start from the newest authorized working **Occult Hybrid Unlocker & Stabilizer 1.13.7 FIXE** package/script set available to the project.

Import, hash, inventory, diff and preserve its useful working behavior before replacing anything. Direct authorized reuse, porting, adaptation, merging and re-ID into Apex are allowed where that is the strongest route.

### 2. Crilender CASUnlocks baseline

Start from the newest authorized **Crilender CASUnlocks v1.9h** package and relevant current addons available to the project.

Use its real category/resource coverage as the starting CAS-unlock implementation base. Preserve/port strong working resources, then improve and consolidate them into Apex.

### 3. MC Command Center baseline

Start from the newest author-authorized **MCCC MC CAS + MC Dresser + shared CAS-related implementation** available to the project. The current public baseline recorded in the repo is MCCC 2026.5.0 for Sims 4 PC 1.128.90.1030 unless a newer authorized build/source is available.

Study and port the strongest CAS/outfit/appearance logic rather than rebuilding it blind.

### 4. thepancake1 Color Sliders baseline

Start from the newest author-authorized **thepancake1 Color Sliders** package/tooling available to the project. The current public baseline recorded in the repo is v4f, which must be ported/revalidated forward to Apex's current supported game build.

Use the authorized UI/resource/conversion architecture as the starting point for Apex-native color support.

### Permission boundary

Preserve author attribution and exact source/version provenance. Owner permission applies to the relevant author-owned material described above; it does not automatically grant rights over unrelated third-party components that may be bundled inside those archives. Preserve separate third-party terms where applicable.

## Migration rule: build upward, then remove old dependencies

For every authorized baseline:

`acquire exact archive -> hash -> extract/inventory -> runtime-test baseline -> map behavior to resources/modules -> add parity/regression proof -> reuse/port strong pieces -> improve/replace weak pieces -> compare baseline vs Apex -> remove old dependency only after parity + improvement -> clean-profile Apex-only proof`

Do not throw away working authorized code/resources just to claim a rewrite. Do not keep an old runtime dependency merely because it was convenient during development.

## Required final Apex artifacts

The production release must converge on Apex-owned artifacts, including at minimum:

- `ApexOccultHybrid.package`
- `ApexOccultHybrid.ts4script`
- `ApexCASUnlocks.package`
- first-party Apex color-slider package/integration, currently targeted as `ApexColorSliders.package` or an explicitly owned equivalent integration
- the Apex F11/native overlay component where that feature is enabled
- deterministic source/release manifests and SHA-256 hashes
- install, upgrade, rollback and troubleshooting documentation

The normal user must **not** need TD1/LordPercival/IcedCream hybrid files, Crilender CASUnlocks, MCCC, thepancake1 Color Sliders, Lot51 Core, XML Injector, or another hybrid/CAS controller for Apex's accepted core capabilities.

Optional interoperability is allowed; runtime dependency is not.

## Non-negotiable product requirements

### Standalone occult-hybrid core

Apex must own hybrid membership, active/current form, linked form state, pending transformations, selected occult gameplay/perk panel, temporary/pseudo-occult states, diagnostics and persistence.

Required behavior includes compatible multiple-occult membership, official transformation paths where safe, Add/Remove Occult, verified form switching, stuck/snap-back recovery, Spellcaster charge and Werewolf Fury/orb handling, current Vampire/Mermaid/Fairy/Alien and other supported occult behavior, capability-aware PlantSim/Ghost/Servo handling, progression preservation and patch-aware occult resource discovery.

The historical 1.13.7 behavior/fix floor must be preserved or improved without requiring the old runtime files.

### Original-mod failure ledger is release-blocking

Every R001–R010 item in `docs/USER_REPORTED_REGRESSIONS.md` must remain closed.

Especially preserve these exact failure classes as permanent regressions:

- CAS/MCCC edits appear saved but later revert or never reach the intended stored occult form;
- secondary hybrid forms disappear or become inaccessible after CAS;
- a hybrid becomes stuck in one form or snaps back;
- werewolf hair/headwear/body parts/CC are stripped or corrupted;
- edits made while already in werewolf form fail to persist;
- skin details, makeup, hair, tattoos, accessories or clothing bleed between forms or vanish;
- stale CAS/MCCC/recovery snapshots overwrite newer intentional edits;
- broad copy/repair changes unrelated CAS or occult state;
- human and occult forms lose independent editability;
- an operation reports success without switch-away/back and save/reload proof.

Never “fix” these by deleting forms, flattening appearances, dropping content, or weakening verification.

### Apex CAS Unlock Core

Apex must ship a real first-party CAS unlock package and keep compatible categories unlocked through CAS entry/re-entry, Sim switch, form switch, outfit switch, MCCC-style CAS workflows, history restore and UI rebuilds.

Preserve and improve Crilender coverage, especially Werewolf/Mermaid/Fairy/archetype/base-layer behavior. Add installed-pack awareness, patch fingerprints, current-game regeneration, hidden/locked/debug/reward/occult catalog support, native reward-unlock semantics where stronger, conflict diagnostics and the F11 Unlock Matrix.

A visible item is not automatically safe to apply. Preserve age/species/frame/form compatibility unless the user explicitly chooses a supported advanced override.

### Apex Live CAS Studio — CAS Anywhere

Anything safely representable through CAS should be controllable from Live Mode/F11 without forcing the user into the full CAS UI when the current game provides a safe runtime or non-UI CAS-service path.

Apex must match or exceed authorized MCCC MC CAS + MC Dresser appearance/CAS capabilities, including:

- body/face numeric values and presets;
- searchable CAS-part editing;
- runtime-safe CAS identity/preferences metadata;
- every outfit category and outfit slot/index;
- outfit copy within one Sim;
- outfit copy Sim A -> Sim B;
- **all-outfits copy** Sim A -> Sim B;
- Face-only / Body-only / Face+Body / selected-category / current-outfit / selected-outfits / all-outfits / full Appearance Clone modes;
- exact human/occult form targeting;
- Tray Sim/household appearance sources with preview;
- Saved Form/history/preset sources;
- reusable appearance/outfit libraries;
- Include/Exclude/Lock/custom-definition rules;
- safe category/outfit/body-type randomization;
- missing CC/pack diagnostics;
- selected multi-Sim bulk operations;
- preview, semantic diff, verification, Undo/Redo and rollback for every accepted mutation.

Opening full CAS UI is a last-resort fallback. When a surface is genuinely engine-blocked outside CAS, record evidence and preserve the same transaction/history behavior.

### Photoshop-style CAS History Studio

Maintain one canonical CAS Change Journal shared by Live CAS Studio, Post-CAS Commit, Drift Guard, MCCC compatibility, Saved Forms and recovery.

Required behavior includes live meaningful history events, semantic before/after inspection, Undo, Redo, jump-to-state, preserved branches after editing from an older state, named checkpoints, category-scoped revert, compatible cherry-pick, optional reference images at checkpoints, interrupted-session recovery and explicit human/occult form lanes.

History is evidence. Revert/undo creates a new mutation event rather than erasing the record.

### Full ColorState and Apex Color Studio

Color is part of appearance state, not a cosmetic side channel.

For every compatible CAS part, Apex must preserve the actual current-game color state, semantically including:

- base swatch;
- Hue;
- Saturation;
- Brightness/Value;
- Opacity;
- exact Sim/form/outfit/body-type/part ownership;
- slider/texture compatibility identity and provenance.

**Every relevant copy path must carry exact compatible ColorState by default.** This includes single-part/category copy, outfit copy, all-outfits copy, Sim-to-Sim copy, Face/Body/Appearance Clone, form copy, Saved Forms, history checkpoints, presets and Tray sources when resolvable.

Provide explicit copy modes where safe:

- Part + exact color (default)
- Part only / preserve destination color
- Color only
- Base swatch only

Never silently collapse custom slider colors back to ordinary EA swatches.

Apex must provide its own F11 Color Studio and first-party/native CAS slider support without requiring the original thepancake1 mod. Converted-texture coverage must be patch-aware and installed-pack aware. Detect/handle original Color Sliders, More CAS Columns and overlapping UI resources safely.

### F11/native control-plane rules

F11 remains the primary control surface. Every visible control must be wired end-to-end to real domain logic; no fake buttons, placeholder panels or UI-only success.

The native render thread must never directly mutate Sims state. Mutations go through the canonical validated Python/game-thread owner. Hidden overlay mode must not continuously poll Sims/HTTP or scan the world.

### Performance without loss

Do not claim speed by doing less work, loading fewer resources, dropping history, weakening validation, omitting categories, skipping content, or losing visual fidelity.

Measure equivalent work. Preserve current/new performance floors once proven. Keep heavy indexing/conversion/diff work off interactive/render hot paths. Use bounded queues, cancellation/generation IDs, deduplication, caching and event-driven invalidation where appropriate.

### Persistence and recovery

Any state the user reasonably expects to persist must survive form switch, outfit switch, household switch, save/reload and full game restart when applicable.

Risky mutations must have preview/verification and recovery/rollback where practical. Stale asynchronous work or stale snapshots may never overwrite newer intent.

## Execution protocol for Codex

Treat `docs/CODEX_MASTER_EXECUTION.md` as the canonical executable checklist.

- Read the full execution contract once.
- Resolve the authoritative repo/worktree, dirty state, actual build/test/package/launch commands and available baseline archives.
- Reuse verified paths/commands/state until invalidated; do not repeatedly rediscover them.
- Continue from the earliest unchecked or invalidated canonical task whose prerequisites are satisfied.
- Work in bounded internal windows: one coherent subsection or roughly 6–12 ready leaf tasks.
- Update canonical checkboxes/proof notes in place as work is actually proven.
- Use targeted changed-path verification during leaf work; broaden at parent gates and final convergence.
- If later work invalidates earlier proof, reopen the original task/gate rather than pretending it remains complete.
- If a task is blocked, record `BLOCKED: <exact cause>; NEXT: <exact recovery>` on that task and continue independent work.
- After two materially unchanged failed attempts, change strategy. Do not loop the same failure.
- Do not create a second reduced checklist that can drift from the canonical master.
- Do not stop because the work is large. Preserve state/checkpoint and continue.
- Do not ask the user to reconfirm already accepted scope.

## GitHub / durability requirements

Keep the repository, issues, canonical docs, TODO/wiki mirror and release artifacts synchronized at coherent checkpoints.

Relevant existing trackers include the main Codex issue and focused regression/CAS/unlocker/hybrid/color issues already in the repository. Update those rather than creating disconnected shadow backlogs.

Commit/push coherent implementation checkpoints before long runtime/build gates so work is recoverable.

If the actual GitHub Wiki becomes available, keep it synchronized from the canonical repo docs. Do not silently treat an unsynced repo-side wiki mirror as a published live Wiki.

## Proof requirements

Build/static success alone is not completion.

Use the strongest available evidence for each capability:

- source/static/type/lint checks;
- package/tuning/resource structural validation;
- deterministic manifests and hashes;
- targeted unit/regression fixtures;
- current Windows/native overlay build where applicable;
- exact current Sims 4 runtime launch;
- representative human + supported occult/hybrid matrix;
- normal CAS and CAS-while-transformed paths;
- Live CAS copy/preset/Tray workflows;
- exact ColorState copy verification;
- form switch away/back;
- outfit switch/category switch;
- save/reload/full restart;
- clean Mods profile with legacy baseline mods removed;
- equivalent-work performance measurements;
- logs/diagnostics proving the actual production path was exercised.

Tests that bypass production wiring do not satisfy runtime acceptance.

## Convergence rule

Use this loop until complete:

`implement -> targeted verify -> inspect actual diff/runtime -> compare against every accepted requirement -> repair gaps -> rerun affected proof -> continue`

Before final completion, scan the full accepted contract for missing, partial, contradictory, stale or unverified work. Any newly discovered accepted gap gets the next unused canonical task ID and is implemented before completion.

Do not manufacture convergence by deleting tasks, weakening assertions, reducing supported cases, disabling hard features, removing content, or relabeling blockers as complete.

## Handoff execution controls

These T900-series items are **orchestration controls only**. They do not replace, summarize, renumber, or reduce canonical `T001–T196` / `G001–G015` in `docs/CODEX_MASTER_EXECUTION.md`.

- [ ] **T900** · Resolve the authoritative repository/worktree/branch, current dirty state, real build/test/package/launch commands, and the exact available authorized baseline archives; record any genuine blocker inline and then proceed directly into implementation.
- [x] **T901** · Read every canonical document listed in this handoff once, confirm the current `docs/CODEX_MASTER_EXECUTION.md` task/gate identity, and do not create a second reduced implementation checklist. **Proof:** all 15 required canonical documents and the complete master were read before implementation; original T001–T196/G001–G015 identities preserved. Additional discovered safety/CLI work uses T197–T200 in that same master; G009 remains the final gate.
- [ ] **T902** · Resume and execute the canonical master from the earliest ready unchecked/invalidated task, updating its existing T/G checkboxes and proof/blocker notes in place as work is genuinely proven.
- [ ] **T903** · Persist coherent implementation checkpoints to the canonical GitHub repository and keep the repo TODO/issues/wiki mirror/release lineage synchronized instead of leaving the only current state in local scratch or chat.
- [ ] **T904** · Before declaring completion, run a whole-contract convergence pass covering all canonical requirements, R001–R010, clean-profile runtime proof, exact ColorState copy proof, save/reload/restart, release artifacts/hashes, and equivalent-work performance.
- [ ] **T905** · Confirm canonical `G009 · FINAL COMPLETION GATE` is truthfully the last completed executable item in `docs/CODEX_MASTER_EXECUTION.md`; if it is not, continue execution rather than returning a roadmap.

## Done when

There is only one valid finish condition:

**Every canonical T001–T196 task and G001–G015 gate is complete or has been legitimately superseded by later canonical tasks without lost scope, no accepted blocker remains, the exact Apex release artifacts are built/hashed, the current production workflows are runtime-proven, R001–R010 remain closed, standalone clean-profile proof passes, equivalent-work performance is materially non-regressive, and `G009 · FINAL COMPLETION GATE` is truthfully checked as the final executable item.**

Until then, continue executing the master contract.

## First action

Open the repository, verify the authoritative worktree/branch and `SOURCE_RECOVERY_STATUS.md`, read the canonical documents listed above, resolve the exact authorized baseline archives presently available, then begin at the earliest ready unchecked task in `docs/CODEX_MASTER_EXECUTION.md`.

Do not respond with another roadmap. Execute.

- [ ] **G900 · FINAL COMPLETION GATE** — This handoff is complete only after T900–T905 are complete **and** canonical `docs/CODEX_MASTER_EXECUTION.md` has truthfully completed every accepted T/G requirement through `G009 · FINAL COMPLETION GATE`, with no unresolved accepted blocker and no silently dropped scope.
