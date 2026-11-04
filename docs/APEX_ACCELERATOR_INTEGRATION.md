# Apex and TS4 Accelerator performance work

Owner request, October 13, 2026: improve game loading, camera movement and
frame-time lows while making Apex's DLL inexpensive. Preserve content, visuals,
simulation behavior, scripts, saves, Tray and third-party compatibility.

## Implementation decision

Keep Accelerator as a separate optional component initially. Apex owns F11,
appearance transactions and its existing DX11 presentation hook. Accelerator
owns package preparation and any subsequently qualified engine acceleration.
Share versioned diagnostics and benchmark evidence. A second independent
presentation hook, render stack or resource replacement is not required merely
to integrate them. Consolidating DLLs is a later measured engineering choice.

The [Accelerator wiki](https://github.com/Herbertofury/TS4-Accelerator/wiki)
prioritizes verified unchanged-work reuse and qualifying the physical shadow
package route. It does not certify current-game speed gains. The
[current research checkpoint](https://github.com/Herbertofury/TS4-Accelerator/wiki/Current-Build-and-Research-Evidence)
distinguishes separately recovered source and isolated prototypes. In particular,
some lazy-cache experiments regress and are not promoted.

The Desktop Accelerator copy inspected here reports Cargo 0.1.0 and has no Git
checkout. Its existing DLL uses file/mapping hooks and process-level boost
settings. It is not assumed to contain the newer research source. Reconcile
exact source hashes and provenance before porting patches or calling it latest.

## Apex boundaries already inspected

Hidden F11 skips ImGui initialization/drawing and automatic status HTTP polling.
Queued explicit CLI work can still run. Its worker currently wakes at 250 ms
while hidden; the presentation hook still handles discovery, configuration,
hotkey sampling and explicit captures. These are source observations, not
measured proof of negligible overhead. The render mutex also spans the real
Present call, so lock contention deserves measurement before any redesign.

The catalog/resource service runs outside the game and retains exact resource
identities. Keep resource parsing, image generation, index building and large
collection work off the simulation and presentation threads. Keep bounded caches
and demand-driven resource access for editing thousands of Sims.

## Acceptance work

- [x] Read current Accelerator Home, research evidence and implementation backlog.
- [x] Locate the Desktop source and distinguish its version from newer research.
- [x] Record present/worker boundaries and select separate optional ownership.
- [ ] Reconcile newer source artifacts and exact recovered/repository lineage.
- [ ] Measure baseline, Apex hidden, Apex visible, and 3D-preview workloads with
  matched camera movement, content/settings and cold/warm/incremental states.
- [ ] Collect startup/load phases separately from gameplay; report long stalls,
  p99/p99.9 intervals, slowest-1% metrics, CPU waits, memory and observer cost.
- [ ] Qualify owned preparation candidates individually on Windows. Retain exact
  effective resource winners, ordering, decompressed bytes and script/config
  visibility. Include original Studio/Tray Importer operations and save/reload.
- [ ] Remove demonstrated repeated work or stalls in Apex, then repeat the
  matched measurements. Gate changes against regressions across workloads.
- [ ] Integrate only qualified Accelerator improvements. Preserve pass-through,
  exact-build guards and independent enable/disable without changing originals.

Do not promote blanket priority/timer/allocator/GC/threading/cache tweaks, discard
useful shader caches or reduce texture/LOD quality to obtain a better number.
The [Accelerator backlog](https://github.com/Herbertofury/TS4-Accelerator/wiki/Validation-and-Implementation-Backlog)
requires native/game qualification of its candidates. This integration record
adds work to the project; it is not a DLL deployment or an FPS result.
