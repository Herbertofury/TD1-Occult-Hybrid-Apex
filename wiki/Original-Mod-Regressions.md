# Original Mod Pain Points & Regression Ledger

These are the bugs Apex exists to eliminate. They are **release blockers**, not optional polish.

## The failures we must never ship again

- **CAS/MCCC edits do not stick** — the edit looks saved, then the occult form reverts or never receives it.
- **Secondary hybrid forms get deleted/lost after CAS** — only the form used to enter CAS survives correctly.
- **Sim gets stuck in one form** — form switching does nothing, snaps back, or leaves state half-switched.
- **Werewolf CAS parts get stripped/corrupted** — including hair/headwear or other werewolf parts disappearing after category/outfit changes.
- **CAS opened while already in werewolf form does not reliably save edits.**
- **Wrong skin details, makeup, hair, tattoos, accessories or clothing bleed between forms or vanish.**
- **Human and occult forms overwrite each other** when they should remain independently editable.
- **Stale CAS/recovery snapshots overwrite newer good edits.**
- **Broad repair/copy operations damage unrelated categories or occult state.**
- **A tool says “success” even though switching forms or reloading proves the edit was not actually persisted.**

## Apex behavior required

1. Know which persistent form owns an edit.
2. Preserve every pre-existing secondary form across CAS/MCCC.
3. Never delete an ambiguous/unknown form to “fix” state.
4. Diff before repair.
5. Repair the narrowest requested scope.
6. Treat intentional newer state as authoritative over stale snapshots.
7. Verify by switching away/back, saving, reloading and restarting.
8. Keep Drift Guard event/user-triggered rather than adding timer/tick lag.
9. Preserve unrelated CAS categories, occult traits/powers/progression and custom content.
10. Never call a mutation successful until the post-operation state proves it.

See the canonical engineering ledger: [docs/USER_REPORTED_REGRESSIONS.md](../docs/USER_REPORTED_REGRESSIONS.md).
