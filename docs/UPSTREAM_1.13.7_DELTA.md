# 1.13.7 Behavioral Reference — Required Independent Apex Coverage

## Important: reference, not dependency

Occult Hybrid Unlocker & Stabilizer is a behavioral/regression reference only. Production Apex must not require its package/script files, import its runtime modules, or ship a renamed/repacked copy.

Use public/recovered evidence to define expected behavior and regressions, then independently implement the Apex-owned equivalent from current Sims 4 data and Apex source/policy.

## Verified behavioral floor

The current distributed upstream release is **Occult Hybrid Unlocker & Stabilizer 1.13.7 (FIXE)**, uploaded May 16, 2026. The public upstream GitHub repository later received a September 7, 2026 README credit commit, but its visible source lineage still centers on 1.13.5. Therefore Codex must not assume the public GitHub tree alone represents the 1.13.7 distributed package.

## Required deltas

Apex must independently reproduce or improve the following behavior before claiming the historical reference floor is covered:

1. **Missing STBL coverage** equivalent to the FIXE behavior, implemented in Apex-owned resources.
2. **TMex PhoneSearch compatibility**: independently preserve the PlantSim Pie Menu behavior without depending on upstream package resources.
3. **Apex-owned tuning injection coverage** equivalent in behavior for:
   - werewolf traits;
   - fairy traits;
   - fairy bloodline traits.
4. **Cache diagnostics** equivalent in capability to:
   - `td1hybrid.view_sim_cached_occults`;
   - `td1hybrid.view_global_cached_occults`;
   - `td1hybrid.view_cas_cached_sims`.

## Apex improvement rule

Do not copy upstream UI/commands/package resources. Route independently implemented equivalent capabilities through Apex's canonical state/diagnostics layer so F11, browser fallback and console diagnostics agree.

## Evidence standard

For each delta record:

- upstream artifact/version/source of evidence;
- Apex file(s) changed;
- fixture or runtime reproduction;
- changed-path verification;
- save/reload result if persistent state is touched;
- failure behavior when the relevant pack/occult is absent.


## Standalone proof

The behavioral floor is not satisfied until the same tests pass on a clean Mods profile with:
- no TD1/TwelfthDoctor1 hybrid package/script;
- no IcedCream hybrid package;
- no LordPercivalXII hybrid package/script;
- no other hybrid stabilizer.

The exact tested production pair must be `ApexOccultHybrid.package` + `ApexOccultHybrid.ts4script`.
