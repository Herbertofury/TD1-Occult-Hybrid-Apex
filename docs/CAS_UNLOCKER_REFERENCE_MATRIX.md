# CAS Unlocker Reference Matrix — 2026-10-06

Current verified Sims 4 PC build for this research: **1.128.90.1030**, released 2026-09-22.

This document distinguishes **behavioral references** from **code/tooling references**. Third-party mod behavior may inspire independently implemented Apex features; proprietary package contents are not copied. **None of the unlocker projects in this matrix may become an Apex runtime dependency.**

## Current unlocker challengers

| Project | Current observed status | Best idea to learn from | Limits Apex should improve |
|---|---|---|---|
| Crilender — CASUnlocks | v1.9h; file uploaded 2026-05-31, listed for game 1.124.63 | Extremely small category-focused unlocker; keeps hidden CAS categories available; modular occult addons; Werewolf/Mermaid/Fairy/Archetypes support lineage; base-layer support | All Rights Reserved; current listing does not explicitly target 1.128.90; static override maintenance; separate addon model; Apex needs patch fingerprinting, hybrid diagnostics and generated current-game policy |
| Loulicorn — Ultimate CAS Items Unlocker | latest listed 2026-04-16 for game 1.122.218 | Broad hidden/locked/debug/occult item exposure; useful functional grouping of catalog states | All Rights Reserved; static pack-specific files; warns users to remove unowned-pack files and recommends CAS-only usage; Apex should auto-detect installed packs, keep validity rules explicit and support normal integrated runtime |
| Szemoka — Unlock CAS Items | updated 2026-02-13; reward unlock interaction path | Uses the game's reward-style unlock semantics via Sim/mailbox interactions and states it adds new resources rather than overriding game files | Focused on reward/unlock-state items rather than category visibility; content list is hand-maintained; current page still cites old game-version testing; Apex should dynamically discover reward resources and integrate the native-unlock path where possible |
| LordPercivalXII / TD1 / IcedCream — Occult Hybrid Unlocker & Stabilizer | 1.13.7 FIXE, 2026-05-16 | Hybrid-occult ownership/state compatibility and recovery expectations | Not primarily a CAS catalog/category unlocker; use as hybrid-state floor, not as the unlock implementation |
| Aravyn — Werewolf Abilities in CAS | updated 2026-08-21; supports 1.127.41-era builds | Modern proof that additional werewolf state can be exposed through CAS UI | Specialized werewolf abilities/rank/temperament UI, not a general category/item unlocker |

## Crilender CASUnlocks — behavior to independently reproduce/improve

Observed public behavior:
- removes restrictions on CAS categories so they remain available;
- notes that unlocked empty categories may be blank/gray;
- Werewolf addon unlocks non-occult categories such as skin details/tattoos;
- Mermaid addon unlocks fingernails;
- historical updates added eyelashes support;
- 2025 update added Fairy support and fixed missing Werewolf faces CAS menu item;
- 2026 v1.9h added base-layer support;
- ModTheSims currently lists addon packages for Werewolf, Mermaid, Fairy, Horse, Archetypes and Gloves-below-Tops.

Apex disposition: **behavioral reference only**. Reimplement from current game resources/policy.

Public project:
- https://www.curseforge.com/sims4/mods/casunlocks
- https://modthesims.info/d/639159/cas-unlocks-v1-1.html

## Loulicorn Ultimate CAS Items Unlocker — behavior to independently reproduce/improve

Observed public behavior:
- unlocks normally locked items;
- exposes hidden/reward-style items;
- exposes debug items;
- exposes occult-restricted items for broader use;
- has a Crystal jewelry group;
- package set is pack-specific;
- warns to remove files for packs the user does not own;
- recommends removing the mod outside CAS even though applied items remain on Sims.

Apex disposition: **behavioral/catalog taxonomy reference only**. Reimplement with installed-pack discovery, safe compatibility metadata and integrated hybrid-aware runtime.

Public project:
- https://www.curseforge.com/sims4/mods/ultimate-cas-items-unlocker

## Szemoka Unlock CAS Items — native reward-unlock pattern

Observed public behavior:
- adds an `Unlock CAS Items` interaction to Sims and mailboxes;
- can unlock for one Sim/household or all Sims through mailbox interaction;
- uses the game's own reward-style ownership/unlock behavior rather than exposing everything only through static CASP overrides;
- states that it adds new resources instead of overriding in-game resources;
- was updated 2026-02-13 with additional pack CAS items and uses Lot51 Core Library.

Apex disposition: **strong behavioral/architecture reference for reward unlocks**. Prefer native game unlock/ownership semantics when a resource belongs to the game's unlock system; do not mutate CASP visibility just to simulate an ownership reward if the game already provides a durable supported unlock path.

Public project:
- https://modthesims.info/d/672037

## Current game-version gap

EA's 2026-09-22 update is PC **1.128.90.1030**.

At this research checkpoint:
- Crilender's current CurseForge main file is listed for **1.124.63**.
- Loulicorn's current CurseForge main file is listed for **1.122.218**.

That does not by itself prove either mod fails on 1.128.90. It does prove Apex should not equate “latest uploaded unlocker” with “verified against the current game build.”

Apex must carry its own game-build fingerprint and test status.

## Open technical references

### The Sims 4 Modders Reference
Useful current reference for:
- CAS Part resource type `0x034AEECB`;
- appearance/category/body-type behavior;
- occult form `sim_info` ownership;
- patch history.

Important appearance lesson: editing the live/current Sim appearance does not automatically synchronize the corresponding occult-form `sim_info`; Apex already treats this as a core regression source.

- https://thesims4moddersreference.org/tutorials/modifying-sim-appearances/
- https://thesims4moddersreference.org/reference/file-types/
- https://thesims4moddersreference.org/reference/patches/112890/

### Sims 4 Toolkit
- `@s4tk/models`: MIT package/resource models.
- `@s4tk/extraction`: MIT game indexing/extraction.
- Candidate for an Apex builder if it covers the needed current CASP fields cleanly.

Repositories:
- https://github.com/sims4toolkit/models
- https://github.com/sims4toolkit/extraction

### LlamaLogic.Packages
MIT-licensed modern .NET package reader/writer. Strong candidate for deterministic generator/validator work.

- https://github.com/Llama-Logic/LlamaLogic

### PhuVinhAI/ModTS4
MIT-licensed modern mod workspace with a package-authoring path using LlamaLogic.Packages. Its documented generator reads patch delta before older full-build tuning, a useful precedence pattern for Apex's patch-aware builder.

- https://github.com/PhuVinhAI/ModTS4

### CmarNYC tools
- TS4SimRipper contains a mature CASP parser.
- TS4CASTools is a dedicated CAS tooling codebase.
- Both repositories are GPL-3.0 at this checkpoint.

Apex disposition: **reference first**. Do not paste/link GPL implementation into Apex unless the project deliberately accepts the resulting licensing obligations.

- https://github.com/CmarNYC-Tools/TS4SimRipper
- https://github.com/CmarNYC-Tools/TS4CASTools

## Standalone requirement

Apex must pass its complete CAS unlock runtime matrix with **none** of the researched unlockers installed. Their absence may not disable a feature or trigger a lesser fallback.

Open-source parser/package libraries are implementation candidates, not user-facing mod dependencies. If one is used in a builder, its required functionality must ship inside the Apex toolchain/output so the end user does not separately install it.

## Recommended implementation stack

1. Use current game data as authority.
2. Prefer MIT tooling for package extraction/writing if it meets requirements.
3. Independently map the CAS/category fields needed by Apex.
4. Build a versioned unlock policy + patch-aware generator.
5. Keep category reassertion event-driven at runtime.
6. Maintain a manifest/diff so new EA categories/items cannot silently disappear from coverage.
7. Use the F11 Unlock Matrix to expose policy and compatibility state.
