[← Apex](Home) · [How it works](How-Apex-Works) · [Dynamic CAS comparison](Dynamic-CAS-Companion-Merge)

# ⌕ CAS, content and fast search
### Find the item you recognize. Keep the identity you can verify.

> **Development reference · October 21, 2026**<br>
> The metadata backend, typo planning and native background transport are implemented. A schema-5 real-CC lookup through the native worker also passed: five packages, 62 CASPs and five item families; typo + creator + type + CC filtering returned the correct lipstick package with 30 grouped swatches. The new native CAS search presentation and its real card-selection proof remain unfinished. Do not interpret this design as a shipped search bar.

## The intended workspace

Search belongs in the existing **Filter Items…** bar immediately below the native category title, as requested in the Shoes example. Keep native filter chips and their ordinary filter-panel access alongside the editable query; do not move this into another floating window. Typing, cursor keys, selection and clearing must remain owned by the text field while it has focus. Type a recognizable item name, part of a `.package` filename or internal code; narrow by creator, CAS type and EA/CC origin. Keep ordinary native cards and swatches, a visible result count, an obvious clear action and a clear explanation when fuzzy matching corrected a term.

Arrow keys are being added for actual card navigation: Left/Right, Up/Down using the actual column count, Home/End, Page Up/Down and Enter through the native card-click route. A focus outline is distinct from the equipped selection. Input fields retain normal cursor behavior. Keyboard handling must not steal a dialog's keys, change a different Sim or equip an item merely because the focus moved.

## Why an index is necessary

CAS catalog identifiers alone do not supply reliable package filenames or creator names. Apex bridges the game's catalog to a resource index instead of inventing that missing information.

```mermaid
flowchart LR
    P[Installed EA and CC packages] -->|Read only, background| I[Resource metadata index]
    I --> Q[Prefix and typo search]
    Q --> B[Native background transport]
    B --> C[CAS result cards]
    C --> E[Native eligibility and exact selected owner]
    E --> A[Explicit player selection]
```

The full resource key has type, group and a 64-bit instance. Family and swatch identity are recorded separately. A native catalog base ID is not blindly cast into a resource key. Ambiguous or overridden candidates need resolution before Apex can claim a filename identifies the item currently loaded by the game.

### Names the player can choose

| Display | Meaning |
|---|---|
| **Readable name** | A uniquely resolved localized title when available; otherwise the best supported fallback |
| **Package name** | The installed container's filename, useful for identifying CC |
| **Code name** | The CASP's original internal name, useful for diagnostics |
| **Creator** | Verified EA origin or an explicitly unverified filename-derived creator hint |

Source spelling is retained. New schema-5 indexes also tokenize camel-case names, so a word inside `yfHair_SDXLightBrown` can be searched without renaming the resource. Older snapshots remain readable but need a rebuilt alias index for this improvement.

## Keeping typing away from gameplay

The broker verifies the immutable index at startup and retains a read-only lease. Querying does not reopen or hash every source package. Exact filters and pages are cached under the complete query, including creator, type, grouping and favorites. Cache entries are bounded and copied before a caller modifies presentation fields.

Exact/prefix results take priority. When none match, optional typo matching allows one insertion, deletion, substitution or adjacent transposition in a word. Corrections are returned for display. This does not promise arbitrary multi-word semantic search or unlimited edit distance.

The DLL worker retains at most the active request and the latest pending request. Every publication belongs to its ticket and exact CAS context. A changed Sim, form, session or generation cannot accept an old result. Network delays produce a pending/error state without holding the game thread. Fetching metadata never equips a part.

### Measured backend timing

On a 539,005-row schema-4 snapshot, the recorded 50-repeat warm-query medians were approximately **0.15–0.79 ms** across two recorded runs. The largest recorded warm sample was **0.97 ms**. Cold necklace queries took **56–108 ms**; opening/verifying that snapshot took **9.2 seconds** outside the game.

These measurements cover the metadata worker only. They exclude transport, native UI layout, thumbnail rendering and gameplay frame times. The older snapshot did not contain the new split-name aliases; tests of the alias feature use newly built schema-5 fixtures. A real large-library alias-index benchmark and in-game search qualification are still required.

The real-CC transport probe also passed against five copied packages (62 parts,
five swatch families). The DLL worker's `lipstik` query, filtered to Magic Hand,
makeup body type 29 and CC origin, returned the correct lipstick package as one
30-swatch family and suggested **lipstick**. The retained worker measurement was
1.323 ms including transport, with 0.406 ms in the metadata query. This small
snapshot and one request do not measure a large-library UI or game frame time.

## Content actions must tell the truth

An item's image should come from its actual resource or a properly identified generated preview. The game wins on age/species/body eligibility and actual loaded content. A missing image is not permission to show an unrelated thumbnail.

**Open in Sims 4 Studio** must resolve the containing package and open a verified working copy. Browsing or opening a package must not modify the owner's original CC. The full source location belongs in an explicit inspection view, not every network page.

Favorites, hidden items, recently tried items and saved outfits need separate identities and semantics. A recently tried item is not an undo snapshot. A saved outfit is not a whole-Sim replacement. Form history must preserve skin details, tattoos, jewelry, presets, sliders, unknown fields and individual outfit numbers.

## Native keyboard browsing


Arrow keys move a separate white focus outline through the native item cards.
Up/Down use that panel's actual column count, including a different count in
Face and Clothing panels. Home/End reach the first/last item; Page Up/Down move
by the visible rows. An off-screen target scrolls into view. Enter dispatches
the original card-click event: ordinary catalogs select the item, while an
equipped-item card opens its own category. Browsing alone does not equip a part.

Text fields retain their keys. Loading screens, modal dialogs and pending
semantic commands do not consume catalog navigation. A bounded FIFO retains
rapid Arrow-then-Enter order; changing the Sim, form, panel or native feed
invalidates old queued input and focus. The idle handler consumes one key per
frame and redraws the outline only when its bounds change. It does not scan
packages, call the metadata broker or rebuild the native catalog.

The CLI can exercise movement directly with `cas catalog-key --key down`, or
send actual window-addressed keyboard messages with `game key --background
--key DOWN`. The semantic command checks the native movement receipt and does
not provide an alternate equip path. A background delivery receipt establishes
window-message acceptance only; the changed UI must be observed separately.

The actual runtime pass below covers main hair/face cards and the equipped
category. Text fields, modals, variation popups, held repeat and specialized
palette/painter contexts still need separate qualification.

### Runtime corrections through V257

V254's actual Home command moved to the right card but exposed an uninitialized
page-step register. V255 initializes it explicitly; all eleven navigation
receipts then pass on the actual five-column, 436-item hair catalog. These are
index/movement receipts, not a complete visibility or physical-key pass.

The captures expose a Page Down target below the mask, despite an existing
recycled view. V257 measures the actual scroller mask, computes page size from
visible cells and places the outline inside the masked grid. A readback now
requires the focused card to be visibly inside that region.

Windows' acceptance of a posted key did not establish a CAS response. V256's
synthetic event also failed to reach its listener. V257 registers the native
stage listener for capture and target/bubble phases and adds
`cas catalog-input --key right --focus-catalog`. That invokes the same keyboard
handler inside the CAS movie. Enter is an explicit supported input and reports
the possibility of an appearance change; a dispatched card click alone does
not prove which part was equipped. The optional focus flag changes the game
UI's focus only. Text fields and modals retain their guards, and received-key,
rejection and visibility diagnostics are retained. Actual V257 qualification
is recorded below.

Validation also passes 171 focused Python cases and fourteen native targets.
The broader 2,732-case run passes 2,731 cases and finds one obsolete fixture
looking for a listener in a callback which was deliberately retired. The fixture
now injects prohibited input into that empty callback, adds a separate inline
mutation of the active EA panel, and requires both serialized regressions to be
rejected. All 23 affected bytecode cases pass. No production validator or field
comparison was relaxed to obtain that result.

### Actual V257 qualification

Eleven navigation steps pass on the current Alien's 436-item, five-column Hair
catalog, including the partial last row. The actual mask and focus rectangles
are checked, with End/Page Down captures reviewed. The native Face/Nose grid
separately confirms two-column Up/Down movement. A background Windows RIGHT
message reaches the stage listener and changes the index from 2 to 3.

Enter uses the native card handler to change hair from 272449 to 272455, and
native Undo restores 272449. The recorded desktop foreground remains unchanged.
Enter on the first of twenty equipped cards opens Hair without changing its
worn part. That navigation executes in the next idle UI phase: the retained
initial assertion is followed by a fresh read, never a replayed Enter.

All twenty save/backup files remain unchanged. This selected-form pass does not
qualify edited-household persistence or actual-save use. The movable form strip
also overlaps lower cards in this narrow viewport; layout QA remains open. See
[the exact scoped report](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/blob/apex/recover-and-harden/Reports/CAS_KEYBOARD_V257.json).

## Remaining proof

**Native owner acknowledgement · V258.** A same-form refresh previously completed
in the native engine but waited for a changed-owner heartbeat in its UI readback.
The readback now consults the bound native owner directly. Seven actual bindings
pass, including same-owner Alien, Human and Vampire, and Alien → Vampire → Alien.
The original unresolved request remains retained and was never replayed. This
does not qualify edited-household/save/Tray retention. See
[the scoped runtime evidence](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/blob/apex/recover-and-harden/Reports/CAS_OWNER_REFRESH_V258.json).

The host CLI also avoids repeated API binding, duplicate inventory traversal and
unrelated certificate-store setup. File identities, USNs and per-request change
checks remain intact. Its measured inventory median falls from 278.4 ms to
109.3 ms; this is not a game frame-time claim.

- [ ] Complete and visually qualify the native CAS search bar and native result cards.
- [x] Verify a copied real-CC typo query with creator/type/origin filters through the native transport.
- [ ] Qualify the complete native CAS search UI, including filename and EA searches.
- [ ] Resolve exact native resource provenance before claiming a package is the active winner.
- [x] Qualify main-card navigation, scrolling, Enter/Undo and native two/five-column layouts in CAS.
- [x] Verify background Windows-key delivery and equipped-card category navigation.
- [ ] Qualify text fields, modals, variation popups, held repeat and specialized palettes.
- [ ] Verify changing members/forms during a search cannot publish or apply stale results.
- [ ] Add incremental invalidation for added/changed/deleted packages without full per-query rescans.
- [ ] Compare cold startup, memory use, tail frame times and large-category responsiveness.

[Follow implementation and evidence in PR #8](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/pull/8). The preservation failures documented in [How Apex Works](How-Apex-Works) remain release blockers independently of search.
