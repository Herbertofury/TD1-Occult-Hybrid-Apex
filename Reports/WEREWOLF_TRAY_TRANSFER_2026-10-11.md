# Werewolf styles, native Tray sources and selective cross-form paste

This extends the independent appearance room. Full CAS/MCCC/Tray parity,
controlled save/reload, universal fitting and the final completion gate stay
open. The owner's original profile is strictly read/copy only.

## Implemented behavior

- New occult generation keeps the EA-generated alternate appearance. The
  previous Human-payload overwrite erased the Werewolf head/body/morph/pelt.
  Native generator coat sharing with an existing Human owner is restored
  separately, without replacing the new occult's defaults.
- Existing damaged Werewolf looks have an explicit EA-default try-on. Before
  invoking the inspected native generator, a durable preimage retains every
  original owner and the map. The temporary generated owner is detached, and
  the original map/owners are restored and verified before returning a preview.
- Human/CC Werewolf style is explicit and defaults off. EA and Human/CC styles
  retain separate edits across toggles; the independent renderer chooses the
  matching visual form without changing gameplay membership.
- Bounded, immutable appearance clipboards retain explicit Sim/Tray provenance.
  Any represented source form may target a different existing destination form.
  Whole appearance/wardrobe, one numbered outfit, skin details, tattoos and
  individually selected fields/categories share the normal try-on/Apply/Undo
  journal. Sim identity, household, traits and progression are excluded.
- Outfit IDs/categories remain owned by the destination. Unselected category
  rows and all their parallel arrays stay intact. A selected empty source
  category removes only that category. Missing categories are inserted in
  native BodyType order; existing category positions remain stable.
- Whole-appearance previews expose a separate detached outfit inventory, so
  newly generated IDs can be displayed before Apply. The real equipped/accepted
  inventory is retained separately and stale preview identities are refused.
- Native v1/v2 household envelopes are bounded and checked before projection
  through the separately licensed worker's pinned EA protobuf schemas. Exact
  original Sim bytes, household/footer/unknown bytes and complete item groups
  remain retained. Shared fields are reported where the native stored-occult
  Tray schema lacks its own value.
- F11's Tray viewer separates source and destination, switches represented
  source forms/outfits and copies the displayed form through bounded owner
  requests. No new game Sim is created and no game focus is required. Complete
  existing Tray groups exchange through hashed bundles; import refuses differing
  existing filenames and only writes in the marked disposable profile.

Usage and exact CLI/selection fields: [appearance transfer guide](../docs/APPEARANCE_TRANSFER.md).

## Observed development evidence

V51 (`2026-10-11-werewolf-tray-transfer-v51`) passed 1,712 Python tests,
five native CTest targets, 76 Python 3.7 module compilation and independent Rust
verification of 206 package resources. Its candidate ZIP SHA-256 is
`f849a28adb44ec1e819c5253a6a09db25f2f3aa41f1d0331bcb827a0af6d5057`.

The actual disposable native household was read without game contact or asset
exports: one existing Tray Sim, represented Vampire and Human owners, twelve
appearance fields per owner. Household SHA-256:
`33f451c7a30e77d18f3f76ce46f3d8dc9163a14e01d2784613ee329ed9fdecd5`.

Actual V51 EA Werewolf generation preserved every original owner before
returning its try-on. Apply changed only the inactive Werewolf while the real
Alien remained active. The independent scene displayed the proper EA wolf
head/body; actual background pixels were inspected. After unpause, Undo restored
every complete captured stored/active appearance. Exact receipts remain private
and their hashes are appended after final reconciliation below.

The first Alien → Human skin-detail paste failed complete readback because the
new category row was appended after later categories. It was rejected and
rolled back; complete Sim snapshots before/failure match. This is a retained
failure, not an accepted paste proof. V51's CLI Tray display also hit the old
Source host-operation whitelist before entering the native preview function;
no source Sim was imported. Both defects are corrected in the subsequent
candidate and require new runtime proof.

V52/V53 full-suite runs were interrupted for discovered fixes and are not
certified complete runs. V54 passed 1,715 Python tests and used the verified
five-target native build. Its candidate ZIP SHA-256 is
`f648abff02543cdffedf5746d40394380b4405f0c42ef5260d26d50af9e6af88`.

Actual V54 Alien → Human and Vampire → Mermaid transfers of skin tone plus
forehead skin-detail category 38 pass complete readback after unpause. Only
those selected fields on the destination change; the active Alien and every
other stored owner remain exact. Undo restores every captured appearance.
Detached EA Werewolf wardrobes, including newly generated outfit IDs, render
before Apply; preparation, rendering and Cancel leave the complete Sim equal.
Tray Human/Vampire source switching also leaves the real Sim unchanged. Native
five-file Tray group export/import verifies all bytes and skips five identical
existing files without overwriting any.

V54's displayed-Tray clipboard final reply failed because its transport-only
context had no history reader. Complete before/failure Sim snapshots match.
The CLI independently identified the same terminal error; neither failure is
accepted copy proof. V55 gives only the final upload step a real history context,
tests the complete begin/chunk/finish dispatch, and exposes the native copy's
terminal result to CLI status. Its fresh runtime acceptance is recorded below.

Private receipt hashes (save/CC contents are not published):

| Scoped receipt | SHA-256 |
| --- | --- |
| V51 EA Werewolf Apply/unpause/Undo | `c032315219f1269f59c8b42cb888a29663421e6954d666328fdeb604dfa1479a` |
| V51 inactive Human/CC style and separate preview | `f30080111c2c3ef45c38abed69d3e6c9a241493caed820f96e1d0bb683a38dcc` |
| V51 skin-tone-only cross-form paste | `0da1f497d55d6f8aa77ad2927fbfea625d0951ca622d8137f0c1afbcc559236c` |
| V51 rejected category-order paste, rolled back | `6c5a96b79b42821b183c88fef6256886231aa6f0bfc0164c690f95dd4725ff82` |
| V51 normal unsaved closure, saves unchanged | `e0706f0d74c77cb54640432162ed6cbaf21fcf3826b5c89720bbc53688165de2` |
| V54 cross-form skin/detail paste after unpause/Undo | `c195c5112f127eb92b45769e13ad7cd53a5443f865d79dbb938dcd7b7afd41b6` |
| V54 detached EA wardrobe try-on/Cancel | `438a30be7502b69cc7ac4bc4de6cdac6fbf6283d57def9fa95b3a3516badebb8` |
| V54 independent Tray Human/Vampire switching | `2f24bcba378304f5cfc567285d0c609e13e43e43cf2f496be9fe7274d3ee0bba` |
| V54 failed native Tray clipboard final reply | `9759dd34208693d83716f53cd57d2afbbe0b041ff48442b2c6727b4b847e904b` |
| V54 CLI diagnostic of the same final-step bug | `d68934a748b95103cb6d9963b52db1a1b3620cac179f1f4610ca64a5f5f150b1` |
| V54 native Tray group export | `d94d14b6dc1a58f549387d130a33d9639aaaa6ba46e725698d5321435d82a858` |
| V54 identical native Tray group import | `72eff3aab8a859e3657c29881f8653a17738f7bc1c2bc84fb5474062128944a5` |

V55's displayed-Tray clipboard copy completed through the corrected final
owner request without changing the real Sim. A Vampire source's single outfit
was pasted onto Mermaid; a tattoo-category selection was pasted onto Human.
Both retained unrelated owners and destination outfit identities after actual
unpaused simulation ticks, and Undo restored the full captured baseline.
The tattoo probe covers its exact represented category rows, not every tattoo
layer or an arbitrary custom-tattoo blob.

Full appearance/all-wardrobe paste was rejected on outfit and voice-pitch
readback and fully rolled back. The worker's binary32 voice projection has
since been corrected; the full-wardrobe mismatch still needs runtime diagnosis.

| Additional scoped receipt | SHA-256 |
| --- | --- |
| V55 native displayed-Tray clipboard, no Sim write | `cb115d543bec2fefe74bfbe527cd7529ade7525ca6c3b9c10350b4fa5a6ebde8` |
| V55 one-outfit and tattoo-category Apply/unpause/Undo | `b0f8d6e4b5f929a168875263c8fed97958fdfcf6912a4eb16bdfe97cf0c46e6d` |
| V55 rejected full-appearance paste, complete rollback | `164c32b6a6c282afaab6e8e61e15d649e315dc6d52992217c18a9c2da69238e8` |

## Open acceptance work

- Full-appearance/all-wardrobe paste and broader tattoo-layer combinations
  remain acceptance work; the scoped successful copies above do not close them.
- Exact Human/CC Werewolf visual behavior in the actual Live engine and every
  animation, fresh full CAS/MCCC editing, and controlled save/reload.
- Creating a new native Library/Tray item from the current Live Sim. Existing
  complete Tray group exchange is implemented; it is not that export operation.
- Complete EA shader/material matching, all CAS panels/presets/traits/voices,
  universal CC fitting, every thumbnail/swatch family, portable helper startup,
  thousands-of-Sims performance, palette/texture conversion and a headless engine.

No failed receipt is promoted by fixture success, an independent scene or a
later installation. Normal save/backup files and the protected original remain
separate explicit safety evidence.

## CAS families, native gallery and generated images

The current candidate is `2026-10-11-cas-swatches-tray-v58`, ZIP SHA-256
`6f1e639cbc8637299e32f090f5e2739ba217ca443dcd22cf8864de6bc59256a2`.
It contains 76 verified Python 3.7 modules and seven packages with 206 resources
independently extracted and hash-checked by the Rust implementation.

The installed read-only index covers 5,004 packages: 539,005 container CASPs,
195,895 distinct variants and 54,334 source/fitting-scoped native OutfitID
families. Unknown family IDs remain separate. Exact source and conflicting
resource variants are retained; no effective game load-order winner is invented.

Actual V58 F11 acceptance verified one item card for a 30-swatch CC lipstick,
then used the typed CLI to inspect a different swatch. Its exact TGI, resource
hash and ARGB colors match the host's selected native CASP. The absent item image
rendered from actual resources to a separate 256×256 GPU target with pixel hash
`124bab4334c48a0aa7740644b033d567ff306851430e432b2486b1ea4a2dae55`.
The visible character scene stayed unchanged; only image pixels are retained in
the native RAM cache. Actual background pixels were inspected.

The native Tray gallery displayed the test household's decoded portrait, name
and creator, selected its source Sim and rendered its represented Vampire owner.
Source and destination identities stay separate. The complete stored/active
appearance snapshot before and after all these operations is equal. No Apply,
Save, Sim creation, asset export, OS cursor movement or foreground handoff was
required. Gallery browse supports household/lot/room names, creators, descriptions
and images; lot/room 3D reconstruction remains open.

Retained failures identified the worker's group-zero CASP map and the native
gallery's rejection of empty descriptions. Both were corrected before the
successful run. A CLI library query requested before preview load failed to
produce a page; the host renderer now re-arms its exact read-only
filters. Failed receipts are retained, and no game command was blindly replayed.

The V56 full Python suite passed 1,723 tests. Later focused CLI, sidecar and
epoch checks passed 7, 12 and 23 tests; final native CTest passed all five targets
and the real host page/inspection/gallery replay passed 109 native checks. The
corrected worker self-test covers modern deformation, binary32 Tray voice data
and detached outfit row/parallel-array preservation. Exact-head CI is separate.

| Additional private evidence | SHA-256 |
| --- | --- |
| Corrected V58 F11 swatches, generated thumbnail and native Tray source view; all appearances unchanged | `fb6c8344dc2949d309b8eb16968bb47cf5beec212ab7ba8b84210c7ee21c9c92` |
| Actual F11 native gallery pixels | `c2074909c53ccac699b8a63991f7e4e8e26fdc997f515080000f6bc10e03aa50` |
| Actual generated-item card pixels | `483da623a5eca0f36eae78a0d85a74d5fe56253cac7abd2b6c86fa20e6d8bf3a` |
| Rejected initial detached CASP lookup; Sim unchanged | `71c222fe76ca82ae3556b0159da31a02b5e5978549edc06a202a07f8e0ea4a44` |
| Successful thumbnail, rejected empty-description gallery; Sim unchanged | `4642181596b3e7f08e6e26754b3125ec5337ffaf9e4980af55a80ff76ab8dcae` |
| Abandoned older-generation CLI library query; Sim unchanged | `f6c3ab165056346a37af2b56db8ee7aba9fac88dd6b582138caec882ae44754c` |
| Normal unsaved closure before V58; disposable saves/backups unchanged | `bad63b503e52d3034683196758ae588ea9d1d7237f68070dfcaf1b21dff02340` |

Universal content fitting, all EA materials/thumbnails, native current-Sim Tray
creation, full Gallery/Tray Importer parity and all earlier broad occult/CAS/MCCC
acceptance gates remain open. The protected original was not modified.
