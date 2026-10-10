# Getting Started

## What Apex is

Apex is a recovery-first hybrid-occult control suite built around an F11 in-game control center. The Sims/Python backend remains the authority for game-state mutation; the native overlay is a presentation/input layer.

## Safe test setup

1. Back up the Sims 4 `saves` folder.
2. Use a dedicated test save/household first.
3. Install the current matching Apex candidate package/script set in the test profile after checking duplicate hybrid owners.
4. Enable Script Mods and Custom Content/Mods.
5. Keep the matching native DLL/config/manifest under `Mods/Apex/Native`. Use DX11; after household loading, press F11. `apex.overlay.start/status` provide diagnostics. No Game/Bin copies are needed for this candidate.
6. Start with auto repair disabled.

The owner handles live tests with the single retained disposable profile. The
original `The Sims 4 DO NOT FUCKING TOUCH!!!` folder is read/copy-only and only
the owner may rename it. See [current installation steps](../docs/CANDIDATE_INSTALL_AND_TEST.md)
and [verification/remaining work](../Reports/SIDECAR_AND_COLOR_2026-10-07.md).

## Recommended CAS / MCCC workflow

```text
F11
 -> MCCC Shield: Arm Household
 -> edit in CAS / MCCC
 -> return to Live Mode
 -> Restore Household
 -> Commit Current -> Selected Occult
 -> Scan Selected Occult
```

## Normal F11 goals

- See the selected Sim and every detected occult.
- Toggle supported occults deliberately.
- Switch forms.
- Save/restore named forms.
- Copy/paste only the intended CAS categories.
- See drift before repairing it.
- Export meaningful diagnostics instead of guessing.

Anything destructive or ambiguous should explain the consequence before execution.
