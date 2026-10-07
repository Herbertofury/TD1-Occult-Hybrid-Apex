# Source Recovery Status

Recovered baseline archive: `TD1_Occult_Hybrid_Apex_Full_Mod_FINAL_ACCOUNTING_V9_5.zip`  
Archive SHA-256: `5bae3bfdb0f7aef8fde94f3e1058d74bdc80fb79fdcbd33c12fed78beae83249`

## Mirrored directly in this repository

- `Source/TD1OccultNativeBridge.c`
- `NativeOverlay/CMakeLists.txt`
- `NativeOverlay/verify_ts4_dx11_imports.py`
- `NativeOverlay/install_to_game_bin.ps1`
- `NativeOverlay/build_msvc_x64.bat`
- `NativeOverlay/README_BUILD_AND_INSTALL.txt`
- Current Codex execution/parity/toolbox docs
- Wiki mirror and TODO

## Recovered but not yet directly mirrored through this connector

These are present in the verified V9.5 recovery archive and are **active recovery inputs**, not lost/unknown files:

| File | Bytes | SHA-256 |
|---|---:|---|
| `Source/td1_occult_hybrid_apex.py` | 377,380 | `f2020d351f1344beb0641dea20d5cc47e91430a3fb4d49a61179bf641673e34b` |
| `NativeOverlay/Source/TD1ApexD3D11Proxy.cpp` | 51,297 | `3d9a7b28dead101cb9f480384c611904a3bd55614099507929a8742361fcfbac` |
| Dear ImGui vendored source tree | recovered | see V9.5 archive / upstream 1.92.8 provenance |
| packaged `.ts4script`, `.package`, `.dll/.lib` artifacts | recovered | see `RECOVERED_BINARY_ARTIFACTS.md` |

The GitHub connector used for this recovery writes repository text directly but has no safe local-file streaming input for these large recovered files. Do **not** recreate them from memory. Codex/local Git should extract the verified archive, compare these hashes, then commit the exact recovered files before editing them.

## First Codex recovery action

1. Obtain the verified V9.5 archive.
2. Verify archive SHA-256.
3. Extract to a clean staging directory.
4. Verify the two hand-authored large-source hashes above.
5. Compare against repository paths.
6. Commit the exact recovered sources.
7. Only then begin T005/T007 and implementation changes.
