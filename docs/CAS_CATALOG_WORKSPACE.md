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

The current Items tab is an interim text list. The owner's clarified target is
a full native CAS category: EA thumbnail tiles, swatches, native selected/hover
states and precise per-item removal. That replacement remains in development.
The reported missing right outline edge is also open; thumbnail geometry and
stroke inset must replace the current hit-area rectangle. A fixed-viewport
animation test was rejected when the window changed to 2560×1417; preferences
were restored and all 39 records still compared unchanged. Visible pulse/flash
qualification must use fresh geometry. Large-catalog category and thumbnail
costs also require measurement before any performance claim.

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
python tools/apex_cli.py cas catalog-view --state .work/reusable-profile-session.json --sim-id 285159751289798669 --view style --output .work/catalog-style-tab-check.json
python tools/apex_cli.py cas catalog-slider --state .work/reusable-profile-session.json --sim-id 285159751289798669 --control red --fraction 0.8 --output .work/catalog-red-slider-check.json
python tools/apex_cli.py cas catalog-view --state .work/reusable-profile-session.json --sim-id 285159751289798669 --view closed --output .work/catalog-close-check.json
```

These commands require a fresh output filename and retain the normal one-shot
request/acknowledgement evidence. Preferences require exact complete typed
values; an incomplete or mismatched result is refused.

The slider CLI invokes the same handler as pointer dragging and verifies both
the actual thumb position and its setting value. Color/glow changes have a
separate style signature; they do not invalidate or reposition the native
catalog grid. The thumb moves directly during dragging rather than waiting
for a panel rebuild. Outfit/part refresh events only mark the list dirty;
the next idle frame refreshes it when visible. A closed browser does no
background inventory scan.

V234 runtime evidence confirms that the native entry is below Shoes and the
20 current-outfit rows exactly match an independent protobuf decode, including
uint64 part keys and layer values. Requested columns 2/6/12 and static/pulse/
flash settings acknowledge correctly; the current portrait window fits five
columns. The selected native tile displays the custom magenta border.
The 1 ms-resolution selection timer measured a 2 ms maximum over 1,080 frames,
with four samples above 1 ms. This is not a universal 0–1 ms guarantee.

V236 reserves the complete catalog width in EA's model-bound container rather
than shifting a child repeatedly. In the 1278-unit portrait viewport the native
panel is 595 units wide, its local X remains zero, and its complete bounds fit
on screen. Six shared slider-handler samples verify setting and thumb position;
RGB/glow changes do not rebuild the grid. All 39 selected-Sim appearance records
remain byte-equivalent after the UI-only exercise. V237 additionally preserves
the enlarged width in the separate native outfit-header attachment, keeping
EA's outfit buttons, padding and handlers. V237 runtime captures verify all eight outfit categories fit without clipping;
its shared controls also retain all 39 selected-Sim appearance records.

The V235 outfit-refresh exercise discovered an unrelated destructive native
path: viewing Everyday 1 and returning to Swimwear changed Alien eyebrows and
forehead crease parts/genetics without selecting an item. The permanent guard
restored all 40 Live appearance views and retained 155 named looks; all 20 save
and backup files stayed unchanged. This is a successful guard recovery and a
**failed direct native isolation gate**. The direct outfit-normalization fix,
edited household, MCCC, save/cold-load and Tray/Gallery qualification remain open.

The game's SharedObject store did not retain the style across a real process
restart. The UI correctly labels these as session settings. Persistent Apex
preferences remain unfinished; do not advertise them as saved.

Progress:

- [x] Inspect donor resource identities and column layout.
- [x] Preserve other native handlers and all non-script art/tags.
- [x] Add viewport-bound columns and selection controls.
- [x] Add native radial entry, CAS panel, F11 controls and semantic CLI.
- [x] Test outfit array decoding, layer retention, invalid preferences and
  exact Sim/form acknowledgements; compile the candidate.
- [x] Verify the native entry's placement, native tile border, viewport column
  changes, style acknowledgements and exact equipped rows in game (V234).
- [x] Qualify the shared slider handler, exact value and actual thumb (V236).
- [x] Qualify outfit refresh and color changes without grid rebuilding.
- [x] Verify complete catalog bounds and 39 unchanged appearance records (V236).
- [x] Qualify the V237 separate outfit-header clamp in game.
- [ ] Qualify physical pointer button/drag events; semantic handler checks do
  not prove native hardware input delivery.
- [ ] Complete persistent preference storage and reload; SharedObject failed.
- [x] Measure V235 selection work: 2,445 frames, 2 ms maximum, nine above 1 ms.
  Slider samples below the clock's 1 ms resolution are not literally zero time.
- [ ] Qualify latency across broad catalogs, resolutions and mod combinations.
- [ ] Qualify CC display names/thumbnails in this integrated CAS list.

V236's subsequent five-member no-edit CAS/Live cycle has no differences before
the guard; after simulation advances, all 40 Live views and 155 named looks
remain exact. Every save/backup file remains unchanged. This does not qualify
the separate destructive outfit-view path discovered in V235.

The final V237 launch recovered from an EA dialog that returned only blank
capture frames. The CLI completed a source-pinned normal-permissions EA restart
with a recovery receipt, then launched the verified account content ID 1015806
and loaded the disposable household. The rejected handoff was not silently
replayed. This is a verified recovery path, not proof every EA dialog can be
automated.

## Adjustable cards, V247

The Card layout tab adds proportional card size (65–160%), independent horizontal
and vertical spacing (0–32 logical pixels), and an EA card-size/spacing reset.
Columns and size fit the available viewport; the requested size can be reduced
on a narrow screen so at least two cards remain accessible. Selection styling
stays separate. Native thumbnails, swatches, hover removal and hit areas scale
together. EA still owns the recycled cells and on-demand thumbnail loading.
Only cells carrying Apex's empty marker use the scaled-height getter. The other
1,784 native Customizer methods retain their original bytecode and all native
non-code tags remain unchanged.

F11 exposes the same values. Semantic CLI controls are:

```
cas catalog-cards --card-scale 0.85 --gap-x 2 --gap-y 8 ...
cas catalog-view --view layout ...
cas catalog-slider --control card_scale --fraction 0.4 ...
cas catalog-card-reset ...
```

The selection outline anchors to the actual thumbnail, with the whole stroke
inside its mask. V247 draws each edge and corner explicitly, closing the path
instead of relying on GFx's incomplete stroked rounded-rectangle primitive.
Runtime status reports actual cell scales, positions, native heights and hit-area
bounds, instead of treating requested settings as rendered geometry. Layout
controls sit clear of the native catalog, so changes can be previewed while
dragging. Fresh semantic panel navigation also sends EA's radial state message
to establish its model attachment.

### Row-cache regression

V241's acknowledged settings and correct panel widths did not prove row spacing:
independent coordinates rejected its overlapping rows. V242's native height
readback was correct, but ordinary positioning still failed. V243 patched a
dormant library copy; V244 found the active ClassLibrary, yet its placement also
failed. V245's separate calculated/cache/display readbacks finally identify the
cause: the first cached Y value is not finite. Arithmetic propagates that invalid
anchor, and the native display objects retain their previous positions.

V246 uses EA's existing `ResetAndPositionCells` operation when changing layout
or correcting stale rows. The native reset seeds the cache before positioning
and drawing recycled cells. No shared ClassLibrary/OlympusLibrary override or
replacement layout algorithm ships. The compiled gate rejects replacing reset
with ordinary positioning. Failed convergence is bounded and restores the native
layout; it cannot become an endless idle relayout loop.

V246 passes all four actual layouts and eighteen controls at 1278×1376. Its
spaced and large layouts show distinct second rows at 204.45 and 267.2 units.
The EA reset and independent sliders pass, all 39 retained appearances remain
unchanged, and no save is written. Separate pixel review rejects its selector:
three edges have full central coverage, while the right edge has zero at every
size. V247 requires explicit path segments in compiled bytecode; V247 actual captured
pixels confirm full central coverage of all four edges at every tested size. Glow, pulse and flash remain separate checks.

The failed UI-only runs retain all 39 committed selected-Sim appearance records,
with every save/backup file unchanged. Their forced disposable-session closures
are recorded as forced termination. V245's two startup promo cards were closed
through individually observed background CLI input; its rejected Resume request
submitted no click. Fresh Home and subsequent Live observations are retained
separately from that refusal.

- [x] Build bounded card size, separate gaps, reset and CAS/F11/CLI controls.
- [x] Preserve native art, recycling and unrelated native bytecode.
- [x] Require the native Margin binding, scaled height and row-cache reset.
- [x] Qualify four sizes/gaps against actual cell positions and viewport (V246).
- [x] Inspect all four selection-outline edges in the actual captures (V247).
- [x] Verify all 39 retained appearances after the complete control pass (V246).

V247 also qualifies actual native pointer delivery: window-addressed background
CLI clicks change the three visible sliders independently to 112.5%, 6.4 and
25.6, then the visible EA reset returns 100% and gaps 4/4. Every request has a
fresh receipt, the game is never asked to take focus, and all twenty save files
remain unchanged. This verifies clicks through the real controls in addition to
the semantic shared-handler tests. It does not qualify a continuous physical
mouse drag or another viewport. See [the scoped report](../Reports/CAS_CARD_LAYOUT_V247.json).

The equipped-item text list remains interim; it is not the requested native
thumbnail category. Persistence, animated border visibility,
large-catalog hitch measurements and the direct outfit-normalization fix remain
separate open gates. These controls do not qualify actual-save use.

Validation also passes 171 focused Python cases and fourteen native targets.
The broader 2,732-case run passes 2,731 cases and finds one obsolete fixture
looking for a listener in a callback which was deliberately retired. The fixture
now injects prohibited input into that empty callback, adds a separate inline
mutation of the active EA panel, and requires both serialized regressions to be
rejected. All 23 affected bytecode cases pass. No production validator or field
comparison was relaxed to obtain that result.
