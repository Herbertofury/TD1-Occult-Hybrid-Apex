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
| `NativeOverlay/` | Rebuilt x64 F11 ImGui component and `ApexOverlay.ini`; exact current-game hook compatibility is unverified |
| `Manifests/` | Exact artifact/resource/module identities and source baseline provenance |

MCCC is a concrete source of the ported Dresser part/color helpers. Its whole
unrelated automation suite is not included. Full MC CAS/MC Dresser feature parity,
Tray sources, numeric color codec, texture conversion, shared history across all
legacy actions and the regression/release gates remain unfinished.

## Install in your existing test profile

You handle game testing. Close the game normally before changing test artifacts.
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
5. The native component belongs in the game's `Game/Bin`, never in `Mods`.
   `NativeOverlay/install_to_game_bin.ps1` remains check-only by default and
   refuses unsupported imports, running games and an existing `d3d11.dll` owner.
   The currently inspected executable fails its import check. Do not overwrite
   another proxy or assume this candidate's F11 hook has been proven to load.
   The F11 interface compiles; resolving this game loader remains tracked work.
   The bundle preserves the installer's `build/Release/d3d11.dll` source layout.
   A custom key also requires the supplied `ApexOverlay.ini` beside the installed
   DLL; keep an existing user configuration if one is already present.

No installer has copied this candidate into your test profile or game directory.
No game launch, save load, native input or in-game mutation was performed for
this build. The older development script currently in your test profile is not
the new candidate.

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

The backend commands use the same game-thread dispatcher as the overlay. They
are also callable from the Sims console, without a native overlay:

```text
apex.studio status
apex.studio checkpoint "Before color edit"
apex.studio color_copy "0:HAIR"
apex.studio color_preview "1:HAIR"
apex.studio apply "PREVIEW_ID_RETURNED_ABOVE"
apex.studio undo
apex.studio redo
```

The new command signature is `apex.studio ACTION [VALUE] [SIM_ID]`. It prints the
full result, including preview IDs and history nodes. These source paths are
offline-tested, not game-tested.

## Rollback

Close the game normally. Remove only the candidate files you copied into the
test profile and restore your previous test artifact if needed. Retain your
disposable save and `TD1_OccultHybridApexData/CASHistory` recovery records. Handle any
native component through its recorded installer receipt and never replace an
existing unrelated proxy. Your original profile is left for you to rename.

The earlier UserSetting.ini copy did not reliably suppress DLC announcement
cards; that issue is still open. No false suppression or headless-launch claim
is attached to this candidate.
