import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))
import hitch_stage as stage
import compare_hitch_stages as incremental
import capture_frame_intervals as capture
import test_compare_frame_runs as frame_fixture


def definition(name='hybrid', features=None):
    features = ['hybrid'] if features is None else features
    return dict(id=name, features=features,
        artifacts=[dict(path='Apex/ApexOccultHybrid.ts4script', sha256='a' * 64)] if features else [],
        loaded=dict(apex_script_loaded=bool(features), apex_cas_package_loaded=False, apex_overlay_loaded=False))


class StageIdentityTests(unittest.TestCase):
    def state(self, stage_def=None):
        value = definition() if stage_def is None else stage_def
        return dict(schema=2, target_pid=123, process_creation_filetime=42,
            inventory_and_loaded_modules_observed=True, observation_method='synthetic fixture only',
            other_mods_sha256='b' * 64, stage=value, stage_sha256=stage.digest(value), **value['loaded'])

    def test_no_mod_and_partial_components_are_distinct_valid_stage_states(self):
        for value in (definition('vanilla', []), definition()):
            state = self.state(value)
            self.assertEqual(stage.validate_mod_state(state, 123, 42), value)
            self.assertTrue(capture.validate_mod_state(state, 'stage', 123, 42))

    def test_cannot_relabel_a_partial_build_as_full_apex_or_no_mod(self):
        for mode in ('apex', 'baseline'):
            with self.assertRaises(ValueError):
                capture.validate_mod_state(self.state(), mode, 123, 42)

    def test_loaded_flags_inventory_hash_and_process_are_bound(self):
        for key, changed in (('apex_script_loaded', False), ('stage_sha256', 'c' * 64),
                ('target_pid', 124), ('process_creation_filetime', 43), ('schema', True),
                ('inventory_and_loaded_modules_observed', False)):
            value = self.state(); value[key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                stage.validate_mod_state(value, 123, 42)
        value = self.state(); value['stage']['artifacts'][0]['sha256'] = 'c' * 64
        with self.assertRaises(ValueError):
            stage.validate_mod_state(value, 123, 42)

    def test_overlay_requires_inactive_profilers(self):
        value = self.state(); value['stage']['loaded']['apex_overlay_loaded'] = True
        value['apex_overlay_loaded'] = True; value['stage_sha256'] = stage.digest(value['stage'])
        with self.assertRaisesRegex(ValueError, 'profilers'):
            stage.validate_mod_state(value, 123, 42)
        value['native_service_profile'] = dict(enabled=False, installed=False, inflight=0)
        value['native_gfx_snapshot_profile'] = dict(enabled=False, prepared=False, active_heap_hooks=False, inflight=0)
        self.assertTrue(stage.validate_mod_state(value, 123, 42))
        value['native_service_profile']['installed'] = True
        with self.assertRaises(ValueError): stage.validate_mod_state(value, 123, 42)

    def test_inventory_refuses_aliases_traversal_noncanonical_and_wrong_hashes(self):
        for name in ('../save', '/absolute', 'Apex\\x', 'Apex/./x', 'Apex//x', 'C:/x', '', 'Apex/x.', 'Apex/x ', 'Apex/x?'):
            value = definition(); value['artifacts'][0]['path'] = name
            with self.subTest(name=name), self.assertRaises(ValueError): stage.validate_definition(value)
        value = definition(); value['artifacts'].append(dict(path='apex/apexocculthybrid.ts4script', sha256='b' * 64))
        with self.assertRaises(ValueError): stage.validate_definition(value)
        value = definition(); value['artifacts'][0]['sha256'] = 'z' * 64
        with self.assertRaises(ValueError): stage.validate_definition(value)

    def test_add_exactly_one_feature_without_dropping_any(self):
        first, second = definition('vanilla', []), definition()
        third = definition('ui', ['hybrid', 'maru-ui'])
        self.assertEqual(stage.validate_ladder([first, second, third]), [first, second, third])
        for ladder in ([second, third], [first, third], [first, second, definition('ui', ['maru-ui'])],
                [first, second, definition('hybrid', ['hybrid', 'maru-ui'])]):
            with self.subTest(ladder=ladder), self.assertRaises(ValueError): stage.validate_ladder(ladder)

    def test_empty_control_cannot_hide_installed_apex(self):
        value = definition('vanilla', []); value['artifacts'] = definition()['artifacts']
        with self.assertRaises(ValueError): stage.validate_definition(value)

    def test_mixed_zero_and_nonzero_etw_losses_never_pass(self):
        for text in ('0 events lost; 12 buffers dropped', 'Lost 0 events and 12 buffers',
                     'No buffers were dropped; lost 7 events', 'events lost: unknown'):
            with self.subTest(text=text): self.assertTrue(capture.event_loss(text))
        self.assertFalse(capture.event_loss('0 events lost; 0 buffers dropped'))

    def test_duplicate_json_keys_cannot_conceal_evidence(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'evidence.json'
            path.write_text('{"state":"invalid","state":"completed"}')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                incremental.frames.load_json(path)


class StageEvidenceTests(unittest.TestCase):
    def setUp(self):
        fixture = frame_fixture.MatchedFrameComparisonTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.directory = fixture.root
        control, candidate = definition('vanilla', []), definition()
        self.manifest = dict(schema=2, scenario=fixture.scenario, stages=[control, candidate],
                             comparisons=[dict(control='vanilla', candidate='hybrid', runs=fixture.manifest['runs'])])
        for run in self.manifest['comparisons'][0]['runs']:
            definition_value = control if run['kind'] == 'baseline' else candidate
            run['kind'] = definition_value['id']
            mod_path = Path(run['mod_state']); mods = json.loads(mod_path.read_text())
            mods.update(schema=2, stage=definition_value, stage_sha256=stage.digest(definition_value), **definition_value['loaded'])
            mods.pop('apex_candidate_sha256')
            mod_path.write_text(json.dumps(mods))
            capture_path = Path(run['capture']); captured = json.loads(capture_path.read_text())
            captured.update(benchmark_mode='stage', stage_id=definition_value['id'], stage_sha256=stage.digest(definition_value),
                            mod_state_sha256=hashlib.sha256(mod_path.read_bytes()).hexdigest())
            capture_path.write_text(json.dumps(captured))
            trace_path = Path(run['actions']); trace = json.loads(trace_path.read_text())
            trace['capture_sha256'] = hashlib.sha256(capture_path.read_bytes()).hexdigest()
            trace_path.write_text(json.dumps(trace))

    def test_stage_pair_reports_hitch_counts_and_rates_with_unequal_windows(self):
        frame_fixture.set_unequal_action_hitch_fixture(self.manifest['comparisons'][0]['runs'])
        frame_fixture.set_unequal_action_hitch_fixture(self.manifest['comparisons'][0]['runs'][2:])
        result = incremental.compare(self.manifest, self.directory)
        action = result['comparisons'][0]['pairs'][0]['action_windows'][0]
        self.assertEqual((action['control_frames'], action['candidate_frames']), (5, 6))
        self.assertEqual((action['control_over_33_3ms'], action['candidate_over_33_3ms']), (1, 2))
        self.assertEqual(action['over_33_3ms_count_delta'], 1)
        self.assertEqual(action['control_over_33_3ms_per_1000'], 200)
        self.assertAlmostEqual(action['candidate_over_33_3ms_per_1000'], 1000 / 3)
        self.assertAlmostEqual(action['over_33_3ms_per_1000_delta'], 1000 / 3 - 200)
        reverse = result['comparisons'][0]['pairs'][1]['action_windows'][0]
        self.assertEqual(reverse['over_33_3ms_count_delta'], -1)
        self.assertAlmostEqual(reverse['over_33_3ms_per_1000_delta'], 200 - 1000 / 3)
        self.assertFalse(result['performance_pass'])

    def test_real_analysis_of_synthetic_csv_stops_on_measured_slowdown(self):
        result = incremental.compare(self.manifest, self.directory)
        self.assertEqual(result['stopped_at_stage'], 'hybrid')
        self.assertEqual(result['state'], 'slowdown_observed')
        self.assertEqual(result['comparisons'][0]['pairs'][0]['candidate_minus_control']['max_ms'], 40)
        action = result['comparisons'][0]['pairs'][0]['action_windows'][0]
        self.assertEqual(action['control_frames'], 5)
        self.assertEqual(action['candidate_frames'], 5)
        self.assertEqual(action['p95_delta_ms'], 1)
        self.assertEqual(action['p99_delta_ms'], 1)
        self.assertFalse(result['performance_pass']); self.assertFalse(result['hitch_free_claimed'])

    def test_later_stages_are_not_evaluated_after_a_slowdown(self):
        self.manifest['stages'].append(definition('ui', ['hybrid', 'maru-ui']))
        self.manifest['comparisons'].append({'invalid_later_evidence': True})
        result = incremental.compare(self.manifest, self.directory)
        self.assertEqual(result['not_evaluated'], ['ui'])

    def test_no_runs_reports_awaiting_measurements_without_success(self):
        self.manifest['comparisons'] = []
        result = incremental.compare(self.manifest, self.directory)
        self.assertEqual(result['state'], 'awaiting_measurements')
        self.assertEqual(result['not_evaluated'], ['hybrid'])
        self.assertFalse(result['performance_pass'])

    def test_equal_intervals_still_require_correctness_review(self):
        import csv
        for run in self.manifest['comparisons'][0]['runs']:
            path = Path(run['csv'])
            with path.open(newline='') as stream:
                reader = csv.DictReader(stream); fields = reader.fieldnames; rows = list(reader)
            for row in rows: row['MsBetweenPresents'] = '10'
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
            cpath = Path(run['capture']); captured = json.loads(cpath.read_text())
            captured['analysis']['csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            cpath.write_text(json.dumps(captured))
            tpath = Path(run['actions']); trace = json.loads(tpath.read_text())
            trace['capture_sha256'] = hashlib.sha256(cpath.read_bytes()).hexdigest()
            tpath.write_text(json.dumps(trace))
        result = incremental.compare(self.manifest, self.directory)
        self.assertEqual(result['state'], 'review_required')
        self.assertIsNone(result['stopped_at_stage'])
        self.assertEqual(result['comparisons'][0]['next_action'], 'review_correctness_before_next_stage')
        self.assertFalse(result['performance_pass'])

    def test_reject_wrong_stage_or_changed_non_apex_content(self):
        for mutate in (lambda m: m['stages'][1]['artifacts'][0].update(sha256='e' * 64),
                       lambda m: m['comparisons'][0].update(candidate='unknown'),
                       lambda m: m['scenario'].update(other_mods_sha256='f' * 64)):
            value = copy.deepcopy(self.manifest); mutate(value)
            with self.assertRaises(ValueError): incremental.compare(value, self.directory)

    def test_refuse_one_order_overlapping_runs_and_missing_action_proof(self):
        for change in ('order', 'overlap', 'actions'):
            value = copy.deepcopy(self.manifest)
            runs = value['comparisons'][0]['runs']
            if change == 'order': runs[2:] = runs[:2]
            elif change == 'overlap': runs[1]['started_ns'] = runs[0]['started_ns']
            else:
                path = Path(runs[0]['actions']); trace = json.loads(path.read_text())
                trace['ui_transitions_verified'] = False; path.write_text(json.dumps(trace))
            with self.subTest(change=change), self.assertRaises(ValueError): incremental.compare(value, self.directory)


if __name__ == '__main__': unittest.main()
