# Life-state artwork and variant browsing

The native CAS strip groups appearances by their named life state. It never
groups by the rendering genus: Ghost, Servo and Imaginary Friend can use the
Human renderer while retaining separate identities and appearances. Fairy,
Werewolf and Reaper alternate appearances likewise belong inside their life
state's menu. Human remains one shared entry.

Imaginary Friend has one top-level button. Its submenu exposes Lil' Monster,
Pegacorn, Spooky Kid and Wild Child, each with its own exact owner/token and
game artwork. Human / Real selects the existing shared Human; retained legacy
Real documents are not overwritten or deleted by this presentation change.
Browsing a submenu does not switch a form or alter appearance/gameplay.

Buttons use EA's tooltip component, with names and descriptions available even
on the selected button. Tooltips are shut down before controls are rebuilt or
CAS unloads. The strip retains its drag, lock, resize and collapse controls.

## Installed references

These references were read from the installed 1.128.90 simulation tuning. Game
images remain installed and load through EA's image loader; no image bytes or
EA source are bundled in this repository. Native occult icons continue to use
`GetOccultIcon`. Special references use type `2F7D0004`, group zero:

- PlantSim: `425BCD3B1EBB6371`, `buff_PlantSims_MainBuff_Visible` (162844).
- Human: `785DDFE321BCAE11`, EA's `OccultSelectionButton.HUMAN_ICON` in the installed CAS molecule.
- Servo: `75A1ACA2763417F0`, `trait_Humanoid_Robots_MainTrait` (218444).
- Skeleton: `57CABC4EE22AA528`, `buff_Skeleton` (175971).
- Ghost: `14094B494CD3F93D`, `headline_ghost.png`, base simulation tuning.
- Reaper: `632E51F43A7678CC`, `buffs_grimreaper.png`, base simulation tuning.
- Patchy: `A55AC15B5A63645D`, `headline_Scarecrow.png`, EP05 tuning.
- Imaginary Friend: `9EADF868D4FA1232`, `PieMenu_ImaginaryFriend.png`, base delta / EP20 tuning.
- Lil' Monster: `03843C32B120C44E`, `phone_imaginaryFriendLilMonster_icon.png`, EP20.
- Pegacorn: `463FF86E000CB962`, `phone_imaginaryFriendPegacorn_icon.png`, EP20.
- Spooky Kid: `C6742495A4CF0BD6`, `phone_imaginaryFriendSpookyKid_icon.png`, EP20.
- Wild Child: `3A60D722D08102F3`, `phone_imaginaryFriendWildChild_icon.png`, EP20.

The 64-bit instance travels as a decimal string, without conversion through an
ActionScript Number. Unknown mod-added life states retain their text label
rather than borrowing another occult's icon. Missing packs/artwork and complete
special-state gameplay remain separate compatibility/qualification concerns.

## CLI

`apex_cli.py cas form-menu --family imaginary_friend` opens that variant menu;
`--family all` returns to the main strip. Both require the usual `--state`,
`--sim-id` and retained `--output`. Readback includes unique life-state groups,
exact variant owners, names, artwork references and descriptions. Actual form
selection continues to use the separately validated `form-owner-select` command.

## Runtime checkpoint

V198's actual native-menu Alien -> Vampire -> Alien cycle retains each exact
owner and mask 127, with the native button visible after both switches. Human's
EA artwork is visually verified. A native Fairy card supplies the missing wing
paint layers and produces purple wings that remain coloured through Fairy ->
Alien -> Fairy. The complete 195-owner audit finds changes only in the fourth
member's Fairy; a deeper outfit comparison finds only its wing part changed.
Five-member Live acceptance, repeated settled switching, normal save and V200
cold loading retain all forty appearances and five named-form documents.
This qualifies that stock-card edit, not automatic repair of empty paint data,
the quarantined semantic wing API or complete Fairy gameplay.

V197 development checkpoint: Human now uses EA's actual species-button icon,
visibly verified in V195 full CAS. The owner confirms the third Sim itself is
intact; the suspect crop was a stale portrait, so no appearance reset is applied.
V195 and V196 cold loads retain all forty native appearances and each member's
saved named forms after simulation advances. Save files and seal ledger stay
unchanged. These results do not qualify every editing category or Tray/Gallery.

The package now also patches the installed CAS molecule: a combined membership
mask must not be passed to the single-occult icon lookup; existing-household
full editing must not depend only on `SimIsNew`. Its choices route retained
hybrids through exact independent-owner tokens instead of native conversion.
The final widget redraw restores the actual button and emits bounded read-only
visibility/geometry observations. CAS's display genus follows the bound owner
without changing memberships, traits or native appearance data.

V196 runtime QA catches an incorrect plain-string `TooltipExtension.SetText`
call that interrupts widget loading. V197 uses the inspected `Text:Object`
property instead of the `SetText(LocKey)` method; six source/API checks and 143
compiled bytecode checks pass. The CLI now refuses entry readiness after a new
native UI exception even when its inventory socket connects. Corrected native
button operation and Fairy wing/material editing still require runtime proof.
Do not use V196 for play. V197 passes 2,601 regression tests, loads full CAS
without a new UI exception, and its actual native popup routes Alien to the
retained Vampire owner with mask 127. Subsequent redraws hide the button again.
V198 corrects the molecule's private HouseholdSimData presentation mask rather
than changing SimInfo membership. It is built, with seven molecule/API checks;
repeated popup operation and Fairy editing remain runtime gates. These are
development candidates.

V194 shows all thirteen occult/special icons in actual full CAS, including the
Ghost resource whose base and delta art differ. EA's loader resolves its current
installed image. Human's native icon getter returns no artwork, so Human / Real
retains its explicit label pending shared portrait integration.

The real Imaginary Friend button opens four labelled, illustrated variants and
the shared Human / Real shortcut. Clicking Spooky Kid selects that exact named
owner; Pegacorn and the original Alien remain separately selectable. A native
hover capture shows the actual description. Menu browsing and a selected-Alien
click preserve every member's graph generation, selection and logical bindings.
These checks do not qualify independent variant edits or special gameplay.

A complete 39-owner export after Spooky Kid -> Pegacorn -> original Alien
compares identically with the pre-entry fields. No appearance edit or save was
submitted during these menu tests. The disposable session remains in full CAS.
