# Multi-hybrid preservation and crash investigation

Development checkpoint, not a completed release. The protected original profile
remains read/copy only. One disposable profile is reused. V90 intentionally saved the disposable normal Slot02 after the explicit Alien-only
commit and verified its stable file hash and complete appearance seal. The
protected original was untouched. Earlier V88 CAS entry changed the six
disposable autosave-family files; these writes are recorded explicitly.

## October 14: independent household CAS protection, V100–V102

### V102–V104 runtime continuation

V102's imported native definition works in-game: all eleven body-type regions
45–54 and 113 are returned; selecting region 46 verifies its exact native
readback. The same EA tattoo 399362, body type 45/layer 0/id 1, also fails native
acceptance on the Human disguise. Two Undo operations permit corrected return;
an explicitly restored Human lane and all five context commits return every
appearance to the saved baseline. This does not establish an Alien-only cause.

V103 tries EA's temporary first tattoo slot without AddEmptyLayer. The exact
part/layer readback acknowledges, then the game crashes before the return
command creates an acceptance request. Private minidump parsing records a
native write access violation at `0x14112c713` to `0x34aeec0`. Captured code
starts with `and qword ptr [rax], 0xf`; no native function name or causal
interpretation is certified. The normal Slot02 remains SHA-256
`4cddc75fd958c2b154cf50d5cc49c1f2209ef77467d002a0b1797cc4bf9294a3`.
The failed prototype remains evidence; 1,884 passing unit tests do not make it
runtime safe. The new serialized fixture initially modified the wrong method;
that failed suite is retained separately from its corrected passing run.

Closed crash archival now preflights every member's exact entry checkpoint and
native availability extension before any write. It atomically archives all
five never-observed receivers, preserves their complete originals/prior banks,
and verifies every save/backup hash unchanged. It performs no appearance or
save replay. V104 removes the crashing temporary-slot write and blocks first
tattoo insertion before native mutation; existing-layer work remains separately
unproven. Tattoo completion and full production readiness remain open.

V104's frozen suite passes **1,888 tests in 272.073 seconds**. Its guarded
cold load preserves all 40 saved appearance owners before and after **2,277
actual simulation ticks**. In native full CAS, both first-part insertion and
empty-layer creation return explicit refusals with `mutation_started: false`.
The no-edit native acceptance is rejected; a separately recorded nose preset
edit permits a transition, while the early Live observer lacks its complete
instanced context. A later fresh native read confirms the exact household in
paused Live without repeating acceptance. Independent explicit original-owner
restoration is required for that diagnostic edit; this does not certify the
earlier incomplete return observer or tattoo retention.

Private crash evidence: `multi-v103-first-slot-native-crash.json`, SHA-256
`49f8c3ed08d340350ff5fab03be994a323b5d75adced3a1b028fb0a942024f74`;
preserved XML SHA-256
`ede3813e68f90d5501d65596a31436d682ff9963e812c1106656791f48bfc4c4`.

Full household entry previously projected every member's native availability
but checkpointed only the selected Sim. `checkpoint_members` now checks the
complete existing roster, preflights every hybrid companion, and captures each
through the existing raw receiver before any projection. `cas-household-commit`
binds the exact retained entry/PID/profile/candidate and per-member pending
hashes, observes everyone before plans, keeps only named Sim/form edits, and
restores other changed owners plus every captured availability context. It
reuses the selected member's already-observed journal without replay. Dynamic
core-tick/queue counters cannot be mistaken for a changed runtime identity.

V100's native full-household editor reports mode 0 and actual Alien type 2.
Fourteen panels acknowledge exact edits: nose, eyes, mouth, ears, skin tone,
hair, fullbody clothing, head skin details, eyelashes, lips, earrings,
necklaces, rings and eyebrows. The body skin-detail catalog has no different
eligible item; it does not count as edited. Only the Alien stored and active
records change (outfits, facial attributes, genetics, skin tone). Other owners
and companions remain exact. All five independent context/appearance commits
verify. Alien → Vampire → Alien advances 2,420/2,416 real simulation ticks with
no unintended household delta. The controlled normal save produces SHA-256
`4cddc75fd958c2b154cf50d5cc49c1f2209ef77467d002a0b1797cc4bf9294a3`.
V101 cold load retains all 40 appearance owners before and after 2,343 ticks.
The first Resume observer times out after accepted input; fresh native reads
prove the loaded household without another Resume input.

V101's region traversal calls a controller-only highlight method which is
absent on PC. V102 uses the public native selection grid and the exact imported
TattooBodyData definitions/filter, checks native selected-index/type agreement,
and emits the normal native region-change event. V101's intermediate reflective
lookup fails with Error 1069 (unbound `flash` scope); that failed query remains
evidence. The bytecode verifier now requires the exact imported class/data
access and limits region/layer native services to reviewed literal getters.
The native GUI treats null layer storage as an empty region; the bridge admits
that only with two exact false native part/paint predicates. Unknown/occupied
storage stays rejected. The workbench visits every actual returned tattoo
region and uses exact ordinary layer IDs while preserving medical layer 127.
An empty catalog/family cannot create a blank layer.

The V101 default-region edit acknowledges body type 45, layer index 0/id 1,
EA part 399362. Native SaveAndExitCAS then returns false. One semantic Undo
removes the selected part; a second removes the empty layer. The corrected
acceptance returns to Live with no changed stored lanes; every member's
context commit verifies. The normal saved file remains unchanged throughout
this rejected/undone pass. Tattoo acceptance/retention is **not** certified;
the native rejection's cause is not inferred from acknowledgement alone.
V102 passes **1,882 frozen tests in 324.233 seconds** and is a development
candidate, SHA-256 `2b469d8d7858f8af6709bf7a62059e1609f8d75f15587a374fcb47a5ba1f8e5f`.

Private complete evidence remains outside Git:

- `multi-v100-full-cas-entry.json`: `c67e5117d45c3b474aeb47d43e7666ed09b64ad922495c9cb639cf9c122704c7`.
- `multi-v100-alien-household-commit.json`: `c0478085dc8c96e9812dab0bc83ed87ee300175ee7954696ad3f238c5817d29b`.
- `multi-v100-full-cas-alien-to-vampire.json`: `1c266bed462f66e92c9496cdf02345af24f970356e3f4bef93c38d0cafa2783f`.
- `multi-v100-full-cas-vampire-back-to-alien.json`: `113a9fe230d1631748735558aa4cefd8c27171db8d5a344429a3cb3877eb69c7`.
- `multi-v101-alien-cas-cold-settled.json`: `d04aa5466b36645db5b98117e4db30ef86f2c7127fb631330e0cf30c0c7cdc8d`.
- `multi-v101-alien-default-body-tattoo-edit.json`: `a7056a35b374565f6c943c843946b092b5e1aef1305b2d72696bfbc15be61093`.
- `multi-v101-alien-tattoo-cas-return.json`: `a17daa4f256f35ac7e949fd5f58242f13ada98565a5d3d3795c282501def3cf3`.

All-member/all-panel edits, several edited members in one visit, ordinary
phone/MCCC entry and complete native Tray round trips remain open. No
production readiness or performance increase is claimed.

## October 14: queued body-hair initialization, V95–V97

The two fresh companions' V94 active genetic deltas add four body-hair parts,
using different variants from the preferred growth list. Their face/body
genetics, preferred list and every stored form remain intact. The indexed
normal save's root genetics exactly match both original active and stored
Alien records, ruling out the proposed root serializer mismatch for this
failure. V95's refresh guard fails to install because its signature check
incorrectly treats EA's required `stat_cache` argument as optional. V96 fixes
that signature and verifies installation on all five trackers, but reproduces
the same changes after 2,443 actual ticks. Neither is a successful repair.

V97 binds the exact body-hair requests already queued during native loading
to their original native tracker, Sim, form map, current kind and immutable
incoming appearance owners. The first dispatch consumes that capability.
Only unchanged matching queued entries are removed, and only if the complete
current appearance still matches the loaded source. Changed requests, other
body types, newly edited appearances and later growth/shaving stay native.
The original dispatch runs once with the remaining requests; no save file,
previous bank or reconstructed Sim supplies appearance authority. The bounded
runtime receipt records before/after field hashes and the exact suppressed
initial requests. The module runs at lifecycle/growth boundaries, with no
new render/frame polling or performance-gain claim.

Actual V97 results on the reused five-member household:

- Both cold-load comparisons pass all **35 stored plus five active owners**,
  including all twelve currently readable appearance/outfit fields per owner.
- Native time advances **2,336 ticks** between the paused captures.
- Native dispatch receipts retain unchanged full appearance hashes and skip
  the four queued initial body-hair slots; unrelated requests remain native.
- Initial proof SHA-256:
  `6c2312a8529742bb11a918937e068db403ddb8f1779e5fcbac9c4fa7329dd55b`.
- Settled proof SHA-256:
  `eca38a4204d49f695d040b9208d0acafef180866502a385f3d60630d28ae3a09`.

The first V97 switch attempt stops before native mutation because its old
test bank is uncertified for this runtime. Twenty successful fresh Live
checkpoint/observe/prepare/commit commands refresh all five banks from the
current native owners, retaining every appearance unchanged. They are not
CAS entry/edit proof. Their complete receipt SHA-256 is
`5aea0048e15b5cfa4f197a6fbe4c6bcc70893c3e578c654b4b324b6be6b61e4a`.
The earlier
25-step run and failed unselected Alien-to-Human transition remain retained.
All-category/all-member CAS and full production acceptance remain open.

V95 and V96 normal CLI unsaved exits preserve every disposable save/backup,
without a new native crash. V96 and V97 launches acknowledge the exact EA
permission window through the saved background broker. The launcher now
waits on an unterminated live log append; completed malformed or competing
requests still fail exact validation. The earlier V95 refused handoff and
delayed actual start are retained, rather than issuing duplicate launches.
Two V95 pack announcement cards were dismissed through recognized game-window
Close controls without foreground/cursor changes; their recognition helper
remains private test tooling, not a shipped general-purpose dismissal feature.

Final frozen V97 source/tool suite: **1,854 tests pass in 322.029 seconds**.
Candidate ZIP SHA-256:
`3787d65daa8432b16b4074ee508b7e077667359c1550898fea79fae87e33591a`.
The build verifies 85 Python 3.7 modules, seven packages/206 resources, and the
unchanged native DLL. This remains a development candidate pending the open
production workflow gates.

The next V97 whole-roster run passes six targeted transitions, then fails
strictly on the original Spellcaster's active outfit at step seven. Its
incoming Everyday row has ID zero and no `parts` field. Native progression
fills that empty placeholder and appends category-5/category-9 rows. All
existing non-ID row bytes, root unknown bytes, genetics, other appearance
fields, stored owners and companions remain intact. The failed strict receipt
stays unchanged. `household-stress` now classifies this exact empty native
initialization separately: a positive-ID or part-containing original cannot
qualify; all existing metadata/unknown bytes must remain exact, and additions
are limited to the inspected OutfitData generation fields. It never counts
such generation as an actual CAS edit. The rerun remains a separate proof.

## V98: edits before the first unpause

V97's conservative whole-appearance match would leave an old queued load
update native when a fresh edit had already changed the appearance. V98 adds
per-slot native request generations. An exact original native owner and
unchanged pre-readiness request generation authorize skipping only that
old initialization request. A later request remains native even at the same
numeric level. A newer appearance is never replaced with the loaded snapshot.
This capability is consumed before the single native dispatch and never
reconstructed from a historical bank.

In the actual five-Sim game, the CLI changes the original Alien's equipped
lipstick hue while the newly loaded household remains paused, before any
simulation progression. It then advances **2,360 simulation ticks**, verifies
the hue remains **0.1500244140625** (the requested 0.15 encoded in Q14), and
checks every returned field on all 35 stored and five active owners against
the fresh edited state. There are no differences. The dispatch receipt
explicitly reports `load_appearance_verified: false`, exact native ownership
and unchanged fresh appearance after skipping the old queued slots. Undo
then restores the entire original household appearance inventory exactly.
Receipt SHA-256:
`e3f2a8f98ecfe7a18d16271818332220309d78d9caf2cf2ba2502752e69a2594`.

The V97 generation-aware switch run passes 19 targeted transitions and stops
on an unselected companion changing Alien to Mermaid during simulation. A
separate complete comparison proves departing Alien edits were retained,
the active Mermaid matches its prior stored owner, and every other returned
field/form stays exact. Its original failed receipt remains immutable.
The CLI now classifies only such completely verified companion transitions;
it does not claim their trigger or tolerate changed/missing source/target
fields. Unknown/composite forms and merged/lost edits still fail.

Frozen V98 source/tool suite: **1,857 tests pass in 258.933 seconds**.
Candidate ZIP SHA-256:
`44c9702143c4b057a321df466d9e221739fe74900d3ad47c92b43d6429d3a817`.
The build retains 85 compiled Python 3.7 modules, seven packages/206 resources
and the unchanged native DLL. The protected original remains read/copy only.
This is still a development candidate; full CAS/MCCC/Tray production gates
remain open.

## V98 complete switch run and V99 normal-save repair

The final V98 repeated run completes **all 45 targeted transitions**, nine
per member, including Alien → Vampire → Alien and Mermaid/Werewolf/Fairy/
Spellcaster/Human/Alien on each. Every step checks all five members after
**1,465–2,478 actual simulation ticks**. Two observed unselected transitions
retain their fresh departing edits, exact prior target and every other stored
field. One bounded native empty outfit initialization is recorded. None of
these observations counts as an actual CAS edit. Complete proof SHA-256:
`5aadb96c224094967087ed6907795d05a17a074edccd88aca05286e4ec16fdea`.

The subsequent controlled V98 normal save succeeds and produces Slot02
SHA-256 `bca9825bd9609efec1fd72c7b09343c79d35fb3914e047eeb68fc7aca4ba5c3a`.
The post-save whole-household comparison then **fails** because the original
and one fresh companion's active `physique` changed. Every stored form and
other appearance field remains intact. Native `SimInfo.save_sim` calls
`_save_sim_base`, which invokes `_set_fit_fat` after the occult serializer has
already preserved the stored owners. The active body is recalculated from
shared fitness statistics, even when its independently edited CAS physique
is different. The file-write/seal success is not appearance-retention proof.

V99 scopes the existing exact-owner physique suppression around the actual
native `save_sim` for initialized hybrids with distinct existing form owners.
The original serializer runs once, retains all other data and leaves the
scope on every exit. Genuine gameplay fit/fat calls, other Sims, ordinary
pairs and unproved/aliased owners retain native behavior. Five regressions
cover saved/runtime physique, gameplay and another owner, exceptions,
single-pair/alias refusal and cloning/idempotence.

On actual V99 cold load of that saved household, all 35 stored and five active
appearances match the complete pre-save baseline, before/after **2,324 real
simulation ticks**. Both changed active bodies are restored from their
immutable stored owners. The serializer guard is installed on all five.
Settled proof SHA-256:
`9a1c9676170d21bae20c8c03855447b0322c2e574122b14c3fd452311097ba5c`.
The corrected V99 normal save now also passes the complete whole-household
comparison, including every active physique. Exact fresh Native checkpoints
refresh all five banks without changing any appearance. Normal Slot02 becomes
SHA-256 `13d2217c48a47c513cdc7754c160f86619d7c432a49f8ded0274f2c2b0f455db`.
Post-save retention proof SHA-256:
`242db5840b6450a026cdb8c82046b52d685ea4a44d17d44f294e522922206f5d`.
The baseline SHA-256 for the corrected save/cold check is
`85798f61ebd209dfe91a6e7990721669635f549d46c76de4389927e750a26eb8`.
Cold restart of this exact corrected save now also passes all 35 stored plus
five active owners before and after **2,359 actual simulation ticks**. Initial
proof SHA-256:
`61f0be8bc524fadfb7d89ea0039d8ffa6de21182711a686ec3b59afb39e6e4ae`.
Settled proof SHA-256:
`3feba5bf05a2c6df2a8e8a24dfd970d956a781b2a215b8bd2418a3186c1b025d`.
The exit command loses its final native input acknowledgement while the
process shuts down. Its unresolved receipt is retained without a repeated
click. A separate read-only closure observation proves the process is absent
and every save/backup remains unchanged before the one subsequent launch.
No successful button acknowledgement is invented from process absence.

Frozen V99 source/tool suite: **1,862 tests pass in 268.429 seconds**.
Candidate ZIP SHA-256:
`37a4a99487bf904481f98e54a8ccb367782ae855e43e787a5ee44e84662c4d0a`.
Protected originals remain read/copy only. The V98 intentional normal save
changed only the disposable Slot02 and its native backup family; its later
normal unsaved closure preserved those files exactly.

## Earlier October 13 findings

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
