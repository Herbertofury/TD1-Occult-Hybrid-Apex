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
```

The launcher selects the account's last successful Client Play content ID for
this exact installation, rather than guessing an edition. The owner's current
verified ID is `1015806`. The three game executables request `asInvoker`, but
had forced `RUNASADMIN` compatibility flags. Removing only those HKCU tokens
with an external recovery receipt enabled an observed CLI launch. Other
compatibility flags and executable manifests remain intact. To restore them,
use `launch-config restore` with the same game root, state and receipt.

Save verification observes a stable save-file rewrite. Full appearance/form
reload comparison is a separate gate. Native `quit` opens the game's Save Game
confirmation; automatic selection of Save and Exit remains unfinished. Do not
interpret request acceptance as completed shutdown. `--headless` explicitly
fails because an actual headless game runtime has not been implemented.

The repeatable `test color-cycle` and `test hybrid-cycle` commands require an
explicit Sim ID and evidence filename outside both profiles. They unpause
briefly to settle changes, record every request/observation, and leave paused.
They never blindly repeat an unresolved mutation or replace earlier evidence.

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
