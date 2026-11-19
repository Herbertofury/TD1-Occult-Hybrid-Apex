# Full TODO — Apex Occult Hybrid

The canonical executable checklist is [docs/CODEX_MASTER_EXECUTION.md](../docs/CODEX_MASTER_EXECUTION.md). This page is the human-readable wiki view.

## Controlling CAS correction — 2026-10-17

Use one shared Human appearance and modify EA's actual portrait UI and form
behavior. Preserve existing EA form layouts; forms without a paired portrait
interface get their own form above the shared Human with full linking/copying.
This never substitutes Vampire data or merges forms. Alien retains EA's
existing portrait arrangement and gains missing Link/Unlink and Copy controls.
Use the [player-focused judgment rule](../.cursor/rules/apex-player-first-hybrids.mdc)
throughout development and QA. All supported forms need actual independent editing,
explicit linking/copying and household/save/Tray retention. Duplicate internal
records are not separate player-facing forms or proof of completion.

Follow the [shared-Human implementation and QA checklist](../docs/CAS_SHARED_HUMAN_REQUIREMENTS.md).
This supersedes older layout assumptions; the historical checkpoint below does
not establish current implementation or runtime readiness.

## Current checkpoint — 2026-10-18

- [x] V204: verify actual Alien -> Vampire -> Alien on every household member,
  retain all 195 records during linked no-edit refreshes, and verify unlinking.
- [x] Verify all five actual native portrait pairs and measure a native strip
  click at 15 ms to bound-owner acknowledgement; rendered readiness is separate.
- [x] Retain the failed direct Human-paint return proof. Restore all forty
  appearances and five named documents through the guard; unpause for 887 ticks,
  pause again, and verify every save file and the ledger are unchanged.
- [ ] Reuse EA's actual category checkbox link/copy panel for each independent
  pair. Add missing category support, pair-scoped preferences and selective undo.
- [x] V205: verify CAS-only animation isolation in 37 visits across all five
  members and all seven native genera; Werewolf keeps its flag, other forms
  do not, and every field in all 195 captured records remains unchanged.
- [x] Retain V205/V206's failed first-preview proofs. V206's late actor is
  reproduced by native tests; its no-edit audit retains all 195 records.
- [x] V207: verify initial full-CAS Alien animation before any form switch;
  complete thirteen preview visits across all five members/all seven native
  genera, then retain every field in all 195 records and every test save file.
- [x] V207 cold load: retain forty Live appearances and five saved named
  documents through 731 simulation ticks, with save/ledger unchanged and paused.
- [x] V204 full regression: 2,645 passes. V205 native regression: 12 passes.
- [x] Reproduce and fix no-edit native Sync propagating through a new link;
  compare complete native serialized data, including unknown fields.
- [x] Add native regressions for unlinking and directed-copy isolation when
  the destination is also linked to a third form.
- [x] Cold-load V203: retain forty native appearances and five named documents
  after 740 simulation ticks, pause again, and keep the save/ledger unchanged.
- [x] Qualify V204 next-frame switching, actual paired portraits and toolbar
  placement in the observed viewport; verify linked no-edit full-field retention.
- [ ] Prove actual linked edits and directional whole/partial Copy isolation.
- [x] Replace HUM with EA's actual Human artwork; verify it visually in full CAS.
- [x] Verify V195/V196/V197 cold loading preserves forty native appearances and five
  independent saved named documents after simulation advances; keep save/ledger unchanged.
- [x] Fix the observed native tooltip API type mismatch and add its regression check.
- [x] Reject CAS readiness when a new native UI exception occurs despite a connected inventory.
- [x] Exercise actual native-menu Alien -> Vampire -> Alien selection in full CAS;
  retain mask 127 and the distinct Alien appearance, with the button visible after both switches.
- [x] Exercise all six native popup forms on all five household members;
  compare every field of all 195 captured owners with no unintended change.
- [ ] Correct the CAS-return Human paint merge: Werewolf/Fairy active paint
  reaches Human before the guarded receiver restores its authoritative data.
- [ ] Keep the strip clear of native popup cards on short viewports; qualify fresh
  geometry separately from the cached SetSimInfo observation during animations.
- [ ] Fix and qualify grey Fairy wings, style/color editing and independent retention.
- [x] Qualify the fourth member's native purple wing-card selection through
  Fairy -> Alien -> Fairy, Live switching, normal save and a cold load.
- [ ] Qualify prompt portrait refresh separately from actual appearance integrity.

V197 passes 2,601 regression tests and loads full CAS without a new UI exception.
Its native menu opens and selects the actual retained Vampire owner from Alien,
with all six memberships retained. A subsequent molecule redraw hides the button
again: its private HouseholdSimData still carries the combined mask. V198 uses
the selected genus on that presentation model only, retaining full membership
on SimInfo and the native owners. It passes 2,602 full regression tests, seven
molecule/API checks, and the actual Alien -> Vampire -> Alien popup cycle. All
forty native appearances and five named documents survive its cold load and
935 simulation ticks. A native-card edit selects purple Fairy wings 473791,
which remain visibly coloured through Fairy -> Alien -> Fairy. The 195-owner
comparison changes only that fourth member's actual Fairy outfits, genetics
and pelt fields; all other 194 appearances remain unchanged. Live acceptance
from that member requires shared-Human owner navigation in the CLI rather than
the incomplete legacy pair; its 78 return/settlement tests pass. The household
commit now succeeds for all five members. All forty Live appearances match
after 989 ticks; fourth-member Alien -> Vampire -> Alien -> Fairy also passes
with no added outfits. A normal save retains all forty appearances and creates
all five named-form seals. The
subsequent OCR-angle fix passes 24 OCR and 307 host game tests; the captured
8.5-degree Home-menu case now targets Resume correctly. V196's
widget-loading failure is retained as failed evidence. Do not promote these
candidates to actual-save readiness or close hybrid/link/copy/Tray gates.

V199 passes 2,615 full regression tests and twelve native checks. Its installed
frame-separated pointer completes normal background exit. The native cold load
retains all forty appearances, but its saved named-form admission rejects the
qualified V198 source. V200 explicitly admits only that audited schema-compatible
metadata source, without native appearance restoration authority. Its cold load
reopens all five independent named documents and retains all forty native
appearances before and after 946 simulation ticks; save and ledger stay unchanged
and Live is paused again. Ninety-two focused save/upgrade/return tests pass;
the frozen V200 complete regression passes 2,616 tests in 776.817 seconds.
The subsequent 38-selection household popup pass retains all 195 captured
owners. All five receiver commits and forty Live appearances pass after 881
ticks, including every independent named document, with save/ledger unchanged.
Before those commits, Human paint alone differs on the Werewolf/Fairy members:
it equals their active paint bytes. That return-boundary defect remains open.
The host CLI now uses the native pair's actual base owner for acceptance,
including Alien above its Human disguise, and refreshes/reconnects only status
after a native read; all 83 return tests pass without changing the game build.
The background CAS-grid fix still needs a real grid-selection check. Initial
Fairy records with empty wing paint data and semantic wing selection remain
open; successful stock-card editing does not qualify their separate repair/API.

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

Historical V180 preparation: the V179 allocator crash did not hit an Apex
owner guard. Event callbacks now queue socket cleanup for the next UI Timer,
ignore stale socket events, and send a single retained ASCII frame with lossless
Unicode JSON escaping. All 76 focused checks pass, including serialized unsafe
callback/buffer cases. Earlier full CAS checks passed 959 tests and ten native
checks pass. V180 runtime qualification remains open; production use is not
qualified, and all save/Tray and native copy/link gates stay open.

V178 crashed after nine visits and six body edits; a same-build collapsed-strip
run reproduced a crash after six visits/four edits. It is unsafe for real-save
use. All twenty disposable save files remain unchanged. V179 diagnostic
preparation removes repeated idle metadata redraws and adds opt-in protected
Apex owner allocations to identify memory misuse. No crash-fix claim is made.
Actual native copy/link, complete household/category edits and save/Tray/Gallery
qualification remain unfinished.

Historical V178 preparation: the cold runtime test was pending. V177 reproduced the cold fourth-member
Alien body-edit allocator crash despite retaining EA's layer lifecycle. V178
matches the stock slider's preview -> completion sequence, with an owner check
and consumed one-shot completion state. Compiled bytecode checks pass; this
does not establish a crash fix. V177's pre-gesture CAS suite passed 957 checks.
All twenty save files still match. Production use remains unqualified.

V177 is built; runtime cold Fairy -> Alien qualification is pending. It retains
EA's actual layer-transition lifecycle rather than manually flipping its layer
byte before the inner binder. Nine native checks pass. After the V176 crash
reproduced, the fourth member retained three distinct Human/Vampire/Alien body
edits through six switches. Full audit of all 195 captured owners finds only
those three intended fields changed, with no lost originals or added outfits.
Cancellation and unsaved exit leave all twenty test saves unchanged. This does
not qualify all categories, actual copy/link controls, CAS return or save/Tray.

Historical V176 checkpoint:

V176 is installed only in the disposable profile. The native adapter now writes
the exact displayed logical form to its EA cache lane, retaining older aliases
without copying them over the player's edit. Link propagation follows direct
configured scopes, and UI snapshots query only the current panel. Nine native
checks pass. V175's real test retained twelve body edits across three members
but crashed during the fourth member's first body edit. The allocator failure
is preserved and unexplained; all twenty test saves are unchanged. V176's cold
readback matches all forty original appearances. Current household editing and
return validation, actual EA copy/link controls, all-category coverage and
save/Tray/Gallery round trips remain open. Do not use this checkpoint as a
production-readiness certificate.

## Execution checkpoint — 2026-10-07

The owner-selected V9.6 source is preserved and the actual authorized hybrid, Crilender, MCCC and Color Sliders files are implementation bases. Six packages/204 resources and a matching 47-module script build; Foundry independently extracts/verifies every resource. Four ported MCCC helpers match nine original-bytecode cases. F11 now has a mod-folder sidecar loader plus numeric H/S/B/O controls using actual CASP ranges and shared preview/Apply/Undo recovery. 101 offline fixtures, 21 native data checks, actual independent DX11 menu/color rendering and packaged Python 3.7 extension-loader checks pass. The metadata reader matches 32 installed-game CASPs and nine original C# writer versions. Source/build leaves T207/T208 are checked with proof. See [the current report](../Reports/SIDECAR_AND_COLOR_2026-10-07.md) and canonical task proofs. Current-game compatibility and all runtime/regression/release gates remain open.

The owner handles game testing. The new candidate is not installed or launched by the agent. The exact original `The Sims 4 DO NOT FUCKING TOUCH!!!` folder is read/copy-only; only the owner may rename it. One test profile retains the disposable save/Sim. Older isolation/launch history is preserved in the reports with its original evidence limits. This remains a repository wiki mirror, not a claim of publishing GitHub's live Wiki.

## P0 — standalone Apex Occult Hybrid Core

- Ship `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script` as the canonical hybrid engine.
- Start from the newest authorized working TD1/LordPercival hybrid package/script set; import/inventory and work upward from it.
- Owner confirms full author permission to use the hybrid baseline material in Apex.
- No TD1/TwelfthDoctor1/IcedCream/LordPercival hybrid runtime dependency in the final install.
- Preserve/port useful working 1.13.7 behavior first, then improve it.
- Support compatible multiple-occult membership and normal transformation paths.
- Safe Add/Remove Occult.
- Verified form switching without stuck/snap-back states.
- Switch occult gameplay/perk/motive panels without changing membership.
- Preserve Spellcaster charge / Werewolf Fury and other occult progression.
- Replace remove-all-occults-before-CAS with targeted state/form reconciliation.
- Patch-aware current-game tuning/resource generation.
- Clean Mods profile proof with Apex + official EA packs only.
- Full details: [Apex Occult Hybrid Core](Apex-Occult-Hybrid-Core).

## P0 — behavioral reference and safety

- Independently close every verified useful 1.13.7 behavior/fix without depending on upstream files.
- Reconcile authoritative SimInfo/OccultTracker state versus transient caches.
- Prove no native render-thread gameplay mutation.
- Prove save/reload/restart on representative hybrids.
- Fail closed on unknown game/native hook surfaces.

## P0 — original-mod regression closure

- CAS and MC Command Center edits must actually persist to the intended occult form.
- CAS must never delete secondary hybrid forms.
- Hybrids must never get stuck in one form.
- Werewolf hair/headwear/body/CAS parts and custom content must survive category/outfit/form changes.
- CAS entered while already in werewolf form must save correctly.
- Skin details, makeup, hair, tattoos, accessories and clothing must not bleed across forms or disappear.
- Stale CAS/MCCC/recovery snapshots must not overwrite newer intentional edits.
- Human and occult forms must remain independently editable.
- Every repair/commit must verify success after switching away/back and after save/reload.
- Full details: [Original Mod Regressions](Original-Mod-Regressions).

## P0 — Apex Live CAS Studio

- Owner confirms full author permission to study/use MCCC CAS-related implementation material.
- Start from current authorized MC CAS + MC Dresser + shared CAS helpers; preserve/port strong working behavior before replacing it.
- Make CAS-grade appearance editing available from Live Mode/F11 wherever the game exposes a safe runtime or non-UI CAS-service path.
- Body/face values and presets outside CAS.
- Searchable CAS-part browser outside CAS.
- Copy outfit category/slot within one Sim.
- Copy outfit Sim A -> Sim B.
- Copy **all outfits** Sim A -> Sim B.
- Copy Face / Body / selected CAS categories / full appearance between Sims.
- Searchable Tray/household source browser with preview.
- Saved appearance/outfit libraries.
- Visual include/exclude/lock/custom-definition rules.
- Safe randomize by outfit/category/body type.
- Exact human/occult form targeting.
- Missing CC/pack diagnostics.
- Bulk selected-Sim appearance operations.
- Every change previewable and Undo/Redo through CAS History.
- Current MCCC occult copy/body-part persistence fixes are permanent regression tests.
- Final clean-profile proof with no MCCC installed.
- Full details: [Apex Live CAS Studio](Live-CAS-Studio).

## P0 — Apex Color Studio

- Owner confirms full permission from thepancake1 for relevant Color Sliders baseline material.
- Start from current authorized Color Sliders v4f package/tooling and work upward.
- Preserve full compatible ColorState: base swatch + Hue + Saturation + Brightness/Value + Opacity.
- Every part/category/outfit/all-outfits/Sim/form copy must preserve exact custom color by default.
- Add explicit Part+Color, Part-only, Color-only and base-swatch-only copy modes.
- F11 Color Studio works without the original Color Sliders mod installed.
- Native CAS slider support is first-party Apex, patch-aware and optional.
- Automatic current-game/installed-pack texture conversion coverage.
- More CAS Columns and original Color Sliders coexistence/conflict diagnostics.
- Saved colors/palettes and color-aware randomization.
- CAS History/Undo/Redo/Saved Forms preserve exact ColorState.
- Human/occult form colors remain independent.
- Full details: [Apex Color Studio](Color-Studio).

## P1 — make F11 the best way to use the mod

- Selected-Sim dashboard with active occults/current form/health.
- One-click occult enable/disable with safe confirmations.
- Form switching with target preview.
- Searchable/renameable Saved Forms.
- Category-scoped copy/paste/commit/apply-all.
- Undo for the latest safe reversible appearance operation.
- Keyboard/focus/accessibility pass.

## P0 — Apex CAS Unlock Core

- Start from the newest authorized Crilender CASUnlocks v1.9h package/addons; import/inventory and work upward from them.
- Owner confirms full author permission to use Crilender baseline material in Apex.
- Own the final unlock behavior instead of permanently depending on the old package.
- Keep supported CAS categories unlocked through CAS entry, form switch, outfit switch, MCCC CAS and UI rebuilds.
- Default hybrid-aware Werewolf/Vampire/Mermaid/Fairy/Alien category expansion.
- Optional hidden/locked/debug/reward/occult item catalog.
- Installed-pack detection; no manual deleting pack files the user does not own.
- Preserve authorized working Crilender resources where strongest; replace only when Apex has a demonstrably better path.
- Patch fingerprint + current-game resource scan + deterministic regenerated unlock package/manifest.
- F11 Unlock Matrix explaining exactly why a category/item is available or blocked.
- Detect overlap/conflicts with other CAS unlocker overrides without deleting them.
- Werewolf faces/hair/headwear/base-layers/category regressions are P0.
- Full details: [Apex CAS Unlock Core](CAS-Unlock-Core).

## P1 — CAS History Studio

- Live Photoshop-style CAS history while edits happen.
- Undo / Redo / jump to any prior state.
- Preserve redo branches when editing after undo.
- Named checkpoints and Compare-with-current.
- Inspect exactly which CAS parts/resources/values were added, removed or replaced.
- Separate history lanes for human and every occult/custom form.
- Revert one change or category without damaging unrelated data.
- Safe cross-form cherry-pick with compatibility checks.
- Optional Reference Shot images at checkpoints, not every micro-change.
- Interrupted-session journal recovery.
- Reuse the same F11 overlay/injection, snapshot/diff engine and game-thread mutation queue.
- MCCC Shield, Drift Guard, Post-CAS Commit and Saved Forms all use the same CAS Change Journal.
- Full details: [CAS History Studio](CAS-History-Studio).

## P1 — CAS/MCCC/Drift

- Explicit MCCC Shield state machine.
- Lot51 event path + manual fallback.
- Stale-snapshot prevention.
- Drift diff before repair.
- Repair category / occult / explicit all separately.
- Persist minimal recovery state across interruption.

## P1 — diagnostics

- Selected-Sim cache view.
- Global cache view.
- CAS-session cache view.
- Explain why each occult/form is present/pending/inconsistent.
- Structured export suitable for bug reports/Codex.

## P2 — performance

- Zero hidden HTTP polling.
- Zero idle continuous Sim scans.
- Request coalescing while overlay is visible.
- Stale-response cancellation/generation IDs.
- PresentMon/WPR proof of non-regressive frame time.

## Release gate

Do not call Apex finished until R001–R010 in the original-mod regression ledger are no longer reproducible and the current Sims 4 build has exercised the actual F11 workflows including the standalone Apex Occult Hybrid Core, Apex Live CAS Studio, Apex Color Studio/full ColorState copy, CAS Unlock Core/Unlock Matrix and CAS History/Undo/Redo, representative hybrid combinations, CAS/MCCC recovery, Drift Guard, diagnostics, persistence, upgrade path and measured overlay overhead.
