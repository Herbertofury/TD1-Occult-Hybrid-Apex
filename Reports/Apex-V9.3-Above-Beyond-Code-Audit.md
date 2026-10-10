# TD1 Occult Hybrid Apex — V9.3 Above-and-Beyond Code Audit

Date: 2026-05-29
Base audited package: V9.2 Tech Radar
Result: V9.3 code-audited, runtime-safe package.

## Goal

Audit the actual Apex Python backend and Dear ImGui/DX11 overlay source against current Sims 4 modding guidance, current CAS changes, MCCC compatibility expectations, and the supplied Sims 4 game bin. Fix concrete issues instead of only documenting them.

## Research checked

- The Sims 4 Modders Reference appearance guide, especially CAS parts, genetic parts, BodyType slots, and Sims with occult forms.
- Current EA Base Layer CAS update notes.
- Lot51 Core Library current documentation and installation notes.
- Current MCCC 2026.3.1 release metadata and module archive listing supplied by the user.
- Sims 4 `.ts4script` packaging guidance.
- Dear ImGui Win32 + DirectX 11 backend examples and input-capture pattern.
- Microsoft D3D11 entry-point documentation and the supplied `TS4_x64.exe` DX11 string scan.

## Issues found and fixed

### 1. Build identity regression

**Finding:** The V9.2 package still executed an older V9.1 readiness shim near the end of the Python source, resetting `_BUILD_VERSION` to `2026.05.28-v9.1-ready-overlay-safe`.

**Fix:** V9.3 appends a final hardening shim that sets:

```text
_BUILD_VERSION = 2026.05.29-v9.3-code-audited-runtime-safe
IMGUI_OVERLAY_API_VERSION = 9
```

The overlay state and capabilities payloads now report this final version.

### 2. New/latest CAS categories were not fail-closed enough

**Finding:** Runtime-only patch-sensitive CAS categories such as `BASE_LAYER`, `HEAD_DECORATION`, `SKIN_SPECULARITY`, and `TATTOO_HEAD_WINGS` could fall back to hardcoded numeric values when the Sims runtime enum was unavailable. That was too risky after game patches.

**Fix:** V9.3 treats these as runtime-only categories. They are visible in the F11 menu, but actions refuse safely unless the live Sims runtime exposes a matching `BodyType` enum member. Stable BodyType values 0-112 may still use the fallback table.

Runtime-only category keys now include:

```text
HEAD_DECORATION
SKIN_SPECULARITY
TATTOO_HEAD_WINGS
BASE_LAYER
```

### 3. Legacy MCCC guard could still behave like an idle periodic check

**Finding:** A legacy guard layer defaulted `_MCCC_GUARD` and `_MCCC_AUTO_RESTORE` to true in older code. Even though newer F11 MCCC Shield controls were explicit, that old layer could still snapshot after an idle interval once the queue was active.

**Fix:** V9.3 forces both defaults off:

```text
_MCCC_GUARD = False
_MCCC_AUTO_RESTORE = False
```

The explicit MCCC Shield buttons still arm, snapshot, restore, commit, and scan when the player chooses them.

### 4. Future DX11 proxy risk after Sims patches

**Finding:** The current proxy source wraps the D3D11 device creation entry points used by the supplied game bin, but future Sims patches could change or add entry usage.

**Fix:** Added:

```text
NativeOverlay/verify_ts4_dx11_imports.py
```

Run it against `TS4_x64.exe` before installing the built proxy. It confirms the currently scanned bin uses the expected D3D11 entry strings and warns if extra D3D11 entry names appear.

### 5. Code audit command missing from the F11 workflow

**Finding:** QA Self-Test existed, but there was no separate read-only command focused on code-audit/runtime category preflight.

**Fix:** Added read-only commands:

```text
code_audit
apex_code_audit
v9_3_audit
```

The F11 overlay now has a **Code Audit** button beside QA Self-Test.

## Confirmed implementation alignment

### Occult forms

Apex keeps the important workflow explicit: switch/select occult, commit current form to selected occult, accept baseline, scan drift, and fix/restore from baseline or saved form. This aligns with the documented Sims 4 behavior where the current visible `sim_info` and occult-form `sim_info` records are separate and current-form edits do not automatically sync into the occult-form record.

### CAS categories

Apex tracks CAS BodyType categories and separates stable body-type fallbacks from runtime-only patch-sensitive entries. Copy/paste uses category-specific operations and keeps conflict handling for Full Body vs Upper/Lower Body. Genetic/detail categories are treated differently from simple outfit slots.

### MCCC

Apex does not depend on private MCCC internals. It detects MCCC presence, provides explicit MCCC Shield arm/restore commands, and supports the intended workflow of editing through MCCC then committing/scanning/restoring occult form data from Apex.

### Lot51 / XML Injector

Lot51 Core remains optional. Apex can detect and use it where available, but does not hard-require it. XML Injector remains optional and is not forced into this package because Apex already has a Python backend/native overlay and most of the requested UI/control work is not XML-interaction driven.

### Overlay performance

The F11 overlay still polls only while visible. Gameplay edits are routed through the Python/game-thread command queue. Drift scans, category copy/paste, MCCC snapshots, screenshots, and QA/audit checks are button-driven.

## Validation performed in this environment

- Python AST parse: OK
- Python compile to temporary `.pyc`: OK
- Offline Apex backend smoke test: OK
- `/api/overlay/capabilities`: HTTP 200
- `/api/overlay/state`: HTTP 200
- `/api/command?action=code_audit`: HTTP 200
- `/api/command?action=cas_category_status`: HTTP 200
- Stable category fallback check, `SHOES`: OK
- Runtime-only category fail-closed check, `BASE_LAYER`: OK
- Runtime-only category fail-closed check, `HEAD_DECORATION`: OK
- Numeric runtime-only value `116` fail-closed when live enum unavailable: OK
- MCCC legacy guard default: OFF
- MCCC legacy auto-restore default: OFF
- Overlay C++ brace/string/comment sanity check: OK
- Supplied `TS4_x64.exe` DX11 preflight scan: OK
- No `__pycache__` / `.pyc` files included in mod folder before packaging.

## Supplied game-bin DX11 preflight result

```text
Contains d3d11.dll string: True
D3D11CreateDevice: FOUND
D3D11CreateDeviceAndSwapChain: FOUND
OK: current proxy entry coverage matches this TS4_x64.exe string scan.
```

## Remaining test that cannot be completed in this Linux sandbox

The Windows DirectX 11 proxy must still be compiled on Windows with Visual Studio Build Tools and tested by launching Sims 4. This environment cannot launch Sims 4, cannot load the Windows D3D11 runtime, and cannot verify actual in-game CAS save events. Use the included QA Self-Test, Code Audit, MCCC Shield flow, and DX11 verifier before playing a real save.

## Final V9.3 Windows-side checklist

1. Back up your Sims 4 save.
2. Install `TD1 Occult Hybrid Apex` one folder deep under `Documents\Electronic Arts\The Sims 4\Mods`.
3. Build the overlay from `NativeOverlay` on Windows with `build_msvc_x64.bat`.
4. Run `verify_ts4_dx11_imports.py` against your current `TS4_x64.exe`.
5. Copy the generated `d3d11.dll` next to `TS4_x64.exe` only if the verifier passes.
6. Launch Sims 4 in DX11.
7. Press F11.
8. Run **Code Audit** and **QA Self-Test**.
9. Test with a copied save before using on a main save.
10. After MCCC/CAS edits, run Commit Current -> Selected Occult, Accept Baseline, and Scan Selected Occult.
