[← Apex](Home) · [CAS search](CAS-and-Content-Search) · [How it works](How-Apex-Works)

# ◇ Dynamic CAS Companion merge notebook
### Keep the better implementation. Bring the missing conveniences across.

The owner supplied `maru_Dynamic_CAS_Companion.package`. Its SHA-256 is `12cd97eedb4283330e89c898518bc21ff7542c938e1b0c63564d13d04d2b2d86`. The read-only audit found **25 resources**, including three GFX resources. Exported scripts were inspected locally; the donor package was not installed into the test profile.

The following assessment comes from that package inspection. The [author's feature page](https://www.curseforge.com/sims4/mods/dynamic-cas-columns) provides the public baseline. Credit: **maru**, [Creative Commons Attribution 4.0](https://www.curseforge.com/sims4/mods/dynamic-cas-columns/license). Apex's comparison and modifications do not imply the author's endorsement.

## What to retain, extend or port

| Feature found in the donor | Apex decision | Qualification still needed |
|---|---|---|
| Edge-drag column resizing, reset shortcut | Compare against Apex's existing column slider; add the direct drag affordance if it remains cheap | Same viewport, UI scale and category; cold/warm timings |
| Thumbnail scaling and automatic rearrangement | Keep Apex's independent card-size and horizontal/vertical gap controls; compare reflow cost | Recycled cells, partial last row, screen edges |
| Resizing body, face, generic, featured-look and skin panels | Bring across missing panel coverage; current Apex custom fitting primarily targets clothing | Each actual panel, all supported forms |
| Right-click favorites, favorite-only view and random choice | Integrate with stable resource/family identities and exact form ownership | Saved preferences and eligibility after patch/content changes |
| Hidden-item mode and hidden-only view | Add reversible hiding without deleting or disabling packages | No interference with favorites, equipped items or search |
| Recently selected-item history | Preserve as a browsing convenience alongside complete Apex appearance history | No confusion between “recent item” and reversible edit |
| Dedicated swatch preview and compact hair colors | Compare native swatch handling; retain exact child variant and custom modifiers | Hair/brows, matching flags, color sliders, alternate forms |
| Current outfit by category, individual/category removal | Integrate with Apex's native equipped category and optional text inventory | Layers, nonremovable defaults, undo, inactive forms |
| Named saved outfits, selective application and fashion filtering | Port with explicit appearance/outfit scope; never overwrite gameplay or unrelated forms | Clothing/makeup/hair subsets and missing CC |
| Eye preview/favorites and compatible color editing | Extend Apex color browsing using verified eye resources | Compatible textures; no claim every material can be recolored |
| Background presets, sliders, saved colors and wheel | Port the useful controls; investigate alpha rendering before default enablement | Transparent Alpha CC must remain visible |
| CAS animation pause/play and shortcut | Add focus-aware playback controls, separate from Live autonomy | Typing, dialogs, form animations and leaving CAS |
| Expanded skin brightness and numeric input | Port precise controls only with actual native supported ranges and persistence | Boundaries, exact readback, CAS return and reload |
| Persisted columns, scale and panel layout | Keep compatible Apex preferences and offer explicit migration | Reset, resolution/UI-scale changes and old settings |

## Why this is a merge rather than another installed override

The donor changes the CAS Customizer and shared UI library resources that Apex also depends on. Loading both wholesale would leave resource order to choose a winner. It would not combine independent appearance handling, column work and the donor's drawers.

Apex's build process grafts inspected changes into the exact installed UI and checks that unrelated methods remain intact. Useful donor behavior should enter through that process, with narrow additions and explicit native service contracts. Raw shared-library replacement is not evidence of a correct integration.

The donor's resize method is guarded by a changed column count and updates multiple panel types. Apex already avoids repeated clothing reflow and retains a fitted recycled pool while moving between panels. Neither source inspection proves which feels faster. The runtime A/B comparison remains open; no winner has been declared.

## Merge acceptance

- [x] Inventory and decode the supplied package without writing it.
- [x] Identify shared resource collisions and inspect the relevant scripts.
- [x] Record the feature inventory, attribution and comparison strategy.
- [ ] Measure both column paths under the same conditions.
- [ ] Port all useful missing features and connect existing Apex equivalents.
- [ ] Qualify native CAS, F11, all form owners, all household members and undo.
- [ ] Test transparent CC, dialogs, keyboard focus, resolution changes and preferences.

The merge is **in progress**. This checklist deliberately does not mark code inspection as a completed feature port.
