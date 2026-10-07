# TD1 Occult Hybrid Apex

> A safety-first, highly usable Sims 4 hybrid-occult control suite with an **F11 in-game overlay**, explicit CAS recovery workflows, saved occult forms, per-category appearance tools, drift detection, diagnostics, and a game-thread-only mutation backend.

**Recovered project checkpoint:** V9.5 Final Accounting / Runtime Safe — May 29, 2026  
**Recovered source archive SHA-256:** `5bae3bfdb0f7aef8fde94f3e1058d74bdc80fb79fdcbd33c12fed78beae83249`  
**Current upstream compatibility target:** Occult Hybrid Unlocker & Stabilizer **1.13.7 (FIXE)** — May 16, 2026

TD1 Occult Hybrid Apex is an independent continuation/research project. It preserves attribution to TD1/TwelfthDoctor1, LordPercivalXII, IcedCream and other upstream contributors where their work or behavior is referenced. It is not presented as an official upstream release.

## Why Apex exists

The upstream mod does the hard, important work of making hybrid occults viable. Apex keeps that compatibility goal and adds a much more observable, recoverable and user-friendly control layer around it:

- **F11 Dear ImGui control center** in the running game.
- **Saved Forms** with labels, search, apply and reuse.
- **CAS History Studio** — Photoshop-style live CAS history with semantic diffs, Undo/Redo, jump-to-state, branching history, named checkpoints, category revert and hybrid-aware cherry-pick.
- **Apex CAS Unlock Core** — a fully standalone unlocker: keeps compatible CAS categories available, exposes optional hidden/locked/debug/occult items, understands hybrid forms and installed packs, regenerates against current game resources after patches, and requires no third-party CAS unlocker.
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

Apex CAS Unlock Core and CAS History Studio are designed as part of that fix strategy. **Apex does not depend on Crilender, Loulicorn, Szemoka, or another CAS unlocker; those are research references only.** the same canonical appearance journal/diff layer powers live CAS history, MCCC Shield, Post-CAS Commit, Drift Guard and Saved Forms so the user can see exactly what changed and safely restore earlier states. See [`docs/CAS_HISTORY_STUDIO.md`](docs/CAS_HISTORY_STUDIO.md) and [`docs/APEX_CAS_UNLOCK_CORE.md`](docs/APEX_CAS_UNLOCK_CORE.md).

## Architecture

```text
                 The Sims 4 / live Sim state
                           ^
                           | game-thread queue only
                           |
          +----------------+----------------+
          |                                 |
  Python script mod                  upstream package/tuning
  TD1_OccultHybridApex               compatibility layer
          ^
          | localhost commands on 127.0.0.1:8017
          |
  +-------+-------------------------------+
  |                                       |
F11 DX11 Dear ImGui overlay          browser fallback UI
(render/input only)                  (local only)
```

**Critical invariant:** the native render thread never edits Sims data directly. It renders UI, captures input/reference shots and sends commands. Gameplay mutation stays in the Python/Sims command queue.

## Current upstream 1.13.7 parity target

The latest distributed upstream release verified for this handoff is **1.13.7 (FIXE)**. Apex must carry forward these upstream fixes before claiming parity:

1. Missing STBL fix.
2. TMex PhoneSearch compatibility: PlantSim interactions accessible from the Pie Menu rather than the conflicting path.
3. `ClassInstanceTuningInjections` coverage for werewolf, fairy and fairy bloodline traits.
4. Debug commands equivalent to:
   - `td1hybrid.view_sim_cached_occults`
   - `td1hybrid.view_global_cached_occults`
   - `td1hybrid.view_cas_cached_sims`

See [`docs/UPSTREAM_1.13.7_DELTA.md`](docs/UPSTREAM_1.13.7_DELTA.md) and the full Codex execution contract in [`docs/CODEX_MASTER_EXECUTION.md`](docs/CODEX_MASTER_EXECUTION.md).

## Install / use the recovered V9.5 package

1. Back up the save before testing hybrid-occult mutations.
2. Place the folder `TD1 Occult Hybrid Apex` one folder deep under `Documents\Electronic Arts\The Sims 4\Mods`.
3. Enable Custom Content/Mods and Script Mods, then restart the game.
4. The script/backend can run without the native overlay.
5. To use the F11 overlay, build `NativeOverlay` on Windows x64 and follow `NativeOverlay/README_BUILD_AND_INSTALL.txt`.
6. Run `NativeOverlay/verify_ts4_dx11_imports.py` against the current `TS4_x64.exe` before installing the proxy.

### Recommended safe CAS / MCCC flow

```text
F11 -> MCCC Shield -> Arm Household
-> use MCCC Modify in CAS / edit the Sim
-> return to Live Mode
-> Restore Household
-> Commit Current -> Selected Occult
-> Scan Selected Occult
```

The V9.5 design intentionally refuses the old soft/private MCCC hook path.

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

The recovered V9.5 source passed its recorded offline Python/static/audit checks, but **live Sims 4 runtime proof is still required** for the current game build, the native overlay, MCCC/CAS flows, new upstream 1.13.7 parity work, all supported occults and release packaging. The repository deliberately keeps these gates open instead of calling source presence “done.”

## Start here for Codex

1. Read [`docs/CODEX_MASTER_EXECUTION.md`](docs/CODEX_MASTER_EXECUTION.md).
2. Read [`docs/UPSTREAM_1.13.7_DELTA.md`](docs/UPSTREAM_1.13.7_DELTA.md).
3. Read [`docs/USER_REPORTED_REGRESSIONS.md`](docs/USER_REPORTED_REGRESSIONS.md).
4. Read [`docs/CAS_HISTORY_STUDIO.md`](docs/CAS_HISTORY_STUDIO.md).
5. Read [`docs/APEX_CAS_UNLOCK_CORE.md`](docs/APEX_CAS_UNLOCK_CORE.md).
6. Read [`docs/CAS_UNLOCKER_REFERENCE_MATRIX.md`](docs/CAS_UNLOCKER_REFERENCE_MATRIX.md).
7. Read [`docs/DEVELOPER_TOOLBOX.md`](docs/DEVELOPER_TOOLBOX.md).
8. Preserve the V9.5 safety invariants and continue from the earliest ready task ID.
9. Do not replace the project with a fresh scaffold.

## Provenance

See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Upstream behavior/release references are tracked there and in the engineering docs so Codex can distinguish **Apex-owned code**, **vendored dependencies**, **retained upstream artifacts**, and **research references**.
