# Apex Occult Hybrid

> A safety-first, highly usable Sims 4 hybrid-occult control suite with an **F11 in-game overlay**, explicit CAS recovery workflows, saved occult forms, per-category appearance tools, drift detection, diagnostics, and a game-thread-only mutation backend.

**Recovered project checkpoint:** V9.5 Final Accounting / Runtime Safe — May 29, 2026  
**Recovered source archive SHA-256:** `5bae3bfdb0f7aef8fde94f3e1058d74bdc80fb79fdcbd33c12fed78beae83249`  
**Historical behavioral reference:** Occult Hybrid Unlocker & Stabilizer **1.13.7 (FIXE)** — May 16, 2026 — **not a runtime dependency**

Apex Occult Hybrid is a standalone first-party hybrid-occult project recovered from earlier Apex/TD1-oriented work. The project owner has explicitly stated they have full permission from the relevant TD1/LordPercival hybrid, Crilender CASUnlocks, MCCC, and thepancake1 authors to use the relevant baseline material in Apex. Their newest working packages are therefore the concrete starting code/resource baselines to import, inventory, port and improve—not merely inspiration—while the finished release converges on Apex-owned artifacts and preserves attribution/provenance.

## Why Apex exists

Apex now owns the full hybrid stack itself, but development deliberately starts from the current authorized working TD1/LordPercival hybrid, Crilender CASUnlocks, MCCC MC CAS/MC Dresser, and thepancake1 Color Sliders baselines. Codex should preserve their useful working behavior first, then improve/replace weak pieces and converge them into Apex-owned artifacts:

- **Apex Occult Hybrid Core** — first-party `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script`; no TD1/IcedCream/LordPercival hybrid runtime dependency.
- **F11 Dear ImGui control center** in the running game.
- **Apex Live CAS Studio** — a standalone MCCC CAS/Dresser superset: edit CAS-grade appearance data from Live Mode, copy whole outfits/all outfits/appearance between Sims, use Tray/preset sources, and undo/redo everything without requiring MCCC.
- **Apex Color Studio** — first-party full Hue/Saturation/Brightness/Opacity editing built upward from thepancake1 Color Sliders, with exact custom-color preservation through every part/outfit/form/Sim copy and no runtime dependency on the original mod.
- **Saved Forms** with labels, search, apply and reuse.
- **CAS History Studio** — Photoshop-style live CAS history with semantic diffs, Undo/Redo, jump-to-state, branching history, named checkpoints, category revert and hybrid-aware cherry-pick.
- **Apex CAS Unlock Core** — a fully standalone unlocker shipping its own first-party `ApexCASUnlocks.package`: keeps compatible CAS categories available, exposes optional hidden/locked/debug/occult items, understands hybrid forms and installed packs, regenerates against current game resources after patches, and requires no third-party CAS unlocker.
- **Drift Guard** to detect and repair occult-form appearance drift without constant scanning.
- **Post-CAS Commit** so visible edits can be deliberately committed into the selected occult form.
- **CAS Categories** for scoped copy/paste/apply-all-forms instead of blunt full-appearance replacement.
- **MCCC Shield** with explicit arm/restore flow; no private MCCC monkey-patching.
- **Reference Shots** for face/body/full-frame visual baselines.
- **Browser fallback/control panel** on `127.0.0.1:8017`.
- **Structured diagnostics and final audits** with fail-closed behavior on patch-sensitive paths.
- **No hidden continuous Sim scanning by default.** Hidden overlay mode performs no HTTP polling.

## Problems Apex exists to eliminate

These are known historical failure modes and are **release blockers**, not “edge cases”:

- CAS or MC Command Center edits appear saved but later revert because the intended stored occult form never received them.
- CAS can damage or lose secondary hybrid forms, leaving only the entry/current form usable.
- Hybrids can become stuck in one form or snap back after switching.
- Werewolf hair/headwear and other werewolf CAS parts can disappear or corrupt when changing categories/outfits or editing through CAS.
- Entering CAS while already in werewolf form can fail to preserve the edits.
- Skin details, makeup, hair, tattoos, accessories, clothing or other CAS data can bleed between forms or vanish.
- Stale recovery/CAS cache state can overwrite a newer good edit.
- Broad repair/copy operations can damage unrelated appearance data or occult state.

The canonical reproduction and acceptance ledger is [`docs/USER_REPORTED_REGRESSIONS.md`](docs/USER_REPORTED_REGRESSIONS.md). Apex is not complete while any R001–R010 failure remains reproducible.

Apex Occult Hybrid Core, CAS Unlock Core and CAS History Studio are designed as one integrated fix strategy. **Apex does not depend on TD1/IcedCream/LordPercival for hybrid runtime behavior, or Crilender/Loulicorn/Szemoka for CAS unlocking; those are research references only.** The same canonical state/journal/diff layers power form ownership, live CAS history, MCCC Shield, Post-CAS Commit, Drift Guard and Saved Forms. See [`docs/APEX_OCCULT_HYBRID_CORE.md`](docs/APEX_OCCULT_HYBRID_CORE.md), [`docs/CAS_HISTORY_STUDIO.md`](docs/CAS_HISTORY_STUDIO.md), and [`docs/APEX_CAS_UNLOCK_CORE.md`](docs/APEX_CAS_UNLOCK_CORE.md).

## Architecture

```text
                    The Sims 4 / save state
                              ^
                              | validated game-thread actions
                              |
                   ApexOccultHybrid.ts4script
                    /        |          \
                   /         |           \
      hybrid state/form   CAS journal   unlock policy
              |              |              |
              +------- Apex domain ---------+
                          ^
                          |
                F11 / browser / console
                          |
                existing native overlay
                  (render/input only)

   ApexOccultHybrid.package        ApexCASUnlocks.package
   hybrid tuning/interactions      CAS/category/catalog layer
             \                         /
              \---- same policy/build ----/
```

**Critical invariant:** the native render thread never edits Sims data directly. Gameplay mutation stays in the Apex Python/Sims game-thread domain.

### Standalone release target

The normal release is built around Apex-owned artifacts:

- `ApexOccultHybrid.package`
- `ApexOccultHybrid.ts4script`
- `ApexCASUnlocks.package`
- optional Apex native F11 overlay component

No TD1/TwelfthDoctor1/IcedCream/LordPercival hybrid file is required. No third-party CAS unlocker is required. MCCC/Lot51/XML Injector may be detected for optional interoperability but cannot be required for core hybrid/unlock behavior.

## Historical 1.13.7 behavioral reference

The latest verified historical reference release is **1.13.7 (FIXE)**. Apex must independently provide equivalent-or-better behavior for the useful fixes below before claiming the reference floor is covered:

1. Missing STBL fix.
2. TMex PhoneSearch compatibility: PlantSim interactions accessible from the Pie Menu rather than the conflicting path.
3. `ClassInstanceTuningInjections` coverage for werewolf, fairy and fairy bloodline traits.
4. Debug commands equivalent to:
   - `td1hybrid.view_sim_cached_occults`
   - `td1hybrid.view_global_cached_occults`
   - `td1hybrid.view_cas_cached_sims`

See [`docs/UPSTREAM_1.13.7_DELTA.md`](docs/UPSTREAM_1.13.7_DELTA.md), [`docs/APEX_OCCULT_HYBRID_CORE.md`](docs/APEX_OCCULT_HYBRID_CORE.md), and the full Codex execution contract in [`docs/CODEX_MASTER_EXECUTION.md`](docs/CODEX_MASTER_EXECUTION.md).

## Current recovery vs production target

The recovered V9.5 archive is historical implementation/research input. **It is not the desired production dependency layout.** Codex must converge the project onto the first-party Apex package/script artifacts above, then test those exact hashed release artifacts on a clean Mods profile. Back up saves during development/testing.

### Recommended safe CAS / MCCC flow

```text
F11 -> MCCC Shield -> Arm Household
-> use MCCC Modify in CAS / edit the Sim
-> return to Live Mode
-> Restore Household
-> Commit Current -> Selected Occult
-> Scan Selected Occult
```

The Apex design intentionally refuses private MCCC monkey-patching. MCCC integration is optional and must degrade to native Apex workflows when MCCC is absent.

## Performance contract

- Hidden F11 overlay: **no HTTP polling**.
- Idle Sim scans: **off by default**.
- Auto repair: **off by default**.
- Drift Guard: fire-on-click / event-bounded, not a high-frequency timer.
- Expensive work: user-triggered or event-triggered.
- No quality/content reduction is an acceptable performance optimization.

## Repository map

- `Source/td1_occult_hybrid_apex.py` — Sims/Python backend source.
- `NativeOverlay/` — Windows x64 Dear ImGui/DX11 overlay source kit.
- `Native/` — recovered native bridge source.
- `Reports/` — historical validation and research from the recovered build lineage.
- `docs/` — current engineering/Codex handoff.
- `wiki/` — canonical Markdown mirror for the live GitHub Wiki.
- `RECOVERED_BINARY_ARTIFACTS.md` — exact binary-file identities retained from V9.5.

## Current truth, not marketing

The recovered V9.5 source passed recorded offline Python/static/audit checks, but **live Sims 4 runtime proof is still required** for the current game build, the first-party Apex Occult Hybrid package/script pair, CAS Unlock package, native overlay, CAS/MCCC interoperability, all supported occults and release packaging. The repository deliberately keeps these gates open instead of calling source presence “done.”

## Start here for Codex

**Single-file handoff:** [`docs/CODEX_APEX_COMPLETE_EXECUTION_HANDOFF.md`](docs/CODEX_APEX_COMPLETE_EXECUTION_HANDOFF.md)

1. Read [`docs/AUTHORIZED_BASELINE_STRATEGY.md`](docs/AUTHORIZED_BASELINE_STRATEGY.md).
2. Read [`docs/CODEX_MASTER_EXECUTION.md`](docs/CODEX_MASTER_EXECUTION.md).
3. Read [`docs/APEX_OCCULT_HYBRID_CORE.md`](docs/APEX_OCCULT_HYBRID_CORE.md).
4. Read [`docs/UPSTREAM_1.13.7_DELTA.md`](docs/UPSTREAM_1.13.7_DELTA.md).
5. Read [`docs/USER_REPORTED_REGRESSIONS.md`](docs/USER_REPORTED_REGRESSIONS.md).
6. Read [`docs/CAS_HISTORY_STUDIO.md`](docs/CAS_HISTORY_STUDIO.md).
7. Read [`docs/APEX_CAS_UNLOCK_CORE.md`](docs/APEX_CAS_UNLOCK_CORE.md).
8. Read [`docs/CAS_UNLOCKER_REFERENCE_MATRIX.md`](docs/CAS_UNLOCKER_REFERENCE_MATRIX.md).
9. Read [`docs/APEX_LIVE_CAS_STUDIO.md`](docs/APEX_LIVE_CAS_STUDIO.md).
10. Read [`docs/MCCC_CAS_BASELINE_MATRIX.md`](docs/MCCC_CAS_BASELINE_MATRIX.md).
11. Read [`docs/APEX_COLOR_STUDIO.md`](docs/APEX_COLOR_STUDIO.md).
12. Read [`docs/PANCAKE_COLOR_SLIDER_BASELINE.md`](docs/PANCAKE_COLOR_SLIDER_BASELINE.md).
13. Read [`docs/DEVELOPER_TOOLBOX.md`](docs/DEVELOPER_TOOLBOX.md).
14. Preserve the V9.5 safety invariants and continue from the earliest ready task ID.
15. Do not replace the project with a fresh scaffold.

## Provenance

See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Upstream behavior/release references are tracked there and in the engineering docs so Codex can distinguish **Apex-owned code**, **vendored dependencies**, **retained upstream artifacts**, and **research references**.
