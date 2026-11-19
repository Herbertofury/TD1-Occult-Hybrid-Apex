# TD1 Occult Hybrid Apex V9.4 - Unbelievable Research Accounting Pass

Build: `2026.05.29-v9.4-research-lockdown-accounted`

This pass reviewed the known high-risk areas for this tool: Sims 4 script packaging, Python runtime behavior, CAS appearance data, occult form SimInfo separation, MCCC compatibility, Lot51/Core/XML Injector strategy, DX11 Dear ImGui proxy behavior, ReShade/proxy conflicts, screenshot capture, and post-patch update procedures.

## Research-backed conclusions

- Sims 4 script mods remain `.ts4script` archive packages; packaged `.py` source is acceptable and the file must be placed no more than one folder deep under `Mods`.
- CAS Parts cover clothes, hair, tattoos, body/face details, eye colors, and more; each CAS part occupies a BodyType slot, and genetic BodyTypes such as tattoos/skin details need separate genetic-data handling.
- Occult forms are separate occult `sim_info` records. Editing the visible/current SimInfo does not automatically update the stored occult form SimInfo, so Apex must keep explicit Commit, Baseline, Scan, Fix, and Saved Form commands.
- Full Body conflicts with Upper Body / Lower Body; category paste must normalize those slots.
- Base Layer is a new May 2026 CAS feature; it must remain runtime-resolved/fail-closed, not trusted as a permanent hardcoded numeric category.
- Lot51 Core is useful as an optional event/config/logging layer, but detection must be passive. Automatic event registration from status polling is too risky.
- XML Injector is not appropriate as a core dependency for this tool; it is best for future tuning-facing pie menu / object interaction entry points.
- MCCC should be treated as an external major mod, not an API to mutate. Apex compatibility is best handled by explicit MCCC Shield snapshot/restore around MCCC Modify in CAS.
- TS4 DX11 is active by default on many Windows NVIDIA/AMD setups, but DX9/DX11 selection and other proxy DLLs matter. The native overlay must be documented as a DX11 `d3d11.dll` proxy and must not claim compatibility with every ReShade/GShade/proxy setup without chain-loader testing.

## Code changes made in V9.4

1. Lot51 detection is now passive: `_detect_lot51_core()` no longer registers event handlers just because the F11 overlay polls capabilities/status.
2. Legacy Lot51 event hooks are no longer installed automatically at import/startup.
3. V6 Lot51 event registration is no longer attempted automatically. Manual registration remains available through `lot51_register_events` / `lot51_events_on` after the MCCC Shield is armed.
4. Legacy MCCC guardian defaults are disabled. The supported path is the explicit F11 MCCC Shield workflow.
5. Added backend command `research_audit`.
6. Added F11 overlay button `Research Audit`.
7. Updated build identity to `2026.05.29-v9.4-research-lockdown-accounted`.

## Default safety policy

- No gameplay edits from the native DirectX render thread.
- No hidden overlay polling.
- No drift scans unless clicked or explicitly enabled after a command.
- No legacy MCCC/Lot51 background guardian by default.
- Patch-sensitive CAS categories fail closed unless the live Sims runtime exposes the matching enum.

## Required Windows-side tests

1. Build `NativeOverlay` from an x64 Visual Studio Developer Command Prompt.
2. Run `verify_ts4_dx11_imports.py` against the active `TS4_x64.exe`.
3. Install the mod into `Documents\Electronic Arts\The Sims 4\Mods\TD1 Occult Hybrid Apex`.
4. Install the built `d3d11.dll` proxy next to `TS4_x64.exe`, after resolving any ReShade/GShade/RTBP proxy conflicts.
5. Launch a copied save in DX11.
6. Press F11 and run `Research Audit`, `Code Audit`, and `QA Self-Test`.
7. Use MCCC > Sim Commands > Modify in CAS only after arming Apex MCCC Shield.
8. After CAS exit: restore, commit current form to selected occult, accept baseline, scan drift, then save.

## Remaining honest limitation

This package is defensively coded and offline-validated, but no offline Linux sandbox can prove flawless behavior inside every Sims 4 save, Windows GPU driver, DX11 overlay stack, MCCC configuration, and post-patch runtime. The new guards make unknown runtime changes fail closed instead of silently touching Sim data.

## External references reviewed

- Sims 4 Modders Reference - Modifying Sim Appearances: https://thesims4moddersreference.org/tutorials/modifying-sim-appearances/
- Sims 4 Modders Reference - Creating an injector: https://thesims4moddersreference.org/tutorials/creating-injector/
- Lot51 Core Library docs: https://lot51.cc/mods/core-library
- Lot51 Core Library GitHub: https://github.com/lot51/core-library
- XML Injector documentation: https://scumbumbomods.com/xml-injector
- MCCC documentation: https://deaderpool-mccc.com/documentation.html
- MCCC FAQ: https://deaderpool-mccc.com/faq.html
- MCCC installation guide: https://deaderpool-mccc.com/installation.html
- MCCC 2026.3.1 CurseForge release: https://www.curseforge.com/sims4/mods/mc-command-center/files/8080206
- EA Sims 4 DX11 guide: https://forums.ea.com/discussions/the-sims-4-technical-issues-pc-en/directx-11-dx11-for-the-sims-4---a-step-by-step-guide/11811172
- EA Base Layers creator guide: https://forums.ea.com/blog/the-sims-game-info-hub-en/layer-up-a-creator%E2%80%99s-guide-to-base-layers-in-cas/13349904
- Dear ImGui DX11 example: https://github.com/ocornut/imgui/blob/master/examples/example_win32_directx11/main.cpp
- Dear ImGui releases: https://github.com/ocornut/imgui/releases
- MinHook: https://github.com/TsudaKageyu/minhook
- DirectXTex ScreenGrab: https://github.com/microsoft/DirectXTex/wiki/ScreenGrab
- ReShade API docs: https://crosire.github.io/reshade-docs/index.html
- EA alarm-handle discussion: https://forums.ea.com/discussions/the-sims-4-mods-and-custom-content-en/fixed-how-to-use-properly-alarmhandlde-/630234
- ModTheSims real-time alarm thread: https://modthesims.info/showthread.php?t=651671
- TD1 Occult Hybrid Unlocker/Stabilizer public notes: https://www.curseforge.com/sims4/mods/occult-hybrid-unlocker-stabilizer
