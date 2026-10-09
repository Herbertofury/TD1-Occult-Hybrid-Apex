# F11 equipped item names, thumbnails and Studio

Generation 40 remains frozen at Source `9cb1938e…`, AS v4 `9edad97e…` and DLL
`3d7c5960…`, from candidate `ced3c256…`, with all 14 artifact records retained.
Exact identities and earlier failed leaves are in the
[runtime ledger](../Reports/LIVE_CLI_2026-10-07.md).

The current v5 observation is PID 27788, original disposable Live household,
clock speed 0 and native slot 0. The prior MapPlay receipt remains failed after
six autosave-file changes. Separate read-only observation verifies stable paused
identity twice and all 18 save files unchanged during that observation; normal
Slot02 loading and A0 restoration remain unverified.

Current F11 renders 13 equipped Swimwear names and 119 category choices. The
first inspected frame retains unavailable thumbnails while the broker was off.
After the existing broker started, one resource-cache Refresh and separate native
captures verify the selected Hair name and actual 104 × 148 PNG, exact CASP TGI
and enabled containing-package Studio-copy button. Color inspection retains that
name/image; the scrolled view renders Hue/Saturation/Brightness/Opacity and the
wheel. The observed HSV ranges are −0.5 to 0.5, Opacity 0.2 to 1, native CAS step
0.05 and Q14 resolution 1/16384. Values remain 0/0/0/1. No Preview, Apply or color
change was submitted. A failed heading-collapse attempt is not a successful UI
transition. The current render/inventory aggregate is
`72bc5472d9f5e1fc16e55a74918dceca09a81e6e28de63201ebb94ecd415ca3a`;
all 18 saves stayed unchanged and the Sim remained paused at the same clock.

Standalone frozen-header validation separately verifies all 91 resource records,
91 code/package/preferred-name fields and 84 real WIC-decoded images. Its proof
`5b2a0ffb3d2e7c3f82c64c8b0f89db22bfb129668e4f86ff303b64b38d6d2ba9`
remains host decoding evidence. The later actual native captures separately
establish selected-image rendering, not coverage of every image or Studio action.

The new typed `studio inventory` host command automatically pages eight exact
rows at a time, then rechecks each selected owner and appearance. Actual Human
inventory contains 221 rows. Final all-existing-form inventory verifies 865 rows
across 61 outfits and six native owners, with no activation, appearance Apply or
Save. Every row resolves native CASP metadata; 740 rows match the pinned catalog
and 679 rows have resolved thumbnails. Forty-four distinct equipped parts are
outside that 91-record catalog. Spellcaster is absent; no missing owner or prior
bank is recreated. Exact final native fingerprints and outfit inventories pass
again after the full scan. Opaque preset/genetic data is retained separately;
the command invents no equipped CASP identity for it. The inventory proof is
`54ba16586b170fc4e2c7f9dfcb399119dd9ba587cdb1bdccc37045f923315b0f`.
Historical selected-image/Studio leaves below remain scoped to their original
epochs. All localized titles/images, color acceptance and T224 stay open.

AS v4's unseen-owner default requests zero occult auto-sync flags, preserving
explicit choices already held by that widget session. Runtime effect and
cross-session choice persistence remain unproved. This does not fix the bank's
entry-lane-only reconciliation: editing another layer in the same CAS visit can
still be rejected or restored away. It supplies no new F11 name/image, native
CAS resource mapping, color mutation or all-form persistence proof.

This candidate has two distinct read-only metadata paths. The optional native
CAS bulk catalog-metadata query is disabled pending proof of its getter contract:
the preceding enabled candidate crashed during CAS entry. The catalog-isolated
candidate passed primary Human entry and its native regression with all 72 raw
panel records, equipped parts, presets and history intact. A native image URI
remains a URI, rather than decoded pixels or a filesystem path. Native localized
name/thumbnail enrichment is not runtime-verified.

For Live and stored-form outfits, selecting an equipped row inspects that exact
part's effective game CASP bytes. The inspection includes the actual native
resource type, group and instance, resource SHA-256, body type, appearance hash,
form and outfit target. F11 accepts a pinned cache row only when those identities
agree. Cached inspections are cleared when the appearance or history lane
changes. The broker prepares three explicit name choices: `preferred_name`, `package_name`
and `code_name`. Preferred names use a verified nonempty localized STBL title,
then the exact original containing filename for mod CC, then a genuine CASP
internal code for EA resources. Package names preserve original case, Unicode
and extension; code names preserve `metadata.internal_name`. Missing values stay
null, and unresolved/ambiguous resources gain no filename guess.
`preferred_name_status` records the selected provenance, while existing
`display_name`/`name_status` alias the preferred choice. The preferred-name chooser is now rendered in actual Live F11. Runtime switching
through every preferred/package/code choice remains unproved. These fields do not replace exact CASP/hash or container identities.

Live and stored-form rows describe the last accepted owner status/inspection.
Use **Inspect / refresh** after changes outside this view. A stored-form
inspection must have a valid current owner; an uncertified prior-session bank
cannot supply a baseline. Native CAS uses its separate acknowledged working
snapshot and records that acknowledgement's age. These views are not
interchangeable, and a cached image proves the displayed inspected row rather
than continuous Live tracking.

The generic equipped-row reader covers the current runtime categories,
including skin details, jewelry, layered items and unknown future body types.
It does not synthesize an item for an empty category. Only individually
inspected items with a verified cache match have resolved images and Studio
actions. Other rows explicitly show why a name, image or package is unavailable.
Native CAS catalog IDs have no verified CASP mapping yet, so their Studio
actions remain disabled.

## Pinned local resource broker

`tools/cas_resource_catalog.py prepare` reads explicitly supplied source
packages and exact resource requests into the checkout's single private
`.work/cas-resource-cache`. The fixed localhost service starts with the generated
manifest and its exact SHA-256:

```powershell
python -B tools/cas_resource_catalog.py serve --manifest <manifest.json> --expected-manifest-sha256 <manifest-sha256>
```

F11's transport worker uses only `127.0.0.1:8022`, with typed catalog, thumbnail
and open operations. It never accepts arbitrary network URLs, commands or
paths. Complete response sizes, canonical identities and effective resource
hashes are checked before presentation. Networking and PNG decoding run on the
worker; the render thread uploads immutable owned RGBA pixels. An unavailable
broker yields an explicit unresolved state and leaves rendering asynchronous.

Thumbnail bytes must match the pinned PNG SHA-256 and dimensions, with an
8 MiB compressed limit and maximum 512 × 512 pixels. WIC decodes the real image;
the native UI shows no substitute thumbnail. The installed Studio catalog
thumbnail contract is distinct from its swatch thumbnail link, and the cache
retains that association evidence.

The Studio button submits only a resource ID and cache proof. The host verifies
the sealed cache, installed Studio executable and dependencies, then opens a
fresh independent package copy. The original game resources and source mods
are never passed to Studio for editing. This requests opening the containing package;
automatic selection of the individual CASP resource inside Studio is currently
unsupported. Where equal effective bytes appear in multiple EA archives,
provenance identifies a matching container rather than claiming an exclusive
loaded winner. Open requests are submitted once, with lost or rejected results
reported as unverified.

## Candidate evidence

The CAS build manifest pins the exact source bytes of
`Source/CASUi/semantic_methods.as`, `Source/CASUi/selector_methods.as`,
`tools/CasBytecodePatch.java` and `tools/CasSelectorBytecodePatch.java`. A package
is refused when an input changes during compilation or no longer agrees at
bundle time. The native build preserves 1,785 original method bodies, with
explicit serialized gates for catalog getter arguments and localization QName
linkage.

Focused checks cover exact identity mismatches, stale appearances, malformed
HTTP framing, PNG hash/dimension failures, actual WIC RGBA decoding, native GPU
texture upload/readback and renderer cleanup. These are source and host checks.
Actual Source inspection now resolves 221 equipped rows across 29 BodyTypes to
63 unique CASP internal names. The pinned broker contains 63 resolved resources,
62 real hash/dimension-verified PNG thumbnails and one unresolved image. This
proves resource resolution and extracted pixels, not their presentation in F11.

The old DLL's F11 capture showed an empty equipped list despite the complete
773,174-byte Source status response exceeding its former 512 KiB cap. The newer
installed DLL accepts bounded Source JSON up to 4 MiB and retains owned RPC
polling. Its real PID 44372 F11 capture now shows all 13 active Swimwear equipped
CASP names, 119 category choices and the selected Hair item's real 104 × 148 PNG.
Two metadata pages (8 + 5 rows) completed against that exact runtime. The selected
item retains exact TGI `034AEECB:00000000:0000000000065238`, BodyType 2 and effective
resource identity; its containing-package Studio button is enabled. This closes
active Live name and selected-image rendering only. Complete native CAS metadata, localized titles, all images and individual Studio
resource selection remain open. The later small real CC package-open proof below
closes only that containing-package leaf. The recorded
Studio handoff started the native Studio process using a fresh sealed package
copy, but `package_open_verified:false` and
`individual_resource_selected_verified:false` remain explicit. Automatic resource
selection is unsupported.

| Private proof in `.work` | SHA-256 | Observed scope |
| --- | --- | --- |
| `catalog-isolated-equipped-metadata-proof.json` | `548a0b293f85c41193eb6139040b268e450ab00c519cb6c73dc218ef3cf4babd` | 221 equipped rows; 29 BodyTypes; 63 CASP internal names |
| `catalog-isolated-resource-cache-proof.json` | `6053a67c479d620e0edaeb6ef185b41727ef111a27f8c75b198d8c2dd8197785` | 63 resources; 62 verified PNG thumbnails; one unresolved image |
| `catalog-isolated-f11-parts.json` | `abc75f43eff8aa5af5c48a03225131a5465b5aa2fd0a67958cca85507f2d0829` | Old DLL capture succeeded; equipped display remained empty |
| `cas-resource-studio-handoff-proof.json` | `c9056b1c4a62824b3eebf4d7e53fc336d8e4961b5ccc2b60d990ada0578f6f11` | Native Studio process startup; package opening and resource selection unverified |

The original catalog-isolated tested DLL is
`33dfd19ee4c48eb767eb5e1ff60385a2f45938d5b89ea825dba51aee765d913e`.
The completed PID 45012 runtime used replacement
`480b9a955f92ecff3e7519371936b6b9143fc32b9b7c15d5d2cd23836e2f92d5`.
Following PID 45012's verified normal no-save exit, the then-installed bundle
`0e37d5f8f744ffd464ceffaece2f9a77762985fd9dab278b6e8b6c034791ce24`
contains DLL `9e87e10c715e696a1b2f75f4c3314011825da14e5f31483e081ca55585b72562`;
it is installed in profile generation 34. Fresh CLI EA permission acknowledgement
and exact game PID 44372 process start passed. A separate read-only CLI check
verified the expected Slot02 household already loaded and paused, without Resume
input; the native F11 capture supplies the narrow rendering proof above.
All 767 Python tests, 179 native transport/data checks, 29 resource checks and
three WARP targets pass. These host checks and the narrow active Live capture do
not close T224's all-category/name/image or Studio acceptance.

The same Source candidate passed seven-form read-only reload verification only
after explicit reconciliation of its certified seal recreated the missing native
Spellcaster owner. This proves sealed-assisted recovery in PID 45012; it does
not establish automatic native seven-form reload, all item presentation or Studio
package opening. The exact persistence proofs remain in the runtime ledger.

The earlier 9e87 native rendering proof is
`.work/owner-completion-9e87-f11-proof.json`, SHA-256
`58978d401637a858d676199fce0b1983fa5f83258736e51b4afa80fb044e2aee`.
Its reviewed `.work/owner-completion-9e87-f11-parts.bmp` capture has SHA-256
`3b24fd6b2875382a6ddc69bb6d60a9180dbdc1587cd4c98865c940342134b610`.
The original empty-display capture remains retained as the prior-DLL failure.

A separate read-only actual-CC naming probe resolves all 28 CASPs from three small
packages, preserving original filenames as preferred names and genuine codes as
independent fields. It verifies 22 real PNG thumbnails. Its proof is
`.work/cas-resource-cache/cc-name-probe.json`, SHA-256
`13d24c4dbf9c48eeb14eeb09e0a221dbcb4cffb87aa603c1e6be33d35c3f1bd4`.
These sealed copies and their separate static manifest remain in the existing
cache; that static probe left the active pinned broker unchanged. Later closed-
game CC installation and native chooser/wheel rendering are recorded below;
actual CC equip/copy/color acceptance and all name-mode transitions remain open.

The current native F11 Studio button's first input was explicitly refused before
submission. A separate focused retry reports accepted native input with a verified
pointer. Root reported historical Studio process startup with broker parent and
the exact fresh sealed copy in its command line; that process has exited and no
saved process-observation artifact binds the report. The copy-observation proof retains
`copy_verified:false` because it includes both the prior and fresh copies; both
1,878,086,355-byte files match expected package SHA-256
`f02a7b60ccf0bf3051ac7810d79e7ed57c4cf3da5db27d18a41f12a32ea804ff`.
`package_open_verified:false` and `resource_selected_verified:false` remain the
reported GUI acceptance state. Input/handoff and matching bytes are narrower
proof than a loaded Studio package/resource.

A new observation independently hashes the exact fresh `ecf981…` copy rather
than requiring only one historical copy. Proof
`.work/owner-completion-9e87-f11-studio-exact-copy-proof.json`, SHA-256
`1527d8ea2859c9001b3a8bb67d5a2c5afaeebff4f28d7a493bbfb53141df3b60`, reports
`hash_verified:true`, exact length and unchanged file signature. It explicitly
keeps causal launch, live process and GUI package/resource verification false;
the historical root-reported process association is `artifact_bound:false`.

## October 8 — generation 36 Live rendering and real CC package opening

PID 27852 uses CAS package `9776d402…`, DLL `cd644541…` and unchanged A0 script.
The reviewed saved-parts capture renders 13 equipped/119 category choices,
preferred-name chooser, exact selected Hair CASP name and the real cached PNG.
The item retains TGI `034AEECB:00000000:0000000000065238`, BodyType 2 and its
containing-package action. This proves the displayed inspected item; all name-
mode transitions, every item image/localized title and native CAS enrichment
remain open. The merged static broker manifest contains 91 records (63 EA +
28 actual CC), not 91 runtime-equipped items.

A separate actual wheel capture follows slider inspection and renders the HSB
wheel, but its resource names and thumbnail are unavailable at that moment.
At this gen36 capture the later native metadata-retention/Source context
correction was not installed. Gen37 later installed the new DLL/AS selector,
but no post-fix wheel/name-retention capture is yet certified here. Wheel rendering verifies no color
mutation, preview/Apply/Undo or save/reload persistence.

The host launched Studio PID 13208 with a fresh 25,851-byte freckles package copy.
Independent read-only UIA matched that exact PID/window and copied path, observed
two real swatches and Texture/Warehouse tabs, and rehashed the unchanged copy to
`b2bfff7768c1e0f0b431b5256bf0cd150d2689a7636b0ae55929850898c52f8b`.
`package_open_verified:true` closes this small actual CC containing-package GUI
leaf. `resource_selected_verified:false` remains explicit; selection of the
specific CASP is unsupported. Original CC was never passed to Studio for editing.
The earlier large-package handoff and copy-only proofs retain their failed or
unverified GUI flags.

| Private proof in `.work` | SHA-256 | Verified scope |
| --- | --- | --- |
| `owner-qol-f11-saved-capture-proof.json` | `66f8b57df4b66d5a0065cc73959e347cf5dd327a275a4f37559e679e31020478` | Actual gen36 F11 backbuffer captured |
| `owner-qol-f11-parts-saved.bmp` | `bdc95b8ce6d96efdd9370bead13487b2fc17ac3ed2c06ba5534576f551ca2384` | Reviewed equipped list/chooser, selected exact Hair name and real PNG |
| `owner-qol-f11-wheel-capture-proof.json` | `57f5eb4f0f3d6bbd59917638ac980cb8b91d450bf5ad3fb4956f3052920ba041` | Actual wheel capture; no mutation acceptance |
| `owner-qol-f11-color-wheel.bmp` | `85149efa8339aad6938c0c69d539c08c20b4c3c74074a01d6628c196a634b360` | Wheel visibly rendered; names/image unresolved in this view |
| `owner-qol-small-cc-studio-proof.json` | `cbe5fdaaac27f10b136e90add256b9ae108eec08e79fbabf3bd876dd563bc7fd` | Exact fresh copy/process/parent; initial GUI-open flag false |
| `owner-qol-small-cc-studio-uia-proof.json` | `b66121aead3f31bc2d2aefe387f2ebdc68b1e36dea93c8b5d5657361290586b3` | Independent read-only actual Studio window/path/tabs/swatches |
| `owner-qol-small-cc-studio-open-verified-proof.json` | `74e988a73381208c1c0c43d8ebd470993020834d511ecd0e7a2a226ffe280783` | Small actual CC GUI package open and unchanged copy; specific CASP unproved |

Generation 37 later installed CAS bridge `1106b4df…` and DLL `1556eb4c…` with A0
unchanged after normal no-save exit preserved the new seal/save backups. The
new selector raw-entry feed is actually delivered and complete in PID 20644's
Fairy CAS inventory. Human/Fairy layers share the same original Sim ID; the
fresh retained view shows Fairy selected. Owner mapping/alternate acceptance
remain false, so this supplies no verified native-CAS CASP mapping, color edit
or alternate return proof. Source ownership/metadata changes were uninstalled
in that gen37 runtime; generation 40 installation does not certify their Live behavior.

That gen37 alternate CAS session later crashed after the native Cancel popup
opened, before confirmation input. The saved crash proof reports native category
`0x14112c645`, unchanged save/backup bytes and causality_verified:false. The
successful entry/raw-feed observation remains separate from that failed exit;
no alternate acceptance, return or persistence is proven.
