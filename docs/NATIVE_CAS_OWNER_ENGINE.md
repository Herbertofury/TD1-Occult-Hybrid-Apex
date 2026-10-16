# Separate native CAS form owners

Cross-occult CAS selection is unfinished and is not qualified for production
saves. V155 reached a native Alien kind, but CAS still highlighted Vampire.
Its early UI acknowledgement reported the old kind. The conversion/history
route can cache Alien appearance data under Vampire's identity. It is not the
independent, clickable form selector requested by the user.

V156 disables that route at Source dispatch, the AS client and the scoped
native service/history boundaries. Complete import and activation alone no
longer authorize navigation. Status reports the conversion quarantine and
`independent_owner_view_ready: false`. The permanent Source guard remains on.
The old V155 code remains cached in the current disposable game; building a
replacement is not evidence that it has been installed or qualified.

## Implemented owner separation

`ApexCasOwnerGraph.h` owns one separate appearance allocation for every
captured Human/occult owner of each Sim. Selection changes only its cursor.
It cannot copy appearance fields or create/delete memberships. Edits require
the exact Sim, form and selection generation. Stale, repeated and cross-Sim
commits are refused.

Forms are unlinked by default. Explicit copy deep-copies a complete appearance
and preserves the destination owner identity. Explicit directed Human/form
links control subsequent edit propagation; enabling a link does not overwrite
either existing appearance. Unlink stops propagation. Copying between different
occults is supported as an explicit action, independently of linking.

The native adapter clones the game's complete CasData with its deep-copy
routine, then sets only the destination identity header. Unknown captured
fields remain in that native copy. The active entry appearance is captured
separately and initializes only its actual owner. Reseeding after the real CAS
handshake is refused before native protobuf construction. Graph ownership and
revision metadata are visible in status without exporting appearance payloads.

The graph currently represents the seven captured native kinds. It does not
claim complete special-lifestate coverage or additional same-kind alternate
slots. Native undo histories, view binding, edited return serialization and
extra alternate-slot identities still need integration and runtime proof.

## Native integration still required

The inspected native primary/alternate selector synchronizes the old view
before rebinding. That synchronization also copies fields into the inactive
owner. The replacement must commit the exact bound owner, preserve every
unlinked inactive record, bind the requested existing owner, and associate
its own undo history. Calling SetSimOccult again is not that implementation.

Native conversion is blocked for the captured development household. Ordinary
unscoped Sims retain EA's implementation. All hooks are tied to the exact
1.128.90.1030 executable and inspected runtime function fingerprints. No
executable file is rewritten. Runtime code windows remain private work data.

The `.package` strip shows all captured kinds and supports qualified same-pair
navigation. Cross-kind buttons remain disabled. They must not be enabled until
the direct owner-view path and its postconditions are implemented. A native
kind change alone does not prove correct appearance ownership or retention.

## Evidence

The new native owner graph fixture exercises five Sims, seven independently
allocated forms each, all fixture fields including unknown fields, 800 repeated
form selections, edits across the household, explicit copy/link/unlink,
stale/cross-Sim rejection and allocation-failure atomicity. All nine native
CTest targets pass. These are code-level checks, not an actual game switch.

The V155 failed trial was cancelled through the actual CAS confirmation,
without applying its conversion. Live simulation advanced from 1,603,309 to
1,631,115 ticks before pausing. All five Sims and all forty stored/active
appearances exactly match the canonical capture. All twenty save/backup
files remain unchanged. Private evidence:

- `.work/native-cas-v156-after-cancel-all40.json`, SHA-256
  `4574968bd79d2c1f49e1dc012817775a59d6a7b82d1264272cd6eec89f70098f`.
- `.work/native-cas-v156-after-cancel-save-inventory.json`, SHA-256
  `53a98c18de5e074c1833f1802a05f34ad688bca111f05d8ef3ff277195714ea8`.
- `.work/native-cas-v156-final-native-tests.log`.

Release gates remain actual Alien/Vampire/Alien separate edits, explicit
Human/alternate links and copies, every household member and category,
CAS/MCCC/F11/Live changes, native undo/redo, settled Live return, controlled
save/cold load and complete household Tray/Gallery round trips.
