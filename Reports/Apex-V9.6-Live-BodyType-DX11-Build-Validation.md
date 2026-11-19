# Apex V9.6 Live BodyType / DX11 Build Validation

Date: 2026-05-29

## Read-only game inspection

- Installed game binary inspected: `C:\Games\The Sims 4\Game\Bin\TS4_x64.exe`
- Game version: `1.124.63.1020`
- TS4 SHA256: `00833E92F0529691B0C347087EAB06B9CB6AD385CBC6D59E390BA33B74EACF71`
- Python runtime present: `Game\Bin\python37_x64.dll`
- Required Python extension files present:
  - `Game\Bin\Python\DLLs\_ctypes_x64.pyd`
  - `Game\Bin\Python\DLLs\_socket_x64.pyd`
  - `Game\Bin\Python\generated.zip`
- No local `d3d11.dll`/`dxgi.dll` proxy was found in `Game\Bin` during validation.

## Current live BodyType tail

Read from `Data\Simulation\Gameplay\simulation.zip\sims\outfits\outfit_enums.pyc`:

```text
112 BIRTHMARKOCCULT
113 TATTOO_HEAD
114 WINGS
115 HEADDECO
116 SKINSPECULARITY
117 BASE_LAYER
118 UNUSED
```

V9.6 updates both the Python command table and the ImGui overlay table to these names and fallback values. Patch-sensitive rows still runtime-resolve from the live `BodyType` enum before use.

## Build outputs

- Script archive repacked: `TD1_OccultHybridApex.ts4script`
- Script archive SHA256: `54FB2553425F28C30CF751ED3CB49628A945304F78B6088D1F544EF8D6396002`
- Native overlay built: `NativeOverlay\build\Release\d3d11.dll`
- Native overlay SHA256: `575BA25A281D638DDFFAABF7916D5C8FCD29D8701BDAC331A6A1CC3EA244C2D8`
- Native overlay target: x64 DLL
- Exported D3D11 entry points:
  - `D3D11CreateDevice`
  - `D3D11CreateDeviceAndSwapChain`

## Validation run

- Source syntax compile: OK
- External import/audit: OK, sandbox-tolerant
- `.ts4script` archive test: OK
- Embedded script SHA256 matches `Source\td1_occult_hybrid_apex.py`
- CMake Release build with MSVC 19.44: OK
- `verify_ts4_dx11_imports.py` against installed `TS4_x64.exe`: OK

## In-game follow-up

Run on a copied save:

1. F11 -> `BodyType Live Audit`
2. F11 -> `QA Self-Test`
3. F11 -> `Final Audit`
4. Test `BASE_LAYER`, `HEADDECO`, `SKINSPECULARITY`, `TATTOO_HEAD`, and `WINGS` copy/paste individually.
