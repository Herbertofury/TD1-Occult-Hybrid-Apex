# Apex Live CAS Studio — Full CAS-Grade Editing Outside CAS

Last reconciled: 2026-10-06
Current public MCCC baseline verified for research: MC Command Center 2026.5.0, compatible with Sims 4 PC 1.128.90.1030.

## Objective

Make Apex a **better full CAS-control system than MCCC for appearance/CAS work**, with the core promise:

> If a Sim attribute can be safely inspected or changed through Create-a-Sim, Apex should expose an equivalent or better control from Live Mode/F11 without forcing the user to enter CAS.

The experience should feel like a professional live character editor: select a Sim, select the exact human/occult form and outfit, inspect every CAS-editable property, change it immediately, preview/diff it, undo it, copy it, save it as a preset, or apply it to another Sim.

This is appearance/CAS scope. Do not expand this feature into unrelated MCCC story progression, pregnancy, population, career or relationship automation unless separately accepted.

## Authorized MCCC implementation baseline

The project owner states they have **full permission from the MCCC author** to study/use the relevant MCCC material for Apex.

Use the newest authorized/current MCCC package/source available to the project as a concrete implementation baseline, especially:

- MC CAS;
- MC Dresser;
- relevant shared mc_cmd_center helpers used by those modules;
- Copy/Paste appearance paths;
- Paste Tray Sim paths;
- occult-aware appearance-copy fixes;
- outfit save/load/copy/randomize paths;
- body-part value/range logic;
- include/exclude/custom-definition logic;
- any current CAS persistence or SimInfo/form synchronization helpers.

Current public official documentation identifies MCCC 2026.5.0 as the public release for Sims 4 PC 1.128.90.1030. If the author provides a newer authorized package/source build, use the newest verified authorized baseline instead and record its identity.

Do not start this subsystem from blank code while ignoring the authorized working MCCC implementation.

Final Apex runtime must not require MCCC.

## Current MCCC behavior to preserve and exceed

Official MCCC documentation currently demonstrates useful CAS-side behavior including:

- MC CAS manipulation of Sim appearance/body parts from the Sim menu without entering CAS;
- exact body-part/range controls;
- Sim-level CAS-style edits such as name, voice, body appearance, fitness/fat;
- MC Dresser saved outfits;
- loading saved outfits;
- copying an outfit from one category to another on the same Sim;
- copying an outfit from one Sim to a different Sim;
- replacing/randomizing individual body types or full outfits;
- include/exclude item lists;
- custom definitions covering skin details, scars, tattoos, body hair and nails;
- Paste Tray Sim workflows;
- appearance/face copy-paste;
- occult-aware appearance copy/paste;
- 2026.4/2026.5 fixes for copied appearance/body-part values being lost when an occult Sim switches forms.

Apex must preserve these useful capabilities and then substantially improve their UX, safety, hybrid awareness, history, discoverability and completeness.

---

# Product promise: CAS Anywhere

## Live Mode first

Normal workflow:

```text
F11 -> Live CAS Studio -> select Sim -> select form -> select outfit
   -> edit/copy/paste/randomize/restore
   -> preview semantic diff
   -> apply through canonical Apex action queue
   -> verify
   -> CAS History event/checkpoint
```

No CAS loading screen should be required for an operation that can be safely represented and committed through current Sims runtime state.

If a game operation fundamentally requires the EA CAS service:
1. first try the supported non-UI CAS generation/manipulation service;
2. keep the operation transactional and history-aware;
3. open full CAS UI only as a final fallback when the game truly exposes no safe outside-CAS route;
4. explain the reason in the UI.

Do not use “MCCC did not support it” as a reason to omit a Live CAS capability.

---

# Canonical data model

Live CAS Studio must operate on the same canonical Apex appearance model used by:

- CAS History Studio;
- Saved Forms;
- Drift Guard;
- MCCC Shield compatibility;
- Post-CAS Commit;
- Apex CAS Unlock Core;
- Apex Occult Hybrid Core.

Model at minimum:

- target Sim identity;
- exact target human/occult/custom form identity;
- outfit category;
- outfit index;
- body/CAS part slots;
- CASP resource IDs;
- swatches/colors;
- canonical per-part ColorState including base swatch + full current slider state (Hue, Saturation, Brightness/Value, Opacity) and exact form/outfit/resource ownership;
- physique/fit/fat values;
- face/body morph/modifier values;
- skin tone;
- skin details;
- hair/headwear/facial hair;
- brows/eyes/teeth;
- makeup/face paint;
- scars;
- tattoos;
- body hair;
- accessories/jewelry/piercings;
- nails;
- clothing/body/full-body/top/bottom/shoes/socks/tights/gloves;
- occult-specific body/head/detail parts;
- voice parameters;
- walk style where current game exposes it through Sim appearance/CAS state;
- current-game CAS identity settings that are safely editable;
- CAS-selected traits/aspiration/preferences/likes-dislikes and other current CAS-managed metadata where the game provides a stable API/state path;
- compatibility constraints and provenance.

Do not hardcode the 2026 CAS surface as forever complete. Discover new CAS-editable fields/resources after patches and surface them as unclassified until policy support is reviewed.

---

# Live editor surfaces

## 1. Sim Overview

Show:
- portrait;
- Sim ID/name;
- age/species/frame;
- human/occult memberships;
- selected form;
- current outfit;
- current CAS History branch/checkpoint;
- pending edits;
- unlock compatibility warnings.

## 2. Identity / CAS metadata

Where current game state safely supports it, edit outside CAS:

- first/last name;
- pronouns / identity fields exposed by the current game;
- voice type/pitch;
- walk style;
- gender/frame/customization settings;
- CAS-managed attraction/orientation/preferences;
- likes/dislikes;
- aspiration;
- traits chosen through CAS;
- other newly discovered current CAS metadata.

These must use searchable pickers, not MCCC-style giant unfilterable lists.

For gameplay-sensitive traits/settings:
- validate pack/age/species/occult requirements;
- show conflicts;
- preview removals/replacements;
- verify persistence after save/reload.

## 3. Face / Body Studio

Expose numeric + visual editing for:

- body physique/fit/fat;
- body-part modifier values;
- facial/body morph/modifier values;
- available presets;
- skin tone;
- current-game body/face values discoverable through CAS state.

Provide:
- current numeric value;
- safe discovered range;
- reset;
- copy;
- paste;
- lock;
- favorite/preset;
- fine-step and coarse-step editing;
- before/after diff;
- live reversible preview.

Continuous edits should coalesce into useful history actions.

## 4. CAS Parts Studio

Browse/apply/remove compatible resources by category:

- hair;
- hats/headwear;
- facial hair;
- eyebrows;
- eyes;
- teeth;
- skin details;
- makeup;
- face paint;
- scars;
- tattoos;
- body hair;
- accessories;
- jewelry/piercings;
- nails;
- tops/bottoms/full body;
- shoes;
- socks/tights/gloves;
- occult details;
- all newly discovered compatible categories.

Integrate Apex CAS Unlock Core so locked/hidden/debug/occult items can be inspected with compatibility state.

Provide text search, pack filters, CC/game filters, category filters, favorites, recently used and current-form compatibility.

## 5. Outfit Studio

Outside CAS, allow:

- inspect every outfit category;
- inspect every outfit slot/index;
- create/duplicate/delete outfit slots where current game supports it;
- copy one outfit category -> another;
- copy one outfit slot -> another;
- copy one Sim's outfit -> another Sim;
- copy one Sim's full outfit category including alternate slots -> another Sim;
- copy all outfits from one Sim -> another Sim;
- save outfit preset;
- load outfit preset;
- rename/tag/favorite outfit presets;
- apply outfit to current form only or compatible selected forms;
- randomize whole outfit;
- randomize only selected body type/category;
- clear selected removable parts;
- replace selected part;
- swap individual parts between outfits;
- bulk apply one accessory/hair/makeup rule across chosen outfits;
- compare two outfits semantically before copying.

Copy operations must allow explicit source and destination:
`Sim -> form -> outfit category -> outfit index -> category/part scope`.

**Color-copy invariant:** when a copied part/category includes slider-compatible color state, copy its exact canonical ColorState by default. Outfit copy, all-outfits copy and cross-Sim copy must never silently collapse a custom color back to an EA swatch.

## 6. Whole-Sim Appearance Copy

Provide professional copy/paste modes:

- Face only;
- Body only;
- Face + Body;
- CAS parts only;
- current outfit only;
- selected outfit categories;
- all outfits;
- skin details only;
- makeup only;
- hair/head details only;
- tattoos/scars only;
- accessories only;
- selected CAS categories;
- current form only;
- selected forms;
- compatible all forms;
- **Appearance Clone**: all CAS-visible appearance without gameplay identity/state.

Source may be:
- another live Sim;
- another household Sim;
- off-lot Sim by Sim ID/search;
- current household;
- Saved Form;
- CAS History checkpoint;
- Tray Sim / saved household;
- saved Apex appearance preset.

Never conflate appearance cloning with cloning relationships, career, inventory, occult progression, genealogy or gameplay identity unless a separate explicit feature requests it.

Appearance Clone must include exact compatible ColorState for every included CAS part. Provide explicit modes for Part+Color, Part-only/preserve-destination-color, Color-only where compatible, and base-swatch-only.

## 7. Tray / Library Appearance Source

Beat MCCC Paste Tray Sim by making it searchable and previewable.

Support:
- browse saved Tray Sims/households;
- filter/search by Sim/household name;
- preview source appearance;
- choose exact source Sim from household;
- choose Face / Body / outfit / full CAS appearance;
- choose destination form/outfit;
- show compatibility diff;
- apply as a journaled transaction;
- preserve target gameplay identity.

If Tray internals require CAS service calls, use the narrowest non-UI service route first.

## 8. Presets / Libraries

Save reusable:

- full appearance;
- face;
- body;
- morph set;
- individual category;
- makeup set;
- skin-detail set;
- tattoo/scar set;
- outfit;
- all outfits;
- form;
- hybrid form mapping.

Presets should be searchable, tagged, previewable, versioned and content-addressed.

Missing CC/pack resources on restore:
- report exact missing items;
- apply compatible remainder only after explicit policy/preview;
- never silently substitute random parts.

## 9. Color Studio

Integrate `docs/APEX_COLOR_STUDIO.md`.

Outside CAS expose:
- Hue;
- Saturation;
- Brightness/Value;
- Opacity;
- base swatch;
- exact numeric state;
- copy/paste color;
- saved colors/palettes;
- reset;
- recent/favorite colors;
- current part/form/outfit ColorState inspector.

Apex uses the authorized thepancake1 Color Sliders implementation as the baseline but must provide full color controls with that mod absent.

Color state must participate in every relevant copy, preset, Tray, Saved Form and history operation.

## 10. Include / Exclude / Lock Rules

Absorb and improve MC Dresser-style control.

Support:
- allowed/preferred item lists;
- excluded item lists;
- category-specific rules;
- age/species/frame/form rules;
- outfit-category rules;
- saved-only outfit pools;
- protected/locked categories;
- “never randomize this” rules;
- custom definitions for skin details/scars/tattoos/body hair/nails and current discovered body types.

Rules must be editable through F11 UI rather than requiring config-file syntax.

## 11. Randomize / Generate

Provide safe randomization:

- entire appearance;
- face only;
- body only;
- outfit only;
- selected category/body type;
- selected compatible pool;
- saved/include list only;
- preserve locked categories;
- preserve occult-only protected parts;
- deterministic seed option for reproduction;
- optional color randomization scope: preserve exact colors by default, or explicitly randomize base swatch/full ColorState/selected palette.

Every randomize action is undoable and previewable.

---

# Hybrid / occult awareness

This feature must be materially better than MCCC for occult/hybrid Sims.

Every action must target an explicit form lane.

Examples:
- copy Human Everyday 1 -> Werewolf Everyday 1 only when categories are compatible;
- copy face/body to Human + Vampire Dark Form by explicit choice;
- keep Werewolf-only body/head parts untouched when copying clothing;
- copy makeup without touching occult skin details;
- copy an outfit from another Sim without overwriting target morphs;
- copy full appearance while preserving independent occult form state unless user explicitly chooses linked application.

Use the Apex hybrid state model to update persistent linked form SimInfos correctly.

The MCCC 2026.4/2026.5 occult copy/body-part persistence fixes are a required baseline regression case, not the endpoint.

---

# Photoshop-style history and transactions

Every Live CAS Studio mutation is a CAS History transaction.

Before apply:
- show source;
- destination;
- exact form/outfit;
- semantic categories;
- compatibility warnings;
- expected additions/removals/replacements.

After apply:
- verify target state;
- verify protected state unchanged;
- record event;
- allow Undo/Redo;
- allow jump/branch;
- allow save as preset/checkpoint.

Bulk actions should be one parent transaction with inspectable child diffs.

---

# Bulk / multi-Sim workflows

Allow explicit multi-target operations where safe:

- copy one outfit to selected Sims;
- copy makeup/accessory rule to selected Sims;
- apply saved outfit/preset to selected Sims;
- clear a selected unwanted part from selected Sims;
- apply inclusion/exclusion/lock rule;
- normalize one selected category;
- export appearance diagnostics.

Always preview target count and incompatibilities before mutation.

No world-wide automatic appearance rewriting by default.

---

# MCCC-authorized baseline study

## Required current baseline

Start from the current author-authorized MCCC CAS-related implementation, at minimum matching public MCCC 2026.5.0 behavior unless a newer authorized build/source is available.

Inventory:

### MC CAS
- body-part values;
- body-part min/max/ranges;
- copy/paste appearance;
- copy/paste face/body;
- occult appearance handling;
- Sim-specific CAS attributes;
- current Tray paste paths;
- persistence helpers;
- form synchronization.

### MC Dresser
- outfit save/load;
- outfit copy across categories;
- outfit copy between Sims;
- whole/part randomization;
- included/excluded lists;
- custom definitions;
- removable-part handling;
- outfit-category mappings;
- body-type mappings;
- cleaning/replacement logic that is useful interactively.

### Shared helpers
- Sim lookup/off-lot selection;
- CAS/SimInfo manipulation helpers;
- current occult-form synchronization;
- persistence/save helpers;
- current-game compatibility shims.

Owner permission allows direct inspect/reuse/port/adaptation of the authorized MCCC material. Preserve attribution/provenance. Separately owned dependencies inside the archive retain their own terms.

---

# Standalone release rule

MCCC is a development baseline, not a final dependency.

Apex must pass Live CAS Studio acceptance on a clean profile with:
- no MCCC;
- no MC CAS;
- no MC Dresser;
- no third-party CAS controller;
- only Apex + required EA packs.

If MCCC is installed, Apex may detect/coexist or warn about overlapping appearance mutations, but removing MCCC may not reduce Apex Live CAS capabilities.

---

# Performance

Live CAS must feel immediate.

Requirements:
- no whole-Sim full serialization for every slider tick;
- coalesce continuous edits;
- cache indexed CAS resource metadata by game build;
- virtualize large item lists;
- searchable indexes off the render thread;
- lazy thumbnails/previews;
- no per-frame full wardrobe scans;
- bounded background preview generation;
- cancel stale searches/previews;
- batch multi-Sim changes;
- preserve complete semantic history.

Benchmark:
- F11 open;
- Sim select;
- category open;
- search;
- individual part apply;
- slider drag;
- full outfit copy;
- all-outfits copy;
- whole-Sim appearance copy;
- Tray appearance apply;
- undo/redo.

No speed gain may come from dropping compatibility checks/history/verification.

---

# Required runtime matrix

Test current supported Sims 4 build across:

- ordinary human Sim;
- Vampire + Dark Form;
- Werewolf;
- Mermaid;
- Fairy;
- Alien/disguise;
- Spellcaster;
- representative hybrid;
- off-lot source Sim;
- Tray Sim source;
- CC-heavy Sim;
- missing-CC preset;
- multiple outfit slots;
- save/reload/restart.

Required workflows:

1. change one body-part value outside CAS;
2. change full face/body outside CAS;
3. change skin details/makeup/hair/tattoo/accessory outside CAS;
4. copy an outfit category within one Sim;
5. copy outfit Sim A -> Sim B;
6. copy all outfits Sim A -> Sim B;
7. save/load outfit preset;
8. copy face/body Sim A -> occult Sim B;
9. copy selected appearance categories across forms;
10. paste a Tray Sim appearance while preserving target gameplay identity;
11. randomize one category with locks;
12. undo/redo every above class;
13. form switch away/back;
14. save/reload/restart;
15. confirm source and unrelated target state unchanged.

---

# Completion standard

Apex Live CAS Studio is complete only when:

- the major CAS-editable surfaces can be controlled from Live Mode without opening CAS;
- current MCCC MC CAS + MC Dresser appearance capabilities are matched or exceeded;
- whole-outfit and whole-appearance copy between Sims is safe, form-aware and reversible;
- Tray/preset sources are searchable/previewable;
- all mutations use the shared CAS History transaction model;
- occult/hybrid persistence exceeds the MCCC baseline;
- current package/source baseline material is properly attributed/provenanced;
- MCCC is not required in the final install;
- exact Apex release artifacts pass clean-profile current-game runtime proof;
- performance remains materially non-regressive.
