# Troubleshooting

## F11 does nothing

- Confirm the game is running the intended DX11 executable/path.
- Run `NativeOverlay/verify_ts4_dx11_imports.py`.
- Confirm the proxy was built x64 and placed next to the correct `TS4_x64.exe`.
- Remove the proxy DLL to return to a clean game launch if startup fails.

## Overlay opens but occult controls do not update

Treat this as a backend/queue/state issue, not a reason to mutate game data from the render thread. Check the local API/backend log and selected-Sim diagnostics.

## CAS edits reverted or forms drifted

Do not immediately “repair all.” Inspect the selected occult/category drift, check MCCC Shield/recovery snapshot state, and repair the narrowest intended scope.

## Wrong occult data

Per-Sim occult state is save-backed. Cache diagnostics help explain state but deleting a mod settings/cache file is not equivalent to removing an occult from a Sim. Back up the save before corrective mutation.
