# Full TODO — TD1 Occult Hybrid Apex

The canonical executable checklist is [docs/CODEX_MASTER_EXECUTION.md](../docs/CODEX_MASTER_EXECUTION.md). This page is the human-readable wiki view.

## P0 — parity and safety

- Close every verified upstream 1.13.7 delta.
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

## P1 — make F11 the best way to use the mod

- Selected-Sim dashboard with active occults/current form/health.
- One-click occult enable/disable with safe confirmations.
- Form switching with target preview.
- Searchable/renameable Saved Forms.
- Category-scoped copy/paste/commit/apply-all.
- Undo for the latest safe reversible appearance operation.
- Keyboard/focus/accessibility pass.

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

Do not call Apex finished until R001–R010 in the original-mod regression ledger are no longer reproducible and the current Sims 4 build has exercised the actual F11 workflows, representative hybrid combinations, CAS/MCCC recovery, Drift Guard, diagnostics, persistence, upgrade path and measured overlay overhead.
