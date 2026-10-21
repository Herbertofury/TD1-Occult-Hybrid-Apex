[← Apex](Home) · [How it works](How-Apex-Works) · [Dynamic CAS comparison](Dynamic-CAS-Companion-Merge)

# ⌕ CAS, content and fast search
### Find the item you recognize. Keep the identity you can verify.

> **Development reference · October 21, 2026**<br>
> The metadata backend, typo planning and native background transport are implemented. A schema-5 real-CC lookup through the native worker also passed: five packages, 62 CASPs and five item families; typo + creator + type + CC filtering returned the correct lipstick package with 30 grouped swatches. The new native CAS search presentation and its real card-selection proof remain unfinished. Do not interpret this design as a shipped search bar.

## The intended workspace

Search belongs in CAS, beside the native catalog. Type a recognizable item name, part of a `.package` filename or internal code; narrow by creator, CAS type and EA/CC origin. Keep ordinary native cards and swatches, a visible result count, an obvious clear action and a clear explanation when fuzzy matching corrected a term.

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

The candidate package and DLL are built. Physical keys, scrolling, Enter,
partial rows, equipped items, text fields and modal isolation still require
actual-game qualification; fixture passes alone do not close that gate.

The full regression passed 2,748 tests before the final keyboard queue/readback and asset-lock separation edits. Subsequent focused suites passed 128 cases; fourteen native test targets passed separately. Actual-game keyboard qualification remains open.

## Remaining proof

- [ ] Complete and visually qualify the native CAS search bar and native result cards.
- [ ] Test fuzzy, creator, type, EA/CC and filename searches against copied real CC.
- [ ] Resolve exact native resource provenance before claiming a package is the active winner.
- [ ] Confirm keyboard navigation, focus, scrolling, Enter and text-field/modal isolation.
- [ ] Verify changing members/forms during a search cannot publish or apply stale results.
- [ ] Add incremental invalidation for added/changed/deleted packages without full per-query rescans.
- [ ] Compare cold startup, memory use, tail frame times and large-category responsiveness.

[Follow implementation and evidence in PR #8](https://github.com/Herbertofury/TD1-Occult-Hybrid-Apex/pull/8). The preservation failures documented in [How Apex Works](How-Apex-Works) remain release blockers independently of search.
