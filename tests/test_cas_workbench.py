import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
from apex_core import cas_ui
import cas_workbench as workbench
import test_cas_hair_audit as fixture


class CasWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.CasHairAuditTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.game = self.fixture.game
        original_client = self.game.client
        self.menu = cas_ui.PANELS['clothing_hair']
        self.layer, self.fault, self.preset = 1, None, -1
        def client():
            value = original_client()
            value.update(menu_state=self.menu, panel_visible=True)
            value['sim'].update(allOccultTypes=65, occultType=64, occultLayer=self.layer, age=16)
            value['native_context']['forced_full_edit'] = {'query':'returned-value', 'value':True}
            return value
        self.game.client = client
        self.original_request = self.game.request

    def request(self, state, action, sim_id=None, **kwargs):
        observed = kwargs.get('submission_observer')
        if observed is not None: observed(action, uuid.uuid4().hex)
        if action != 'cas_ui_request':
            return self.original_request(state, action, sim_id, **kwargs)
        operation = json.loads(kwargs['value'])
        op = operation['operation']
        if op == 'status': return self.original_request(state, action, sim_id, **kwargs)
        self.game.submitted.append(operation)
        rid = '{:032x}'.format(len(self.game.submitted))
        if 'panel' in operation: self.menu = cas_ui.panel(operation['panel'])
        client = self.game.client()
        if op in ('catalog', 'swatches'):
            client['control'] = {'operation':op, 'offset':operation['offset'], 'limit':operation['limit'], 'total':0, 'items':[]}
        elif op != 'panel': self.fail('Unexpected workbench operation ' + op)
        result = {'ok':True, 'protocol':1, 'operation':op, 'cas_request_id':rid,
            'cas_request_state':'completed', 'client':client, 'ui_transition_verified':True}
        if self.fault:
            changed = self.fault(operation, result)
            if changed is not None: result = changed
        self.game.pending[rid] = result
        return {'ok':False, 'outcome':'pending-client', 'cas_request_id':rid}

    def run_workbench(self, **kwargs):
        original = self.game.files(self.game.original)
        saves = self.game.files(self.game.profile)
        result = workbench.run(self.game.state, self.game.output, self.game.identity, self.request, fixture.SIM, **kwargs)
        self.assertEqual(original, self.game.files(self.game.original))
        self.assertEqual(saves, self.game.files(self.game.profile))
        proof = json.loads(self.game.output.read_text())
        raw = self.game.output.with_suffix('.jsonl').read_bytes()
        for step in proof['steps']:
            if 'offset' not in step: continue
            data = raw[step['offset']:step['offset']+step['bytes']]
            self.assertEqual(hashlib.sha256(data).hexdigest(), step['sha256'])
            self.assertEqual(json.loads(data)['operation'], step['operation'])
            self.assertTrue(step['owner_requests'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), proof['raw_sha256'])
        self.assertFalse(proof['accept_submitted']); self.assertFalse(proof['save_submitted'])
        return result, proof, [json.loads(line) for line in raw.splitlines()]

    def test_complete_registry_has_no_small_navigation_subset_limit(self):
        result, proof, rows = self.run_workbench()
        self.assertTrue(result['ok'], result.get('error'))
        self.assertEqual([item['panel'] for item in proof['panels']], list(cas_ui.PANELS))
        self.assertEqual(len(proof['panels']), 77)
        self.assertTrue(all(item['discovered'] for item in proof['panels']))
        self.assertEqual(rows[0]['result']['client']['futureSnapshotField']['identity'], fixture.EXACT_HIGH_ID)
        self.assertFalse(proof['all_edit_paths_complete'])
        self.assertFalse(proof['full_catalog_inventory'])
        self.assertFalse(proof['live_retention_verified'])

    def test_alternate_editor_is_allowed_but_source_accept_still_requires_primary(self):
        value = self.game.client()
        self.assertEqual(workbench.context(value, fixture.SIM)['occultLayer'], 1)
        with self.assertRaisesRegex(ValueError, 'primary'): cas_ui.validate_accept_context(value)
        self.layer = 0
        cas_ui.validate_accept_context(self.game.client())
        self.assertEqual(workbench.context(self.game.client(), fixture.SIM)['occultLayer'], 0)

    def test_wrong_form_context_after_query_stops_without_next_panel(self):
        def fault(op, result):
            if op['operation'] == 'catalog': result['client']['sim']['occultLayer'] = 0
        self.fault = fault
        result, proof, _ = self.run_workbench(panels=['hair','nose'])
        self.assertFalse(result['ok'])
        self.assertIn('context changed', result['error'])
        self.assertEqual(len(proof['panels']), 1)

    def test_terminal_non_mutating_query_refusal_is_retained_and_next_panel_is_observed(self):
        def fault(op, result):
            if op.get('panel') == 'clothing_hair':
                return dict(result, ok=False, cas_request_state='failed', mutation_started=False, message='Native catalog unavailable')
        self.fault = fault
        result, proof, _ = self.run_workbench(panels=['hair','nose'])
        self.assertTrue(result['ok'])
        self.assertEqual(proof['panels'][0]['outcome'], 'native-query-unavailable')
        self.assertTrue(proof['panels'][1]['discovered'])

    def test_uncertain_mutation_stops_without_repeat_or_cleanup(self):
        def fault(op, result):
            if op['operation'] == 'catalog':
                return dict(result, ok=False, cas_request_state='failed', mutation_started=True, message='Uncertain engine state')
        self.fault = fault
        result, proof, _ = self.run_workbench(panels=['hair','nose'])
        self.assertFalse(result['ok'])
        self.assertEqual(len(proof['panels']), 1)
        self.assertEqual([row['operation'] for row in self.game.submitted], ['status','catalog'])

    def test_household_full_editor_preserves_alternate_form_and_all_native_context(self):
        value = self.game.client()
        value['native_context']['edit_mode']['value'] = 0
        self.assertEqual(workbench.context(value, fixture.SIM)['occultLayer'], 1)
        value['native_context']['entered_from_play_area']['value']['result'] = False
        with self.assertRaises(ValueError):
            workbench.context(value, fixture.SIM)

    def test_not_full_editor_refuses_before_any_panel(self):
        base = self.game.client
        def client():
            value = base(); value['native_context']['forced_full_edit']['value'] = False
            return value
        self.game.client = client
        result, proof, _ = self.run_workbench(panels=['hair'])
        self.assertFalse(result['ok']); self.assertEqual(proof['panels'], [])

    def test_output_reuse_and_alias_duplicates_refuse_before_transport(self):
        with self.assertRaises(ValueError): workbench.panel_names(['hair','clothing_hair'])
        self.game.output.write_text('immutable earlier proof')
        with self.assertRaises(ValueError):
            workbench.run(self.game.state, self.game.output, self.game.identity,
                          lambda *_args, **_kwargs:self.fail('No replay'), fixture.SIM)


if __name__ == '__main__': unittest.main()
