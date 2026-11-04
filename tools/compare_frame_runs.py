"""Compare matched PresentMon intervals without launching or controlling Sims.

The manifest links already completed capture metadata, raw CSVs and independently
recorded action traces. It must contain at least two opposite-order pairs of
baseline (Apex absent) and candidate (Apex present) recordings. Scenario values
are declarations supplied by the experiment runner; they are not independently
discovered or proof of hardware/content identity. See FRAME_BENCHMARK.md.
"""
import argparse
import bisect
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import hitch_stage

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON = 4 * 1024 * 1024
MAX_CSV = 256 * 1024 * 1024
SCENARIO_FIELDS = frozenset(('name', 'game_exe_sha256', 'hardware_sha256',
    'save_sha256', 'other_mods_sha256', 'settings_sha256', 'profile_id',
    'resolution', 'dpi', 'display_mode', 'refresh_hz', 'fps_cap',
    'renderer', 'cache_state', 'game_mode', 'actions'))
HASH_FIELDS = ('game_exe_sha256', 'hardware_sha256', 'save_sha256',
               'other_mods_sha256', 'settings_sha256')


def load_json(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError('Evidence JSON exceeds its bounded size.')
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate evidence JSON key: ' + key)
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON'))), hashlib.sha256(raw).hexdigest()


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def validate_scenario(value):
    if not isinstance(value, dict) or set(value) != SCENARIO_FIELDS:
        raise ValueError('Scenario must include all exact matching fields.')
    if any(not _hash(value[k]) for k in HASH_FIELDS):
        raise ValueError('Scenario fingerprints must be SHA-256.')
    if any(not isinstance(value[k], str) or not value[k].strip() for k in
           ('name', 'profile_id', 'display_mode', 'renderer', 'cache_state', 'game_mode')):
        raise ValueError('Scenario text fields must be nonempty.')
    if (not isinstance(value['resolution'], list) or len(value['resolution']) != 2 or
            any(type(x) is not int or x <= 0 for x in value['resolution']) or
            type(value['dpi']) is not int or value['dpi'] <= 0):
        raise ValueError('Resolution and DPI must be positive.')
    for field in ('refresh_hz', 'fps_cap'):
        v = value[field]
        if field == 'fps_cap' and v is None:
            continue
        if type(v) not in (float, int) or not math.isfinite(v) or not 0 < v <= 1000:
            raise ValueError('Display refresh and optional FPS cap must be finite and positive.')
    actions = value['actions']
    if not isinstance(actions, list) or not actions or len(actions) > 1000 or any(not isinstance(x, str) or not x.strip() for x in actions):
        raise ValueError('A nonempty ordered action sequence is required.')
    return value


def percentile(sorted_values, p):
    pos = (len(sorted_values) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def statistics_for(values, refresh):
    ordered = sorted(values)
    slow = ordered[-max(1, math.ceil(len(ordered) * .01)):]
    mean = statistics.mean(ordered)
    return {'frames': len(ordered), 'mean_ms': mean,
            'p50_ms': percentile(ordered, .50), 'p95_ms': percentile(ordered, .95),
            'p99_ms': percentile(ordered, .99),
            'p99_9_ms': percentile(ordered, .999) if len(ordered) >= 1000 else None,
            'max_ms': ordered[-1], 'slowest_1pct_mean_ms': statistics.mean(slow),
            'over_refresh_budget_per_1000': 1000 * sum(x > 1000 / refresh for x in ordered) / len(ordered),
            'over_33_3ms_per_1000': 1000 * sum(x > 1000 / 30 for x in ordered) / len(ordered)}


def action_statistics(values, clocks, start, end, refresh):
    """Describe intervals overlapping an observed window, not its cause."""
    # For interval i the endpoints are clocks[i-1], clocks[i]. Both
    # inequalities are strict so a mere boundary touch is not overlap.
    first = max(1, bisect.bisect_right(clocks, start))
    last = min(len(clocks), bisect.bisect_left(clocks, end) + 1)
    within = values[first:last]
    if not within:
        raise ValueError('An observed action has no frame timestamp within its recorded window.')
    ordered = sorted(within)
    return {'frames': len(within), 'selection': 'present-interval-overlap',
            'p50_ms': percentile(ordered, .50), 'p95_ms': percentile(ordered, .95),
            'p99_ms': percentile(ordered, .99), 'max_ms': ordered[-1],
            'over_refresh_budget': sum(x > 1000 / refresh for x in within),
            'over_33_3ms': sum(x > 1000 / 30 for x in within)}


def read_frames(path, pid, expected_sha):
    path = Path(path)
    with path.open('rb') as stream:
        raw = stream.read(MAX_CSV + 1)
    if len(raw) > MAX_CSV or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('CSV is oversized or differs from its capture hash.')
    values, clocks, chain, runtime, skipped_initial = [], [], None, None, False
    with io.StringIO(raw.decode('utf-8-sig'), newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'ProcessID', 'SwapChainAddress', 'PresentRuntime', 'MsBetweenPresents', 'CPUStartQPC', 'TimeInQPC'}
        if (not required <= set(reader.fieldnames or ()) or
                len(reader.fieldnames or ()) != len(set(reader.fieldnames or ()))):
            raise ValueError('Frame CSV needs PID, swapchain, present interval and QPC timestamps.')
        for row in reader:
            if row['ProcessID'] != str(pid):
                raise ValueError('Foreign process row makes this capture unsuitable.')
            identity = (row['SwapChainAddress'], row['PresentRuntime'])
            if not all(identity):
                raise ValueError('Frame swapchain/runtime identity is missing.')
            if chain is None:
                chain, runtime = identity
            elif identity != (chain, runtime):
                raise ValueError('Multiple swapchains cannot be silently pooled.')
            val = row['MsBetweenPresents']
            if val in ('', 'NA') and not values and not skipped_initial:
                skipped_initial = True
                continue
            try:
                interval = float(val)
                # This metric ends at the Present() event, not CPU frame start.
                stamp = int(row['TimeInQPC'])
                cpu_stamp = int(row['CPUStartQPC'])
            except (TypeError, ValueError):
                raise ValueError('Invalid frame interval or QPC timestamp.')
            if not math.isfinite(interval) or interval <= 0 or stamp <= 0 or cpu_stamp <= 0 or (clocks and stamp <= clocks[-1]):
                raise ValueError('Frame intervals/QPC timestamps must be positive and strictly ordered.')
            values.append(interval); clocks.append(stamp)
    if len(values) < 120:
        raise ValueError('At least 120 valid frames are required per recording.')
    return values, clocks, runtime


def analyze_run(spec, scenario, manifest_dir, stage=None):
    if not isinstance(spec, dict) or set(spec) != {'kind', 'capture', 'csv', 'actions', 'mod_state', 'started_ns', 'ended_ns', 'scenario'}:
        raise ValueError('Run must include exact evidence paths, order, mode, and scenario.')
    kinds = ('baseline', 'apex') if stage is None else (stage['id'],)
    if spec['kind'] not in kinds or spec['scenario'] != scenario:
        raise ValueError('Run mode or matched scenario differs.')
    if type(spec['started_ns']) is not int or type(spec['ended_ns']) is not int or not 0 < spec['started_ns'] < spec['ended_ns']:
        raise ValueError('Run wall-clock ordering is invalid.')
    def resolve(name):
        if not isinstance(name, str) or not name:
            raise ValueError('Evidence path is missing.')
        path = Path(name)
        return path if path.is_absolute() else manifest_dir / path
    capture, capture_sha = load_json(resolve(spec['capture']))
    trace, trace_sha = load_json(resolve(spec['actions']))
    mods, mods_sha = load_json(resolve(spec['mod_state']))
    if not isinstance(capture, dict):
        raise ValueError('Capture metadata must be an object.')
    analysis = capture.get('analysis')
    if (capture.get('state') != 'completed' or capture.get('ready_seen') is not True or
            capture.get('window_identity_and_geometry_unchanged') is not True or
            capture.get('benchmark_mode') != ('stage' if stage is not None else spec['kind']) or
            capture.get('game_exe_sha256') != scenario['game_exe_sha256'] or
            capture.get('game_exe_hash_unchanged') is not True or
            capture.get('mod_state_sha256') != mods_sha or
            not isinstance(analysis, dict) or analysis.get('valid') is not True or
            analysis.get('event_loss_warning') is not False or
            len(analysis.get('swapchains', [])) != 1 or not _hash(analysis.get('csv_sha256')) or
            not _hash(capture.get('collector_sha256'))):
        raise ValueError('Capture is incomplete, invalid, lossy or ambiguous.')
    before, after = capture.get('window_before', {}), capture.get('window_after', {})
    identity_fields=('process_id','image_path','process_creation_filetime','hwnd','window_class',
                     'ui_thread','client_size','window_rect','dpi','foreground_hwnd')
    if (not isinstance(before, dict) or not isinstance(after, dict) or
            any(key not in before or key not in after or before[key] != after[key] for key in identity_fields) or
            before.get('client_size') != scenario['resolution'] or before.get('dpi') != scenario['dpi'] or
            before.get('process_id') != capture.get('target_pid') or
            type(before.get('process_creation_filetime')) is not int or before['process_creation_filetime'] <= 0):
        raise ValueError('Capture viewport, DPI or process identity differs.')
    pid = capture.get('target_pid')
    if type(pid) is not int or pid <= 0:
        raise ValueError('Capture PID is invalid.')
    command = capture.get('collector_command')
    if (not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command) or
            command.count('--qpc_time') != 1 or command.count('--process_id') != 1):
        raise ValueError('Collector command must enable QPC and identify one target process.')
    target_index = command.index('--process_id')
    if target_index + 1 >= len(command) or command[target_index + 1] != str(pid):
        raise ValueError('Collector target PID differs from capture.')
    normalized_command = []
    index = 1
    duration = capture.get('configured_seconds')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Capture duration is missing or invalid.')
    if capture.get('capture_backend')=='xperf_etl':
        import offline_xperf
        normalized_command=offline_xperf.validate_offline_capture(capture,command,pid,duration,resolve(spec['csv']).resolve())
    elif capture.get('capture_backend') is None:
        unique_options = ('--process_id', '--output_file', '--session_name')
        if any(command.count(option) != 1 for option in unique_options):
            raise ValueError('Collector command has missing or duplicate run-specific options.')
        while index < len(command):
            item = command[index]
            if item in unique_options:
                if index + 1 >= len(command):raise ValueError('Collector option is missing its value.')
                index += 2
            else:
                normalized_command.append(item); index += 1
        if command.count('--timed') != 1 or command.index('--timed') + 1 >= len(command):
            raise ValueError('Collector command must specify one capture duration.')
        try:command_duration = float(command[command.index('--timed') + 1])
        except ValueError:raise ValueError('Collector command duration is invalid.')
        if command_duration != duration:raise ValueError('Collector duration differs from capture metadata.')
        command_csv = Path(command[command.index('--output_file') + 1])
        if not command_csv.is_absolute(): command_csv = ROOT / command_csv
        if command_csv.resolve() != resolve(spec['csv']).resolve():raise ValueError('Collector output file differs from the CSV evidence.')
    else:
        raise ValueError('Unknown collector backend')
    expected_present = spec['kind'] == 'apex'
    if stage is not None:
        observed_stage = hitch_stage.validate_mod_state(mods, pid, before['process_creation_filetime'])
        if (observed_stage != stage or capture.get('stage_sha256') != hitch_stage.digest(stage) or
                capture.get('stage_id') != stage['id']):
            raise ValueError('Capture or observed state differs from the pinned stage.')
    if stage is None and (not isinstance(mods, dict) or type(mods.get('schema')) is not int or mods['schema'] != 1 or mods.get('target_pid') != pid or
            mods.get('process_creation_filetime') != before.get('process_creation_filetime') or
            mods.get('other_mods_sha256') != scenario['other_mods_sha256'] or
            mods.get('inventory_and_loaded_modules_observed') is not True or
            any(mods.get(name) is not expected_present for name in
                ('apex_script_loaded', 'apex_cas_package_loaded', 'apex_overlay_loaded')) or
            not isinstance(mods.get('observation_method'), str) or not mods['observation_method'].strip()):
        raise ValueError('Apex and non-Apex mod-state evidence is missing or differs.')
    if stage is not None and mods.get('other_mods_sha256') != scenario['other_mods_sha256']:
        raise ValueError('Non-Apex mod inventory differs between stages.')
    artifact_sha = mods.get('apex_candidate_sha256') if stage is None else mods['stage_sha256']
    if stage is None and ((expected_present and not _hash(artifact_sha)) or (not expected_present and artifact_sha is not None)):
        raise ValueError('Candidate artifact identity is inconsistent with its mod state.')
    values, clocks, runtime = read_frames(resolve(spec['csv']), pid, analysis['csv_sha256'])
    qpc_frequency = None
    if capture.get('capture_backend')=='xperf_etl':
        offline_xperf.validate_coverage(capture,clocks)
        qpc_frequency = capture['offline_etw']['qpc_frequency']
    if (not isinstance(trace, dict) or trace.get('capture_sha256') != capture_sha or
            trace.get('target_pid') != pid or trace.get('process_creation_filetime') != before.get('process_creation_filetime') or
            trace.get('clock') != 'QPC' or trace.get('ui_transitions_verified') is not True):
        raise ValueError('Action trace is not bound to this process and capture with observed transitions.')
    events = trace.get('events')
    if not isinstance(events, list) or len(events) != len(scenario['actions']):
        raise ValueError('The action trace is incomplete.')
    previous = clocks[0]
    actions = []
    for name, event in zip(scenario['actions'], events):
        if (not isinstance(event, dict) or event.get('action') != name or event.get('observed') is not True or
                type(event.get('start_qpc')) is not int or type(event.get('end_qpc')) is not int or
                not previous <= event['start_qpc'] < event['end_qpc'] <= clocks[-1]):
            raise ValueError('Action sequence, ordering or frame-window coverage differs.')
        previous = event['end_qpc']
        # Include a long interval crossing either boundary, even when its final
        # Present() occurs after the recorded action. Never silently drop the hitch.
        # The first interval lacks an observed prior Present and is excluded from
        # action attribution; action windows already start at/after clocks[0].
        action = action_statistics(values, clocks, event['start_qpc'], event['end_qpc'], scenario['refresh_hz'])
        action['action'] = name
        action['duration_ms'] = (1000 * (event['end_qpc'] - event['start_qpc']) / qpc_frequency
                                 if qpc_frequency is not None else None)
        actions.append(action)
    stats = statistics_for(values, scenario['refresh_hz'])
    return {'kind': spec['kind'], 'started_ns': spec['started_ns'], 'ended_ns': spec['ended_ns'],
            'capture_sha256': capture_sha, 'trace_sha256': trace_sha, 'mod_state_sha256': mods_sha,
            'apex_candidate_sha256': artifact_sha, 'csv_sha256': analysis['csv_sha256'],
            'collector_sha256': capture['collector_sha256'], 'present_runtime': runtime,
            'collector_options': normalized_command, 'configured_seconds': duration,
            'fps_claimed': False, 'statistics': stats, 'action_windows': actions}


def compare(manifest, manifest_dir):
    if (not isinstance(manifest, dict) or set(manifest) != {'schema', 'scenario', 'runs'} or
            type(manifest['schema']) is not int or manifest['schema'] != 1):
        raise ValueError('Unknown benchmark manifest schema.')
    scenario = validate_scenario(manifest['scenario'])
    runs = manifest['runs']
    if not isinstance(runs, list) or len(runs) < 4 or len(runs) > 40 or len(runs) % 2:
        raise ValueError('Require at least two bounded baseline/Apex pairs.')
    if any(not isinstance(run, dict) or run.get('kind') not in ('baseline', 'apex') for run in runs):
        raise ValueError('Each run needs an exact benchmark mode.')
    order = [(runs[i]['kind'], runs[i + 1]['kind']) for i in range(0, len(runs), 2)]
    if any(set(pair) != {'baseline', 'apex'} for pair in order) or len(set(order)) != 2:
        raise ValueError('Use both baseline→Apex and Apex→baseline pair orders.')
    results = [analyze_run(run, scenario, Path(manifest_dir)) for run in runs]
    if any(a['ended_ns'] >= b['started_ns'] for a, b in zip(results, results[1:])):
        raise ValueError('Runs overlap or are not in recorded order.')
    if len({r['capture_sha256'] for r in results}) != len(results) or len({r['trace_sha256'] for r in results}) != len(results):
        raise ValueError('A capture or action trace was reused across recordings.')
    if len({r['csv_sha256'] for r in results}) != len(results):
        raise ValueError('Raw CSV evidence was reused across recordings.')
    if len({r['collector_sha256'] for r in results}) != 1 or len({r['present_runtime'] for r in results}) != 1:
        raise ValueError('Collector or presentation runtime differs.')
    if len({(tuple(r['collector_options']), r['configured_seconds']) for r in results}) != 1:
        raise ValueError('Collector options or duration differ between recordings.')
    if len({r['apex_candidate_sha256'] for r in results if r['kind'] == 'apex'}) != 1:
        raise ValueError('Apex candidate changed between recordings.')
    comparisons = []
    for i in range(0, len(results), 2):
        pair = {r['kind']: r for r in results[i:i + 2]}
        a, b = pair['baseline']['statistics'], pair['apex']['statistics']
        action_deltas = []
        for base_action, apex_action in zip(pair['baseline']['action_windows'], pair['apex']['action_windows']):
            if base_action['action'] != apex_action['action']:
                raise ValueError('Paired action windows differ.')
            action_deltas.append({'action': base_action['action'],
                                  'baseline_frames': base_action['frames'], 'apex_frames': apex_action['frames'],
                                  'duration_delta_ms': (None if base_action['duration_ms'] is None or apex_action['duration_ms'] is None
                                                        else apex_action['duration_ms'] - base_action['duration_ms']),
                                  'p50_delta_ms': apex_action['p50_ms'] - base_action['p50_ms'],
                                  'p95_delta_ms': apex_action['p95_ms'] - base_action['p95_ms'],
                                  'p99_delta_ms': apex_action['p99_ms'] - base_action['p99_ms'],
                                  'max_delta_ms': apex_action['max_ms'] - base_action['max_ms']})
        comparisons.append({'order': list(order[i // 2]), 'apex_minus_baseline_ms': {
            key: None if a[key] is None or b[key] is None else b[key] - a[key]
            for key in ('mean_ms', 'p50_ms', 'p95_ms', 'p99_ms', 'p99_9_ms', 'max_ms', 'slowest_1pct_mean_ms')},
            'action_windows': action_deltas})
    return {'schema': 1, 'comparable_under_declared_conditions': True, 'scenario': scenario,
            'runs': results, 'pairs': comparisons, 'displayed_fps_measured': False,
            'hitch_free_claimed': False, 'performance_pass': False,
            'limitations': ['Scenario, mod-state and action observation evidence are supplied by the experiment runner.',
                'Present intervals are not displayed frame times or an input-to-photon measurement.',
                'Action-window comparisons can contain different frame counts; tail percentiles and maxima are sensitive to sample size and do not establish causation.',
                'Action duration is derived only from validated offline QPC frequency; matching labels or durations do not prove equal work.',
                'A finite matched sample cannot prove that all hitching is eliminated.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest, manifest_sha = load_json(args.manifest)
    result = compare(manifest, args.manifest.resolve().parent)
    result['manifest_sha256'] = manifest_sha
    output = args.output.resolve()
    if ROOT / '.work' not in output.parents:
        raise ValueError('Write the new comparison only inside this checkout’s .work directory.')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'ok': True, 'output': str(output), 'performance_pass': False}))


if __name__ == '__main__':
    main()
