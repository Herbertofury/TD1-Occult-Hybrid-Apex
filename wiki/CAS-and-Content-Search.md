[← Apex](Home) · [How it works](How-Apex-Works) · [Dynamic CAS comparison](Dynamic-CAS-Companion-Merge)

# ⌕ CAS, content and fast search
### Find the item you recognize. Keep the identity you can verify.

> **Development reference · October 21, 2026**<br>
> **V269: readable native search and real card selection verified.** In full CAS, `lipstick` displays readable text and the matching CC card. Typo + creator + type + CC filtering also passes; 30 indexed variants map to one eligible native card. No-match returns zero cards and clearing restores all 41 original cards. Selecting that filtered card through the native click route changes the lipstick; Undo restores its exact original part and color modifiers. This scoped test uses five copied CC packages and 62 CASPs. Full-library qualification and automatic broker distribution/startup remain open; this is not a release claim.

## Search by the Sim who wears it

The offline catalogue now supports `sim:"Bella Goth"` and
`household:"Goth Family"`, combining equipped CC across captured forms and
outfits. Add `form:Alien outfit:everyday/2` to narrow the look, or combine
`author:`, `folder:` and normal item text. Outfit numbers are one-based.
Matching names can include several Sims; `sim-id:` and `household-id:` select
one identity precisely. These searches never change the selected Sim or equip
anything. F11 item tooltips identify matching Sims, forms and outfits.

An explicit paged capture builds a separate immutable reference index, without
exporting Sim meshes, textures or complete Sim records. Replacing a household
capture updates names, membership and moved Sims atomically, while retaining
other captured households in the same save. Wrong save/catalogue pins and stale
captures are rejected. Native CAS also checks the capture's session. Empty
native outfits with ID zero remain empty.

**Measured, with limits:** retained native appearances from the real five-Sim
household produce a 90 KB reference index. Its four distinct CC resources are
found in the 539,005-item catalogue in 0.368–0.783 ms of query work after opening
the database. A separate 1,000-Sim fixture passes household isolation, item
deduplication and bounded provenance checks. These are worker/fixture results,
not a claim that the new UI path has been tested in the running game.

**Actual V271 check:** the five-member capture and native Sim, household, type,
form and outfit queries run in full CAS. The active Sim and every save remain
unchanged. Two CC references used by other members are indexed but their
swatches fail to map to the visible parent card in native CAS; that defect is
still open. F11 global browsing needs its separate actual-game pass.

Capture currently uses the marked test profile, committed CAS graphs and persisted names; automatic
production refresh after CAS/Live/Tray edits and an integrated capture button
remain unfinished. Pending try-ons and unsaved renames are not advertised as
current indexed data. Ambiguous resource identities remain unresolved rather
than being assigned to an arbitrary package. Most EA equipped attribution in
the older full catalogue still needs effective-resource hashes. The permanent
appearance guards and actual-save release gates remain in place.

The direct CAS-exit service also rejects after the body-hair pass. The actual
EA checkmark works through the background CLI: all forty appearances and 155
named looks remain intact after returning to Live, and saves are unchanged.
The existing household review journal must be resolved before Studio opens.
This is a retained regression, not a qualified direct-exit pass.

The full EA catalogue check also exposed a separate grouping bottleneck. A
metadata-only preparation job now builds swatch-family lookup tables and
category/origin/name indexes. The same real 60-card Hair page falls from
1,314.656 ms to 2.024 ms of worker query time, retaining all 1,423 families and
the exact card ordering. Custom text, folder, author and equipped predicates
retain their filtered grouping semantics. No game package is rewritten.

## The intended workspace

### V270 development: offline search and full creator metadata

The new Rust catalogue library reads a pinned local SQLite/FTS snapshot on the
native metadata worker. Its game build excludes the CLI and HTTP dependencies.
Indexing, S4MM cache import and provider downloads are explicit jobs that exit.
The current developer build still needs actual-game qualification; V269's
earlier scoped gameplay evidence below is not proof of these new changes.

The search language adds `folder:"Makeup"`, typo correction and indexed folder
suggestions, `package:*lipstick*.package`, quoted names, `-gloss` exclusions,
`added:7d`, `sort:newest` and `sort:modified`. Combine these with creator, type
and EA/CC filters. An exact folder includes descendants and excludes similarly
named siblings. “Added” uses recorded first observation of package content;
the initial baseline and moving an identical file do not create fake new CC.

The owner-requested WCIF import has stored all **757 creator objects**, including
their complete social, site and specialty data, and **336,719 item objects**.
Its attachment index contains **181,822 package filename/size records**.
Separate WCIF observations link to **50,604 distinct CurseForge URLs** and
**104,886 distinct TSR URLs**, with other platforms retained as well.
These are source links, not claims of independently fetched provider inventories.

One source discrepancy remains explicit: creator `8981` (`unidentifiedsims`)
declares 670 items, while search reports 674 and returns only 670. Reverse-order
paging returns the same identities. Coverage therefore remains 756/757 fully
qualified creators. Available metadata can feed the catalogue with that source
gap attached; the importer does not label the archive complete.

Complete objects and each source's evidence are retained separately. Strong
content hashes, attachment/fingerprint hints and filename-prefix hints have
different confidence. No installed package is renamed or edited. See the
[catalogue implementation and commands](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/tree/apex/recover-and-harden/Metadata)
for the supported jobs and remaining integration gates.

Search belongs in the existing **Filter Items…** bar immediately below the native category title, as requested in the Shoes example. Keep native filter chips and their ordinary filter-panel access alongside the editable query; do not move this into another floating window. Typing, cursor keys, selection and clearing must remain owned by the text field while it has focus. Type a recognizable item name, part of a `.package` filename or internal code; narrow by creator, CAS type and EA/CC origin. Keep ordinary native cards and swatches, a visible result count, an obvious clear action and a clear explanation when fuzzy matching corrected a term.

Arrow keys are being added for actual card navigation: Left/Right, Up/Down using the actual column count, Home/End, Page Up/Down and Enter through the native card-click route. A focus outline is distinct from the equipped selection. Input fields retain normal cursor behavior. Keyboard handling must not steal a dialog's keys, change a different Sim or equip an item merely because the focus moved.

### Native filter-pane implementation under qualification

The editable field is attached to the native category's filter pane, immediately
above its existing chips. Its clear button restores the original native feed.
The normal filter toggle and chips keep their original handlers. Enter submits
the current search intent; Escape clears it. Cursor movement and text selection
belong to the input while it has focus.

Search accepts readable/internal names and package-name terms. Optional fields
include `author:"Magic Hand"`, `type:29` and `origin:cc` or `origin:ea`.
The current native category, filters and eligibility still determine which
cards can appear. A metadata hit is resolved through the game's catalog, then
intersected with the exact current native feed. Apex does not construct a new
product from a filename or introduce another equip path. Native cards retain
their original thumbnails, swatches, selection and undo handlers.

Typing records one latest intent with a short debounce. The DLL worker performs
metadata queries; the UI resolves at most one returned resource per idle frame.
Changing the Sim, appearance, generation, category or feed invalidates old
results. Replacing the visible result list clears queued card navigation so an
old Enter cannot select a new item at the previous index. A missing metadata
broker reports an unavailable search and leaves the native cards intact.

`cas catalog-search --text 'lipstik author:"Magic Hand" origin:cc'` controls the same
field. Its acknowledgement proves the text/intent only; use subsequent status
to verify completed results. Search does not edit a Sim. The development broker
currently needs a separately started, verified metadata index; automatic
distribution/startup and the full EA/CC-library UI test remain release gaps.

The first V265 game test confirms the field's location beside the native filter
toggle, above the native chips and cards. It fails before submitting a query:
the source rows are not admitted during the initial panel transition. V266
defers that admission and checks the exact visible feed and Sim/form context.
The failed test is retained in the [scoped report](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/blob/apex/recover-and-harden/Reports/CAS_NATIVE_SEARCH_V265.json);
search completion remains unqualified until the corrected build passes.

V266 admits the 41-item native lip feed and acknowledges the exact CLI query.
Clearing restores all 41 cards. Metadata submission still fails. V267's retained
refusal identifies a transport ownership error: search sent a Sim ID where the
protocol requires its opaque channel ID. V268 corrects those two calls without
relaxing the ownership gate. It also avoids rebinding unchanged result cards.
See [the follow-up evidence](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/blob/apex/recover-and-harden/Reports/CAS_NATIVE_SEARCH_V266.json).
The matching actual query/result test remains pending.

V268 successfully submits a query but exposes a second runtime incompatibility:
the game's GFx runtime does not provide the `JSON` class. Its raw Arial input
font also renders typed letters as blocks. V269 uses the same embedded
`$TextFont` as the readable CAS labels and leaves the native caret/selection
alone during typing. The metadata worker now validates and prepares a bounded
resource-only page on its background thread. The UI reads that small page
without a JSON decoder, checks its ticket, index and pagination, then resolves
only eligible native products. The existing rich JSON endpoint remains available
to its other clients.

The V269 game capture confirms readable `lipstick`, a result count of one and
the native CC thumbnail. Both plain and typo/creator/type queries traverse two
metadata pages and resolve all 30 indexed variants into that one native card.
The actual filtered-card click and exact Undo also pass. The plain asynchronous
query completes in 1,744 ms in this run, with 3 ms spent publishing the card list;
this is not a 0–1 ms response claim. The no-match query produces zero cards,
and clearing restores the complete 41-card feed. Five search/transport tests,
including nine serialized bytecode cases, and all fifteen native targets pass.
Physical typing/editing-key coverage, larger libraries and index/broker startup
still need qualification. CLI text acknowledgement alone does not prove those
remaining behaviors.

After the filtered-card selection and Undo, a fresh complete owner export
matches all 195 compared records across the five-member household. All save
files remain unchanged. These records include internal preservation entries;
their count does not mean there are 195 playable forms. The retained
[V269 report](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/blob/apex/recover-and-harden/Reports/CAS_NATIVE_SEARCH_V269.json)
separates these actual results from the remaining release checks.

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
