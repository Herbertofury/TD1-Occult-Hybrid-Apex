# TD1 Apex VS Code Insiders Studio/Warehouse Validation

Date: 2026-05-29 13:12:40 -06:00

## Result

- Built VS Code extension: `VSCode/td1-sims4-apex-tools/td1-sims4-apex-tools-0.2.0.vsix`
- Installed target: VS Code Insiders via `code-insiders --install-extension .\td1-sims4-apex-tools-0.2.0.vsix --force`
- Verified installed extension: `td1-local.td1-sims4-apex-tools@0.2.0`
- VSIX SHA256: `2B68106C225D2285531AE839DFEB3CE274ABACDF329FCAB5090CBEC5267D2C64`
- VSIX size: 20,295 bytes

## What Changed

- Upgraded `.package` and `.ts4script` custom editors to dark Studio/Warehouse webview layouts inspired by Sims 4 Studio.
- Added S4S-like chrome, File/Settings/Tools/Content Management/Help menu strip, Studio and Warehouse tabs, swatches, package preview stage, warehouse filters, selectable rows, and resource actions.
- Kept the editor read-only for DBPF/ZIP safety while preserving direct virtual previews for STBL JSON, XML/text, Python, and hex resources.
- Expanded package resource type labels using The Sims 4 Modders Reference resource type index.
- Added a Content Security Policy to the webviews and cleaned VSIX contents so the package ships runtime files only.

## Research Decisions

- VS Code custom editors are the correct API for binary `.package` files and readonly custom document models.
- VS Code webviews are the supported way to render rich editor UI and message actions back to the extension host.
- Existing public work, especially `sims4toolkit/s4tk-vscode`, confirms that a Sims 4 package viewer in VS Code is practical, but this extension remains focused on TD1 validation, TS4Script inspection, S4S companion launching, and a Sims 4 Studio-like workflow.
- Sims 4 Studio is a .NET/WPF desktop app. This extension launches it as an external companion instead of loading private assemblies into VS Code.

## Sources Checked

- https://code.visualstudio.com/api/extension-guides/custom-editors
- https://code.visualstudio.com/api/extension-guides/webview
- https://github.com/sims4toolkit/s4tk-vscode
- https://thesims4moddersreference.org/tutorials/
- https://thesims4moddersreference.org/reference/dbpf-format/
- https://thesims4moddersreference.org/reference/stbl-format/
- https://thesims4moddersreference.org/reference/resource-types/
- https://thesims4moddersreference.org/reference/s4s-top-menus/

## Verification

- `npm run compile`: passed
- `npx @vscode/vsce package --allow-missing-repository --no-dependencies`: passed
- `code-insiders --list-extensions --show-versions`: returned `td1-local.td1-sims4-apex-tools@0.2.0`
