# TD1 Occult Hybrid Apex — Codex Master Execution Contract

Last reconciled: 2026-10-06
Recovered baseline: V9.5 Final Accounting / Runtime Safe
Upstream parity floor: Occult Hybrid Unlocker & Stabilizer 1.13.7 (FIXE)

## Objective

Finish TD1 Occult Hybrid Apex as a safe, polished, observable hybrid-occult control suite that is materially easier to use and recover than the upstream mod while preserving upstream compatibility and all still-valid V9.5 behavior.

## Context

The recovered V9.5 project already contains a large Sims/Python backend, a Windows x64 DX11 Dear ImGui overlay source kit, saved-form support, MCCC/CAS shield behavior, Drift Guard, reference shots, category-scoped appearance operations, diagnostics, localhost control endpoints and extensive offline validation reports.

Do not restart this project as a new mod. Reuse and harden the recovered implementation.

## Constraints

- Preserve save safety and require explicit user intent for destructive/ambiguous occult mutations.
- The native render thread must never mutate Sims state directly. Send typed commands to the Python/game-thread owner.
- Hidden overlay mode must not poll Sims/HTTP continuously.
- No private MCCC monkey-patching.
- Auto repair stays opt-in.
- No quality/content reduction to claim performance wins.
- Upstream 1.13.7 fixes are a required compatibility floor, not optional inspiration.
- Keep attribution/licensing/provenance for upstream or vendored work.
- Never call build/static checks live-game proof.

## Resume rule

Continue from the earliest unchecked or invalidated task whose dependencies are satisfied. Work in bounded internal windows of roughly 6–12 ready leaf tasks, update this file in place, checkpoint coherent source state, and continue. If two materially unchanged attempts fail without new evidence, change strategy. Blockers remain inline as `BLOCKED: ...; NEXT: ...`.

## Phase A — Recover and normalize V9.5

- [ ] **T001** · Verify the recovered archive SHA-256 and current repository source manifest against the V9.5 recovery record.
- [ ] **T002** · Normalize the repository layout without deleting historical reports or provenance.
- [ ] **T003** · Resolve the canonical Sims/Python backend entrypoint and document every packaged script/module owner.
- [ ] **T004** · Resolve the canonical native-overlay entrypoint, DX11 proxy/export model and installation path.
- [ ] **T005** · Identify all duplicated/obsolete V5–V9 compatibility paths inside the large Python source and mark which remain runtime-reachable.
- [ ] **T006** · Add deterministic source-manifest generation for text and binary artifacts.
- [ ] **G001 · GATE** — Recovery is reproducible and no V9.5 capability was silently lost.

## Phase B — Upstream 1.13.7 parity floor

- [ ] **T007** · Diff Apex behavior against the latest distributed 1.13.7 package/source evidence instead of assuming the public GitHub tree contains every 1.13.7 change.
- [ ] **T008** · Port/verify the missing-STBL fix.
- [ ] **T009** · Port/verify the TMex PhoneSearch / PlantSim Pie Menu compatibility change.
- [ ] **T010** · Port/verify missing `ClassInstanceTuningInjections` coverage for werewolf traits.
- [ ] **T011** · Port/verify missing `ClassInstanceTuningInjections` coverage for fairy traits.
- [ ] **T012** · Port/verify missing `ClassInstanceTuningInjections` coverage for fairy bloodline traits.
- [ ] **T013** · Provide Apex-equivalent diagnostics for selected-Sim occult cache state.
- [ ] **T014** · Provide Apex-equivalent diagnostics for global occult cache state.
- [ ] **T015** · Provide Apex-equivalent diagnostics for CAS-session cached Sims/households.
- [ ] **T016** · Add regression fixtures proving 1.13.7 parity work does not bypass Apex safety/queue ownership.
- [ ] **G002 · GATE** — Apex contains every verified 1.13.7 compatibility fix and retains V9.5 behavior.

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

- [ ] **G009 · FINAL COMPLETION GATE** — All accepted tasks/gates are complete; no unresolved blocker remains; production packaging succeeds; the current TS4 build has exercised F11 occult toggles, form switching, Saved Forms, CAS Categories, MCCC Shield, Drift Guard, diagnostics, save/reload/restart and representative hybrid combinations; upstream 1.13.7 parity is proven; overlay performance is measured on equivalent workloads; and no requested capability was silently removed or replaced by a placeholder.
