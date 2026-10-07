# Full TODO — TD1 Occult Hybrid Apex

The canonical executable checklist is [docs/CODEX_MASTER_EXECUTION.md](../docs/CODEX_MASTER_EXECUTION.md). This page is the human-readable wiki view.

## P0 — parity and safety

- Close every verified upstream 1.13.7 delta.
- Reconcile authoritative SimInfo/OccultTracker state versus transient caches.
- Prove no native render-thread gameplay mutation.
- Prove save/reload/restart on representative hybrids.
- Fail closed on unknown game/native hook surfaces.

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

Do not call Apex finished until the current Sims 4 build has exercised the actual F11 workflows, representative hybrid combinations, CAS/MCCC recovery, Drift Guard, diagnostics, persistence, upgrade path and measured overlay overhead.
