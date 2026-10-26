# TD1 Occult Hybrid Apex — Developer Toolbox

Use these as challengers/references, not automatic dependencies.

## Upstream / Sims modding

- `https://github.com/L-P-TD1/ts4-occulthybrid` — original TD1 source lineage and build structure.
- `https://www.curseforge.com/sims4/mods/occult-hybrid-unlocker-stabilizer` — distributed release/changelog truth; currently 1.13.7 FIXE.
- `https://github.com/Oops19/TS4-XmlInjector` — Sims tuning/XML injection patterns.
- `https://github.com/stark-studio-labs/sims4-stark-devkit` — current public Sims 4 development-kit reference.

## CAS unlock / package-generation challengers

- `https://www.curseforge.com/sims4/mods/casunlocks` — Crilender CASUnlocks; behavioral reference for keeping CAS categories available. All Rights Reserved: do not copy package content.
- `https://www.curseforge.com/sims4/mods/ultimate-cas-items-unlocker` — Loulicorn Ultimate CAS Items Unlocker; behavioral reference for broad hidden/locked/debug/occult catalog exposure. All Rights Reserved.
- `https://modthesims.info/d/672037` — Szemoka Unlock CAS Items; behavioral reference for using game-native reward unlock semantics rather than only static overrides.
- `https://github.com/sims4toolkit/models` — MIT CAS/package resource models.
- `https://github.com/sims4toolkit/extraction` — MIT game-file indexing/extraction.
- `https://github.com/Llama-Logic/LlamaLogic` — MIT LlamaLogic.Packages reader/writer.
- `https://github.com/PhuVinhAI/ModTS4` — MIT package-authoring/reference workflow with patch-delta precedence.
- `https://github.com/CmarNYC-Tools/TS4SimRipper` and `TS4CASTools` — GPL-3.0 CASP/CAS technical reference; do not copy/link into a differently licensed Apex deliverable without explicit compatible licensing.

## Native overlay / diagnostics

- `https://github.com/ocornut/imgui` — Dear ImGui; recovered V9.5 vendored 1.92.8-era sources.
- `https://github.com/TsudaKageyu/minhook` — narrow Windows hooks if a hook is truly required.
- `https://github.com/microsoft/Detours` — alternative mature Windows instrumentation/hooking reference.
- `https://github.com/GameTechDev/PresentMon` — frame/present telemetry for proving overlay non-regression.
- Windows Performance Recorder / Analyzer (WPR/WPA) — CPU/thread/file activity proof.

## Working rule for Codex

Challenge before reinventing. For every candidate, record: use as-is / adapt / reference only / reject, plus licensing/provenance and the reason. Do not pull in a framework merely because it is newer.


## Authorized MCCC CAS baseline

Project owner states full author permission to use relevant MCCC material.

Current public baseline verified 2026-10-06:
- MC Command Center 2026.5.0 — Sims 4 PC 1.128.90.1030
- https://deaderpool-mccc.com/downloads.html
- https://deaderpool-mccc.com/mccas.html
- https://deaderpool-mccc.com/mcdresser.html
- https://deaderpool-mccc.com/changelogs/mccc2026_4_0.html
- https://deaderpool-mccc.com/changelogs/mccc2026_5_0.html

Use MC CAS + MC Dresser + shared CAS helpers as an authorized implementation baseline for Apex Live CAS Studio. Preserve attribution/provenance; final runtime must not require MCCC.


## Authorized Color Sliders baseline

Project owner states full permission from thepancake1 for relevant Color Sliders material.

Current public baseline:
- Color Sliders v4f
- https://www.patreon.com/thepancake1/posts/color-sliders-157258822
- UI checked/updated for 1.127.41 on 2026-08-26
- Apex target is newer 1.128.90.1030, so diff/port/revalidate before release

Study/port:
- slider-enable UI resources
- eyebrow slider resources
- classlibrarygamedata / cascustomizer changes
- converted texture package architecture
- conversion tooling
- pack/category manifests
- More CAS Columns compatibility
- CC compatibility and current slider-state serialization

Final Apex Color Studio must work without the original mod installed.

## October 8 — CAS ownership challengers rechecked

- [Sims4CommunityLibrary outfit utilities](https://github.com/DeviantGameMods/Sims4CommunityLibrary/blob/main/Scripts/sims4communitylib/utils/cas/common_outfit_utils.py): reference only for category/index, BodyType/part arrays and native dirty-outfit semantics. Its normal outfit helpers do not establish a complete several-owner hybrid CAS commit or save/reload certificate. No library runtime dependency or copied implementation was added in this pass.
- [Oops19 TS4-EditInCAS](https://github.com/Oops19/TS4-EditInCAS): reference only for its explicit transfer/filter limitations. Its own README excludes occult support and says the transfer cannot distinguish randomly replaced values from intended edits. It does not satisfy Apex's hybrid-preservation requirement. Apex's schema-2 receiver therefore retains originals and raw returned owners and requires explicit decisions for every changed form; it must not classify every secondary-form change as corruption.

These are source references, not proof that Apex's runtime acceptance gate is complete. Continue the exact-game CAS, switching and restart checks in the canonical master.
