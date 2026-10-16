# TD1 Occult Hybrid Apex V9.5 - Final Accounting Research Audit

Build: `2026.05.29-v9.5-final-accounting-safe`

## Purpose
This pass exists to reduce the last high-risk compatibility issues after another Sims 4 modding research review. The priority was not adding more power; it was removing anything that could silently fight The Sims 4, MCCC, Lot51 Core, or future CAS patch changes.

## Research conclusions applied

1. **Occult form data must be treated as separate form SimInfo data.** The Sims 4 appearance workflow is not one single appearance blob for all forms. The Apex Commit / Baseline / Scan / Fix / Saved Forms flows remain necessary.
2. **CAS categories must remain BodyType-based and fail closed.** Stable BodyType values `0-112` are kept; newer categories such as Base Layer are runtime-resolved and refused if the live runtime does not expose the enum.
3. **MCCC compatibility must not monkey-patch MCCC internals.** V9.5 disables the soft/private hook scan path. MCCC interaction is now explicit: arm snapshots, use MCCC, restore/commit/scan.
4. **Lot51 Core is optional and manual.** Event registration is useful only after MCCC Shield is armed. V9.5 blocks Lot51 event registration before an explicit shield arm.
5. **Offline QA must distinguish sandbox from live Sims.** Missing Sims-only modules outside the game are now warnings; inside live Sims they remain fatal if required for a feature.
6. **Overlay stays isolated.** Native ImGui/DX11 UI sends commands to the Python backend. It never mutates gameplay data from the render thread.

## Code changes made in V9.5

- Added final build shim: `2026.05.29-v9.5-final-accounting-safe`.
- Added `final_audit`, `zero_mistake_audit`, and `v9_5_audit` commands.
- Disabled `mccc_soft_hooks_on` / private MCCC hook wrapping. The command now refuses safely.
- Disabled legacy browser aliases `mccc_guard_on` and `mccc_guardian_on` so older UI paths cannot re-enable background MCCC guardians.
- Gated `lot51_register_events` / `lot51_events_on` behind an explicitly armed MCCC Shield.
- Updated QA runtime-import audit so external Linux/dev sandbox testing does not falsely fail on Sims-only modules, while live Sims runtime remains strict.
- Updated the Dear ImGui overlay title and added a `Final Audit` button.
- Changed the MCCC Shield tab so the risky soft-hook checkbox is gone and replaced with a hook-lockdown verification button.

## Validation results

- Python compile: OK
- Offline import smoke test: OK
- `overlay_capabilities`: OK
- `research_audit`: OK
- `code_audit`: OK
- `qa_self_test`: OK in external sandbox with expected runtime warnings
- `final_audit`: OK
- `mccc_soft_hooks_on`: fail-closed, as intended
- `lot51_register_events` before MCCC Shield arm: fail-closed, as intended
- `mccc_guard_on`: fail-closed, as intended
- CAS category status: 117 categories
- Runtime-only patch-sensitive categories: fail closed outside live Sims runtime

## Live-game test checklist

1. Back up the save.
2. Install `TD1 Occult Hybrid Apex` one folder deep under Mods.
3. Build the overlay DLL on Windows from `NativeOverlay/build_msvc_x64.bat`.
4. Run `NativeOverlay/verify_ts4_dx11_imports.py` against `TS4_x64.exe`.
5. Copy the built `d3d11.dll` next to `TS4_x64.exe` only if no other DX proxy conflict exists, or use a chain-loader plan.
6. Launch Sims 4 in DX11.
7. Press F11.
8. Run `Research Audit`, `Code Audit`, `QA Self-Test`, and `Final Audit`.
9. Test MCCC with explicit `MCCC Shield -> Arm Household`, then MCCC Modify in CAS, then `Restore Household`, `Commit Current -> Selected Occult`, and `Scan Selected Occult`.

## Hard limit
No offline tool can prove literal zero problems in every Windows Sims 4 install. This build makes the risky paths explicit, fail-closed, and auditable.
