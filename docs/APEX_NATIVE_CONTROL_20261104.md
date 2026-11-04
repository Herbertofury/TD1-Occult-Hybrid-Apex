# Native control and CLI continuation, November 4, 2026

Hitching remains unresolved. A fresh no-Apex profile reached native CAS, but
collector qualification failed. There is no valid measured baseline, paired
comparison, FPS improvement, Maru parity or actual-game hybrid regression pass.
No feature component was reintroduced after the failed control qualification.

## Actual Modernize conversation and CLI method

The supported local task API reached thread
`01a11397-45c1-7662-94ef-75f96f18d660`, **Modernize Sims 4 mod toolkit**,
`hostId: local`. In response to the owner's explicit request, a read-only CLI
handoff completed in turn `01a1a579-9d29-78f1-aa42-825575508f83`. A later
read-only collector handoff completed in turn
`01a1a594-30fa-7f30-9b3d-95b045f77b67`. These were conversations with the actual
native thread, not inferred guidance from the Foundry folder. Neither request
authorized Modernize to change the running game, install files or resume tests.

Modernize's earlier focus-free game commands depended on the installed Apex
script/DLL bridge. That bridge cannot be installed in a genuine no-Apex control.
Its independent FFmpeg Windows Graphics Capture recorder and guarded external
window-message prototype were therefore carried unchanged into this checkout's
ignored `.work`. The external input prototype was model-tested, but had not
previously been qualified against a no-Apex game.

The owner then explicitly requested CLI operation. After that instruction no
Computer Use input was used. Normal Windows approval started a ten-minute
fixed-process helper at the same integrity level as the game (12288); the
ordinary sender was 8192. This did not alter UAC, application compatibility,
registry security or injection settings. The helper accepted only immutable,
token-bound snapshot, inspection, click and stop requests. It pinned the game
PID, creation time, executable hash, Canvas, HWND, UI thread, geometry, DPI,
source files and disposable journal. Each click additionally required actual
live encoded FFmpeg progress and a fresh reviewed image of the unchanged target
control. Unrelated avatar animation was excluded from the target pixel check;
the exact process/window guards remained in force.

Observed native transitions: dismiss two promotional panels, New Game, decline
the Story flow, reach a new ordinary human in CAS, open the native menu and exit
without saving. Each submitted point retained separate input receipts and
after-images. Queue acceptance alone was never counted as a successful UI
transition. No focus request or physical cursor movement was submitted. A stale
recording and a changed-image attempt were rejected before input; neither was
blindly replayed.

One initial launch through the normal installed launcher preceded the owner's
CLI instruction. No claim is made that that launch used this new CLI route.

## Profile isolation and verified restoration

The protected original `The Sims 4 DO NOT TOUCH` was never renamed or written.
The prior active profile was already token-marked disposable; its guard and
multi-hybrid saves were preserved. Before any profile change, all **8,055 files,
21,739,622,657 bytes** were copied and destination hashes verified, with source
stats and save hashes rechecked. The backup manifest SHA-256 is
`af4b24e7989d3d0340c1556c7b4a660eb525c1482d90bb3e3f98fdbc5574c554`.

The intact old disposable directory was retained by a journaled same-volume
rename. A new empty token-marked profile occupied the existing disposable slot,
containing copied Options.ini and empty saves/Tray/Mods with Resource.cfg only.
No old hybrid save was loaded without Apex. The new profile generated an
ordinary human in native CAS; it was not saved as a reproducible fixture.

The process was `95936`, creation FILETIME `134382510974420748`, game version
`1.129.39.1030`, executable SHA-256
`95e40b75f76711c66b9f36a974ec04d43304a6f591d409d3d4019818f366237b`.
The fresh profile had no mod artifacts. A higher-integrity read-only inventory
observed 140 loaded modules, no Apex/TD1-named module, and the system D3D11/DXGI
modules. The game-bin inspection found no Apex graphics proxy. The mod-state
record documents the exact observation method; a boolean alone is not proof.

After native exit and independent process-absence verification, the new control
was archived and the entire retained disposable profile returned to its former
path. An independent full rehash matched **all 8,055 file contents and stats**
against the backup, including all 22 saved files. No restore from lossy copies,
recursive deletion, protected-original rename or installed-mod replacement
occurred. The complete backup and control results remain available locally.

## Collector results: stop before adding features

Hardware observation: RTX 4090, desktop 2560 by 1440 at 144 Hz; actual Canvas
2560 by 1385, DPI 96. The pinned PresentMon 2.6.0 binary SHA-256 is
`b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af`.
Every attempt used a unique owned trace name. No unrelated trace was stopped.

| Attempt | Duration | Scope and changed condition | Lost ETW events | Usable rows |
| --- | ---: | --- | ---: | ---: |
| cas-idle-qualification-01 | 30 s | Target PID, initial collector command | 238,166 | 0 |
| cas-idle-qualification-02 | 30 s | Target PID, disable GPU/display metrics | 17,997 | 0 |
| all-process-diagnostic-01 | 5 s | Same reduced metrics, no PID filter | 3,100 | 0 |
| target-stdout-diagnostic-01 | 5 s | Target PID, normal child process, stdout | 3,016 | 0 |

The first three produced no CSV. The final stdout file contains only a two-byte
BOM. All remain invalid despite exit code zero. Different duration/options and
collector context mean these loss totals are not comparable game-performance
measurements. The all-process failure also prevents blaming only the PID filter.
The cause of event loss is not established. Thread count, process elevation,
background operation or the mod must not be declared the cause from this data.

The private raw logs, metadata, module/window inventories and hash-bound
`qualification-summary.json` remain in `.work/control-20261104`. Summary SHA-256:
`ab80697332ef8a95747fcdfae4c2f27ca90c7878c88978245cfcad7aca28b98d`.
No synthetic intervals replace missing presents.

External WGC videos verify sampled UI transitions, not every Present, displayed
FPS or latency. Several 30-second videos passed exact integer encoder/decoded
PTS equality. One was rejected for a one-tick mismatch and retained as invalid.
The exit recording became invalid when the target Canvas disappeared, as
expected during native shutdown; it is not used as timing evidence.

Modernize supplied historical successful Apex CSVs plus a later failed V346
attempt with 40,150 lost events. Those establish neither a current control nor
a cure. Its older WPR CPU trace and window-thread sampler may help attribute a
future reproducible hitch; they do not substitute for a valid frame trace.
WPR was observed available and not recording; no WPR capture was started here.

## Safe code progress and validation

The collector now requests present-only metrics without changing the default
combined QPC CSV contract. This is reduced requested instrumentation, not a
proven fix for ETW loss. Actual stdout diagnostics were BOM-marked UTF-16;
the collector now preserves raw log bytes, decodes UTF-8/UTF-16 explicitly and
invalidates unknown or truncated final encodings. A usable CSV accompanied by
a UTF-16 loss warning is rejected. Log hashes and observed loss are recorded
even when no CSV exists. These are evidence-integrity fixes, not CAS behavior.

Validation: **38** collector/comparator/stage cases pass under both embedded
Python 3.7.9 and Python 3.13. Broader frame discovery with Python 3.13 and the
explicit project import root runs **60 cases: 53 pass, seven skip**. The bounded
local CLI protocol and pixel tests pass seven cases; the unchanged external
input prototype's 21 model tests passed before the native qualification.
The early discovery failures were test environment/import-root issues, resolved
without changing CAS runtime code. Static/model tests are not game regression
or performance measurements.

## Remaining work

First obtain a loss-free collector with the same clock/identity guarantees and
diagnose its failures with supported trace tools. Prepare and hash a native,
ordinary saved fixture, qualify the exact action sequence and independently
observe completion. Then run both orders with matched settings/cache/workload,
CAS and Live separately. Add one cumulative supported component group at a
time, preserve the permanent guard and every accepted feature, and stop at any
tail/action regression before proceeding. Saved original hybrids stay out of
this control flow.

All shared-Human/occult ownership, F11 exact item name/image/Studio coverage,
Maru feature switches/search/presets and the complete historical regression
inventory remain required. They have not been implemented or certified by
this measurement checkpoint. The separate external CAS worker's files and
resource work were not edited. The earlier sandbox read denial was resolved
through supported approved execution; no user-data access denial or user action
is currently blocking this work. The present blocker is invalid measurement
evidence and the still-unsaved matched fixture.
