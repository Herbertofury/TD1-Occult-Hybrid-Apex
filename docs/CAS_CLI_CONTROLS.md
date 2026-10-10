# Native CAS CLI controls

V27 adds `cas layer-select --target-layer 0` (Primary) and `--target-layer 1`
(Alternate/Dark). Supply the exact currently observed `--expected-layer`,
`--native-session`, `--household-id` and original `--sim-id` from a fresh
`cas status`. This navigation supports Vampire pairs in which both native
records report type 4. It does not relabel Primary as Human or authorize
alternate-layer acceptance. F11 exposes the same explicit native layer buttons.
The existing `form-select --form` remains restricted to an unambiguous native
pair; neither operation can select an arbitrary retained occult in one visit.
Generation 62 verifies actual Dark -> Primary, Primary -> Dark and edited
Dark -> Primary through this semantic command, without mouse input. Eleven
Dark edits have native readback, but their subsequent reconciliation fails on
another form's lost Mermaid genetics; navigation success is not retention.

The development CLI uses native CAS methods and a later native UI tick for readback. It does not click catalog tiles or run arbitrary game services. All commands require the marked disposable profile and an explicit existing Sim ID. A failed or unresolved command is not a successful edit. Poll its returned request ID; do not repeat a mutation.

The v23 candidate adds 27 typed operations to the earlier controls and five previously missing Vampire detail panels. The panel inventory contains 77 native menu states. Eyebrows and whiskers use the native face panel's string part selector; eyebrows then use a separate next-tick palette operation. They do not use the preset-index or clothing modifier-object setter. Every advertised typed control must have both execution and result dispatch before the package builder accepts it. Opening a panel and capturing every selected field are distinct from proving an edit persisted through CAS, Live, switching and disk reload. The complete per-form test matrix is still open.

Use `python -B tools/apex_cli.py cas panels --state .work/reusable-profile-session.json` for exact panel names, palette types and required command fields. Use `cas --help` for arguments. Examples below are fragments after that same CLI prefix; supply `--state` and `--sim-id` for each operation.

| Task | Command and exact native evidence |
| --- | --- |
| Open any mapped panel | `cas panel --panel skin_details`; actual visible native menu state |
| Discover available items | `cas catalog --panel skin_details --offset 0 --limit 8`; complete native page, total count and current filters |
| Enumerate variants | `cas variants --panel skin_details --data-id <native-base-id>`; returned native color family |
| Select clothing, skin details, jewelry, makeup, body hair, scars or Vampire details | `cas select --panel <name> --data-id <exact-returned-variant-id>`; native filtered panel membership, exact body type and selected item readback |
| Select head, nose, eyes, jaw, mouth, cheek, ears, chin or body presets | `cas preset --panel <name> --data-id <native-preset-id>`; exact native catalog index and preset record |
| Select eyebrow or whisker parts | `cas select --panel eyebrows --data-id <exact-variant-id>`; exact equipped identity, rather than a preset index |
| Discover tattoo body regions | `cas body-types --panel clothing_body_tattoos`; complete cycle of eligible native body region IDs, original region restored |
| Select a tattoo region | `cas body-type --panel clothing_body_tattoos --body-type <native-id>`; selected native region |
| Inspect all layers in that region | `cas layers --panel clothing_body_tattoos --body-type <native-id>`; complete native layer array, including medical entries |
| Add a tattoo layer | `cas layer-add --panel clothing_body_tattoos --body-type <native-id>`; exactly one empty append, other rows unchanged |
| Equip a layered tattoo | `cas select-layer --panel clothing_body_tattoos --body-type <native-id> --layer-index <index> --layer-id <identity> --data-id <exact-variant-id>`; exact item and layer identity |
| Remove or reorder a tattoo layer | `cas layer-remove` or `cas layer-move` with the same body/index/identity arguments; move also requires `--target-index`; complete other rows must remain unchanged |
| Remove an ordinary equipped item | `cas remove --panel <name> --data-id <equipped-id>`; exact selected identity absent afterwards |
| Discover skin, eyes, eyebrows, facial/body hair or animal palettes | `cas swatches --swatch-type <type> --offset 0 --limit 8`; complete paged native palette |
| Select a palette entry | `cas swatch --swatch-type <type> --data-id <native-swatch-id>`; actual selected native identity; fur also uses `--color-index` |
| Set weight or muscle | `cas physique --physique-type 0 --value 0.5` (weight) or type `1` (muscle); exact native physique array readback |
| Inspect a part's complete color slider records | `cas modifiers --panel <name> --data-id <equipped-id>`; complete native modifier ranges, values and unknown fields |
| Edit a part's four native color sliders | `cas color-sliders --panel <name> --data-id <equipped-id> --hue 0.1 --opacity 1 --saturation 0 --brightness 0`; each value must fit that part's returned range, then all four values and other fields must read back |
| Inspect or change native hair-color matching checkboxes | `cas hair-matching` or `cas hair-match --flags <0-63>`; exact native mask. This controls eyebrow/facial/body-hair matching, not independent outfit hairstyles |
| Discover every eligible voice and its pitch bounds | `cas voices`; complete native array for the original Sim's current species/age, including icon and unknown fields |
| Set a voice actor | `cas voice-actor --actor-index <zero-based-index>`; the game reports the resulting actor as a one-based number; primary full editor required |
| Set voice pitch | `cas voice-pitch --value <number>`; finite value inside the selected voice's native min/max, including negative pitches; primary full editor required |
| Discover or set a walkstyle | `cas walkstyles` or `cas walkstyle --data-id <returned-trait-id>`; complete native inventory and exactly one requested equipped trait; eligible primary full editor required |
| Inspect, enter or leave detailed edit mode | `cas detail-status`, `cas detail-mode --enabled` or `cas detail-mode --no-enabled`; the native detail-mode component must read back the requested state. This does not yet implement direct sculpt strokes |
| Inspect native catalog filters | `cas filters --panel <name>`; complete selected tags, excluded/context tags, pack IDs and native filter flags |
| Clear removable catalog filters | `cas filter-clear --panel <name>`; native ClearSelections, followed by the empty native filter-bubble readback. Required context and prohibited tags remain in the native filter record |
| Outfit category/number | `cas outfit --category <native-category> --index <existing-number>`; actual current outfit identity |
| Add an outfit | `cas outfit-add --category <native-category>`; one native append; no random replacement of an existing outfit |
| Native undo/redo | `cas undo` or `cas redo`; a real Sim/equipped-data difference, not only navigation |
| Navigate the observed occult pair | `cas form-select` with exact household, current layer, native session and target form; same original Sim/pair required |
| Return to Live | `cas return` with exact household and a new external `--output`; primary layer required, then actual simulation ticks and final pause |

Catalog paging has no total item cutoff. Packet size limits require another page; they never discard items. Native null results remain unavailable rather than being converted to empty inventories. A native tattoo component currently has five ordinary layers; medical layer 127 is protected from the tattoo removal/reordering commands. This is the installed game's native layout, not a history cutoff.

Appearance history has no edit-count or total-document cutoff. Inactive complete rows move into immutable content-addressed JSON archives, written and verified before references enter the active bank. The latest legacy completion and every active original/checkpoint/write-ahead record remain directly available. Older raw rows must verify against their length and SHA-256 when opened. No archive grants permission to replay a native mutation.

`cas-workbench --state .work/reusable-profile-session.json --sim-id <id> --output .work/new-workbench.json` visits the entire panel registry by default. Repeat `--panel <name>` to use a chosen scope. Add `--edit` to exercise different exact returned catalog items in the already-open full editor. One adjacent JSONL file retains every full response; the JSON manifest binds each byte range and SHA-256. Empty and unavailable panels remain visible. An unresolved acknowledgment or uncertain mutation stops the sequence without replay, acceptance or saving. Tattoo region/layer and featured-look workflows are reported separately; a completed workbench is not complete edit-path or Live-retention proof. Normal modifier slots use layer index `-1` and identity `0`; layered modifiers require an explicit existing index and non-medical identity.

If native success fails the Source postcondition, the complete rejected acknowledgment and validation error are retained under its original request ID. The request remains blocked: an invalid response cannot authorize another mutation or acceptance. This also distinguishes a rejected native reply from a reply that never arrived.

Voice and walkstyle are native Sim-wide properties. These commands do not claim that they are independently owned by each appearance lane. Remaining CLI coverage includes direct face/body sculpting, tattoo/coat/wing paint strokes, featured-look workflows, arbitrary native filtering/search selection, identity/trait/aspiration editors, and every native confirmation dialog. These require their own inspected contracts and native readback; the generic item setter is not a substitute. Full custom CAS-room, MCCC/manual-entry and save/reload parity remain release gates.

The installed build's read-only native UI exports are the primary contracts. Relevant public references include [S4CL outfit utilities](https://github.com/DeviantGameMods/Sims4CommunityLibrary/blob/main/Scripts/sims4communitylib/utils/cas/common_outfit_utils.py), [its appearance modifier implementation](https://github.com/DeviantGameMods/Sims4CommunityLibrary/blob/main/Scripts/sims4communitylib/classes/appearance_modifiers/common_attach_cas_parts_appearance_modifier.py), and [EditInCAS](https://github.com/Oops19/TS4-EditInCAS). None of those references establishes Apex's hybrid-form persistence or native CAS UI test results; native tests remain required.

Native inventory getter records are copied immediately into owned arrays/objects before the next native call. The package builder checks this rule in source and serialized bytecode. This protects the lifetime of complete data during bulk discovery; it is not a causally proven game crash fix.


Form selection automatically obtains a new owned native status immediately before navigation. The caller's exact household, current layer and native session must still match that observation; they are never replaced with guessed values. A pending/rejected preflight or mismatch blocks the selection. The complete preflight reply is retained in the result. This avoids expiring the Source's five-second freshness guard while an operator reads a previous status.


Generation 59 has native proof for a Fairy alternate's exact hair, eyebrows, head skin detail and nose preset through full CAS, primary-layer acceptance, explicit Fairy-only reconciliation and unpaused Human/Fairy switching. Other six stored forms remain unchanged. A controlled disposable save/seal passes; cold reload and complete per-form/category coverage are still open. See the [alternate test ledger](../Reports/ALTERNATE_CAS_2026-10-08.md).


`game cas --value full` now uses the native existing-household entry after
retaining all appearance owners. This corrects the single-Sim configuration
that hides personality and the selector even when forced full-edit is true.
The workbench accepts observed existing-family modes 0 and 7, verifies actual
forced full-edit and entry from Live, and never substitutes a new Sim.
The native and Source accept guards still require the exact original identity,
household and primary layer. All-occult same-visit navigation remains unfinished.
Native `CASCatalogFilter` slots are copied through data-class-only reflection,
retaining public fields and readable accessors rather than returning an empty
object for a sealed native record. Full native retesting remains separate from
passing the 1,546 frozen fixture checks and four native targets.

Actual existing-household mode 0 now has native proof for eleven Alien creature
panels, original-Sim Live return, explicit Alien-only decisions and unpaused
Alien → Vampire → Alien retention. Empty body skin details and failed tattoo
queries remain explicit. V25's accept path adds the native pending-name and
family validation required by this editor before the single SaveAndExitCAS;
name warnings refuse rather than selecting a dialog answer implicitly. The
earlier failed semantic request and separate successful native confirmation
remain distinct evidence. The host normal-quit guard now recognizes every
public typed control, while active peers and unresolved requests still block.

Cold `game load` can use the fixed native input route before the first household
has created TimeService. This narrow admission requires the exact installed
process/profile/script, a never-ticked bridge with no retained/pending queue
entries, and a complete fresh Home or uniquely indexed normal-load menu.
It provides no Sim-mutation or Live-completion authority. Normal Source CAS,
identity and clock verification remain mandatory once a household is loaded.
Native pre-input pointer refusals remain failed observations; they are not
silently treated as completed clicks.

For a cold start with an uninitialized hidden F11 renderer, the public native
CLI can initialize its frames before `game load`. First verify `bridge` and
`request overlay_status`; start only on the exact “F11 sidecar has not been
started” response. Then focus, show, observe status 3 with submitted frames,
and hide before capturing the ordinary menu:

```powershell
python tools/apex_cli.py request overlay_start --state .work/reusable-profile-session.json
python tools/apex_cli.py game focus --state .work/reusable-profile-session.json
python tools/apex_cli.py request overlay_show --state .work/reusable-profile-session.json
python tools/apex_cli.py request overlay_status --state .work/reusable-profile-session.json
python tools/apex_cli.py request overlay_hide --state .work/reusable-profile-session.json
```

Generation 67 verifies this sequence through the public CLI, with matching
native DLL, actual frame submission and `sim_data_read=false`. These are native
frame controls, not household readiness or headless-engine proof. Retain every
request UUID; an unresolved start/show/hide is not permission to replay it.

At the observed 2560×1385 Home viewport, native OCR can omit Marketplace while
returning exact Home, Resume Game, Load Game, New Game and Gallery labels.
The load gate admits that missing-label case only with both independent exact
Home/Resume headers and all three gameplay controls; duplicates, partial menus
and known blocking dialogs still refuse. The target uses fresh measured Load
Game bounds, and the requested save still needs its indexed name/hash/GUID,
unique normal-row Play and exact original-Sim Live readback. A completed Play
which opens the neighborhood map remains unresolved for Live. This rule is
covered by the 14 load tests and does not infer successful game input from OCR.
