# Apex CAS Unlock Core

Apex will include its own **always-unlocked, patch-aware CAS system** with **zero dependency on another creator's unlocker**.

## Standalone means standalone

The user installs Apex. That's it for CAS unlocking.

Crilender, Loulicorn, Szemoka, Lot51 Core, XML Injector, or another unlock/script package are **not required** for Apex CAS Unlock Core. We learn from good ideas in other projects, then independently implement the strongest combined behavior ourselves.

If another unlocker is installed, Apex may report conflicts/overlap, but removing it must not reduce Apex's capabilities.

## What ours does

### Keep categories unlocked
Human and occult forms keep their intended CAS categories available through:
- CAS entry/re-entry;
- form switching;
- outfit switching;
- MCCC CAS;
- history restore/undo/redo;
- UI rebuilds.

Reassertion is event-driven, not a background polling loop.

### Unlock hidden/locked items
Optional catalog modes expose compatible:
- locked items;
- hidden/reward items;
- debug/NPC items;
- occult-restricted items.

A visible item is **not automatically considered safe to apply**. Age/species/frame/form compatibility stays explicit.

### Hybrid-aware
Human, Werewolf, Vampire, Mermaid, Fairy, Alien and other form identities remain separate. Unlocking more choices must never flatten or corrupt forms.

### Patch-aware
Apex records the exact Sims 4 build its generated unlock catalog came from. When EA patches CAS resources:
- old generated data is marked stale;
- current game resources are rescanned;
- changes are diffed;
- only the required minimal unlock resources are regenerated;
- runtime category policy can continue only when its current introspection remains valid.

### F11 Unlock Matrix
Show exactly:
- which categories are unlocked;
- which items are hidden/locked/debug/occult;
- why something is unavailable;
- pack ownership;
- current form compatibility;
- current patch verification state;
- third-party override conflicts.

## Best current mods we're learning from

- **Crilender CASUnlocks** — strongest category-unlock behavior reference.
- **Loulicorn Ultimate CAS Items Unlocker** — strongest broad hidden/locked/debug item-catalog reference.
- **Occult Hybrid Unlocker & Stabilizer** — hybrid state compatibility reference, not the catalog engine.
- **Werewolf Abilities in CAS** — useful modern example of expanding werewolf CAS capabilities.

Apex clean-room reimplements the behavior it needs from current game data; it does not copy proprietary packages.

Full engineering spec: [docs/APEX_CAS_UNLOCK_CORE.md](../docs/APEX_CAS_UNLOCK_CORE.md)

Research matrix: [docs/CAS_UNLOCKER_REFERENCE_MATRIX.md](../docs/CAS_UNLOCKER_REFERENCE_MATRIX.md)
