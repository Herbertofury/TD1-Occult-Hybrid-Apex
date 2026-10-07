# CAS History Studio

**Photoshop-style history for Create-a-Sim, built directly into Apex.**

While CAS is open, the F11 overlay should show a live timeline of meaningful edits: what changed, on which form, which outfit/category was touched, what resources were added/removed/replaced, and whether the change has actually been committed to the intended occult form.

## What it should feel like

- live Photoshop-style History panel;
- Undo / Redo;
- click any earlier state and restore it;
- named checkpoints;
- branch history instead of deleting redo states;
- compare selected entry with current;
- revert one change or one category;
- cherry-pick a safe change to another form;
- full semantic change inspector;
- optional face/body/full reference images at checkpoints;
- exportable CAS session log.

## Hybrid awareness is mandatory

Every entry belongs to the correct form lane: human/base, vampire dark form, werewolf, mermaid, alien, fairy/custom, etc.

Apex must never use CAS History to flatten every form into one appearance.

Cross-form copy is explicit and compatibility-checked.

## Especially important for werewolves

CAS History must capture and protect:

- edits made while already in werewolf form;
- hair/headwear;
- body/head CAS parts;
- outfit changes;
- category changes;
- custom content;
- form-switch round trips.

If a werewolf part disappears unexpectedly, the timeline should show **which action removed/replaced it**, and the user should be able to restore the prior valid state.

## Shared architecture

No second overlay or second DLL injection.

CAS History should reuse:

- the existing F11 Dear ImGui overlay;
- existing native injection/proxy when native observation is needed;
- one canonical CAS snapshot/diff journal;
- the existing Python/game-thread mutation queue;
- MCCC Shield;
- Post-CAS Commit;
- Drift Guard;
- Saved Forms;
- Reference Shots.

That gives us one source of truth and avoids duplicated polling/state/resource overhead.

Full engineering spec: [docs/CAS_HISTORY_STUDIO.md](../docs/CAS_HISTORY_STUDIO.md).
