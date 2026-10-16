# Independent native CAS form owners

The current development candidate is V168, awaiting installation/runtime checks.
Production saves are not qualified.
The permanent Source guard remains enabled alongside the native fixes.
Machine-readable results and unqualified gates are recorded in
`manifests/native-cas-v167-validation.json`; private raw game data is not published.

## Exact ownership

A form has a `family/variant` identity. EA's native kind is rendering metadata,
not its identity. Human, Alien, Vampire, Mermaid, Spellcaster, Werewolf, Fairy,
PlantSim, Servo/Robot, Ghost, Reaper, Skeleton, Scarecrow, Imaginary Friend and
their named alternates can occupy separate graph records. Same-kind alternates
are independent. The native graph also accepts future/custom form identities;
the Source gameplay registry is still explicit and versioned.

The original stored native owners and the current active appearance are
separate allocations. Five Sims with seven stored forms each plus their five
active appearances require forty records; an active Alien cannot replace that
Sim's independently stored Alien record. Complete native CasData is deep-copied,
including fields outside the Python appearance codec. This does not claim that
every unknown field has a public editor.

Selection changes a cursor and binds the selected record. It does not copy
appearance, convert an occult or create/remove membership. Links start empty.
Explicit directed links and copies can connect any two exact owners; adding a
link does not immediately copy their appearances. Prepared edit propagation
is atomic across linked destinations. These graph operations still need their
complete native drawer/CLI interaction and persistence integration.

## Native binding

The scoped adapter replaces EA's unconditional primary-to-alternate copying
binder, including initial CAS load, household-member binding and ordinary
refreshes. Each Sim retains an entry owner and an independently selected partner.
The reusable native model is tracked by exact Sim/controller identity so an
incoming member cannot harvest the previous member's model. An ordinary refresh
first retains that same owner's newly edited data.

Each visited owner retains its own native undo context. EA's two physical layers
are not used as undo identity. Native history rebind preserves the exact inactive
owner and leaves the active edited/undone model intact. A selection receipt must
prove the requested owner, rendering kind, model context and native undo owner.
Matching only the native kind is insufficient.

The `.package` drawer receives all captured owners in bounded pages, supports
scrollable pages, movement, scale, lock and collapse, and highlights the exact
selected owner. UI clicks use reserved native capabilities on the UI thread.
The typed `cas form-owner-select` CLI stages one exact owner/generation and
consumes it once. The old `occult-owner-view` conversion route remains blocked.
Native calls are pinned to the inspected runtime code of game 1.128.90.1030.
The executable file is not rewritten. Private code windows are not distributed.

The native model setter contains a separate Vampire-biased rendering test. V161
exposed this in the real game: an Alien graph owner bound to a Vampire model, and
the switch was correctly reported as failed. V163 redirects only that inspected
CALL through a nearby relay. For an exact scoped owner, that rendering test uses
the selected genus; the actual membership mask and shared getter remain intact.
The aligned CALL operand changes atomically and is restored on installation
failure. Tests exercise executable relay installation, rollback and reuse, in
addition to reproducing the biased model setter. Runtime qualification is still
required; the correction is not a completed cross-form validation result.

Fresh named captures read the current native Sim/owner. They may preserve an
older bank without authorizing or replaying its appearance data. Prior-runtime
named-form replay remains blocked pending qualified reload integration. A named
appearance slot is not proof of an NPC career, death state, role or Imaginary
Friend relationship. Special-state gameplay producers remain separate work.

## Evidence and open gates

- Native fixtures cover all registered families/alternates, same-kind identity,
  complete fixture fields, repeated switches, explicit copy/link/unlink, stale
  and cross-Sim rejection, allocation failure, per-owner native undo references,
  initial binding, same-owner refresh and a shared-model household-member round trip.
- All nine native CTests pass. The DX11 smoke also replaces a retired swapchain
  without replacing its HWND; F11/capture cannot remain attached to a retired chain.
- V159's real native activation accepts the inspected runtime pins.
- V158's activation was refused; its stock CAS visit is not an adapter pass.
  Cancelling that visit and unpausing changed one Werewolf member's stored/active
  skin tone. The session was discarded without saving. The subsequent cold
  V159 comparison verifies all five Sims and all forty original appearances.
- All twenty disposable save/backup files remain unchanged through V159's
  normal unsaved closure. Protected original files were not written.
- V161's real CAS drawer displayed 39 independent owners for the first Sim,
  including 31 named form/alternate slots. The named Alien selection failed
  because the model rendered Vampire; this is retained as failure evidence.
- V163's fresh Live comparison verifies all five Sims and forty original
  appearances. All twenty save files also match the pre-V161 inventory.
- The Python ownership/payload, typed selection and seed-engine suites pass
  (29, 14 and 8 tests). All nine native CTests pass, including the local CALL
  relay fixture. These are implementation checks, not gameplay qualification.
- V163's real native engine completed Alien -> Vampire dark -> the same Alien,
  with exact graph identities, model genera, full membership masks and separate
  native undo contexts. Vampire also passed the complete semantic CLI receipt.
  Alien's semantic receipt failed because it compared `CASGetSimInfo` family
  metadata against the selected model genus. The failure is retained.
- V164 reads the inspected `GetSimOccult` model-genus getter separately in
  `native_context.rendered_form`. It preserves the original `CASGetSimInfo`
  record. Both the typed rendered-form read and exact native owner/undo receipt
  are required; a family-kind match alone cannot pass. The reconnect fix waits
  only after an explicit unqueued status-read refusal and never replays a queued
  read or mutation. Runtime validation of this package remains open.
- V164's full semantic CLI selected every one of the first Sim's 39 owners.
  A second visit caught changed body-hair swatch IDs on the Fairy alternate in
  four of the 77 observed panels. The matrix stopped at visit 43 and is FAILED.
- V165's temporary suppression of hair matching during binding/synchronization
  did not solve that runtime discrepancy. It is removed from V166. Its passing
  synthetic tests are not evidence that the body-hair issue is fixed.
- V166 adds `export-owner` to the typed native control. It serializes a committed
  owner DTO through inspected game functions, checks the Sim/generation, bounds,
  exact serializer end pointer and SHA-256, and optionally catalogs every declared
  field through the game's Python descriptor. Raw bytes remain available if that
  descriptor cannot be imported. This reads the committed graph; it does not
  harvest the current model, apply data or write a save. Nonappearance DTO fields
  may contain construction defaults, so this is not a whole-Sim backup or restore.
  Real-game exports succeed and establish that the Fairy loss is a stored-data
  change: leaving the view changed 122 exported fields, including 56 root outfit
  part entries. The first selection itself left the committed graph unchanged.
- V167 replaces the scoped two-slot synchronizer with a complete deep copy of
  the current edited model into its exact selected owner and native slot. The
  stock routine also changes preview modes, regenerates genetic/outfit parts
  and writes the inactive slot; it is not merely a serialization call. Scoped
  synchronization no longer calls that routine. Unscoped CAS keeps its native
  path. The regression fixture mutates both the model and inactive slot inside
  the stock routine, and checks that current edits and an opaque field survive.
- Household member navigation now validates delivered identities against every
  actual retained base row. Missing alternate thumbnails cannot block member
  selection. It neither fills filtered rows nor relaxes alternate acceptance;
  a destination can retain its previously selected alternate layer. The native
  selector still performs the member change and next-tick readback verifies it.
- V167 passes 893 CAS tests, nine native CTests and 31 epoch/migration checks.
  The real-game Fairy -> Werewolf -> Alien -> Vampire -> Fairy sequence and a
  subsequent same-owner synchronization retain identical complete snapshot
  bytes at all five export points. The edited repeat/member matrix completes
  142 visits across 71 owners/five Sims with zero returned-field/panel differences.
  Its first pass uses distinct observed physique values, so identical unedited
  templates cannot conceal aliases. All 39 first-Sim owners and eight owners
  for each other member are revisited after the household edit sequence.

## Repeatable CLI matrix

`python tools/cas_owner_matrix.py --state .work/reusable-profile-session.json --output .work/NEW-matrix.json`

The command discovers every captured owner for every scoped household member;
it does not hard-code native kinds, family names or a first-Sim-only subset.
Two visits compare all returned Sim fields and equipped panels, including
empty panels. Each action retains its existing typed CLI intent and receipt.
An ambiguous command or appearance difference stops the matrix without retry,
acceptance or saving. `--member-id` can narrow a diagnostic run; the default
covers the full captured roster. This is appearance-view retention evidence,
not proof of edited native fields, special gameplay roles or save/Tray round trips.
With `--edit-physique-markers`, the first cycle gives every owner a distinct
actual native physique value. Later visits must retain those values and every
other observed field/panel. This detects aliases that identical unedited
templates could conceal. Marker edits remain in the disposable CAS session;
the command does not accept or save them.
With `--verify-native-bytes`, actual edits are first flushed through same-owner
selection on the game thread. Every visit then exports that exact committed
owner/generation and compares all serialized bytes with its first-cycle
baseline, including unknown fields. This does not reload a whole Sim or treat
the DTO's construction defaults as gameplay data. A complete snapshot mismatch
stops the matrix even if all visible CAS fields still match. The seven matrix
tests include stale identity/generation, truncated data, digest and future-byte
changes. Runtime qualification is recorded separately from these tool tests.
The panel workbench separately checks the typed actual rendered genus and
records the independent owner when present. `CASGetSimInfo` family metadata
cannot stand in for the actual form. Switching owners mid-workbench changes
its context and stops subsequent edits.

Runtime gates still include edited Alien/Vampire/Alien and every other form,
all members/categories, native undo/redo, explicit copy/link controls, complete
edited graph export on CAS return, repeated CAS entries, MCCC/F11/Live edits,
settled simulation readback, controlled save/cold load and whole-household
Tray/Gallery round trips. No passing unit/build result closes those gates.

V167's subsequent panel-preview test passes head/body skin details but FAILS
body tattoos: opening that panel and switching Alien -> Vampire -> Alien
reduces one outfit's part arrays from 20 to 15 without an appearance edit.
The V168 candidate runs only the three inspected reversible preview-cleanup
functions before deep copying the current owner. Its new native fixture holds
an outfit part outside the short header in a temporary preview cache and checks
restoration before copying, current-edit retention and no repeated cache replay.
The stock regeneration/cross-owner routine remains bypassed. V168's real
tattoo -> Vampire -> Alien round trip now preserves identical committed native
bytes. Head/body skin details, eye makeup, nose and skin color also pass, and
all five complete Fairy exports remain identical through its cross-kind round
trip and another synchronization. Native CAS imports 39 owners for each of
five members (195 total); this is broader than V167's 71-owner inventory.
The 142-visit edited evidence remains V167; the expanded edited V168 matrix
must be qualified separately. `manifests/native-cas-v168-validation.json`
records these concrete cases without certifying gameplay roles or persistence.

Private evidence: `.work/native-cas-v160-final-native-tests.log`,
`.work/native-cas-v160-current-native-capture-tests.log`,
`.work/native-cas-v160-undo-receipt-tests-corrected.log`,
`.work/native-cas-v159-arm-inspected-pins.json`,
`.work/native-cas-v159-cold-all40.json`,
`.work/native-cas-v159-unsaved-exit-for-v160.json`.
