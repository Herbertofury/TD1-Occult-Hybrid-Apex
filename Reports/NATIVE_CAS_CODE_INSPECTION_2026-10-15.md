# Native CAS service inspection, October 15

The mod must provide all owned occult forms in ordinary/full/MCCC CAS and
support additive membership without merging their appearances. Existing
native presentation limits remain implementation work. The permanent guard
and native copy prevention stay enabled together.

## Current native UI and engine work

V147 places the movable form strip in the CAS package itself, using native
CAS fonts and game occult icons. The CLI verifies movement, 110% scale,
locking, collapse and expansion without an appearance write. Its same-pair
navigation delegates to EA's complete `SelectSimLayer` handler, including
thumbnail cleanup, native selection, retained UI selection and copy/link
panel updates. All other native selector bodies remain byte-for-byte intact.

Actual typed navigation verifies Alien layer 0 → Human disguise layer 1 →
Alien layer 0. After native acceptance, actual simulation ticks and all five
member commits, all 40 appearance owners match the canonical baseline:
`ff74138724a7fe3ca8ff928648901e2a6f6e54f93243ea0fc942ef06a7ba3ac7`.
Normal unsaved exit verifies all 20 save/backup entries unchanged.

Two earlier window-addressed input attempts were followed by native crashes.
The later control comparison exposes stale CAS hit-testing, so those ACKs
cannot establish which control was clicked. They remain failures of unknown
precise cause; the successful typed pair navigation does not qualify mouse
buttons, kind conversion or production saves.

V148 follows the actual kind setter's second native interface: its preflight,
selection, pair-construction and UI-rebinding methods. The fixed reader
checks the pinned executable and exact read-only vtables, bounds every
snapshot and calls none of these interfaces. This work targets the direct
native owner/constructor fix. Cross-kind conversion remains quarantined
until its ownership and lifetime behavior is understood and tested.

V149 additionally inspects the native cache's Sim IDs and stored kind keys.
Two bounded reads must agree, and cyclic/shared nodes, duplicate IDs/kinds,
unaligned pointers, exhausted bounds and key/record mismatches are refused.
This operation explicitly declares `sim_data_read=true`; it reads no appearance
payload. The real main-menu probe returns an empty cache. Inspection inside
the existing household's CAS is the next step. The helper callsites and the
native protocol-response references are captured separately so construction,
cache lookup and initial population can be distinguished before patching.

## Confirmed runtime boundary

V135 prepares every member of the five-hybrid household with all six
non-Human bits (`126`). The native selector packet nevertheless describes one
Human/occult pair per member. This packet observation alone does **not** prove
that persistent membership has been deleted; the editor-view model and stored
membership must be distinguished before selecting a native intervention.
The strict old native-view probe refuses before any setter against that mask.

After normal unedited CAS acceptance, actual simulation ticks and all five
independent restoration commits, all 40 appearance owners still match exactly.
V135's final normal unsaved exit verifies unchanged complete save/backup files.
The protected original profile remains read/copy only.

## Read-only inspection implemented and exercised

- [x] Add a fixed, no-argument native diagnostic in the authorized mod. It
  verifies the actual executable's SHA-256, PE layout and loaded-image identity.
  It reads only its own pinned code and read-only constant sections.
- [x] Expose a disposable-token-gated CLI path that works before any household
  loads. It accepts no caller-supplied memory addresses or operations, performs
  no Sim/service inspection and deduplicates the exact request UUID.
- [x] Exercise V136 in the real main-menu process. The reader inspects
  31,337,372 code bytes and finds actual service-registration references for
  `SetSimOccult` and `CasGetAvailableOccults`. Loaded code differs from the
  on-disk code, explaining the earlier unsuccessful static reference search.
- [x] Retain the private runtime receipt, SHA-256
  `6c79020677c42afd016944ea712b82154e0ac9a113f64ce4a496d9eebeb0ed11`.
  It reports no game-memory writes, game-file writes or full memory-dump file.
  Proprietary code snippets remain in ignored private research receipts.
- [x] Derive the registered callbacks from the observed Win64 argument pattern.
  Pinned exception/unwind metadata identifies their real function boundaries;
  encrypted on-disk bodies cannot establish runtime behavior.
- [x] Exit V136 normally from the unloaded main menu through background native
  input. All 20 top-level disposable save and backup entries are unchanged.
  A first comparison accidentally used the prior filtered normal-save roster;
  it remains retained as a failed comparison. The subsequent complete-roster
  comparison passes without modifying or deleting either proof.
- [x] Add automatic exact-sidecar initialization to the diagnostic CLI, using
  the existing idempotent loader and recorded request IDs. An unacknowledged
  startup stops before inspection. Transport errors retain their original IDs.

```powershell
python tools/apex_cli.py game native-cas-probe --state .work/reusable-profile-session.json --output .work/new-native-code-proof.json
```

This command requires the marked disposable profile and a running game. It
does not require a loaded household, a camera position or foreground focus.

## Bounded callback snapshots

V137 adds fixed inspection of the actual selection, creation, removal and
synchronization services. It derives callbacks only from the observed
registration pattern and validates their boundaries against the exact pinned
unwind table. Up to 32 functions, two direct-branch levels and 65,536 code bytes
can be returned. Branches are explicitly candidates until independent decoding
establishes instruction boundaries; no native patch is marked qualified.

The matching immutable V137 candidate has 93 Python 3.7 modules, seven packages
and 207 independently Rust-verified resource payloads. Bundle SHA-256:
`d3cc7c1c9b1ac49d5220b88f43b58d740d2640c389eaef4460986b2e77a604a2`.
All seven native CTests pass, including forward/backward references, truncated
instructions, out-of-image bounds, bounded pointers and exact registration
pattern rejection. Source/control/CLI tests cover unloaded or replaced DLLs,
wrong process identity, missing fingerprints, write claims, incorrect tokens,
arbitrary-address rejection, initialization failure and response loss.

- [x] Run the single-command V137 reader in the actual main-menu process. It
  initializes the exact sidecar automatically, finds seven service references
  and returns 17 bounded unwind-region snapshots totaling 3,587 code bytes.
  Receipt SHA-256:
  `af63333faeec074b098ce795eb4452377662267195ee85eaa8b3d943aefec44c`.
- [x] Decode the actual selector's argument handling: `CasSelectOccultForm`
  reads an optional Boolean `select` and invokes a primary/alternate interface
  method. It is not an occult-kind selection API. No unsupported numeric
  occult argument is sent to it.
- [x] Identify split native handlers. Unwind-region boundaries need not enclose
  a complete semantic function: native branches and switch targets can leave
  the captured region. V138 labels that distinction explicitly and adds bounded
  callback contexts under the same total code-byte limit.
- [x] Runtime-qualify V138's additional contexts with the single CLI command:
  six contexts and 17 unwind regions, 28,163 captured code bytes. Receipt
  SHA-256 `5383d70e329e3dd1d9ffe5049118360915bb24ea82c84fff9b898e27a51b6965`.
  No household is loaded. Independent decoding checks the captured hashes.
- [x] Decode the kind setter's dispatch. `SetSimOccult` accepts a numeric kind
  in the native `1..64` dispatch range, derives the current dominant kind and
  invokes the controller's kind-setting method when they differ. It is not an
  additive membership-bitmask API. This observation does not qualify calling
  it as a lossless hybrid appearance switch.
- [ ] Trace the controller's conversion/creation behavior and retained form
  storage before invoking a cross-kind edit or changing native behavior.
- [ ] Qualify every owned occult inside one native CAS visit, with distinct
  edits retained through Live, MCCC, save/reload and Tray/Library import.
- [ ] Complete additive CAS membership and special-life-state gameplay.

There is no background scanning or per-frame diagnostic work. The reader does
not implement a native CAS fix or establish production-save readiness.

The V135 hosted run passes 2,137 offline tests, then correctly fails its stale
canonical source inventory. The inventory must be regenerated from the final
staged sources; no integrity check is disabled or weakened.

## Controller conversion and native cache

V139 reads only the fixed controller pointer reached independently by the
two inspected callbacks. Four bounded pointer reads verify the same controller
and read-only vtable before returning method code. No interface is invoked.
The runtime receipt is
`f182afa0c7a1010a6c049bfdb6f109f4d2ae0b5fcdb2b11b119cebb17f952e71`.
Kind conversion and primary/alternate selection are separate methods.

V140 follows decoded instruction boundaries with the already-bundled HDE64,
including conditional paths across split unwind regions. Immediate bytes and
unreachable instructions after a return do not become fabricated calls.
The actual main-menu receipt captures 52,950 code bytes under the existing
64 KiB limit, SHA-256
`8ed87f34844bf8e4a752b08ef5477dd0e38f5e7194e49c440f509a0de3424720`.
Its conversion helper saves the old pair into a keyed cache using a tree
lookup/insertion and record assignment. That helper is **not a deletion
routine**. This does not yet establish that conversion, subsequent edits or
serialization retain every cached appearance or occult membership.

V139 and V140 exit normally from the unloaded main menu, using one recorded
background confirmation each. Both confirm-input acknowledgements are lost
when the game exits; the requests remain retained and are not repeated.
Independent process disappearance and complete save inventories confirm all
20 save/backup files are unchanged.

V141 adds a separate disposable-only `occult-cache-view` qualification path.
It requires the exact profile token, a pre-entry actual-membership capture,
existing target appearance owner, fresh paired observation and exact
household/session/layer. It deliberately distinguishes native pair projection
from persistent membership. Its selection ACK cannot certify cache retention,
appearance persistence or production safety. Ordinary `occult-view` retains
its stricter existing contract. The deletion warning is not suppressed.

- [x] Compile the updated retained-bytecode CAS package without loosening its
  native service inventory or original-body preservation checks.
- [ ] Exercise actual Alien → Vampire → Alien with distinct alternate edits,
  inspect raw returned owners before restoration, and verify all 40 owners.
- [ ] Add the actual native CAS all-owned portrait/icon selector and additive
  membership controls after the navigation path is qualified.
- [ ] Prove ordinary/phone/MCCC CAS, save/cold reload and single-Sim/household
  Tray/Gallery transfers before removing the corresponding deletion warning.

V141 cold-load qualification compares all 40 native owners exactly with the
retained baseline, receipt
`b88baeb5b52964af4d451f7d7c43f52a3f9c5b004b8100522e8056868fa7bbde`.
The first entry then correctly refuses before its native CAS command because
all five records retain never-observed checkpoints from the now-closed V138
process. It does not bypass or overwrite that gate.

The new `cas-frontdoor-archive` recovery accepts the actual Source-authored
entry receipt and a later read-only cold comparison. Every old raw stored and
active owner must match exactly. Both observed processes and every game
process must be closed, the normal save hash must match, and all captured
transactions must remain in their never-observed state. It validates the
complete household before changing metadata, retains a flushed full bank
backup and all raw originals in history, then uses the existing cooperative
atomic bank writer. It performs no Sim restoration or save and makes no CAS
return or save/reload acceptance claim. Four recovery tests cover altered
scope, mismatched owners/checkpoints/runtime, begun observation/writes and the
complete atomic backup/archive round trip.

Actual recovery passes for all five V138 records. The complete bank's stored
appearances and all save/backup files remain unchanged. New bank hash:
`65f034a4063e1bb7df9029a72b1fa9e191ffcc08d6b709a36c77727e232ade9a`.

## V141 actual conversion failure and V142 quarantine

The recovered V141 cold load again matches all 40 owners exactly, receipt
`8aec9e4c64e0bc7139f4bccdf2a052c52dc2e1715f2f4735808703ec001b3a34`.
Full existing-household CAS entry passes, receipt
`9a1176e2aad1f81903958cb21b647d7dbe3e92c6cedef796b18695ae3033fed8`.
The actual Alien is type 2 on layer 0. One recorded cache view request selects
Vampire type 4 on layer 0, projected mask 4. This is selection only. Its new
alternate row is the native zero-ID placeholder, not an existing dark form.
The proposed return to Alien is refused before submission by the pair-binding
validator; that refused request is not retried.

The process then disappears and produces a new native crash at game RVA
`0x105a1de`, with caller `0x3f7ad2` in the retained stack. The diagnostic preserves
the original crash, SHA-pinned proof
`9209f963f73831144f1b4e02c1279273b820a1734e184a2708a8fe421051e7b8`.
Temporal sequence is observed; the precise native cause is not established.
There is no return, alternate edit, cache-retention or release-safety pass.

V142 refuses this experimental operation in the host CLI and Source receiver,
before guards, RPC or native submission. Tests retain the offline typed-contract
coverage under an explicit fixture override and separately verify the real
quarantine. No user-facing selector is wired to the unqualified conversion.
The permanent guard stays enabled and the deletion warning is not hidden.

The older CLI entry result omitted its native frontdoor ID. Closed crash
archival now accepts a separate SHA-pinned actual Source frontdoor receipt
only when its runtime, household and every captured checkpoint match the
preserved crash entry exactly. Two tests cover that compatibility path and
refuse altered runtime, missing members and changed checkpoint hashes.
Actual archival preserves all five raw checkpoints and bank appearances,
with final bank SHA-256
`761e99b37adb2b9695a506d8f2c83a427a74bd10226758b42a8b95f6688ea57f`.
An independent comparison against the last normal-exit complete roster confirms
all 20 save/backup files are byte-for-byte unchanged after the crash.

V142 adds fixed bounded diagnostic windows for the retained CAS crash sites.
These windows are not function-entry assertions, patch targets or native calls.
Actual root-cause analysis and a verified native fix remain required.

The V142 reader is exercised in a fresh unloaded main-menu process. It returns
56,022 bounded code bytes, receipt
`8124106eee2cdf81f51f98bd3b0cffb04d7eaa2f6268f06da7322866fb336a02`.
Pinned unwind-chain metadata and independent decoding identify the newest
fault at a source-buffer read in a counted four-byte-element copy. Its retained
controller frame dispatches the actual `CASSetSimInfo` UI message. This narrows
the investigation to native UI data/lifetime handling; the offending field
and exact ownership error remain unidentified. No null-check patch, skipped
copy, allocator patch or deletion-warning suppression is substituted for a
real ownership fix.

The V142 immutable bundle has 93 Python 3.7 modules, seven packages and 207
independently Rust-verified resources. Bundle SHA-256:
`1190feb28bb1de058dcb092efbecd98a1ae1fcb97466ede3600201d0018e6be3`.
All seven native CTests, 26 frozen-source migration checks, 22 CLI intent
checks, 16 crash-archival checks and four interrupted-entry archival checks
pass. The updated cache/quarantine contract suite has 18 passing checks.
These component passes do not qualify the failed gameplay path.
