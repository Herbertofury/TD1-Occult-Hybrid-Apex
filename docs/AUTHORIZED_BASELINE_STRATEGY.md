# Authorized Baseline Strategy

## Owner authorization

The project owner explicitly states they have full permission from the relevant authors of all four development baselines:

- the current TD1/LordPercival Occult Hybrid package/script lineage;
- Crilender CASUnlocks; and
- MC Command Center (MCCC), including the relevant MC CAS / MC Dresser / shared CAS-related implementation material; and
- thepancake1 Color Sliders, including the relevant thepancake1-owned UI/package/conversion material covered by the author's permission.

For Apex development, Codex may inspect, extract, diff, reuse, port, adapt, merge, modify and incorporate material covered by that permission. Preserve attribution and source/version provenance. Do not assume this permission extends to unrelated third-party components bundled inside an archive.

## Mandatory starting point

Do not start either subsystem from blank code while ignoring the working packages.

### Hybrid

Start from the newest authorized working **Occult Hybrid Unlocker & Stabilizer 1.13.7 FIXE** package/script set.

Inventory the real package/script contents first, preserve useful working behavior, then improve upward into:

- `ApexOccultHybrid.package`
- `ApexOccultHybrid.ts4script`

Preserve/port strong working membership, transformation, form-switch, CAS, panel/orb, tuning and diagnostic behavior. Replace pieces when they are stale, defective, or materially weaker than the Apex architecture.

### MCCC CAS / Dresser

Start from the newest author-authorized **MC Command Center** package/source available to the project. The current verified public release is MCCC 2026.5.0 for Sims 4 PC 1.128.90.1030; if the author provides a newer authorized source/package baseline, use that newer verified build.

Inventory the real MC CAS, MC Dresser and shared CAS-related helpers first, including:
- body-part value/range logic;
- copy/paste appearance and face/body paths;
- outfit save/load/copy/randomize;
- included/excluded lists;
- custom definitions;
- Tray Sim paste/import paths;
- occult appearance persistence helpers;
- off-lot Sim selection and shared SimInfo/CAS helpers.

Preserve/port strong working behavior, then improve it into Apex Live CAS Studio so the final user can do CAS-grade editing from Live Mode/F11 without MCCC installed.

### thepancake1 Color Sliders

Start from the newest author-authorized **thepancake1 Color Sliders** package/tooling available to the project. The current public baseline is v4f, updated/checked through patch 1.127.41; Apex targets 1.128.90.1030 and must port it forward.

Inventory:
- slider-enable UI resources;
- eyebrow slider resources;
- classlibrarygamedata/cascustomizer changes;
- Hue / Saturation / Brightness / Opacity state;
- saved custom-color behavior;
- converted texture architecture;
- pack/category resource layout;
- conversion tooling;
- More CAS Columns compatibility;
- CC slider-ready behavior.

Preserve/port strong thepancake1-owned pieces and make ColorState a first-class Apex appearance field so exact custom colors survive every part/outfit/form/Sim copy. Final Apex color support must work with the original Color Sliders mod removed.

### CAS unlocker

Start from the newest authorized **Crilender CASUnlocks v1.9h** package plus relevant current addons.

Inventory its real resources/category coverage first, preserve/port strong working behavior, then improve and consolidate into:

- `ApexCASUnlocks.package`

Include its useful Werewolf/Mermaid/Fairy/Archetype/base-layer/category behavior before extending Apex with installed-pack awareness, hidden/locked/debug/reward catalog support, F11 diagnostics, hybrid awareness and patch-aware generation.

## Migration rule

Use this order:

1. acquire and hash exact baseline archives;
2. extract/inventory package resources and script modules;
3. map useful behavior to resource/module owners;
4. runtime-test the baseline on the current Sims 4 build;
5. add parity/regression tests;
6. reuse/port authorized working material when strongest;
7. improve or replace weak/stale pieces;
8. compare baseline vs Apex on identical workflows;
9. remove the old runtime dependency only after Apex proves parity + improvement;
10. finish with Apex-only clean-profile runtime proof.

The final install is standalone, but authorized baseline material from TD1/LordPercival, Crilender, MCCC and thepancake1 may legitimately survive inside the evolved Apex implementation with provenance.

Do not throw away good authorized code/resources merely to claim a rewrite.
