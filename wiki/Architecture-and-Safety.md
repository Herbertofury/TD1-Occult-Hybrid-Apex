# Architecture & Safety

```text
F11 Dear ImGui overlay / browser fallback
               |
        typed localhost commands
               v
       Apex Python domain layer
               |
        game-thread queue only
               v
   Sims 4 SimInfo / OccultTracker
```

## Hard invariants

- Native Present/render thread never mutates Sims state.
- Hidden overlay performs no Sims/HTTP polling.
- No private MCCC monkey-patching.
- Auto repair is opt-in.
- Stale snapshots must not overwrite newer intentional edits.
- Unsupported/custom occults are preserved as unknown/ambiguous state rather than deleted.
- Build/static checks are not live-game proof.

## Recovery model

Every high-risk workflow should expose: current state -> proposed target -> mutation -> verification -> persistence/reload proof -> rollback/recovery when practical.
