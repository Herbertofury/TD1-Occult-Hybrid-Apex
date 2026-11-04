# Appearance transfer and native Tray groups

Cross-form appearance paste is explicit: Alien → Human, Vampire → Mermaid,
and other represented source/destination pairs use the same transfer path.
It does not change the destination Sim's identity, household, occult membership,
traits or progression. A paste targets one selected appearance owner; it does
not merge the other occult looks.

In F11's appearance room, select the destination Sim, form and numbered outfit,
then expand **Copy / paste appearance**. Copy any existing form, or load a Tray
source with the CLI below. The source's name/form remains visible above the
paste controls. Whole appearance, one outfit, skin details, tattoos and custom
field/category selections are available. The shared **Apply immediately**
checkbox defaults off: try-on changes the independent preview, and Apply keeps
it. Discard and journal Undo retain the previous appearance.

One-outfit paste preserves the destination's outfit ID/category. Category-only
paste preserves all other parts and their parallel color/object/layer arrays.
An empty selected source category removes only that destination category.
Whole wardrobe maps category plus numbered outfit, preserving destination IDs
and additional destination outfits. Unknown or unavailable selected fields
are refused; values are not fabricated.

The CLI needs the existing marked disposable profile state. Examples use
explicit IDs and externally saved receipts; replace the placeholders:

```powershell
python -B tools/apex_cli.py studio copy-appearance --state <state.json> --sim-id <source-id> --form 2
python -B tools/apex_cli.py studio paste-preview --state <state.json> --sim-id <destination-id> --form 1 --value-file <paste.json>
```

`paste.json` binds the source clipboard and fresh destination status:

```json
{
  "clipboard_id": "<32-character id from copy>",
  "clipboard_sha256": "<64-character hash from copy>",
  "lane": "<destination history_lane>",
  "appearance_sha256": "<destination appearance_sha256>",
  "selection": {
    "fields": [],
    "outfits": "one",
    "source_outfit": 0,
    "target_outfit": 0,
    "body_types": [3]
  }
}
```

`body_types` selects runtime CAS category IDs; an empty list selects the whole
outfit. `outfits` is `none`, `one` or `all`. `fields` may select physique, facial
attributes, skin tone/shift, pelt, genetics, custom texture, custom tattoos and
voice fields actually present on both owners. Outfit parts have their own
scope, rather than an unchecked raw outfit identity overwrite. Clipboard data
is bounded, immutable and expires with the running game process.

## Tray source workflow

```powershell
python -B tools/apex_cli.py tray list --folder <read-only-Tray-folder> --output <new-list.json>
python -B tools/apex_cli.py tray inspect --household <exact.householdbinary> --expected-sha256 <file-hash> --output <new-inspection.json>
python -B tools/apex_cli.py tray preview --state <state.json> --inspection <inspection.json> --expected-sha256 <inspection-hash> --source-sim-id <tray-id> --form 4 --outfit-index 0 --target-sim-id <existing-live-id> --target-form 8 --output <new-preview.json>
python -B tools/apex_cli.py tray paste --state <state.json> --inspection <inspection.json> --expected-sha256 <inspection-hash> --source-sim-id <tray-id> --form 4 --target-sim-id <existing-live-id> --target-form 8 --selection <selection-only.json> --output <new-paste.json>
```

`selection-only.json` is the inner `selection` object above. Paste defaults to
try-on; `--apply-immediately` explicitly commits. Inspection and preview keep
the exact original native Sim bytes and only expose forms present in that Tray
record. The independent viewer has a separate source-form/outfit switcher and
**Copy displayed Tray form** button. The actual selected destination stays an
existing game Sim. A Tray preview never creates a Sim or saves the game.

Native Tray records share some data, notably pelt/custom texture where the
stored-occult schema lacks its own field. Inspection reports `shared_fields`
instead of claiming independent data that the Tray file does not contain.

```powershell
python -B tools/apex_cli.py tray export --folder <Tray-folder> --item <exact.trayitem-filename> --archive <new-bundle.zip>
python -B tools/apex_cli.py tray import --state <state.json> --archive <bundle.zip>
```

Bundle exchange preserves the complete existing native item group, metadata,
images, original household footer and unknown bytes, with per-file hashes.
Import writes only into the marked disposable profile's Tray. Existing
identical files are reused; differing files are refused without overwrite.
The owner's protected original remains read/copy only. This exchanges existing
library items; creating a new native Library item from the current Live Sim
remains a separate unfinished integration.

## Werewolf styles

New occult creation retains the EA-generated appearance instead of overwriting
it with Human. On an existing damaged Werewolf form, **Try EA-generated Werewolf
defaults** prepares a reviewable replacement and retains all original owners
before generation; Apply/Undo use the ordinary appearance journal. Native coat
sharing with Human is restored before returning that preview.

**Human / personal CC look** is explicit and defaults off. Its first use copies
the existing Human appearance; later toggles retain separate edited EA and
Human/CC styles. The independent renderer uses the Human visual path for that
style while the actual gameplay owner remains Werewolf. Exact native Live
visual behavior, fresh full CAS/MCCC editing and save/reload acceptance must be
verified separately; fixture or independent-render success does not prove them.
