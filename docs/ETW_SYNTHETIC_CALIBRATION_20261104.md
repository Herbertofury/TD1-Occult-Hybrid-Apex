# Synthetic ETW calibration, November 4, 2026

This is an instrumentation calibration, **not a Sims measurement, displayed
FPS measurement, game-hitch diagnosis or performance pass**. It cannot establish
that ETW capture has negligible overhead in CAS, Live Mode or large mod sets.

A separate off-screen 128 × 128 DXGI probe called `Present(0, 0)` in a loop
with a fixed 16 ms sleep. It recorded QPC immediately before and after each
call. Each run lasted approximately five seconds and yielded 303–304 intervals
between successive call starts; the observed QPC frequency was 10 MHz. All
probe calls returned success. There was no rendering workload comparable to
Sims. A read-only guard found no Sims or launcher process before the experiment,
before each run and at sampled checks while the probe ran. The guard itself
and other background work can perturb measurements.

`control` means no ETW session owned by this experiment; other Windows ETW
sessions remained active. `ETW` means a uniquely named file-backed xperf session
using the offline adapter's five providers, 1,024 KiB buffers, sequential mode
and 1 GiB file cap. The actual buffer limits were identical across traced runs.
The trace header reported zero lost events and buffers in all four ETW runs,
start/end logger settings matched, and all four owned sessions stopped. Zero
reported loss does not prove that the driver emitted every event. Each ETL was
approximately 90–112 MB including session startup and shutdown; these files
may contain process metadata and remain private.

The fixed order was **control, ETW, ETW, control, control, ETW, ETW, control**,
forming four adjacent pairs in both orders. Percentiles use linear interpolation
at index `p × (n − 1)` over each run's QPC-derived Present-start intervals.

| Run | Condition | p95 ms | p99 ms | Maximum ms | Intervals > 33.3 ms |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | control | 16.6343 | 16.6871 | 28.7308 | 0 |
| 1 | ETW | 16.6317 | 16.7066 | 28.7961 | 0 |
| 2 | ETW | 16.6626 | 16.7630 | 24.1386 | 0 |
| 3 | control | 16.6496 | 16.7014 | 32.8801 | 0 |
| 4 | control | 16.6376 | 16.6983 | 24.1194 | 0 |
| 5 | ETW | 16.6507 | 16.7436 | 34.1621 | 1 |
| 6 | ETW | 16.6132 | 16.6639 | 28.5838 | 0 |
| 7 | control | 16.6150 | 16.7012 | 27.3739 | 0 |

Across the four pairs, ETW-minus-control p95 ranged from **−0.00262 to
+0.01313 ms**, p99 from **−0.03734 to +0.06162 ms**, and maximum interval from
**−8.7415 to +10.0427 ms**. One traced run had one interval above 33.3 ms;
the four controls had none. These short samples and an individual outlier do
not establish causation, a reliable upper bound on overhead or a regression in
the game. Background load, scheduling, thermal state and GPU clocks were not
isolated; the order was counterbalanced but not randomized.

Probe, reused DXGI source, Python executable, xperf and adapter hashes were
recorded in the experiment metadata. The supervisor and analyzer sources were
snapshotted afterward and were **not independently pinned during the run**.
The hash of the private analysis receipt is
`db0802d9465c82ee3b37bfa24159873cd21c08456a8da7e8234fa4278c868268`.
Raw QPC samples, logger/header receipts, private traces and source snapshots
remain in the task workspace under `collector-overhead-calibration/paired-001`;
they are not published with this documentation.

Before using the offline backend to compare Apex stages, independently qualify
the actual game process, profile, installed and loaded mods, saved fixture,
action transitions, exact window and QPC traces. Measure capture overhead under
that workload and repeat matched runs in both orders. Stop at regressions for
diagnosis; this calibration does not close any Sims performance gate.
