# Getting Started

## What Apex is

Apex is a recovery-first hybrid-occult control suite built around an F11 in-game control center. The Sims/Python backend remains the authority for game-state mutation; the native overlay is a presentation/input layer.

## Safe test setup

1. Back up the Sims 4 `saves` folder.
2. Use a dedicated test save/household first.
3. Install the recovered Apex script/package set only after removing duplicate obsolete hybrid files.
4. Enable Script Mods and Custom Content/Mods.
5. For the native overlay, run the DX11 preflight before copying a proxy DLL beside `TS4_x64.exe`.
6. Start with auto repair disabled.

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
