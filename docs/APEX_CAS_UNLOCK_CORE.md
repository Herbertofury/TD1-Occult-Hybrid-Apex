# Apex CAS Unlock Core — Always-Unlocked Categories, Hidden Items & Patch-Aware Hybrid CAS

Last reconciled: 2026-10-06
Current verified Sims 4 PC patch: 1.128.90.1030 (2026-09-22)

## Objective

Build an Apex-owned CAS unlock system that keeps intended CAS categories available for human and occult/hybrid forms, exposes compatible hidden/locked/debug/reward/occult items when the user wants them, survives normal form/outfit/CAS transitions, and has a repeatable update path when EA changes CAS resources.

The goal is to **start from the authorized current Crilender CASUnlocks implementation**, preserve its strongest working category-unlock behavior, then consolidate and improve it into Apex's own integrated unlock system. The project owner has stated they have full author permission to use Crilender's work, so Codex may inspect, reuse, port, merge and adapt the authorized package resources directly instead of recreating equivalent tuning solely for clean-room reasons.

## Zero third-party unlocker dependency invariant

The shipped Apex CAS Unlock Core must be **fully standalone**.

A normal user must not need to install:
- Crilender CASUnlocks;
- Loulicorn Ultimate CAS Items Unlocker;
- Szemoka Unlock CAS Items;
- another CAS unlock package;
- Lot51 Core;
- XML Injector;
- another script library;
- a separate package generator/parser/runtime just to make Apex unlocking work.

Those projects may be researched as challengers. They are never runtime requirements, fallbacks, or hidden prerequisites.

The only legitimate content prerequisites are The Sims 4 itself and the EA pack that owns a piece of content the user wants to use.

Open-source technical libraries may be used internally during development/build tooling only when licensing permits and when the finished Apex user experience remains self-contained. Prefer vendored/embedded narrow functionality or generated final artifacts over asking the user to install developer tooling separately.

If an optional third-party mod is present, Apex may diagnose overlap or coexist with it safely, but Apex functionality must be identical in capability when that third-party mod is absent.

## Required release artifact: ApexCASUnlocks.package

Apex CAS Unlock Core must ship with a real, first-party Sims 4 package:

`ApexCASUnlocks.package`

This is not optional and not merely a generated cache.

It is the canonical packaged CAS/tuning/resource layer for Apex and should be the user-facing equivalent of installing a traditional CAS unlocker, except integrated with the rest of Apex and held to a much stronger maintenance/verification standard.

The package should contain only Apex-owned or independently generated resources required for:
- CAS category availability/unlock tuning;
- occult/hybrid category expansion;
- supported hidden/locked/debug/occult catalog exposure where package overrides are the correct mechanism;
- Apex-owned STBL strings needed by packaged interactions/UI/tuning;
- any minimal tuning/injection resources required to connect packaged CAS behavior to the Apex script/runtime;
- package-level compatibility data needed by the current supported Sims 4 build.

The package must not contain copied third-party unlocker resources.

### Package identity and release discipline

Every release must record:
- package filename;
- semantic project version;
- supported Sims 4 build/fingerprint;
- generated/source manifest version;
- exact resource count by type;
- installed/current pack coverage;
- SHA-256;
- source-game resource hashes for every overridden/generated resource;
- reproducible build/generator command;
- validation report.

The package should be deterministic: identical input game data + identical Apex policy + identical toolchain must produce byte-identical output where the package format/tooling permits it, or a documented normalized-equivalent output otherwise.

### One package for the normal user

The normal installation target is one Apex CAS package, not a maze of per-pack/per-occult addon files.

Prefer:
- `ApexCASUnlocks.package`

over:
- `ApexCASUnlocks_Werewolf.package`
- `ApexCASUnlocks_Mermaid.package`
- dozens of pack-specific fragments.

If technical/package-format evidence proves internal splitting is safer or materially better, the release process may build internal modules but should still present one coherent install path and one ownership/manifest model. Do not recreate the third-party “install/delete the right addon files manually” burden.

## Current design decision

Use a three-layer architecture:

1. **ApexCASUnlocks.package**
   - the canonical packaged CAS/tuning/resource layer;
   - installs like a normal Sims 4 `.package`;
   - carries the current verified category/catalog overrides and Apex-owned package resources;
   - is generated/validated from Apex policy + current EA game data;
   - remains fully first-party and reproducible.

2. **Runtime Unlock Policy Engine**
   - keeps supported CAS categories available;
   - reapplies policy on real CAS lifecycle/form/outfit boundaries rather than polling;
   - understands the active hybrid form;
   - provides diagnostics and compatibility state;
   - remains useful even if a generated item catalog needs rebuilding after a patch.

3. **Patch-Aware Unlock Catalog Builder**
   - reads CAS resources from the user's/current clean game installation;
   - inventories installed packs and CASP resources;
   - applies Apex-owned unlock policy to compatible resources;
   - generates a minimal Apex unlock package/manifest for the exact game build;
   - does not depend on copying third-party unlocker packages;
   - can be rerun after EA patches and diffed against the prior generated manifest.

One subsystem owns the policy/model. `ApexCASUnlocks.package`, runtime UI, generator, diagnostics and CAS History must all consume the same policy data so package behavior and script-side behavior cannot drift.

---

# Clean-room reference rule

Crilender CASUnlocks is the primary authorized implementation baseline; other unlockers remain research/challenger inputs.

For Crilender material covered by the owner's author permission, direct reuse/port/adaptation is allowed. Do not copy:
- package resources from Loulicorn Ultimate CAS Items Unlocker;
- material from unrelated third parties not covered by the owner's permission;
- creator-specific identifiers or package structure unless independently required by the game format.

Required/allowed work:
- extract and inventory the authorized current Crilender package/addons;
- reuse/port/merge authorized resources where they remain the strongest route;
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

## Native Reward Unlock lane

When a CAS item belongs to the game's own reward/ownership unlock system, prefer using that durable game mechanism instead of forcing visibility through a CASP override.

Requirements:
- discover current reward-unlock resources from current game data where technically possible;
- allow targeted Sim/household unlock as well as an explicit all-supported-rewards action;
- journal the unlock as an ownership/state event;
- preserve normal save persistence;
- never re-grant/rewrite the reward every CAS frame/session;
- fall back to catalog visibility only when there is no safe native ownership path and the user explicitly enabled that catalog mode.

This follows the stronger architectural idea demonstrated by Szemoka's Unlock CAS Items without copying its implementation.

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
- `ApexCASUnlocks.package` as the canonical normal-user artifact;
- native reward-unlock discovery/manifest data for items that should use game ownership semantics instead of static visibility overrides;
- `apex_cas_unlock_manifest.json`;
- patch/build fingerprint;
- list of categories unlocked;
- list/count of items exposed;
- installed-pack coverage;
- unsupported/ambiguous resources;
- diff from prior manifest;
- deterministic SHA-256 manifest.

Generated package resources must change only the minimum fields/resources required by the unlock policy.

## Package/source synchronization invariant

For every resource inside `ApexCASUnlocks.package`, Codex must be able to answer:
- why this resource exists;
- which Apex policy rule owns it;
- which current-game source resource/tuning it derives from, if any;
- whether it is generated, authored, injected, or copied from an allowed first-party Apex source;
- which patch/build it was last verified against;
- which regression test covers it.

No opaque binary-only package edits are allowed. Sims 4 Studio may be used to inspect/debug/package during development, but the authoritative package must be rebuildable from source/policy data rather than existing only as hand-edited binary state.

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
- a compatibility mode if a third-party package is intentionally retained and coexistence is safe;
- explicit confirmation that Apex does not need that package and remains fully functional after it is removed.

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

Record adopt/adapt/reference/reject decisions and licensing consequences. Any adopted technical library must not become a separate end-user runtime/mod dependency for CAS unlocking.

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

# Better-than-current-unlockers acceptance

Apex should materially exceed the current standalone unlockers in the areas that matter:

- **Crilender-style category permanence**, but with patch fingerprinting, form awareness, diagnostics and one integrated package.
- **Loulicorn-style breadth**, but with installed-pack awareness, safety classification, one install path and no manual per-pack file management.
- **Szemoka-style native reward ownership**, used when that is the correct durable mechanism instead of forcing everything through static CASP visibility.
- **Apex-only hybrid integration**: form identity, CAS History, Drift Guard, MCCC recovery, post-CAS persistence and werewolf regression protection all share one canonical state/policy model.
- **Reproducible package generation** from current game resources instead of a package that must be manually rediscovered after every patch.

"Better" must be proven by behavior and maintenance/runtime evidence, not by feature-count marketing.

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
- no third-party CAS unlocker/script library is required at runtime;
- a clean Mods profile containing Apex but none of the researched unlockers/libraries passes the full unlock regression matrix;
- exact release `ApexCASUnlocks.package` is rebuilt from source/policy, hashed, structurally validated and current-game runtime-tested;
- CAS responsiveness is materially non-regressive.
