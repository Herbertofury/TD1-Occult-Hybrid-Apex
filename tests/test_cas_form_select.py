"""Bound native CAS form navigation, with no game or profile access."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tools'))
from apex_core import cas_ui
import apex_cli
import cas_client

SIM = '9223372036854775815'
HH = '9223372036854775817'
GUID = '9223372036854775823'


def request(layer=0, form=64):
    return {'operation': 'form-select', 'household_id': HH, 'expected_layer': layer,
            'form_flags': form, 'native_session': 1}


def client(layer=0, sequence=1, base_form=1, alternate_form=64):
    mask = base_form | alternate_form
    def row(side):
        return {'sim_id': SIM, 'index': 0, 'occult_type': base_form if side == 0 else alternate_form,
                'all_occult_types': mask, 'occult_layer': side, 'selected': side == layer}
    pair = {'index': 0, 'base': row(0), 'alternate': row(1)}
    raw_pair = copy.deepcopy(pair)
    raw_pair['base']['selected'] = raw_pair['alternate']['selected'] = False
    selected = {key: value for key, value in row(layer).items() if key not in ('selected', 'index')}
    selected['household_id'] = HH
    return {'scope': 'native-cas-client',
            'sim': {'simId': SIM, 'householdId': HH, 'occultType': base_form if layer == 0 else alternate_form,
                    'allOccultTypes': mask, 'occultLayer': layer},
            'native_context': {'edit_mode': {'query': 'returned-value', 'value': 7},
                'new_family': {'query': 'returned-value', 'value': False},
                'entered_from_play_area': {'query': 'returned-value', 'value': {'result': True}}},
            'menu_state': cas_ui.PANELS['clothing_hair'], 'panel_visible': False,
            'outfit': {'outfit_type': 0, 'outfit_index': 0},
            'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                         'preset': None, 'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()],
            'owner_pair_observation': {'protocol': 1, 'scope': 'native-cas-paired-feed-read-only',
                'session': 1, 'listener_registered': True, 'stable': True, 'complete': False,
                'selected_query': 'returned-value', 'household_query': 'invalid-record',
                'selected': selected, 'household': [],
                'selector_query': 'returned-value',
                'selector_feed': {'protocol': 1, 'scope': 'native-selector-owner-pair-view',
                    'service_registered': True, 'reset_listener_registered': True,
                    'mapping_verified': False, 'alternate_accept_authorized': False,
                    'raw_feed': {'source': 'native-selector-raw-entry-observer', 'before_native_handler': True,
                        'delivered': True, 'complete': True, 'sequence': sequence,
                        'selected_index': 0, 'selected_layer': layer, 'base_row_count': 1,
                        'alternate_row_count': 1, 'pairs': [raw_pair]},
                    'retained': {'source': 'native-selector-retained-filtered-feed', 'available': True,
                        'complete': True, 'selected_index': 0, 'selected_layer': layer,
                        'selected_sim_id': SIM, 'pairs': [pair]}}}}


class CasFormSelectTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear(); cas_ui._PEERS.clear(); cas_ui._OWNER_BASELINES.clear()
        self.now = 10
        self.sim = Obj(id=int(SIM), household_id=int(HH))
        self.tracker = Obj(sim_info=self.sim, forms={64: Obj(id=int(SIM) + 2)})
        self.sim.occult_tracker = self.tracker
        self.backend = Obj(_get_sim_info_by_id=lambda sim_id: self.sim,
                           _form_map=lambda tracker: tracker.forms,
                           services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: int(GUID))))
        cas_ui.capture_original_owner(self.backend, self.sim)
        self.peer = cas_ui.attach_client(SIM, clock=lambda: self.now)

    def observe(self, layer=0, **pair):
        rid = cas_ui.submit(SIM, {'operation': 'status'}, clock=lambda: self.now)['cas_request_id']
        cas_ui.poll_client(self.peer, clock=lambda: self.now)
        cas_ui.receive_socket(self.peer, rid, json.dumps({'protocol': 1, 'ok': True,
            'cas_request_id': rid, 'client': client(layer, **pair)}), clock=lambda: self.now, backend=self.backend)
        return rid

    def submit(self, value=None):
        return cas_ui.submit(SIM, value or request(), clock=lambda: self.now, backend=self.backend)['cas_request_id']

    def receipt(self, rid, layer, expected, base_form=1, alternate_form=64):
        return {'protocol': 1, 'ok': True, 'cas_request_id': rid,
                'client': client(layer, base_form=base_form, alternate_form=alternate_form),
                'form_selection': {'native_session': 1, 'sim_id': SIM, 'household_id': HH,
                    'selected_index': 0, 'expected_layer': expected, 'target_layer': layer,
                    'form_flags': base_form if layer == 0 else alternate_form, 'selection_changed': expected != layer,
                    'selection_verified': True, 'mapping_verified': False, 'alternate_accept_authorized': False}}

    def acknowledge(self, rid, value):
        cas_ui.poll_client(self.peer, clock=lambda: self.now)
        cas_ui.receive_socket(self.peer, rid, json.dumps(value), clock=lambda: self.now, backend=self.backend)

    def test_household_editor_navigation_keeps_same_id_pair_and_never_authorizes_alt_accept(self):
        self.observe(0)
        rid = self.submit(request(0, 64))
        value = self.receipt(rid, 1, 0)
        value['client']['native_context']['edit_mode']['value'] = 0
        self.acknowledge(rid, value)
        result = cas_ui.result(rid)
        self.assertTrue(result['selection_only_verified'])
        self.assertFalse(result['alternate_accept_authorized'])
        self.assertEqual(result['client']['sim']['occultLayer'], 1)

    def test_observed_same_id_pair_selects_both_directions_without_claiming_mapping(self):
        for before, after in ((0, 1), (1, 0)):
            self.setUp(); self.observe(before)
            rid = self.submit(request(before, 1 if after == 0 else 64))
            wire = cas_ui.poll_client(self.peer, clock=lambda: self.now)
            self.assertEqual(wire.split('|')[1:], [SIM, 'form-select', str(1 if after == 0 else 64), str(before), '1', HH])
            self.acknowledge(rid, self.receipt(rid, after, before))
            result = cas_ui.result(rid)
            self.assertTrue(result['selection_only_verified'])
            self.assertFalse(result['mapping_verified'])
            self.assertFalse(result['alternate_accept_authorized'])
            self.assertFalse(result['appearance_persistence_verified'])
            self.assertEqual(result['client']['owner_pair_observation']['household'], [])

    def test_same_layer_readback_is_verified_without_claiming_a_change(self):
        self.observe(); rid = self.submit(request(0, 1))
        value = self.receipt(rid, 0, 0)
        self.acknowledge(rid, value)
        self.assertFalse(cas_ui.result(rid)['form_selection']['selection_changed'])

    def test_actual_vampire_kind_on_both_layers_can_navigate_by_layer_without_human_guess(self):
        for before, after in ((0, 1), (1, 0)):
            self.setUp()
            self.tracker.forms = {4: Obj(id=int(SIM)+4)}
            cas_ui.capture_original_owner(self.backend, self.sim)
            self.observe(before, base_form=4, alternate_form=4)
            value = {'operation':'layer-select','household_id':HH,'expected_layer':before,
                     'target_layer':after,'native_session':1}
            rid = self.submit(value)
            wire = cas_ui.poll_client(self.peer, clock=lambda:self.now)
            self.assertEqual(wire.split('|')[1:], [SIM,'layer-select',str(after),str(before),'1',HH])
            self.acknowledge(rid,self.receipt(rid,after,before,base_form=4,alternate_form=4))
            result=cas_ui.result(rid)
            self.assertEqual(result['outcome'],'layer-selected')
            self.assertTrue(result['selection_only_verified'])
            self.assertEqual(result['form_selection']['form_flags'],4)
            self.assertFalse(result['mapping_verified'])
            self.assertFalse(result['alternate_accept_authorized'])
            self.assertFalse(result['appearance_persistence_verified'])
            self.assertFalse(result['cas_room']['rows'][0]['navigation_supported'])

    def test_layer_navigation_refuses_stale_or_foreign_pair_and_untyped_target(self):
        value={'operation':'layer-select','household_id':HH,'expected_layer':1,'target_layer':0,'native_session':1}
        for mutate in (lambda c:c['owner_pair_observation'].update(session=2),
                       lambda c:c['owner_pair_observation']['selector_feed']['retained']['pairs'][0]['base'].update(sim_id='13'),
                       lambda c:c['owner_pair_observation']['selector_feed']['raw_feed'].update(delivered=False),
                       lambda c:c['sim'].update(occultLayer=0)):
            c=client(1,base_form=4,alternate_form=4);mutate(c)
            with self.assertRaises(ValueError):cas_ui.form_selection_binding(c,SIM,value)
        for target in (True,-1,2,None):
            with self.assertRaises(ValueError):cas_ui.envelope(SIM,dict(value,target_layer=target))
        with self.assertRaises(ValueError):
            cas_ui.form_selection_binding(client(1,base_form=4,alternate_form=4),SIM,request(1,4))

    def test_layer_selection_failed_after_native_write_cannot_be_replayed(self):
        self.tracker.forms={4:Obj(id=int(SIM)+4)}
        cas_ui.capture_original_owner(self.backend,self.sim)
        self.observe(1,base_form=4,alternate_form=4)
        rid=self.submit({'operation':'layer-select','household_id':HH,'expected_layer':1,'target_layer':0,'native_session':1})
        self.acknowledge(rid,{'protocol':1,'ok':False,'cas_request_id':rid,'mutation_started':True})
        self.assertEqual(cas_ui.result(rid)['outcome'],'form-select-unresolved')
        with self.assertRaisesRegex(ValueError,'unresolved'):
            cas_ui.submit(SIM,{'operation':'status'},clock=lambda:self.now)

    def test_creature_base_human_disguise_uses_observed_layer_in_both_directions(self):
        for before, after in ((0, 1), (1, 0)):
            self.setUp()
            self.tracker.forms = {1: Obj(id=int(SIM)+1), 2: Obj(id=int(SIM)+2)}
            cas_ui.capture_original_owner(self.backend, self.sim)
            self.observe(before, base_form=2, alternate_form=1)
            target = 1 if after == 1 else 2
            rid = self.submit(request(before, target))
            wire = cas_ui.poll_client(self.peer, clock=lambda: self.now)
            self.assertEqual(wire.split('|')[1:], [SIM, 'form-select', str(target), str(before), '1', HH])
            self.acknowledge(rid, self.receipt(rid, after, before, base_form=2, alternate_form=1))
            result = cas_ui.result(rid)
            self.assertTrue(result['selection_only_verified'])
            self.assertEqual(result['form_selection']['target_layer'], after)
            self.assertEqual(result['client']['sim']['occultType'], target)
            self.assertFalse(result['alternate_accept_authorized'])

    def test_reversed_pair_cannot_acknowledge_requested_disguise_at_creature_layer(self):
        self.tracker.forms = {1: Obj(id=int(SIM)+1), 2: Obj(id=int(SIM)+2)}
        cas_ui.capture_original_owner(self.backend, self.sim)
        self.observe(0, base_form=2, alternate_form=1)
        rid = self.submit(request(0, 1))
        with self.assertRaisesRegex(ValueError, 'actual observed target layer'):
            self.acknowledge(rid, self.receipt(rid, 0, 0, base_form=2, alternate_form=1))
        self.assertFalse(cas_ui.result(rid)['ok'])

    def test_unloaded_live_zone_keeps_original_capability_for_cas_navigation_only(self):
        self.observe(1)
        self.backend._get_sim_info_by_id = lambda _sim_id: None
        self.backend.services.current_zone = lambda: None
        rid = self.submit(request(1, 1))
        self.acknowledge(rid, self.receipt(rid, 0, 1))
        result = cas_ui.result(rid)
        self.assertTrue(result['selection_only_verified'])
        self.assertFalse(result['alternate_accept_authorized'])
        self.assertFalse(result['appearance_persistence_verified'])
        with self.assertRaisesRegex(ValueError, 'manager owner'):
            cas_ui._owner_context(self.backend, self.sim)

    def test_unmanaged_navigation_refuses_live_zone_unknown_zone_and_replacement_sim(self):
        for zone, managed in ((Obj(), None), (None, Obj(id=int(SIM))), ('unavailable', None)):
            self.setUp(); self.observe(1)
            self.backend._get_sim_info_by_id = lambda _sim_id, value=managed: value
            if zone != 'unavailable': self.backend.services.current_zone = lambda value=zone: value
            with self.subTest(zone=zone), self.assertRaisesRegex(ValueError, 'manager owner'):
                self.submit(request(1, 1))
            self.assertEqual(len(cas_ui._RECORDS), 1)

    def test_detached_zero_household_and_guid_keep_captured_navigation_only(self):
        for household, guid in ((0, int(GUID)), (int(HH), 0), (0, 0)):
            self.setUp(); self.observe(1)
            self.backend._get_sim_info_by_id = lambda _id: None
            self.backend.services.current_zone = lambda: None
            self.sim.household_id = household
            self.backend.services.get_persistence_service = lambda value=guid: Obj(get_save_slot_proto_guid=lambda: value)
            rid = self.submit(request(1, 1))
            self.acknowledge(rid, self.receipt(rid, 0, 1))
            self.assertTrue(cas_ui.result(rid)['selection_only_verified'])
            self.assertFalse(cas_ui.result(rid)['alternate_accept_authorized'])
            with self.assertRaises(ValueError):cas_ui._owner_context(self.backend,self.sim)

    def test_detached_ambiguous_or_changed_captured_identity_refuses_before_delivery(self):
        for mode in ('ambiguous', 'household', 'guid', 'wrapper'):
            self.setUp(); self.observe(1)
            self.backend._get_sim_info_by_id = lambda _id: None
            self.backend.services.current_zone = lambda: None
            old = next(iter(cas_ui._OWNER_BASELINES.values()))
            if mode == 'ambiguous':
                cas_ui._OWNER_BASELINES[(old['baseline']['runtime_pid'], '17', SIM)] = old
            elif mode == 'wrapper': old['baseline']['wrappers'][0]['sim_id'] = '13'
            else: old['baseline'][mode + '_id' if mode == 'household' else 'save_guid'] = '13'
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.submit(request(1, 1))
            self.assertEqual(len(cas_ui._RECORDS), 1)

    def test_unloaded_navigation_never_dereferences_disposed_live_objects_or_asserts_mapping(self):
        self.observe(1)
        self.backend._get_sim_info_by_id = lambda _id: None
        self.backend.services.current_zone = lambda: None
        class Disposed:
            def __getattribute__(self, name):
                raise AssertionError('Disposed Live producer must not be read in CAS: ' + name)
        stored = next(iter(cas_ui._OWNER_BASELINES.values()))
        stored['sim'] = stored['tracker'] = stored['form_map'] = Disposed()
        stored['wrappers'] = {64: Disposed()}
        self.backend.services.get_persistence_service = lambda: (_ for _ in ()).throw(
            AssertionError('Disposed Live persistence must not be read in CAS'))
        rid = self.submit(request(1, 1))
        self.acknowledge(rid, self.receipt(rid, 0, 1))
        result = cas_ui.result(rid)
        self.assertTrue(result['selection_only_verified'])
        self.assertFalse(result['mapping_verified'])
        self.assertFalse(result['alternate_accept_authorized'])
        self.assertFalse(result['appearance_persistence_verified'])

    def test_live_navigation_still_rejects_changed_wrapper_or_household(self):
        for change in (lambda: setattr(self.sim, 'household_id', 13),
                       lambda: self.tracker.forms.update({64: Obj(id=int(SIM) + 2)}),
                       lambda: setattr(self.tracker, 'forms', dict(self.tracker.forms))):
            self.setUp(); self.observe(1); change()
            with self.assertRaisesRegex(ValueError, 'continuity'): self.submit(request(1, 1))
            self.assertEqual(len(cas_ui._RECORDS), 1)

    def test_untyped_or_unbounded_request_never_delivers(self):
        for key, invalid in [('expected_layer', True), ('expected_layer', 2), ('form_flags', True),
                             ('form_flags', 65), ('native_session', True), ('native_session', 0),
                             ('native_session', 2**31), ('household_id', '01')]:
            value = request(); value[key] = invalid
            with self.subTest(key=key, value=invalid), self.assertRaises(ValueError):
                cas_ui.envelope(SIM, value)
        value = request(); value['another_sim_id'] = '13'
        with self.assertRaises(ValueError): cas_ui.envelope(SIM, value)

    def test_missing_or_stale_native_ack_refuses_before_pending_record(self):
        with self.assertRaisesRegex(ValueError, 'acknowledgement'): self.submit()
        self.observe(); self.now += 4
        cas_ui.poll_client(self.peer, clock=lambda: self.now)
        with self.assertRaisesRegex(ValueError, 'acknowledgement'): self.submit()
        self.assertEqual(len(cas_ui._RECORDS), 1)

    def test_new_peer_cannot_reuse_old_peer_ack(self):
        self.observe(); cas_ui._PEERS.pop(self.peer)
        self.peer = cas_ui.attach_client(SIM, clock=lambda: self.now)
        with self.assertRaisesRegex(ValueError, 'acknowledgement'): self.submit()

    def test_original_producer_wrapper_or_household_change_refuses_selection(self):
        for change in (lambda: setattr(self.sim, 'household_id', 13),
                       lambda: self.tracker.forms.update({64: Obj(id=int(SIM) + 2)}),
                       lambda: setattr(self.tracker, 'forms', dict(self.tracker.forms))):
            self.setUp(); self.observe(); change()
            with self.assertRaisesRegex(ValueError, 'continuity'): self.submit()
            self.assertEqual(len(cas_ui._RECORDS), 1)

    def test_current_layer_requested_form_and_session_must_match_actual_observation(self):
        self.observe()
        for value in (request(1), request(0, 4), dict(request(), native_session=2)):
            with self.subTest(value=value), self.assertRaises(ValueError): self.submit(value)
        self.assertEqual(len(cas_ui._RECORDS), 1)

    def test_feed_reset_foreign_or_distinct_wrapper_id_cannot_authorize_navigation(self):
        mutations = [lambda o: o['selector_feed']['raw_feed'].update(delivered=False),
                     lambda o: o['selector_feed'].update(service_registered=False),
                     lambda o: o['selector_feed']['retained'].update(selected_index=1),
                     lambda o: o['selector_feed']['retained']['pairs'][0]['alternate'].update(sim_id='13'),
                     lambda o: o['selector_feed']['raw_feed']['pairs'][0]['alternate'].update(occult_type=32),
                     lambda o: o['selector_feed']['retained']['pairs'][0]['base'].update(selected=True),
                     lambda o: o['selected'].update(household_id='13'),
                     lambda o: o['selector_feed'].update(mapping_verified=True)]
        for mutation in mutations:
            value = client(1); mutation(value['owner_pair_observation'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                cas_ui.form_selection_binding(value, SIM, request(1, 1))

    def test_raw_household_is_new_cannot_replace_authoritative_native_context(self):
        value = client(); value['owner_pair_observation']['household_primitives'] = [{'isNew': True}]
        self.assertEqual(cas_ui.form_selection_binding(value, SIM, request())['target_layer'], 1)
        value['native_context']['new_family']['value'] = True
        with self.assertRaisesRegex(ValueError, 'existing family'):
            cas_ui.form_selection_binding(value, SIM, request())

    def test_changed_postcondition_remains_unresolved_and_cannot_repeat(self):
        for mutate in [lambda d: d['client']['sim'].update(occultLayer=0),
                       lambda d: d['client']['owner_pair_observation'].update(session=2),
                       lambda d: d['form_selection'].update(selection_verified=False),
                       lambda d: d['form_selection'].update(target_layer=True)]:
            self.setUp(); self.observe(); rid = self.submit()
            value = self.receipt(rid, 1, 0); mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): self.acknowledge(rid, value)
            result=cas_ui.result(rid)
            self.assertEqual(result['outcome'], 'invalid-native-acknowledgement')
            self.assertEqual(result['native_acknowledgement'], value)
            self.assertEqual(result['cas_request_state'], 'pending')
            with self.assertRaisesRegex(ValueError, 'unresolved'): self.submit()

    def test_partial_native_write_failure_retains_exclusive_unresolved_claim(self):
        self.observe(); rid = self.submit()
        self.acknowledge(rid, {'protocol': 1, 'ok': False, 'cas_request_id': rid,
                              'mutation_started': True, 'message': 'Selection readback unavailable'})
        self.assertEqual(cas_ui.result(rid)['outcome'], 'form-select-unresolved')
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            cas_ui.submit(SIM, {'operation': 'status'}, clock=lambda: self.now)
        self.assertIsNone(cas_ui.poll_client(self.peer, clock=lambda: self.now))

    def test_fresh_alternate_navigation_never_relaxes_accept_layer_zero(self):
        with self.assertRaisesRegex(ValueError, 'primary occult layer 0'):
            cas_ui.validate_client(client(1), SIM, {'operation': 'accept', 'household_id': HH})

    def test_cli_passes_only_exact_form_selection_fields(self):
        args = apex_cli.parser().parse_args(['cas', 'form-select', '--state', 'state.json', '--sim-id', SIM,
            '--household-id', HH, '--expected-layer', '1', '--form', '1', '--native-session', '1'])
        args.seconds = 10
        rid = 'a' * 32
        calls = []
        def transport(state, action, sim_id=None, **kwargs):
            calls.append((action, kwargs))
            if action == 'cas_ui_request':
                return {'cas_request_id': rid}
            if len(calls) == 2:
                return {'ok': True, 'client': client(1), 'cas_room': {'native_session': 1}}
            return {'ok': True, 'outcome': 'form-selected'}
        self.assertTrue(cas_client.execute(args, transport)['ok'])
        self.assertEqual(json.loads(calls[0][1]['value']), {'operation': 'status'})
        self.assertEqual(json.loads(calls[2][1]['value']), request(1, 1))
        args.native_session = None; calls.clear()
        with self.assertRaises(ValueError): cas_client.execute(args, transport)
        self.assertEqual(calls, [])

    def test_cli_fresh_preflight_preserves_exact_session_layer_and_household(self):
        args = apex_cli.parser().parse_args(['cas', 'form-select', '--state', 'state.json', '--sim-id', SIM,
            '--household-id', HH, '--expected-layer', '1', '--form', '1', '--native-session', '1'])
        args.seconds = 10
        for field in ('session', 'layer', 'household', 'sim'):
            with self.subTest(field=field):
                calls = []
                observed = {'ok': True, 'client': client(1), 'cas_room': {'native_session': 1}}
                if field == 'session': observed['client']['owner_pair_observation']['session'] = 2
                elif field == 'layer': observed['client']['sim']['occultLayer'] = 0
                elif field == 'household': observed['client']['sim']['householdId'] = '13'
                else: observed['client']['sim']['simId'] = '13'
                def transport(state, action, sim_id=None, **kwargs):
                    calls.append((action, kwargs))
                    return {'cas_request_id': 'a'*32} if action == 'cas_ui_request' else observed
                with self.assertRaises(ValueError):
                    cas_client.execute(args, transport)
                self.assertEqual(len(calls), 2)
                self.assertEqual(json.loads(calls[0][1]['value']), {'operation': 'status'})

    def test_cli_rejected_preflight_never_submits_form_selection(self):
        args = apex_cli.parser().parse_args(['cas', 'form-select', '--state', 'state.json', '--sim-id', SIM,
            '--household-id', HH, '--expected-layer', '1', '--form', '1', '--native-session', '1'])
        args.seconds = 10
        calls = []
        rejected = {'ok': False, 'outcome': 'invalid-native-acknowledgement',
                    'native_acknowledgement': {'future': {'retain': True}}}
        def transport(state, action, sim_id=None, **kwargs):
            calls.append((action, kwargs))
            return {'cas_request_id': 'a'*32} if action == 'cas_ui_request' else rejected
        result = cas_client.execute(args, transport)
        self.assertFalse(result['form_selection_submitted'])
        self.assertFalse(result['form_selection_preflight_verified'])
        self.assertEqual(result['native_acknowledgement'], rejected['native_acknowledgement'])
        self.assertEqual(len(calls), 2)

    def test_earrings_exact_item_selection_preserves_untyped_skin_and_preset_refusals(self):
        _, wire = cas_ui.envelope(SIM, {'operation': 'select', 'panel': 'clothing_accessories_earrings', 'data_id': '123'})
        self.assertIn('|select|' + str(cas_ui.PANELS['clothing_accessories_earrings']) + '|', wire)
        for panel in ('face_skin_details', 'face_skin_tone', 'body_tattoos'):
            with self.subTest(panel=panel), self.assertRaises(ValueError):
                cas_ui.envelope(SIM, {'operation': 'select', 'panel': panel, 'data_id': '123'})


if __name__ == '__main__':
    unittest.main()
