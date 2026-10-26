# Native CAS forms: shared Human and EA portrait layout

## Owner priority: merge performance, 2026-10-24

Performance engineering is the first priority; visual polish runs in parallel.
Retain the donor panels, sliders, favorites and hide features while Apex owns
catalog geometry and its 2–32 column controls, with 20–160% requested card sizes.
Fit the requested column count first and expose any viewport limit honestly.
Keep the catalog in its compact footprint. Increasing column count, card size
or spacing must never widen it across the Sim, face, traits or other controls.
Fit additional columns within the reserved catalog area, using native logical
and panel-local coordinates. Preserve requested values separately from the
effective fit; effective card size may be below the size slider's minimum.
Test resizing and UI scaling as well as the ordinary viewport.
Eliminate competing geometry
writers and repeated category rebuilds. Move suitable immutable CPU work off
the game/UI/render threads with bounded workers; do not move game objects or
thread-affine engine calls onto those workers. Choose concurrency from measured
work and hardware capacity, rather than maximizing utilization as an end in
itself. Keep the permanent guard and all complete-field checks. Qualify actual
click-to-result timing and frame-time spikes separately from offline worker
benchmarks; neither a Rust rewrite nor a successful build proves hitch-free play.

Runtime behavior must work for arbitrary Sims, households and player-created
looks. Test-household identities and appearance fixtures are not runtime rules.
Bind each operation to the selected save, Sim, independently owned form and
outfit; never substitute a test Sim's appearance. Reuse display controls only,
then bind fresh owner-specific data. Keep metadata and native bytes separate.

Saving, loading, importing and exporting must preserve every independent form
through every supported entry point, including normal Save/Save As, household
travel and reload, CAS acceptance/cancel, phone/MCCC, local Tray and Gallery.
Normal browsing controls must retain EA's own availability rules. Do not use an
Apex manual-review lock as a general UI/save-lock predicate. Automatically
settle only a fully authenticated native return, preflight every captured member
before committing any, and revalidate the entire household after the last write.
The permanent preservation guard remains active at actual serialization. A
clickable Gallery icon does not qualify its import/export round trip; test the
native output and reload all appearances separately.

Owner-confirmed requirements: 2026-10-17. This is an implementation and QA
checklist, not a claim that the current candidate meets these requirements.
It supersedes the earlier user-facing layout that exposed canonical, active
and named implementation records as separate form choices.

## Latest catalog evidence: 2026-10-26

V351 fixes the original six-column Hair PageDown failure: one-row return binds,
draws and selects only six entering cards, reuses the other 42, and constructs
none. Actual Body 12-column/35% sizing, right-edge grow/shrink 200px, nine native
button exclusions and overflow navigation pass. The broader sweep still fails:
Bracelets repeatedly replans without publishing its current category, leaving
stale previous artwork. Hair 12-column/35% scrolling also exceeds the ten-second
deadline; sampled video retains old cards until a late publication. This is
not instant or a blank-free/FPS release pass. All 195 records remain exact after
the failures and raw native Cancel, all five original-only commits complete,
normal unsaved exit succeeds, and all 21 save/backup files stay unchanged.

The exact clean Source successor `371982bf` passes 3,927 cases, with zero failures
or errors and 335 explicit skip entries. That does not close runtime gates.
The next candidate gates the native selectable PositionCells override before
its unconditional selection tail, preserves direct feed/selection routes, and
records bounded native event kinds. This fixes a proven callback defect; its
being the sole Bracelets cause remains unproved. See the
[actual V351 report](../Reports/CAS_CARD_SCROLL_AND_CATEGORY_VALIDATION_V351.json).

## Earlier evidence: 2026-10-20

V215's full regression passes 2,695 tests. Its cold Live pass retains all forty
native appearances, but actual CAS acceptance is rejected by the new complete
cache-copy check. It never reaches the original native acceptance service or
the Live comparison; do not record this as a successful direct fix. The owner
authorized discarding test edits and reloading. The exact disposable process
was ended, and all twenty save/backup files remained unchanged.

V216 corrects the verification context: the complete native serializer includes
the Sim shell as well as AppearanceData. Its witness now copies the exact source
shell before assigning the cache's copied data. No serialized field is excluded
from the comparison. A native regression includes differing shell metadata,
and twelve native targets pass. Twenty-six seal and twenty-six upgrade checks
pass; seven packages, 105 Python 3.7 modules and 208 independently Rust-validated
resources build. Actual V216 acceptance now verifies all five complete caches
at generation 42, without selecting other members or writing their appearance
graphs. Direct isolation nevertheless fails for the same three unselected
members: their incoming cores differ from their own independent final owners.
The loader refuses those cores. The separate no-edit disposition restores all
forty native appearances, retains all 155 named looks and leaves every save
unchanged after simulation advances. A subsequent normal unsaved exit succeeds;
that single exit does not close the shutdown-stability gate.

V217 addresses the later household serialization boundary rather than weakening
the loader comparison. Only the pinned CAS household caller may project each
form's own final native appearance into its matching outgoing record. A member
never bound to the editor also retains its own entry appearance at the root.
The game's own parser validates a detached result; a complete field comparison
includes unrelated and unknown data before the actual output is replaced and
read back. Failures restore the original output and invalidate acceptance.
Thirteen native targets pass, including foreign identities, caller/generation
gates, parser rejection and rollback. An independent oracle using the installed
game's schema verifies all seven native genera, unknown fields, defaults and
unchanged gameplay metadata. This is not actual-game acceptance proof; the
five-member CAS/Live qualification fails the direct fix. All five export
receipts are absent, and the observed call paths never reach the targeted
caller. The same three unselected members change. The separate no-edit
disposition still retains all forty native appearances and 155 named looks,
with every save unchanged. The owner's earlier process exit was confirmed as
an intentional restart, not an observed crash.

V218 therefore prepares the actual CAS household roots immediately before
native acceptance. It resolves each imported entity from the controller's
bounded member list and stages every complete packet before writing any root.
Each occult record comes from its own final graph owner; never-selected members
also retain their own active appearance. The native attributes copy service
receives only a detached, game-parser-validated packet. Complete readbacks
check unknown fields and unrelated gameplay data. A failure restores every
attempted root and blocks acceptance. The unused outgoing-export hook is
removed. Native fixtures cover selected and unselected roots, duplicate and
foreign members, aliased attributes, parser rejection and multi-member rollback.
V218 is withdrawn before actual CAS entry or native arming: a final inspection
of the installed export service identifies an embedded attributes object where
the adapter and its original fixture assumed a pointer. The unarmed native
status is retained; no household acceptance or save was submitted. This is an
adapter defect caught before exercising that path, not a qualified game pass.

V219 corrects the inline object address and pins the inspected export/copy
boundary. The regression fixture now uses distinct embedded attributes objects
with a shared vtable and rejects a vtable address as a copy destination. All
thirteen native targets pass, including complete selected/unselected readbacks,
parser failures and multi-member rollback. Twenty-six seal and twenty-six
upgrade checks pass. Seven packages, 105 Python 3.7 modules and 208 independently
Rust-validated resources build. The actual five-member V219 run rejects native
acceptance: a complete prepared root readback differs from its projected packet.
Every original root is restored and read back, and EA's acceptance handler is
not called. The same middle three members remain unselected. The test session
is canceled and closed without saving; all save/backup files stay unchanged.
Do not classify the rejection as a direct isolation or Live-return pass.

V220 adds bounded field-level diagnostics at this exact rejection boundary.
They cover root fields, attributes, tracker fields and each independently keyed
occult record, reporting field paths, byte counts and SHA-256 values. No field
is excluded from verification and no private appearance bytes are exported in
the status report. The original-root rollback remains mandatory. Thirteen
native targets, 26 seal and 26 upgrade checks pass. Actual V220 diagnosis isolates
the unselected Werewolf member: root field 63 (pelt layers) disappears, and
occult record 1 field 17 (Human genetics) changes. Both full original roots and
all other roots are restored. Independent owner exports retain the expected
Human genetics and Werewolf pelt, so those captures are not the failing source.

Inspection confirms that the stock serializer regenerates paired form records
after copying attributes and chooses pelt data from its paired child. V221
therefore preflights complete detached packets, then projects the final native
serialized output for the exact prepared CAS roots. It verifies the current
controller, imported entity, scope and owner generation; ordinary Live/save
exporters are excluded. Root memory is not rewritten. The game parser and full
output readback qualify each actual projection; failures restore the original
output and invalidate acceptance. Fresh per-member receipts and bounded caller
traces distinguish preparation from an actual export. Cancellation and scope
retirement clear the authority. Thirteen native targets, 26 seal and 26 upgrade
checks pass, including lost pelt/Human genetics, root immutability, stale scope
and output rejection/rollback. Actual five-member acceptance succeeds, but all
fifteen observed exports use copied objects rather than the prepared editor
roots. No output projection receipt qualifies. The same three never-selected
members change before the guard; direct isolation fails. The controller matches
throughout, so the missing authority is the native copy lifetime, not the Sim
identity. Do not widen the hook to identities alone. Edited-category persistence
and actual-save readiness remain open.

V221's separate no-edit disposition and guard retain all forty native
appearances and 155 named looks after simulation advances; all twenty save
files remain unchanged. Its normal unsaved exit also succeeds. V222 follows
the inspected native constructor/assignment chain instead of treating the
copied household as the original editor roots. A copy inherits authority only
from a currently prepared root during acceptance or an already authenticated
copy in that accepted scope. Sim identity, native entity and final owner
generation must all match. Reassignment and destruction revoke the old proof;
prepared-root destruction retires the authority. Unrelated exporters with the
same Sim identity are still excluded. The lifetime map and propagation depth
are bounded; copy/destructor hooks take an atomic disabled path outside this
short CAS scope. Thirteen native targets, 26 seal and 26 upgrade checks pass,
including copied output, propagation, overwrite, reuse and source retirement.
Actual V222 qualification still fails. Three late outgoing copies have verified
projection receipts, but the earlier exports and the two selected members have
no copy provenance. Two unselected members still differ before the guard. One
native fault invalidates the acceptance qualification; later successful member
receipts do not establish its cause. The separate guard retains all forty native
appearances and 155 named looks after simulation advances. All twenty save files
remain unchanged, and normal unsaved exit succeeds.

V223 validates the earlier native CAS household dispatch before EA queues its
copies. Only the pinned CAS caller may seed it, during prepared acceptance.
The native household/controller identity, complete bounded roster, unique Sim
and entity identities and every prepared owner generation must agree. Staging
publishes all output roots together; malformed, foreign, incomplete or stale
dispatches are blocked before the original dispatch call. Subsequent native
copies inherit that scope; unrelated matching IDs do not qualify. A bounded
eight-entry fault history retains phase, scope and message even after later
successful exports. Thirteen native targets, 26 seal and 26 upgrade checks pass;
seven packages/105 Python 3.7 modules and 208 Rust-validated resources build.
Actual V223 verifies all five outgoing packets, each with dispatch provenance
and generation 42. The retained fault identifies an adapter lifetime error:
normal destruction of the first editor root invalidates the already completed
handoff. The strict load extension consequently does not run, two appearances
still differ before the guard, and direct qualification fails. The separate
guard retains all forty appearances and 155 named looks; every save file stays
unchanged and normal unsaved exit succeeds.

V224 tombstones retired editor addresses while retaining the independently
owned, authenticated dispatch copies and their verified receipts. A queued
dispatch copy may outlive its editor/controller; Sim/entity, scope and final
generation checks still apply, as do complete parser/readback verification and
output rollback. An unauthenticated handoff still fails. A reused retired
address cannot enroll a new object by matching IDs. Once all actual outputs
verify and their copies are destroyed, tracking disables and every editor
authority retires; the strict loader can still use the captured graphs and
receipts. Thirteen native targets, 26 seal and 26 upgrade checks pass, including
freed editor/controller, surviving descendants, reuse and failed handoff cases.
Seven packages/105 Python 3.7 modules and 208 Rust-validated resources build.
Actual V224 passes the five-member no-edit household cycle. All forty native
appearances match before the guard, including the three never-selected members.
All five dispatched output receipts and strict native-load extension receipts
verify at generation 42; native acceptance remains qualified after all editor
authorities retire, copy tracking disables and no native fault is recorded.
The separate no-edit disposition retains all forty native appearances and 155
named looks after simulation advances, with every save/backup file unchanged.
This qualifies the previously failing no-edit path, not edited-category, MCCC
or save/Tray round trips. Those remain open. The next same-process CAS session
tests distinct Alien/Vampire category edits across all five members. No core
comparator or preservation guard is weakened; actual-save readiness remains open.

V214's untouched-member acceptance test fails direct isolation: members two,
three and four return changed Human genetics and/or active outfits/paint.
The final-graph loader refuses their mismatched incoming cores. The separate
no-edit disposition restores all forty native appearances and retains all 155
named looks after simulation advances, with every save unchanged. This extends
the open regression to members never selected in the editor. Do not weaken
the core comparison or classify these changes as user edits. V214's corrected
full fixture run passes 2,690 tests; that does not override the runtime failure.

The subsequent unsaved exit produces crash category `0x14117dba1`. The process
is closed and all disposable save/backup files are unchanged. The report is
retained, and the installer stops rather than labeling this a normal exit.
Shutdown stability is a release gate alongside form persistence.

V215 adds a pinned native SaveAndExitCAS adapter that synchronizes the selected
model and settles every materialized household member's canonical cache without
selecting other members. Complete serialized readbacks precede the original
service call. The native graph mutex is released around EA's handler. The GFx
Boolean result, not its separate handled return value, qualifies acceptance;
the native CancelCAS handler invalidates it. Fresh accepted generations gate
the loader, so Cancel cannot accept paint-only edits. Twelve native targets
and fifteen loader/acceptance checks pass. The actual acceptance failure above
keeps these fixes unqualified despite the full regression pass.

V214 implements a load-time schema completion for native CAS: the current
unfinished session's final native owner graph can supply pelt/custom-texture
fields omitted from OccultSimInfo. The save GUID, household, Sim, session and
logical owner must agree; every incoming core field is compared before a
detached record receives extras. Unknown native fields remain intact. Ordinary
loads do not query the graph. Stale/foreign sessions, changed cores, missing
owners and occupied extension fields refuse the entire projection. Decoding
these two fields during native form creation is separate from the always-on
preservation guard. Ten new loader checks pass; actual CAS-exit qualification
is running in the single disposable profile and is not yet claimed.

The same candidate accelerates canonical transaction hashing while preserving
the existing complete SHA-256 identities. Four compatibility checks cover
Unicode, uint64, floats, unknown fields, invalid/cyclic input and the Python
encoder fallback. An offline read-only Python 3.7 benchmark on the roughly
24 MB test bank measures the old encoder at 0.71–0.73 seconds and the accelerated
path at 0.10–0.11 seconds, with identical hashes. This is not an in-game commit
latency measurement. V212's real review operations still held the game thread
for 20–61 seconds; end-to-end responsiveness remains a release gate.

V212's five-member CAS matrix now passes all thirty visits: each member selects
the complete Human/CC Werewolf appearance, beast, Fairy, beast, Fairy and its
original owner. In-process native callbacks and model readbacks agree on the
selected rendering genus; the Werewolf animation flag is set only for the beast.
A reviewed game capture shows a full Human head and body. A subsequent export
compares every field of all 195 captured records against the pre-entry reference;
none changed, and all save files remain unchanged. Those are internal records,
not 195 player-facing choices or proof of edits, copying or save/Tray retention.

The subsequent CAS exit reproduces the unresolved direct-isolation failure:
the Werewolf and Fairy members' Human paint changes. The separate no-edit
household disposition and guard restore all forty native appearances and
retain all 155 named looks after simulation advances; every save file remains
unchanged and Live ends paused. This is a guard pass, not a direct-fix pass. Both V212 CI
workflows pass. These scoped passes do not make the candidate an actual-save
release or complete the selective EA checkbox-panel requirement.

V212 passes all 2,676 local regression tests. It adds two recovery/CLI
corrections found during actual household QA. A
hidden canonical preimage can share the rendering genus of a Sim's visible
active form. Requesting that backup through the form-selection CLI stranded
V211's UI acknowledgement. The CLI now requires one exact owner in the fresh
player-facing form catalog before staging a native selection; unknown,
duplicate and hidden owner IDs are rejected without a mutation. The household
test resolves each member's own logical form bindings rather than assuming
`native/32` or `native/64` is always the player-facing record. The failed request
is retained separately and is not replayed.

The following load exposed a real Windows PID-reuse bug: the old Sims PID
belonged to Opera, so the old PID-only check blocked saved-look admission.
Recovery now queries the executable image through the same held, query-only
handle. Live Sims names and failed/ambiguous queries remain conservative;
unrelated applications no longer count as the old Sims runtime. UTF-16 length,
64-bit handles, denial and cleanup are tested. A real Windows read-only probe
distinguishes Opera from the running Sims process. In-game V212 admission now
succeeds for all five members; all forty native appearances remain identical
through 2,961 simulation ticks. The stored Human/CC initialization again
preserves every native appearance and other named look, with save files unchanged.

V211's actual EA Fairy-card click now selects the independent Fairy owner,
renders genus 64 and updates the occult icon, retaining membership 127. A game
capture verifies the Werewolf model is gone. Another actual CAS capture verifies
the Human/CC Werewolf look has a full Human head and body; the separate beast
view remains available. One member completes Human/CC, beast, Fairy and original
form visits. That is distinct from the still-running five-member V212 matrix,
CAS return, Live geometry and save/Tray release gates.

V211 checkpoint (reviewed 2026-10-20): the frozen candidate passes all 2,671
local regression tests and 134 compiled-UI checks. The owner's Fairy picker
report exposed a dropped-click path: the hybrid handler refused input during
a pending readback while the stock panel still highlighted the requested card.
The corrected package retains the latest explicit choice for the same Sim and
CAS session, applies it only after the current operation completes, and uses
the actual bound native genus for the stock selection highlight. Negative
bytecode fixtures reject lost intents, foreign sessions, missing command
leases and inline native work. Actual picker verification remains open.

The retained built-in Human/CC Werewolf capture contained the beast's complete
outfit, physique and genetics. New captures seed every appearance field from
the one shared Human. This named look uses Human rendering in CAS and Studio,
while retaining its independent Werewolf gameplay lane and stored identity.
The explicit `lifestate human-look --id werewolf_human_cc --expected-sha256 ...`
repair retains the prior complete look in recovery history; inventory and CAS
entry never silently replace existing edits. Tests cover whole-body fields,
ordinary beast isolation, stale checksums and named CAS return to lane 32.
Visible CAS and Live geometry, repeated switches and save/Tray retention still
require actual-game proof before this is an actual-save release.

Menu work preserves the permanent guard. Save admission is validated during
zone setup and reuses a stamp-checked compact index until a file revision;
writer leases and external replacements still invalidate it. One paused Live
pie-menu cProfile sample per build measures generation at 228.4 ms in V208,
215.2 ms in V209 and 134.1 ms in V210. The seven save-lock tooltip checks fall
from 81.3 ms to 8.8 ms; all 525 AOP validity calls remain. These instrumented
samples do not establish unprofiled click latency, p95 or FPS. The native DLL
also releases its render mutex before real DXGI Present/Present1/ResizeBuffers;
an actual-hook regression reproduces the old message-thread stall and passes
with the correction. CAS Sync reuses one scratch graph and an exclusively
owned comparison baseline, while continuing full mutable-model comparisons
and canonical-cache repair. See the scoped
[responsiveness record](../manifests/cas-responsiveness-validation.json).

V204's full regression passes 2,645 tests. In actual full CAS, all five members
complete Alien -> Vampire -> Alien and return to their starting owners. A
linked, no-edit export retains every field in all 195 captured records;
unlinking is acknowledged. An actual Alien strip click measures 15 ms to the
bound native owner, excluding rendered-avatar readiness. All five native
portrait pairs remain complete. These passes do not qualify selective copying.

The subsequent no-edit CAS exit still merges Werewolf/Fairy paint into two
Human records. No other field changes. The installed generator patch is not
called on that path and therefore does not fix it. The permanent guard restores
all forty Live appearances and all five named documents after another 887
simulation ticks; save files and the ledger stay unchanged. Preserve the failed
direct-fix proof separately from this successful guard-only restoration.

The owner clarified that Werewolf howling leaks chiefly in CAS. V205 scopes
the inspected idle actor's animation membership to the exact selected native
CAS preview, without changing model, owner or gameplay membership. Twelve
native checks pass, including every native genus, ordinary/foreign contexts
and preservation of complete owner serialization. Actual actor reads verify
Vampire mask 4 with the Werewolf flag off and model membership still 127.
The first preview nevertheless starts with the combined animation mask until
a form switch. V206 also settles animation parameters at exact owner binding,
checks the actor cache, and skips an already settled actor. Its twelve native
targets pass, including a distinct named Ghost and foreign-member refusal.
V205's actual matrix now passes 37 visits across all five members, including
all seven native genera. The actor's Werewolf flag is set only for Werewolf;
each model retains membership 127. A complete follow-up export retains every
field in all 195 captured records, with no save write. These are internal
appearance records, not 195 player-facing form choices.

V206 still fails its first-preview check: the actor can be created after the
binder returns. Its no-edit export again retains all 195 records. V207 scopes
the inspected actor-construction caller too, with the same exact model, actor,
Sim and owner checks. The call-site bytes are pinned. Native tests reproduce
the late actor and construction during binding, retain opaque owner fields,
and reject foreign contexts. Twelve native targets and 49 seal/upgrade tests
pass. V207's actual first full-CAS entry now verifies Alien animation mask 2
with no preceding form switch, model membership 127 and the construction
callback recorded. Thirteen visits verify all seven native genera and the
original occult owner on all five members. The complete post-matrix comparison
retains every field in all 195 captured records; all test save files remain
unchanged. The first-entry check is distinct from the later member/form checks.
See the [scoped validation record](../manifests/cas-animation-validation.json).

The requested final link/copy interface is EA's existing checkbox panel,
extended to the independent selected pair, plus missing categories such as
tattoos. Retain its native visuals, layout and direction; scope preferences by
Sim AND form pair. Do not merely unhide EA's destructive stock auto-sync or
reuse its Sim-only link state across different occults. The floating whole-copy
toolbar remains interim. Partial copy/link isolation, undo and saved preferences
remain release blockers.

V203 checkpoint: the last frozen V202 regression passes 2,638 tests. V203
reproduces and corrects a native Link bug in which a no-edit Sync propagated
the whole appearance. Full native serialization now distinguishes edits from
refreshes, including opaque fields; the native test also checks later linked
edits, unlinking and copy isolation from a linked third form. Twelve native,
fifty-five selector and fifteen fast/pair UI checks pass. V203 cold loading
retains all forty native appearances and five independent named documents
through 740 simulation ticks, with the save/ledger unchanged and Live paused.
The pinned Human-paint patch is installed on all five members. The actual CAS
return before guarded restoration, pair presentation, real link/copy isolation,
complete member/category coverage and Tray/Gallery remain open gates. V203's
full regression and game checks are in progress. It is not an actual-save release.

V200 cold-load checkpoint: all five saved independent named-form documents
reopen and all forty native appearances match before and after 946 simulation
ticks, with the save file and seal ledger unchanged and Live paused again.
This follows the fourth member's actual purple Fairy wing-card edit, retained
through Fairy -> Alien -> Fairy, five-member acceptance, forty-owner Live
verification and Alien -> Vampire -> Alien -> Fairy. The 195-owner comparison
changes only the intended Fairy outfit/genetic/pelt fields; the outfit decoder
finds only the wing part changed in category 9, index 0. V199's named-metadata
upgrade refusal remains retained as a failed proof. V200 adds the exact audited
V198 metadata predecessor without granting native restore authority; 92 focused
save/upgrade/return checks pass. V200's complete regression passes 2,616 tests.
Native-menu Alien -> Vampire -> Alien now stays visible after both redraws.
Initial empty wing paint data, semantic wing selection, every-member/category,
native Link/Unlink/Copy and household Tray/Gallery remain open. This is not an
actual-save release.

V197 checkpoint: EA Human artwork is visibly verified in full CAS, replacing
HUM without adding a second Human owner. The owner confirms the third Sim's
appearance is intact; its stale portrait does not justify changing saved looks.
V195/V196 cold loads retain all forty native appearances and all five saved
named documents after simulation advances, with save/ledger unchanged. Native
molecule restoration now routes choices through retained owners and corrects
the display genus separately from native membership. V196 exposes a real tooltip
type error during widget loading; V197 fixes the inspected API contract and
passes six molecule checks plus 143 compiled-UI checks. CLI entry now rejects a
new UI exception rather than calling a connected but broken editor ready.
Corrected native button switching and Fairy wing/material behavior remain open
runtime gates. Neither candidate is an actual-save release.

V194 menu checkpoint: the CAS strip groups variants under one life-state button,
including one Imaginary Friend entry with four independent variant owners and
a shortcut to the existing shared Human / Real appearance. Special artwork
references come from installed game tuning; native hover descriptions use
EA's tooltip lifecycle. The CLI can browse a family or return to all forms
without selecting an appearance. The package builds and focused metadata,
menu, catalog, control and serialized bytecode checks pass. V193's frozen
regression run passes 2,583 tests. V194 adds selected-button no-op behavior,
readable variant tiles, cached group metadata and a metadata-only V192 save
upgrade; 108 focused checks pass. Actual full CAS shows fourteen unique
life-state groups, thirteen installed occult/special icons and one Imaginary
Friend entry. Its four labelled variant tiles use their own game artwork;
Human / Real references the one shared Human. Native hover text is visibly
verified. Browsing leaves all five graph generations, selected owners and
logical bindings unchanged; clicking the selected Alien is a verified no-op.
Actual button clicks open Imaginary Friend and select the exact Spooky Kid
owner; Pegacorn and the starting actual Alien remain separately selectable.
A complete post-switch export retains every field in all 39 member owners.
This is menu/selection proof, not special-state gameplay or native link/copy
qualification. Human still uses text until shared portrait artwork is wired.

V192 now also completes distinct eyebrow, head skin-detail and earring edits
on the second member's actual Alien and Vampire. Nine readbacks retain all
choices through Alien -> Vampire -> Alien, followed by its original Werewolf
view. The complete 195-owner audit finds changes only in that member's two
chosen appearances (outfit/genetic fields); the other 193 remain identical.
A known ordinary eyebrow family works; the first catalog family's colour
request remains a failed result, not a qualified selection. This checkpoint
also completes all five receiver commits, retains all forty Live appearances
after 1,396 ticks and passes Alien -> Vampire -> Alien -> original Werewolf
with full-household checks and no added outfits. One normal save completes
under its original UUID, creates all five named seals and preserves all forty
post-save appearances. Its host observer initially stops too early; the CLI
now spends the remaining bounded timeout polling only the original request
instead of abandoning it after one short poll. Twenty-seven save checks pass.
V194 cold loading reopens all five saved named documents and retains all
forty appearances before and after another 685 simulation ticks, with the
save file and seal ledger unchanged and no native appearance restoration.
In-game menu presentation and exact variant selection now pass as described
above. Full-category/every-member coverage, universal shared-Human ownership,
native link/copy and household Tray/Gallery remain open release gates.

V192 development checkpoint: ordinary CAS selections bind an exact visible
parent and returned colour variant, with native selected-item readback. V191
actually applies different child earring colours to the second member's Alien
and Vampire, retains both through Alien -> Vampire -> Alien and restores the
starting Werewolf view. This is a CAS-only earring qualification. Its eyebrow
colour request remains a failed result: the palette widget changed its index,
but the native colour stayed on the base. V192 resolves the requested identity
from the refreshed widget's actual feed and avoids its duplicate refresh.

The second-member test also catches an initial portrait-binding race before
part editing. Explicit views consume only an unsubmitted automatic bootstrap;
readback requires the exact bound owner as well as its actual native genus.
Pending readback can poll owner metadata with the original nonce and one-frame
lease. An already-bound owner skips redundant bootstrap. Twelve serialized
bytecode fixtures, seven bounded preflight checks and eleven socket checks pass.
V191's frozen regression suite passes 2,575 tests; V192 passes 2,579 tests.

Cancelling the V191 test retains all forty original Live appearances and all
five memberships. Normal unsaved closure leaves every save file unchanged.
Closed-only recovery preserves every captured checkpoint and never invents an
inventory, CAS acceptance or reload pass. A stale CAS peer/captured guard still
requires explicit test cleanup after cancellation; automatic player cancellation
lifecycle, full category/member coverage, shared-Human Live/F11 ownership,
native link/copy and Tray/Gallery remain release gates. V192 builds 103 Python
3.7 modules, seven packages and 207 Rust-verified resources. It is a development
candidate; V192 runtime palette/member-switch qualification remains open.

V188 category-retention checkpoint: the first member receives distinct actual
Alien and Vampire eyebrow, head skin-detail and earring items through full CAS.
Nine selected-item readbacks pass through Alien -> Vampire -> Alien. Complete
committed exports and unchanged companion graph generations account for all
195 owners: only that member's chosen Alien and Vampire records change, in
outfit and genetic fields. The active visible owner is captured on departure;
a committed-only export taken before that departure is not a loss verdict.

After declining two unrelated self-discovery trait prompts, the original CAS
Accept is completed without replay. All five receiver commits pass. All forty
Live appearances match the intended CAS choices after another 1,163 simulation
ticks. Normal Save and Exit creates fresh five-member named-form seals. Cold
loading that exact file then retains the separate category edits, all five
independent Ghost documents and all forty native appearances after another
727 ticks, with save/ledger unchanged and Live paused. This is a first-member,
three-category test; it is not an all-category/every-member qualification.

The CLI now reconnects after the exact pre-queue transport refusal proving no
native request was created. Issued/unknown UUIDs and started operations never
enter that path. Five reconnect, 22 intent-journal, 16 workbench, 12 member and
30 form-navigation checks pass, alongside both CI jobs. A legitimate colour
family child absent from the filtered base list is still refused before write;
ordinary-part base/variant capabilities remain open under issue #7. The final
cold launch also exercises a successful EA-only restart to clear a blank stale
Qt permission surface; account and every save remain unchanged by the restart.

V188 checkpoint: the ordinary native Save and Exit path creates a fresh
five-member household seal with all independent named documents, writes the
normal save and exits normally. Cold loading that exact file reopens each
member's distinct Ghost metadata independently of Human. Every field in all
forty native appearances remains correct before and after 667 simulation ticks;
the save and seal ledger stay unchanged, no native appearance restoration is
requested, and the game is paused again. Repeated named inventory reads do not
rewrite the bank. The owner's protected original remains read/copy-only.

V188 also passes Alien -> Vampire -> Alien across all five members in Live,
with eighteen settled transitions including restoration of each starting form.
Each transition checks the full household: stored and active appearance fields
stay intact, every independent named document stays unchanged, no outfits are
added, and the normal save is unchanged. This is actual occult switching after
the saved-metadata cold load, not a Human-only test.

V187's frozen regression run passes 2,548 tests. Its first real metadata cold
load exposed an admission refusal despite exact native appearance retention.
V188 accepts an exact current saved native match without depending on an early
tracker-load sample, while divergent current fields still require a complete
matching load observation. It adds bounded diagnostic reasons and an exact
V187 schema-compatible metadata transition; this grants no native restoration
authority. Focused checks pass: 11 saved-name, 6 household-seal, 23 core-seal,
26 audited-upgrade, 55 CAS receiver, 18 save-admission and 9 save-lifecycle tests.
The candidate builds 103 Python 3.7 modules, seven packages and 207 independently
Rust-verified resources. Actual Save As, complete-category editing, native
link/copy, universal Live/F11 form ownership and Tray/Gallery remain unqualified.
This is a development candidate, not an actual-save release.

Current checkpoint: V182 completed 60 actual full-CAS form visits across all
five hybrid household members, with 20 distinct Human/Alien/Vampire/Ghost
physique edits. A second switching pass retained every marker. Complete native
exports cover all 195 captured owners: exactly the 20 intended physique fields
changed, with no unrelated changes or added outfits. These are body-edit tests,
not complete-category or special-gameplay qualification. The original small
fourth-member Alien gesture and its larger follow-up also passed.

CAS returned to the same Live Sim/household, advanced simulation ticks and was
paused again. The host recovered its acknowledged Accept intent after a
read-only zone-transition timeout, without replaying Accept. All five native
return archives were retained before any plan or commit. This exposed a real
boundary gap: EA's returned Live wrappers still held older canonical appearances,
although the native CAS graph retained the edits. No stale appearance commit or
save was submitted. The disposable session closed without saving; all twenty
save files remain unchanged, and complete pending/returned records are archived.

V183 projects the graph's captured logical owner bindings into the existing
explicit accept/restore transaction. Shared Human and the active Alien alias
are exact identities; named special forms cannot substitute for canonical lanes
by matching genus. Actual Live wrappers remain separate durable rollback and
concurrency evidence. Receiver tests prove separate Human/Alien acceptance,
Vampire restoration and independent Ghost variants. Focused checks pass: 55
receiver, 43 transaction, 2 projection, 10 engine, 67 return-observer, 13 household,
23 seal and 26 upgrade tests. V183 builds 100 Python 3.7 modules, seven packages
and 207 independently Rust-verified resources. Runtime CAS-to-Live retention,
full-category edits, copy/link, save/cold-load and Tray qualification remain open.

V184 separates pure historical graph-receipt validation from current-runtime
receiver authority, so a completed receipt can survive a cold load without
authorizing replay. Three projection checks cover this separation; the 55
receiver checks also validate a completed receipt under a later process ID.
The host CLI now defaults to full-household CAS; explicit native/MCCC routes
remain available. Runtime checks caught an accidentally requested single-Sim
entry before edits and refused household-member navigation. This is retained
as a failed test attempt, not a household qualification.

V183's untouched single-editor visit completed five receiver transactions;
a fresh Live audit exactly matched all forty saved appearances. Its next full
CAS entry then refused before native entry because the ready graph could not
be reseeded. This exposed a repeated-visit lifecycle gap, not an edited-form
retention pass. The session exited normally without saving; all twenty files
were unchanged and the five never-entered checkpoints remain archived.

V186 now also completes the second return and all five receiver commits. After
1,351 further simulation ticks, all forty Live appearances still match. One
controlled normal save, normal game closure and cold load then preserve all
five members, six occult memberships each and every field in all forty native
appearances. A further 750-tick selected-member reload audit passes without
appearance or bank restoration, followed by another full-household comparison.
The original profile remains untouched. This establishes the body-edit native
save boundary; it does not qualify every CAS category or Tray/Gallery.

That cold load exposed a separate named-form metadata gap: V186 certifies only
the selected member and cannot reopen independently edited Ghost looks as saved
variants. V187 captures all household bank members in one save group, retains
separate named documents, and distinguishes a new load tracker from later Live
edits. Saved metadata admission writes no native appearance; unsaved looks stay
in content-addressed recovery history. An explicit legacy draft import never
claims old uncaptured names were saved. The normal EA save generator now captures
and finishes the same group, including Save As, without a second save. Synthetic
checks pass for failure/cancellation, no replay, household isolation and named
reloads; the matching V187 runtime qualification remains pending. Native copy/link,
full-category edits, universal Live/F11 form semantics and Tray gates remain open.

V186 adds private completed-session retirement. Source requires verified
completion of every scoped receiver; the DLL requires the entire exact graph
generation roster, no active native view and a finished/disconnected transport.
Only then are the old detached graph/undo owners released. Installed hooks and
the armed roster remain ready for a fresh checkpointed import. Public research
commands cannot request retirement; the loader requires the held Source
completion object, and an attempted retirement is never replayed. Six Source
checks exercise the real loader validation, and eleven native checks pass,
including refusal for stale/missing members and successful fresh reseeding.
V186's actual full-household run repeats all sixty visits and twenty independent
Human/Alien/Vampire/Ghost physique edits. Complete returned native data matches
all 195 CAS exports byte for byte. All five explicit receiver commits pass,
including the separate Ghost choices; only the fifth completed receiver retires
the graph. The native counter verifies one retirement with the armed roster
retained and no imported graph. After 1,294 further simulation ticks, all forty
active/stored Live appearances match the intended logical CAS choices in every
captured field, and the game is paused again. All five named Ghost records match
their edited exports. No save was submitted. The frozen Source regression run
passes 2,506 tests. A second full-CAS visit in the same process then passes
thirty Human/Alien/Vampire/Ghost visits across all five members, retaining every
distinct body edit. Its complete 195-owner audit matches every expected field,
including the untouched outfit and skin-detail data. The host observes EA's
initially selected captured household member without replaying entry or sending
selection input; 25 entry and 26 transition checks pass. All-category edits,
native copy/link, save/cold-load and Tray qualification remain open.

- [x] Five-member, sixty-visit distinct physique-edit matrix and exact all-owner audit.
- [x] Five explicit graph-to-Live receiver commits, with independent Ghost choices.
- [x] Post-commit Live advancement and forty active/stored full-field comparisons.
- [x] Completed native graph retirement and fresh same-process full-CAS entry.
- [x] Thirty reopened form visits and complete 195-owner field retention.
- [x] First-member Alien/Vampire eyebrows, head skin details and earrings through CAS/Live/save/cold-load.
- [ ] Qualify distinct edits in every applicable category and native copy/link.
- [x] Native body-edit save/cold-load retention for all five members and forty appearances.
- [x] Five-member saved independent named metadata and ordinary native Save and Exit.
- [ ] Qualify actual Save As and independent named metadata in every editing route.
- [ ] Qualify household Tray/Gallery retention.

V182's native-owned UI transport completed this matrix without the previously
reproduced allocator crash. It does not establish universal crash freedom or
prove a root cause. Eleven native checks pass; diagnostic owner-memory guards
remain enabled in this development DLL. This is not a production release.

A same-build V180 session successfully changed one actual EA body preset on the
fourth member's actual Alien with the bridge connected. Its exact native preset
and physique changed. This does not establish an exact EA slider comparison.
The session was cancelled and closed normally without saving; all twenty saves
remained byte-identical. Production, native copy/link, complete-category and
save/Tray gates remain open.

V175 presents one shared Human and twenty logical form choices while retaining
all 39 captured storage owners per member. A real full-CAS image shows the
selected Alien below its shared Human disguise, preserving EA's Alien ordering.
The native graph also defines the independent Ghost/Human and other special
pairs. This is partial presentation work: EA copy/link controls are not yet
connected to these graph owners, special icons and some native labels are
incomplete, and Live/F11/Tray still need the same logical-form contract.

V175 completed twelve distinct Human/Alien/Vampire/Ghost body edits and eighteen
visits across three household members. It crashed during the fourth member's
first body-slider edit after member and Alien selection had completed. The dump
faults in the native UI allocator at `TS4_x64+0x112c645`; the corrupting operation
is not identified. There was no CAS acceptance or save. All twenty existing
disposable save files still match their pre-launch hashes. These results do
not qualify the household, full-category edits, CAS return, save or Tray gates.

V176 fixes a separately reproduced cache mismatch: the exact visible logical
owner now also supplies its EA native cache lane, instead of serializing an
older hidden alias. The older appearance remains retained. Regression tests
exercise the actual native adapter's cache write and preserve the hidden
original. Link propagation now follows only explicitly configured direct edit
scopes, preventing an Alien -> Human -> Vampire chain from merging three forms.
UI snapshots query only the current panel and mark inactive panels as unknown;
complete native appearance exports retain the other fields. These changes pass
offline checks, but allocator-crash causality and runtime retention remain open.

The first V176 cold matrix reproduced an allocator crash during the fourth
member's first Alien body edit (`TS4_x64+0x112c713`). In the following session,
that member accepted distinct Vampire, Human and Alien body edits, then retained
all three through six repeated switches. Complete export comparison covers all
195 captured owners: exactly those three intended `physique` fields differ,
with no other changed fields, lost original records or added outfits. This is
limited body-edit evidence, not all-category, CAS acceptance or save proof.
The session was cancelled and exited without saving; all twenty saves match.

V177 replaces the manual physical-layer byte update in independent view
selection with EA's pinned original layer-transition handler. Same-layer
changes still rebind the exact owner because EA's layer selector would no-op.
The outgoing model is captured first, and the permanent binding guard prevents
the original handler from harvesting the newly assigned pair as an old edit.
Nine native checks pass, including actual adapter lifecycle/undo isolation.
Runtime cold Fairy -> Alien qualification remains open. Its candidate SHA-256
is `5756ff081d73cfd3da9ae615f098a9b7757ab029780a3075e2af6d604463c50e`.

The host CLI now refreshes a preflight once only after the exact Source refusal
that precedes CAS queue/token creation. A returned/unknown native UUID, possible
mutation, changed context or lost response never permits resubmission. Native
capture observes asynchronous background readback for up to fifteen seconds,
then checks local file stability without another game round trip after the
completion counter. A real background CAS cancellation-dialog capture succeeds;
the earlier unresolved capture receipts remain unchanged.

V177's cold fourth-member Alien body edit still crashed at `TS4_x64+0x112c645`;
the lifecycle correction is not a demonstrated allocator fix. Its complete
pre-gesture CAS regression run passed 957 checks. V178 makes the CLI physique
edit follow the inspected stock preview/completion sequence on separate UI
ticks, checks that the Sim/form has not changed, consumes the completion phase
before dispatch, and verifies the final value. Its package builds with compiled
one-shot gesture checks. Runtime cold-edit qualification remains open, and no
CAS acceptance or save is authorized by these fixture/build results.

V178's cold fourth-member pass completed, but the expanded matrix crashed on
returning the first member from Alien to shared Human after nine visits and six
body edits (`TS4_x64+0xed3913`). A same-build run with the custom strip collapsed
also crashed, during the first member's Alien body edit after six visits and
four fourth-member edits (`TS4_x64+0x112c645`). The strip stayed collapsed in the
completed receipts; removing its icons did not eliminate the failure. All twenty
save files remain byte-identical, with no CAS acceptance or save submitted.

The next diagnostic candidate removes redundant idle OWNERSTATE transmissions
and identical-message strip invalidations. The per-connection state cache still
sends the first state on reconnect and each actual owner/layer/state change;
fourteen metadata tests pass. A separate opt-in native build guards only
Apex-owned appearance-object boundaries and quarantines destroyed objects in
inaccessible pages, capped at 128 MiB of reserved address space. This aims to
locate an invalid object access; it is not a crash fix or a production allocator.
The normal build option remains off. A host capture correction restores a
previously attached but subsequently minimized exact game window without
foreground input; 57 related host checks pass.

The V179 guarded run still faults in the UI allocator (`TS4_x64+0x112c66a`),
not on a protected Apex owner page; no body edit completed. Save hashes remain
unchanged. This does not identify the original corruption, but rules out a
reported owner-boundary violation in that run.

V180 corrects a concrete socket-lifetime violation: Socket event failures queue
cleanup for a later owned Timer, rather than calling native close/reset from the
callback. Data/failure events must belong to the exact current socket. Each
outgoing frame now uses one retained ASCII header/body write, with Unicode JSON
escaped losslessly and one outstanding-frame lease. Compiled checks reject
callback closure, stale-event handling, unretained writes and unescaped JSON.
All 76 focused transport/control/metadata tests pass. Runtime matrix and release
qualification remain open. V180 retains the opt-in owner-memory diagnostics;
it is not a production build. Candidate SHA-256:
`3ee4b0ba6da497461f82dbbf34c82d8f59e4b7866fb886062a5fc59d00b4c32e`.

## Working rule: player-focused judgment

Use self-agency and common sense: consider how a player would enjoy creating,
editing and playing a hybrid household, then improve obvious friction with
coherent quality-of-life behavior. Make routine implementation choices without
repeated clarification, verify actual behavior and account for other mods that
share UI resources or hooks. Protect game data and compatibility, keep changes
reversible where practical, and do not describe an unproved feature as flawless.
The persistent project rule is
[apex-player-first-hybrids.mdc](../.cursor/rules/apex-player-first-hybrids.mdc).

## Required player experience

- There is exactly one shared Human appearance per Sim. Changing the selected
  occult must not create or select another occult-specific Human appearance.
- Modify the actual CAS portrait UI and its underlying selection, editing,
  linking, copying and persistence behavior. Keep EA's visual language and
  familiar portrait controls.
- Preserve existing EA form-specific portrait arrangements and behavior. For
  occult/special forms WITHOUT a paired portrait interface, implement an
  EA-style pair with that form above the shared Human below, including full
  Link/Unlink and directional Copy support. Selecting Ghost or Imaginary Friend
  must display and edit that actual form. Reusing the interaction pattern must
  never merge its appearance with Vampire or assign Vampire identity/gameplay.
- **Alien exception:** retain EA's existing Alien portrait arrangement,
  placement and selection behavior for compatibility. Do not force Alien into
  the Vampire-style top/bottom ordering. Add the missing Link/Unlink and Copy
  capabilities to that existing arrangement. Its human appearance still refers
  to the same shared Human; this exception does not create another Human.
- A compact selector integrated with CAS exposes all owned occult/special
  forms, with relevant game icons, clear names and an obvious selected state.
  Preserve genuine distinct alternate forms, without exposing internal native
  lanes, rendering genera, active aliases or duplicate Human records.
- Support Human, Alien, Vampire, Mermaid, Spellcaster, Werewolf, Fairy,
  PlantSim, Servo/robot, Ghost, Reaper, Skeleton, Scarecrow/Patchy, Imaginary
  Friend and their applicable distinct alternate forms. Implement missing UI
  and editing behavior rather than showing nonfunctional choices. Appearance
  support and actual gameplay behavior must both be qualified where promised.
- Every applicable form pair gets working Link/Unlink and directional Copy
  controls, including pairs for which EA did not supply them. Identify the
  source, destination and included details clearly; offer whole-appearance and
  selective category/detail copying. Unlinked forms edit independently.
- Human-looking Werewolf remains a Werewolf appearance option with Werewolf
  gameplay, not another Human form or a switch to Human gameplay.
- No accidental cross-form merge, propagation, deletion or replacement. Keep
  the permanent preservation guard while also correcting destructive game
  behavior at its source.
- Respect intentional edits from normal/full CAS, phone/MCCC CAS, F11 and
  Live mode, and preserve them through household, save and Tray/Gallery paths.
- Quality-of-life defaults: concise labels, compact spacing, consistent icons,
  clear copy direction, useful previews and reversible edits. Keep ordinary
  form switching simple and do not surface internal implementation choices.

## Implementation checklist

- [x] Record the owner's shared-Human correction and Alien layout exception.
- [x] Record the player-focused working rule and clarify that missing portrait
  pairs reuse EA's interaction pattern without substituting Vampire forms.
- [ ] Audit existing owner records and UI selection paths; distinguish actual
  player-visible forms from aliases and internal rendering/storage records.
- [ ] Define one shared Human identity used consistently by native CAS,
  Source, F11, saved banks, linking, copying and import/export.
- [ ] Migrate previous duplicate Human records without silently discarding
  differing appearances: preserve originals in recoverable history and obtain
  an explicit choice when differing retained looks cannot be reconciled.
- [ ] Replace the duplicate-record strip with the integrated native portrait
  selector and implement the selected-occult/shared-Human presentation.
- [ ] Keep Alien's stock layout and add its missing Link/Unlink/Copy behavior;
  check compatibility with other CAS UI modifications.
- [ ] Implement missing portrait, selection and actual editable form support
  for each supported special life state and genuine alternate form.
- [ ] Bind edits, undo/redo, return capture and persistence to the exact selected
  appearance, independently of its rendering genus and other household Sims.
- [ ] Implement and expose explicit link scope, unlinking and directional
  whole/partial copying for every applicable pair, including special forms.
- [ ] Eliminate unauthorized automatic outfit creation and other destructive
  normalization; distinguish original-byte retention from strict no-change QA.
- [x] Package the matching UI, script and native changes together; verify the
  candidate before installation into the single disposable profile.

## Player-focused acceptance tests

- [ ] Give Human and several actual occult forms visibly different hair,
  clothing, skin/details, tattoos, accessories, presets and slider values.
  Extend coverage to every discovered editable category and outfit slot.
- [ ] Prioritize actual Alien -> Vampire -> Alien edits/switches, then cover
  every other supported form and genuine alternate; do not substitute Human
  appearances rendered under another occult label.
- [ ] Switch repeatedly in CAS; verify both the selected portrait and exact
  edited appearance, with only one shared Human and no duplicate menu entries.
- [ ] Verify Alien retains EA's portrait arrangement and gains functioning
  linking/copying without disrupting existing Alien CAS behavior.
- [ ] Verify newly implemented Ghost/Human, Imaginary Friend/Human and other
  missing portrait pairs edit their own appearances and never add Vampire data,
  membership or gameplay merely because they reuse the portrait layout.
- [ ] Link a chosen pair/scope and prove only the intended propagation occurs;
  unlink it, edit again and prove further propagation stops.
- [ ] Copy in both directions with whole-appearance and selective details;
  prove only the chosen destination and included fields change. Verify undo.
- [ ] Return to Live, unpause when required for changes to apply, switch actual
  forms repeatedly, reopen full CAS and compare all retained appearances.
- [ ] Repeat through phone/MCCC CAS and F11/Live editing; preserve the latest
  intentional edits rather than restoring stale snapshots.
- [ ] Edit one household member, then several/all members; verify isolation
  and retention for every Sim while moving among their forms.
- [ ] Leave/re-enter the household, save normally and cold-load; verify shared
  Human, all occult/alternate appearances, link state and gameplay membership.
- [ ] Export/import the multi-hybrid household through Tray and applicable
  local Gallery paths; verify every member, actual form and distinct edits.
- [ ] Verify special-form gameplay, Werewolf appearance mode, autonomy/sunlight
  test protections, original-profile isolation and non-regressive performance.

A large count of duplicated form records does not prove any acceptance test.
Body markers, fixture results and preserved post-initialization bytes alone do
not prove full-category editing, correct UI, CAS return, save or Tray retention.
Keep unproved acceptance items open and retain evidence for failures.


## V225 native portrait panel and responsiveness work (2026-10-20)

The owner requested EA's real Vampire-style category link/copy panel in the
existing portrait toolbar, including Alien's existing portrait arrangement,
without Vampire identity substitution or a new floating toolbar. The seven
selected native panel methods now adapt only the hybrid branch to the exact
Sim/shared-Human/selected-form graph. EA's embedded artwork, buttons, checkbox
component, native placement and other selector methods remain intact. Stock
controller-wide autosync is never used by that hybrid branch. Category masks
include tattoos, skin details/scars, accessories, makeup, eyes/eyebrows, body
hair and wings; unselected fields and opaque destination data are retained.
Links are direct pair edges: an Alien edit cannot relay through Human into a
separately linked Vampire. Linking does not copy either current appearance.
The same masks are available through the semantic CLI.

The replacement floating link/arrow controls and their idle native/feed reads
are retired. Local form clicks retain one latest desired selection for the
exact Sim/editor, including while an earlier transition/readback is pending.
Outstanding transitions continue on UI frames rather than waiting for the
500 ms network polling timer; EA's pair panel refreshes after the actual bind.
A 0-1 ms click-handler budget is a target, not a claim that complete game
binding, asset loading or rendering can finish within that time. Runtime
latency distribution and native-panel player-visible qualification remain open.

V224's interrupted edited-category run completed twelve real item edits and
six Alien/Vampire switch visits across the first two household members. Its
automated driver was stopped to avoid competing with the owner's input. The
last read-only request was later observed complete, without replay. The
remaining members, edited CAS return, selective checkbox actions, save and
Tray/Gallery round trips remain unqualified; no save or CAS acceptance was
submitted by that interrupted run. V224's earlier five-member no-edit return
proof remains a separate, qualified result.


## Native panel integration, V226-V229 (2026-10-20)

The native panel adapter retains EA's options container and its inner
`mcAlternativeFormCopy` widget. Reading the outer container as if it were the
copy widget caused an Error 1010 in retained-feed diagnostics; V229 addresses
the actual inner widget. Read-only panel status can run during CLI readback;
mutations still require the exact idle Sim/pair/generation. A changed bound
owner/generation refreshes the EA panel, including initial binding.

Form input uses the retained UI Sim instead of synchronizing/serializing a
complete native Sim inside the click callback. The latest choice survives a
busy transition, including clicking the previously active form again. Timing
retains the original queued timestamp. The observed V228 native Vampire bind
was 10.0329 ms; it is not a 0-1 ms end-to-end result.

V228 opened full CAS after verifying all 195 stored appearances. Its first
panel qualification stopped on the diagnostic/visibility error. A separate
voice-only copy failed before writing an appearance: outfit IdList identifiers
are packed fixed64, while body types/colors/object/layer arrays use their own
varint encodings. V229 corrects that distinction, accepts an omitted default
outfit category, and avoids parsing/copying unselected outfit/morph data for
scalar-only operations. Native fixtures include fixed64 boundaries and voice
copy retaining complete outfit/morph bytes. Runtime checkbox/selective-copy,
link/unlink, household return and save/Tray gates remain open.

A stale unresolved preflight from a closed process also blocked retry. The
Source recovery path now archives that exact old preparation only after the
prior process is absent and the same save/household, complete actual native
appearances, traits, current kinds and requested memberships match. It retains
its raw hashed preimage and does not replay a CAS return or restore old data.
Sixteen entry-context tests pass, including changed-data/live-process refusal.
The earlier Human-looking Werewolf test recipe with non-genetic parts in its
genetic-data list was retained in history; only disposable fixtures were
explicitly rebuilt from current Human appearances. This does not qualify
arbitrary legacy recipes or weaken strict native-import comparison.


## Input latency and native tooltip contract, V230-V231 (2026-10-20)

V230 diagnostics identify the repeated connection reset: the native tooltip
`SetText` method takes a LocKey, while the hybrid adapter supplied a String.
The actual GFx Error 1034 names the directional copy tooltip. V231 uses EA's
existing String `Text` setter. Its bytecode gate requires both directional text
writes and rejects a regression to SetText; a compiler-tampering fixture tests
that contract. All 61 selector bytecode checks pass.

The owned command dispatchers now stop after one transaction with a 1 ms
scheduling budget, rather than batching four within a 20 ms allowance. The
queue records execution counts, command/drain maxima and budget overruns in
constant storage. A running native game transaction is not preempted or
reported as a fictitious 1 ms completion. Deterministic regressions cover
budget yielding, a measured 25 ms overrun, retained pending UUIDs and the
actual alarm dispatcher yielding after one transaction. Eight queue tests and
ten backend ownership tests pass. Empty-queue host Python timing over 10,000
samples has p99 0.0008 ms and maximum 0.0056 ms; this is not game/UI proof.

Occult-choice input now only queues; its full-edit permission read is deferred
to the UI frame that consumes the choice. Navigation uses the Customizer's
retained selected-Sim primitives instead of allocating the complete household
and native category-panel feed on every frame. Exact native Sim/owner/session
validation still precedes writes. Accepted input timings expose sample count,
maximum, total and over-budget count separately from complete model binding.
The UI clock has 1 ms resolution; a zero reading is below that resolution,
not proof of zero processing time. Runtime latency distribution, actual panel
checkbox/copy/link qualification, edited household return, cold save reload
and Tray/Gallery gates remain open. The candidate is not actual-save ready.

## Linked edits and catalog workspace, V232-V233 (2026-10-20)

V231's real Alien/Human voice-link test exposed an unflushed model on unlink:
the last linked voice edit had not reached Human. V232 flushes through the old
link scope before either enabling or disabling a link, then validates the same
Sim/owner and uses the resulting generation. Its native regression covers
edits before linking, the last edit before unlinking, subsequent isolation and
a failed flush leaving the link unchanged. Rapid checkbox changes coalesce
only within the same unsubmitted pair; explicit Copy remains one-shot.

V232's in-game selective voice test passed. Human retains 0.23 while Alien
retains its subsequent unlinked 0.77; the other 193 internal records match
their pre-entry captures. The household returned to Live and was unpaused:
all 40 Live appearance views and 155 named looks match their logical owners.
The selected active Alien maps to the native Alien slot on return, rather
than remaining an extra player-visible form. The initial comparison script
incorrectly treated that internal preimage as a second Alien; its original
failed evidence is retained beside the explicit alias comparison. All 20
save/backup files remain unchanged. The session closed normally by CLI.

V233 adds the catalog workspace described in
[CAS_CATALOG_WORKSPACE.md](CAS_CATALOG_WORKSPACE.md). Its UI-only style changes
and exact current-outfit inventory do not establish household/save/Tray
qualification. Keep the broader all-category, MCCC, save/cold-load,
Tray/Gallery, player-input latency and compatibility gates open until tested.

## CAS catalog addition, October 21

V247 separately qualifies card size, independent spacing, native row-cache reset
and a complete static selection outline in the disposable CAS session. Four
layouts, eighteen semantic controls and actual background clicks on three
sliders plus EA reset pass. All 39 committed selected-Sim appearance records
remain unchanged after the semantic pass; every save/backup file is unchanged.
See [the scoped card report](../Reports/CAS_CARD_LAYOUT_V247.json). This is a UI
qualification only: the direct outfit/genetics normalization and full edited
household/save/Tray release gates above remain open.

## Keyboard and same-form acknowledgement, V257-V258 (October 21)

V257 qualifies arrows, Home/End, Page Up/Down, native Enter/Undo and equipped-card
category navigation in actual Alien CAS. It covers five-column Hair and
two-column Face grids, viewport masking and background Windows-key delivery.
The twenty save/backup files remain unchanged. Specialized palettes, modals,
typing and layout overlap still need their own runtime qualification. See
[the keyboard report](../Reports/CAS_KEYBOARD_V257.json).

The next household preparation exposed a same-form CLI acknowledgement defect:
the native Human bind completed in 11.5 ms, but its UI readback waited for a
changed-owner heartbeat. The original request and native applied receipt are
retained; no mutation was replayed. V258 reads the current bound native owner
during readback. Seven actual bindings now pass, including same-owner Alien,
Human and Vampire, and Alien → Vampire → Alien. Native times and the separate
3–5 second host/transport/evidence times are retained. Thirteen serialized
bytecode cases include rejection of a missing bound-owner refresh. See
[the acknowledgement report](../Reports/CAS_OWNER_REFRESH_V258.json).

The host's repeated inventory scans also retain exactly the same device/file
identities, USNs and content checks while avoiding duplicate traversal, repeated
Windows API binding and unrelated TLS setup. Six paired local samples reduce
median inventory-check time from 278.4 ms to 109.3 ms. This is a host-tool result,
not a gameplay frame-time claim. See [the host report](../Reports/CLI_HOST_INVENTORY_V257.json).

## Member presentation scheduling, V259 (October 21)

The new candidate addresses the wait between selecting a household member and
seeing its native link/copy controls. The prior customizer advances member
detection, connection and owner/pair setup through separate 500 ms timer waits.
V259 listens to EA's existing `CASSetSimInfo` notification and queues later UI
frames to advance that same checked setup. It retains EA's typed handler and
portrait/category panel. The frame listener detaches when ready or closed; its
two-second budget leaves slow/loading peers on the ordinary timer. An existing
CLI claim retains its original timer-owned execution and readback.

Readiness requires the current Sim, complete owner catalog, bound selection and
matching pair generation. Repeated incoming notifications retain their first
timestamp; returning quickly to the still-bound member clears the superseded
target. Twenty-nine serialized owner/presentation cases, thirty-nine native form
selection cases, twenty typed controls, six raw source-pin cases and both
twenty-six-case seal/migration suites pass: 146 focused checks. Seven packages,
105 Python 3.7 modules and 210 independently Rust-verified resources build.

Actual member-click latency, visible EA link/copy controls, idle frame cleanup
and complete appearance preservation still need qualification in the installed
candidate. These build checks do not establish a universal timing guarantee or
actual-save readiness. See [the scoped report](../Reports/CAS_MEMBER_PRESENTATION_V259.json).

These are scoped passes. Keep all-category edited-household return, the observed
Human genetic-cache normalization, save/cold-load, Tray/Gallery, compatibility
and actual-save readiness gates open. Duplicate internal preimages are never
counted as additional playable forms.


## V260: exact native occult record export (runtime pending)

V258 retains thirty distinct native selections across five household members
and Alien/Vampire revisits. All 195 internal records are compared, with only
the ten deliberately edited owners changing. These counts do not establish
all requested forms or categories. Native CAS acceptance is rejected before
EA's actual handler; no game save is submitted.

Read-only native inspection identifies the writer's Human/non-Human bucket
lookup: on a Werewolf-, Mermaid- or Fairy-first tracker, exporting Alien
replaces the wrong occult and leaves duplicate Alien records. V260 routes
the pinned native writer to the exact existing record only in a qualified
detached CAS household output, then restores record order. Original roots,
unrelated callers and strict complete-field/roster/parser checks stay intact.
The permanent guard remains active. Forty-nine genus/order cases, nine
invalid-input refusals, exception restoration, 114 focused Python checks and
two rebuilt native targets pass. Actual edited return, normal save/cold load,
Tray/Gallery and visible member-switch latency remain unqualified.

V260 installs and launches through the CLI. All forty saved native appearances
remain unchanged after simulation advances. Fresh CAS preparation nevertheless
refuses before opening the editor: the game filters five unique genetic part
entries from an existing Human/CC Werewolf look. The stored look is retained
and is not reinitialized to bypass this gate. Exact-record exit repair remains
runtime-unproved until this import defect is resolved.


## V261: retained genetic entries and native control transport

The native import now admits an existing genetic body type only while the
exact captured message is being imported into its exact native temporary and
genus. The shared predicate remains unchanged. Native tests execute the relay
ABI and refuse foreign messages, destinations, genera and threads. Fresh full
CAS entry verifies all 195 captured appearance records across five members
without resetting the stored Human/CC Werewolf look or excluding genetic data.
This does not establish edited exit or production readiness.

Creator-data field 76/24 is included in exact whole-form export and copy. A real
detached game-codec probe retains populated creator data while all eight actual
Sim owners and all twenty save files remain unchanged. Native ghost-color
channels 73/74 do not round-trip through this codec; no complete per-form Ghost
color claim is made. Their unrelated incoming wire fields are preserved.

Full appearance CLI inputs use bounded POST with the matching game guard; lost
responses are not resubmitted. The CLI retains explicit HTTP error reasons. A
compact real POST codec probe passes; the fresh full-size input qualification
and actual native portrait timing remain pending.


## V261: actual edited household save and cold-load qualification

V261 now completes 30 real Alien/Vampire eyebrow, skin-detail and earring selections across all five household members, including repeated Alien → Vampire → Alien and member revisits. Complete comparisons retain the other 185 internal records. Native acceptance verifies all five exact outputs without root memory writes or faults, and all 40 Live appearances match before explicit disposition. The edited household survives a normal save, normal exit and same-candidate cold reload: all 40 native appearances remain exact before and after simulation advances, and all 155 named looks are admitted from saved metadata without native restore or draft resumption. This is scoped persistence proof, not a full release qualification.

The separate native portrait-input test remains incomplete/failed. Three selections completed with status-observer-contaminated 21–23 second timings; the fourth posted window click did not select its target. Core data was independently re-exported and compared before the single CAS acceptance. Core persistence success does not qualify pointer reliability or responsiveness. Normal automatic engine arming and a fresh scope after retirement are subsequent V262 source work; neither is installed in V261. Keep all remaining release gates open.


## V262: normal entry scope and resident native calls

Normal hybrid-household preparation previously imported native owners only after a research CLI arm command. It now validates every live member and fresh raw transaction before arming the matching engine itself. A complete retired scope can receive a fresh identity and roster only after native owner, controller, copy and transport authority have been released. Active or partially imported scopes remain nonreplaceable. The native entry protocol is explicit so an older DLL cannot silently acknowledge this lifecycle.

Active native CAS calls reuse the fixed export bound to the already authenticated loaded handle, checking the caller archive and retaining native scope/Sim/owner/generation checks. They no longer hash the entire on-disk DLL or create ctypes function classes at every heartbeat. An explicit start still checks the manifest/disk bytes and refuses to relabel a different build. This is not mapped-instruction tamper detection or measured player-latency proof.

Eighty focused Python checks, fifty-two final frozen recovery checks, fifteen rebuilt native targets and the private Python 3.7 ABI/packaged-loader checks pass. The matching immutable candidate contains seven packages, 105 compiled modules and 210 Rust-validated resources. The initial full run caught stale recovery hashes; those checks pass after the final source freeze, with a new complete CI run still required. Actual automatic entry without research arming and repeated retirement/reentry require fresh qualification. Mixed ordinary/single-occult companions, all-Human/new-Sim main-menu CAS, cancellation and complete responsiveness remain open; the five-hybrid path is not universal coverage. See [the scoped report](../Reports/CAS_PLAYER_ENTRY_V262.json).


## V263: saved named metadata after a code update

The real V262 upgrade retains all forty native appearances and every save file, but saved named-form admission refuses the V261 script because its exact producer was not yet in the reviewed metadata-only list. No CAS entry is submitted. V263 adds only that reviewed V261 producer after its actual five-member edited save/cold-load qualification. It retains immutable seal, file, owner and native/load checks; unknown producers and native restoration remain subject to their original restrictions. No seal or save is repinned to bypass the failure.

Sixty-six frozen recovery/named tests and the private Python 3.7 ABI/packaged-loader checks pass. The final fourteen named tests independently preserve the prior producer regressions and reject native restoration from the newly reviewed metadata producer. The matching candidate is built; actual named admission, normal automatic CAS entry, repeated retirement/reentry and the full release matrix still require qualification. See [the scoped report](../Reports/CAS_SAVED_NAMED_UPGRADE_V263.json).


### V263 actual matching-build qualification

V263 admits the reviewed V261 saved named looks without native restoration. The matching game retains all 40 native appearances and 155 exact named looks. Full CAS opens without manual research arming and preserves all 195 captured internal records; returning to Live preserves all 40 before explicit disposition. After review, the native scope retires, and a second same-process entry creates a fresh scope with every captured field unchanged. Saved files remain unchanged. This is same-household lifecycle proof, not every requested form/category/edit route or production readiness.

The first return harness incorrectly treated the expected explicit-review outcome as a failed transition. The continuation verifies that original acceptance/Live receipt and does not resend Accept. The earlier pointer test remains incomplete/failed. A new complete CI run, every-category/form/route, other-household and Tray/Gallery coverage, native search UI and responsiveness remain open.


### V263 quiet native portrait presentation

A quiet V263 pass verifies actual background portrait switches from member one to five and back, with no semantic claims during each settling interval. EA link/copy controls become ready 1,066 and 1,166 ms after CASSetSimInfo notification. All 195 fields and saved files remain unchanged, desktop focus stays fixed, and idle setup frames stop. Click-to-notification time is not measured. These samples do not form an A/B comparison with the earlier contaminated 21–23 second observations, and they do not meet the responsiveness goal. See [the scoped timing report](../Reports/CAS_MEMBER_QUIET_V263.json).

### V264–V266: pair acknowledgement and native search placement

V263's complete CI run 39696227324 passes 2,614 Python checks and all fifteen
native targets at bfe3ae7. This supersedes its earlier pending-CI note; it does
not qualify later source changes. V264 checks the exact immediate pair-renderer
acknowledgement. Its two quiet actual switches retain all 195 captured fields,
but readiness remains 1,105 and 1,100 ms. Do not claim that this resolves lag.
The no-edit return retains all forty native appearances before and after
disposition and all 155 named looks, followed by a normal unsaved exit.

V265 builds an editable field at the native Filter Items location, with the
existing toggle/chips and native cards. The matching game retains all forty
native appearances after reload and all 195 records on normal full-CAS entry.
A backbuffer capture confirms the bar's visible placement. The first search
test fails before submitting a query: the initial native source rows are not
admitted. V266 queues that UI-owned source, then checks Sim, form, generation,
category and actual visible feed in the idle phase. It keeps native eligibility,
card/swatches and appearance setters unchanged. Corrected actual search, input,
selection, context transitions, broker startup and large-library tests remain
open. See [V264 timing](../Reports/CAS_MEMBER_QUIET_V264.json) and the
[V265 search failure](../Reports/CAS_NATIVE_SEARCH_V265.json).

V266's deferred admission receives all 41 native lip cards; exact query intent
and clearing are observed, but metadata submission is refused. Its complete
CI at 0028587 passes 2,619 Python checks and fifteen native targets. V267's
bounded read-only diagnostic identifies the protocol error: SEARCH/SEARCHREAD
were sent the Sim ID instead of the native channel. V268 corrects those two
calls and adds a serialized regression rejecting that substitution. The native
ownership check remains intact. Actual corrected results and selection still
need qualification. See [the follow-up report](../Reports/CAS_NATIVE_SEARCH_V266.json).

A game-thread disposition profile separately records repeated complete-bank
reads, JSON encoding and SHA work. V268 removes an ignored canonical digest
used only for JSON validity: duplicate-key checking remains, finite numbers
are validated during parsing, and the full raw-file SHA is still computed.
Unknown fields, finite extremes, negative zero and malformed JSON are covered;
the targeted transaction/commit regressions pass. This is not yet a measured
gameplay-speed improvement or a reason to relax the permanent guard.

### V276: legacy Human/CC Werewolf and form-specific UI repairs

The reported black Human/CC Werewolf retains beast head genetics and pelt data
inside an older named look. New captures already seed the complete shared
Human appearance. An explicit **Reset Human/CC from Human** button now repairs
an older look through the same exact-pair whole-appearance copy transaction.
Its tooltip explains that head, body, skin and outfits are replaced only in
that chosen CC variant. Opening CAS does not reset a player's saved CC edits.

EA's wing header and radial menu can query the physical alternate's Vampire
display type after the native model binds Fairy. The three wing-header methods
now resolve the exact selected owner before choosing paint mode, enabling the
paint header or displaying its tooltip. The radial also retains the selected
owner's UI context across refreshes, copying every public SimInfo slot.
These UI changes retain the complete membership mask and independent owners.

Expanded portrait tooltips now describe each displayed owner separately while
preserving EA's disabled-state warnings and relationship text. Original class
construction, artwork, unrelated methods and inherited cleanup remain retained
by the serialized build checks. See [the scoped form-repair report](../Reports/CAS_FORM_REPAIRS_V276.json)
for actual runtime results; these repairs do not close the broader release checklist.

### V278–V280: retain canine parts, correct pelt composition and merge Companion code

The owner rejected replacing an existing Human/CC look as the fix. The retained
canine head, ears, claws, genetics and paint must remain editable. V278 corrects
the exact renderer genus pointer and routes only the temporary texture-composer
copy through the pelt path. Actual CAS pixels show the former black material
rendering as fur on Human geometry, without an appearance reset. All 195
captured appearances stay unchanged through the unedited Werewolf round trip.
Live rendering remains unqualified.

The Human/CC catalogue now combines the native Human and Werewolf queries for
eleven face/fur states while retaining the original age, gender and tag filters.
The actual head catalogue expands from 19 to 25 presets and ears from 72 to 82.
A selected canine-head edit survives Werewolf and Fairy round trips with the
other 194 records unchanged. Its native preset-index acknowledgement still
fails; visible editing and field retention do not turn that predicate into a
pass. Head/ear shape distortion and eye placement remain open.

The optional Maru build now starts from the owner's actual compiled Companion
code, retaining its helper classes and 65 dependent resources. It preserves
2,633 of 2,650 donor method bodies around Apex's reviewed adapters, including
five named-form identity checks for cached selection, eye/skin tools and outfit
previews. V278 exposes a broken definition-resolver binding; V279 corrects it
and adds a serialized gate. V280 now detects the actual donor controls with
duplicate Apex companion handlers disabled. Native favorites/history and
shared column layout still require actual runtime checks.

V280 adds explicit **Human skin / no fur** and **Use Werewolf fur** actions for
the selected Human/CC owner. Removal copies the shared Human skin tone and
clears only fur layers/paint and body-fur parts. The other action copies the
current EA Werewolf form's fur settings; it does not promise to restore an
archived former CC fur look. Both retain canine head/ears, morphs, clothing and
tattoos. Scope and selective-field tests pass; actual toggle rendering and
round-trip checks remain required. The first actual V280 removal is refused by
detached game-readback validation before graph publication. Its original
failure is retained without replay. V281 preserves byte-identical outfits when
no selected wearable part is present, adds exact changed-field diagnostics and
restores the chosen view after a refused copy. Those corrections do not qualify
the fur actions until their real rendering and retention checks pass.

The complete frozen V280 Python suite passes all 2,835 checks. V281's rebuilt
native suite passes all sixteen targets, including the fur scope fixtures.
See [the scoped validation report](../Reports/CAS_CANINE_COMPANION_V280.json).

### V287–V288: actual fur/favorites qualification and unload repair

V287 cold-loads all forty native appearances with the supplied Animated Tails
and Animated Wings bases installed. The reviewed attachment adapter installs;
it scopes EA's single-head reservation only for those two attachment tags,
preserving original parenting, animation and persistence calls. Nine focused
tests cover simultaneous parts, removal, restoration and failure isolation.
Actual simultaneous animation and CAS/F11 selection remain open.

The original full-CAS entry exceeds its timing gate. Read-only late observation
qualifies that same entry with all 195 appearance records unchanged; no second
entry is submitted. This is not a responsiveness pass. The literal Companion
favorite click and Favorites/All button handlers now pass actual CLI invocation,
restore their original preference, and leave all 195 records unchanged. Native
right-click and restart persistence are still open.

The fur failure was a real default-body mismatch, not permission to weaken
verification: EA converts anatomical nude templates into CAS underwear parts.
V287 uses independently identified female defaults for outfit substitution,
while genetics retain their own anatomical defaults. Fur-on leaves clothing
unchanged. Actual no-fur/fur pixels and complete scoped readbacks pass through
Werewolf and Fairy round trips, retaining the chosen CC and other 194 records.
The existing head/ear/eye deformation remains visible and open. Male defaults,
Live rendering and edited save/Tray cycles are not qualified by this CAS pass.

An actual teardown exception separately identifies a catalogue redraw after
EA has retired its tuning. V288 releases owned card-layout references on unload
without enumerating or reflowing the retiring native grid. A compiled mutation
test rejects reintroducing that redraw. The complete V288 regression passes
2,848 Python tests and all sixteen native targets. Its new game cold-loads all
forty appearances and enters full CAS with all 195 captured records unchanged.
The actual acceptance/unload and unpaused Live return also pass: all forty
native appearances match before and after the separate no-edit disposition,
all 155 named looks remain, all twenty save/backup files are unchanged, and
the complete rotated UI-report inventory has no new or changed report. This
qualifies this no-edit return, not every cancellation stall or an edited fur
save/Tray cycle.

### V289–V292: actual Live scene and transition completion

The actual EA Fairy/Dark Form interactions expose a visible failure that a
matching native flag cannot qualify: the server and portrait can select Vampire
while the world still shows Fairy. A bounded disposable CLI now submits the
original EA affordance test/queue path, preserving its animation and native
tests. Read-only observations distinguish the client outfit source and actual
back-carry owners from stored appearance records.

V291 removes the stale native wing carrier, but a later observation reaches
Human. It is not a stable Vampire pass. V292 defers carry cleanup until the
reviewed native transformation has exited its original pipeline, preserving
the remaining loot and transition cleanup. Its optional trace is explicit and
bounded; no polling or blanket removal of wings/tails is introduced.

Profiling also identifies repeated complete bank reads from the optional hair
hook. A stable read index supplies only the enabled bit; actual enabled repairs
still require fresh full authority. Immutable byte-projection caches avoid
reparsing identical outfit/genetics values without skipping native reads or
complete comparisons. Their size is bounded and they contain no appearance
write authority. Runtime speed and all directed form transitions remain open.

A real colored Fairy on another household member visibly retains purple/teal
wings and all native appearance fields. Blank-palette test forms have no color
layers; native CAS swatch selection and full color persistence still require
qualification. See [the scoped Live report](../Reports/LIVE_FORM_PRESENTATION_V292.json).

V292 now completes the actual EA Fairy reveal → Vampire Dark Form → Fairy
reveal sequence on one member. Both 8-second and 24-second observations agree,
including the settled world model. All household stored native appearance
fields remain unchanged and the final active fields match the selected Fairy.
An actual EA wing-card click colors a blank-palette test Fairy; its selected
base and visible colors survive a Vampire round trip. This does not qualify
every swatch or save/Tray persistence. One actual strip click measures 31 ms
from queued input to bound owner, including 16.9 ms in the native binder.
Do not describe this sample as universal 0–1 ms switching.

V293 shares that strip's checked, immediate EA pair-panel refresh with the
typed selection path. The latter must finish presentation before acknowledging
its owner. Serialized checks retain the exact Sim/owner/generation predicates
and refuse another model bind or appearance copy in the helper. Native cleanup
also tolerates an actor retired by the completed original pipeline without
catching or replaying the original game's/mod's exceptions. The candidate
builds and focused checks pass; matching runtime qualification remains open.
See [the pair-presentation report](../Reports/CAS_PAIR_PRESENTATION_V293.json).

V294 separates a read-only status lease from appearance write ownership. A
seven-field status command may coexist with same-Sim native form/pair input
only in readback phase one, with matching visible Sim and claim nonce and no
command mutation. Received/unknown commands and all mutating commands retain
their block. UI input still queues to a separate rendered event; no native
work is added inside the input callback. The compiled classifier has no calls
and its mutation fixtures reject a wrong operation, phase, length, Sim, nonce,
mutation flag or receiving state. This removes an avoidable timer wait in the
code; matching runtime responsiveness qualification remains open. See
[the input-priority report](../Reports/CAS_INPUT_PRIORITY_V294.json).

The V292 matrix completes 191 selections: all 42 directed native pairs on one
member and all twenty exposed forms on each of five members. The final field
comparison fails. Member five's shared Human inherited-hair entry changes
277692 → 306960, although Human hair was not edited. All Human outfits already
use 306960, so this identifies automatic inheritance regeneration during view
setup rather than evidence that Fairy and Human appearances were merged.
The other genetic rows and native appearance fields remain exact. No save or
CAS acceptance is submitted after this failure.

V295 pins the inspected outfit-to-genetics setup call and skips its regeneration
only within the exact independent model bind, with matching Sim, group, owner,
genus and destination addresses. It retains the incoming complete genetics
instead of restoring or guessing it later. Ordinary hair/outfit edits and other
callers remain native. Seventeen native targets pass, including the exact hair
case, unknown-data retention and foreign-context refusals. Matching actual-game
hair edits, undo and complete retention remain required. See
[the captured-genetics report](../Reports/CAS_CAPTURED_GENETICS_V295.json).


V297 re-enables an EA pelt/wing color layer only when its exact selected native
color resolves in the available palette. The native GetPeltColors method keeps
all original native reads and unknown-entry handling. This fixes the observed
empty-palette-to-valid-palette disabled control state without choosing colors
for a player. The literal Companion merge now retains 2,632 of 2,650 original
method bodies; the eighteenth reviewed adapter is this native palette UI fix.

Initial owner catalogue/state metadata also precedes a queued CLI claim, so a
read-only status cannot suspend the member bootstrap behind timer readback.
After that first bootstrap, ordinary command priority returns; missing metadata
falls back without re-claiming or replaying work. No polling or appearance
write authority is added. Five transport regressions pass. Matching member
latency and palette UI qualification remain required. See
[the palette/bootstrap report](../Reports/CAS_PALETTE_AND_BOOTSTRAP_V297.json).


V295 repeats all 191 native/named selections across five Sims with all 195
complete appearance records matching the two deliberate Human hair and Fairy
wing-palette edits. Actual CAS exit, exact two-lane disposition and saving retain
all 40 native appearances and 155 named looks. V300 also cold-loads them before
and after advancing Live simulation, with no native appearance restoration.
Its compatibility change admits metadata from the exact audited V295 script
hash, retaining immutable seals, native equality checks, unknown-source refusals
and the separate A0-only native recovery authority.

Undo remains a release blocker: two native Undos restore the original Human
hair outfit but replace inherited hair 277692 with 306960. Two native Redos
recover the exact edited Human. V298 adds explicit, scope-bound research tracing,
disabled by default and at fresh scope/retirement, with sixteen bounded call
records and eight game-frame RVAs each. It implements no functional Undo fix.

V300 schedules variant opening, same-owner dismissal and ordinary form-toolbar
changes on the next rendered frame instead of awaiting the network timer.
Thirty-three serialized menu mutations, thirty-nine owner metadata mutations
and thirty-nine form-selection mutations pass. Matching interactive latency,
Fairy controls and the remaining release gates still require actual QA. See
[the menu/metadata report](../Reports/CAS_MENU_AND_SAVED_METADATA_V300.json).


V302 requalifies the edited save (40 complete native appearances and 155 named
looks) and normal full-CAS entry (195 complete records). Actual V300 pointer
selections measured 31–56 ms from queued gesture to bound owner, with a native
pair panel. The queue handler alone measured 0 ms at 1 ms resolution; this is
not a universal complete-switch latency claim. Member presentation still took
1,624 ms / 44 frames in a measured sample.

The native Fairy layer picker now works after selecting a valid palette from an
empty gray palette; purple paint survives two Vampire round trips, changing
only Fairy pelt_layers and retaining Human. Paint-history CLI qualification is
still open. V302 adds bounded same-owner palette readback evidence to Undo/Redo.

The inspected catalogue pre-action genotype rewrite is now suppressed only for
the exact captured model/context. A real hair edit still updates inheritance.
The deliberately mismatched legacy inheritance Undo test still fails; neither
this partial correction nor the palette evidence closes the history gate.
The original unresolved command is never replayed. See
[the history/palette report](../Reports/CAS_HISTORY_AND_PALETTE_V302.json).

V303 addresses member-handshake delays: bounded bootstrap frames drain existing
ACKs before the ordinary 500 ms Timer, while their dispatcher still refuses
command execution/readback on a frame. BUSY from the previous closing worker
retries without a connection reset. Both dedicated loopback endpoints disable
Nagle batching. No background service, idle frame polling or appearance-write
authority is added. Measure actual member transitions before claiming a win.

V306 repeats all 191 full-CAS selections across five members, including every
directed native pair and all twenty exposed forms on every member. All 195
complete records and all twenty save/backup files remain unchanged. Actual
Vampire/Human/Alien pointer selections settle in 31–38 ms. Household-member
presentation still takes 1,405–3,556 ms; the fifth member misses the bounded
local bootstrap. See [the measured report](../Reports/CAS_LOCAL_MENU_SWITCHING_V306.json).

V307 primes the complete prepared menu from its exact opened native lease,
without waiting for TCP or a new native Sim-info allocation. The native group,
member, scope, rendering kind and bound model still gate presentation. Source
commands retain their separate connected transport, nonce, UUID and claim.
Native link/copy actions use the same exact pair and replay checks. Five actual
member selections now publish the local catalogue and EA pair controls on one
frame in 737–854 ms. This is an improvement, but still fails the 250 ms target.
Actual Vampire/Human/Alien clicks take 31–43 ms; their queue handlers alone
measure 0 ms at 1 ms resolution. Profile the delay before the first frame and
the menu/pair/icon publication costs next. Do not call this instant.

The matching V307 sources pass 2,912 Python checks and nineteen native targets.
Cold Live reload retains forty complete native appearances and 155 named
looks; normal automatic full-CAS entry retains all 195 records. This does not
qualify every special-form mesh or shader, edited MCCC/F11 persistence, or the
native full-household Tray/Gallery round trip. See
[the local-presentation report](../Reports/CAS_LOCAL_PRESENTATION_V307.json).

The corrected swatch-ID-to-ARGB projection acknowledges the first actual Fairy
layer Undo. A second native Undo changes no verified appearance field and its
original request remains unresolved without replay. Purple wings survive two
Vampire round trips while Human stays exact. Existing empty wing palettes still
start gray; explicit native swatches enable all five working color layers.
Initial default-color repair and complete paint history remain open. See
[the actual palette/history evidence](../Reports/CAS_PALETTE_HISTORY_V306.json).

V307's complete repeat also passes 191 selections and retains every one of the
195 complete records, with all twenty save files unchanged. V308's bounded
publication counters show 700–1,504 ms before the first frame in four measured
member changes, plus 205–319 ms publishing the native pair panel. Icon lookup
and drawing cost only 0–2 ms. The fifth member again misses the bounded bootstrap;
this is a failed speed gate. Concurrent regression tests were running. The
actual native selector filters valid hybrid portrait rows and its observer then
restores and relayouts them; prevent that filtering and avoid rebuilding unchanged
copy-filter definitions before measuring again. See
[the publication profile](../Reports/CAS_PUBLICATION_PROFILE_V308.json).

V308 passes all 2,915 Python tests. Native DLL bytes are unchanged from the
nineteen-target pass. A blank Qt permission surface no longer forces the launcher
to depend on captured pixels: the exact EA UIA control can be invoked after a
read-only child revalidates the pinned Sims launch immediately before input.
All 73 permission tests pass, and the actual V308 launch succeeds on its first
handoff. No UAC approval or foreground activation is automated.


### V312 completed Live matrix; V315 verification pending

V312 completes **230 Live selections**: every directed native pair separately on all five Sims, followed by extra Fairy → Vampire → Fairy return legs. Every existing appearance field and outfit row remains exact, as do all 155 named looks. Native category-9 outfit additions are retained and separately classified; this is not a claim of complete original-byte equality. Full CAS then retains all 195 captured records. Actual member clicks measure **631–749 ms** in this pass; the pair-panel update itself measures **1–2 ms**. The initial uncontended Live measurements improve to **1.47–2.04 seconds**, which still fails the speed goal.

The original Spellcaster tattoo-link → hair-unlink case fails again: the no-change deep copy itself changes category traversal. Publication remains blocked. Normal CAS cancellation retains all forty complete appearances, and all twenty disk save files remain exact. The process is later observed absent before another exit-confirmation input; the exit cause is unqualified, and no input is replayed. Captured metadata is archived with the original bank preserved.

V313's archive-directory batching passes **2,935 tests**; V314's complete-byte write acknowledgment and exact-type checks pass **2,942 tests**. These are combined in V315. The new native path preserves the destination's independent category-chain order after EA's head-insert copy/import, with every outfit payload unchanged. It validates the full map before linking any detached node, rejects source aliases/cycles/foreign categories and handles immutable empty buckets without writes. The original strict appearance comparator remains. All **19 native targets**, **26 seal tests** and **26 upgrade tests** pass. The next actual-game run must verify both the original failed pair operation and switching speed. Actual-save readiness and the other release gates remain open.
