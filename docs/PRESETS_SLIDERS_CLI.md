# Presets, sliders and per-occult ownership

The owner’s original `Sliders And Presets` folder is read/copy-only. Its 897
packages are installed in the one marked disposable profile, with each SHA-256
recorded in that profile’s journal. Two identical, previously installed color
packages were reused. Original source hashes and disposable save hashes were
unchanged. Candidate replacement retains these separately authorized inputs.

## Copy and inspect

From this repository, with Sims closed:

```powershell
python tools/apex_cli.py profile sliders-presets --state .work/reusable-profile-session.json --install
python tools/slider_catalog.py --mods-root 'C:\Users\Owner\Documents\Electronic Arts\The Sims 4\Mods' --game-root 'C:\Games\The Sims 4' --output .work/slider-catalog.json
```

Use a new external output filename. The catalog reads packages in place and
writes metadata only. It records full TGIs, complete decompressed resource
hashes, containing package names, face/body regions, deformation references,
and each hotspot’s direction, viewing angle, age/frame and occult filters.
Unrecognized formats remain explicitly unparsed rather than being guessed.

The actual owner/game scan has 8,370 unique preset, sculpt, modifier and hotspot
resources across 781 relevant packages, 66 resources with differing mod
definitions, and 112 resources with identical mod definitions. All scanned
modifier and hotspot layouts parsed. These are resource counts; an identical
resource does not prove an entire package is redundant. Package load order is
not inferred from filename ordering or file dates.

One merged owner package contains a modifier with instance zero. The catalog
retains it for diagnosis, the F11 editor refuses to activate it, and the preview
startup inventory skips that unusable sentinel. No source package is repaired,
removed or rewritten.

## F11 and background CLI

Start the existing memory-only preview broker with the exact external catalog:

```powershell
python tools/apex_cli.py preview start --state .work/reusable-profile-session.json --slider-catalog .work/slider-catalog.json --slider-catalog-sha256 <complete-sha256>
```

F11’s appearance slider view has a paginated EA/CC modifier library. Search by
package, region or resource key, filter conflicts and duplicate definitions,
and inspect source packages and hotspot bindings. Observed sliders also have
exact numeric entry and a configurable display range. The display range is
not a certified native deformation limit; current values are never clamped to
fit it. The existing Apply/Cancel and live-edit options also cover modifiers.

The same catalog can be queried without opening F11:

```json
{"search":"hipDip","offset":0,"limit":25,"kind":"modifier","conflicts_only":false}
```

```powershell
python tools/apex_cli.py preview sliders --state .work/reusable-profile-session.json --values .work/query.json --output .work/query-proof.json
python tools/apex_cli.py studio shape-inspect --state .work/reusable-profile-session.json --sim-id <sim-id> --form 2 --output .work/alien-sliders.json
```

An existing slider edit uses its exact field, group, ordinal, uint64 key,
observed value, history lane and complete appearance hash. Face/body and aged
face/body groups remain distinct, including duplicate keys at different
ordinals. Physique components retain the game’s observed numeric formatting.
Unrelated modifier bytes, preset sculpt references, genetic data, outfit data
and unknown fields are preserved. A selected stored form can be edited without
activating it. Apply records the complete appearance through the existing
history journal; Undo restores the prior packet.

Previously absent/zero modifiers use `studio shape-add-preview` or
`studio shape-add-live` with this exact contract:

```json
{"group":3,"value":0.375,"resource_tgi":"C5F6763E:00000000:923C24AA38E212E1","resource_sha256":"<complete-resource-sha256>","lane":"<observed-history-lane>","appearance_sha256":"<complete-appearance-sha256>"}
```

Before writing, the game’s actual resource manager must return the requested
TGI and the same resource hash. A missing resource, wrong hash, stale owner,
existing group/key, zero identifier or nonfinite amount is refused. No other
form or modifier is substituted.

## What can be independent

Different modifier IDs can be edited independently even when competing
hotspots hide their CAS gestures. Two packages defining different bytes at
the same modifier TGI share one loaded native definition. The menu shows the
competing definitions, and activation refuses a definition whose hash differs
from what the game loaded. Independent versions of that same ID require
verified cloning/remapping of the modifier and its dependent resources; that
conversion is not implemented or claimed by this catalog.

## Acceptance gates

- [x] Original remains read/copy-only; one disposable profile is reused.
- [x] All 897 source packages accounted for, with hashes and unchanged saves.
- [x] Actual package conflicts and identical definitions detected.
- [x] Modifier amounts and unknown bytes covered by mutation/Undo tests.
- [x] Previously absent modifier activation checks the actual loaded resource.
- [x] Preview startup succeeds with the real zero-ID slider bundle installed.
- [x] All 40 household appearance records matched the saved baseline after loading these packages.
- [ ] Copied presets preserved across Alien → Vampire → Alien and household reload.
- [ ] Every modded and EA modifier visually validated in every appearance owner.
- [ ] Per-definition isolation for conflicting copies of the same modifier ID.
- [ ] Ordinary phone/MCCC CAS entries and the complete household edit matrix qualified for production.

The current candidate remains a development build. Passing packet checks does
not establish visible deformation, full CAS parity or safety for the owner’s
actual save. Native CC nose-preset selection returned an unrecognized preset
index in the first pass; that failed acknowledgment is retained. The actual CC
body-preset selection succeeded in Alien full CAS. The explicit Alien-only
commit changed only its stored and active appearance; the other 38 household
appearance records stayed exact. A copied Obscurus body modifier accepted .375
in Live and survived 4,559 simulation ticks and Alien → Vampire (4,173 ticks).
Vampire → Alien then failed exact facial readback: the native setter restored
the unchanged genetic base and relocated the edited amount to the aged group.
The failed UUID and all originals are retained; that round trip has not passed.

V110 edits the same explicit base modifier in GeneticData as well as facial
attributes, preserving unrelated genes and aged groups. New modifiers insert
within their protobuf group; V108 had correct values but failed byte readback
because the native setter reordered a modifier appended after aged fields.
Mutation tests cover the corrected ordering. Actual activation, visible
deformation and successful switching/reload still require runtime proof.
