# Apex rebuild acceptance inventory

This inventory records the requirements relayed by the Modernize project
handoff and the later user direction. It is a review checklist, not evidence
that this branch implements or passes any item. The diagnostics branch is based
on an earlier upstream commit; it is not the complete preserved desktop working
tree. Reconcile changes against that tree without overwriting it.

## Forms and preservation

- Retain a single shared Human form and independently editable owned occult
  forms. Preserve per-form appearance and appropriate Sim-wide fields across
  CAS entry and reentry, accept and cancel, household switching, Live Mode,
  travel, save and cold load, Tray and Gallery. Include all forms and variants
  listed in `APEX_OCCULT_HYBRID_CORE.md` and the active player checklist.
- Keep the permanent preservation guard while fixing destructive behavior;
  do not bypass it to make a test or save pass. Preserve native occult gameplay,
  including Mermaid swimming and voluntary Werewolf transformations.
- Keep native form-selection affordances, category Link/Unlink and directional
  whole or selective Copy. Cover applicable outfits, details, tattoos, presets,
  body, face and other appearance fields without changing unrelated forms.
- Support the requested human-looking Werewolf options and repair applicable
  rendering issues without stripping choices. Preserve selected Fairy wing
  colors and qualify compatible wing and tail animation in each requested mode.

## Catalog and CAS

- Integrate the user's supplied Dynamic CAS package features with Apex in one
  coherent UI. Verify favorites, hide/history, saved outfits, swatches, search,
  filters, previews, backgrounds, sliders, playback, settings, presets and
  hotkeys individually against the exact supplied version. Respect attribution
  and the applicable license; do not publish third-party assets as source.
- Retain **both bottom sliders**, one for thumbnail size and one for column
  count. Also provide an integrated panel-edge drag and heart controls for
  per-card favorites and filtering, following the later user reference. The
  reference video motion has not yet been verified. Support at least 12 columns
  and the requested wider range without covering the Sim or native controls.
- Preserve native All Equipped thumbnails and removal plus the requested text
  list. Provide the requested item and package provenance, search combinations,
  swatches and missing-preview handling. In F11, identify each equipped item's
  exact name and image and offer opening it in Sims 4 Studio, including skin
  details and every applicable CAS category.

## External CAS, exchange and compatibility

- Full external and F11 CAS, separate form previews, appearance controls,
  cameras, color editing, live or staged application, undo/redo, presets and
  slider integration remain required. Coordinate with the separate external
  CAS work instead of duplicating or overwriting it.
- Qualify searchable Tray/Gallery workflows, whole-Sim and selected-form
  transfer, selective appearance fields and household round trips while
  preserving unrelated destination data.
- Preserve the requested native and mod compatibility, F11 controls, attribution
  and documentation. Current patch compatibility and historical bug fixes
  require evidence for the actual build, not a historical partial pass.

## Evidence gates

- Preserve the existing dirty checkout, saves and installed mod. Use a
  verified backup, isolated disposable profile and independently verified input
  for a no-Apex control. Coordinate exclusive game ownership first.
- Establish repeated matched control captures, then reintroduce real feature
  groups cumulatively. Stop and investigate a regression before moving on.
  Record workload, identities, cache conditions and raw evidence; compare
  p95, p99, worst intervals and hitch counts as well as averages. Distinguish
  submitted inputs from observed UI transitions and declared packages from
  independently observed loads.
- Synthetic tests, static bytecode checks and historical runs are useful but do
  not certify in-game behavior, current feature parity or performance. A clean
  build does not establish a speedup. No frame comparison currently qualifies
  as a matched no-Apex baseline.

Primary project sources include `APEX_OCCULT_HYBRID_CORE.md`,
`OCCULT_SAFETY_CONTROLS.md`, `APEX_CAS_UNLOCK_CORE.md`,
`CAS_NATIVE_OWNER_CONTRACT.md`, `DYNAMIC_CAS_UPDATED_DONOR_AUDIT.md`,
`CAS_SWATCHES_TRAY_GALLERY.md`, `APEX_EXTERNAL_CAS_MILESTONE_20261030.md`,
`PRESETS_SLIDERS_CLI.md`, `CAS_1129_CATEGORY_HITCH_EVIDENCE.md`,
`FRAME_BENCHMARK.md`, `APEX_ACCELERATOR_INTEGRATION.md`, and the preserved
`.work/apex-wiki/Active-Player-Checklist.md`. Later user directions control
where an older design differs.
