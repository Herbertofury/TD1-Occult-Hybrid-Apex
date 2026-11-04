# Experimental file-backed frame capture

`tools/offline_xperf.py` is a new experimental backend for the existing frame
comparison tools. A separate synthetic DXGI window produced an ETL with no
reported loss, and PresentMon 2.6.0 parsed target QPC rows from it. **This does
not qualify the backend against Sims, prove complete Present coverage, establish
a no-Apex baseline, or establish a performance improvement.**

The first external probe submitted 424 Present calls and the offline parser
produced 422 target rows. The reason for the two-row difference has not been
independently established. Only claims within actually observed action windows
are permitted after future controlled game qualification.

A later five-second end-to-end adapter mechanics exercise produced 316 rows;
the final revision produced 317 rows inside the requested QPC window with zero
header loss. The probe's process and
profile identity checks were deliberately stubbed, and its output is marked
`synthetic_probe_only`; it cannot satisfy the game comparator. This confirms
only the measured offline mechanics and the fixture setup, not the game path.

The adapter reuses `capture_frame_intervals.verify_start`: it requires the
existing marked disposable-profile journal, exact Sims PID and executable SHA,
visible Canvas identity and geometry, caller-provided PID-bound mod inventory,
explicit `--parent-ready --run`, the pinned PresentMon executable and a fresh
output prefix in this checkout's `.work`. The preflight does not independently
prove which profile a running process opened or which packages loaded; gather
that independent evidence before use. The adapter never starts or controls the
game, changes a profile, sends input or touches another ETW session.

The command captures into a randomly named, owned file-backed xperf session.
It requests QPC timing, 1,024 KiB buffers, sequential file mode and a 1 GiB
maximum; at least 2 GiB free space is required. It reads the actual logger
configuration at the start and end to verify the name, output path, sequential
mode, buffer size, actual buffer counts, file cap and exact pinned provider
GUIDs, keyword masks and levels. Unknown, missing, extra or changed providers
fail closed. Those checks are sampled, not continuous. It polls the named session approximately
once a second; these extra probes can perturb the workload and must be held
constant and assessed across conditions. Actual ETW buffer counts become part
of the matched collector identity.

Only the session this invocation has confirmed starting is stopped. If starting
or stopping fails or times out, its outcome may be uncertain: the metadata
marks `manual_inspection_required`, names the exact session and ETL path, and
the adapter does not blindly retry or stop a generic session. Catchable
interruptions after a confirmed start trigger one attempt to stop that owned
session; a failed or uncertain stop is not retried automatically. An
uncatchable process kill or machine interruption can leave a session behind.
Before launching xperf, metadata records `state: starting`, an uncertain start
outcome, a manual-inspection requirement, the unique name and intended ETL
path. The flag remains set while the session may exist and is cleared only
after a confirmed stop. Query xperf/logman read-only, verify both name and path, and stop only
that exact verified owned session if still running. Never use upstream's example stop script, which
uses generic session names and can affect unrelated sessions.

After an owned stop, the backend rejects a missing/empty trace, one within 1 MiB
of its file cap, a header naming a different ETL, a non-sequential trace, or
anything other than exactly one trace with explicit zero lost events and zero
lost buffers. It hashes the ETL, logger configuration and header. The existing
CSV reader requires one PID and swapchain, DXGI runtime identity, positive
intervals, `CPUStartQPC`, strictly increasing `TimeInQPC` and at least 120 rows.
PresentMon's full raw CSV is retained separately: it includes startup and
shutdown outside the requested action window. The adapter derives a second CSV
containing only intervals whose preceding and current Present timestamps both
fall within the exact ready/end QPC bounds. It never infers or adds frames.
The comparator hashes the raw CSV and independently rederives the identical
window subset, then checks all retained hashes and command identities again. The
adapter also rejects session-poll gaps over three seconds and samples with no
target Present within one second of either capture boundary; each action still
needs independently observed transition evidence inside the CSV QPC span.

Before selecting rows, the adapter checks every adjacent raw QPC timestamp
against `MsBetweenPresents`. The pinned PresentMon 2.6.0 source calculates the
metric as binary64 `ticks * (1000.0 / frequency)` and prints 14 fractional
digits. The allowed rounding error is half of the `10^-14` ms print quantum
plus four binary64 epsilons of the exact rational interval, covering integer
conversion, division and multiplication roundoff. Missing, noncanonical or
inconsistent metrics fail closed. The first raw row is excluded because its
predecessor is unobserved. This check detects many missing output rows; it does
not prove completeness if the collector omitted events before constructing its
per-swapchain metric. See [upstream metric calculation](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/IntelPresentMon/CommonUtilities/mc/MetricsCalculatorAnimation.cpp),
[QPC arithmetic](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/IntelPresentMon/CommonUtilities/Qpc.cpp)
and [CSV output](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/PresentMon/CsvOutput.cpp).

Those checks are conservative but do not prove every driver event was emitted,
or rule out a shorter interruption between polls. File size and the ETW loss
counters may not reveal every possible source of truncation. The method must be
checked against an independently observed, reproducible game workload before
being used for a comparison. A zero-loss trace can still contain missing events
or omit the action of interest. Never convert synthetic identity stubs or a
partial trace into a completed game-capture record. The offline validator
explicitly rejects synthetic/stub markers even if the state was relabeled
`completed`; an unmarked declaration is not proof that the game was measured.
The reported PresentMon SHA must equal the pinned 2.6.0 binary fingerprint.

Launch from a suitably authorized shell; the tool never requests or bypasses
elevation itself. Supply the actual xperf SHA-256 as well as the game SHA:

```powershell
python tools/offline_xperf.py --state <disposable-journal> --pid <pid> --exe <game-exe> --exe-sha256 <game-sha256> --xperf-sha256 <xperf-sha256> --mode baseline --mod-state <evidence-json> --seconds 30 --output .work/benchmark/offline-1 --parent-ready --run
```

`READY` means the unique session was observed and the window still matched;
it is not a valid final capture. Action timing/transition observation remains
separate. A successful run emits the existing comparator's QPC CSV format, plus
backend-specific metadata, private raw ETL and attestation logs. A comparison
must use the same backend, pinned collector, adapter source, xperf binary, actual buffer counts,
provider settings and duration for every paired run. Mixing live and offline
collectors is refused. Raw ETLs can contain other process or system metadata;
retain them privately and never publish them with source changes.

Historical retained evidence on GoldenOreo is in the task workspace under
`collector-diagnostic/offline-001`. Its ETL SHA-256 is
`0e35739d356bb64027589977c488b2041b4f78504f3a8f17e79d4c48902bc4d2`;
its parsed CSV SHA-256 is
`b5bc7d5ea3371fc1deace6dc9c59aff8d5d4a92ad2724b888550529a21407cde`.
The ETL is retained locally, not in this repository.
