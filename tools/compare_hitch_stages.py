"""Compare cumulative feature stages; stop at the first observed slowdown.

Consumes separately collected evidence only. Does not launch the game, install
features, edit saves, certify correctness or prove a cause for a regression.
"""
import argparse
import json
from pathlib import Path

import compare_frame_runs as frames
import hitch_stage

TAIL_METRICS = ('p95_ms', 'p99_ms', 'max_ms', 'over_33_3ms_per_1000')


def compare(manifest, directory):
    if (not isinstance(manifest, dict) or
            set(manifest) != {'schema', 'scenario', 'stages', 'comparisons'} or
            type(manifest['schema']) is not int or manifest['schema'] != 2):
        raise ValueError('Exact incremental experiment schema 2 required.')
    scenario = frames.validate_scenario(manifest['scenario'])
    stages = hitch_stage.validate_ladder(manifest['stages'])
    comparisons = manifest['comparisons']
    if not isinstance(comparisons, list) or len(comparisons) > len(stages) - 1:
        raise ValueError('Comparisons must follow the bounded cumulative stage order.')
    results, captures, traces, csvs = [], set(), set(), set()
    previous_end = 0
    collector_identity = None
    stopped = None
    for index, comparison in enumerate(comparisons):
        control, candidate = stages[index:index + 2]
        if (not isinstance(comparison, dict) or set(comparison) != {'control', 'candidate', 'runs'} or
                comparison['control'] != control['id'] or comparison['candidate'] != candidate['id']):
            raise ValueError('Compare each stage to its immediate predecessor without skipping stages.')
        runs = comparison['runs']
        if not isinstance(runs, list) or not 4 <= len(runs) <= 40 or len(runs) % 2:
            raise ValueError('Require at least two opposite-order pairs for each added feature group.')
        if any(not isinstance(r, dict) or r.get('kind') not in (control['id'], candidate['id']) for r in runs):
            raise ValueError('Run identity differs from this stage pair.')
        orders = [(runs[i]['kind'], runs[i + 1]['kind']) for i in range(0, len(runs), 2)]
        if (any(set(pair) != {control['id'], candidate['id']} for pair in orders) or
                len(set(orders)) != 2):
            raise ValueError('Each stage comparison needs both run orders.')
        analyzed = []
        for spec in runs:
            stage = control if spec['kind'] == control['id'] else candidate
            run = frames.analyze_run(spec, scenario, Path(directory), stage=stage)
            if run['started_ns'] <= previous_end:
                raise ValueError('Stage captures overlap or are not in chronological order.')
            previous_end = run['ended_ns']
            if (run['capture_sha256'] in captures or run['trace_sha256'] in traces or
                    run['csv_sha256'] in csvs):
                raise ValueError('Every stage run needs fresh capture and transition evidence.')
            captures.add(run['capture_sha256']); traces.add(run['trace_sha256']); csvs.add(run['csv_sha256'])
            identity = (run['collector_sha256'], run['present_runtime'],
                        tuple(run['collector_options']), run['configured_seconds'])
            if collector_identity is None:
                collector_identity = identity
            elif collector_identity != identity:
                raise ValueError('Collector, options, runtime or duration changed between stages.')
            analyzed.append(run)
        pairs, slowdowns = [], []
        for i in range(0, len(analyzed), 2):
            pair = {r['kind']: r for r in analyzed[i:i + 2]}
            a, b = pair[control['id']], pair[candidate['id']]
            deltas = {metric: b['statistics'][metric] - a['statistics'][metric] for metric in TAIL_METRICS}
            action_deltas = []
            for before, after in zip(a['action_windows'], b['action_windows']):
                if before['action'] != after['action']:
                    raise ValueError('Action windows differ between stages.')
                delta = after['max_ms'] - before['max_ms']
                action_deltas.append({'action': before['action'], 'max_delta_ms': delta,
                    'control_over_33_3ms': before['over_33_3ms'],
                    'candidate_over_33_3ms': after['over_33_3ms'],
                    'over_33_3ms_count_delta': after['over_33_3ms'] - before['over_33_3ms'],
                    'control_over_33_3ms_per_1000': before['over_33_3ms_per_1000'],
                    'candidate_over_33_3ms_per_1000': after['over_33_3ms_per_1000'],
                    'over_33_3ms_per_1000_delta': after['over_33_3ms_per_1000'] - before['over_33_3ms_per_1000'],
                    'duration_delta_ms': (None if before['duration_ms'] is None or after['duration_ms'] is None
                                          else after['duration_ms'] - before['duration_ms']),
                    'p95_delta_ms': after['p95_ms'] - before['p95_ms'],
                    'p99_delta_ms': after['p99_ms'] - before['p99_ms'],
                    'control_frames': before['frames'], 'candidate_frames': after['frames']})
                if delta > 0:
                    slowdowns.append({'pair': i // 2, 'action': before['action'],
                                      'metric': 'max_ms', 'delta': delta})
            slowdowns.extend({'pair': i // 2, 'metric': metric, 'delta': delta}
                             for metric, delta in deltas.items() if delta > 0)
            pairs.append({'order': list(orders[i // 2]), 'candidate_minus_control': deltas,
                          'action_windows': action_deltas})
        results.append({'control': control['id'], 'candidate': candidate['id'],
            'added_feature': next(iter(set(candidate['features']) - set(control['features']))),
            'runs': analyzed, 'pairs': pairs, 'slowdowns': slowdowns,
            'next_action': 'diagnose_this_stage' if slowdowns else 'review_correctness_before_next_stage'})
        if slowdowns:
            stopped = candidate['id']
            break
    measured = len(results)
    return {'schema': 2, 'scenario': scenario, 'comparisons': results,
        'stopped_at_stage': stopped,
        'not_evaluated': [s['id'] for s in stages[measured + 1:]],
        'state': 'slowdown_observed' if stopped else ('awaiting_measurements' if measured < len(stages) - 1 else 'review_required'),
        'displayed_fps_measured': False, 'performance_pass': False, 'hitch_free_claimed': False,
        'limitations': ['Feature inventories and actual-load/UI-transition observations are runner-supplied declarations.',
            'Legacy offline captures have no bound parser log; see parse_log_verification for each run. The legacy loss declaration is not independent proof.',
            'Any positive tail/action-maximum delta stops evaluation; noise requires diagnosis and fresh repeats, not a causal claim.',
            'Action-window percentiles are descriptive and sample-size sensitive, particularly for short actions; intervals may overlap adjacent windows.',
            'Raw hitch counts depend on window duration and frame count; counts per 1000 overlapping intervals are not rates per unit time and remain sample-size sensitive.',
            'A present interval crossing adjacent action windows is counted in both; action-window counts must not be summed as unique hitches.',
            'Action duration uses only validated offline QPC frequency; matching labels or durations do not prove equivalent work.',
            'Equal source presence or passing fixture tests does not establish feature parity.',
            'Present intervals are not displayed frame times or input-to-photon latency.',
            'No game, mod installation, profile, save or external CAS project was changed by this report.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest, manifest_sha = frames.load_json(args.manifest)
    result = compare(manifest, args.manifest.resolve().parent)
    result['manifest_sha256'] = manifest_sha
    output = args.output.resolve()
    if (frames.ROOT / '.work').resolve() not in output.parents:
        raise ValueError('Write new evidence only inside this checkout .work directory.')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(output), 'state': result['state'], 'performance_pass': False}))


if __name__ == '__main__':
    main()
