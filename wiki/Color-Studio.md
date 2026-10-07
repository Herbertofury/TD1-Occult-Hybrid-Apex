# Apex Color Studio

**Full color sliders everywhere Apex can edit or copy CAS appearance.**

Apex treats custom color as real appearance data—not something that gets lost when an outfit or Sim is copied.

## Authorized baseline

The project owner has full permission from **thepancake1** to use the relevant Color Sliders material.

Current public baseline: **Color Sliders v4f**.

Apex starts from the real authorized implementation, ports it forward to the current game, and improves it. The original Color Sliders mod is **not required** in the final install.

## Exact ColorState

For every compatible CAS part Apex preserves:

- base swatch;
- Hue;
- Saturation;
- Brightness/Value;
- Opacity;
- exact Sim/form/outfit/part ownership;
- texture compatibility/provenance.

## Copying

Full color travels with:

- a single part;
- selected CAS category;
- outfit;
- all outfits;
- Sim A -> Sim B;
- Face/Body/Appearance Clone;
- occult forms;
- Saved Forms;
- CAS History checkpoints;
- presets;
- Tray sources when resolvable.

Default: **Part + exact color**.

Also allow:
- Part only / preserve destination color;
- Color only;
- Base swatch only.

Never silently collapse a custom color to a standard EA swatch.

## F11 Color Studio

The current candidate implements exact signed-Q14 numeric H/S/B/O controls and
per-channel reset using the selected effective CASP's actual ranges. It preserves
unedited lanes, requires explicit preview/Apply and supports scoped recovery and
Undo/Redo. Independent original-C# comparisons and a real hidden DX11 render test
pass. Palettes/favorites, conversion and full accepted runtime scope below remain
tracked work. See [current evidence](../Reports/SIDECAR_AND_COLOR_2026-10-07.md).

- Hue
- Saturation
- Brightness
- Opacity
- numeric values
- base swatches
- copy/paste color
- recent/favorite colors
- saved palettes
- reset
- before/after preview
- Undo/Redo

## Native CAS

Apex also targets its own native-CAS slider package/integration so full sliders remain available without the original mod.

Converted textures are patch-aware and installed-pack aware rather than requiring the user to manually manage a forest of per-pack folders.

## Hybrid aware

Human and occult-form colors remain separate unless the user explicitly copies color between forms.

Full spec: [docs/APEX_COLOR_STUDIO.md](../docs/APEX_COLOR_STUDIO.md)

Baseline matrix: [docs/PANCAKE_COLOR_SLIDER_BASELINE.md](../docs/PANCAKE_COLOR_SLIDER_BASELINE.md)
