# Apex V10 Modders Reference / VS Code / S4S Audit

Date: 2026-05-29

## Sources Read

- The Sims 4 Modders Reference tutorials clone: `Llama-Logic/TS4-Modders-Reference`, commit `f9cd931349827d747773d110d2461816a66b3fc7`, dated `2026-05-12`.
- Tutorial files read: 34 `.md` / `.mdx` pages under `src/content/docs/tutorials`.
- Reference pages used for the extension parser:
  - DBPF format
  - STBL format
  - Resource Type Index
- Existing VS Code project reviewed: `sims4toolkit/s4tk-vscode`, commit `377bb39ca76b637d6d534a7532d7a0c68a4c9ff9`, dated `2024-03-11`.
- Installed Sims 4 Studio inspected read-only:
  - `C:\Program Files (x86)\Sims 4 Studio\S4Studio.exe`
  - Version `3.2.6.2`
  - Runtime: `.NET 6` WPF app.

## Tutorial Coverage

| Tutorial | Audit Result |
|---|---|
| Comparing Files with WinMerge | Confirms our patch workflow should keep old/new files comparable. V9.6 changes were appended and documented instead of silently rewriting history. |
| Creating a Custom Pie Menu | Relevant to future in-game command injection. Current overlay/backend does not depend on pie-menu injection, so no correction needed. |
| Creating an injector | Confirms XML/tuning injection should be explicit and scoped. Apex keeps XML Injector optional and does not require it for the overlay/backend. |
| Creating an XML Compare File with WinMerge | Supports our report-driven patch audit approach. No direct code correction needed. |
| Custom Maps | Not applicable to the current occult hybrid script/overlay, except it reinforces package testing in-game. |
| Fixing CC For New Occults | Relevant to new occult/CAS category drift. V9.6 BodyType audit is aligned with this principle: verify new categories from live game data before mutating. |
| Links to Off-Site Tutorials | Reviewed as index material. No direct TD1 changes required. |
| Modding on Linux | Confirms Wine/S4S workflow assumptions; not a blocker because this build is Windows-native and uses MSVC/DX11. |
| Modifying Sim Appearances | Most important tutorial for this mod. Apex follows the script-method model: parses `Outfits_pb2`, edits parallel outfit lists, handles growth/genetic data separately, and treats occult forms as separate SimInfo surfaces. |
| Restricting a File to a Pack Using Group ID | Relevant to `.package` group IDs. Current package scan found pack/group-scoped resources in the big packages and generic `80000000` groups in optional interaction packages; no forced group-ID rewrite should be done blindly. |
| Scumbumbo XML Extractor | Confirms extracted XML/TDESC comparison workflow. No direct runtime dependency. |
| Scumbumbo XML File Finder | Confirms reference lookup workflow. Useful for future tuning edits. |
| MIY Aspirations Series Index | Index page reviewed; no direct occult/CAS correction. |
| MIY Aspirations Part 1 | Iteration/objective tuning concepts reviewed; no direct correction. |
| MIY Aspirations Part 2 | STBL/string workflow reviewed; extension now decodes STBL resources when uncompressed/zlib. |
| MIY Aspirations Part 3 | Objective tuning reviewed; no direct correction. |
| MIY Aspirations Part 4 | String token handling reviewed; no direct correction. |
| MIY Aspirations Part 5 | String formatting reviewed; no direct correction. |
| MIY Aspirations Part 6 | Modding basics, instance IDs, SimData, and TDESC workflow reviewed; supports extension package/SimData inspection goals. |
| MIY Aspirations Part 7 | Aspiration structure reviewed; no direct correction. |
| MIY Aspirations Part 8 | Aspiration track tuning reviewed; no direct correction. |
| MIY Aspirations Part 9 | Icons/images reviewed; no direct correction. |
| MIY Aspirations Part 10 | Aspiration tuning and SimData reviewed; reinforces paired tuning/SimData inspection. |
| MIY Aspirations Part 11 | Snippet tuning reviewed; no direct correction. |
| MIY Aspirations Part 12 | Objective SimData reviewed; no direct correction. |
| MIY Aspirations Part 13 | Objective tuning types reviewed; no direct correction. |
| MIY Aspirations Part 14 | Trait/buff/situation/mood objective patterns reviewed; no direct correction. |
| MIY Aspirations Part 15 | Relation/object/money/photo/perk objective patterns reviewed; no direct correction. |
| MIY Aspirations Part 16 | Additional objective tests reviewed; no direct correction. |
| MIY Aspirations Part 17 | Reward tuning reviewed; no direct correction. |
| MIY Aspirations Part 18 | Reward type patterns reviewed; no direct correction. |
| MIY Aspirations Part 19 | Cross-pack content reviewed; reinforces pack-aware group and dependency checks. |
| MIY Aspirations Part 20 | Testing/wrap-up reviewed; reinforces copied-save testing. |

## Mod Correctness Verdict

The current Apex architecture remains correct against the tutorial corpus:

- Gameplay writes stay in Sims Python/game-thread command paths, not in the DX11 overlay.
- CAS category edits are scoped to a specific BodyType and preserve parallel part/body/color/object/layer rows.
- V9.6 fixed the most important current drift found during research: live Sims 4 `1.124.63.1020` BodyTypes are `BIRTHMARKOCCULT=112`, `TATTOO_HEAD=113`, `WINGS=114`, `HEADDECO=115`, `SKINSPECULARITY=116`, `BASE_LAYER=117`, `UNUSED=118`.
- The old `TATTOO_HEAD_WINGS` concept is intentionally not aliased because the live runtime splits head tattoos and wings.
- The mod still needs in-game copied-save testing for mutating commands; offline validation cannot prove save/runtime behavior.

## Package Scan

Read-only DBPF index scan of current packages:

| Package | Resources | Groups | Types |
|---|---:|---|---|
| `[TD1-IC] Hybrid - Plantsim Interactions.package` | 5 | `80000000` | `0C772E27`, `7DF2169C`, `E882D22F` |
| `[TD1-IC] Hybrid - Plantsim No Vampire Thirst.package` | 1 | `80000000` | `7DF2169C` |
| `[TD1-IC] Hybrid - Plantsim Permanent.package` | 2 | `80000000` | `7DF2169C` |
| `[TD1-IC] Hybrid - Servo Interactions.package` | 5 | `80000000` | `0C772E27`, `7DF2169C`, `E882D22F` |
| `[TD1-IC] Hybrid - Servo No Vampire Thirst.package` | 1 | `80000000` | `7DF2169C` |
| `[TD1-IC] OccultHybrid.package` | 120 | `00000000`, `00000011`, `0000001E`, `0000003C`, `0017E8F6`, `005FDD0C`, `009BC58E`, `00E9D967`, `80000000` | `00B2D882`, `03B33DDF`, `03E9D964`, `0C772E27`, `220557DA`, `339BC5BD`, `545AC67A`, `6017E896`, `7DF2169C`, `CB5FDDC7`, `E882D22F` |
| `[TwelfthDoctor1] OccultTurnActionsUnlocker.package` | 29 | `00000000`, `00000011`, `00000015`, `0000001C`, `0000001D`, `0000003C`, `0000003F`, `005FDD0C`, `80000000` | `545AC67A`, `7DF2169C`, `CB5FDDC7`, `E882D22F` |

No package was modified.

## GitHub / Existing Tooling Findings

- `sims4toolkit/s4tk-vscode` already exists and is MIT-licensed.
- It provides S4TK project workflows, package viewing, STBL editing, FNV hashing, XML reference helpers, and build commands.
- It does not directly solve the TD1 needs that triggered this pass:
  - `.ts4script` archive inspection/security/readability.
  - TD1 Apex validation commands.
  - Installed Sims 4 Studio bridge commands.
  - Live BodyType audit workflow.

## New VS Code Extension

Created and installed:

```text
VSCode\td1-sims4-apex-tools\td1-sims4-apex-tools-0.1.0.vsix
```

Extension features:

- Custom read-only editor for `.package`.
- Custom read-only editor for `.ts4script`.
- DBPF header/index/resource table.
- Resource key copy.
- Resource virtual document previews:
  - STBL -> JSON
  - XML-like resources -> XML text
  - JSON-like resources -> JSON text
  - Other resources -> hex preview
- TS4Script ZIP entry table.
- TS4Script entry preview/extract.
- Suspicious `.ts4script` entry warnings for `.pyc`, `__pycache__`, executable/script payloads, and path traversal.
- Sims 4 Studio bridge panel:
  - Launch S4 Studio.
  - Open active package in S4 Studio.
  - Run TD1 Apex workspace validation.
- Workspace validation:
  - Python source compile without writing `__pycache__`.
  - `TD1_OccultHybridApex.ts4script` archive parse.
  - Embedded/source SHA256 comparison.
  - Optional DX11 verifier against configured `Game\Bin\TS4_x64.exe`.

Build/installation results:

```text
npm install: OK
npm run compile: OK
npx @vscode/vsce package --allow-missing-repository --no-dependencies: OK
code --install-extension VSCode\td1-sims4-apex-tools\td1-sims4-apex-tools-0.1.0.vsix --force: OK
```

## S4 Studio Integration Decision

Sims 4 Studio `3.2.6.2` is a `.NET 6` WPF desktop app. No supported command-line editing API or VS Code-embeddable interface was found in the installed files. The safe integration is therefore:

- Launch S4S externally from VS Code.
- Pass a `.package` path when opening from context menu.
- Keep DBPF/STBL/TS4Script inspection inside VS Code.
- Do not copy, redistribute, reflectively load, or depend on private S4S assemblies.

Future improvement path:

1. Add optional S4TK dependency for richer XML/SimData decoding.
2. Add a package resource export command with deterministic output paths.
3. Add a guarded package writer only for STBL/XML resources after checksum/backups are implemented.
4. Add a local TDESC/doc search panel fed by the Modders Reference clone.
