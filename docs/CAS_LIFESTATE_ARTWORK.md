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
