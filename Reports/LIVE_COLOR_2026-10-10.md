# Focus-free CC color and Alien retention checkpoint

Target PC game 1.128.90.1030. The one disposable profile is
`C:/Users/Owner/Documents/Electronic Arts/The Sims 4`; the owner's original
`The Sims 4 DO NOT FUCKING TOUCH!!!` remains read/copy only.

## Actual generation 72, V35

The owner loaded Sim `285159751289798669`, household `285159751289798668`,
save GUID `1841692672` in process 5712. The authenticated bridge matched script
`e32a661e219bfde71e61f51d69276088617f7dd5bc0db9021fe1272152e7712b`.
No launch, restart, force termination or input/focus operation was used for
this CAS/color sequence. Source records and native CAS acknowledgements are
retained separately; a native catalog identity is never guessed from a TGI.

Full existing-household CAS equipped these two read-only copied CC packages
on the actual Alien creature owner:

| Item | Package SHA-256 | Actual equipped CASP |
| --- | --- | --- |
| Magic Hand Lipstick N91 | `4e5d1113e2bdcafb330776fc40e15315aa1a3e759d27cb7d1779110a7d2570be` | `034AEECB:80000000:ABE28708F9230CF7` |
| Simbience Hello Sunshine Swirl Blush | `eeee18ae983e0f8f7cf71e1a44ca5c34e8b54c76a197578424cd0d8ba5f33c6f` | `034AEECB:80000000:A0565D4F175321C7` |

Only Alien lane 2 changed on return. Original-Sim Live return, native clock
progression and final Pause passed. Explicit Alien-only acceptance then
verified all seven stored owners and the distinct Live appearance. Alien →
Vampire → Alien passed after 1,677 / 1,505 actual simulation ticks, with all
stored appearances and occult memberships unchanged.

| Immutable private receipt | SHA-256 |
| --- | --- |
| Native return; overall explicit-decision-required outcome | `0026b42553aae57e58fbffab2ac03ba6e1bfe3328bc0022769aec9432625f556` |
| Explicit Alien-only commit | `15b292a470060c41aabfe36b9313212fb23128c7be3620f062b280c4b537f7f1` |
| Alien → Vampire after ticks | `9cb0d706d50e25983c0310c16c8ba7ef66a1f51132540550e5eaec57f0be12af` |
| Vampire → Alien after ticks | `16964167329ce7c2d439953f4490d333c76228e14d0ab9859a480e83bd5c7556` |
| Actual F11 DX11 frame capture | `3dc7dc6a7d4d4037f955ec3c0f84e80db7b6ac7956c0c88ea39e99daa618d6d3` |

The F11 capture's host foreground stayed HWND 854236 before/after, with no
foreground fallback. The capture shows the equipped-items interface rendering;
it does not prove a wheel gesture or visible changed makeup. Initial colors
were neutral `4000000000000000` on Swimwear outfit 1, exact Studio targets
`9:29:9` and `9:32:10`.

The first live-color regression stopped **before any color write**. Its exact
inspection UUID `a3f5ab5c70c645069bcba5a85c33adc6` failed with
“The effective CAS part resource could not be read.” The failed request was not
replayed. This is a reproducible CC-resource lookup defect, not a color pass.
Historical native load/genetics diagnostics also remain retained; passing the
current explicit form transaction does not erase earlier failure diagnostics.

## Corrected V36 build

`get_resource_key(integer, CASPART)` constructs a key rather than finding its
actual group. Passive inspection of the installed Core bytecode confirms that
constructor path and `get_all_resources_of_type` using `resources.list(type=...)`.
V36 resolves the unique native indexed TGI, preserving its group. The index is
bounded/cached per resource-manager module; actual resource bytes and their
hash are read fresh. Missing/conflicting groups fail before loading or writing.
Resource resolution, cache separation and changed-byte tests pass.

Bundle `Apex_Development_Candidate_2026-10-10-cc-resource-groups-v36.zip` has
SHA-256 `789c3f1624e94e0f4988b0c99db491dc4d0da5c0a49c3b8d2ccdb34bec3c6093`;
script `feda3a7ec16bcf7a17a92a646ccfb6f301155c89562706ccbaae8de2c7a89c0d`.
The exact candidate passes portable compiled Python 3.7 Main import, production
native-loader host refusal and independent Rust verification of 206 package
resources. These build checks are separate from real-game color proof.

`studio color-live` applies an exact hash-bound part edit in one owner-thread
transaction, preserving journal Undo/Redo and rolling back failed native-bank
readback. F11 defaults to applying one gesture when released. It never sends
input, changes clock speed or activates an inactive form. An accepted numeric
edit explicitly reports `rendered_result_verified=false`.

The public `test live-color` regression verifies Q14 readback after actual
simulation ticks, every other native appearance owner, all untouched native
fields and unknown outfit bytes, stale-state refusal, Undo/Redo and final
original-state restoration. It sends no game input, starts no game and saves
nothing. Separate visible rendering proof remains mandatory.

## Actual generation 73, V36: active colors and occult retention

The owner reopened the same saved household and provided a close camera view.
Process 26404 matches the V36 script above. A fresh zero-change current-native
checkpoint accepts all seven owners; it does not replay a prior-PID bank or
claim automatic certified reload. The two full-CAS CC edits saved by the owner
are present on the actual Alien appearance. Corrected lipstick inspection
resolves group `80000000` and its exact resource bytes in 0.712 seconds.

The first V36 numerical suite recorded a failed assertion, retained under
its original UUIDs. It incorrectly expected the distinct native stored Alien
wrapper to change during an active Live edit. Exact snapshots show that only
Live and the accepted independent bank change; the stored wrapper remains
unchanged until normal form switching. The harness now checks both owners
independently, with regression coverage for wrong-owner, missing-edit and
untargeted-owner changes. The failure was not relabeled as successful.

The corrected public lipstick suite passes all four channels, native-tick
settling, exact untouched fields/unknown outfit bytes and other owners,
stale-state refusal, Undo/Redo and exact final original-state restoration.
The separate visible cycle applies lipstick then blush, unpauses each, switches
Alien → Vampire → Alien, and verifies all seven stored appearances plus the
distinct Live appearance. The other six forms remain exact; the accepted
Alien-only colors survive both switches. Two explicit Undo operations and a
normal away/back synchronization restore every original appearance exactly.
The same Sim, household, GUID and game process remain present. No input,
focus handoff, launch, close or Save command runs during this sequence.

| Exact changed color | Four-channel packed Q14 |
| --- | --- |
| Lipstick: H .35 / S -.15 / B .25 / opacity .25 | `10001666F6661000` |
| Blush: H -.35 / S .15 / B .4 / opacity .3 | `1333E99A099A199A` |

Actual tick counts for the visible sequence are 512, 536, 556, 587, 600, 814,
688 and 646. All captures leave their current foreground unchanged without
a fallback. The owner changes foreground applications between operations;
the overall beginning/ending HWNDs differ. That is recorded and is not
presented as proof of a globally unchanged desktop.

The captured close-ups were visually inspected: the lipstick changes from
red to a subdued green/gray; the blush's white spirals become faint blue/gray.
The returned Alien retains both changes. The final frame shows the original
red lipstick and white spirals again. Pose differences caused by unpaused
animation are retained. Numerical receipts still report
`rendered_result_verified=false`; visible assessment comes from these separate
actual DX11 frames rather than an invented machine rendering assertion.

| Immutable private receipt / actual BMP | SHA-256 |
| --- | --- |
| Fresh native all-owner acceptance | `1874156445ea4c0784353212f5abf94a907cb0704ee60aff8ea4dde0df560c8f` |
| Corrected effective CC inspection | `d05e8ab6ba18ae31949bd5b3f5b936d3a1a49c253a0524522255fb7864ec1dba` |
| First V36 failed harness assumption | `a683b0b918a922b3241815fc194fb5da905e673146b890e46f4192372c4e075f` |
| Passing public lipstick regression | `c172f8df27d4c865c78244d0ab77c43907d1f8988a2c39c2ccc32c1ce2d4617e` |
| Visible color / away-back / exact Undo cycle | `936ba99edde3baeaf65340acc4bbcae8b161511149a4197e5e48392ed3d394eb` |
| Before colors | `74bf3b7c2b701f9ed8c0d6d8fceb667590d72c96c4d4503c7cb45ee757ba56d2` |
| Lipstick changed | `e4ff3f2c7b160afa348a848ae436550794222d6b21056a9c1c2b80ef4c4af7a9` |
| Both changed | `e65feb2ca8c8b9a258548e24a28cfc80f861ed2e5be0c5d2a016877d7c506291` |
| Returned Alien | `a852cb886022f6ab8c21b064d59a3233ed4981ec0f1d82bb63be57c7f92d0120` |
| Original colors restored | `a99c42b570196904398ca7fe0e71eaa1aae43bebe62c1d3ce78b178cbbc3d372` |

The public inactive-owner blush regression also passes: active Vampire remains
selected while the exact Alien stored owner changes. After 354 actual ticks,
all four Q14 channels read back exactly, every other appearance/unknown outfit
field and all six other stored forms remain exact, and the distinct Vampire
Live appearance is untouched. Stale-state refusal, Undo/Redo and final exact
original-state restoration pass. Receipt SHA-256:
`ad16f592bfe26379bec00208806a813e2d10393c8fc5ad88c265d35ebb65d1bc`.

Final unchanged-source local verification passes 1,603 Python tests and four
native CTest targets. Receipt SHA-256:
`baabb9130a02d31286c51592e2635350e7551dd0fd0a1ad6deb9929ab4264e98`.
The matching V36 compiled imports and independent resource inspection remain
separate build receipts. No source/native module changes occur during runtime
testing; the corrected owner distinction changes only the host harness/tests.

## Actual F11 wheel and opacity gesture acceptance

Two distinct window-addressed releases exercise the real F11 controls, without
an explicit CLI color-edit request. The wheel sets hue to exactly -.25
(`4000F00000000000`); the opacity slider retains that hue and sets its packed
opacity to `1913` (`1913F00000000000`, approximately .391785). After 431 actual
simulation ticks, exact native readback verifies the selected color, every
untargeted field/unknown outfit byte and all other appearance owners. Two
separate Undo/Apply operations, followed by 472 and 434 ticks, restore every
original stored owner and the distinct Live appearance exactly. Process 26404,
the Sim, household, save GUID and active Alien form remain unchanged. The game
is left paused and F11 is hidden. No Save, launch or shutdown runs.

The first gesture sequence remains failed: refreshing the panel moved the
opacity slider, so a stale coordinate did not change opacity. A new measured
release succeeded. Its immediate read-only inspection was cancelled before
execution when the owner queue exceeded its admission lifetime. Neither
gesture was blindly replayed. A later new read-only observation verifies the
completed write, then the explicit history restoration. These earlier failed
receipts remain failed; the final receipt links both.

| Immutable private receipt / actual BMP | SHA-256 |
| --- | --- |
| Final widget readback, ticks and exact two-Undo restoration | `c7079699fc70ba7000bf079db747b054a138ca23a7d06c155086651322fd4860` |
| Actual F11 widget changes after ticks | `1edd1d01da6d6361d9ed4cd456fdc5bcb8473cc6f522e5be3635224d9e60eb9c` |
| Measured opacity input receipt | `8a254359287933875cdc2f6f521968877d4c8d808d93cd965e59e342662c28e4` |
| Opacity operation: foreground/cursor observation | `dc21d843ac246ced04fa35df45515c92a91f199a1073be0e54abb3c3d95cf5b2` |
| Final restored Live frame with F11 hidden | `ae3229cf8eb7c4e93f552ec967e7ca8bd4e39adccb304222aa3cace94d71ec35` |

The final close-up was inspected and shows the original red lipstick and white
blush spirals. A native Sim pie menu is also visible; unchanged appearance
proof does not certify the absence of unrelated UI effects from a pointer
gesture. Numeric receipts remain distinct from visible rendering assessment.

## Live CAS catalog foundation

The new public host `live-cas-catalog` indexes all CASPs in explicitly provided
packages, including parts never equipped on the test Sim. It uses a bounded
single content-verified metadata pass per package and an immutable SQLite FTS5
snapshot, with category/origin filters, name modes and stable pagination.
Duplicate containers/groups and unclassified future metadata remain visible;
selection rechecks package and resource hashes before returning provenance.
It does not infer effective load order, compatible equipment or successful
game mutation from a historical catalog row.

The final atomic-publication code indexes all 62 CASPs in the five unchanged
private disposable CC copies in .049 seconds. Queries take .002302, .002553
and .002021 seconds; 30 Magic Hand lipstick and four Simbience blush variants
are found, and exact selected provenance resolves. No game command or focus
handoff runs, and the same process stays present. This small sample is not a
CC-heavy performance benchmark. Receipt SHA-256:
`868619976ebcc2473f433b8ee8c770a683eaa86a9646ffc6e54bc8accadaf907`.

The requested full Live CAS columns and independent rotatable/poseable preview
are added to T225/T226/T227. The host index is implemented; F11 browser
integration, complete item compatibility/equip and the actual 3D renderer are
unfinished. Every-category/manual/MCCC workflows and disk persistence also
remain open. The owner closed the disposable session normally for the V36
cached-script fix; the agent did not initiate another launch/shutdown loop.

After the catalog changes, final unchanged-source verification passes all
1,609 Python tests and four native CTest targets. Receipt SHA-256:
`061fc4900094adb904814c11b9ff65a80a0fcd49099e0f456e092dff1072a121`.
The exact V36 game modules/artifacts remain unchanged; host catalog additions
require no game reload. This supersedes the earlier 1,603-test host inventory
for current repository validation without changing that immutable receipt.
