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
        self.catalog, self.families, self.selected = [], {}, []
        def client():
            value = original_client()
            value.update(menu_state=self.menu, panel_visible=True)
            value['sim'].update(allOccultTypes=65, occultType=64, occultLayer=self.layer, age=16)
            value['native_context']['forced_full_edit'] = {'query':'returned-value', 'value':True}
            value['native_context']['rendered_form'] = {'query':'returned-value','value':64}
            value['selected'] = copy.deepcopy(self.selected)
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
            client['control'] = {'operation':op, 'offset':operation['offset'], 'limit':operation['limit'],
                                 'total':len(self.catalog), 'items':copy.deepcopy(self.catalog)}
        elif op == 'variants':
            client['control'] = {'operation':op, 'data_id':operation['data_id'],
                                 'family':copy.deepcopy(self.families[operation['data_id']])}
        elif op == 'select':
            self.selected = [{'dataID':operation['data_id']}]
            client['selected'] = copy.deepcopy(self.selected)
            client['catalog_selection'] = dict(base_data_id=operation['base_data_id'],
                data_id=operation['data_id'], body_type=12, filtered_base_matches=1, family_variant_matches=1)
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

    def test_child_swatch_keeps_parent_binding_even_when_absent_from_filtered_cards(self):
        self.catalog = [{'data_id':'129329', 'body_type':12}]
        self.families = {'129329':{'mItems':[{'dataID':'129323'}]}}
        result, proof, _ = self.run_workbench(edit=True, panels=['earrings'])
        self.assertTrue(result['ok'], result.get('error'))
        selections = [row for row in self.game.submitted if row['operation'] == 'select']
        self.assertEqual(selections, [dict(operation='select', panel='clothing_accessories_earrings',
                                          base_data_id='129329', data_id='129323')])
        self.assertEqual(proof['panels'][0]['selected_data_id'], '129323')

    def test_rendered_form_is_distinct_from_family_kind_and_part_of_context(self):
        value=self.game.client();value['sim']['occultType']=4
        value['native_context']['rendered_form']['value']=2
        value['form_strip']=dict(cross_kind_navigation=True,native_owner_state='bound',
            selected_owner_id='alien/alien_alien',desired_owner_id='')
        result=workbench.context(value,fixture.SIM)
        self.assertEqual(result['occultType'],4);self.assertEqual(result['rendered_form'],2)
        self.assertEqual(result['independent_owner_id'],'alien/alien_alien')

    def test_unavailable_or_untyped_rendered_form_refuses_before_edits(self):
        for bad in (None,dict(query='unavailable',value=2),dict(query='returned-value',value=True)):
            with self.subTest(bad=bad):
                value=self.game.client();value['native_context']['rendered_form']=bad
                with self.assertRaisesRegex(ValueError,'actual rendered'):workbench.context(value,fixture.SIM)

    def test_in_progress_independent_form_is_not_an_edit_owner(self):
        value=self.game.client();value['form_strip']=dict(cross_kind_navigation=True,
            native_owner_state='bound',selected_owner_id='alien/alien_alien',desired_owner_id='vampire/vampire_dark')
        with self.assertRaisesRegex(ValueError,'still switching'):workbench.context(value,fixture.SIM)

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


class TattooRegionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []; self.item = {}; self.adds = 0
    def control(self, operation, **args):
        self.calls.append((operation, args)); body = args.get('body_type')
        data = {'operation': operation}
        if operation == 'body-types': data['body_types'] = [46, 47]
        elif operation == 'catalog': data.update(total=1, items=[{'body_type': self.current, 'data_id': '100'}])
        elif operation == 'body-type': self.current = body
        elif operation == 'layers': data['layers'] = [{'layerId': 127, 'futureMedical': 'keep'}]
        elif operation == 'layer-add':
            self.adds += 1; data['layers'] = [{'layerId': 127, 'futureMedical': 'keep'}, {'layerId': 1, 'partKey': '0'}]
        elif operation == 'variants': data['family'] = {'mItems': [{'dataID': '101'}]}
        return {'ok': True, 'cas_request_id': 'a' * 32, 'client': {'control': data}}
    def test_all_actual_regions_use_exact_ordinary_layer_and_preserve_medical_layer(self):
        workbench.edit_tattoo_regions(self.control, 'clothing_body_tattoos', self.item, lambda: None)
        self.assertEqual(self.adds, 2)
        edits = [args for op, args in self.calls if op == 'select-layer']
        self.assertEqual([row['body_type'] for row in edits], [46, 47])
        self.assertTrue(all(row['layer_id'] == 1 and row['layer_index'] == 1 for row in edits))
        self.assertTrue(self.item['edit_verified_in_cas'])
    def test_uncertain_layer_addition_stops_before_selection_and_other_regions(self):
        def control(op, **args):
            if op == 'layer-add': raise RuntimeError('unresolved native UUID')
            return self.control(op, **args)
        with self.assertRaisesRegex(RuntimeError, 'unresolved'):
            workbench.edit_tattoo_regions(control, 'clothing_body_tattoos', self.item, lambda: None)
        self.assertFalse(any(op == 'select-layer' for op, args in self.calls))
        self.assertEqual(len(self.item['tattoo_regions']), 1)
    def test_empty_region_is_reported_without_layer_or_item_creation(self):
        def control(op, **args):
            result = self.control(op, **args)
            if op == 'catalog': result['client']['control'].update(total=0, items=[])
            return result
        workbench.edit_tattoo_regions(control, 'clothing_body_tattoos', self.item, lambda: None)
        self.assertFalse(self.item['edit_verified_in_cas']); self.assertEqual(self.adds, 0)
        self.assertTrue(all(row['outcome'] == 'no-eligible-native-item' for row in self.item['tattoo_regions']))

    def test_empty_variant_family_never_creates_a_blank_native_layer(self):
        def control(op, **args):
            result = self.control(op, **args)
            if op == 'variants': result['client']['control']['family']['mItems'] = []
            return result
        workbench.edit_tattoo_regions(control, 'clothing_body_tattoos', self.item, lambda: None)
        self.assertEqual(self.adds, 0)
        self.assertTrue(all(row['outcome'] == 'no-different-native-variant' for row in self.item['tattoo_regions']))

    def test_empty_tattoo_storage_is_quarantined_without_any_native_mutation(self):
        def control(op, **args):
            result = self.control(op, **args)
            if op == 'layers':
                result['client']['control'].update(layers=[])
            return result
        workbench.edit_tattoo_regions(control, 'clothing_body_tattoos', self.item, lambda: None)
        self.assertEqual(self.adds, 0)
        edits = [args for op, args in self.calls if op == 'select-layer']
        self.assertEqual(edits, [])
        self.assertTrue(all(row['outcome']=='native-first-tattoo-insertion-quarantined'
                            for row in self.item['tattoo_regions']))


if __name__ == '__main__': unittest.main()
