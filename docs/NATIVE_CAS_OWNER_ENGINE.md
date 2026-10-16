# Independent native CAS form owners

The current development candidate is V164. Production saves are not qualified.
The permanent Source guard remains enabled alongside the native fixes.

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

Runtime gates still include edited Alien/Vampire/Alien and every other form,
all members/categories, native undo/redo, explicit copy/link controls, complete
edited graph export on CAS return, repeated CAS entries, MCCC/F11/Live edits,
settled simulation readback, controlled save/cold load and whole-household
Tray/Gallery round trips. No passing unit/build result closes those gates.

Private evidence: `.work/native-cas-v160-final-native-tests.log`,
`.work/native-cas-v160-current-native-capture-tests.log`,
`.work/native-cas-v160-undo-receipt-tests-corrected.log`,
`.work/native-cas-v159-arm-inspected-pins.json`,
`.work/native-cas-v159-cold-all40.json`,
`.work/native-cas-v159-unsaved-exit-for-v160.json`.
