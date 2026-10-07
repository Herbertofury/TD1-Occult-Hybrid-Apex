TD1 Apex Dear ImGui DirectX 11 Overlay Source Kit
=================================================

What this is
------------
This is a native Windows x64 d3d11.dll proxy overlay project for The Sims 4 DX11 path. It uses the Dear ImGui 1.92.8 source you provided and talks only to the TD1 Apex local API at 127.0.0.1:8017.

How it is designed
------------------
- The Sims 4 script mod stays responsible for occult data changes.
- The overlay only renders UI and sends local HTTP commands to the script mod.
- F11 toggles the ImGui overlay.
- Hidden mode is passive: no HTTP polling and no Sims data scans.
- Visible mode polls compact overlay state about once per second and reads the running log.
- Commands are executed by the Python mod's game-thread alarm queue, not directly from the DirectX Present thread.

Build requirements
------------------
- Windows 10/11 x64
- Visual Studio 2022 with "Desktop development with C++"
- CMake tools for Windows
- The Sims 4 running in DirectX 11 mode

Build
-----
From an x64 Visual Studio Developer Command Prompt:

    cd NativeOverlay
    build_msvc_x64.bat

Install
-------
Copy the resulting:

    NativeOverlay\build\Release\d3d11.dll

to your Sims 4 Game\Bin folder next to TS4_x64.exe. This is the same broad proxy-DLL placement style used by RTBP-like native overlays, but this implementation is TD1-specific and only talks to localhost.

Disable
-------
Delete the copied d3d11.dll from Game\Bin. Do not delete the system d3d11.dll in Windows\System32.

Lot51 Core
----------
Lot51 Core is not bundled in this archive because its own public guidance says mod authors should depend on it rather than include the packaged library. This build detects it if the user installs a current lot51_core.ts4script in Mods, and reports that status in diagnostics.

Validation note
---------------
The Python script, archive structure, and helper bridge DLL are validated in this Linux build environment. The DirectX 11 ImGui proxy source requires Windows SDK/Visual Studio to compile and must be smoke-tested in-game on Windows because this environment cannot launch The Sims 4 or link against the Windows DirectX SDK.

V9 QA note:
- Build the overlay with Visual Studio 2022 x64 and CMake using build_msvc_x64.bat.
- After copying d3d11.dll next to TS4_x64.exe, launch the DX11 game, open a household, press F11, and click QA Self-Test.
- QA Self-Test must report no fatal items before using mutating commands. Warnings about optional MCCC/Lot51/XML Injector are informational unless you are testing that integration specifically.
- Category paste is now conflict-aware for FULL_BODY versus UPPER_BODY/LOWER_BODY, matching the documented Sims body-type exclusivity rule.

V9.3 preflight
--------------
Before copying d3d11.dll into Game\Bin, run:

    py verify_ts4_dx11_imports.py "C:\Path\To\The Sims 4\Game\Bin\TS4_x64.exe"

The proxy currently wraps D3D11CreateDevice and D3D11CreateDeviceAndSwapChain. If the verifier reports extra D3D11 entry points, expand the proxy exports/wrappers before installing. This avoids entry-point-missing launch failures after EA changes the DX11 binary.
