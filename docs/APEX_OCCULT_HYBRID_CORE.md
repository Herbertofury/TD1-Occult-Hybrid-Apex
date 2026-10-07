# Apex Occult Hybrid Core — Standalone First-Party Hybrid Engine

Last reconciled: 2026-10-06

## Objective

Ship a fully first-party Apex occult-hybrid engine that requires **none** of the TD1 / TwelfthDoctor1 / IcedCream / LordPercivalXII hybrid packages or scripts at runtime.

Apex must independently provide the useful behavior of current hybrid solutions, preserve compatibility with normal Sims 4 occult gameplay, fix the historical corruption/persistence failures documented in this repository, and integrate the entire feature set with Apex CAS Unlock Core, CAS History Studio, Drift Guard, Saved Forms, MCCC Shield and the F11 control center.

The historical TD1/IcedCream/LordPercival lineage is a behavioral/reference baseline only. It is not a runtime dependency or a release component.

---

# Required release artifacts

The canonical normal-user hybrid artifacts are:

- `ApexOccultHybrid.package`
- `ApexOccultHybrid.ts4script`

They must be Apex-owned and built from Apex source/policy plus current Sims 4 game/tuning data.

The normal release must **not** require:

- `[TD1-IC] OccultHybrid.package`;
- `[TwelfthDoctor1] OccultTurnActionsUnlocker.package`;
- `TwelfthDoctor1_OccultHybridHandler.ts4script`;
- TD1 Teleport Memory System;
- IcedCream hybrid packages;
- LordPercivalXII hybrid packages;
- another hybrid stabilizer;
- Lot51 Core;
- XML Injector;
- MCCC;
- another script library.

MCCC/Lot51 or similar mods may remain optional interoperability targets, but Apex's core hybrid behavior must be complete without them.

## Historical recovered artifacts

Recovered upstream/legacy files may remain in research fixtures/manifests for comparison and regression reproduction, but they are excluded from the production release unless a future explicit licensing/provenance decision says otherwise.

A clean-profile test with only Apex + the relevant official EA packs is mandatory.

---

# Behavioral compatibility floor

Apex must independently cover and improve the user-visible capabilities established by current hybrid mods.

## Hybrid occult coexistence

A Sim may legitimately hold multiple supported occult identities at once.

The engine must model separately:

- occult membership;
- active/visible form;
- linked form SimInfo/state;
- selected gameplay panel/secondary occult;
- occult-specific motive/perk presentation;
- pending transformation;
- temporary occult/status effects;
- CAS/recovery snapshots.

Never collapse these into one overloaded flag.

## Normal gameplay transformations remain usable

Where the official game normally lets a Sim become an occult, Apex must allow that transformation for a compatible hybrid without the stock single-occult test blocking it.

Examples include current-game equivalents of:

- Rite of Ascension / becoming a Spellcaster;
- Mermaidic Kelp / Mermaid conversion;
- Vampire conversion;
- Werewolf conversion;
- Alien/occult transformation paths where applicable;
- Fairy/current occult conversion paths;
- future EA occult transformation paths discovered by the patch scanner.

Do not globally delete tests from unrelated interactions. Generate the narrowest Apex-owned tuning/injection needed for the current supported game build.

## Add / remove occult controls

F11 and supported game interactions must provide explicit:

- Add Occult;
- Remove Occult;
- Switch Active Form;
- Select Gameplay/Perk Panel occult;
- Repair/Diagnose occult state.

Removing one occult must not remove or rewrite another occult's form, CAS data, progression, perks or motives.

## Stable form switching

Do not blindly rely on the historical "always force human first" workaround as the architecture.

Implement an explicit transformation state machine:

`current state -> validate target -> safe intermediate only if required -> transform -> verify target -> reconcile UI/motives -> journal result`

Use a human/base intermediate only when the current game requires it for a specific transition.

Detect and recover:

- stuck pending transformation;
- current form not present in available forms;
- transition snap-back;
- partially updated visible form;
- target form SimInfo missing;
- multiple conflicting current-form indicators.

## Gameplay UI / Motive Panel switching

A hybrid must be able to select which supported occult gameplay panel is active without deleting other occult identities.

Where the current game exposes them, support:

- occult perk/power panel;
- occult-specific motives/resources;
- Spellcaster charge/orb presentation;
- Werewolf Fury/orb presentation;
- Vampire power/needs UI;
- Mermaid/other occult-specific UI where applicable;
- Fairy/current occult gameplay panel behavior;
- future supported occult panel types discovered after patches.

The selected panel is presentation/gameplay focus, not the sole canonical occult identity.

---

# Own package/tuning layer

## ApexOccultHybrid.package

The package should contain only the minimal Apex-owned/generated resources required for the standalone hybrid system, such as:

- transformation-test/tuning adjustments;
- interactions for Apex Add/Remove/Switch/Diagnose where package tuning is appropriate;
- trait/tuning injections;
- motive/panel selection support;
- occult-form transition support;
- STBL strings;
- pack-specific injections generated only for installed/supported packs;
- current-build compatibility resources.

Every resource must have:

- Apex policy owner;
- source/current-game resource identity when derived;
- first/last verified Sims 4 build;
- reason for existence;
- SHA/source hash;
- regression coverage.

No opaque hand-edited-only binary state.

## ApexOccultHybrid.ts4script

Own the runtime domain logic:

- canonical hybrid state model;
- transformation state machine;
- Add/Remove/Switch actions;
- CAS entry/exit reconciliation;
- selected gameplay panel state;
- cache/state diagnostics;
- save/reload verification;
- event-driven Drift/CAS integration;
- F11/browser/console domain API.

The script must not import TD1/IcedCream/LordPercival modules.

---

# Patch-aware generation

Use the same current-game-authority philosophy as Apex CAS Unlock Core.

On each supported Sims 4 build:

1. resolve exact game build and installed packs;
2. discover relevant occult traits/tuning/interactions/forms/UI resources;
3. diff against the last verified manifest;
4. identify new/changed occult surfaces;
5. generate/stage `ApexOccultHybrid.package`;
6. run structural/tuning validation;
7. run targeted hybrid runtime tests;
8. promote only the verified package.

If a patch changes an occult path:

- mark affected Apex rule/resources stale;
- preserve unrelated verified occult support;
- report the new/changed surface clearly;
- do not pretend an old override is current.

A newly introduced EA occult must appear as `unclassified / support review required` rather than silently being treated as human or deleted.

---

# CAS and form preservation

Apex's own hybrid engine must solve the historical CAS failure class rather than depending on an upstream cache-remove-readd implementation.

Before CAS:

- inventory all known occult memberships/forms;
- identify the exact edited form;
- checkpoint links/identity + minimal required appearance state;
- begin CAS Change Journal session.

After CAS:

- detect what actually changed;
- verify every pre-existing occult/form still exists;
- reconcile only damaged links/state;
- commit intended appearance to the correct form;
- preserve independent human/occult appearances;
- verify form switch away/back;
- save/reload proof where the workflow touches persistent state.

Never remove every occult as the default CAS strategy merely because historical mods did so.

---

# Occult-specific progression safety

For every supported occult, preserve unrelated gameplay state through hybrid/form operations.

Protect where applicable:

- rank;
- powers/perks;
- weaknesses;
- abilities;
- points/currency;
- motives/commodities;
- Fury/charge state;
- spell knowledge;
- vampire progression;
- werewolf temperament/progression;
- mermaid/fairy/alien-specific persistent state;
- occult aspirations/traits;
- pack-specific custom state discovered in current game data.

Add/remove/switch form actions may touch only the state explicitly owned by the operation.

---

# Temporary / pseudo-occult handling

PlantSim, Ghost, Servo and other special states do not necessarily behave like full linked-form occults.

Represent capability/state explicitly rather than forcing every type through one linked-form implementation.

The canonical model should support capability flags such as:

- persistent occult membership;
- linked secondary form;
- gameplay panel;
- transformation interaction;
- CAS form;
- temporary status;
- mechanical species/state.

This allows future occults and custom states to be supported without corrupting assumptions.

---

# Better-than-current-hybrid acceptance

Apex must exceed current hybrid mods in measurable behavior, not just branding.

Required improvements:

- no dependency on another hybrid mod;
- explicit canonical state ownership rather than opaque caches;
- form-switch verification and stuck-transition recovery;
- CAS History and precise post-CAS commit;
- stale-snapshot protection;
- independent human/occult form editing;
- werewolf CAS-part protection;
- patch-aware package generation;
- installed-pack awareness;
- F11 diagnostics for membership/form/pending/panel/cache state;
- per-occult Add/Remove/Switch with narrow mutation previews;
- save/reload/restart proof;
- no continuous background polling;
- clean-profile operation without MCCC/Lot51/XML Injector;
- current-build manifests/hashes and reproducible package/source builds.

---

# Interoperability

Apex may detect and cooperate with:

- MCCC;
- Lot51 Core;
- CAS unlockers;
- other occult mods;
- custom occult mods.

But interoperability is additive.

When absent, Apex core functionality remains intact.

When an overlapping hybrid mod is installed:

- detect likely overlapping package/script owners;
- report conflicts;
- do not delete third-party files;
- refuse ambiguous double-ownership paths when safety cannot be proven;
- recommend removing redundant hybrid stabilizers once Apex is verified.

---

# Required clean-profile validation

Test a Mods profile containing:

- Apex release artifacts;
- no TD1/IcedCream/LordPercival hybrid files;
- no other hybrid stabilizer;
- no MCCC;
- no Lot51 Core;
- no XML Injector;
- only the official EA packs required for each tested occult.

Prove:

1. adding supported multiple occults works;
2. official transformation paths work for already-occult Sims where compatible;
3. switching forms works repeatedly;
4. selected gameplay/perk panel changes correctly;
5. Spellcaster/Werewolf orb/motive presentation follows the selected supported panel;
6. CAS editing preserves all occult memberships/forms;
7. CAS while already transformed persists edits;
8. human and occult forms stay independently editable;
9. secondary forms survive save/reload/restart;
10. removing one occult preserves the others;
11. rank/perks/progression remain intact through unrelated operations;
12. R001-R010 remain closed;
13. Apex CAS Unlock Core works with the hybrid engine;
14. CAS History logs transformations/state changes coherently;
15. the exact hashed `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script` pair is what was tested.

---

# Completion standard

Do not call Apex Occult Hybrid Core complete until the production artifacts are:

- standalone;
- source/policy reproducible;
- structurally validated;
- current-build runtime tested;
- clean-profile proven;
- behaviorally at least equivalent to the verified useful capabilities of current hybrid mods;
- measurably safer/more observable in the historical failure paths;
- integrated with CAS Unlock Core, CAS History, Drift Guard, Saved Forms and F11;
- free of required TD1/IcedCream/LordPercival runtime files.
