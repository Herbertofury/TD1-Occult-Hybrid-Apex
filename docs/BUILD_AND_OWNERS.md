# Source, build and runtime owners

## Recovered input

The owner selected the newer local V9.6 source on 2026-10-06. Commit `44b2827` preserves it before edits. The unavailable V9.5 ZIP remains historical provenance; no hash equivalence to that ZIP is claimed. Historical reports retain their original dates and evidence limits.

`Source/td1_occult_hybrid_apex.py` is the single recovered Apex Python entrypoint. Its original archive contained source only. Current-game importer inspection invalidated the assumption that this is sufficient: compiled script archive module discovery selects `.pyc`/`.pyo`. `tools/build_script.py` now includes source plus matching Python 3.7 bytecode for every explicit Apex module. Python 3.13 bytecode is incompatible and rejected. The private compiler uses magic `420d0d0a`, fixed hash seed, stable filenames and PEP 552 source-hash headers; no mod is executed during compilation.

The authorized `TwelfthDoctor1_OccultHybridHandler.ts4script` is now a concrete implementation input. The candidate adapts all 36 modules into `apex_hybrid`, with portable filenames and preserved instruction streams except explicitly recorded safety ports. Its original archive is not a runtime dependency. `Source/apex_hybrid/Modules/TD1_OccultHybrid_OccultPicker.py` supplies a real adapter for two orphaned package references, inheriting the actual baseline picker. Hybrid resources retain compatibility IDs while custom module references move into the embedded namespace. Presence of these builds does not prove gameplay parity.

`Source/apex_core/dresser_parts.py` ports four actual authorized MCCC Dresser helpers with recorded comparisons, then supplies strict array handling used by production category paths. `change_journal.py` and `studio.py` own new Studio previews/transactions/history. They do not yet replace every recovered legacy snapshot owner. Crilender's seven actual packages and both thepancake1 UI resources are concrete build inputs, not research-only placeholders.

## Native overlay

`NativeOverlay/Source/TD1ApexD3D11Proxy.cpp` is the overlay entrypoint, linked with the exact vendored ImGui tree. CMake builds an x64 `d3d11.dll` forwarding `D3D11CreateDevice` and `D3D11CreateDeviceAndSwapChain` to the Windows system DLL, and intercepts swapchain Present/ResizeBuffers. F11 toggles the overlay. HTTP transport runs in a worker; the render path must never mutate Sim data.

The optional historical helper source is `Source/TD1OccultNativeBridge.c`. Its compiled mask-helper DLL is distinct from the DX11 proxy and must not be silently assumed present.

Build in this checkout:

```powershell
cmake -S NativeOverlay -B NativeOverlay/build -G "Visual Studio 17 2022" -A x64 -DCMAKE_GENERATOR_INSTANCE="H:/Visual Studio/Product"
cmake --build NativeOverlay/build --config Release
ctest --test-dir NativeOverlay/build -C Release --output-on-failure
python NativeOverlay/verify_ts4_dx11_imports.py "C:/Games/The Sims 4/Game/Bin/TS4_x64.exe"
python tools/fetch_build_python.py
python tools/build_script.py --output dist/dev/ApexOccultHybrid.ts4script
python tools/build_candidate.py --foundry "C:/Users/Owner/Desktop/Sims 4 Foundry/target/release/foundry.exe"
python tools/source_inventory.py Source/td1_occult_hybrid_apex.py --output manifests/runtime-owners.json
python -m unittest discover -s tests -v
git add Source NativeOverlay tools tests docs Reports wiki
python tools/source_manifest.py
python tools/source_manifest.py --check
```

The source-only script command is a development transport build; it omits the authorized namespace and is not the full hybrid candidate. `build_candidate.py` requires the pinned private baseline files and the already-built native component. It emits one bundle under `dist/candidate`, checks every custom XML module reference and can independently extract/hash every package resource through Foundry. It never deploys, launches or changes a Sims user profile. Package/script manifests include their extensions to avoid filename collisions.

`NativeOverlay/install_to_game_bin.ps1` defaults to check-only. It requires a closed game, unlinked paths, strict executable import verification, stable input hashes and an unoccupied `d3d11.dll` path. Explicit `-Install` uses a no-overwrite copy and records exact identities. Existing ReShade/GShade/RTBP proxies are separate owners. The current executable fails import verification, so no proxy has been installed and live F11 compatibility remains open. The rebuilt component has a sidebar, retained command result, CAS History/Color Studio controls and destructive legacy-action confirmation; `ApexOverlay.ini` persists F1–F24 with F11 default. See `docs/CANDIDATE_INSTALL_AND_TEST.md` for the bundle layout/limits.

## Backend transport and layered definitions

The HTTP server binds `127.0.0.1:8017`. `_handle_http_client` parses commands, `_submit_action` schedules work, and `_process_pending` dispatches `run_action` on the Sims alarm path. Console commands use the same action dispatcher from the game thread. External imports without Sims services no longer start a server or load persistent form data; external tools should still use the CLI/bridge instead of importing the game module.

The original source appends V6, V6.2, V7, V8, V9, V9.1, V9.3, V9.4, V9.5 and V9.6 layers. Final `run_action`, `_status` and `_overlay_capabilities` retain earlier implementations through `_BASE_*`, `_V62_*`, `_V6_*`, `_V8_PREV_*`, `_V9_PREV_*`, `_APEX93_*`, `_V94_*`, `_V95_*` and `_APEX96_*` aliases. These wrappers remain reachable; deleting earlier definitions would break delegation. `tools/source_inventory.py` records exact definition lines, captures and superseded global owners without executing them.

The canonical queue now rejects off-thread dispatch/bootstrap, bounds admission/results/drain, cancels expired pending work and exposes already-running outcomes. Its weak-referenceable alarm owner matches the current game's alarm contract. Native overflow rejects new work and stale selection responses are ignored. Remaining gaps include an armed idle alarm, broad legacy action contracts, HTTP authentication/request/thread bounds, domain revision guards and exact packaged runtime proof. Static inventory and fixtures do not close runtime gates.

## Retained CLI work and owner test boundary

The owner took over game testing and requested packages/scripts/F11 work. No agent game launch, save load, bridge polling or native input is part of the candidate build. The latest original-profile constraint supersedes older swap instructions: `The Sims 4 DO NOT FUCKING TOUCH!!!` is read/copy-only and only the owner may rename it. Tools reject original swaps/restoration in that layout. One existing test profile retains the owner's disposable save/Sim; old tool-created test folders were content-hash backed up before consolidation.

`tools/apex_cli.py` retains reusable test-only adoption/install/recovery/status and actual bridge/EA handoff source for future Foundry reuse. Closed-game guards never kill the game. The journal and artifact backups are outside all user profiles. For a read-only state check:

```powershell
python tools/apex_cli.py profile status --state .work/reusable-profile-session.json
```

The retained launch code reads installed EA manifest/content IDs, informed by the [Lutris EA integration](https://github.com/lutris/lutris/blob/master/lutris/services/ea_app.py); no Lutris source is bundled. Literal identifier commas and read-only exact process-image queries fix the observed handoff/observation faults. A protocol handoff alone is never marked success. An older patched packaged bridge answered at the actual main menu, with loaded-zone/alarm readiness false; this is not current-candidate household/CAS/native proof. No further agent game testing is authorized by this checkpoint.

`wait` requires a ready game-thread alarm, not merely an open socket. `probe` writes exact artifact identities and read-only results outside both profiles. Generic commands require an exact active isolated session. Local transport refuses proxies/redirects. Truly headless engine execution is not implemented; `--headless` fails explicitly without launching a graphical game. The separate Foundry backlog retains that accepted objective.

Source manifests describe canonical staged Git blobs so Windows line endings do not change identities. Unstaged source edits are rejected; stage coherent source before generating/checking. Artifact manifests always hash exact raw artifact bytes.

The pinned [official Python 3.7.9 embedded compiler](https://www.python.org/downloads/release/python-379/) is a private build tool matching the game's bytecode generation; it is not the desktop app's tech stack or a global Python install. Its downloaded archive SHA-256 is `18627a097adf47829a847053febac5532376075243e233bd9ec61d6ea09dee1f`, with the official published MD5 independently matching `60f77740b30030b22699dbd14883a4a3`. The binary's PSF Authenticode signature verifies locally. It is used offline only to compile trusted project source, and is not shipped inside the mod. Original compiler license/config files remain preserved in private tooling.

## Test and release boundary

The owner tests with the single existing isolated profile and disposable save/Sim. The protected original is never written/renamed/deleted by tools, and only the owner restores it. No runtime/regression/release gate may be checked merely because a source manifest, build or fixture passes. Exact current evidence and limits are in `Reports/AUTHORIZED_CANDIDATE_2026-10-07.md`; 87 offline fixtures, 18 compiled native data checks and the native build pass.
