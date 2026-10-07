# thepancake1 Color Sliders Authorized Baseline Matrix — 2026-10-06

## Authorization

The project owner states they have full permission from **thepancake1** to use the relevant Color Sliders material in Apex.

Treat Color Sliders as an **authorized implementation baseline**, not merely an interoperability target.

Permission covers thepancake1-owned material as stated by the project owner. Separately owned contributions in the broader Color Sliders lineage retain their own provenance/terms unless separately authorized.

## Current public baseline

**Color Sliders v4f**

Public release page:
https://www.patreon.com/thepancake1/posts/color-sliders-157258822

Current public status documented there:
- UI updated/checked for patch 1.127.41 on 2026-08-26;
- texture files last updated 2026-07-28;
- v4 rebuilt the slider-enable UI packages;
- v4 introduced new base converted-texture packages split by pack/category;
- v2/v3 texture support is scheduled to end 2027-05-18.

Apex target game build is newer: 1.128.90.1030. Treat v4f as the code/resource baseline, then port forward.

## Public category coverage to inventory

- Full Body Clothes
- Hairs
- Facial Hairs
- Tops
- Bottoms
- Shoes
- Base Layers
- Accessories group:
  - Glasses
  - Gloves
  - Socks
  - Necklaces
  - Earrings
  - Wrist Accessories
  - Nose Rings
  - Brow Rings
  - Finger Rings/Accessories
  - Leggings
  - Fingernails
  - Toenails
  - Skin Specularity
- Body Hairs
- Hats and Head Decorations
- additional compatible skin-detail categories / CC

## Controls

The Color Sliders ecosystem exposes the makeup-style controls used for:
- Hue
- Opacity
- Saturation
- Brightness

Apex must discover and preserve the exact current-game serialized representation rather than assuming normalized storage from UI labels.

## Baseline architecture to study/port

Inventory:
- main slider-enable UI package/resources;
- eyebrow slider package/resources;
- `classlibrarygamedata` modifications;
- `cascustomizer` modifications;
- More CAS Columns compatibility behavior;
- base converted texture packages;
- patch converted texture packages;
- pack/category layout;
- conversion tooling/scripts if included in the authorized material;
- CASP -> diffuse/converted resource mapping;
- CC compatibility behavior;
- saved custom color behavior where present.

## Apex improvements

- no thepancake1 mod dependency;
- full ColorState copied with CAS parts/outfits/forms;
- F11 Live Color Studio;
- exact color Undo/Redo/history;
- saved palettes;
- hybrid form isolation;
- automatic installed-pack detection;
- current-patch resource diff/regeneration;
- no manual texture-pack selection;
- no manual folder/load-order naming tricks;
- current More CAS Columns coexistence;
- deterministic manifests/hashes;
- explicit missing texture/CC diagnostics.

## Patch gap

v4f is publicly checked through 1.127.41.
Apex targets 1.128.90.1030.

Codex must diff and port forward before current-build acceptance.
