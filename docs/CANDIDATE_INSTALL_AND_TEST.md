# Apex authorized-baseline development candidate

This is a concrete development build for owner testing, not a completed release
or a claim of current-game parity. Target game: PC 1.128.90.1030. Full accepted
scope and remaining work stay in `docs/CODEX_MASTER_EXECUTION.md`.

## Contents

| File | Implemented build content |
| --- | --- |
| `Mods/Apex/ApexOccultHybrid.package` | 159 authorized hybrid/turn/PlantSim/Servo resources; custom script references migrated into `apex_hybrid` |
| `Mods/Apex/ApexOccultHybrid.ts4script` | Recovered Apex backend, canonical owner queue, Studio/journal/helpers, and all 36 adapted hybrid modules; matching Python 3.7 bytecode |
| `Mods/Apex/ApexCASUnlocks.package` | All seven Crilender v1.9h packages consolidated into 39 unique resources; explicit Fairy addon precedence for two overlaps |
| `ExperimentalUI/ApexColorStudio.package` | Both authorized v4f slider and eyebrow SWFs merged; current-patch UI validation and converted texture coverage remain open |
| `Optional/` | Permanent PlantSim and separate PlantSim/Servo no-vampire-thirst policies, preserving optional baseline behavior |
| `Mods/Apex/Native/` | x64 F11 sidecar, matching SHA-256 manifest and configuration; loads through the game's own Python extension loader |
| `Manifests/` | Exact artifact/resource/module identities and source baseline provenance |

MCCC is a concrete source of the ported Dresser part/color helpers. Its whole
unrelated automation suite is not included. Full MC CAS/MC Dresser feature parity,
Tray sources, texture conversion, shared history across all
legacy actions and the regression/release gates remain unfinished.

## Install in your existing test profile

The owner reauthorized CLI game testing. Close the game normally before changing test artifacts.
Use the single existing test profile under
`C:\Users\Owner\Documents\Electronic Arts\The Sims 4` and your disposable test
save/Sim. The original folder named `The Sims 4 DO NOT FUCKING TOUCH!!!` is
read-only to the tools; only you may rename it.

1. Replace the previous Apex development script in the test profile. Keep only
   one Apex script version. Copy the contents of the bundle's `Mods` directory
   into the test profile's `Mods`. Leave `.ts4script` zipped, at most one folder
   deep. Enable Custom Content and Script Mods in the game's options.
2. Test the hybrid/package pair and CAS unlocks first. Original hybrid and
   Crilender files are incorporated into these Apex candidates; installing both
   copies creates overlapping owners. Check conflicts in the test profile only.
3. If testing the color UI, copy the experimental package into `Mods/Apex` as a
   separate test step. The public v4f baseline predates the target patch, and
   converted EA/CC textures are not supplied by this candidate. Slider UI alone
   cannot make every texture support custom colors.
4. Choose optional policy packages individually if you want their behavior.
5. Keep `Native/ApexOverlay.dll`, `Native/overlay-manifest.json` and
   `Native/ApexOverlay.ini` beside the script under `Mods/Apex`. This candidate
   requires **no Game/Bin copies**. Use Windows x64 and DX11. After loading your
   disposable household, the script checks the DLL hash and protocol and starts
   the DXGI hook. Press F11 with the game window focused. `AutoStart=0` disables
   automatic loading; `apex.overlay.start` starts it manually from the console.
   `apex.overlay.status` reports loading failures and native initialization state.
   The first keypress, actual DX11 render, resizing and render-state restoration
   passed in an independent hidden WARP test host. The matching DLL also
   initialized and submitted frames in the real game after verified CLI focus.
   F11 key/input and all menu-action acceptance still require proof; a foreign
   swapchain hook is refused rather than replaced.

The verified candidate installer has installed the package/script/native set in
the single marked test profile. It preserves external recovery copies and
refuses installation while the game runs. No game-directory deployment is required.
`Reports/LIVE_CLI_2026-10-07.md` distinguishes exact tested builds from later fixes.

## CLI testing and launch

Run from this checkout, using `.work/reusable-profile-session.json`:

```powershell
python tools/apex_cli.py launch-config status --state .work/reusable-profile-session.json --game-root 'C:\Games\The Sims 4'
python tools/apex_cli.py launch --state .work/reusable-profile-session.json --game-root 'C:\Games\The Sims 4' --execute
python tools/apex_cli.py game pause --state .work/reusable-profile-session.json
python tools/apex_cli.py game save --state .work/reusable-profile-session.json
python tools/apex_cli.py game focus --state .work/reusable-profile-session.json
python tools/apex_cli.py request overlay_show --state .work/reusable-profile-session.json
python tools/apex_cli.py request overlay_status --state .work/reusable-profile-session.json
python tools/apex_cli.py game capture --state .work/reusable-profile-session.json --output .work/cas-before.bmp
python tools/apex_cli.py game all-data --state .work/reusable-profile-session.json --sim-id YOUR_TEST_SIM_ID --output .work/sim-complete-before.json
python tools/apex_cli.py request cas_session_begin --state .work/reusable-profile-session.json --sim-id YOUR_TEST_SIM_ID
python tools/apex_cli.py game cas --state .work/reusable-profile-session.json --sim-id YOUR_TEST_SIM_ID --value full
# After accepting CAS and returning to Live:
python tools/apex_cli.py request cas_session_finish --state .work/reusable-profile-session.json --sim-id YOUR_TEST_SIM_ID
python tools/apex_cli.py game shutdown --state .work/reusable-profile-session.json --output .work/normal-save-exit-proof.json
```

The launcher selects the account's last successful Client Play content ID for
this exact installation, rather than guessing an edition. The owner's current
verified ID is `1015806`. The three game executables request `asInvoker`, but
had forced `RUNASADMIN` compatibility flags. Removing only those HKCU tokens
with an external recovery receipt enabled an observed CLI launch. Other
compatibility flags and executable manifests remain intact. To restore them,
use `launch-config restore` with the same game root, state and receipt.

Save verification observes a stable save-file rewrite. Full appearance/form
reload comparison is a separate gate. Native `quit` opens the main menu first.
The held native CLI click accepted CAS's checkmark, returned to Live, selected
Exit Game and then Save and Exit in the actual game. The normal save rewrite
and process exit were observed. `game shutdown` now recognizes both complete
native menus with local Windows OCR and selects their observed buttons; its
single-command end-to-end game acceptance still needs the next launch. It
retains every observation and requires both a normal slot rewrite and process
exit before reporting success. `--headless` explicitly
fails because an actual headless game runtime has not been implemented.

The repeatable `test color-cycle` and `test hybrid-cycle` commands require an
explicit Sim ID and evidence filename outside both profiles. They unpause
briefly to settle changes, record every request/observation, and leave paused.
They never blindly repeat an unresolved mutation or replace earlier evidence.

The new game-owned capture/input candidate adds `game key` (F11, Escape, Enter,
Tab and Space) and `game click`, requiring the observed viewport dimensions.
The native sidecar refuses input outside its own foreground game window and
refuses stale coordinates. Inputs are submissions; captured frames and game
data must prove the resulting UI state. Matching script/DLL replacement requires
normal game closure. F11 toggling, actual CAS checkmark acceptance and normal
Save and Exit now have game evidence; all controls and form persistence do not.

## Independent CAS form ownership

Switch to the intended form before choosing **Before CAS: Retain Originals** in
F11 → Forms or Phone → Apex CAS History. The command retains all form appearances,
occult membership/traits and the complete native Sim record. Enter native full
CAS or MCCC CAS, make the intended form's edits, accept, then return to Live.
Choose **After CAS: Accept This Form**. Only this form's returned appearance is
accepted; other form appearances are restored from their retained originals.
Returned appearances and full native records are saved before any recovery write.
Ambiguous destinations, failed readbacks and interrupted operations retain both
states and refuse further switches. This explicit single-form workflow is
implemented and has offline regressions; actual edited-form switch/restart proof
and automatic capture for every native/MCCC entry path remain open. Do not use
the legacy CAS restore action to accept a newer edit.

The accepted form bank preserves exact outfit/color bytes, physique, face,
genetics, pelt, skin tone/brightness, custom textures/tattoos and voice fields.
Appearance restores do not load old whole-Sim data or replace progression.
Accepted Human-looking Werewolf changes also update an existing form bank.

`game all-data` uses the exact game's full Sim save serializer, retaining native
bytes and every declared schema field, even absent or apparently irrelevant
fields. Runtime-only field coverage and complete owner editing remain open.
The Human-looking Werewolf controls are in Phone → Apex Forms and F11 → Forms,
or `request werewolf_human_on/off/status`. They copy appearance only, preserve
the original Werewolf look, and refuse automatic restore over a later CAS edit.
Visible human shape, gameplay and persistence still require the in-game test.

## Phone menu

The existing TD1 phone/Sim picker retains its original settings, continuations
and icons. Its main picker now also exposes Apex Settings, Forms, Saved Forms,
CAS History, Drift Guard, F11 visibility/status and diagnostics. Module-tuning
owners, invalid blank species entries, a malformed localization ID and the
placeholder-icon field are repaired. Apex actions use the canonical game-thread
dispatcher; history Undo/Redo prepares a preview and never silently applies it.
The settings rows read current values and refuse stale selections. Phone dialog
rendering, every original setting and full phone feature coverage still require
runtime acceptance.

## New Studio controls

The rebuilt F11 component adds **CAS History** and **Color Studio**, alongside
the recovered Forms, Saved Forms, CAS Categories, Drift Guard and MCCC Shield.
Change `ToggleKey=F11` in `ApexOverlay.ini` to another F1–F24 key before launch
to persist a different shortcut. Hidden mode sends no status polling requests.

Studio targets the selected Sim's **currently active form** and binds its journal
to save GUID + save slot + Sim ID + current-form flags. It does not silently switch forms.
Inspect outfits to see the serialized indices, then use `0:HAIR` (or the desired
index/BodyType) to copy an explicit uint64 color state. Color-only paste requires
the same CAS part ID/body type. Preview does not change the Sim. Apply checks the
whole current outfit snapshot again and rejects newer edits. Cancel leaves the
appearance unchanged.

History supports named checkpoints, previewed Undo/Redo/Jump, retained branches
and interrupted-transaction reconciliation. Copy a node ID from the timeline to
select a redo branch or jump target. Applying a restore records a new operation;
it does not erase the earlier states. New Studio operations have serialized
readback checks and rollback; **legacy mutations are not yet all journaled**.
Save/reload/form-switch persistence must still be tested.

The history table supports direct row selection and search by label/identity;
hover a row for its capture timestamp. Color Studio's outfit and part selectors
come from this form's serialized data. Duplicate BodyTypes remain individually
targetable by row, with exact resource/color and object/layer identities shown.
Controls explain absent color state or an unresolved runtime BodyType. After
Apply, inspect again to refresh the part inventory; the old preview token clears.
The advanced console/overlay target syntax is `outfit:BodyType:part-row`, for
example `0:HAIR:2`; leaving off the row is allowed only for a unique BodyType.

Select a part and click **Inspect selected part slider bounds** to enable numeric
hue, saturation, brightness and opacity controls. These read the effective CASP
resource through the game's resource manager, including any loaded overrides.
Only edited channels change; values quantize to signed Q14 and the preview shows
the actual result. CASP-disabled channels and out-of-range/nonfinite values are
rejected. Preparing an edit rechecks save/Sim/form, the whole outfit revision,
part/color identity and effective resource hash. Apply/Cancel/Undo use the same
recovery journal. Slider metadata does not establish texture compatibility; an
unconverted texture can still ignore the color. Skin specularity's brightness
lane corresponds to gloss in the authorized baseline CAS UI.

The backend commands use the same game-thread dispatcher as the overlay. They
are also callable from the Sims console, without a native overlay:

```text
apex.studio status
apex.studio checkpoint "Before color edit"
apex.studio color_copy "0:HAIR"
apex.studio color_preview "1:HAIR"
apex.studio color_inspect "0:HAIR"
apex.studio apply "PREVIEW_ID_RETURNED_ABOVE"
apex.studio undo
apex.studio redo
```

The new command signature is `apex.studio ACTION [VALUE] [SIM_ID]`. It prints the
full result, including preview IDs and history nodes. Current-form numeric color
edits, Apply/Cancel/Undo/Redo and inactive-form preservation have actual CLI proof
for the exact build recorded in the live report. This does not establish texture
render compatibility or full parity.

## Rollback

Close the game normally. Remove only the candidate files you copied into the
test profile and restore your previous test artifact if needed. Retain your
disposable save and `TD1_OccultHybridApexData/CASHistory` recovery records. Handle any
native component through its recorded installer receipt and never replace an
existing unrelated proxy. Your original profile is left for you to rename.

The earlier UserSetting.ini copy did not reliably suppress DLC announcement
cards; that issue is still open. No false suppression or headless-launch claim
is attached to this candidate.


## Equipped CAS inspector and complete-record checkpoints

F11 now has a searchable **Equipped CAS** list and a shared History workspace.
Click an actual equipped row to inspect its part resource and choose a replacement
from the same Sim/form wardrobe. Preview preserves destination references/layers;
Apply verifies exact appearance and synchronizes the accepted form bank.

History checkpoints retain the complete native Sim save model, runtime-discovered
schema, absent fields and unknown wire bytes, compressed losslessly. This includes
serialized preset results, eyebrows and every serialized part, rather than a
relevance-based category filter. Full-record tracking does not imply complete
runtime-only coverage or safe editing handlers for every gameplay field. Appearance
Undo includes shape, face, skin, genetics, tattoos, voice and every captured outfit;
it never loads a whole Sim or rewinds unrelated gameplay. Older outfit-only journals
are retained separately. Native CAS changes are observed when returned to the owner
and explicitly inspected/checkpointed; individual client-only CAS drags are not yet
automatically intercepted.

```powershell
python tools/apex_cli.py studio open-history --state .work/reusable-profile-session.json --sim-id 772674414928396571
python tools/apex_cli.py studio open-parts --state .work/reusable-profile-session.json --sim-id 772674414928396571
python tools/apex_cli.py studio part-inspect --state .work/reusable-profile-session.json --sim-id 772674414928396571 --value '0:2:0'
python tools/apex_cli.py studio record --state .work/reusable-profile-session.json --sim-id 772674414928396571 --output .work/native-history-record.json
python tools/apex_cli.py game capture --state .work/reusable-profile-session.json --with-overlay --output .work/history-ui.bmp
```

Use actual targets returned by `studio status`; the example row is illustrative.
Part previews use a bounded JSON value file containing `target`, `source`, `lane`
and `appearance_sha256`. GUI and CLI use the same current owner and transactions.
Native pointer controls now separate movement from button-down, scope DPI locally,
verify the exact cursor position and report release completion; accepting input
still requires an observed UI/data transition. EA administrator confirmation and a
truly headless EA game runtime remain unproven.

## Inspect and edit a stored form without activating it

The form selector scopes inspection, preview, Apply, Undo, Redo and Jump to that
form's independent history. Existing native forms are written to their stored
appearance owner and read back exactly. An accepted bank-only form can be edited
in its bank for the next switch. Neither path activates the form or changes the
current form's gameplay. An absent form is refused rather than generated.

The CLI uses the identical transaction path with `--form`, for example:

```powershell
python tools/apex_cli.py studio status --state .work/reusable-profile-session.json --sim-id 772674414928396571 --form 4
python tools/apex_cli.py studio undo --state .work/reusable-profile-session.json --sim-id 772674414928396571 --form 4
```

Form IDs are Human 1, Alien 2, Vampire 4, Mermaid 8, Spellcaster 16,
Werewolf 32 and Fairy 64; use the owners returned by status. Apply needs the
preview ID from the same form/save/Sim lane. A preview from another lane is refused.

The outfit selector and equipped list follow the selected form. **Show unequipped
categories** is optional; hiding empty rows changes presentation only. Group,
alphabetical/equipped-first/serialized-row ordering and search include skin details,
jewelry, eyebrows and runtime-discovered categories. Empty rows do not invent a
part. Complete native field/schema checkpoints remain retained regardless of these
display filters. Preset results are retained as native face/body/outfit data; the
original preset asset identity is available only if the game serializes it.

Current direct part editing replaces an equipped part from that form's own wardrobe.
Adding/removing empty slots, searching the entire game/CC catalog and complete
runtime-only/all-owner editing remain open checklist work.

## Independent hairstyles for every outfit

Enable **Keep hairstyles / colors independent per outfit** in F11, use the phone's
CAS History choices, or run `studio hair-enable --state ... --sim-id ...`.
This captures Hair and supported HairColorOverride rows for every existing form,
outfit category and category-relative outfit number, including exact uint64 color
values and absent/layered rows. The game’s real outfit-change callback restores
unaccepted propagation. Approved Studio changes update only their accepted outfit
rows. Repairs are journaled; clothes, skin, gameplay and unknown outfit fields stay
outside the repair. Disabling protection retains its captured data.

For native/MCCC CAS, choose the intended form/outfit in F11 and use **Before CAS:
edit hair only in selected outfit**, then **After CAS: accept selected edit** after
returning. This preserves returned hair in the explicit target and restores hair
elsewhere. The raw CLI capture accepts `{"hair_target":[CATEGORY, ZERO_BASED_NUMBER]}`.
Other outfits can retain different hairstyles and colors. A single CAS session
that intentionally edits hair in multiple outfits needs separate explicit targets;
automatic discovery of the CAS client's current editing target remains open.

The hook uses the installed game's `register_for_outfit_changed_callback` contract
and reattaches an enabled Sim on its first outfit change after loading. No per-frame
wardrobe scan is introduced. Replaced outfit identities, incomplete native arrays,
pending CAS/Studio transactions and unavailable owners are refused or deferred
without guessing. Existing corruption before capture cannot reconstruct lost hair.
Unpause briefly before checking live appearance; paused readback is data proof only.

**Duplicate selected outfit / preview** creates another numbered outfit in its
existing category, with a fresh identity from the game's allocator and all source
outfit fields copied. Apply, Cancel and exact Undo/Redo use the same form/history
transactions, including inactive forms. The CLI `studio outfit-duplicate` takes a
bounded value file with `source` (serialized source index), `category` (existing
destination category), `lane` and `appearance_sha256` from status. It refuses stale
owners/revisions, duplicate IDs and a sixth outfit in a category. User-facing outfit
numbers are category-relative and start at 1; CLI `game outfit` uses zero-based
`{"category": CATEGORY, "index": NUMBER}` for an existing outfit and still requires
unpaused visual verification.


## Native CAS semantic prototype

The optional `ApexCASBridge.package` targets the exact installed 1.128.90.1030 CAS resource, SHA-256 `8fe6d87964b8d2e1ad919972d8bb2168c4c176b9aab7300b2a838e638f87aad6`. It retains original class/script construction and 1,786 untouched native method bodies; one original Initialize method receives an Apex initialization call. Apex's compiled methods are appended with the native lexical scope. All non-script SWF tags remain unchanged. Game assets/decompiled exports stay in ignored local research and are not source-controlled.

This is a development prototype. The first full-class recompilation crashed on native CAS entry; compilation/offline tests do not prove game compatibility. The builder now refuses that approach. Do not treat an unresolved request as success or replay it. Pending request identity is retained for inspection.

Build from the locally extracted matching SWF and class export with Java 17 and FFDec 26.3.0:

```powershell
python -X utf8 tools/cas_ui_build.py --input-swf .work/research/current-cas-customizer.swf --decompiled .work/research/current-cas/scripts/widgets/CAS/Customizer/CASCustomizerMain.as --ffdec .work/research/ffdec/ffdec-cli.exe
python -X utf8 tools/build_candidate.py --foundry '<foundry executable>' --cas-ui-package dist/candidate/ApexCASBridge.package
```

The bridge replaces the same CAS Customizer resource as the earlier Color Studio UI experiment. The installer refuses installing both together. Native CAS UI data is separate from the accepted Live/form-bank appearance record.

```powershell
python -X utf8 tools/apex_cli.py cas panels --state .work/reusable-profile-session.json
python -X utf8 tools/apex_cli.py cas status --state .work/reusable-profile-session.json --sim-id <decimal Sim ID>
python -X utf8 tools/apex_cli.py cas panel --panel skin_details --state .work/reusable-profile-session.json --sim-id <decimal Sim ID>
python -X utf8 tools/apex_cli.py cas outfit --category 0 --index 1 --state .work/reusable-profile-session.json --sim-id <decimal Sim ID>
python -X utf8 tools/apex_cli.py cas result --request-id <returned request ID> --state .work/reusable-profile-session.json --sim-id <decimal Sim ID>
```

Inside F11, CAS History / Equipped CAS has an **Editing in native CAS** mode. Refresh requests a complete readout of all mapped panel catalogs, including empty/unsupported results. Selecting an equipped row requests its matching native panel and displays all returned item metadata. Panel opening does not reapply the item. Empty catalogs can be hidden; unsupported results remain distinguishable. Every item and returned CAS Sim field can be copied exactly. This is the current outfit/selected CAS form, refreshed on request; automatic freshness, all-outfit/inactive native CAS client editing and complete runtime Sim field ownership remain unfinished.


`cas diagnostics --state <session.json>` is read-only. It distinguishes native
CAS initializer observation from a verified client snapshot and reports whether
the distributor can send operations. An unresolved status read can be refreshed
after ten seconds; an unresolved edit still blocks subsequent edits. Startup
observation alone does not prove that catalog navigation or field edits work.


Open the native CAS equipped-items/history view directly through the CLI:

```powershell
python tools/apex_cli.py studio open-cas-parts --state <session.json> --sim-id <exact-id>
python tools/apex_cli.py studio open-cas-history --state <session.json> --sim-id <exact-id>
```

These commands select the exact Sim in F11 and submit one native CAS status
request. They use no category or menu pointer clicks. Pending requests remain
tracked; the readout labels the last acknowledged snapshot and its age. Presets
use their separate native query and preserve raw fields; a null/failed query is
not complete preset coverage. Direct native item writes currently support only
ordinary hair/tops/bottoms/full-body/shoes. Other panels still support navigation
and returned metadata; preset, layered, skin-tone and featured-look writes require
their own verified contracts.
