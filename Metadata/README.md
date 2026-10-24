# Apex local content catalogue

The catalogue separates explicit indexing and provider downloads from CAS search.
`apex-catalog.exe` performs a requested job and exits. The DLL links the Rust
library with **default features disabled**: no HTTP client, credentials, CLI,
provider downloader, watcher or scheduled service is present in that library.
SQLite/FTS reads run on the existing native metadata worker. Typing retains only
the latest pending query. Source packages are opened read-only during indexing;
search uses the resulting immutable, SHA-256-pinned snapshot.

## Search examples

- `lipstick folder:"Makeup" author:"Magic Hand"`
- `folder:Makepu` — one-typo folder correction, with actual indexed paths.
- `folder:"Makeup/Lips" origin:cc type:29`
- `package:*lipstick*.package -gloss`
- `name:"Cherry Lipstick"` or `code:yfMakeup*`
- `added:7d sort:newest` or `sort:modified`
- `sim:"Bella Goth"` or `household:"Goth Family"` — equipped CC across captured forms/outfits.
- `sim:"Bella Goth" form:Alien outfit:everyday/2` — second Everyday outfit in that form.
- `household:"Goth Family" author:"Magic Hand" folder:Makeup`
- `sim-id:123456789` / `household-id:987654321` — distinguish matching names precisely.

Plain words are prefix searches; quoted phrases stay together. `*` and `?`
are supported by the package/name/code filters. An exact folder wins over a
similarly named sibling (`Makeup` does not select `Makeup2`); its descendants
are included. A prefix can identify several existing folders. Folder suggestions
come from materialized metadata, without traversing directories while typing.
Unsupported filters and incomplete quoted values produce explicit errors.
The existing native category, age/species restrictions and other filters still
control which actual cards may appear. Searching cannot equip a part.

**Recently added** means content first observed by a successful local indexing
history, not an inferred original installation date. The first indexing pass is
a baseline and is excluded from `added:`. Identical content moved to another
folder retains its history. File modification time is separate. A refreshed
snapshot is necessary to see packages installed since the previous explicit scan.

## Provider archive and evidence

The full WCIF import preserves each returned creator/item object, including
unknown fields, aliases, social links, specialties, styles, source details,
attachments and timestamps. Items are keyed by the provider's stable ID;
creator associations are checked against `creatorId`. Ordered page receipts
reference the stored objects rather than duplicating every item. Images,
packages, attachment URLs and social websites are not downloaded by that job.

Separate indexed observations retain links to CurseForge, TSR, Patreon,
SimFileShare, Tumblr and other sites. A WCIF link to TSR remains a WCIF
observation, rather than pretending to be an independent TSR verification.
Explicit `source-refresh` jobs can retain public JSON-LD/OpenGraph claims and
HTTP outcomes independently. SimsFinds and TS4Rebels are supported provider
identities; no creator inventory is invented when their public data is absent.

Installed S4MM SQLite caches are read-only inputs. Only public file/project
metadata is imported; account storage, session files and its embedded developer
API key are not accessed. Official CurseForge discovery requires an explicitly
configured user API key. PlumbDex normalized records can be imported; its live
sync protocol is not yet implemented.

Exact SHA-256 evidence, attachment filename/size hints, 32-bit fingerprint hints
and creator-prefix hints remain distinguishable. Contradictory attribution is
retained for review. Multiple provider records and complete WCIF profiles stay
available; enrichment does not rename packages or overwrite their internal data.

The standalone tool includes a 757-creator WCIF profile seed (October 21, 2026),
with every returned profile field retained. Seeding is local and requires no
network. The much larger item archive stays separate and is fetched only by an
explicit `wcif-import` job; it is not duplicated into every release or Sim.

## Explicit jobs

Build with `cargo build --release --locked`. The checked-in lockfile pins the
dependencies. The current CLI enriches an existing Apex schema-3..7 catalogue;
standalone raw DBPF scanning and a player-facing indexing wizard remain open.

```powershell
apex-catalog wcif-import --output wcif.sqlite --workers 2
apex-catalog wcif-index --database wcif.sqlite
apex-catalog source-index --database wcif.sqlite
apex-catalog source-refresh --database wcif.sqlite --provider tsr --limit 20
```

Re-running `wcif-import` at the same path resumes incomplete creators using
validated page checkpoints. It preserves completed creators. It is a resume,
not a fresh remote refresh; use a fresh archive for a new complete source snapshot.
An inconsistent provider total leaves the archive's coverage **incomplete**.
Indexing the available validated objects retains that gap in its result and
the enriched snapshot. It does not turn a source discrepancy into a pass.

```powershell
apex-catalog sync --index existing.sqlite --expected-sha256 INPUT_SHA256 `
  --output refreshed.sqlite --cache history.sqlite `
  --wcif-database wcif.sqlite --s4mm "PATH\s4mm.sqlite" `
  --publish-config "PATH\Native\apex-catalog.snapshot.json"
```

Use a fresh output snapshot. Replacing an existing native config also requires
its exact `--previous-config-sha256`; an intervening change is rejected. The
config stores index path/digest, `network_at_runtime:false`, and an optional
save-scoped equipped-reference path/digest.
`cas catalog-companion --action refresh-search` explicitly retires the cached
native index and repeats the current query against the new pin. It never
restarts the game or writes an appearance.

The HTTP-enabled executable and HTTP-free library are separate feature builds.
The rest of F11 still has its existing preview/asset infrastructure; removing
the CAS search broker does not establish independence of every F11 feature.

## Qualification

### Equipped Sim/household references

Equipped searches default to **CC**; `origin:ea` explicitly includes resolvable
EA items. Multiple matching Sims contribute a union of item identities, with
one result per identity (or swatch family when grouping is enabled). Sim,
household, form and outfit predicates must match the same equipped row.
Outfit numbers are one-based: `outfit:everyday/2`, `outfit:formal/1`, or numeric
category `outfit:0/2`. A category without a number includes all existing slots.
A search never selects, transforms or equips another Sim.

The separate sidecar stores labels and references, without meshes, images,
textures, packages, restore payloads or complete Sim exports. Explicit capture
uses the existing validated native owner pages without activating inactive
forms or generating absent outfits. Every graph generation and the complete
household roster must remain unchanged through the final check. Valid empty
native outfits with ID zero are retained. Partial/stale jobs publish no capture.
The CLI projects detached metadata in memory; complete DTOs are never written
to the capture file. Its disk output contains compact references only.

```powershell
python tools/apex_cli.py catalog-usage --state SESSION.json `
  --save-guid SAVE_GUID --household-id HOUSEHOLD_ID `
  --catalog-sha256 INDEX_SHA256 --output equipped-capture.json
apex-catalog.exe usage-import --index catalogue.sqlite `
  --expected-sha256 INDEX_SHA256 --capture equipped-capture.json `
  --output equipped-next.sqlite --publish-config PATH\apex-catalog.snapshot.json
```

The native capture CLI currently requires the marked disposable profile. It
uses **committed** CAS graphs and persisted names; a pending try-on or unsaved
rename is not included. Refresh after committing edits. Automatic capture on
production CAS/Live/Tray changes and an integrated refresh button remain
unfinished. No hidden service or watcher is installed.
Track the generated config in that profile with `apex_cli.py profile
catalog-snapshot --state SESSION.json --source CONFIG.json`. Replacing it
requires `--expected-previous-sha256` of the tracked config. Other unknown or
changed mod files still block launch/control. Candidate updates preserve this
explicit config; changing metadata requires no additional game reload.

`usage-import --previous equipped.sqlite --previous-sha256 SHA256` retains other
captured households in the same save while atomically replacing the complete
refreshed household. Renames, removed members and moved Sims update their
associations. Older captures cannot replace newer ones. Publish at a fresh path;
existing snapshots remain immutable. Import/search never scans source packages,
changes a Sim or modifies a save.

The DLL binds references to the exact catalogue digest and save GUID. Native
CAS rejects another CAS session's capture; F11 checks its inspected Sim's save
lane. Item `used_by` metadata identifies Sim/household names and IDs, exact form
owner, outfit category/number, layer and capture time. F11 card tooltips show
these uses; an eight-row sample is marked incomplete when more exist. Full
references remain indexed. Resource-ID collisions are reported as ambiguous,
never attributed to an arbitrary package. A new catalogue digest requires
rebuilding references. Per-capture unresolved/ambiguous counts remain visible.

Actual retained five-member native captures resolve four distinct CC resources
in the 539,005-row installed catalogue. The sidecar is 90,112 bytes; measured
query work is 0.368–0.783 ms after opening the index. These worker measurements
do not establish end-to-end CAS latency. Most EA references in this older
catalogue have competing source entries and remain unqualified for equipped
attribution until effective-resource hashes are captured. Actual-game use of
the capture command and native Sim/household/type/form/outfit searches now
passes on the five-member household. Names remain readable and the selected
Sim and save files remain unchanged. Native CAS retains its current category
feed: two CC references used by other members are indexed but their swatches
do not yet map to a visible parent card. That mapping is an open defect;
unrestricted F11 browsing remains a separate actual-game qualification gate.

V272 subsequently qualifies F11 actor search in the running game: household
name returns three CC families, Sim name two, an exact second-member ID one,
and an unknown name zero. Compact HTTP encoding fixes the 5.83 MB pretty-print
overflow while retaining the complete 3.19 MB document and the 4 MB native
bound. All twenty save/backup files remain unchanged.

V273 then qualifies native CAS swatch mapping: the two worn eyelash variants
used by other members resolve to one actual eligible Hollywood Eyelashes card.
The game's color family is intersected with the current native feed, requiring
one unambiguous parent; detached IDs are cached for sibling swatches. Clearing
restores all five original cards. The compact capture's transient DTO pages
also support a complete 195-record field comparison without writing full DTO
files or assets; all fields and all twenty save/backup files are unchanged.
Automatic production refresh and F11 saved/favorite/recent views remain open
qualification gates. See `Reports/CAS_ACTOR_SEARCH_V273.json` for exact scope.

V271 also exposes a direct CAS-exit service failure after browsing body hair.
The actual EA checkmark, activated once through window-addressed background
input, returns to Live. All forty appearances and 155 named looks are retained,
with every save/backup unchanged. The pending household journal must still be
completed through the normal checked review path before Studio can edit. Do
not bypass that guard or treat the failed direct-service return as a pass.

### Other catalogue checks

An explicit metadata `sync` also materializes category/origin-consistent swatch
families with indexed ordering. Existing schema-7 indexes can use
`apex-catalog.exe optimize --index OLD --expected-sha256 SHA --output NEW`.
This prepares catalogue metadata once; source packages are not opened. Native
unfiltered grouped pages use these small lookups and fetch only the requested
cards' full metadata. Queries with text, author, folder, usage or added filters
retain the general matching path so filtering cannot pick an unrelated swatch.
The real 60-card EA Hair page falls from 1,314.656 ms to 2.024 ms of query work,
with the same 1,423 families and identical item identities/order. Source index
bytes remain unchanged. The optimized catalogue receives a new digest, so its
equipped sidecar must be rebound through a fresh explicit import.

Rust tests cover exact/prefix/typo folders, descendants versus similar siblings,
Unicode and Windows separators, combined filters, wildcard escaping, quoted
phrases, exclusions, baseline dates, moved content, changed pins, streaming
fingerprints, conflicting evidence, source-domain spoofing and structured data.
Native tests cover exact query/page/context ownership and percent-encoded
folder suggestions. Actual CAS, whole-library scale and complete donor feature
parity remain separate qualification gates.
