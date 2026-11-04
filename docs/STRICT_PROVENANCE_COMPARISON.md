# Strict staged comparison with provenance

`tools/compare_provenance_stages.py` is an **opt-in** wrapper around the existing
schema-2 staged comparator. It does not change the original schema-1 or schema-2
tools and does not launch Sims, collect input, install mods, or change a profile.
It requires the separately recorded `tools/mod_provenance.py` before/after
observations for every declared offline ETW run. The observations and traces
must be produced safely in an isolated profile under the user's coordinated
game-testing workflow. This wrapper has been tested with synthetic fixtures only;
no game baseline or performance improvement has been established.

The wrapper's private JSON manifest has exact keys `schema`, `experiment`, and
`proofs`. `experiment` points to the unchanged schema-2 staged experiment JSON.
Each proof is bound to **one** exact capture metadata file by SHA-256 and pins
the exact before, after, and action-trace bytes:

```json
{
  "schema": 1,
  "experiment": "experiment.json",
  "proofs": [
    {
      "capture_sha256": "<64 lowercase hex>",
      "before": "run-1.before.json",
      "before_sha256": "<64 lowercase hex>",
      "after": "run-1.after.json",
      "after_sha256": "<64 lowercase hex>",
      "action_trace_sha256": "<64 lowercase hex>"
    }
  ]
}
```

There must be one proof for every declared run, with no extra or reused capture,
before, or after files. The example illustrates the shape, not a valid complete
experiment: a stage comparison still needs at least four counterbalanced runs.
Proof paths are relative to the strict manifest; experiment run paths remain
relative to the experiment JSON. All inputs and the fresh output must be in the
checkout's private `.work`; symlinks, reparse points and hardlinked evidence are
refused by the provenance reader. ETLs and paths can contain private system and
mod information; do not publish the evidence files.

For strict mode, `scenario.other_mods_sha256` is the SHA-256 of the control
observation's **complete** `mods.files` array, encoded exactly as follows:

```python
raw = json.dumps(before['mods']['files'], sort_keys=True, separators=(',', ':'),
                 ensure_ascii=True, allow_nan=False).encode('ascii')
other_mods_sha256 = hashlib.sha256(raw).hexdigest()
```

The list comes from `mod_provenance.py`, sorted by case-folded relative path,
with each row containing `path`, `bytes`, and `sha256`. It includes Resource.cfg,
settings and every other file the observation found in the control `Mods` tree.
This strict digest is deliberately defined here and can differ from a legacy
experiment's declared hash. Use the same digest in the scenario and each
stage's mod-state record. Do not reinterpret an existing run's digest silently.

Artifact paths in each stage are relative to `Mods`. The wrapper requires each
observed stage inventory to equal the complete control inventory **plus** the
stage's explicitly declared artifact paths and SHA-256 values. Known artifact
paths for any declared stage must be absent from the control. Extra, missing,
changed or case-aliased files cause refusal. Runtime-generated files must also
be accounted for and stable; the wrapper does not ignore logs or settings by
guessing. Stage changes that intentionally replace a control file require a
different reviewed experiment design rather than silently relaxing this rule.
This version covers declared artifacts **under Mods only**. An overlay stage
must declare a DLL under Mods and it must appear with the declared hash; a stage
whose required DLL exists solely in game Bin cannot satisfy that requirement
and is refused. The wrapper does not inventory Bin artifacts as stage files or
prove that the DLL observed under Mods was the module actually loaded. A DLL in
Bin or an unrelated DLL under Mods cannot be treated as proof of overlay loading.

For each run it validates the provenance pair's exact hashes, process lifetime,
viewport, active journal/marker identity, module inventory and file hashes, and
the QPC interval around the capture. The same observed test-profile path/token,
game executable path, viewport/position/DPI and foreground status are required
across runs. Scans and capture windows must be ordered without QPC overlap and
use one frequency. The capture, stage definition and mod-state file hashes are
cross-bound; the actual comparator CSV and action trace are hashed and checked.
The original comparator then validates the ETL/CSV/action evidence and computes
metrics with its existing rules. It stops evaluating metrics at the first
observed slowdown. The wrapper validates proofs for **all declared runs** up
front; reports for later, unevaluated stages explicitly say `metric_evaluated:
false` and are not performance results. Only evaluated stages receive the
original comparator's full ETL/header/loss and action-window validation. Later
declared runs receive provenance, metadata, stage/mod-state and CSV-hash checks
only; their `full_etl_validation_performed` value is false.

The strict mode verifies consistency of the supplied observation files, not
their authenticity as a hardware attestation. It does not prove the game opened
the specified profile, that an installed package/script was actually loaded,
that every Apex component was identified, that saved-game data matches a
declaration, that loaded in-memory code matches on-disk modules, or that no
transient change occurred between snapshots. Explicit synthetic/stub markers
are refused; their absence does not prove a game observation. Stage loaded
flags and UI-transition observations remain runner-supplied declarations.
The control can contain an undeclared Apex file, even if all *declared* stage
artifact paths are absent. Independent evidence is still needed for all those
claims. No setting of this wrapper establishes feature parity, a performance
pass, displayed FPS, or hitch-free operation.

Full hashing occurs outside each capture window and may warm caches. Keep the
same preparation and cache state across run orders, and measure trace/observer
overhead separately before interpreting differences. The original comparator's
finite-sample and trace-loss limitations still apply.

Run only after the complete private evidence exists:

```powershell
python tools/compare_provenance_stages.py --manifest .work/<strict-manifest>.json --output .work/<new-report>.json
```

The output never overwrites an existing file. An empty comparisons list returns
`awaiting_measurements`, with no provenance pair marked verified.
