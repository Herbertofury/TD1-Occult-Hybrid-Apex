# Source, build and runtime owners

## Recovered input

The owner selected the newer local V9.6 source on 2026-10-06. Commit `44b2827` preserves it before edits. The unavailable V9.5 ZIP remains historical provenance; no hash equivalence to that ZIP is claimed. Historical reports retain their original dates and evidence limits.

`Source/td1_occult_hybrid_apex.py` is the single recovered Apex Python entrypoint. Its `.py` source is stored at the root of `TD1_OccultHybridApex.ts4script`; the game loads the source with its own Python runtime. Compiling it with the development machine's Python 3.13 into `.pyc` would produce incompatible bytecode and is prohibited. Syntax validation targets Python 3.7.

The separate historical `TwelfthDoctor1_OccultHybridHandler.ts4script` owns the `OccultHybrid` package: CoreLib, FrameworkLib, IC_Hybrid, Modules and UtilLib. It is a baseline/regression input, not part of the final standalone artifact. Its module/resource inventory belongs in the baseline manifests, outside production source ownership. The recovered Apex module contains legacy memory-trait IDs and optional native bridge detection; presence of source alone does not prove standalone gameplay parity.

## Native overlay

`NativeOverlay/Source/TD1ApexD3D11Proxy.cpp` is the overlay entrypoint, linked with the exact vendored ImGui tree. CMake builds an x64 `d3d11.dll` forwarding `D3D11CreateDevice` and `D3D11CreateDeviceAndSwapChain` to the Windows system DLL, and intercepts swapchain Present/ResizeBuffers. F11 toggles the overlay. HTTP transport runs in a worker; the render path must never mutate Sim data.

The optional historical helper source is `Source/TD1OccultNativeBridge.c`. Its compiled mask-helper DLL is distinct from the DX11 proxy and must not be silently assumed present.

Build in this checkout:

```powershell
cmake -S NativeOverlay -B NativeOverlay/build -G "Visual Studio 17 2022" -A x64 -DCMAKE_GENERATOR_INSTANCE="H:/Visual Studio/Product"
cmake --build NativeOverlay/build --config Release
python NativeOverlay/verify_ts4_dx11_imports.py "C:/Games/The Sims 4/Game/Bin/TS4_x64.exe"
python tools/source_inventory.py Source/td1_occult_hybrid_apex.py --output manifests/runtime-owners.json
python -m unittest discover -s tests -v
git add Source NativeOverlay tools tests docs Reports wiki
python tools/source_manifest.py
python tools/source_manifest.py --check
```

`NativeOverlay/install_to_game_bin.ps1` defaults to check-only. It requires a closed game, unlinked paths, strict executable import verification, stable input hashes and an unoccupied `d3d11.dll` path. Explicit `-Install` uses a no-overwrite copy and records the exact identities. Existing ReShade/GShade/RTBP proxies are separate owners. The current executable fails import verification, so no proxy has been installed and live F11 compatibility remains open.

## Backend transport and layered definitions

The HTTP server binds `127.0.0.1:8017`. `_handle_http_client` parses commands, `_submit_action` schedules work, and `_process_pending` dispatches `run_action` on the Sims alarm path. Console commands use the same action dispatcher from the game thread. External imports without Sims services no longer start a server or load persistent form data; external tools should still use the CLI/bridge instead of importing the game module.

The original source appends V6, V6.2, V7, V8, V9, V9.1, V9.3, V9.4, V9.5 and V9.6 layers. Final `run_action`, `_status` and `_overlay_capabilities` retain earlier implementations through `_BASE_*`, `_V62_*`, `_V6_*`, `_V8_PREV_*`, `_V9_PREV_*`, `_APEX93_*`, `_V94_*`, `_V95_*` and `_APEX96_*` aliases. These wrappers remain reachable; deleting earlier definitions would break delegation. `tools/source_inventory.py` records exact definition lines, captures and superseded global owners without executing them.

The canonical queue now rejects off-thread dispatch/bootstrap, bounds admission/results/drain, cancels expired pending work and exposes already-running outcomes. Its weak-referenceable alarm owner matches the current game's alarm contract. Native overflow rejects new work and stale selection responses are ignored. Remaining gaps include an armed idle alarm, broad legacy action contracts, HTTP authentication/request/thread bounds, domain revision guards and exact packaged runtime proof. Static inventory and fixtures do not close runtime gates.

## CLI test workflow

`tools/apex_cli.py` shares the profile tool and actual production transport. No original saves or Tray content enter a test profile. Closed-game guards apply to activation/restoration and executed launches; neither tool kills a process. A retained journal and sibling folders recover interrupted swaps.

```powershell
python tools/apex_cli.py profile activate --profile "$env:USERPROFILE/Documents/Electronic Arts/The Sims 4" --state .work/session.json --artifact dist/dev/ApexOccultHybrid.ts4script
python tools/apex_cli.py profile status --state .work/session.json
python tools/apex_cli.py launch --game-root "C:/Games/The Sims 4" --state .work/session.json
python tools/apex_cli.py launch --game-root "C:/Games/The Sims 4" --state .work/session.json --execute
python tools/apex_cli.py wait --state .work/session.json --seconds 30
python tools/apex_cli.py probe --state .work/session.json --output .work/runtime-proof.json
python tools/apex_cli.py request status --state .work/session.json
python tools/apex_cli.py profile restore --state .work/session.json
```

The launch plan reads this installation's EA manifest/content IDs and hands off to the registered EA launcher. Its protocol shape is informed by the maintained [Lutris EA integration](https://github.com/lutris/lutris/blob/master/lutris/services/ea_app.py); no Lutris source is bundled. EA approval prompts may still need the owner. A plan or handoff is not launch success. The current plan is structurally proven; executed EA protocol launch remains unverified.

`wait` requires a ready game-thread alarm, not merely an open socket. `probe` writes exact artifact identities and read-only results outside both profiles. Generic commands require an exact active isolated session. Local transport refuses proxies/redirects. Truly headless engine execution is not implemented; `--headless` fails explicitly without launching a graphical game. The separate Foundry backlog retains that accepted objective.

Source manifests describe canonical staged Git blobs so Windows line endings do not change identities. Unstaged source edits are rejected; stage coherent source before generating/checking. Artifact manifests always hash exact raw artifact bytes.

## Test and release boundary

Use an isolated disposable user profile and only the required baseline/Apex artifacts. Never load the owner's live save or launch with the large Mods library. Preserve both profiles by rename and restore the original afterwards. No runtime/regression/release gate may be checked merely because a source manifest, build or fixture passes.
