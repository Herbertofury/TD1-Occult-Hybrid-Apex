# User-Reported Original Mod Regressions — Non-Negotiable Fix Ledger

Last reconciled: 2026-10-06

This is not a wishlist. These are concrete failure modes experienced with the original/older hybrid-occult workflow and are **release-blocking regressions for Apex**.

Codex must reproduce, isolate the earliest causal owner, fix the shared cause, add regression protection, and prove the real workflow on the current Sims 4 build. Do not paper over them with “repair all,” repeated cache deletion, forced form resets, or destructive reconstruction of a Sim.

## R001 — CAS / MC Command Center edits do not persist

### Observed failure
- A Sim is edited in CAS, including CAS entered through MC Command Center.
- The edit looks correct in CAS or immediately after returning to Live Mode.
- The intended occult form does not actually keep the edit, or the old appearance returns later.
- This has been especially troublesome when editing occult-specific forms.

### Required Apex behavior
- Detect which live/stored occult form is being edited.
- After CAS exit, reconcile visible/live appearance with the correct persistent occult-form record.
- Never silently apply the edit only to the temporary/current representation while leaving the stored occult form stale.
- MCCC Shield/Post-CAS Commit must make this flow explicit and safe rather than relying on private MCCC hooks.
- A successful commit must survive:
  1. form switch away and back;
  2. outfit/category switch;
  3. household switch;
  4. save;
  5. reload;
  6. full game restart.

### Failure must be visible
If Apex cannot prove which occult form should receive the edit, it must show an ambiguity/error state and preserve both states. It must not guess and overwrite a form.

---

## R002 — Secondary hybrid forms disappear after CAS

### Observed failure
Entering/customizing a hybrid Sim in CAS can leave only the form used to enter CAS intact while one or more secondary occult forms disappear, become inaccessible, or lose their stored appearance.

### Required Apex behavior
Before CAS/MCCC mutation:
- inventory every linked occult/form record relevant to the Sim;
- preserve stable identity for each form;
- capture only the minimum recovery snapshot needed.

### Owner's mandatory six-occult workflow — 2026-10-07

Create one disposable Sim with Alien, Vampire, Mermaid, Spellcaster, Werewolf
and Fairy memberships. Edit each distinct supported appearance form in CAS
entered through MCCC and through the game's own CAS entry, using visibly
different presets, clothing, skin details and colors. Retain exact per-form
snapshots and screenshots. Switch away and back through Apex's actual Live
menu, unpause to settle engine changes, then verify every edited form and every
unrelated form. Repeat after save/reload and a complete game restart.

Spellcaster and other memberships without a separate native CAS appearance
must be explicitly mapped to their shared appearance owner; do not fabricate a
separate saved form or overwrite another membership's look. MCCC coexistence
and standalone Apex runs use the same retained test profile, with exact addon
receipts. Never load the original Mods library or original saves for this test.
Passing membership/form switches alone does not satisfy this workflow.

After CAS:
- prove every pre-existing form still exists unless the user intentionally removed it;
- detect missing form links/records immediately;
- offer narrow recovery for the affected form without overwriting newer valid edits;
- never normalize a hybrid into one surviving form just because CAS returned incomplete state.

---

## R003 — Sim gets stuck in one form

### Observed failure
A hybrid can become effectively locked into one visible form. Switching forms either does nothing, snaps back, or updates only part of the state.

### Required Apex behavior
Form switching must converge all relevant state:
- available occult types;
- current active form/type;
- pending transition state;
- linked occult/form SimInfo records;
- visible appearance;
- form availability flags/caches used by the current game build.

Apex must detect contradictions such as:
- current form not present in available forms;
- multiple “current” candidates;
- pending form never clearing;
- visible appearance not matching the selected stored form;
- a form link existing but being unreachable.

Never “fix” stuck state by deleting the other forms.

---

## R004 — Werewolf CAS items disappear, get stripped, or corrupt

### Observed failure
Werewolf-specific appearance content can be removed or corrupted during CAS/hybrid-form operations. This includes hair/headwear or other CAS parts disappearing when switching categories or outfits, and edits made while already in werewolf form failing to survive.

### Required Apex behavior
For every werewolf form operation:
- preserve the complete CAS-part set before mutation;
- understand mutually exclusive body-part/category semantics instead of treating absence as deletion;
- preserve werewolf-specific parts and custom content unless the user explicitly removes them;
- prevent human-form copy/paste from blindly stripping valid werewolf-only parts;
- prevent werewolf-form copy/paste from polluting the human form;
- preserve outfit-slot-specific data;
- verify category changes and outfit changes do not silently drop parts;
- treat a missing part after an operation as a regression unless the operation explicitly targeted that part/category.

### Required werewolf regression paths
Test at minimum:
1. enter CAS from human form -> switch/edit werewolf -> save -> Live;
2. enter CAS while already in werewolf form -> edit -> save -> Live;
3. change hair/headwear category -> switch outfit -> switch back;
4. switch werewolf -> human -> werewolf;
5. MCCC Modify in CAS -> return -> restore/commit;
6. save -> reload -> game restart.

---

## R005 — Wrong skin details, makeup, hair, tattoos, or other CAS data bleed between forms

### Observed failure
An occult form may unexpectedly inherit or lose visible appearance data: wrong skin detail, makeup, hair, tattoos, accessories, clothing/body parts, or other CAS categories.

### Required Apex behavior
Drift Guard must:
- compare the selected live form against the correct stored baseline/form record;
- identify exactly which categories drifted;
- distinguish intentional edits from stale/reverted data;
- show the diff before destructive repair;
- support repair of one category, one form, or explicit all;
- avoid high-frequency timer/tick scanning.

Detection should be event/user-triggered (“fire once”) around real risk points such as CAS return, MCCC restore, form switch, outfit/category switch, and explicit Scan.

---

## R006 — Old snapshot/cache overwrites a newer good edit

### Observed failure class
A recovery/cache path can become more dangerous than the original bug if stale state is treated as authoritative after the user has intentionally made a newer edit.

### Required Apex behavior
- Every recovery snapshot needs identity, source form, creation generation/time, and relevance checks.
- Newer intentional state wins over an old snapshot.
- CAS-session cache is never automatically treated as authoritative save state.
- Restore must preview what will change when state diverged.
- If freshness/order cannot be proven, preserve both states and ask for a narrow choice rather than overwriting.

---

## R007 — Form/category operations must not destroy unrelated content

A copy/paste/commit/repair action aimed at one category must not silently alter unrelated categories or occult gameplay state.

Protect:
- occult traits;
- powers/rank/progression;
- needs/commodity state;
- perks where applicable;
- linked form identity;
- outfits not selected by the operation;
- custom content;
- tattoos/skin details/accessories outside the selected scope.

“Looks right” is not enough if unrelated data changed.

---

## R008 — Human and occult forms must remain independently editable

The user must be able to intentionally make the human form and each occult form look different.

Apex must not:
- constantly mirror human -> occult;
- constantly mirror occult -> human;
- reapply an old baseline over a new intentional edit;
- assume one appearance should become the canonical appearance for every form.

Cross-form copy is an explicit user action with a preview.

---

## R009 — MC Command Center integration must be recoverable without private patching

The original pain point is the workflow, not just a specific API call.

Required sequence:
1. Arm MCCC Shield / snapshot relevant form state.
2. Enter Modify in CAS.
3. User edits normally.
4. Return to Live Mode.
5. Apex identifies what actually changed.
6. Restore only form links/state that CAS/MCCC incorrectly disturbed.
7. Commit the visible intended edit to the selected occult form.
8. Verify form switch + persistence.

If MCCC is missing or its behavior changes, Apex must degrade to a documented manual CAS recovery path rather than corrupting state.

---

## R010 — No silent “successful” repair

Every mutation/repair must end in verification.

At minimum verify:
- selected form exists;
- all expected secondary forms still exist;
- active/current form is coherent;
- intended CAS categories match the committed result;
- unrelated protected categories did not change;
- form switch away/back reproduces the intended look;
- save/reload preserves it.

If verification fails, keep the operation failed/partial and provide recovery. Do not show success because an API call returned without exception.

---

# Canonical regression matrix

Codex must build automated/fixture coverage where possible and real-game runtime coverage where Sims APIs/CAS behavior cannot be faithfully mocked.

For each supported occult and representative hybrids, cover:

| Scenario | Must prove |
|---|---|
| Human -> CAS -> edit -> save | edits persist, occult forms remain intact |
| Occult form -> CAS -> edit -> save | edits persist to that occult form |
| MCCC Modify in CAS | edits persist and secondary forms survive |
| CAS entry while already werewolf | edits persist; wolf parts survive |
| Form switch away/back | exact intended form restored |
| Outfit switch | no unrelated CAS-part loss |
| Category switch | no hair/headwear/body-part stripping |
| Copy one CAS category | only selected scope changes |
| Commit current -> selected occult | correct stored form changes |
| Drift detected after CAS | exact changed categories shown |
| Repair one category | unrelated categories/forms unchanged |
| Save/reload | state/appearance survives |
| Full restart | state/appearance survives |
| Household switch | state/appearance survives |
| Stale recovery snapshot | cannot overwrite newer intentional edit |

# Root-cause rule

Do not implement one-off patches for every symptom if they share a state-ownership problem.

Codex must trace the earliest authoritative owner across:
- SimInfo / OccultTracker state;
- current/pending occult type;
- occult-form availability;
- linked occult/form SimInfos;
- CAS-session caches;
- MCCC/CAS entry and exit;
- saved-form/baseline snapshots;
- appearance category serialization/copy logic.

Then fix the shared state model and keep these failures as permanent regressions.

# Release blocker

Apex is **not finished** while any of R001–R010 can still be reproduced on the current supported Sims 4 build.
