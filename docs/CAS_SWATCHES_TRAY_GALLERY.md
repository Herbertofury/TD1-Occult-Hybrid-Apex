# CAS families, swatches and native Tray gallery

The F11 EA + CC library presents one item card per native CASP OutfitID family.
Inspect a card to choose its real color swatches; each choice retains the exact
CASP key, resource hash and source package. Unknown/zero family IDs stay separate.
Fitting flags, species and the CC creator/package namespace prevent unrelated
items with colliding family IDs from merging. Conflicting resource bytes remain
distinct variants; identical repeated containers collapse in the browser.

The CLI still supports flat forensic resource pages. Add `--grouped` to request
CAS item cards. Rebuild a catalog with the current schema before serving it:

```powershell
python tools/apex_cli.py live-cas-catalog build --input sources.json --index .work/live-cas-catalog/library-new.sqlite
python tools/apex_cli.py live-cas-catalog serve --index .work/live-cas-catalog/library-new.sqlite --expected-index-sha256 EXACT_BUILD_HASH --tray-root 'C:\Users\Owner\Documents\Electronic Arts\The Sims 4\Tray'
```

Sources are explicit read-only package paths with `mod` or `ea` origin.
Thumbnail providers in other EA packages are indexed by exact resource key and
verified lazily. Browsing does not copy packages or export Sim meshes/textures.
Missing images can be rendered with **Render missing images** or the selected
item's **Render this item's thumbnail** button. This uses an immutable preview
Sim and the actual content-verified CASP in a detached scene, a separate renderer,
and a 256×256 GPU readback. Only thumbnail pixels are retained in the page's RAM
cache. It never equips a thumbnail item on the real Sim, enters a CAS room,
changes the visible character preview, or writes a save. Generated previews are
identified as rendered previews; they are not substituted for verified EA images.
Incompatible or unsupported content and missing base scenes remain explicit
failures. Universal age/species/fitting and exact EA material equivalence still
require acceptance coverage.

**Tray gallery** searches native households, lots and rooms by their real names,
creators and descriptions. Portraits decode from their native envelopes on
demand. Select a household and its source Sim, then **View this Tray Sim in 3D**.
The preview form/outfit switcher shows that source's represented stored forms.
**Copy displayed Tray form** copies appearance only; the selected destination Sim
stays separate. The appearance transfer panel supplies cross-form outfit,
skin-detail, tattoo and custom field selections, with Preview/Apply/Discard/Undo.

Complete existing Tray groups can already be imported/exported through the Tray
CLI. Lot/room 3D reconstruction, current-Live-Sim creation of a new native Tray
item, dependency collection and full Gallery/Tray Importer parity remain open.

The development `household` CLI additionally reads complete native Sim records
and exact external household binaries in the marked disposable profile. Use
`export-records` for an external review ZIP. These files are not a native Gallery
item: generated metadata/portraits are unverified and `export-tray` deliberately
refuses to stage them into the game's Tray. `load-tray --source-file` verifies the
exact source hash/roster and allocates new identities; existing Sims stay intact.
Failed imports retain allocated IDs and block replay. `recover-import` requires
those IDs to be absent after an unchanged unsaved reload before retiring its
journal. Successful all-field household loading/save/reload remains an acceptance
gate; see `Reports/MULTI_HYBRID_CRASH_2026-10-12.md`.

`switch-archive-unsaved` can archive a failed switch after verified unsaved
closure with exact bank/closure/save hashes. It preserves the entire bank preimage
and immutable switch history. It never restores appearances or certifies CAS.

Focus-free F11 commands are available through `preview library-select`, `preview thumbnail`,
`preview gallery-query`, `preview gallery-select` and `preview gallery-view`,
with `--values` pointing to bounded typed JSON. Thumbnail values use exact
`part_id`/`index_sha256`; gallery queries use a `query` containing
`text`/`kind`/`offset`/`limit` (60). Gallery selection uses exact
`item_id`/`library_sha256`; source view uses an exact represented `sim_id`.
`library-select` accepts exact `part_id`/`index_sha256` and optional
`swatch_offset`. It inspects a currently visible family card or one of that
family's returned swatches, without applying the item. `preview status` exposes
the exact selected CASP key/hash, ARGB colors and swatch-page counts. Other
indexes, invisible families and unresolved requests cannot be substituted.
Read `preview status` to observe completion instead of replaying unresolved
operations. Host pages and swatches have explicit bounded pagination.
