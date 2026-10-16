# Mod-folder F11 loading and numeric Color Studio

The candidate now includes a concrete F11 sidecar loading path and scoped numeric
color editing. It remains a development candidate; this report does not assert
full MCCC/Color Studio/Tray parity or close any game/runtime/release gate.

## Changes

- `apex_core.overlay_loader` checks the exact neighboring mod-folder DLL hash,
  protocol, bounded files, archive layout and unlinked paths. It refuses the
  protected original profile and different cached native builds. It uses the
  installed game `_ctypes_x64.pyd` directly, retaining the CPython initialization
  name, even when the pure `ctypes` package is absent. No native code loads on an
  external source import. The loaded-household owner signal starts the overlay;
  `AutoStart=0` and explicit console start/status are available.
- The native DLL validates the actual Sims x64 host and loaded Python/Simulation
  modules before enabling hooks. It gets system DXGI function addresses through
  a hidden bootstrap swapchain. Pinned MinHook v1.3.4 handles x64 detours and
  rollback. Foreign swapchain implementations/entry detours are refused. The
  DLL remains pinned while hooks are active. No Game/Bin proxy is required.
- Fixed the initial F11 toggle checking an uninitialized window handle. Input
  uses the high key-state bit and an owned edge rather than the consumable low
  bit. Native input/render access is serialized. The overlay saves/restores all
  eight original render targets and depth before changing output state, ignores
  unrelated swapchain resizing, and tears down/reinitializes after device loss.
- Numeric H/S/B/O uses four signed 16-bit Q14 lanes. The effective CASP's actual
  ranges, increments and disabled channels are read on explicit owner requests.
  Only edited lanes change. Each preview checks save/Sim/form, full appearance,
  exact part/color identity and resource hash. Apply/readback/rollback and
  previewed Undo/Redo/Jump use the existing persistent recovery journal.
- The candidate's native files now travel together in `Mods/Apex/Native`, with
  the matching SHA-256 manifest, configuration, full licenses and provenance.
  The script contains matching Python 3.7 bytecode for all included modules.

## Verification

| Check | Evidence / result |
| --- | --- |
| Offline Python production fixtures | 101 passed |
| Native transport/typed color/history validation | 21 checks passed |
| Actual independent DX11 WARP host | Present detour, full menu and numeric color rendering, eight RTVs + depth restoration, ResizeBuffers, teardown/reinit and first/held/focus key edges passed; no HTTP worker started |
| Matching Python 3.7 native exports | Protocol=1; start rejects the independent host with -1; no hooks installed |
| Actual packaged script/extension loader | `.ts4script` import succeeded with pure `ctypes` deliberately absent; standard extension loader loaded the private compiler's matching `_ctypes` extension under the game's naming/layout; production DLL correctly refused the non-game host |
| Independent original SimRipper C# parser | 32 installed current-game CASP resources match version/body type and bit-identical float32 slider bounds/increments |
| Original C# writer/reader layouts | CASP versions 44 through 52 match the Apex metadata reader, nine comparisons |
| Packaging | Six DBPFs/204 resources, exact compiled-script references, native manifest/protocol and complete licenses; `manifests/candidate-build.json` records the current exact ZIP hash |

The current-game resources were extracted read-only using Foundry's independent
Rust implementation. SimRipper's original C#/GPL sources were built privately as
a comparison oracle. Only format facts and comparison hashes are published;
neither private EA resource bytes/code nor the third-party oracle is distributed.
The authorized Color Sliders UI confirms neutral H/S/B=0 and opacity=1 and derives
control ranges from CASP metadata. JPEXS FFDec 26.3.0 was a private research tool.
`manifests/cas-color-format.json` records pinned inputs and every comparison.

## Boundaries and remaining work

No game launch, save load, bridge polling, game-directory/profile writes, native
input automation or live Sim mutation occurred. The protected original folder
was never changed. The owner continues live testing with the single retained
disposable profile and Sim/save. Installation steps are in
`docs/CANDIDATE_INSTALL_AND_TEST.md`.

The real game must still prove sidecar startup, first F11 interaction, backend
convergence, device/overlay coexistence, form switching and save/reload/restart.
Full shared history for legacy mutations, MCCC CAS/Dresser coverage, Tray sources,
semantic history, palettes/favorites, current-patch CAS UI port and texture
conversion remain open in the canonical checklist. CASP slider metadata does not
prove LRLE/CC texture compatibility or fix the owner's reported gloss globally.
The separate Foundry/game performance/headless scope remains accepted future
work. No first-try or full-completion guarantee is asserted.

Automatic approval review blocked recursive cleanup of one tool-created temporary
native-host fixture outside the repository. It contains no game data. Subsequent
fixtures run inside private checkout work and are cleaned after child exit.
