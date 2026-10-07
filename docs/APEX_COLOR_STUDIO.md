# Apex Color Studio — Native Full Color Slider Support

Last reconciled: 2026-10-06
Authorized baseline: thepancake1 Color Sliders v4f
Current public Color Sliders verification: UI updated/checked for Sims 4 patch 1.127.41 on 2026-08-26; v4 texture update last published 2026-07-28.
Current Apex target game build: Sims 4 PC 1.128.90.1030.

## Objective

Make full color-slider state a first-class part of Apex appearance data and copying.

Apex must:
- perfectly preserve Color Sliders-style custom colors when copying CAS parts, outfits, forms or whole appearances;
- provide its own color editing UI and runtime behavior even when thepancake1 Color Sliders is not installed;
- use the authorized current thepancake1 implementation as the concrete code/resource/conversion baseline;
- remain compatible when the original Color Sliders mod is installed;
- update its own UI/resources/converted texture coverage for the current game build rather than freezing at the baseline patch.

The original mod is optional interoperability. Apex color features may not disappear when it is absent.

---

# Owner authorization / baseline

The project owner states they have **full permission from thepancake1** to use the relevant Color Sliders material for Apex.

Codex may inspect, extract, diff, reuse, port, adapt, merge and improve thepancake1-owned UI/package/tooling/texture-conversion material covered by that permission.

Start from the newest author-authorized Color Sliders baseline available to the project. The current public baseline verified for this spec is **Color Sliders v4f**.

Do not recreate equivalent working Color Sliders infrastructure from scratch merely for clean-room reasons when authorized reuse/porting is the stronger route.

Preserve provenance for:
- thepancake1 material;
- any separately owned MizoreYukii/CmarNYC/other third-party contributions inside older/current lineage;
- EA source resources used to produce converted textures.

Permission from thepancake1 does not automatically grant rights over unrelated third-party material.

---

# Current baseline behavior to preserve and exceed

Public v4f documentation currently exposes makeup-style color controls across most compatible human-Sim CAS categories, including:

- Full Body Clothes;
- Hairs;
- Facial Hairs;
- Tops;
- Bottoms;
- Shoes;
- Base Layers;
- Accessories, including glasses, gloves, socks, necklaces, earrings, wrist accessories, nose/brow/finger rings/accessories, leggings, fingernails, toenails and skin specularity;
- Body Hairs;
- Hats and Head Decorations;
- additional compatible skin-detail categories, especially CC.

The public v4 architecture separates:
- UI packages that enable sliders;
- optional eyebrow slider UI behavior;
- converted texture packages by pack/category;
- patch texture packages.

Apex must preserve the useful behavior while eliminating manual dependency/setup burdens.

---

# Canonical Apex ColorState

Color is not just a visual UI effect. It is part of the appearance state.

For every compatible applied CAS part, Apex must model a typed `ColorState` containing the actual current-game serialization discovered at implementation time and, semantically, at least:

- CAS part/resource identity;
- base swatch/color variant identity;
- Hue;
- Saturation;
- Brightness/Value;
- Opacity;
- form identity;
- outfit category/index;
- body type/category;
- slider-enabled / slider-compatible state;
- converted-texture/resource compatibility identity;
- custom/saved color swatch identity where the game persists it;
- provenance/source;
- last verified game-build/schema version.

Do not invent byte layouts. Codex must resolve the actual current-game fields/resource/state representation from the authorized baseline and current game data.

The canonical appearance model, CAS History, Saved Forms, Live CAS Studio, Tray import, Drift Guard and copy engine must all share the same ColorState owner.

---

# Copy/paste invariants

## Color follows the part

When a CAS part is copied and the operation includes that part/category, copy its full compatible ColorState by default.

This applies to:

- single-part copy;
- category copy;
- outfit slot copy;
- outfit category copy;
- full outfit copy;
- all-outfits copy;
- Sim A -> Sim B copy;
- Face-only / Body-only copy when relevant colored parts are in scope;
- whole-Sim Appearance Clone;
- human/occult form copy;
- Saved Form;
- CAS History checkpoint;
- Apex appearance/outfit preset;
- Tray Sim/household source when color metadata is present/resolvable;
- bulk selected-Sim operations.

Do not copy only the CASP/swatches and silently normalize the custom color.

## Explicit color copy modes

Every copy operation should expose:

- **Part + exact color** (default);
- **Part only / preserve destination color** when compatible;
- **Color only** onto a compatible destination part;
- **Base swatch only**;
- **Full slider state**;
- **Palette / selected categories**.

Unsafe/incompatible modes are disabled with a reason.

## Exactness

A copied color is successful only if the destination reproduces the source slider state within the current game's actual serialized precision and renders equivalently on a compatible texture.

Do not quantize custom colors down to ordinary EA swatches.

---

# Apex-owned color editing

## F11 Color Studio

Live CAS Studio gets a first-class Color panel with:

- Hue slider;
- Saturation slider;
- Brightness/Value slider;
- Opacity slider;
- base swatch chooser;
- numeric fields;
- reset each channel;
- reset all;
- copy color;
- paste color;
- save color;
- favorite color;
- palette library;
- recent colors;
- compare before/after;
- exact current ColorState inspector.

Support mouse, keyboard and fine/coarse increments.

Every continuous slider gesture coalesces into one CAS History action.

## Normal CAS integration

Apex should also provide native CAS slider availability where technically safe by evolving the authorized thepancake1 package/UI approach.

Target artifact:

- `ApexColorSliders.package`

It may be bundled as an optional first-party Apex module, but it must not require the original thepancake1 package.

If architecture proves cleaner, UI-enable resources may be integrated into another Apex CAS package, but ownership/manifests must remain explicit.

The F11 Color Studio remains functional even if native-CAS slider UI injection becomes temporarily incompatible after an EA patch.

---

# Texture compatibility / conversion

The slider UI alone does not make every texture visually recolorable.

Build an Apex-owned patch-aware conversion pipeline from the authorized v4 texture/conversion architecture.

Requirements:

- inventory current game CASP + diffuse/related texture dependencies;
- detect installed packs;
- determine whether a part already supports the required slider rendering;
- convert current EA textures/resources when required;
- preserve slider-ready CC without needless conversion;
- produce deterministic, manifest-backed Apex texture resources;
- regenerate only changed/new source resources after a patch;
- record source resource ID/hash -> converted output ID/hash;
- validate visual/resource linkage;
- never whole-scan/convert game resources during active CAS.

Preferred user experience:
- no manual download of per-pack texture folders;
- no manual patch-folder priority dance;
- Apex detects installed packs and ships/builds exactly the compatible resources required.

If distribution constraints make prebuilt EA-derived converted textures inappropriate, provide an automated local builder/updater that produces the Apex-owned texture package(s) from the user's installed game with no manual package selection.

---

# Current patch gap

Public Color Sliders v4f is documented as updated/checked through patch 1.127.41, while Apex currently targets PC 1.128.90.1030.

Therefore:

- do not claim v4f resources are automatically current;
- diff current `classlibrarygamedata`, `cascustomizer`, CASP and relevant texture/resource inputs;
- port the authorized v4f behavior forward to the exact current build;
- classify each reused UI/resource as unchanged / adapted / regenerated / replaced;
- runtime-test the exact Apex artifact on 1.128.90.1030.

---

# UI conflict/coexistence handling

The authorized baseline documents conflicts around:

- `classlibrarygamedata` for main slider UI;
- `cascustomizer` for eyebrow sliders;
- load-order interaction with More CAS Columns.

Apex must:

- detect the original Color Sliders package if installed;
- detect More CAS Columns and other overlapping UI overrides;
- identify overlapping resources/TGIs;
- avoid duplicate double-patching;
- integrate/merge compatible UI behavior when authorized and practical;
- report the active winner/owner;
- preserve More CAS Columns compatibility without requiring filename-prefix/load-order hacks from the user;
- remain fully functional with Color Sliders removed.

Never silently overwrite another UI mod's changes when the merged behavior can be resolved.

---

# Hybrid / occult color ownership

ColorState is form-specific.

Apex must:

- keep Human color edits separate from Vampire Dark Form / Werewolf / Mermaid / Alien / Fairy / other forms unless explicitly copied;
- copy exact color into an explicitly selected target form only;
- protect occult-only CAS parts;
- keep werewolf coat/body/head-specific coloring independent from human clothing/hair coloring;
- journal cross-form color transfers separately;
- verify form switch away/back reproduces the intended colors;
- verify save/reload/restart persistence.

No cross-form flattening.

---

# CAS History integration

Color changes are semantic history events.

Examples:

- `Hair · Hue 0.18 -> 0.72`
- `Top · Saturation 0.90 -> 0.42`
- `Accessory set · Applied saved palette "Plum Night"`
- `Outfit copy · 7 parts + exact ColorState copied`
- `Color-only paste rejected · destination texture not slider-compatible`

Undo/Redo must restore the exact pre/post ColorState.

Jump-to-state, branches, checkpoints and Saved Forms must retain ColorState.

---

# Saved palettes / presets

Support reusable:

- single colors;
- named palettes;
- category color sets;
- outfit color sets;
- full appearance color sets.

Allow:
- save current;
- rename/tag/favorite;
- search;
- copy/paste;
- preview;
- apply to selected compatible categories;
- deterministic export/import.

Do not silently apply a color to an incompatible part.

---

# Randomization

Live CAS randomization gets optional color behavior:

- Preserve exact colors;
- Randomize base swatches only;
- Randomize full ColorState;
- Randomize within saved palette;
- Randomize within selected hue/saturation/value/opacity bounds.

Default should preserve colors unless the user explicitly includes color in the randomization scope.

All randomization is reversible.

---

# Missing resource / CC behavior

If source ColorState references:

- missing CC;
- missing converted texture;
- missing pack;
- changed resource after patch;
- unsupported destination part;

show the exact issue.

Do not:
- silently reset to default;
- silently substitute a random swatch;
- drop the slider values without reporting it.

Allow safe partial application only with explicit preview/policy.

---

# Performance

- Color lookup/state access must be indexed by exact Sim/form/outfit/part.
- No per-frame package scanning.
- No texture conversion in active CAS/Live interaction.
- Cache compatibility/resource mappings by exact game build + source hashes.
- Slider preview must remain interactive.
- Continuous gesture updates may render live, while persistent history/checkpoint writes coalesce at gesture completion.
- Cancel stale preview/diff jobs.
- Batch outfit/all-outfit color copy as one transaction with compact child diffs.

Benchmark:
- single slider drag;
- apply saved color;
- outfit copy with 10+ colored parts;
- all-outfits copy;
- whole appearance clone;
- Undo/Redo;
- form switch;
- save/reload.

---

# Required runtime matrix

Test with and without the original thepancake1 Color Sliders installed.

Test at minimum:

1. EA hair with Apex-supported converted textures;
2. slider-ready CC hair;
3. tops/bottoms/full-body/shoes;
4. accessories;
5. body hair;
6. hats/head decorations;
7. eyebrows;
8. nails;
9. base layers;
10. compatible skin detail CC;
11. multiple outfit slots;
12. human -> human Sim copy;
13. human -> occult-form copy where compatible;
14. werewolf/hybrid form isolation;
15. Tray/preset source;
16. missing CC;
17. More CAS Columns coexistence;
18. Color Sliders installed alongside Apex;
19. Color Sliders absent;
20. save/reload/full restart.

For every copy test, compare exact source/destination ColorState and rendered result.

---

# Completion standard

Apex Color Studio is complete only when:

- the full relevant thepancake1 Color Sliders capability is preserved or improved;
- Apex can expose/use full color controls without requiring the original mod;
- every accepted appearance/outfit copy path preserves exact compatible ColorState;
- custom color does not collapse to ordinary EA swatches;
- F11 Color Studio works outside CAS;
- native CAS slider support works on the current supported build where enabled;
- current EA/CC compatibility is patch-aware;
- More CAS Columns/overlapping UI conflicts are diagnosed/merged safely;
- human/occult form color state remains isolated;
- CAS History/Undo/Redo/Saved Forms preserve exact color;
- clean-profile Apex-only runtime proof passes;
- exact release artifacts are hashed/manifested and current-build tested;
- performance remains materially non-regressive.
