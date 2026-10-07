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
python tools/source_manifest.py
python tools/source_manifest.py --check
```

The legacy `NativeOverlay/install_to_game_bin.ps1` is unsafe for unattended use: it does not enforce a closed game or verified import surface and can overwrite another proxy. It must be hardened before any install. Existing ReShade/GShade/RTBP proxies are separate owners; refuse ambiguous replacement.

## Backend transport and layered definitions

The HTTP server binds `127.0.0.1:8017`. `_handle_http_client` parses commands, `_submit_action` schedules work, and `_process_pending` dispatches `run_action` on the Sims alarm path. Console commands currently call the same action dispatcher from the game thread. No external tool should import this module: import starts the bridge and loads saved-form data.

The original source appends V6, V6.2, V7, V8, V9, V9.1, V9.3, V9.4, V9.5 and V9.6 layers. Final `run_action`, `_status` and `_overlay_capabilities` retain earlier implementations through `_BASE_*`, `_V62_*`, `_V6_*`, `_V8_PREV_*`, `_V9_PREV_*`, `_APEX93_*`, `_V94_*`, `_V95_*` and `_APEX96_*` aliases. These wrappers remain reachable; deleting earlier definitions would break delegation. `tools/source_inventory.py` records exact definition lines, captures and superseded global owners without executing them.

Identified safety gaps to repair through the canonical tasks: direct HTTP read-only fallbacks can inspect live Sim state off the game thread; queue alarm setup occurs from HTTP; queue/results are unbounded and timed-out work can execute later; repeating queue alarms remain armed while idle; native overflow discards an older accepted command; native responses lack selection generations. Static inventory is not runtime proof that these paths are safe.

## Test and release boundary

Use an isolated disposable user profile and only the required baseline/Apex artifacts. Never load the owner's live save or launch with the large Mods library. Preserve both profiles by rename and restore the original afterwards. No runtime/regression/release gate may be checked merely because a source manifest, build or fixture passes.
