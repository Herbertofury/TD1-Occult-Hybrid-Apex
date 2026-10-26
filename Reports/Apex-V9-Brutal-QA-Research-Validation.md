# TD1 Occult Hybrid Apex V9 - Brutal QA / Research / Validation

Build: 2026.05.28-v9-brutal-qa-conflict-safe

## Research conclusions applied

- Sims 4 script mods are Python-based `.ts4script` archives and Sims can load packaged `.py` source from a renamed zip archive.
- Script mods must remain no more than one folder under `Mods`.
- Occult forms use separate occult `sim_info` records. Appearance edits to the visible/current form do not automatically sync back into the matching occult form record, so Apex keeps explicit commit/snapshot/restore flows.
- The CAS BodyType table is based on the Sims 4 Modders Reference values 0-112, with runtime-resolved guards for later categories.
- FULL_BODY cannot coexist with UPPER_BODY/LOWER_BODY. V9 patches category paste so it removes conflicting outfit slots when applying those categories.
- MCCC compatibility is implemented through snapshots/restore, not by patching MCCC internals. MCCC itself documents `mc_cmd_center` as required, with `mc_cas`, `mc_dresser`, and `mc_occult` covering the relevant CAS/dresser/occult areas.
- Lot51 Core is optional. If present, event hooks are preferred to extra injection points. XML Injector remains optional because Apex is already a Python/backend/native-overlay mod.
- The ImGui overlay follows Dear ImGui's Win32 + DirectX 11 backend pattern and only talks to the localhost Python backend; gameplay mutation remains on the Sims/Python queue.

## V9 code changes

- Added `qa_self_test`, `preflight`, and `compatibility_preflight` read-only commands.
- Added F11 overlay `QA Self-Test` button.
- Added V9 light QA data to status payloads.
- Added conflict-safe CAS category paste for FULL_BODY/UPPER_BODY/LOWER_BODY.
- Fixed a screenshot error-path native-overlay leak if the BMP file cannot be opened.
- Updated overlay title/build markers to V9.

## Validation performed in this sandbox

- Final zip integrity test.
- Repacked `.ts4script` integrity test.
- Python syntax parse/compile under host Python.
- Python AST parse.
- Source-level CAS table audit: no duplicate keys, no duplicate fallback values, values 0-112 are contiguous, critical rows present.
- C++ source brace/comment/string balance sanity check.
- Overlay source contains QA Self-Test button.
- Native helper DLL remains PE32+ x64.
- Supplied game Bin contains `python37_x64.dll`, `_socket_x64.pyd`, `_ctypes_x64.pyd`, `select_x64.pyd`, `generated.zip`, and `TS4_x64.exe`.

## Known honest limitation

This Linux sandbox cannot launch The Sims 4, execute EA's embedded Python runtime, or compile/run the Windows DirectX 11 proxy DLL. V9 therefore adds an in-game `QA Self-Test` that must be run from the F11 overlay after loading a household. The mod is designed to fail closed if required runtime APIs are unavailable.
