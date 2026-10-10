"""Host-only exact owner diagnostics; no game, persistence or input calls."""
import copy
import json
from enum import IntEnum
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui

BASE = '9223372036854775815'
ALT = '18446744073709551614'
HH = '9223372036854775817'
GUID = '9223372036854775823'


def sim_row(sim_id, layer):
    return {'sim_id': sim_id, 'household_id': HH, 'occult_type': 64,
            'all_occult_types': 65, 'occult_layer': layer}


def feed_row(sim_id, layer):
    row = sim_row(sim_id, layer)
    row.pop('household_id')
    row.update(index=0, selected=layer == 1)
    return row


def client():
    selected = sim_row(ALT, 1)
    return {'scope': 'native-cas-client', 'sim': {'simId': ALT, 'householdId': HH,
                'occultType': 64, 'allOccultTypes': 65, 'occultLayer': 1},
            'menu_state': cas_ui.PANELS['clothing_hair'], 'panel_visible': True,
            'outfit': {'outfit_type': 0, 'outfit_index': 1},
            'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                          'preset': None, 'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()],
            'owner_pair_observation': {'protocol': 1, 'scope': 'native-cas-paired-feed-read-only',
                'session': 1, 'listener_registered': True, 'stable': True, 'complete': True,
                'selected_query': 'returned-value', 'household_query': 'returned-value',
                'selected': selected, 'household': [sim_row(BASE, 0)], 'error': '',
                'feed': {'delivered': True, 'complete': True, 'sequence': 2,
                    'selected_index': 0, 'selected_layer': 1, 'error': '',
                    'pairs': [{'index': 0, 'base': feed_row(BASE, 0), 'alternate': feed_row(ALT, 1)}]}}}


class Lane(IntEnum):
    FAIRY = 64


class OwnerObservationTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear()
        cas_ui._PEERS.clear()
        cas_ui._OWNER_BASELINES.clear()
        self.sim = Obj(id=int(BASE), household_id=int(HH))
        self.wrapper = Obj(id=int(ALT))
        self.tracker = Obj(sim_info=self.sim, forms={Lane.FAIRY: self.wrapper})
        self.sim.occult_tracker = self.tracker
        self.manager = self.sim
        self.guid = int(GUID)
        self.backend = Obj(_get_sim_info_by_id=lambda sim_id: self.manager,
                           _form_map=lambda tracker: tracker.forms,
                           services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: self.guid)))
        self.capture = cas_ui.capture_original_owner(self.backend, self.sim)

    def assert_incomplete(self, value, reason=None):
        self.assertEqual(value['state'], 'incomplete')
        self.assertFalse(value['pair_relationship_observed'])
        self.assertFalse(value['mapping_verified'])
        self.assertFalse(value['alternate_accept_authorized'])
        if reason:
            self.assertIn(reason, value['error'])

    def test_baseline_reads_actual_producer_and_keeps_uint64_and_enum_lane(self):
        self.assertTrue(self.capture['ok'])
        baseline = self.capture['original_owner']
        self.assertTrue(baseline['complete'])
        self.assertEqual(baseline['original_sim_id'], BASE)
        self.assertEqual(baseline['household_id'], HH)
        self.assertEqual(baseline['save_guid'], GUID)
        self.assertEqual(baseline['wrappers'], [{'form_flags': 64, 'sim_id': ALT}])
        json.dumps(self.capture)  # no Sim/tracker/native objects exported
        self.capture['original_owner']['wrappers'][0]['sim_id'] = '1'
        self.assertTrue(cas_ui.owner_pair_diagnostic(client(), self.backend)['pair_relationship_observed'])

    def test_exact_native_pair_is_only_observation_with_base_only_household_getter(self):
        result = cas_ui.owner_pair_diagnostic(client(), self.backend)
        self.assertEqual(result['state'], 'observed-pair-only')
        self.assertTrue(result['pair_relationship_observed'])
        self.assertEqual(result['alternate_wrapper_flags'], [64])
        self.assertTrue(result['base_in_household'])
        self.assertFalse(result['alternate_in_household'])
        self.assertFalse(result['mapping_verified'])
        self.assertFalse(result['alternate_accept_authorized'])
        # Observing the exact alternate never relaxes the original accept guard.
        value = client()
        value['native_context'] = {'edit_mode': {'query': 'returned-value', 'value': 7},
            'new_family': {'query': 'returned-value', 'value': False},
            'entered_from_play_area': {'query': 'returned-value', 'value': {'result': True}}}
        with self.assertRaisesRegex(ValueError, 'primary occult layer 0'):
            cas_ui.validate_client(value, ALT, {'operation': 'accept', 'household_id': HH})

    def test_missing_initial_feed_and_old_client_remain_explicitly_incomplete(self):
        self.assert_incomplete(cas_ui.owner_pair_diagnostic({}, self.backend), 'No owned')
        value = client()
        value['owner_pair_observation']['feed'].update(delivered=False, complete=False, sequence=0, pairs=[])
        self.assert_incomplete(cas_ui.owner_pair_diagnostic(value, self.backend), 'No paired feed delivered')
        self.assert_incomplete(cas_ui.owner_pair_diagnostic(client()), 'owner-thread backend')

    def test_invalid_producer_capture_is_diagnostic_without_creating_any_owner(self):
        self.manager = Obj(id=int(BASE))
        captured = cas_ui.capture_original_owner(self.backend, self.sim)
        self.assertTrue(captured['ok'])
        self.assertFalse(captured['original_owner']['complete'])
        self.assertIn('manager owner', captured['original_owner']['error'])
        self.assertEqual(len(cas_ui._OWNER_BASELINES), 1)

    def test_manager_tracker_wrapper_replacement_save_and_id_changes_refuse_relationship(self):
        changes = [lambda: setattr(self, 'manager', Obj(id=int(BASE))),
                   lambda: setattr(self.tracker, 'sim_info', Obj(id=int(BASE))),
                   lambda: setattr(self.sim, 'occult_tracker', Obj(sim_info=self.sim, forms=self.tracker.forms)),
                   lambda: self.tracker.forms.update({Lane.FAIRY: Obj(id=int(ALT))}),
                   lambda: setattr(self.tracker, 'forms', dict(self.tracker.forms)),
                   lambda: setattr(self.wrapper, 'id', 13),
                   lambda: setattr(self, 'guid', 13),
                   lambda: setattr(self.sim, 'household_id', 13)]
        for change in changes:
            self.setUp()
            change()
            with self.subTest(change=change):
                self.assert_incomplete(cas_ui.owner_pair_diagnostic(client(), self.backend))

    def test_ambiguous_original_wrappers_and_foreign_alternate_refuse_relationship(self):
        self.tracker.forms[2] = Obj(id=int(ALT))
        self.assertFalse(cas_ui.capture_original_owner(self.backend, self.sim)['original_owner']['complete'])
        self.assert_incomplete(cas_ui.owner_pair_diagnostic(client(), self.backend), 'changed after baseline')
        self.setUp()
        value = client()
        value['owner_pair_observation']['feed']['pairs'][0]['base']['sim_id'] = '13'
        value['owner_pair_observation']['household'][0]['sim_id'] = '13'
        self.assert_incomplete(cas_ui.owner_pair_diagnostic(value, self.backend), 'No exact original producer')

    def test_malformed_context_missing_delivery_duplicates_and_bounds_refuse_relationship(self):
        mutations = [lambda o: o.update(protocol=True), lambda o: o.update(session=True),
            lambda o: o.update(listener_registered=False), lambda o: o.update(stable=False),
            lambda o: o.update(complete=False), lambda o: o.update(selected_query='failed'),
            lambda o: o.update(household_query='failed'), lambda o: o['feed'].update(sequence=True),
            lambda o: o['feed'].update(selected_index=True), lambda o: o['feed'].update(selected_layer=2),
            lambda o: o['feed'].update(pairs=o['feed']['pairs'] * 33),
            lambda o: o['feed']['pairs'][0]['alternate'].update(sim_id='0'),
            lambda o: o['feed']['pairs'][0]['alternate'].update(sim_id=str(2 ** 64)),
            lambda o: o['feed']['pairs'][0]['alternate'].update(sim_id='０'),
            lambda o: o['feed']['pairs'][0]['alternate'].update(sim_id='0' + ALT),
            lambda o: o['feed']['pairs'][0]['alternate'].update(occult_layer=True),
            lambda o: o['feed']['pairs'][0]['alternate'].update(occult_type=32),
            lambda o: o['feed']['pairs'][0]['alternate'].update(selected=1),
            lambda o: o['feed']['pairs'][0].update(base=None),
            lambda o: o['feed']['pairs'][0]['base'].update(sim_id=ALT),
            lambda o: o.update(household=[]), lambda o: o.update(household=o['household'] * 2),
            lambda o: o['household'][0].update(household_id='13'),
            lambda o: o['selected'].update(sim_id='13'), lambda o: o['selected'].update(occult_layer=True)]
        for mutation in mutations:
            value = client()
            mutation(value['owner_pair_observation'])
            with self.subTest(mutation=mutation):
                self.assert_incomplete(cas_ui.owner_pair_diagnostic(value, self.backend))

    def test_owner_ack_observation_is_separate_from_immutable_raw_reply_and_duplicates(self):
        peer = cas_ui.attach_client(ALT)
        request = cas_ui.submit(ALT, {'operation': 'status'})['cas_request_id']
        cas_ui.poll_client(peer)
        payload = {'ok': True, 'protocol': 1, 'cas_request_id': request, 'client': client()}
        raw = json.dumps(payload)
        envelope = {'peer': peer, 'request_id': request, 'payload': raw}
        cas_ui.dispatch('cas_ui_socket_ack', ALT, envelope, self.backend)
        result = cas_ui.result(request)
        self.assertTrue(result['ok'])
        self.assertTrue(result['owner_pair_diagnostic']['pair_relationship_observed'])
        self.assertEqual(cas_ui._RECORDS[request]['result'], payload)
        self.manager = None
        cas_ui.dispatch('cas_ui_socket_ack', ALT, envelope, self.backend)
        self.assertEqual(cas_ui.result(request), result)
        self.assertIsNone(cas_ui.poll_client(peer))

    def test_invalid_owner_diagnostic_does_not_manufacture_failure_of_a_valid_read(self):
        request = cas_ui.submit(ALT, {'operation': 'status'}, send=lambda _: None)['cas_request_id']
        value = client()
        value['owner_pair_observation']['feed']['pairs'][0]['alternate']['selected'] = 1
        cas_ui.receive(request, json.dumps({'ok': True, 'protocol': 1, 'cas_request_id': request, 'client': value}), self.backend)
        result = cas_ui.result(request)
        self.assertTrue(result['ok'])
        self.assert_incomplete(result['owner_pair_diagnostic'])


if __name__ == '__main__':
    unittest.main()
