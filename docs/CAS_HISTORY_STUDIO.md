# CAS History Studio — Photoshop-Style Live CAS Journal, Undo/Redo, Diff & Hybrid-Aware Recovery

Last reconciled: 2026-10-06

## Product goal

While the user is inside Create-a-Sim, Apex should provide a **live Photoshop-style history panel** that records meaningful CAS changes as they happen, explains exactly what each change touched, and lets the user safely undo, redo, jump to an earlier state, restore selected categories, or cherry-pick a change without corrupting hybrid occult forms.

This is not a second standalone mod and not a second injection. It should reuse the existing Apex F11 overlay, native DX11 proxy/injection, Python backend, state-diff engine, game-thread command queue, MCCC Shield, Saved Forms and Drift Guard infrastructure wherever technically safe.

The history system is also intended to help diagnose and prevent the original mod failures documented in `docs/USER_REPORTED_REGRESSIONS.md`.

---

# Architecture decision

## One shared CAS Change Journal

Create one canonical **CAS Change Journal** service owned by the Apex backend.

Conceptual flow:

```text
CAS / MCCC / Apex change
        |
        v
CAS observer / supported CAS lifecycle signals
        |
        | read-only observation
        v
canonical appearance snapshot + semantic diff engine
        |
        +----> CAS Change Journal
        |        - ordered events
        |        - checkpoints
        |        - branches
        |        - provenance
        |        - per-form/per-outfit/category scope
        |
        +----> Drift Guard
        +----> Post-CAS Commit
        +----> MCCC Shield
        +----> Saved Forms
        |
        v
F11 CAS History Studio
        |
        | validated command only
        v
Python/game-thread mutation queue
        |
        v
CAS / SimInfo / occult-form state
```

## Reuse the same injection

Do **not** introduce a second DLL/proxy or a second always-running hook stack just for CAS history.

Preferred order:

1. Use supported Sims/CAS lifecycle or state-change signals available to the Python/backend layer.
2. Use the existing Apex native module only for read-only observation that cannot be obtained safely otherwise.
3. If fine-grained native CAS observation is genuinely required, add it as a read-only observer inside the existing injected Apex module and publish compact typed events to the same backend.
4. All state-changing undo/redo/revert/apply operations still go through the canonical validated game-thread/CAS action path. The render thread must never directly rewrite Sim/CAS memory.

This keeps resource use, compatibility risk, patch sensitivity and duplicated state to a minimum.

---

# User experience

## F11 -> CAS History Studio

When CAS is active, F11 gets a dedicated **CAS History** workspace.

The default layout should feel familiar to Photoshop/history-based creative tools:

### Left / center: History timeline

Each entry shows:

- sequence number;
- time;
- target Sim;
- target form;
- outfit slot;
- category/scope;
- concise action label;
- source;
- before -> after summary;
- verification state.

Examples:

- `#018 Werewolf · Everyday 1 · Hair · Changed CAS Part`
- `#019 Werewolf · Head Detail · Slider/sculpt stroke`
- `#020 Human · Skin Details · Added 2 / Removed 1`
- `#021 Vampire Dark Form · Makeup · Preset applied`
- `#022 Apex · Restore checkpoint "Before MCCC CAS"`
- `#023 MCCC/CAS · Outfit changed`

### Right: Change inspector

Selecting a history entry shows the semantic diff.

Where available show:

- CASPart resource IDs and resolved names;
- added parts;
- removed parts;
- replaced parts;
- color/swatch changes;
- slider/body/facial modifier changes;
- skin details;
- tattoos;
- makeup;
- hair/headwear;
- accessories;
- clothing/body parts;
- occult-only / form-specific parts;
- outfit slot;
- affected form identity;
- whether the change is directly observed or inferred from snapshot comparison;
- conflict/exclusivity warnings;
- why the change is safe or unsafe to apply elsewhere.

### Toolbar

Provide:

- Undo
- Redo
- Jump to selected history state
- Restore selected change
- Revert selected change
- Revert selected category
- Restore full checkpoint
- Create named checkpoint
- Compare with current
- Cherry-pick selected change
- Copy selected change to another compatible form
- Export session diagnostics
- Clear completed old sessions only with explicit user intent

No visible control may be a placeholder.

---

# History semantics

## Semantic events, not frame-by-frame noise

The journal should record **meaningful user actions**, not thousands of transient render/update events.

Examples of grouping/coalescing:

- a continuous face/body slider drag -> one history action;
- a sculpt stroke or rapid sequence affecting one modifier -> one action after a short inactivity boundary;
- choosing a swatch -> one action;
- replacing hair -> one action;
- adding/removing several related skin details through one preset -> one grouped action when the game exposes them as one transaction;
- randomize/preset -> one parent action with inspectable child diffs;
- outfit switch -> one state-boundary event;
- form switch -> one state-boundary event;
- MCCC return -> one reconciliation boundary plus the individual appearance diffs that actually occurred.

Do not coalesce unrelated actions merely to reduce event count.

## Provenance

Every event should record its source when knowable:

- native CAS UI;
- game-driven normalization;
- randomize/preset;
- MCCC CAS session;
- Apex action;
- Saved Forms;
- Drift Guard;
- unknown/inferred external mutation.

If exact source is unknowable, say `inferred` rather than inventing provenance.

---

# Snapshots + deltas

Use a compact **periodic full snapshot + semantic delta** model.

Requirements:

- full snapshot at CAS entry;
- full snapshot before risky recovery/restore operations;
- full snapshot at named checkpoint;
- full snapshot around form ownership changes when needed;
- semantic deltas for normal edits;
- content-addressed deduplication for unchanged CAS parts/resources;
- hashes for fast equality testing;
- checkpoint material sufficient for deterministic reconstruction;
- no silent dropping of the active CAS session history.

This is intended to be substantially cheaper than storing a full Sim appearance blob after every micro-change.

Older completed sessions may use configurable retention/cleanup, but the active session must remain complete.

---

# Photoshop-style undo / redo model

## Linear history with preserved branches

Normal editing produces a linear history.

If the user jumps backward and then makes a new edit:

- create a new branch;
- do not silently destroy the old forward history;
- show the prior branch as recoverable until the user explicitly discards it or retention policy expires after the session.

This protects against accidental “undo then edit” data loss.

## Jump-to-state

Jumping to an old state must:

1. resolve the exact target form/outfit;
2. validate compatibility;
3. calculate the minimal delta from current -> target;
4. preview protected/unrelated categories that would change;
5. execute through the canonical action queue;
6. verify the resulting CAS state;
7. add the restore as a new journal event instead of rewriting history.

History is append-only evidence; reverting creates a new event.

---

# Hybrid-aware design

This is mandatory.

## Separate form lanes

History must distinguish:

- human/base form;
- vampire dark form;
- werewolf form;
- mermaid form;
- alien disguise / alien form;
- spellcaster state where appearance form semantics apply;
- ghost/PlantSim/Servo/fairy/custom forms when supported;
- any additional detected linked occult form.

A user editing one form must not accidentally overwrite another.

The UI should make the active form extremely obvious.

## Cross-form actions are explicit

A change may be copied/cherry-picked from one form to another only after:

- target form is explicitly selected;
- compatibility is checked;
- occult-only CAS parts are identified;
- mutually exclusive categories are resolved;
- a preview shows what will change;
- the user confirms when data loss would otherwise occur.

Examples:

- copying a human hairstyle to werewolf should be rejected or translated only if the target form cannot legally use that part;
- copying a werewolf-only head/body part to human must never silently strip/replace the human face;
- copying makeup between compatible forms should touch only makeup.

## Form survival

At CAS entry and exit, the journal/checkpoint layer must verify that every form known before CAS still exists afterward unless the user explicitly removed it.

This directly protects R002/R003/R004.

---

# Live “what is being applied?” inspector

Add a live inspector that can show the most recent or pending semantic mutation.

For each applied/reverted/restored action show:

- action source;
- target Sim;
- target form;
- target outfit;
- target categories;
- resources/values added;
- resources/values removed;
- resources/values replaced;
- compatibility decisions;
- skipped items and why;
- post-apply verification result.

For ambiguous changes, use `unknown/inferred` and preserve data rather than guessing.

---

# Checkpoints and reference images

Reuse the existing Reference Shots capability.

Optional visual checkpoints may capture:

- face;
- body;
- full frame;

at named checkpoints or major CAS boundaries.

Do **not** capture a screenshot on every slider movement.

The history panel should pair a semantic checkpoint with its optional reference image so the user can visually compare “before MCCC CAS,” “after werewolf edit,” and similar states without excessive I/O.

---

# MCCC Shield integration

CAS History Studio should become the visibility layer for MCCC Shield.

Recommended flow:

```text
Arm MCCC Shield
 -> automatic named checkpoint
 -> enter MCCC Modify in CAS
 -> journal changes during/after CAS
 -> return to Live
 -> reconcile form links/state
 -> show exact semantic diff
 -> user accepts/adjusts target form
 -> Post-CAS Commit
 -> verify
 -> checkpoint "Committed after MCCC"
```

The journal must make it obvious whether the visible CAS edit has actually reached the intended stored occult form.

---

# Drift Guard integration

Do not build a second diff engine.

Drift Guard and CAS History should use the same canonical appearance snapshot/diff model.

Drift Guard may create events such as:

- `Drift detected: Werewolf Hair + Head Detail`
- `Repair applied: Werewolf Hair only`
- `Repair rejected: snapshot stale`

This gives the user a human-readable audit trail for repair behavior.

---

# Saved Forms integration

Saved Forms become durable named appearance snapshots that can be related to a CAS History checkpoint.

Capabilities:

- Save current history state as a Saved Form.
- Restore a Saved Form as a new journal event.
- Compare Saved Form vs current.
- Cherry-pick compatible categories from a Saved Form.
- Never silently make a Saved Form the canonical source for every occult form.

---

# Crash/restart recovery

If CAS/game crashes mid-session:

- persist the journal/checkpoint data outside the save in Apex-owned local storage;
- mark it as an interrupted session;
- on next launch, offer read-only inspection first;
- allow recovery only after matching Sim/form identity and freshness checks;
- never auto-apply an interrupted checkpoint.

This is recovery evidence, not a replacement save system.

---

# Performance contract

CAS History must not make CAS feel slower.

Requirements:

- no screenshot per micro-change;
- no full serialization of every form on every frame;
- no polling when CAS is not active;
- prefer event/state-change driven capture;
- hash/deduplicate immutable CAS resources;
- coalesce continuous modifier gestures;
- compute heavy diffs off the render thread;
- bound queues and cancel stale diff work;
- preserve all active-session semantic history;
- benchmark CAS interaction latency, CPU, memory and storage overhead before/after.

The same existing overlay/injection and command queue should be reused unless runtime proof shows a separate mechanism is necessary.

---

# Safety rules

- Undo/revert never edits a different form merely because it visually resembles the selected form.
- Unknown custom CAS data is preserved.
- Unsupported custom occult forms are treated as distinct opaque form identities until proven otherwise.
- No stale checkpoint may overwrite a newer intentional edit without an explicit warning/choice.
- A failed partial revert must not be labeled success.
- Any operation that changes multiple protected categories must show that fact before execution.
- History itself is append-only for the current session; undo is a new mutation event, not deletion of evidence.

---

# Runtime acceptance

Do not call CAS History Studio complete until the exact release build proves all of the following in the current supported Sims 4 runtime:

1. F11 history updates while CAS edits occur.
2. Continuous slider/sculpt edits coalesce into useful actions instead of flooding the timeline.
3. Hair, makeup, tattoos, skin details, accessories, clothing/body parts and outfit changes produce understandable semantic diffs.
4. Undo and redo restore the exact intended state.
5. Jump-to-state works and records the restore as a new event.
6. Editing after undo creates a recoverable branch.
7. Named checkpoints work.
8. Optional reference images work without being captured for every micro-change.
9. The active human/occult form is always clearly distinguished.
10. Cross-form cherry-pick validates compatibility and never strips unrelated parts.
11. CAS entered while already in werewolf form is fully journaled and recoverable.
12. MCCC Modify in CAS is journaled through the shield/commit workflow.
13. Secondary hybrid forms survive CAS.
14. Form switching after restore returns the correct stored appearance.
15. Save/reload/full restart preserves committed edits.
16. Interrupted-session recovery cannot overwrite newer state silently.
17. Drift Guard, Saved Forms and Post-CAS Commit use the same snapshot/diff engine rather than divergent private copies.
18. CAS responsiveness remains materially non-regressive under an equivalent editing workload.
