# CAS catalog workspace

The owner's `More_CAS_Columns_(6_Columns).package` is the layout reference.
SHA-256: `7df4290426fdfeca458b873c7c38626c124b5756314467cc87146d215944c79e`.
Its two resources include the same Customizer resource Apex already adapts.
Do not install both overrides together. No donor source export is committed.

Apex retains the installed game's native bytecode and art. It changes the
clothing catalog's recycled grid in place: a 262-unit two-column panel grows
by 111 units per added column. The requested 2–12 columns fit the logical
viewport automatically; tiles keep their native dimensions and lazy loading.

The native body arc gets an **All equipped CAS items** entry after Shoes.
It uses EA's existing circular renderer, native Show All icons and tooltip.
The Items and Catalog Style tabs share one CAS panel. F11 exposes the same
style preferences and opens that same inventory.

The selected-item frame supports RGB sliders, border width, optional glow,
opacity, static/pulse/flash modes and animation period. Static is the default.
Only recycled visible selected tiles receive effects; previous native frame
transforms are restored on deselection and teardown. The UI reports whether
Scaleform's local preference store accepted persistence. A storage failure
leaves working session settings rather than claiming a saved preference.
The supported primitive storage and shape glow APIs follow
[Autodesk's Scaleform AS3 support reference](https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/scaleform_help/flash_support/as3_class.html).

Inventory is read on demand from a detached copy of the selected native
model, including unsaved edits. It does not synchronize or commit an owner,
query inactive panels, export thumbnails or export complete Sims to disk.
Each row retains its exact 64-bit part key, body type, color and layer.
Unknown future body types remain visible without a guessed navigation target.
The current implementation labels these native categories and exact part
keys; CC marketing names and thumbnails in this CAS panel are not yet
qualified. Changing Sim/form invalidates the displayed list before navigation.

CLI examples, using the marked disposable state and actual selected Sim ID:

```powershell
python tools/apex_cli.py cas catalog-style --state .work/reusable-profile-session.json --sim-id 285159751289798669 --columns 6 --color 0x00c9eb --glow 4 --border 3 --animation pulse --strength 1 --period 1.4 --output .work/catalog-style-check.json
python tools/apex_cli.py cas catalog-open --state .work/reusable-profile-session.json --sim-id 285159751289798669 --output .work/catalog-open-check.json
```

Both commands require a fresh output filename and retain the normal one-shot
request/acknowledgement evidence. Preferences require exact complete typed
values; an incomplete or mismatched result is refused.

Progress:

- [x] Inspect donor resource identities and column layout.
- [x] Preserve other native handlers and all non-script art/tags.
- [x] Add viewport-bound columns and selection controls.
- [x] Add native radial entry, CAS panel, F11 controls and semantic CLI.
- [x] Test outfit array decoding, layer retention, invalid preferences and
  exact Sim/form acknowledgements; compile the candidate.
- [ ] Verify the actual radial button, sliders, selection frame, column
  resizing and cleanup in the running game.
- [ ] Measure added UI work and qualify local preference reload.
- [ ] Qualify CC display names/thumbnails in this integrated CAS list.
