# Apex V8.1 Codex + CAS Categories Validation

Date: 2026-05-28

## Scope

Continued from TD1 Occult Hybrid Apex V7. Added Codex continuation/build/test guide and a full F11 CAS Categories tab with fire-on-click copy/paste/apply buttons for each tracked CAS BodyType category.

## CAS category coverage

- Public BodyType values covered: 0 through 112.
- Runtime-resolved 2025 Sims 4 Studio navigation additions represented as guarded latest/runtime entries: HEAD_DECORATION, SKIN_SPECULARITY, TATTOO_HEAD_WINGS.
- Total F11 rows: 116.
- Commands added: copy_cas_category, paste_cas_category, apply_cas_category_to_all_forms, cas_category_status.
- Latest/runtime entries refuse to paste if the current game enum does not expose the matching BodyType name.

## Safety/performance design

- No category copy/paste timer.
- No hidden overlay polling.
- Gameplay mutation remains in the Python command queue.
- Overlay sends localhost commands only.
- Category copy stores selected BodyType payloads in memory until overwritten.
- V8.1 writer uses ClearField plus repeated-field extend instead of assigning protobuf composite fields directly.

## Validation run in sandbox

- Python source compile: OK.
- TD1_OccultHybridApex.ts4script zip integrity: OK.
- Final archive zip integrity: OK.
- C++ overlay source string/comment-aware brace balance: OK.
- C++ source contains CAS Categories tab, kCasBodyTypes table, and category command actions: OK.

## Required external validation

- Build NativeOverlay as x64 on Windows with Visual Studio Build Tools.
- Install generated d3d11.dll beside TS4_x64.exe.
- Launch Sims 4 DX11, press F11, verify the CAS Categories tab renders.
- In a disposable save, test copy/paste/apply for: shoes, gloves, eyelashes, skin overlay, tattoo arm slot, birthmark slot, occult brow, and a latest/runtime category if exposed by the patched game build.
