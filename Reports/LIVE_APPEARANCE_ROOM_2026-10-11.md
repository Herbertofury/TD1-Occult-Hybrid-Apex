# Independent F11 appearance room: October 11 development evidence

This is a development candidate, not completion of the full CAS, MCCC, Tray,
hybrid persistence or headless engine gates. The owner's original profile is
read/copy only. All game checks use the single existing disposable profile;
ordinary CLI exits leave its save and backup files unchanged.

## Built implementation

- A separate native D3D11 character viewport displays actual assembled EA/CC
  meshes, textures, rig and animation data. It does not follow or rotate the
  Live Sim. Explicit stored-form/outfit selection does not activate that form.
- Perspective/orthographic camera, Blender-style orbit/pan/zoom, roll, front/
  back/side/top/body/face views, animation controls and exposure operate on the
  preview. Face framing uses the assembled rig's head bone.
- Balanced, character, catalog and custom layouts share an adjustable viewport
  and two to eight virtualized catalog columns, optional sidebar and thumbnails.
  The CLI controls layout, columns, gender, filters and workspace tabs without
  mouse input. Filters expose exact category IDs, origin, name mode, creator
  hints, favorites/recent and stable pagination.
- The shared Apply immediately checkbox defaults off. Try-on prepares the
  complete appearance for the independent preview; Apply/Discard and journal
  Undo use the same canonical Sim/form/outfit ownership. A pending try-on blocks
  changing its form, outfit or application mode.
- Observed face/body/aged morph fields and physique values are inspectable and
  editable through typed stale-state-checked requests. Resource names/provenance
  are shown where available; unknown modifier identities remain visible.
- Thumbnail data is bound to the original full TGI, CASP hash, package hash,
  immutable catalog snapshot and requested gender before GPU upload. Browsing
  does not copy whole packages. Studio opens a fresh editable package copy.
- The separate GPL-3.0 SimRipper-based assembler reads installed resources in
  place and returns memory-only scenes. The host scene cache is bounded at
  128 MiB, the managed assembler heap at 2 GiB, and UI images at a bounded page.
  Its pinned upstream sources, adapters, provenance and corresponding-source
  build archive are described in `PreviewWorker/README.md`.

## Bugs found and corrected

The V47 actual try-on changed the rendered scene while leaving the Sim intact,
but Live Apply was undone by history capture. The inspected game serializer
calls `_set_fit_fat`, projecting shared gameplay fitness onto the active form.
History readback therefore reset the field it was meant to verify. V48 scopes
that recalculation suppression to the exact Sim and thread during history/
preview reads; normal saves and other Sims continue calling the native method.
Actual V48 testing caught MCCC's variadic injection wrapper, which a strictly
unary signature check rejected before mutation. V49 validates the actual
serializer call by binding its arguments without calling it, and delegates
ordinary calls through the original wrapper.

Journal acceptance now captures the full native record once, verifies the
accepted appearance again after capture, and rolls back a detected mutation.
Shape-only Apply restores only differing fields, avoiding an unnecessary outfit
reload that could alter unrelated genetics. Visual resends are inside the
checked operation and precede its accepted bank update.

V49 Live Apply retained the edited shape through Alien → Vampire → Alien and
unpaused progression, but Undo only restored the active Sim: the distinct
stored Alien wrapper retained the edit. V50 synchronizes the requested changed
fields to that stored current-form owner during Apply/Undo, preserves all its
unrelated fields, validates both owners after visual refresh, and rolls both
back on rejection. Separate-owner fixtures cover Undo and setter/resend failure.

Windows allowed the old and new catalog helpers to bind the same endpoint with
`SO_REUSEADDR`; a stale helper intermittently rejected the new query schema.
The catalog and preview servers now use exclusive Windows loopback listeners.
Socket tests prove that a second/legacy listener cannot shadow the endpoint.

EA's permission dialog could also be minimized. The launcher now restores a
freshly verified candidate without activation, then rechecks the actual pixels,
account launch context and exact OK target before acknowledgement. V47, V48
and V49/V50 launches acknowledged that EA dialog and observed the game process.
The Windows UAC secure desktop remains an ordinary OS approval boundary.

## Frozen build checks

V50 epoch: `2026-10-11-live-appearance-room-v50`.

Candidate ZIP SHA-256:
`d4b55017b185c8b449d1f78ef363fb82564551ca6512443d5bbaf7cc66c6817f`.

- 1,688 Python tests pass with the source epoch unchanged during the run.
- Five native CTest targets pass, including actual D3D11 preview and image
  upload checks. Native code is unchanged between V48 and V50.
- The candidate compiles 74 Python 3.7 modules, contains seven packages, and
  passes independent Rust verification of 206 package resources.
- The worker self-test covers eight modern DMAP cases, aged face/body modifier
  routing and refusal of an empty outfit rather than borrowing another form.

## Catalog measurement

The fresh complete index reads 5,004 explicit installed EA/disposable-mod
packages in 185.456 seconds, yielding 539,005 CASP container records with zero
source errors. SHA-256:
`0963494ce730b1ffd8a83b96b96b0e66d6e9d7006495fc09ee369eddb526821c`.
The 113 previously refused 96-byte empty files are valid DBPF 2.1 containers;
only an exactly empty header/extent is accepted now.

These are container records, including duplicate providers, historical patch
versions and swatches, not 539,005 distinct compatible visible items. The scan
covers installed EA data and the active private CC sample; it does not claim
to index the owner's protected full mod collection. Effective load precedence,
catalog deduplication and swatch grouping remain separate acceptance work.

## Remaining acceptance work

- Complete EA material/shader/skin-layer matching; the preview is currently an
  independent approximation of game lighting/materials.
- Global EA thumbnail providers/cache fallback, swatch families, every preset,
  voice/trait controls, every CAS panel and unrestricted compatibility/fitting.
- A portable, automatically started helper installation; the candidate mod ZIP
  alone does not install the development host/assembler services.
- New candidate full CAS and MCCC alternate edits, every-category isolation,
  controlled same-script save/reload and raw load-boundary genetics failures.
- Thousands-of-Sims memory/performance acceptance, complete MCCC/Tray parity,
  palettes/texture conversion, and an actual headless Sims engine.

Runtime leaves are appended only after observing their complete result. Prior
failed receipts remain failures; fixture or preview success is not substituted
for Live/CAS/save persistence proof.

## Accepted V50 runtime leaves

The installed V50 script was exercised in the original disposable household,
with the same existing Sim and all seven stored owners. No new Sim was created,
no game focus was required, and no save command was submitted.

| Leaf | Actual result | Private receipt SHA-256 |
| --- | --- | --- |
| Try-on, Discard, immediate shape Apply, unpaused Alien → Vampire → Alien and Undo | Independent scene changes during try-on; the native Sim stays unchanged until Apply. Component 1 retains `0.120` after actual simulation progression and both form switches. Undo restores the active Sim and all seven complete captured appearances exactly. | `496c14559bebe3c792906a23ebb4bc8a2a737abd65d9255d6452460c95917778` |
| Inactive Werewolf shape edit/Undo while Alien stays active | Only the stored Werewolf physique changes to the requested `0.180`; it survives unpause. The distinct active Alien and six other stored forms remain unchanged. Undo restores every captured appearance. | `5954c210f3ee3854be1f0008a5b8ecb20e3f53a95d2c76f2ac31f2302476450e` |
| CLI room layout and actual CC image column | Fresh Alien 3D scene, custom 44% viewport/four-column layout, exact lipstick filter and real embedded female CAS image uploaded to the native GPU column. Complete before/after Sim appearance snapshots match. | `cca77f2b3f82dfc0f9b042fa40d2eeac9b47512255852a5a46c84339943163c0` |
| Compatible CC Live color Apply and Undo | The equipped lipstick hue changes from zero to the requested `0.1`, read back as its exact Q14 value `0.0999755859375` after unpause. Undo restores all seven stored/distinct active appearances. This verifies packed runtime values, not a new visible Live close-up or complete shader-equivalence claim. | `f2b1a0a1627910ffe785999c1e840d3b77efe97de854c8d32056df4fe5804596` |

The exact private CC image is the base `[Magic Hand] Lipstick N91` CASP
thumbnail. Other swatches without their own embedded image remain unresolved;
one image does not prove every CC/EA thumbnail. The image-column screenshot was
captured from the actual background game buffer and inspected visually.

The disposable normal save still hashes to
`941f01d89a374b82c557e3eab368b69197edd06f3dc25d849cc91f2ef96af3f0`.
These are current Live/preview/Undo proofs, not a new controlled save/reload
certificate or a complete fresh full-CAS/MCCC alternate-edit matrix.
