# Apex Occult Hybrid — Codex Master Execution Contract

Last reconciled: 2026-10-06
Recovered baseline: V9.5 Final Accounting / Runtime Safe
Authorized concrete hybrid baseline: Occult Hybrid Unlocker & Stabilizer 1.13.7 (FIXE) package/script set — import and work upward from it; not a required final dependency

## Objective

Finish Apex Occult Hybrid as a fully standalone, safe, polished, observable hybrid-occult system that independently matches the useful behavior of current hybrid solutions, fixes the known failure modes, and materially improves usability, recovery, diagnostics, patch resilience and CAS integration while preserving all still-valid Apex V9.5 work.

## Context

The recovered V9.5 project already contains a large Sims/Python backend, a Windows x64 DX11 Dear ImGui overlay source kit, saved-form support, MCCC/CAS shield behavior, Drift Guard, reference shots, category-scoped appearance operations, diagnostics, localhost control endpoints and extensive offline validation reports. The project owner also explicitly authorizes using the current TD1/LordPercival hybrid and Crilender CASUnlocks packages/code/resources as concrete development bases.

Do not restart this project as a blank mod. Begin from the recovered Apex implementation **and the newest authorized working TD1/LordPercival hybrid + Crilender CASUnlocks packages**, inventory their real contents, reuse/port authorized working pieces where strongest, then improve them until production runtime ownership converges on first-party Apex package/script artifacts.

## Constraints

- Preserve save safety and require explicit user intent for destructive/ambiguous occult mutations.
- The native render thread must never mutate Sims state directly. Send typed commands to the Python/game-thread owner.
- Hidden overlay mode must not poll Sims/HTTP continuously.
- No private MCCC monkey-patching.
- Auto repair stays opt-in.
- No quality/content reduction to claim performance wins.
- The newest authorized TD1/LordPercival 1.13.7 package/script set is the concrete hybrid implementation baseline. Inspect/import/diff it first and preserve useful working behavior; direct authorized reuse/port/adaptation is allowed. Apex must then improve it and remove the old runtime dependency from the final install.
- Preserve attribution and exact provenance for authorized reused/ported baseline material. Owner-provided author permission is authoritative for the TD1/LordPercival hybrid and Crilender baseline material covered by that permission; separately owned third-party components inside an archive still retain their own terms.
- Never call build/static checks live-game proof.
- CAS History Studio must reuse the existing Apex overlay/injection and canonical game-thread mutation path; do not introduce a second always-running DLL/hook stack unless runtime evidence proves the shared path cannot satisfy the requirement safely.
- CAS History observation may be native/read-only when necessary, but undo/redo/revert/apply must never mutate Sims state from the render thread.
- Crilender CASUnlocks v1.9h and relevant current addons are the concrete authorized CAS-unlock implementation baseline. Inspect/import/diff them first; direct authorized reuse/port/adaptation is allowed by the owner's author permission. Apex must then improve/consolidate them into `ApexCASUnlocks.package` and remove the old runtime dependency from the final install.
- Apex CAS Unlock Core is standalone: no third-party unlocker, Lot51 Core, XML Injector or other external script/package library may be required for its normal runtime behavior. Open technical libraries may assist development/build tooling only if users do not need to install them separately.
- The normal release must include a real first-party `ApexCASUnlocks.package`; script-only emulation of CAS unlock behavior does not satisfy the product requirement. That package must be reproducibly buildable from Apex source/policy + current game resources and must be the exact artifact runtime-tested.
- Unlock maintenance must be patch-aware: current game resources + exact build fingerprint are authority, and stale generated overrides must never be silently treated as current.
- Apex Occult Hybrid Core is standalone: the production hybrid engine must not require TD1/TwelfthDoctor1/IcedCream/LordPercival packages/scripts, another hybrid stabilizer, MCCC, Lot51 Core or XML Injector. The normal release must include first-party `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script` and prove them on a clean Mods profile.

## Resume rule

Continue from the earliest unchecked or invalidated task whose dependencies are satisfied. Work in bounded internal windows of roughly 6–12 ready leaf tasks, update this file in place, checkpoint coherent source state, and continue. During leaf work, use the cheapest decisive targeted verification / changed-path test; broaden to section-wide regression at the containing parent gate and whole-product/runtime verification at the final gate when later changes have not already invalidated earlier proof. If two materially unchanged attempts fail without new evidence, change strategy. Blockers remain inline as `BLOCKED: ...; NEXT: ...`.

## Phase A — Recover and normalize V9.5

- [ ] **T001** · Verify the recovered archive SHA-256 and current repository source manifest against the V9.5 recovery record.
- [ ] **T002** · Normalize the repository layout without deleting historical reports or provenance.
- [ ] **T003** · Resolve the canonical Sims/Python backend entrypoint and document every packaged script/module owner.
- [ ] **T004** · Resolve the canonical native-overlay entrypoint, DX11 proxy/export model and installation path.
- [ ] **T005** · Identify all duplicated/obsolete V5–V9 compatibility paths inside the large Python source and mark which remain runtime-reachable.
- [ ] **T006** · Add deterministic source-manifest generation for text and binary artifacts.
- [ ] **G001 · GATE** — Recovery is reproducible and no V9.5 capability was silently lost.

## Phase B — 1.13.7 behavioral regression/reference floor

- [ ] **T007** · Acquire/hash/inventory the actual newest authorized 1.13.7 hybrid package/script set, diff its package resources and runtime modules against recovered Apex/current-game behavior, and use that real implementation as the starting baseline before changing it.
- [ ] **T008** · Preserve or port the authorized working 1.13.7 STBL coverage into Apex-owned resources, then verify and improve it where needed.
- [ ] **T009** · Preserve or port the authorized working TMex PhoneSearch / PlantSim Pie Menu compatibility behavior, then verify it on the current build.
- [ ] **T010** · Start from the authorized current Werewolf tuning injections, port/re-ID them into Apex ownership as needed, and verify/improve current-build coverage.
- [ ] **T011** · Start from the authorized current Fairy tuning injections, port/re-ID them into Apex ownership as needed, and verify/improve current-build coverage.
- [ ] **T012** · Start from the authorized current Fairy bloodline tuning injections, port/re-ID them into Apex ownership as needed, and verify/improve current-build coverage.
- [ ] **T013** · Provide Apex-equivalent diagnostics for selected-Sim occult cache state.
- [ ] **T014** · Provide Apex-equivalent diagnostics for global occult cache state.
- [ ] **T015** · Provide Apex-equivalent diagnostics for CAS-session cached Sims/households.
- [ ] **T016** · Add regression fixtures proving 1.13.7 parity work does not bypass Apex safety/queue ownership.
- [ ] **G002 · GATE** — Apex independently provides every verified useful 1.13.7 behavior/fix needed by the project, retains V9.5 behavior, and does so without a TD1/IcedCream/LordPercival runtime dependency.

## Phase C — Canonical occult state model

- [ ] **T017** · Make one canonical typed model for active occult types, current form, available forms, linked SimInfos and pending mutations.
- [ ] **T018** · Distinguish authoritative save-backed state from transient mod caches and CAS-session caches.
- [ ] **T019** · Add stable per-Sim diagnostics that explain why an occult/form is present, absent, pending or inconsistent.
- [ ] **T020** · Detect unsupported/unknown/custom occult types without deleting them.
- [ ] **T021** · Add explicit ambiguity states instead of guessing when multiple occult/form owners could match.
- [ ] **T022** · Make add/remove/switch/repair actions idempotent where the Sims runtime allows it.
- [ ] **G003 · GATE** — Occult state has one observable owner and ambiguous data cannot be silently destroyed.

## Phase D — F11 control center UX

- [ ] **T023** · Preserve F11 as the default overlay toggle and make the binding configurable/persisted.
- [ ] **T024** · Rebuild the home dashboard around selected Sim, active occults, current form, health/drift status and next safe actions.
- [ ] **T025** · Add one-click occult enable/disable controls with confirmation only when the action is destructive or ambiguous.
- [ ] **T026** · Add clear per-occult form switching with current/target state preview.
- [ ] **T027** · Make Saved Forms searchable, renameable, duplicate-safe and visibly scoped to Sim/occult.
- [ ] **T028** · Make CAS Categories expose face/body/hair/makeup/clothing/accessory and other discovered scopes without hardcoded silent loss.
- [ ] **T029** · Add before/after summaries to copy/paste/commit/apply-all operations.
- [ ] **T030** · Add undo/rollback affordance for the latest safe reversible appearance mutation.
- [ ] **T031** · Add keyboard navigation, focus preservation and clear disabled-state explanations.
- [ ] **T032** · Ensure every visible button/control is wired end-to-end to real domain logic; no fake/placeholder controls.
- [ ] **G004 · GATE** — A user can manage hybrids/forms safely from F11 without relying on console commands for normal workflows.

## Phase E — CAS/MCCC recovery and Drift Guard

- [ ] **T033** · Make MCCC Shield state explicit: unarmed, armed, CAS-away, restore-ready, restored, failed.
- [ ] **T034** · Preserve the rule that Apex does not patch MCCC private internals.
- [ ] **T035** · Verify Lot51 event integration when present and a safe manual fallback when absent.
- [ ] **T036** · Persist/recover the minimum safe CAS snapshot needed for an interrupted session.
- [ ] **T037** · Add stale-snapshot detection so old recovery data cannot overwrite newer intentional edits.
- [ ] **T038** · Make Drift Guard event/user-triggered by default with no high-frequency hidden scan.
- [ ] **T039** · Show exactly which appearance categories drifted before repair.
- [ ] **T040** · Support repair-selected-category, repair-selected-occult and explicit repair-all with separate confirmation semantics.
- [ ] **T041** · Verify save/reload after CAS and after drift repair on representative hybrid combinations.
- [ ] **G005 · GATE** — CAS/MCCC/Drift workflows are recoverable, explainable and do not overwrite newer intent.

## Phase F — Performance and native overlay hardening

- [ ] **T042** · Measure hidden-overlay CPU, render-thread time, request rate and memory before optimizing.
- [ ] **T043** · Prove hidden overlay performs zero HTTP polling and no continuous Sim scan.
- [ ] **T044** · Batch/coalesce visible-overlay status requests so rapidly changing UI cannot flood the game thread.
- [ ] **T045** · Add generation IDs/cancellation so stale UI responses cannot overwrite newer selected-Sim intent.
- [ ] **T046** · Validate DX11 proxy/export compatibility against the current game executable before installation.
- [ ] **T047** · Fail closed on unknown/changed DX11 import/export surfaces instead of partially hooking.
- [ ] **T048** · Measure overlay frame-time impact on equivalent scenes and preserve rendering/gameplay quality.
- [ ] **G006 · GATE** — Overlay/control-plane overhead is measured, bounded and materially non-regressive.

## Phase G — Testing matrix

- [ ] **T049** · Build a fixture matrix for human + vampire/spellcaster/werewolf/mermaid/alien/ghost/PlantSim/Servo/fairy and available custom-occult combinations.
- [ ] **T050** · Add regression coverage for hybrid baby/aging/CAS entry-exit where supported by upstream behavior.
- [ ] **T051** · Add regression coverage for save/load/restart and household switching.
- [ ] **T052** · Verify selected-Sim, global-cache and CAS-cache diagnostics on real runtime state.
- [ ] **T053** · Verify F11 overlay, browser fallback and console diagnostics converge on the same domain state.
- [ ] **T054** · Exercise failure paths: missing packs, missing MCCC, missing Lot51, missing overlay DLL, stale snapshot and unsupported custom occult.
- [ ] **G007 · GATE** — Representative occult combinations and recovery paths are runtime-proven on the current TS4 build.

## Phase H — Release quality

- [ ] **T055** · Produce a clean source build and a separate user installation package.
- [ ] **T056** · Generate SHA-256 manifests and third-party notices for every shipped artifact.
- [ ] **T057** · Document exact supported game version, required packs/dependencies and optional integrations.
- [ ] **T058** · Add upgrade instructions from old TD1/IcedCream/Apex builds including duplicate-file cleanup.
- [ ] **T059** · Add troubleshooting for missing overlay, stale cache, CAS recovery and wrong occult state.
- [ ] **T060** · Run one final challenger pass against current public occult/hybrid utilities and adopt only demonstrably better compatible pieces with provenance.
- [ ] **G008 · GATE** — Release artifacts, docs, provenance and upgrade path are complete.

## Phase I — Close the original-mod failure ledger

The detailed reproduction/acceptance contract is `docs/USER_REPORTED_REGRESSIONS.md`. R001–R010 are release-blocking. A generic CAS smoke test does not satisfy this phase.

- [ ] **T061** · Reproduce and permanently regression-test R001: edits made in normal CAS or MC Command Center Modify in CAS can appear saved yet fail to persist to the intended occult form.
- [ ] **T062** · Reproduce and permanently regression-test R002: entering/customizing CAS must not delete, unlink, or make inaccessible any secondary hybrid form that existed before CAS.
- [ ] **T063** · Reproduce and permanently regression-test R003: hybrids must not become stuck in one form; current/pending/available/link state and visible form must converge after switching.
- [ ] **T064** · Reproduce and permanently regression-test R004: werewolf hair, headwear, body/CAS parts, custom content and outfit-specific parts must not disappear or corrupt during CAS, category changes, outfit changes, MCCC CAS, or form switching.
- [ ] **T065** · Explicitly test CAS entered while the Sim is already in werewolf form; edits must survive Live Mode return, form switch away/back, save/reload and full restart.
- [ ] **T066** · Reproduce and permanently regression-test R005: skin details, makeup, hair, tattoos, accessories, clothing/body parts and other CAS categories must not bleed across forms or disappear unexpectedly.
- [ ] **T067** · Reproduce and permanently regression-test R006: stale CAS-session, MCCC Shield, Saved Form or recovery snapshots must never overwrite a newer intentional edit.
- [ ] **T068** · Reproduce and permanently regression-test R007/R008: category-scoped copy/commit/repair must preserve unrelated CAS data, occult gameplay state and intentional differences between human and occult forms.
- [ ] **T069** · Prove the full MCCC Shield workflow from arm -> Modify in CAS -> Live -> restore links/state -> commit intended appearance -> switch away/back -> save/reload, without private MCCC monkey-patching.
- [ ] **T070** · Make Drift Guard fire-once/event-bounded around real risk points (CAS return, MCCC restore, form switch, outfit/category switch and explicit Scan) and prove it adds no timer/tick scanning regression.
- [ ] **T071** · Require post-mutation verification for every form/CAS repair: expected forms still exist, selected form is coherent, intended categories match, protected categories remain unchanged, and persistence survives form switch + save/reload.
- [ ] **T072** · Build the canonical real-runtime regression matrix from `docs/USER_REPORTED_REGRESSIONS.md` across representative human/vampire/spellcaster/werewolf/mermaid/alien/ghost/PlantSim/Servo/fairy hybrids where the packs/content are available.
- [ ] **G010 · GATE** — R001–R010 are no longer reproducible on the current supported Sims 4 build; the regression suite includes normal CAS, MCCC CAS, CAS while already in werewolf form, category/outfit switching, form switching, save/reload/restart and stale-snapshot recovery, with no lost secondary forms or unrelated CAS/occult data.

## Phase J — CAS History Studio

Detailed product/architecture contract: `docs/CAS_HISTORY_STUDIO.md`.

- [ ] **T073** · Create one canonical CAS Change Journal service shared by CAS History, Drift Guard, Post-CAS Commit, MCCC Shield and Saved Forms instead of separate snapshot/diff implementations.
- [ ] **T074** · Detect CAS lifecycle boundaries and capture a deterministic full checkpoint at CAS entry without starting a per-frame scan.
- [ ] **T075** · Capture meaningful CAS changes live as semantic events with target Sim, exact form identity, outfit slot, category/scope, source/provenance and before/after data.
- [ ] **T076** · Coalesce continuous slider/sculpt/high-frequency edits into one useful history action without merging unrelated operations.
- [ ] **T077** · Implement compact periodic checkpoint + semantic-delta storage with content-addressed deduplication, preserving the complete active CAS session without serializing every full form on every change.
- [ ] **T078** · Build the F11 Photoshop-style CAS History timeline with selectable entries, clear active-form lane, action labels, timestamps, verification state and filtering/search by form/outfit/category/source.
- [ ] **T079** · Build the change inspector showing added/removed/replaced CAS parts, resource IDs/names when resolvable, swatches, sliders/modifiers, skin details, tattoos, makeup, hair/headwear, accessories, clothing/body parts, occult-only parts, outfit scope and observed-vs-inferred provenance.
- [ ] **T080** · Implement Undo and Redo as validated new mutations through the canonical action queue; history evidence remains append-only.
- [ ] **T081** · Implement Jump to history state by computing the minimal current -> target delta, previewing protected changes, applying through the canonical action path, verifying result and recording the restore as a new event.
- [ ] **T082** · Preserve forward history as a recoverable branch when the user edits after undo/jump-back; never silently discard the old branch.
- [ ] **T083** · Implement named checkpoints and Compare-with-current, including optional reuse of Reference Shots for face/body/full-frame checkpoint images without capturing screenshots for every micro-change.
- [ ] **T084** · Implement selected-change/category revert and compatible cherry-pick/copy-to-form with explicit target form, compatibility validation, occult-only-part protection and before/after preview.
- [ ] **T085** · Give each human/occult/custom form an independent history lane and prevent cross-form flattening; unsupported custom forms remain opaque distinct identities until proven compatible.
- [ ] **T086** · Integrate MCCC Shield so Arm creates a checkpoint, MCCC/CAS changes are journaled/reconciled, Post-CAS Commit is visible in history, and persistence verification is recorded.
- [ ] **T087** · Integrate Drift Guard with the same snapshot/diff journal so drift detection/repair creates inspectable events and no second diff engine or timer scan exists.
- [ ] **T088** · Integrate Saved Forms so any history state can become a durable named form, a Saved Form restore becomes a journal event, and compatible categories can be cherry-picked without making one form globally canonical.
- [ ] **T089** · Persist interrupted CAS-session journals in Apex-owned local storage and provide read-only recovery inspection on next launch; never auto-apply an interrupted/stale checkpoint.
- [ ] **T090** · Add live “what is being applied?” status for pending/completed mutations including target form/outfit/categories, added/removed/replaced resources, skipped items/reasons, compatibility decisions and post-apply verification.
- [ ] **T091** · Prove the CAS History Studio specifically protects the R001–R010 failures: werewolf CAS while already transformed, hair/headwear/body-part retention, secondary-form survival, independent human/occult edits, stale-snapshot rejection and MCCC persistence.
- [ ] **T092** · Benchmark equivalent CAS editing sessions with CAS History off/on and prove materially non-regressive input latency, frame time, CPU, memory and storage behavior; optimize shared capture/diff paths rather than dropping history fidelity.
- [ ] **G011 · GATE** — CAS History Studio is live-runtime-proven on the current supported game build: history updates while editing, semantic diffs are understandable, undo/redo/jump/branches/checkpoints/reverts/cherry-pick work, hybrid form lanes remain isolated, MCCC/Drift/Saved Forms share one journal, interrupted recovery is safe, werewolf regression paths pass, and equivalent CAS responsiveness is materially non-regressive.

## Phase K — Apex CAS Unlock Core

Detailed architecture: `docs/APEX_CAS_UNLOCK_CORE.md`. Current challenger research: `docs/CAS_UNLOCKER_REFERENCE_MATRIX.md`.

- [ ] **T093** · Build one versioned canonical CAS unlock-policy registry covering category visibility, item visibility, required packs, age/frame/species constraints, form/occult compatibility, safety state, patch verification and provenance.
- [ ] **T094** · Resolve and fingerprint the actual current Sims 4 installation/build and installed packs; treat the current-game resources as authority rather than an old hand-maintained list.
- [ ] **T095** · Implement a patch-aware scanner for current CASP/category/UI/tuning/SimData resources, honoring patch/delta precedence over older full-build resources where applicable.
- [ ] **T096** · Implement the runtime Keep-Unlocked policy for supported CAS categories on CAS entry, Sim switch, form switch, outfit switch and real UI/category rebuild boundaries with no high-frequency polling.
- [ ] **T097** · Keep human and occult/custom form category policy independent so unlocking more categories never flattens form identity or copies appearance across forms.
- [ ] **T098** · Implement default-on Occult Expanded policy for compatible Werewolf, Vampire, Mermaid, Fairy, Alien/disguise and other supported occult/hybrid forms while preserving occult-only categories.
- [ ] **T099** · Implement Hidden/Locked Catalog classification and optional exposure for locked, hidden/reward, debug/NPC, occult-restricted and special/temporary CAS resources.
- [ ] **T100** · Preserve age/species/frame/body-type safety by default; visibility does not imply safe application, and advanced compatibility bypasses remain explicit/opt-in with warnings.
- [ ] **T101** · Implement installed-pack-aware generation so users never need to manually remove unlock files for packs they do not own and pack install/uninstall invalidates only affected catalog segments.
- [ ] **T102** · Implement the deterministic Patch-Aware Unlock Catalog Builder that generates minimal Apex-owned unlock package(s), JSON manifest, resource coverage/diff report and SHA-256 lineage from current game data.
- [ ] **T103** · On a game-build mismatch, mark generated unlock data stale, retain only runtime policy that passes current introspection, regenerate in staging, diff/validate, and promote only after targeted proof.
- [ ] **T104** · Detect new/changed CAS categories/resources after an EA patch and surface them as reviewed/unclassified/unsupported instead of silently omitting them.
- [ ] **T105** · Implement P0 Werewolf unlock coverage including hair/headwear, skin details, tattoos, compatible makeup/face paint, accessories, scars/details, body/head/coat categories, archetype/face categories and base layers where current game data supports them.
- [ ] **T106** · Regression-test the historical missing-Werewolf-faces/category class of failure and prove category/outfit/form switches cannot strip valid Werewolf parts merely because UI availability changed.
- [ ] **T107** · Implement Mermaid/Fairy/occult parity including Mermaid fingernails, Fairy-era categories and occult archetype surfaces discovered in current game data; new future occult surfaces must be reported for policy review.
- [ ] **T108** · Build the F11 Unlock Matrix showing category/item status, current form, pack source, CASP/resource identity, hidden/locked/debug/reward/occult state, safety/compatibility reason, last-verified patch and reassert/repair state.
- [ ] **T109** · Add event-bound “stay unlocked” verification: when an enabled category unexpectedly disappears, journal the event, attempt one safe policy reassertion, verify it, and expose failure instead of looping.
- [ ] **T110** · Integrate unlock visibility/application events with CAS History Studio while keeping visibility changes separate from actual appearance mutations.
- [ ] **T111** · Detect likely overlapping CAS unlock overrides/packages, including Crilender/Loulicorn-style overlap where identifiable, report conflicting TGIs/winner order, and never delete third-party files.
- [ ] **T112** · Import/inventory the authorized Crilender v1.9h package/addon resources as the initial unlock coverage matrix, then use Sims package tooling (including S4TK/LlamaLogic/ModTS4 where useful) to consolidate and improve them into the Apex package build.
- [ ] **T113** · Prove current-build runtime behavior across Human, Vampire/Dark Form, Werewolf, Mermaid, Fairy, Alien/disguise and a representative multi-occult hybrid through CAS entry/re-entry, outfit switch, form switch, MCCC CAS, CAS History undo/redo and save/reload/restart.
- [ ] **T114** · Benchmark equivalent CAS interaction with unlock core disabled/enabled and prove category reassertion/catalog lookups add no material frame-time, input-latency, CPU or memory regression; expensive game-resource scans must remain outside active CAS.
- [ ] **T115** · Implement a native reward-unlock lane for CAS resources governed by the game's own reward/ownership system, preferring durable Sim/household unlock semantics over forced CASP visibility when the native path is available; discover from current game data and journal/verify persistence.
- [ ] **T116** · Prove the complete CAS Unlock Core on a clean test Mods profile containing Apex and no Crilender/Loulicorn/Szemoka/other CAS unlocker, no Lot51 Core, no XML Injector and no unlock-related third-party script library; all supported category, catalog, reward-unlock, patch-fingerprint and hybrid behaviors must remain available.
- [ ] **T117** · Build the canonical first-party `ApexCASUnlocks.package` from Apex source/policy + current supported game resources, with deterministic/reproducible resource ownership, STBL/tuning/resource manifests and no opaque hand-only binary edits.
- [ ] **T118** · Generate and verify the package release manifest: Apex version, supported Sims 4 build fingerprint, resource counts/types, source-game resource hashes, pack coverage, SHA-256, build command/toolchain and per-resource policy owner.
- [ ] **T119** · Test the exact hashed release `ApexCASUnlocks.package` in the current game across the full G012 matrix; do not substitute an unpackaged dev path or script-only fallback for package proof.
- [ ] **T120** · Prove a normal user install requires one coherent Apex unlock package rather than per-pack/per-occult addon-file micromanagement; if internal generation modules exist, release packaging must converge them into one install path and one manifest/ownership model.
- [ ] **G012 · GATE** — Apex CAS Unlock Core is current-game-runtime-proven: intended categories stay unlocked through supported transitions, hidden/locked catalog exposure is pack/form/safety aware, Werewolf and other occult regressions remain fixed, patch mismatch/regeneration is deterministic and observable, F11 explains availability, third-party proprietary content is not copied, the complete unlock feature set is proven standalone with no third-party unlocker/script-library runtime dependency, the exact first-party `ApexCASUnlocks.package` release artifact is reproducibly built/hashed/runtime-tested, and CAS performance remains materially non-regressive.

## Phase L — Standalone Apex Occult Hybrid Core

Detailed architecture: `docs/APEX_OCCULT_HYBRID_CORE.md`.

- [ ] **T121** · Import/inventory the authorized current TD1/LordPercival hybrid package/script implementation and map its working membership/form/panel/transformation/CAS behaviors into one Apex capability model that separates occult membership, visible/current form, linked form state, selected gameplay/perk-panel occult, pending transformation, temporary occult/status state and CAS/recovery state.
- [ ] **T122** · Build the canonical `ApexOccultHybrid.package` source/policy pipeline from current supported game resources; every generated/authored tuning/STBL/injection resource must have an Apex owner, source/evidence record, patch fingerprint and regression test.
- [ ] **T123** · Build the canonical `ApexOccultHybrid.ts4script` runtime entrypoint and domain modules; production code must not import or require TD1/TwelfthDoctor1/IcedCream/LordPercival runtime modules.
- [ ] **T124** · Implement independent hybrid membership support so a compatible Sim can hold multiple supported occult identities without one identity erasing another.
- [ ] **T125** · Independently unlock compatible official occult transformation paths for already-occult Sims using the narrowest current-build tuning/injection changes rather than globally deleting unrelated tests.
- [ ] **T126** · Implement Apex Add Occult and Remove Occult actions with explicit previews, idempotence and verification; removing one occult must preserve every unrelated occult form, appearance, rank, perks, motives and progression.
- [ ] **T127** · Replace blind “always human first” switching with an explicit transformation state machine that uses a safe intermediate only when current-game behavior actually requires it.
- [ ] **T128** · Detect/recover stuck or contradictory transformation state: pending never clears, snap-back, current form absent from available forms, missing linked form, partial visual switch or multiple conflicting current-form indicators.
- [ ] **T129** · Implement independent selected gameplay/perk-panel state so a hybrid can choose which occult UI/powers/motives are in focus without changing occult membership.
- [ ] **T130** · Implement/verify Spellcaster charge/orb and Werewolf Fury/orb presentation according to the selected supported gameplay panel/secondary form, without corrupting underlying occult state.
- [ ] **T131** · Implement/verify Vampire, Mermaid, Fairy, Alien and other current supported occult gameplay-panel/motive behavior where the game exposes such a surface; unsupported/new surfaces remain explicit rather than silently ignored.
- [ ] **T132** · Model PlantSim, Ghost, Servo and other temporary/pseudo-occult/mechanical states through capabilities instead of forcing every state into the same linked-form implementation.
- [ ] **T133** · Integrate hybrid membership/form transitions with the canonical CAS Change Journal so CAS History records transformations, membership changes, repairs and target-form commits with provenance.
- [ ] **T134** · Replace historical remove-all-occults-before-CAS behavior with form inventory + minimal checkpoint + targeted post-CAS reconciliation; never remove every occult as the default CAS strategy.
- [ ] **T135** · Preserve independent human/occult appearance ownership through CAS, MCCC, form switching, Saved Forms and Drift Guard; prove no cross-form flattening or stale snapshot overwrite.
- [ ] **T136** · Preserve occult-specific progression through unrelated hybrid/form operations, including rank, powers/perks, weaknesses, points/currency, motives/commodities, spell knowledge, Fury/charge and pack-specific persistent state where applicable.
- [ ] **T137** · Implement F11 hybrid diagnostics showing membership, current/available forms, linked-form identities, pending transition, selected gameplay panel, relevant motives/orbs, cache/recovery state and exact inconsistency reasons.
- [ ] **T138** · Add patch-aware discovery of current occult traits/forms/transformation interactions/UI/tuning; new EA occult surfaces must appear as `unclassified / support review required` rather than being treated as human or discarded.
- [ ] **T139** · Generate deterministic source/release manifests for `ApexOccultHybrid.package` and `ApexOccultHybrid.ts4script`, including Apex version, Sims 4 build, installed-pack coverage, resource/module counts, source-game hashes, SHA-256 and build commands.
- [ ] **T140** · Detect overlapping legacy/third-party hybrid packages/scripts and report likely double-ownership/conflicts without deleting them; Apex core behavior must remain complete when they are absent.
- [ ] **T141** · Prove clean-profile operation with Apex + official EA packs only: no TD1/IcedCream/LordPercival hybrid files, no other hybrid stabilizer, no MCCC, no Lot51 Core and no XML Injector.
- [ ] **T142** · On the clean profile, prove compatible multiple-occult membership, official transformation paths, repeated form switching, Add/Remove Occult, selected gameplay/perk panels, Spellcaster/Werewolf orb behavior and save/reload/restart persistence.
- [ ] **T143** · On the clean profile, prove CAS from human and already-transformed forms preserves every secondary occult/form, intended edits, independent appearances and progression while keeping R001–R010 closed.
- [ ] **T144** · Test the exact hashed production `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script` pair in the current supported Sims 4 build; do not substitute recovered TD1 artifacts, dev-only mocks or an unpackaged fallback.
- [ ] **T145** · Run a bounded challenger pass against current hybrid solutions and the authorized baseline itself; preserve/port superior authorized pieces directly where useful, replace weaker pieces, document adopt/adapt/port/replace decisions, and ensure the final install no longer requires the old package.
- [ ] **G013 · GATE** — Apex Occult Hybrid Core, built upward from the authorized current hybrid implementation baseline, matches or exceeds its verified useful capabilities; the exact first-party package/script pair is reproducibly built, clean-profile/current-game-runtime-proven, preserves form/CAS/progression state, supports hybrid transformations/panels, keeps R001–R010 closed, and requires no TD1/IcedCream/LordPercival or other hybrid runtime dependency.

- [ ] **G009 · FINAL COMPLETION GATE** — All accepted tasks/gates are complete; no unresolved blocker remains; production packaging succeeds; the current TS4 build has exercised the exact standalone `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script` pair, F11 occult toggles, form switching, Saved Forms, CAS Categories, Apex CAS Unlock Core/Unlock Matrix and the exact release `ApexCASUnlocks.package`, Photoshop-style CAS History/Undo/Redo, MCCC Shield, Drift Guard, diagnostics, save/reload/restart and representative hybrid combinations; every R001–R010 original-mod regression is proven fixed on the current supported game build; the useful 1.13.7 behavioral reference floor is independently satisfied without upstream runtime files; overlay performance is measured on equivalent workloads; and no requested capability was silently removed or replaced by a placeholder.
