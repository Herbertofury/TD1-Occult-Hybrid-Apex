"""Offline synthetic coverage of the actual staged report path."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import compare_hitch_stages as report
import hitch_stage
import mod_provenance

FLAGS = dict(apex_script_loaded=True, apex_cas_package_loaded=False, apex_overlay_loaded=False)


def stage(name, features, artifacts, flags):
    return dict(id=name, features=features, artifacts=artifacts, loaded=dict(flags))


def row(path, char):
    return dict(path=path, sha256=char * 64)


def setup():
    base = stage('base', [], [], dict.fromkeys(FLAGS, False))
    one = stage('one', ['hybrid'], [row('Apex/script.ts4script', 'a')], FLAGS)
    two = stage('two', ['hybrid', 'ui'], [row('Apex/script.ts4script', 'a')], FLAGS)
    three = stage('three', ['hybrid', 'overlay', 'ui'], [row('Apex/script.ts4script', 'a')], FLAGS)
    stages = [base, one, two, three]
    comparisons = []
    for x, y in zip(stages, stages[1:]):
        comparisons.append(dict(control=x['id'], candidate=y['id'], runs=[dict(kind=k) for k in
            (x['id'], y['id'], y['id'], x['id'])]))
    return dict(schema=2, scenario={}, stages=stages, comparisons=comparisons)


def perform(manifest, slowdown=None, reviews=None):
    i = [0]
    def analyze(spec, scenario, directory, stage):
        i[0] += 1
        value = 11 if spec['kind'] == slowdown else 10
        return dict(kind=spec['kind'], started_ns=i[0]*10, ended_ns=i[0]*10+1,
            capture_sha256='capture'+str(i[0]), trace_sha256='trace'+str(i[0]), csv_sha256='csv'+str(i[0]),
            collector_sha256='collector', present_runtime='DXGI', collector_options=[], configured_seconds=10,
            statistics=dict(p95_ms=value, p99_ms=value, max_ms=value, over_33_3ms_per_1000=0),
            action_windows=[dict(action='open', max_ms=value, frames=10,
                over_33_3ms=0, over_33_3ms_per_1000=0, duration_ms=10,
                p95_ms=value, p99_ms=value)])
    with patch.object(report.frames, 'validate_scenario', return_value={}), patch.object(report.frames, 'analyze_run', side_effect=analyze):
        return report.compare(manifest, Path('.'), continuity_reviews=reviews)


def review_for(manifest):
    before, after = manifest['stages'][1:3]
    return dict(schema=1, reviews=[dict(control_stage_sha256=hitch_stage.digest(before),
        candidate_stage_sha256=hitch_stage.digest(after),
        replaced_artifacts=report.transition_continuity(before, after)['replaced_artifacts'],
        review_evidence_sha256='e'*64)])


class ContinuityReportTests(unittest.TestCase):
    def test_compatible_unchanged_manifest_completes(self):
        result = perform(setup())
        self.assertEqual(result['state'], 'review_required')
        self.assertEqual(len(result['comparisons']), 3)
        self.assertEqual(result['comparisons'][1]['continuity']['replaced_artifacts'], [])
        self.assertFalse(result['comparisons'][1]['continuity']['retention_proven'])
        self.assertFalse(result['performance_pass'])

    def test_removal_rejected_by_actual_report_path(self):
        manifest = setup()
        manifest['stages'][2]['artifacts'] = [row('Apex/other.package', 'b')]
        with self.assertRaisesRegex(ValueError, 'removes'):
            perform(manifest)

    def test_lost_flag_rejected_even_when_other_flag_true(self):
        manifest = setup()
        manifest['stages'][2]['loaded'].update(apex_script_loaded=False, apex_cas_package_loaded=True)
        with self.assertRaisesRegex(ValueError, 'drops'):
            perform(manifest)

    def test_replacement_is_reported_and_stops_later_stage(self):
        manifest = setup()
        manifest['stages'][2]['artifacts'][0]['sha256'] = 'b'*64
        result = perform(manifest)
        self.assertEqual(result['state'], 'review_required')
        self.assertEqual(result['not_evaluated'], ['three'])
        self.assertEqual(result['comparisons'][1]['next_action'], 'review_correctness_before_next_stage')
        self.assertTrue(result['comparisons'][1]['continuity']['review_required'])
        self.assertEqual(result['comparisons'][1]['continuity']['replaced_artifacts'],
            [dict(path='Apex/script.ts4script', previous_sha256='a'*64, current_sha256='b'*64)])

    def test_slowdown_stops_before_later_bad_transition(self):
        manifest = setup()
        manifest['stages'][2]['artifacts'] = [row('Apex/other.package', 'b')]
        result = perform(manifest, slowdown='one')
        self.assertEqual(result['state'], 'slowdown_observed')
        self.assertEqual(result['not_evaluated'], ['two', 'three'])

    def test_slowdown_precedes_replacement_review_but_retains_hashes(self):
        manifest = setup()
        manifest['stages'][2]['artifacts'][0]['sha256'] = 'b'*64
        result = perform(manifest, slowdown='two')
        self.assertEqual(result['state'], 'slowdown_observed')
        self.assertEqual(result['stopped_at_stage'], 'two')
        self.assertTrue(result['comparisons'][1]['continuity']['review_required'])
        self.assertEqual(result['comparisons'][1]['next_action'], 'diagnose_this_stage')
        self.assertEqual(result['not_evaluated'], ['three'])

    def test_bound_review_declaration_allows_continuation_without_proving_retention(self):
        manifest = setup(); manifest['stages'][2]['artifacts'][0]['sha256'] = 'b'*64
        manifest['stages'][3]['artifacts'][0]['sha256'] = 'b'*64
        result = perform(manifest, reviews=review_for(manifest))
        self.assertEqual(result['state'], 'review_required')
        self.assertEqual(len(result['comparisons']), 3)
        record = result['comparisons'][1]['continuity']
        self.assertTrue(record['review_declaration_matched'])
        self.assertTrue(record['review_required'])
        self.assertEqual(record['review_evidence_sha256'], 'e'*64)
        self.assertFalse(record['retention_proven'])
        self.assertFalse(result['performance_pass'])

    def test_changed_stage_or_review_identity_cannot_authorize_continuation(self):
        manifest = setup(); manifest['stages'][2]['artifacts'][0]['sha256'] = 'b'*64
        for mutation in ('old', 'new', 'stage', 'review', 'duplicate', 'unknown'):
            declaration = review_for(manifest)
            record = declaration['reviews'][0]
            if mutation == 'old': record['replaced_artifacts'][0]['previous_sha256'] = 'c'*64
            elif mutation == 'new': record['replaced_artifacts'][0]['current_sha256'] = 'c'*64
            elif mutation == 'stage': record['candidate_stage_sha256'] = 'c'*64
            elif mutation == 'review': record['review_evidence_sha256'] = 'bad'
            elif mutation == 'duplicate': declaration['reviews'].append(copy.deepcopy(record))
            else: record['unknown'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                perform(manifest, reviews=declaration)

    def test_review_declaration_cannot_hide_slowdown(self):
        manifest = setup(); manifest['stages'][2]['artifacts'][0]['sha256'] = 'b'*64
        result = perform(manifest, slowdown='two', reviews=review_for(manifest))
        self.assertEqual(result['state'], 'slowdown_observed')
        self.assertEqual(result['not_evaluated'], ['three'])
        self.assertTrue(result['comparisons'][1]['continuity']['review_declaration_matched'])

    def test_ambiguous_path_aliases_refused_but_added_artifact_accepted(self):
        before = setup()['stages'][1]
        after = stage('two', ['hybrid', 'ui'], [row('apex/script.ts4script','a'), row('Apex/ui.package','b')], FLAGS)
        with self.assertRaisesRegex(ValueError, 'spelling'):
            report.transition_continuity(before, after)
        after['artifacts'][0]['path'] = 'Apex/script.ts4script'
        self.assertEqual(report.transition_continuity(before, after)['replaced_artifacts'], [])
        before['artifacts'][0]['path'] = 'Apex/straße.package'
        after['artifacts'][0]['path'] = 'Apex/strasse.package'
        with self.assertRaisesRegex(ValueError, 'spelling'):
            report.transition_continuity(before, after)

    def test_unevaluated_stages_do_not_create_continuity_claim(self):
        manifest = setup(); manifest['comparisons'] = []
        result = perform(manifest)
        self.assertEqual(result['state'], 'awaiting_measurements')
        self.assertEqual(result['comparisons'], [])
        self.assertEqual(result['not_evaluated'], ['one', 'two', 'three'])

    def test_cli_hashes_optional_review_declaration_in_output(self):
        manifest = setup(); manifest['stages'][2]['artifacts'][0]['sha256'] = 'b'*64
        declaration = review_for(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / '.work').mkdir()
            mp, rp, out = root/'manifest.json', root/'.work'/'review.json', root/'.work'/'report.json'
            mp.write_text(json.dumps(manifest), encoding='utf-8')
            rp.write_text(json.dumps(declaration), encoding='utf-8')
            fake = {'state': 'review_required', 'performance_pass': False}
            args = ['compare_hitch_stages.py', '--manifest', str(mp), '--output', str(out), '--continuity-review', str(rp)]
            with patch.object(sys, 'argv', args), patch.object(report.frames, 'ROOT', root), \
                    patch.object(report, 'compare', return_value=fake) as compare:
                report.main()
            value = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(value['continuity_review_declarations_sha256'], hashlib.sha256(rp.read_bytes()).hexdigest())
            self.assertEqual(compare.call_args[1]['continuity_reviews'], declaration)

    def test_cli_refuses_review_outside_private_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.work').mkdir()
            mp,rp,out=root/'manifest.json',root/'review.json',root/'.work'/'out.json'
            mp.write_text('{}',encoding='utf-8');rp.write_text('{}',encoding='utf-8')
            args=['compare_hitch_stages.py','--manifest',str(mp),'--output',str(out),'--continuity-review',str(rp)]
            with patch.object(sys,'argv',args),patch.object(report.frames,'ROOT',root), \
                    patch.object(mod_provenance,'_unlinked',wraps=mod_provenance._unlinked) as unlinked:
                with self.assertRaisesRegex(ValueError,'inside private'):
                    report.main()
            self.assertNotIn(str(rp),[str(call[0][0]) for call in unlinked.call_args_list])
            self.assertFalse(out.exists())

    def test_cli_refuses_review_changed_during_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.work').mkdir()
            mp,rp,out=root/'manifest.json',root/'.work'/'review.json',root/'.work'/'out.json'
            mp.write_text('{}',encoding='utf-8');rp.write_text('{}',encoding='utf-8')
            def changed(*args,**kwargs):
                rp.write_text('{"changed":true}',encoding='utf-8')
                return {'state':'review_required','performance_pass':False}
            args=['compare_hitch_stages.py','--manifest',str(mp),'--output',str(out),'--continuity-review',str(rp)]
            with patch.object(sys,'argv',args),patch.object(report.frames,'ROOT',root),patch.object(report,'compare',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'changed during comparison'):
                    report.main()
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
