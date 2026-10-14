# Multi-hybrid preservation and crash investigation

Development checkpoint, not a completed release. The protected original profile
remains read/copy only. One disposable profile is reused. V90 intentionally saved the disposable normal Slot02 after the explicit Alien-only
commit and verified its stable file hash and complete appearance seal. The
protected original was untouched. Earlier V88 CAS entry changed the six
disposable autosave-family files; these writes are recorded explicitly.

## October 13: native transition repair and full CAS continuation

V86 tracing identified the actual nested selection failure: native trait refresh
removes another occult's current-form trait, whose legacy removal callback asks
for Human even while Alien is active. `foreign_current_trait` runs native trait
removal and effects once, suppressing only that unrelated nested Human request
inside the exact same tracker/current/map scope. Explicit Human, current-kind
trait removal, ordinary pairs and membership-trait removal keep native behavior.

The first V86 profiler was too broad and delayed simulation by roughly 284
seconds. Its failed request and eventual trace are retained. The owner ended
that runtime. V87 replaces the profiler with bounded, temporary method-boundary
wrappers only for explicit marked-profile switch diagnostics; no per-Python-call
profiler or production frame-loop tracing remains.

V88 records eighteen successful transitions across two imported hybrids:
Alien → Vampire → Alien → Mermaid → Werewolf → Fairy → Spellcaster → Human →
Alien on each. Native time advanced at least 2,141 ticks per step; all six occult
memberships, seven stored appearances and every existing active field remained
exact. Extra native bathing outfits generated after unpause are recorded as
append-only additions. Existing outfit bytes and unknown root fields are still
compared exactly. The earlier strict outfit-hash failure is not relabeled.

The later V88 full-household CAS entry selected the first household Sim instead
of the requested clone. Identity checks blocked edits. That session subsequently
crashed with a null write at TS4 offset `0x112c371`. The exact dump/report and
failed captured-only archival attempt remain retained; causality is unresolved.
Six autosave-family files changed during CAS entry; normal Slot02 and its
backups stayed unchanged.

V89 prepares all three members' existing native availability pairs before full
CAS. Each durable preimage includes every appearance/context and traits. It
changes only availability, verifies current kind, traits and all thirteen
appearance fields unchanged, and refuses uncertain replay. The selected CAS
transaction captures its original context before this preparation. Complete
unselected-member context restoration remains a separate pending gate.

One V89 full household CAS pass then remains stable through six verified Alien
edits: skin details, earrings, lipstick, top, hair and shoes. Exact eyebrow color
requests fail native readback and are retained as failures. Actual Live return
changes only Alien; explicit Alien-only commit verifies all native owners.
Eleven subsequent transitions, including Alien → Vampire → Alien and every
other kind, preserve all seven stored appearances and both household companions.
Each step advances actual simulation by at least 508 ticks and ends paused.

V90 retains complete mismatched swatch acknowledgements as terminal failures,
with exact raw packets/hashes and no resend or success claim. Foreign,
incomplete, history and unresolved ownership replies remain blocked. For the
already-running V89 script, the CLI separately recognizes its complete failed
readback only to permit normal unsaved closure after detached CAS and exact
paused Live checks. Source records remain unchanged; this cannot unlock CAS or
authorize a save. Both native exit menus complete through background CLI input,
with all twenty save/backup files unchanged during closure and no new crash.
V90 CLI launch also handles the observed EA permission dialog, loads the exact
household without taking focus and opens verified full CAS. The actual failed
eyebrow swatch becomes terminal `failed`; a subsequent fresh CAS status succeeds.
V90 then completes semantic native CAS acceptance and matching original-Sim
Live return without human input, verifies 865 simulation ticks and pauses. Its
original bank-observation UUID finishes after the return tool's sixty-second
deadline, recording Alien as the sole changed lane. The same UUID is polled;
the observation and acceptance are never resubmitted. Explicit Alien-only
reconciliation and controlled normal Slot02 save/seal both pass.

Same-script cold startup loads that exact normal slot. All seven stored owners,
the distinct active original Sim and six memberships match the seal before and
after 1,789 actual simulation ticks. No appearance repair, bank update, save or
input is submitted by that verifier. The full household comparison separately
fails for the two imported companions: each stored Alien genetics value changes
to its distinct active genetics, and each active outfit blob changes. Complete
field-level differences are retained. The original's certified pass does not
certify those companions or full-household persistence.

V91 fixes household navigation's use of the initial raw selection index. Raw
delivery continues to prove exact pair identities/positions, while the retained
selector and fresh native selected Sim bind the current index, household and
layer. An initial different member cannot replace that current binding. Thirty
navigation and sixty-nine retained-bytecode tests pass; the frozen full suite
passes 1,814 tests. Same-visit disguise runtime acceptance remains a separate
test.

That actual V91 test then passes twelve distinct selections in one full-CAS
visit: skin detail, earrings, lipstick, top, hair and shoes separately on Alien
primary and Human disguise. Each disguise item differs from its Alien counterpart.
Returning to primary verifies all six Alien selections still equipped. Semantic
native acceptance returns the original Sim to Live, advances actual simulation
and pauses. Raw return changes only Human and Alien; explicit acceptance of both
lanes commits with all native owners verified. Vampire → Alien → Human → Alien
then passes complete stored/existing active-field comparisons after at least
2,200 actual ticks per step, with both companions unchanged. A controlled existing
normal Slot02 save and matching seal pass. This is twelve tested selections,
not every panel or a saved cold-reload claim for those new edits. The final
unchanged-source/tool suite passes 1,817 tests.

The V91 paired-edit same-script cold verifier subsequently passes all seven
stored appearances, distinct active appearance and six memberships before and
after actual simulation progression, with the saved file/bank/reference unchanged
and no appearance repair. Native restore and imported-household acceptance remain
separate. Receipts: `multi-v91-paired-explicit-commit.json`,
`multi-v91-paired-edit-cycle.json`, `multi-v91-paired-existing-slot-save.json`
and `multi-v91-paired-cold-certified-readback.json`.

One later EA launch fails before input when Windows refuses foreground ownership.
The CLI removes this needless precondition and sends the recognized button's
messages directly to the same verified window, without moving the cursor or
requesting focus. Changed window, failed down/release and duplicate input cases
are checked. Twenty-nine permission-handler checks pass, and actual account-bound
launch subsequently acknowledges EA consent and starts the expected Sims process.

Private receipts include `multi-v88-imported-continuation.json`,
`multi-v88-cycle-timeline-audit.json`, `multi-v88-cas-crash-analysis.json`,
`multi-v88-crash-save-inventory.json`, `multi-v89-alien-explicit-cas-commit.json`,
`multi-v89-edited-cycle-audit.json`, `multi-v89-retained-readback-unsaved-exit.json`,
`multi-v90-resume.json`, `multi-v90-full-cas-entry.json`,
`multi-v90-eyebrow-exact-swatch.json` and
`multi-v90-after-failed-swatch-fresh-status.json`. They contain private Sim/vendor
data and remain outside Git. The V90 frozen full suite passes 1,812 tests; later
targeted Source and CLI checks do not substitute for runtime or exact-head CI.

## Changes

- Adding a new occult now captures every existing stored appearance and the
  separate active Sim before EA loot/generation. Native wrapper identities,
  physical flags, current form and native membership are checked afterward.
  New native defaults remain native; older forms cannot become the new form.
- Stored wrappers without `load_outfits` now use the inspected native C++ outfit
  setter. Complete outfit bytes are captured even without the mixin serializer.
- Studio repairs only unrequested setter side effects, then verifies the entire
  appearance. Rejected bytes and assignment diagnostics are retained before
  rollback. Native form context is restored before completion can pass.
- Clone loading retains an immutable source, checks primary facial morphs through
  the actual `facial_attr` descriptor, preserves represented stored core/outfits,
  admits EA registration of the exact new object once, and rejects another object
  at its allocated ID. Matching outfit/category representations and matching
  native masks are no longer unnecessarily rebuilt.
- Queued native spawns are completed after actual unpaused simulation without
  creating the members again. Startup availability is restored from each clone's
  exact pre-startup context; a union inferred from its stored forms is forbidden.
- Live transition restoration repairs only fields that differ, restores the
  active owner before stored owners, and checks the complete set after all
  writes. Rejected setters are never replayed. Cold-load restoration retains its
  separate existing contract.
- `household export-records` writes an external review ZIP containing native Sim
  records. It never writes generated metadata/portraits into the game's Tray.
  `export-tray` refuses unverified native Gallery generation before any operation.
- `household load-tray --source-file` reads an exact bounded external household
  binary, verifies its hash and roster, allocates new identities, and preserves
  existing members. Partial failures retain allocations and prohibit replay.
- `household recover-import` archives a failed journal only after every allocated
  ID is absent from the native manager and persistence buffer and the original
  roster is exact. It removes no Sim and writes no save.
- `switch-archive-unsaved` retires only failed-switch metadata after exact closed
  runtime/unchanged-save evidence. All originals remain in a byte-exact external
  preimage and content-addressed history. It does not certify CAS, restore a
  native appearance, or authorize replay of an old bank.

## Actual runtime evidence

V64 created two additional Sims beside the existing disposable Sim. All twelve
non-Human additions passed independent before/after checks, producing seven
stored owners on each of the three Sims. Fourteen distinct physique edits on
the two new Sims survived actual unpaused simulation. Every other stored owner
remained unchanged. The final current-Human edit also synchronized a Swimwear
outfit that already existed on its active Live owner; its full bytes match that
preexisting wardrobe. This is not an edit leaking to another form.

V66 verified the existing Sim's small physique edit and complete Undo. Actual
Alien → Vampire → Alien, then Mermaid → Werewolf → Fairy → Spellcaster switches
preserved all seven stored appearances after unpause. Human did not converge
from Spellcaster; after simulation advanced it still reported native kind 16.
That failed request remains failure evidence, subsequently archived after the
unchanged unsaved closure. This does not close every pairwise switch gate.

Whole-wardrobe Vampire → inactive Mermaid paste remains rejected: native readback
retains five destination categories and omits new categories. One existing
category changes, so this is not merely a no-op. Complete rollback is verified.
Previous one-outfit/tattoo transfer proofs remain scoped to those operations.

V71 and V75 load two complete native-record clones into the existing household,
giving three members. Both added Sims are instanced and pass all ten native
persistence-buffer checks after simulation progresses. All seven represented
stored appearances match their immutable source. The existing Sim's complete
appearance and owner identities remain unchanged. This proves native import and
spawn completion, not a disk save or cold reload of the three-member household.

V71 also retains fourteen distinct physique values across the two imported Sims.
Its first imported Human → Alien switch fails complete genetics readback. V75's
active-first restoration still rejects that switch. The rejected Alien genetics
lose four **distinct current body-hair parts** (body types 78–81), while preserving
the face, physique and separate preferred-growth records. The current and
preferred IDs differ; these are not identical cross-list duplicates. Their loss
must not be normalized away. Complete originals, native setter observations and
the failed request remain retained. No imported Alien → Vampire → Alien success
is claimed.

V76 adds `game growth-probe`: a token-guarded disposable-profile operation that
uses EA's inspected `set_caspart` source/destination API on a detached native
wrapper. It verifies complete genetics and checks every existing owner and
native context afterward. It never applies that staged result to a real Sim.
Unknown-byte changes, non-body-hair deletions, reordering and conflicting slot
owners are rejected. V76's actual detached preparation passes complete genetics
readback with every real owner and native context unchanged. This is preparation
evidence, not a successful form switch.

V77–V79 reject staging that cannot reconstruct complete genetics. V80 identifies
an existing same-kind stored source whose entire appearance matches the desired
target. Its staged genetics match all 1,507 source bytes. Applying the generic
native override with flags 800 and an empty outfit filter nevertheless loses
current body-hair entries and changes outfits. V82's four-argument override with
flags 288 also fails complete genetics and outfit readback. Both rejected
requests retain complete owner preimages and observed payloads; neither is
reported as a successful repair.

V83 uses the inspected native CASP source/destination call directly after detached
preparation. A complete, distinct same-kind source must match every desired
appearance field; a different wardrobe, partial source or other occult refuses
before a real Apply. The single transfer, distributor resends, every other owner,
native context and entire target appearance are checked afterward. Actual V83
preserves complete genetics in the Live owner, including the four distinct
current body-hair entries. It remains rejected because that CASP operation
replaces CC eyelashes using body type 78 in the wardrobe. Genetics-only success
does not satisfy the full appearance gate.

V84 also restores the exact outfit blob on the detached copy and requires its
entire appearance to match. Only after that proof can the real transfer repair
an outfits-only side effect with one exact native outfit write, without assigning
genetics again. Unknown outfit bytes and all categories remain in the immutable
message. A genetics/skin/voice change or failed detached proof cannot authorize
that second write. Actual V84 and V85 complete this repair in the real Live
owner, with complete genetics, original CC outfit bytes, every unselected owner
and native context verified. The complete form switch still fails: it returns to
Human before the outer acceptance check. V85's retained result shows all seven
stored appearances exact while the active owner is no longer the selected Alien.

V85 removes legacy cleanup from explicit Human/non-Human selection and respects
the native switch's boolean result. Four tests verify successful selection,
Human from Spellcaster, native refusal and a changed selection after availability
writes. The native runtime still refuses imported Human → Alien. The inspected
public native switch performs a trait update after the internal appearance
transition; that boundary and its callbacks require tracing next. Its role in
the reversion is an inference from the accepted internal repair, subsequent
current-form failure and native call order, not a completed isolated proof.

V81 was packaged with stale recovery pins and was not used for a household test.
The build now checks literal recovery epoch, self hash and all pinned module
bytes before any package build and again before bundling. It executes no mod
source during that check and refuses stale or path-traversing declarations.

## Crashes and recovery

The two startup failures at native TS4 offset `0x165e3da` occurred before Apex's
DLL was loaded. They reproduced with the two newly generated experimental Tray
files present. Both exact files were archived and quarantined; the five original
disposable Tray files stayed intact. The same candidate then reached Live mode.
Generated Gallery metadata is now blocked from active Tray entirely.

Separate V65/V66 shutdown crashes followed partial clone loads. The V65 dump
records an invalid execute target `0x6f` from Simulation/CPython call frames;
this is distinct from the startup null read. Their reports/dumps were preserved,
and all twenty disposable save/backup hashes stayed exact. Subsequent V67, V69,
V70, V71, V73, V75–V80 and V82–V85 sessions exited normally without a new crash.
V71/V75–V80/V82–V85 include successful complete native imports. All twenty save/backup hashes remained
unchanged. These scoped successful exits do not prove all crash causes resolved.

Earlier rejected imports remain failure evidence: stored genetics in V65,
redundant registration in V66, Vampire skin-tone changes in V67, and V73's
over-broad restoration regression. V75 retains cold-load behavior separately
from Live transition repair and passes represented-field native reconstruction.
The imported switch, all-field archive and saved household round-trip gates
remain open.

Native stored-occult protobufs do not represent every readable pelt/custom
texture field. A complete Apex appearance sidecar and corresponding acceptance
are still required before claiming an all-field archive round trip.

## Build and private evidence

Current source epoch: `2026-10-13-multi-hybrid-tray-v85`.
Bundle SHA-256:
`500f5e382dbba07f18801dea6faebd4e2beba95f910efec9abac35985401937e`.
It contains 79 Python 3.7 modules and seven packages with 206 independently
Rust-verified resources. The native DLL remains unchanged. V85's frozen full
Python suite passed 1,787 tests. The 16 targeted growth tests pass, including
wrong-source refusal, failed native readback, no replay, detached outfit-write
rejection and both outfit-restoration and resend side effects.
Exact-head CI is a separate check; local/runtime evidence above is not CI proof.
The V68 suite was invalidated by a source-epoch change while it ran and is not
reported as passing evidence.

Private receipts stay outside Git, including:

- `multi-hybrid-occults-v64.json`, `multi-hybrid-edit-cycle-v64b.json`, and
  `multi-v64-fourteen-edits-verification.json`.
- `multi-v64-startup-crash-analysis.json`, the exact two-file quarantine archive,
  and `multi-v64-quarantine-live-proof.json`.
- `original-edit-undo-v66.json`, `original-form-switch-v66b.json`, and
  `multi-v66-human-after-settle.json`.
- `tray-v65-wardrobe-only-runtime.json` and `tray-v66-wardrobe-only-runtime.json`.
- Failed import journals, `multi-v65-shutdown-crash-analysis.json`, immutable
  unsaved-closure receipts and `multi-v66-unsaved-switch-archive.json`.
- `multi-v71-external-load.json`, `multi-v71-after-import-original.json`,
  `multi-hybrid-switch-cycle-v71.json` and `multi-v71-unsaved-switch-archive.json`.
- `multi-v75-external-load.json`, `multi-v75-after-import-original.json`,
  `multi-v75-imported-cycle.json`, complete native form diagnostics and
  `multi-v75-unsaved-switch-archive.json` with its byte-exact bank preimage.
- Passive installed-code investigation `native-growth-setter-callers-v75.txt`.
  Native game code and private Sim/CC payloads are excluded from the repository.

- `multi-v76-alien-growth-probe.json`, V80/V82 rejected generic override journals,
  `multi-v83-imported-cycle.json` and its retained native owner diagnostics.
- V82/V83 exact normal unsaved closures and failed-switch metadata archives,
  with byte-exact external bank preimages. No old bank replay is authorized.
- Owner-confirmed original-folder rename receipt; original inventory observations
  are read-only and do not undo the owner's intervening Mods/save changes.
- `multi-v84-detached-alien-full-probe.json`, verified V84/V85 complete Live growth
  repair journals, `multi-v85-imported-cycle.json`, the all-stored-owner comparison,
  `native-public-switch-trait-path-v85.txt` and exact V84/V85 unsaved closures.

Full CAS/MCCC/every-panel acceptance, every pairwise form switch, native Library
creation, full Tray parity, all-field household round trips, controlled save and
cold reload, universal content/material/thumbnail coverage and the broader
production gate remain open. A rewritten headless Sims engine is not delivered.
# Five-member household stress work, October 13, V92–V93

V94's actual cold load matches every readable field on all **35 stored owners
and five active appearances** before simulation progression. All 35 indexed
extension source receipts match the exact saved core and file; no extension
refusals are reported. After actual unpause, all 35 stored owners, including
every Werewolf pelt, still match. Two fresh companions' active genetics/outfits
change during initialization. The complete active-owner gate remains failed.

The repeatable whole-roster cycle then passes **25 targeted transitions**:
nine on the original, nine on the first imported Sim and seven on the second.
Each step checks all five members after real simulation progression. The first
strict run stops after two successes because two companions append a new
category-5 outfit. A separate byte-level classification proves all existing
rows/indexes and unknown root bytes stay exact. The tool now records only such
bounded active append-only deltas as native generation; destructive changes,
new non-outfit fields and stored-owner changes still fail. The corrected run
stops at step 26 when an unselected fresh companion switches Alien to Human
during Live play. Its original receipt, complete before/after records and
differences remain failed evidence. No full 45-step/all-category/all-member
acceptance is claimed. The final frozen code/tool suite passes **1,840 tests**.

V93's actual controlled save succeeds, seals and produces normal Slot02 SHA-256
`79121bd10b1e0fff3174135fc815f8e7a05cfd75b75a18dbae05ec7740182906`.
Read-only extraction of the indexed kind-13 resource proves that all five
Werewolf carrier records contain the exact pre-save pelt bytes. Nevertheless,
initial/settled cold comparison fails on four companions' pelts and the two
fresh companions' active genetics/outfits. A separate read of EA's existing
loaded save buffer, with no native Sim serialization, contains **zero** carrier
markers. Its Werewolf cell has exactly the same declared core as the indexed
disk record. EA's loaded-buffer path strips the unknown carrier data; proto2
preservation alone does not establish that whole engine path.

V94 adds a read-only indexed-save fallback bound to the actual native slot,
GUID, Sim, household, form and complete extension-stripped incoming cell bytes.
A changed incoming core, ambiguous owner, unsupported slot or changed file
cannot authorize older extras. It verifies the indexed resource identity,
bounded RefPack/zlib decompression and unchanged source file. One memory cache
avoids decoding the save for each member. Runtime receipts expose both source
authority and refused extensions. This fallback independently recovers the
exact pelt from the real V93 saved/loaded companion-cell fixture. Seven new
tests cover stripped carriers, stale cores, identity mismatches, fresh Tray
allocations, unknown slots, future groups and RefPack overlap/bounds. V94's
unchanged-source suite passes **1,839 tests**. Actual V94 load acceptance remains
separate until the household comparison completes.

Before the V94 test launch, the exact closed marked profile's old test bank and
seal files are retained byte-for-byte outside the profile, with hashes and a
durable receipt. Only these two mod metadata files receive fresh empty stores;
the saved household, all save files, other mod data and protected original are
unchanged. This does not resolve old failed intents or certify prior edits.
It permits the new test run to create banks from the actual saved native owners
instead of replaying unsupported records from earlier development runtimes.

The marked reusable profile now contains five existing hybrid Sims. Each has
six actual occult memberships and seven stored appearance owners. The owner
requires every member, every occult, every native CAS category, single-member
and whole-household edits, repeated form changes, household reentry and Tray
reload. `household-stress plan` records **5,390 initially untested cells**:
five members × seven forms × 77 native panels × two edit scopes. Empty and
unsupported categories must remain visible in the evidence and cannot count as
successful edits. Additional controls and lifecycle gates remain separate.

V92 fixes a concrete authority defect: active-form preparation copied the main
Sim's physical data into the cloned incoming stored-form record, then reused
that modified clone as immutable load authority. Preparation now uses another
working copy. Two regression tests cover active preparation and a native loader
that changes its own input. The corrected frozen suite passes 1,820 tests.

The five-member V92 controlled normal Slot02 save completes, with SHA-256
`207fac28cfe2017a3a7a61f3857d43500357294fb2b2e74921b2ee9d9cf50e10`.
Two fresh imported Sims acquired different active/stored Alien genetics after
full-household CAS without intentional edits. The real cold reload preserves
**every stored Alien genetic record** before and after 2,368 simulation ticks.
The whole-household test nevertheless fails: four companions' stored Werewolf
pelt layers differ after reload, and the two fresh companions' distinct active
genetics/outfits differ initially. Those active differences disappear after
simulation initialization. This is not a full household stability pass.

Runtime descriptor discovery finds pelt_layers/custom_texture on native SimData
but neither on PersistableOccultTracker.OccultSimData. V93 introduces a bounded,
inert, checksummed proto2 unknown-field carrier for those two per-form values.
It validates the exact occult kind and readable types, refuses native/foreign
field-number collisions, duplicates and damaged metadata, and preserves every
unrelated wire byte including unknown groups. Optional damaged load metadata is
reported rather than allowing that failure to discard the Sim. Native core
appearance fields retain their existing serialization. [Proto2 preserves unknown
fields during binary parse/serialization](https://protobuf.dev/programming-guides/proto2/);
whether EA's complete disk-save path retains this carrier requires the actual
V93 round trip and is not inferred from the protocol documentation.

V93's frozen suite passes **1,832 tests**. Seven new real-protobuf extension
tests cover parse/copy/replacement, future fields/groups, corruption, collisions
and wrong owner kinds. Five household stress tests require the whole roster,
actual six memberships, every owner/payload, new-field changes and both edit
scopes. The CLI checks every companion after a targeted switch and actual
unpause, records request identities before submission, and stops on unresolved
operations. Its first V93 cycle refuses before native mutation because the
original Sim's bank belongs to an uncertified prior runtime; that failure is
retained. Refreshing a live snapshot transaction is separate from CAS edits and
must not be reported as in-game CAS editing proof.

All closures in this work use the background CLI's normal unsaved exit and
verify unchanged save/backup files during each closure. The controlled normal
test save changes above are deliberate. The protected original is read/copy
only. The V93 candidate and runtime gates remain development work.
