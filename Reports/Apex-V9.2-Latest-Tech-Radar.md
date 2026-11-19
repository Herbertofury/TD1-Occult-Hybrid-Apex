# TD1 Occult Hybrid Apex V9.2 - Latest Tech Radar and Upgrade Plan

Research date: 2026-05-28
Package purpose: continue from V9.1, document the current best technologies and patch one newly discovered CAS category gap.

## Immediate safe code/documentation change applied

- Added guarded runtime CAS category row: `BASE_LAYER` / `Base Layer`.
- Updated the F11 overlay CAS Categories table with a matching `BASE_LAYER` row.
- This is intentionally runtime-guarded through the existing BodyType resolver path. It should only execute if the current Sims 4 runtime exposes `BodyType.BASE_LAYER`; otherwise it fails closed like the other newest categories.

Reason: the Sims4Studio CAS Categories reference was updated on 2026-05-15 with a new `Base Layer` category.

Source: https://www.patreon.com/posts/sims4studio-cas-115978418

## Technologies worth adopting next

### 1. Lot51 Core Library as the optional event/config/service layer

Lot51 Core Library v1.43 was current during this research pass. It provides reusable snippets, logging, config files, game services, and an event system for zone load/unload-style behavior. Apex should keep Lot51 optional, detect it at runtime, and use it for non-critical event/config/logging improvements when present.

Source: https://lot51.cc/mods/core-library

### 2. Sims 4 Community Library as an optional developer API layer

S4CL is described as an API/framework for Sims 4 developers rather than a gameplay mod by itself. It may be useful for standardized logging, event abstractions, resolvers, notifications, and utility wrappers, but Apex should not hard-require both S4CL and Lot51 unless a specific feature genuinely needs it.

Source: https://github.com/DeviantGameMods/Sims4CommunityLibrary

### 3. XML Injector only for optional tuning-facing interaction injection

XML Injector v4.2 is documented for adding interactions, loot action hooks, buffs to traits, phone/relationship panel interactions, and other tuning injections without each mod shipping its own script. Apex already needs Python and native overlay code, so XML Injector should not replace the backend. It is useful only for optional in-game pie-menu, mailbox, computer, or phone entry points.

Source: https://scumbumbomods.com/xml-injector

### 4. Lot51 TDesc Builder / EA TDESC diff workflow

Lot51 Tuning Builder can view and generate tuning from current TDESCs. Codex should add a patch-update workflow that extracts current `generated.zip`, compares BodyType/Occult/CAS/outfit-related enums and TDESCs, and emits a patch report before any code changes.

Sources:
- https://tdesc.lot51.cc/
- https://thesims4moddersreference.org/tutorials/modifying-sim-appearances/

### 5. Dear ImGui 1.92.8 plus docking/table polish

Dear ImGui 1.92.8 is current during this pass. Apex should stay on the official Win32 + DirectX 11 backend and use ImGui tables, filters, child panels, keyboard navigation, and docking-style layout ideas for the F11 menu. Multi-viewports are powerful but should remain disabled inside Sims unless heavily tested, because they create extra OS windows and can complicate input focus over a game window.

Sources:
- https://github.com/ocornut/imgui/releases
- https://github.com/ocornut/imgui/wiki/Multi-Viewports

### 6. MinHook or Detours for a safer overlay hook layer

The current proxy approach is simple. A better V10 native overlay path is:

- Keep `d3d11.dll` proxy as install option A.
- Add MinHook-based `IDXGISwapChain::Present` and `ResizeBuffers` hooks as install option B.
- Keep Microsoft Detours as a researched alternative for Windows API instrumentation, not the default, because MinHook is smaller and purpose-built for minimal x86/x64 function hooks.

Sources:
- https://github.com/TsudaKageyu/minhook
- https://github.com/microsoft/Detours

### 7. DirectXTex for screenshot/reference-shot upgrades

Apex currently captures reference screenshots. DirectXTex should be used for robust WIC-based PNG/JPEG output, resizing, format conversion, and thumbnail generation. It is more appropriate than hand-written BMP-only output if the screenshot system becomes a full reference library.

Source: https://github.com/microsoft/DirectXTex

### 8. WIL for safer Windows C++ overlay code

Microsoft WIL is a header-only library for safer, readable Windows C++ patterns. It should be used in the native overlay for COM lifetime handling, HRESULT checks, registry/path helpers, and RAII cleanup.

Source: https://github.com/microsoft/wil

### 9. vcpkg manifest mode for reproducible Windows builds

The overlay build should gain `vcpkg.json` and documented manifest-mode dependency restore. This makes dependencies such as MinHook, WIL, and DirectXTex reproducible for Codex and Windows builders.

Source: https://learn.microsoft.com/en-us/vcpkg/consume/manifest-mode

### 10. Crashpad or local minidump capture for native overlay failures

Crashpad can capture postmortem crash reports/minidumps. Apex should not send anything online by default. A local-only minidump mode would help diagnose native overlay crashes without guessing.

Source: https://github.com/chromium/crashpad

### 11. ETW and Tracy for optional performance investigation builds

Apex should not ship heavy profiling enabled. For debug builds, ETW markers and optional Tracy zones would make it easier to prove the overlay and backend are not adding frame hitches.

Sources:
- https://learn.microsoft.com/en-us/windows/win32/etw/event-tracing-portal
- https://github.com/wolfpld/tracy

### 12. MCCC-aware compatibility scanner

MCCC 2026.3.1 was the current CurseForge release observed during this research pass. Apex should keep compatibility defensive: detect modules and versions, avoid private internal dependencies where possible, and keep the MCCC Shield workflow user-driven around CAS entry/exit restore/commit.

Source: https://www.curseforge.com/sims4/mods/mc-command-center/files/7841442

## V10 recommended implementation order

1. Add an in-menu `Tech Preflight` report showing detected Lot51, S4CL, XML Injector, MCCC, DX version, ImGui build, overlay hook mode, and CAS category enum availability.
2. Add `BASE_LAYER` runtime category support. Done in this V9.2 package.
3. Convert overlay project to CMake + vcpkg manifest mode with optional MinHook, WIL, and DirectXTex.
4. Add DirectXTex PNG reference screenshots and thumbnail browser in F11.
5. Add Lot51-backed event registration when installed, with fallback to existing fire-once/manual commands when not installed.
6. Add a patch-diff tool that reads `generated.zip`, TDESCs, and BodyType enum symbols from the current game install and writes a compatibility report.
7. Add local-only minidump capture for the overlay DLL, disabled by default.
8. Add debug-only ETW/Tracy profiling toggles.

## Red lines for future Codex work

- Do not move Sims gameplay data edits into the DirectX render thread.
- Do not require Lot51, S4CL, XML Injector, or MCCC for the core occult repair path unless the feature cannot work without them.
- Do not add constant Sim scanning or CAS drift timers by default.
- Do not trust fixed BodyType values for newly added categories; runtime-resolve them.
- Do not bundle third-party mods such as Lot51 Core, XML Injector, or MCCC in the Apex zip. Detect them and tell the user where to install/update them.
- Do not claim zero performance impact; prove low impact with measurements and keep heavy features button-driven.
