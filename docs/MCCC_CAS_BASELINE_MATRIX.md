# MCCC CAS/Dresser Authorized Baseline Matrix — 2026-10-06

## Authorization

The project owner states they have full permission from the MCCC author to use the relevant MCCC material in Apex.

For CAS-related Apex work, MCCC is an **authorized implementation baseline**, not merely a behavioral reference.

Use the newest author-authorized MCCC source/package available to the project. The current official public release verified on 2026-10-06 is **MC Command Center 2026.5.0**, documented as compatible with Sims 4 PC 1.128.90.1030.

Official documentation:
- https://deaderpool-mccc.com/downloads.html
- https://deaderpool-mccc.com/mccas.html
- https://deaderpool-mccc.com/mcdresser.html
- https://deaderpool-mccc.com/documentation.html
- https://deaderpool-mccc.com/changelogs/mccc2026_4_0.html
- https://deaderpool-mccc.com/changelogs/mccc2026_5_0.html

## MC CAS baseline

Official documentation identifies MC CAS as providing appearance manipulation outside normal CAS, including body-part controls and Sim-specific CAS-style settings.

Study/port where strongest:
- body part value editing;
- min/max/range templates;
- appearance copy/paste;
- face/body copy/paste;
- current Sim attributes exposed by MC CAS;
- occult persistence behavior;
- Tray appearance import paths;
- current-game compatibility helpers.

## MC Dresser baseline

Official documentation exposes:
- saved outfits;
- loading saved outfits;
- copying an Athletic outfit to Everyday on the same Sim;
- copying an outfit from one Sim to another;
- randomizing a full outfit or individual body type;
- included/excluded lists;
- custom definitions for skin details, scars, tattoos, body hair, fingernails/toenails;
- outfit-category mappings;
- detailed body-type mappings;
- removable-part behavior.

Apex must make these capabilities easier to discover and operate through F11.

## Relevant recent occult fixes

MCCC 2026.4 documented fixes for:
- pasted Sim appearance/face being lost after an occult Sim switched to occult form and back;
- MC CAS body-part values being lost after occult form switching;
- applying copied face/body appearance to occult appearance.

MCCC 2026.5 documented another fix to MC CAS Set Body Part behavior for occult Sims.

These are direct regression baselines for Apex. Apex must match these fixes and then exceed them through explicit form targeting, state ownership, CAS History and save/reload verification.

## Apex improvements over the MCCC CAS model

- one visual F11 Live CAS Studio instead of scattered menus/console syntax;
- searchable Sim/source/Tray/preset selection;
- semantic previews and diffs;
- Photoshop-style history;
- undo/redo/branching;
- exact human/occult form lanes;
- whole-Sim appearance clone modes;
- all-outfit copy;
- selected-category copy;
- bulk multi-Sim operations;
- integrated CAS unlock catalog;
- integrated saved forms/presets;
- explicit missing-CC handling;
- patch-aware CAS metadata;
- live verification and persistence proof;
- no MCCC runtime dependency.

## Scope boundary

Study MCCC broadly enough to discover reusable CAS-related helpers, but this Apex feature does **not** attempt to clone unrelated MCCC story progression, population, pregnancy, career, clubs, GEDCOM or world automation.

If a non-CAS MCCC helper materially enables CAS functionality, it may be ported/adapted with provenance.
