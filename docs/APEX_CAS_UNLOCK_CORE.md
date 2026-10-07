# Apex CAS Unlock Core — Always-Unlocked Categories, Hidden Items & Patch-Aware Hybrid CAS

Last reconciled: 2026-10-06
Current verified Sims 4 PC patch: 1.128.90.1030 (2026-09-22)

## Objective

Build an Apex-owned CAS unlock system that keeps intended CAS categories available for human and occult/hybrid forms, exposes compatible hidden/locked/debug/reward/occult items when the user wants them, survives normal form/outfit/CAS transitions, and has a repeatable update path when EA changes CAS resources.

The goal is not to copy another unlocker. The goal is to independently reproduce the best user-visible capabilities, fix their maintenance/compatibility gaps, and integrate them with Apex's hybrid form ownership, CAS History Studio, Drift Guard, MCCC Shield and Post-CAS Commit.

## Current design decision

Use a two-layer architecture:

1. **Runtime Unlock Policy Engine**
   - keeps supported CAS categories available;
   - reapplies policy on real CAS lifecycle/form/outfit boundaries rather than polling;
   - understands the active hybrid form;
   - provides diagnostics and compatibility state;
   - remains useful even if a generated item catalog needs rebuilding after a patch.

2. **Patch-Aware Unlock Catalog Builder**
   - reads CAS resources from the user's/current clean game installation;
   - inventories installed packs and CASP resources;
   - applies Apex-owned unlock policy to compatible resources;
   - generates a minimal Apex unlock package/manifest for the exact game build;
   - does not depend on copying third-party unlocker packages;
   - can be rerun after EA patches and diffed against the prior generated manifest.

One subsystem owns the policy/model. Runtime UI, generated package, diagnostics and CAS History must all consume the same policy data.

---

# Clean-room reference rule

Current third-party unlockers are research/challenger inputs only.

Do not copy:
- package resources from Crilender CASUnlocks;
- package resources from Loulicorn Ultimate CAS Items Unlocker;
- proprietary/all-rights-reserved code or assets;
- creator-specific identifiers or package structure unless independently required by the game format.

Allowed work:
- observe/document user-visible behavior;
- compare which categories/items become visible;
- independently discover the responsible current-game CAS/tuning/CASP fields;
- implement Apex-owned behavior from current EA/game data and open technical references.

Record provenance and candidate disposition in `docs/CAS_UNLOCKER_REFERENCE_MATRIX.md`.

---

# User-facing modes

## 1. Core Categories — default ON

Keep normal safe CAS categories available even when EA hides them for a form.

Examples include, where the current game supports the category:
- hair;
- hats/headwear;
- skin details;
- tattoos;
- makeup;
- face paint;
- accessories;
- fingernails;
- body hair;
- scars/details;
- clothing categories;
- shoes;
- gloves;
- occult-specific facial/body detail categories;
- base-layer categories introduced by newer patches;
- additional discoverable current-game CAS categories.

Do not hardcode the above as the complete forever-list. Build a category registry from current game data and layer explicit policy over it.

## 2. Occult Expanded — default ON for Apex hybrids

Make compatible non-occult categories usable for occult forms while preserving occult-only categories.

Required coverage:
- vampire / dark form;
- werewolf;
- mermaid;
- alien/disguise where applicable;
- fairy;
- spellcaster where form-specific behavior exists;
- ghost;
- PlantSim;
- Servo;
- future/current custom occult forms when their capabilities can be safely discovered.

The system must not flatten form identity or copy human appearance into an occult form just because a category becomes visible.

## 3. Hidden / Locked Catalog — default configurable

Expose compatible:
- normally locked CAS items;
- hidden/reward CAS items;
- debug/NPC CAS items;
- occult-restricted items;
- temporary/special-effect items only when the user explicitly enables the more permissive tier.

This is a catalog visibility feature, not permission to apply an incompatible resource.

## 4. Advanced Compatibility Bypass — default OFF

Age/species/frame/body-type restrictions that can produce broken meshes, invalid state or unsupported gameplay remain enforced by default.

If Apex later offers an advanced bypass:
- it must be explicit;
- item-level compatibility must be shown;
- warnings must explain the broken/unsupported risk;
- it must never be required for normal occult-expanded CAS.

---

# Form-aware Keep-Unlocked behavior

## Event-driven reassertion

Re-evaluate/reapply unlock policy only on meaningful boundaries such as:

- entering CAS;
- switching the edited Sim;
- switching human/occult form;
- switching outfit;
- CAS mode/category rebuild;
- returning from MCCC-driven CAS;
- a detected game UI rebuild that invalidates category availability.

No high-frequency CAS polling loop.

## “Stay unlocked” invariant

Once Apex reports a category as enabled for the current form, it must remain available through:

- category changes;
- outfit changes;
- human <-> occult form switches;
- MCCC Modify in CAS;
- named history restore;
- undo/redo/jump-to-state;
- CAS close/re-entry within the supported workflow;

unless the category genuinely becomes incompatible or the user disables the unlock mode.

If a category unexpectedly disappears:
- record an unlock-state event;
- explain which rule/resource changed;
- attempt one safe event-bound reassertion;
- verify visibility;
- if still unavailable, show a compatibility/error state instead of silently looping.

---

# Unlock policy data model

Maintain one versioned registry.

Each category/item rule should support:

- stable category/body-type/resource identity;
- display name;
- source: EA/current game / user CC / unknown;
- required pack(s);
- age constraints;
- gender/frame constraints;
- species constraints;
- occult/form compatibility;
- category visibility rule;
- item visibility rule;
- hidden/locked/debug/reward/occult tags or flags when known;
- whether applying the resource is known-safe, conditionally safe or unsupported;
- current patch first-seen / last-verified;
- override/injection owner;
- conflicts with other policy rules;
- provenance/evidence.

Do not infer “safe to apply” from “visible in CAS.”

---

# Patch-aware game scan and generator

## Inputs

Resolve the actual current Sims 4 installation and read only from it.

Scan:
- base-game CAS packages/resources;
- installed DLC CAS packages/resources;
- current patch/delta resources before older full-build resources when game precedence requires it;
- CASP resources;
- relevant CAS category/UI/tuning/SimData resources;
- pack metadata;
- game version/build identity.

## Outputs

Generate:
- `ApexCASUnlocks.package` or a small set of intentionally separated modules;
- `apex_cas_unlock_manifest.json`;
- patch/build fingerprint;
- list of categories unlocked;
- list/count of items exposed;
- installed-pack coverage;
- unsupported/ambiguous resources;
- diff from prior manifest;
- deterministic SHA-256 manifest.

Generated packages must change only the minimum fields/resources required by the unlock policy.

## Update behavior

On a new game build:
1. detect build mismatch;
2. keep safe runtime category policy available if its current introspection passes;
3. mark the generated catalog as `STALE / REBUILD REQUIRED`, not “broken” or “current” by guess;
4. rescan current game resources;
5. regenerate into staging;
6. compare old/new manifests;
7. run structural validators;
8. run targeted CAS smoke/regression tests;
9. promote the new generated package only after validation.

Do not blindly reuse old CASP overrides after a patch when the source resource changed.

---

# Installed-pack awareness

The user should never have to manually delete unlock files for packs they do not own.

Builder/runtime must:
- discover installed packs;
- generate/include only relevant pack-backed unlock data;
- never create dangling UI references to absent packs;
- show pack source on each unlocked item where resolvable;
- tolerate pack install/uninstall by invalidating/rebuilding only affected catalog segments.

---

# Werewolf requirements

Werewolf support is P0 because it intersects the user's real regressions.

Keep available, where supported:
- hair/headwear;
- skin details;
- tattoos;
- makeup/face paint when compatible;
- accessories;
- scars/details;
- body/coat/head-specific categories;
- archetype/face categories;
- base layers;
- other current werewolf-compatible general CAS categories.

Must specifically guard against:
- missing werewolf faces/category regression;
- parts being stripped because a category became temporarily unavailable;
- outfit/category switches causing valid wolf parts to disappear;
- unlocking a category causing human parts to overwrite wolf-only parts;
- CAS entered while already transformed losing edits.

Every werewolf unlock action integrates with CAS History so a category/resource visibility change is inspectable.

---

# Mermaid / Fairy / other occult requirements

At minimum:
- Mermaid fingernail/category parity where current game data supports it.
- Fairy categories and current Fairy-era CAS additions.
- Occult archetype categories where valid.
- New occult categories discovered by future patch scans become `unclassified` until policy is reviewed rather than silently ignored.

A new EA occult/pack should produce a clear “new CAS policy surface detected” report for maintainers.

---

# Hidden item catalog UX

In F11 CAS tools, add a searchable **Unlock Catalog** / **Unlock Matrix**.

Views:

## Categories
For each category show:
- Visible / Hidden / Unsupported;
- Why;
- current form;
- policy source;
- last verified patch;
- reassert/repair status.

## Items
For each unlockable resource show:
- resolved name;
- CASP/resource ID;
- pack;
- category/body type;
- normal game state: locked / hidden / debug / reward / occult-restricted / visible;
- compatibility with current Sim/form;
- Apex exposure state;
- warning if special/temporary/NPC/debug.

Filters:
- form;
- pack;
- category;
- source state;
- safe only;
- occult;
- hidden;
- locked;
- debug;
- reward;
- CC/game.

No fake toggles. Every visible action is wired to the canonical policy/generator/runtime state.

---

# Conflict / coexistence handling

Detect likely overlapping unlock mods and report them.

At minimum recognize the user may also have:
- Crilender CASUnlocks;
- Loulicorn Ultimate CAS Items Unlocker;
- other packages overriding the same CAS UI/category/CASP resources.

Do not delete third-party files.

Provide:
- overlapping TGI/resource report where available;
- likely override winner/order;
- recommendation to avoid redundant overlapping unlockers once Apex is proven;
- a compatibility mode if a third-party package is intentionally retained and coexistence is safe.

Apex should be able to explain “category X is being controlled by another override” rather than endlessly reasserting itself.

---

# CAS History integration

CAS History Studio should record unlock-related events such as:

- `Category unlocked: Werewolf Hair`
- `Category restored after CAS UI rebuild`
- `Hidden item catalog enabled`
- `Item rejected: incompatible age/species/frame`
- `Unlock manifest stale after game patch`

Visibility changes are history/diagnostic events; they must not be mistaken for appearance mutations.

If applying an unlocked item actually changes Sim appearance, that appearance mutation is journaled normally with exact form/category/resource provenance.

---

# Performance contract

- No whole-game resource scan during active CAS.
- Expensive CASP/game package scanning happens in builder/update tooling or bounded startup/preflight work, not every category click.
- Runtime category rules are compiled/indexed for O(1) or near-O(1) lookups.
- Installed-pack and CASP manifests are cached by exact game build/resource fingerprint.
- Reassertion is event-driven.
- No per-frame category enumeration.
- No duplicate snapshot/diff engine.
- Equivalent CAS interaction latency/frame time must remain materially non-regressive.

---

# Current technical challengers / reusable open tooling

Evaluate before reinventing low-level parsing:

- Sims 4 Toolkit `@s4tk/models` — MIT; package/resource models.
- Sims 4 Toolkit `@s4tk/extraction` — MIT; indexing/extraction from game files.
- LlamaLogic.Packages — MIT; modern read/write package library.
- PhuVinhAI/ModTS4 package-authoring flow — MIT; useful reference for reading patch delta before full build and deterministic package generation.
- CmarNYC TS4SimRipper / TS4CASTools — GPL-3.0; strong CASP structure/reference implementation, but do not copy/link GPL code into a differently licensed Apex binary without making an explicit compatible licensing decision.
- The Sims 4 Modders Reference — current game format/patch/appearance documentation.

Record adopt/adapt/reference/reject decisions and licensing consequences.

---

# Required validation

## Structural
- generated package parses cleanly;
- no duplicate conflicting output resources within Apex;
- every generated override has a source-current-game resource and manifest entry;
- pack references only point to installed/required packs;
- manifest hashes match package inputs/outputs.

## CAS runtime
Test at minimum:
- human;
- vampire + dark form;
- werewolf;
- mermaid;
- fairy;
- alien/disguise;
- representative multi-occult hybrid;
- CAS entered from human form;
- CAS entered while already transformed;
- outfit switch;
- form switch;
- category switch;
- MCCC CAS;
- CAS History undo/redo;
- save/reload/restart.

## Patch resilience
On a controlled changed fixture/current next patch:
- changed source CASP/tuning is detected;
- old generated override is marked stale;
- new resource/category appears in diff;
- regeneration produces deterministic output;
- old user policy survives;
- unsupported new surface remains visible to diagnostics instead of being silently omitted.

---

# Completion standard

Apex CAS Unlock Core is complete only when:

- intended categories stay available through the supported CAS/hybrid workflows;
- hidden/locked catalog behavior is form/pack/compatibility aware;
- werewolf category/part regressions remain fixed;
- hybrid form state is not flattened or corrupted;
- a new game build is detected and can be regenerated/audited without reverse-engineering the entire mod again;
- F11 can explain exactly why a category/item is or is not available;
- CAS History records unlock/reassert/application behavior;
- no third-party proprietary package/code was copied;
- exact release build is current-game runtime-tested;
- CAS responsiveness is materially non-regressive.
