# Independent life-state appearances — development V133

The owner's requested end state is a full hybrid mod: every owned occult and
alternate form selectable and editable from any CAS room, additive life-state
creation, separate appearances, and complete save/Tray retention. Native EA
support is not the feature boundary. **That complete end state is still open.**

## Implemented in this candidate

- [x] Separate named life-state identities from native occult flag values.
  The registry includes Human, Alien, Vampire, Mermaid, Spellcaster, Werewolf,
  Fairy, PlantSim, Servo/Robot, Ghost, Reaper, Skeleton/Bonehilda,
  Scarecrow/Patchy and Imaginary Friend. Native traits/buffs, the death tracker,
  and the actual Imaginary Friend service are inspected as distinct producers.
  A costume trait does not establish an Imaginary Friend's service identity.
- [x] Capture complete named appearance variants on existing native owners.
  Names and Studio handles are independent from native game flags. Variants
  retain the existing appearance codec's physical, genetic, skin, tattoo,
  pelt, texture, voice and complete outfit data.
- [x] Inspect and edit inactive variants through the existing Studio
  preview/Apply/Undo path without activating them or writing another Sim.
- [x] Bind an exact captured original before the first explicit appearance
  switch. Persist intent and native originals before mutation; compare every
  native appearance afterward. A rejected write remains recovery-required
  and cannot be silently retried.
- [x] Synchronize accepted Live/Studio and normal/MCCC CAS transaction edits
  only into the active named variant. Independent inactive looks remain intact.
- [x] Add F11 capture/bind/select controls and an evidence-recording CLI:
  `apex_cli.py lifestate catalog|list|capture|bind|select`.
  Exact inspected checksums and pre-dispatch UUID records are required.
- [x] Keep named preview ownership separate from the native visual rig.
  The preview broker and separately licensed worker accept bounded named
  handles with an explicit native visual form; those handles never become
  occult enums in a game Sim.
- [x] Download and inspect 14 relevant Gauntlet101010 releases, with hashes,
  archive inventories, native tuning identities and current release URLs.
  The downloads stay private and are not installed wholesale. Servo's shared
  bytecode is inspected without importing or executing it. Its trait-equivalence
  and native TraitTest safeguards are retained as porting research.

## Validation and artifacts

28 focused life-state/CLI/Studio tests pass, including inactive edits, exact
original return, other-form preservation, stale checksums, wrong identities,
field-loss refusal, rejected native writes, and unqualified reload refusal.
The existing 36 Studio tests and eight preview-service tests pass. All six
native CTests pass. The separately staged preview worker builds and passes its
eight-scenario modern deformer/native-data self-test. These are component
checks; they do not establish actual in-game special-state or native-CAS parity.

The V133 core regression run passes all 2,232 tests in 938.254 seconds
(`native-cas-v133-full-tests.log`). The later named-preview broker extension
also passes its eight focused tests. An actual Source V131 appearance capture
assembles successfully through the staged named-owner worker: the manifest
retains handle `1299409723`, uses native Alien rig `2`, and returns one surface
and ten in-memory assets. Scene SHA-256:
`2a8cc4790de8134ced66248b23527ef21396819543c2cdf55afc6efe83b85f35`.
This verifies the renderer contract with actual captured bytes, not an installed
V133 Source session. No Sim mesh/texture exports or game mutations occur.

A fresh read of the running V131 household still matches all 40 accepted
appearance owners. Proof SHA-256:
`2e45c9c8763eb0c5e87f0fa65e266fcf5b9f2bc57c0462b1124bdf8cf7ba3f22`.

The immutable candidate is
`Apex_Development_Candidate_2026-10-15-independent-life-state-appearances-v133.zip`,
SHA-256 `6da1228141e355a82043976e0b301a6e3c3e1e46a2c4cb8b8b6a5d6cbc8be857`.
It contains 93 Python 3.7 modules, seven packages and 207 independently
Rust-verified package resources. It is built, not installed or runtime-qualified.
The matching preview worker is staged separately under the private worker
candidate directory; the running helper and game retain their existing builds.

## Required work before production use

- [ ] Native-CAS additive membership and navigation across every captured owner
  within a single CAS visit. The inspected selector currently invokes
  `SetSimOccult`; no verified additive replacement handler is installed here.
  The current native CAS room's two-layer transport remains limited.
  Additional research confirms the inherited `get_occult_types_for_save`
  deliberately projects one occult plus Human. Current actual Live flags can
  be `65` even while the active appearance is Alien `2` and all six native
  memberships exist. Full native export of verified membership is the next
  candidate change; it is not included in V133.
- [ ] Actual special-state creation, gameplay activation and alternate-form
  switching, including Reaper roles/career and Imaginary Friend child/doll
  continuity. Named appearance switching alone is not this gameplay support.
- [ ] Life-state variant save/reload and native Tray/Gallery round trips.
  Old-runtime variant sidecars currently refuse replay, preserving their
  contents for qualification. Cross-session persistence is not claimed.
- [ ] Native runtime proof for F11 named forms and the staged preview worker.
- [ ] All EA/modded walkstyle, trait and career controls and their dependencies.
- [ ] Complete special-state artwork and all per-form CAS/category coverage.
- [ ] Existing native new-game CAS/Gallery crashes and whole-household native
  Library import acceptance. All seven existing GitHub issues remain open.

The permanent guard remains enabled alongside native copy prevention.
The protected original profile is read/copy only. No original save, Mod or
folder was renamed, overwritten or deployed to during this implementation.

## Provenance

The owner explicitly authorized downloading/adapting the relevant author
releases. See [the checked-in baseline inventory](../docs/GAUNTLET_BASELINES_2026-10-15.json)
and [Gauntlet101010's projects](https://www.curseforge.com/members/gauntlet101010/projects?page=1).
Reference releases include [Servo Lifestate Customs](https://www.curseforge.com/sims4/mods/servo-trait-customs),
[Grim Reaper Optionals](https://www.curseforge.com/sims4/mods/sims4-grim-reaper-optionals),
[Skeleton customization](https://www.curseforge.com/sims4/mods/skeleton-unlocked-trait-changed),
and [Adventure Awaits NPCs](https://www.curseforge.com/sims4/mods/adventure-awaits-careers-and-npcs).
Their archives and proprietary game research are not committed. No upstream
endorsement or completed port of the shared script is implied.
