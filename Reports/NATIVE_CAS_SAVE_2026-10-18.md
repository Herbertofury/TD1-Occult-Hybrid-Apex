# Native occult selection, Fairy edit and household save checkpoint

Development evidence only. Native Link/Unlink/Copy, complete category/member
coverage, special-state gameplay and household Tray/Gallery remain release
gates. This checkpoint does not authorize use in the owner's actual save.

## Verified behavior

- The real full-CAS occult popup selects Alien -> Vampire -> Alien through the
  existing independent owners. All six memberships remain present (mask 127),
  and the native button remains visible after both redraws. The molecule's
  presentation mask changes; native Sim membership does not.
- Human uses the installed EA Human artwork. The third member's actual look
  is intact; no appearance reset was applied for its stale portrait.
- The fourth member's actual Fairy receives native purple wing style/color
  473791. The initial wing paint data was empty; stock-card selection supplies
  paint layers. The purple result remains visibly coloured after Fairy ->
  Alien -> Fairy. Automatic empty-paint repair and the separate semantic wing
  API remain unqualified.
- A complete export compares all 195 captured owners. Only the fourth member's
  actual Fairy changes, in outfit/genetic/pelt fields. Decoding the outfit
  protobuf finds only wing body type 114 changed in category 9, index 0; the
  other outfits, parts and fields remain unchanged.
- All five household receiver commits succeed. All forty native Live
  appearances match after 989 simulation ticks. The fourth member's settled
  Alien -> Vampire -> Alien -> Fairy cycle preserves the household, named
  forms and outfit counts. Each transition advances the simulation.
- Normal save writes Slot 2 and certifies all five independent named-form
  documents. V200 cold loading retains all forty native appearances and
  reopens all five named documents before and after 946 simulation ticks.
  Save file and seal ledger remain unchanged; Live is paused again.

V199 correctly refused named metadata written by the unlisted V198 source.
V200 adds only the exact audited schema-compatible V198 script hash to the
metadata predecessor list. It grants no native appearance restoration
authority. Unknown sources and native restoration across this boundary remain
refused and have regression coverage.

## Candidate and validation

- Candidate: `2026-10-18-qualified-fairy-save-v200`.
- Bundle SHA-256: `4beb6b66cedbfbd3232182ad0e3389a5e6fe8d226fed61951b00d8450d24d0a1`.
- Script SHA-256: `37eeaa1ad812f9209d746e63a8cb1baba7b6cd60b668db3d8a597d47150f2d14`.
- DLL SHA-256: `a16f8812d7bfe136152946ab7dd80646955661091d166e3371f4afefd3490876`.
- Saved Slot 2 SHA-256: `93c0051a56fe96c3600efa5d93cbe40ae289dcc7263e5987e0d892199b1b5528`.
- Build: 103 Python 3.7 modules, seven packages, 208 resources independently
  verified by the Foundry Rust CLI.
- V200 complete regression: 2,616 passing tests in 776.817 seconds. Its focused
  save/upgrade/return run passes 92 tests. Twelve native CTest cases pass.
- Normal background exit and EA launch require no user click this checkpoint.
  The installed native pointer separates move/down/up by 120/100 ms. Actual
  CAS-grid selection remains a separate runtime gate.

The DLL's owner-memory diagnostics are enabled for this disposable test.
Production performance and diagnostic-off behavior are not qualified here.

## Retained private evidence

Raw receipts, complete Sim bytes and game captures remain under ignored
`.work/`; they are not published. Hashes identify the exact local proofs:

- `native-cas-v198-native-popup-cycle-r3.json`:
  `197552d2541bc31af15ceb651fc2d2f7f5b7ee48bb7f37b6cb2d79f25eed3955`.
- `native-cas-v198-native-popup-fairy-isolation.json`:
  `13a8ff8789bbce8f4212dd0417d5a6154ad5682b5af1ee7fa39615c1e124d0a7`.
- `native-cas-v198-fairy-only-wing-parts-audit.json`:
  `4358b61c6da22c6d18027f72277e6e148436b372c19d69391b18407bea8ea92f`.
- `native-cas-v198-fairy-saved-reference.json`:
  `9c214ea9475e334c126708e2e74d36df64d6a7c413640dc73a721abd7cf85b48`.
- `native-cas-v200-second-member-category-saved-reload-all40.json`:
  `d22afe0836241e2bdf5261ba4d020f119b843a84129272d883dda4191232e687`.

V196's tooltip failure, V197's redraw failure, intermediate input-coordinate
failures and V199's named-metadata refusal are retained as failures. A passed
successor proof never relabels or overwrites them. The owner's protected
original profile remains read/copy-only; all testing uses one disposable
profile.
