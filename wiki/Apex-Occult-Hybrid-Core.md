# Apex Occult Hybrid Core

Apex is becoming its **own complete occult-hybrid mod**, not a layer that requires TD1/IcedCream/LordPercival's hybrid files underneath it.

## Our release

The normal hybrid engine ships as:

- `ApexOccultHybrid.package`
- `ApexOccultHybrid.ts4script`

Alongside our own:

- `ApexCASUnlocks.package`

No TD1/IcedCream/LordPercival hybrid package or script is required.

## What our hybrid core must do

- Allow compatible Sims to hold multiple supported occults.
- Keep normal gameplay transformation paths usable for hybrids.
- Add/remove individual occults safely.
- Switch forms without getting stuck or destroying secondary forms.
- Switch the active occult gameplay/perk/motive panel.
- Handle Spellcaster charge and Werewolf Fury/orb presentation correctly.
- Preserve occult powers, ranks, perks, motives and progression.
- Preserve all forms through CAS/MCCC workflows.
- Keep human and occult appearances independently editable.
- Survive save/reload/restart.
- Explain all state in F11 instead of relying on hidden caches.
- Detect and recover broken/stuck state.
- Rebuild its own package against current game resources after EA patches.

## Historical mods are references only

TD1, IcedCream and LordPercival's releases remain useful behavioral/regression references. Apex does not need them installed and does not ship their files as dependencies.

The clean-profile acceptance test removes all of them and proves Apex still provides the complete hybrid feature set.

Full engineering spec: [docs/APEX_OCCULT_HYBRID_CORE.md](../docs/APEX_OCCULT_HYBRID_CORE.md)
