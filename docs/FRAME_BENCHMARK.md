# Matched frame-time comparison

Run measurements only after the updated mod is ready for disposable-game
testing. This file describes a comparison tool; it does not launch Sims,
collect frames, change a profile, send input or claim a performance result.

Use the same disposable household, saved state, game executable, graphics and
display settings, hardware, non-Apex mods/CC and viewport for each run. Record
the precise action sequence and direction, such as Body → Tattoo → scroll down
→ scroll up; a CAS transition is not equivalent to an idle sample. Measure
Live interactions separately from CAS. Compare either cold with cold or warm
with warm, and record the preparation method. Capture at least two paired runs,
using both baseline → Apex and Apex → baseline orders to reduce order bias.

The existing private `.work/v344-frame-measurement/capture_frames.py` reports
DXGI present intervals but requires Apex-specific profiler evidence and omits
the QPC option. The new `tools/capture_frame_intervals.py` accepts either a
baseline or Apex state and requests `--qpc_time`; its isolated preflight tests
pass, but **it has not yet been exercised against the game**. Do not reuse an
Apex-enabled run as the no-mod baseline or infer action coverage from an
unaligned whole-session mean. The collector and separate action-trace workflow
still need live verification in both states after the update is ready.

The new collector requires an already-running, visible disposable Sims process,
an exact executable hash, an existing marked test-profile journal, and
PID/creation-time-bound mod-state evidence. It never launches Sims, changes
focus, sends input, writes a save or installs/removes mods. The marked-profile
check and observed window identity do not independently prove which profile the
running process opened. Both runs depend on separately obtained mod-state
evidence; for an Apex run the evidence must also show its optional diagnostic
profilers are inactive and uninstalled. The baseline needs no Apex bridge.
During capture the tool briefly queries the named ETW session at most once per
second until ready; this is measurement overhead, not a hidden service.

```powershell
python tools/capture_frame_intervals.py --state .work/reusable-profile-session.json --pid <pid> --exe 'C:\Games\The Sims 4\Game\Bin\TS4_x64.exe' --exe-sha256 <sha256> --mode baseline --mod-state .work/benchmark/mod-state.json --seconds 30 --output .work/benchmark/baseline-1 --parent-ready --run
```

The output prefix must be new and inside `.work`; the tool does not overwrite
prior recordings. Its `READY` message means the pinned collector reported an
active named trace and the observed process/window remained stable; final CSV
and loss checks still determine whether the recording is valid. Record actions
separately in QPC time and verify their actual UI transitions. Do not assume
that a lack of logged event-loss messages proves the entire OS trace was lossless.

`tools/compare_frame_runs.py` consumes completed, separately recorded evidence.
Each capture metadata JSON must be in the format of the private capture tool:
state `completed`, collector hash, stable process/window identity and geometry,
an analysis with `valid: true`, no reported event loss, one swapchain, and the
SHA-256 of the raw target-process PresentMon CSV. The CSV must include
`ProcessID`, `SwapChainAddress`, `PresentRuntime`, `MsBetweenPresents`, and
`CPUStartQPC` and `TimeInQPC`; for the pinned PresentMon 2.6.0 default combined
output, `--qpc_time` requests these CPU-start and Present-event timestamps. Mixed
PIDs, distinct swapchains, unstable time order and missing QPC data are refused.
Present intervals are not a displayed-frame or input-to-photon measurement.

The manifest is JSON with exact keys `schema`, `scenario`, and `runs`:

```json
{
  "schema": 1,
  "scenario": {
    "name": "cas-body-tattoo-scroll",
    "game_exe_sha256": "<64 lowercase hex>",
    "hardware_sha256": "<64 lowercase hex>",
    "save_sha256": "<64 lowercase hex>",
    "other_mods_sha256": "<64 lowercase hex>",
    "settings_sha256": "<64 lowercase hex>",
    "profile_id": "disposable-profile-id",
    "resolution": [1920, 1080],
    "dpi": 96,
    "display_mode": "windowed",
    "refresh_hz": 60,
    "fps_cap": 60,
    "renderer": "dx11",
    "cache_state": "warm",
    "game_mode": "CAS",
    "actions": ["body", "tattoo", "scroll-down", "scroll-up"]
  },
  "runs": []
}
```

Each run has exactly `kind` (`baseline` or `apex`), `capture`, `csv`,
`actions`, `mod_state`, `started_ns`, `ended_ns`, and `scenario`. Evidence
paths are absolute or relative to the manifest. The scenario must equal the
top-level scenario exactly; each run's ordering times must not overlap. The
`started_ns` and `ended_ns` values are experiment-runner wall-clock
declarations: the comparator checks ordering and overlap but does not
independently bind those values to the collector's timestamps.
The candidate must have the same artifact SHA across Apex runs. Record hashes
using canonical, documented inventories: `other_mods_sha256` excludes all
Apex components and stays identical in both states. Hardware, settings and
inventory fingerprints must actually include the relevant dependencies;
matching arbitrary hashes does not establish that they do.

The `mod_state` evidence is a JSON object binding `target_pid` and
`process_creation_filetime`, `other_mods_sha256`, and `schema: 1`. It includes
`inventory_and_loaded_modules_observed: true`, a nonempty `observation_method`,
booleans `apex_script_loaded`, `apex_cas_package_loaded`, and
`apex_overlay_loaded`, and `apex_candidate_sha256` (null in baseline; the
candidate's SHA-256 in the Apex state). All three booleans must be false for
baseline and true for Apex. The current comparator verifies these declarations
and their process binding but does not independently inspect installed mods,
script loading or modules; establish that evidence before making any claim.
For an Apex capture, the collector additionally requires
`native_service_profile` with `enabled: false`, `installed: false`, and
`inflight: 0`, plus `native_gfx_snapshot_profile` with `enabled: false`,
`prepared: false`, `active_heap_hooks: false`, and `inflight: 0`. The baseline
requires no Apex profiler evidence because Apex must be absent.

The `actions` evidence is a JSON object containing the capture metadata
`capture_sha256`, exact `target_pid`, `process_creation_filetime`, `clock: "QPC"`,
`ui_transitions_verified: true`, and ordered `events` whose `action`,
`observed: true`, `start_qpc`, and `end_qpc` match the scenario. Every event
must fit inside the actual CSV QPC span and remain sequential. Accepted window
messages or a button click alone do not prove that the UI transition happened.
Collect and review independent transition evidence; the tool validates the
supplied trace, not the truth of an arbitrary declaration.

Invoke once the complete evidence exists:

```powershell
python tools/compare_frame_runs.py --manifest .work/benchmark/manifest.json --output .work/benchmark/comparison.json
```

The comparison also checks the captured mode, executable fingerprint, mod-state
file hash, both process/window snapshots, the `--timed` duration and CSV path
against their corresponding declared evidence. The output must be a new file
inside `.work`. It reports per-run mean, median,
p95, p99, maximum, average of the slowest 1% of present intervals and counts
above the declared refresh budget or 33.3 ms normalized per 1,000 frames, plus
frame count, median and maximum interval, and count over the refresh budget
inside each recorded action window. Paired action deltas make it easier to
locate a slow transition, but different frame counts and durations can skew
their maxima and do not establish a cause. P99.9 is omitted for fewer than
1,000 samples. Pair deltas are Apex minus baseline;
positive frame-time deltas mean slower recorded presents. The tool rejects
reused capture/trace evidence and mismatched collectors or present runtimes.
It requires identical collector options and durations, and never reports
`performance_pass`, displayed FPS or hitch-free operation.
A finite comparison, especially under declared conditions, cannot prove that
all game hitches have been eliminated or isolate their cause.

## Incremental rebuild measurements (November 4)

`tools/compare_hitch_stages.py` adds schema 2 for cumulative feature experiments.
This supports T048/T092/T114 measurement work; it does not replace the canonical
feature requirements or mark those tasks complete. The original schema 1
baseline/full-Apex comparison remains available.

Each stage has exact keys `id`, `features`, `artifacts` and `loaded`. For example,
the initial stage is:

```json
{
  "id": "vanilla",
  "features": [],
  "artifacts": [],
  "loaded": {
    "apex_script_loaded": false,
    "apex_cas_package_loaded": false,
    "apex_overlay_loaded": false
  }
}
```

Later stages add exactly one feature group, retaining every earlier feature.
List sorted unique feature ids and sorted Windows-case-unique artifact paths
with SHA-256 values. `artifacts` lists every installed Apex component, including
disabled components; a rebuilt monolithic package needs its new hash. Record
real compiled behavior rather than inventing a feature toggle. Dependency-bound
components may form one documented group. Profiling partitions are not permission
to omit a feature from the final mod or disable its preservation guard.

A schema 2 mod-state record retains the PID/creation-time, observed-inventory
and `other_mods_sha256` fields above, and carries `stage`, `stage_sha256` and
the three observed component booleans. `stage_sha256` is
`hitch_stage.digest(stage)` over canonical JSON. It binds the declaration,
not independent proof of installed/loaded bytes. When the overlay is loaded,
the same inactive/uninstalled diagnostic-profiler evidence is required.
Collect with `--mode stage`; capture metadata pins the stage id and digest.

The incremental manifest has exact keys `schema: 2`, `scenario`, `stages`
and `comparisons`. `scenario` has the same matching fields as above.
Each comparison has `control`, `candidate` and `runs`; these must refer to
adjacent stages. Each run uses the original evidence-path/order/scenario
fields, with its stage id in `kind`. At least four fresh runs are required
per comparison: control/candidate and candidate/control. Do not reuse a
capture or transition trace in another trial or stage comparison.

```powershell
python tools/compare_hitch_stages.py --manifest .work/benchmark/stages.json --output .work/benchmark/stage-report.json
```

Positive deltas in p95, p99, maximum, over-33.3-ms intervals per 1,000, or
action-window maximum stop evaluation at that stage. Investigate measurement
noise and correlate the same window with CPU/file-I/O evidence before deciding
which code is responsible. The report does not automatically continue after a
slowdown. Equal/improved intervals still require real feature/correctness review;
the tool never certifies parity, displayed FPS or a hitch-free result. An empty
comparison list reports `awaiting_measurements`.

Action attribution now uses `TimeInQPC` for the Present event and every observed
present interval overlapping the action window. This retains a stall whose
next Present arrives after the window ends. The full overlapping interval can
include work outside the action; no exclusive causal cost is inferred. The first
interval has no observed previous endpoint and is excluded from action attribution.
`CPUStartQPC` remains required evidence but is not substituted for Present time.
Historical CSVs lacking the Present clock must be recaptured for this analysis.
See the pinned [PresentMon CSV writer](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/PresentMon/CsvOutput.cpp)
and [console documentation](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md).
