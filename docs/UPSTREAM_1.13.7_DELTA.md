# Upstream 1.13.7 Delta — Required Apex Parity

## Verified release floor

The current distributed upstream release is **Occult Hybrid Unlocker & Stabilizer 1.13.7 (FIXE)**, uploaded May 16, 2026. The public upstream GitHub repository later received a September 7, 2026 README credit commit, but its visible source lineage still centers on 1.13.5. Therefore Codex must not assume the public GitHub tree alone represents the 1.13.7 distributed package.

## Required deltas

Apex must verify or port all of the following before claiming parity:

1. **Missing STBL repair** from the FIXE package.
2. **TMex PhoneSearch compatibility**: PlantSim interactions routed through the Pie Menu rather than the conflicting phone-search path.
3. **ClassInstanceTuningInjections additions** for:
   - werewolf traits;
   - fairy traits;
   - fairy bloodline traits.
4. **Cache diagnostics** equivalent in capability to:
   - `td1hybrid.view_sim_cached_occults`;
   - `td1hybrid.view_global_cached_occults`;
   - `td1hybrid.view_cas_cached_sims`.

## Apex improvement rule

Do not merely copy upstream UI/commands. Route the same capabilities through Apex's canonical state/diagnostics layer so F11, browser fallback and console diagnostics agree.

## Evidence standard

For each delta record:

- upstream artifact/version/source of evidence;
- Apex file(s) changed;
- fixture or runtime reproduction;
- changed-path verification;
- save/reload result if persistent state is touched;
- failure behavior when the relevant pack/occult is absent.
