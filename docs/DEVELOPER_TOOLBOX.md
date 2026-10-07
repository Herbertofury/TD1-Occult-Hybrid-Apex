# TD1 Occult Hybrid Apex — Developer Toolbox

Use these as challengers/references, not automatic dependencies.

## Upstream / Sims modding

- `https://github.com/L-P-TD1/ts4-occulthybrid` — original TD1 source lineage and build structure.
- `https://www.curseforge.com/sims4/mods/occult-hybrid-unlocker-stabilizer` — distributed release/changelog truth; currently 1.13.7 FIXE.
- `https://github.com/Oops19/TS4-XmlInjector` — Sims tuning/XML injection patterns.
- `https://github.com/stark-studio-labs/sims4-stark-devkit` — current public Sims 4 development-kit reference.

## Native overlay / diagnostics

- `https://github.com/ocornut/imgui` — Dear ImGui; recovered V9.5 vendored 1.92.8-era sources.
- `https://github.com/TsudaKageyu/minhook` — narrow Windows hooks if a hook is truly required.
- `https://github.com/microsoft/Detours` — alternative mature Windows instrumentation/hooking reference.
- `https://github.com/GameTechDev/PresentMon` — frame/present telemetry for proving overlay non-regression.
- Windows Performance Recorder / Analyzer (WPR/WPA) — CPU/thread/file activity proof.

## Working rule for Codex

Challenge before reinventing. For every candidate, record: use as-is / adapt / reference only / reject, plus licensing/provenance and the reason. Do not pull in a framework merely because it is newer.
