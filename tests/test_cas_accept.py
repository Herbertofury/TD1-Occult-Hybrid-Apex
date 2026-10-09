import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
from apex_core import cas_ui, test_driver

SIM = '9223372036854775815'
HOUSEHOLD = '9223372036854775817'


def native_client():
    return {'scope': 'native-cas-client', 'sim': {'simId': SIM, 'householdId': HOUSEHOLD,
                'isNew': True, 'occultLayer': 0, 'future': {'opaque': '18446744073709551615'}},
            'menu_state': cas_ui.PANELS['clothing_hair'], 'panel_visible': True,
            'outfit': {'outfit_type': 0, 'outfit_index': 1},
            'catalogs': [{'panel': name, 'menu_state': state, 'supported': True, 'items': [],
                          'preset': None, 'preset_query': 'returned-null'} for name, state in cas_ui.PANELS.items()],
            'native_context': {'edit_mode': {'query': 'returned-value', 'value': 7},
                'new_family': {'query': 'returned-value', 'value': False},
                'entered_from_play_area': {'query': 'returned-value', 'value': {'result': True}}}}


def live_snapshot(ticks='100', speed=0):
    return {'ok': True, 'sim': {'id': SIM, 'instanced': True}, 'household_id': HOUSEHOLD,
            'client_id': '9223372036854775819', 'zone_id': '9223372036854775821',
            'save_guid': '9223372036854775823', 'save_slot': 0xffffffff,
            'in_build_buy': False, 'zone_running': True, 'clock_speed': speed,
            'sim_time_source': 'services.time_service().sim_now',
            'sim_now_ticks': ticks, 'runtime_queries': {name: 'returned-value'
                for name in ('client_id', 'zone_running', 'sim_now_ticks')}}


class CasAcceptTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear()
        cas_ui._PEERS.clear()
        self.peer = cas_ui.attach_client(SIM)

    def intent(self):
        rid = cas_ui.submit(SIM, {'operation': 'accept', 'household_id': HOUSEHOLD})['cas_request_id']
        self.assertEqual(cas_ui.poll_client(self.peer).split('|')[2:], ['accept', '0', '0', '0', HOUSEHOLD])
        data = {'ok': True, 'protocol': 1, 'cas_request_id': rid, 'client': native_client(),
                'lifecycle_stage': 'accept-intent', 'commit_submitted': False}
        return rid, data

    def acknowledge(self):
        rid, data = self.intent()
        result = cas_ui.receive_socket(self.peer, rid, json.dumps(data))
        self.assertFalse(result['ui_transition_verified'])
        return rid, data

    def test_accept_requires_current_peer_and_no_generic_ui_fallback(self):
        cas_ui.detach_client(self.peer)
        with self.assertRaisesRegex(ValueError, 'fresh exact-Sim'):
            cas_ui.submit(SIM, {'operation': 'accept', 'household_id': HOUSEHOLD}, send=lambda _: self.fail('sent'))
        self.assertFalse(cas_ui._RECORDS)

    def test_intent_is_nonterminal_identical_duplicates_are_idempotent_and_no_mutation_can_follow(self):
        rid, data = self.acknowledge()
        cas_ui.receive_socket(self.peer, rid, json.dumps(data))
        self.assertIsNone(cas_ui.poll_client(self.peer))
        result = cas_ui.result(rid)
        self.assertEqual(result['outcome'], 'accept-intent')
        self.assertEqual(result['cas_request_state'], 'accept-intent')
        self.assertFalse(result['ui_transition_verified'])
        self.assertFalse(result['live_return_verified'])
        self.assertTrue(result['client']['sim']['isNew'])
        for operation in ('accept', 'status', 'undo'):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'unresolved'):
                request = {'operation': operation}
                if operation == 'accept': request['household_id'] = HOUSEHOLD
                cas_ui.submit(SIM, request)
        changed = copy.deepcopy(data)
        changed['client']['sim']['future']['opaque'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'intent acknowledgement changed'):
            cas_ui.receive_socket(self.peer, rid, json.dumps(changed))

    def test_exact_native_mode_and_object_result_guard_refuses_coercion(self):
        for name, value in (('edit_mode', True), ('edit_mode', 0), ('new_family', 0),
                            ('new_family', True), ('entered_from_play_area', True),
                            ('entered_from_play_area', {'result': 1}), ('entered_from_play_area', {})):
            client = native_client()
            client['native_context'][name]['value'] = value
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                cas_ui.validate_client(client, SIM, {'operation': 'accept', 'household_id': HOUSEHOLD})
        client = native_client()
        client['native_context']['edit_mode']['query'] = 'failed'
        with self.assertRaisesRegex(ValueError, 'not returned'):
            cas_ui.validate_accept_context(client)

    def test_nonprimary_or_untyped_occult_layer_cannot_acknowledge_prepared_accept_owner(self):
        missing = object()
        for layer in (1, -1, 64, True, False, '0', None, missing):
            with self.subTest(layer='missing' if layer is missing else layer):
                cas_ui._RECORDS.clear()
                rid, data = self.intent()
                if layer is missing:
                    data['client']['sim'].pop('occultLayer')
                else:
                    data['client']['sim']['occultLayer'] = layer
                with self.assertRaisesRegex(ValueError, 'primary occult layer 0'):
                    cas_ui.receive_socket(self.peer, rid, json.dumps(data))
                self.assertEqual(cas_ui._RECORDS[rid]['state'], 'pending')
                self.assertIsNone(cas_ui._RECORDS[rid]['result'])
                self.assertIsNone(cas_ui.poll_client(self.peer))

    def test_primary_layer_human_and_vampire_accept_intents_remain_supported(self):
        for occult in (1, 4):
            with self.subTest(occult=occult):
                cas_ui._RECORDS.clear()
                rid, data = self.intent()
                data['client']['sim']['occultType'] = occult
                reply = cas_ui.receive_socket(self.peer, rid, json.dumps(data))
                self.assertTrue(reply['acknowledgement_accepted'])
                self.assertEqual(cas_ui._RECORDS[rid]['state'], 'accept-intent')
                self.assertEqual(cas_ui.result(rid)['client']['sim']['occultLayer'], 0)

    def test_post_intent_native_refusal_preserves_original_and_no_false_success(self):
        rid, data = self.acknowledge()
        refusal = {'protocol': 1, 'ok': False, 'cas_request_id': rid,
                   'lifecycle_stage': 'accept-result', 'commit_submitted': False,
                   'commit_attempted': True, 'commit_accepted': False}
        cas_ui.receive_socket(self.peer, rid, json.dumps(refusal))
        cas_ui.receive_socket(self.peer, rid, json.dumps(refusal))
        result = cas_ui.result(rid)
        self.assertEqual(result['outcome'], 'accept-rejected')
        self.assertEqual(result['accept_intent'], data)
        self.assertFalse(result['ui_transition_verified'])
        self.assertFalse(result['live_return_verified'])

    def test_initial_preflight_refusal_and_claimed_success_are_distinct(self):
        rid, data = self.intent()
        claimed_success = dict(data, lifecycle_stage='live-return', commit_submitted=True)
        with self.assertRaisesRegex(ValueError, 'precommit intent'):
            cas_ui.receive_socket(self.peer, rid, json.dumps(claimed_success))
        refusal = {'protocol': 1, 'ok': False, 'cas_request_id': rid,
                   'lifecycle_stage': 'accept-result', 'commit_submitted': False, 'commit_attempted': False}
        cas_ui.receive_socket(self.peer, rid, json.dumps(refusal))
        self.assertEqual(cas_ui.result(rid)['outcome'], 'accept-rejected')

    def test_detached_peer_cannot_acknowledge_under_a_new_nonce(self):
        rid, data = self.intent()
        cas_ui.detach_client(self.peer)
        new_peer = cas_ui.attach_client(SIM)
        with self.assertRaisesRegex(ValueError, 'claimed peer'):
            cas_ui.receive_socket(new_peer, rid, json.dumps(data))
        self.assertIsNone(cas_ui.poll_client(new_peer))

    def test_expected_household_is_bound_before_delivery_and_owner_ack(self):
        status = cas_ui.submit(SIM, {'operation': 'status'})['cas_request_id']
        cas_ui.poll_client(self.peer)
        cas_ui.receive_socket(self.peer, status, json.dumps({
            'protocol': 1, 'ok': True, 'cas_request_id': status, 'client': native_client()}))
        rid, data = self.intent()
        data['client']['sim']['householdId'] = '9'
        with self.assertRaisesRegex(ValueError, 'bound original request'):
            cas_ui.receive_socket(self.peer, rid, json.dumps(data))
        self.assertEqual(cas_ui._RECORDS[rid]['request']['household_id'], HOUSEHOLD)
        self.assertEqual(cas_ui._RECORDS[rid]['state'], 'pending')
        self.assertIsNone(cas_ui._RECORDS[rid]['result'])
        self.assertIsNone(cas_ui.poll_client(self.peer))  # Claimed wire cannot replay.

    def test_household_identity_is_exact_and_required_before_any_delivery(self):
        for request in ({'operation': 'accept'},
                        {'operation': 'accept', 'household_id': None},
                        {'operation': 'accept', 'household_id': int(HOUSEHOLD)},
                        {'operation': 'accept', 'household_id': '0'},
                        {'operation': 'accept', 'household_id': '09'},
                        {'operation': 'accept', 'household_id': str(1 << 64)},
                        {'operation': 'accept', 'household_id': '９'}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                cas_ui.submit(SIM, request, send=lambda _: self.fail('invalid request delivered'))
        self.assertFalse(cas_ui._RECORDS)

    def test_long_validated_ack_refreshes_exact_peer_before_immediate_accept(self):
        cas_ui._PEERS[self.peer]['observed_at'] = 0
        rid = cas_ui.submit(SIM, {'operation': 'status'}, clock=lambda: 0)['cas_request_id']
        cas_ui.poll_client(self.peer, clock=lambda: 0)
        data = {'protocol': 1, 'ok': True, 'cas_request_id': rid, 'client': native_client()}
        cas_ui.receive_socket(self.peer, rid, json.dumps(data), clock=lambda: 11)
        self.assertEqual(cas_ui._PEERS[self.peer]['observed_at'], 11)
        accepted = cas_ui.submit(SIM, {'operation': 'accept', 'household_id': HOUSEHOLD}, clock=lambda: 11)
        self.assertEqual(accepted['outcome'], 'pending-client')

    def test_rejected_ack_cannot_refresh_peer_freshness(self):
        cas_ui._PEERS[self.peer]['observed_at'] = 0
        rid = cas_ui.submit(SIM, {'operation': 'status'}, clock=lambda: 0)['cas_request_id']
        cas_ui.poll_client(self.peer, clock=lambda: 0)
        client = native_client(); client['sim']['simId'] = '9'
        with self.assertRaisesRegex(ValueError, 'another selected Sim'):
            cas_ui.receive_socket(self.peer, rid, json.dumps({
                'protocol': 1, 'ok': True, 'cas_request_id': rid, 'client': client}), clock=lambda: 11)
        self.assertEqual(cas_ui._PEERS[self.peer]['observed_at'], 0)

    def test_thrown_native_commit_receipt_is_acknowledged_but_stays_blocked_and_can_only_resolve_from_live(self):
        rid, intent = self.acknowledge()
        unresolved = {'protocol': 1, 'ok': False, 'cas_request_id': rid,
                      'lifecycle_stage': 'accept-result', 'commit_attempted': True,
                      'commit_submitted': False, 'commit_accepted': None, 'commit_outcome': 'unresolved'}
        ack = cas_ui.receive_socket(self.peer, rid, json.dumps(unresolved))
        self.assertTrue(ack['acknowledgement_accepted'])
        self.assertFalse(ack['ui_transition_verified'])
        cas_ui.receive_socket(self.peer, rid, json.dumps(unresolved))
        cas_ui.receive_socket(self.peer, rid, json.dumps(intent))  # Late duplicate cannot downgrade it.
        receipt = cas_ui.result(rid)
        self.assertEqual(receipt['outcome'], 'accept-unresolved')
        self.assertEqual(receipt['accept_intent'], intent)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            cas_ui.submit(SIM, {'operation': 'status'})
        refusal = dict(unresolved, commit_accepted=False)
        with self.assertRaisesRegex(ValueError, 'cannot be replaced'):
            cas_ui.receive_socket(self.peer, rid, json.dumps(refusal))
        cas_ui.detach_client(self.peer)
        cas_ui.observe_return(rid, live_snapshot(), 'baseline', HOUSEHOLD, 30)
        complete = cas_ui.observe_return(rid, live_snapshot('140'), 'complete', HOUSEHOLD, 30)
        self.assertTrue(complete['live_return_verified'])
        receipt = cas_ui.result(rid)
        self.assertTrue(receipt['ok'])
        self.assertEqual(receipt['commit_outcome'], 'unresolved')
        self.assertEqual(receipt['accept_intent'], intent)
        self.assertFalse(complete['commit_submission_verified'])

    def test_producer_clock_progress_completes_only_metadata_and_preserves_intent(self):
        rid, data = self.acknowledge()
        cas_ui.detach_client(self.peer)
        cas_ui.observe_return(rid, live_snapshot(), 'baseline', HOUSEHOLD, 30)
        with self.assertRaisesRegex(ValueError, 'progress'):
            cas_ui.observe_return(rid, live_snapshot('120'), 'complete', HOUSEHOLD, 30)
        with self.assertRaisesRegex(ValueError, 'paused'):
            cas_ui.observe_return(rid, live_snapshot('140', 1), 'complete', HOUSEHOLD, 30)
        result = cas_ui.observe_return(rid, live_snapshot('140'), 'complete', HOUSEHOLD, 30)
        self.assertEqual(result['advanced_ticks'], 40)
        self.assertEqual(result['baseline']['sim_time_source'], 'services.time_service().sim_now')
        self.assertEqual(result['final']['sim_time_source'], 'services.time_service().sim_now')
        self.assertTrue(result['ui_transition_verified'])
        self.assertFalse(result['commit_submission_verified'])
        self.assertFalse(result['appearance_persistence_verified'])
        receipt = cas_ui.result(rid)
        self.assertTrue(receipt['live_return_verified'])
        self.assertTrue(receipt['ui_transition_verified'])
        self.assertEqual(receipt['accept_intent'], data)
        cas_ui.attach_client(SIM)
        cas_ui.submit(SIM, {'operation': 'status'})  # A subsequent CAS entry is no longer blocked.

    def test_server_requires_original_household_no_peer_and_immutable_producer_baseline(self):
        rid, _data = self.acknowledge()
        with self.assertRaisesRegex(ValueError, 'peers remain'):
            cas_ui.observe_return(rid, live_snapshot(), 'baseline', HOUSEHOLD, 30)
        cas_ui.detach_client(self.peer)
        with self.assertRaisesRegex(ValueError, 'native producer'):
            cas_ui.observe_return(rid, None, 'baseline', HOUSEHOLD, 30)
        changed = live_snapshot()
        changed['household_id'] = '9'
        with self.assertRaisesRegex(ValueError, 'original native intent'):
            cas_ui.observe_return(rid, changed, 'baseline', '9', 30)
        cas_ui.observe_return(rid, live_snapshot(), 'baseline', HOUSEHOLD, 30)
        changed = live_snapshot('150')
        changed['client_id'] = '9'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            cas_ui.observe_return(rid, changed, 'complete', HOUSEHOLD, 30)
        with self.assertRaisesRegex(ValueError, 'identity cannot be replaced'):
            cas_ui.observe_return(rid, changed, 'baseline', HOUSEHOLD, 30)
        self.assertEqual(cas_ui.result(rid)['cas_request_state'], 'accept-intent')

    def test_missing_or_game_clock_origin_refuses_positive_return_ticks_without_completion(self):
        for origin in (None, 'services.game_clock_service().now()', 'game-clock', True):
            with self.subTest(origin=origin):
                self.setUp()
                rid, _data = self.acknowledge()
                cas_ui.detach_client(self.peer)
                snapshot = live_snapshot('100000')
                if origin is None:
                    snapshot.pop('sim_time_source')
                else:
                    snapshot['sim_time_source'] = origin
                with self.assertRaisesRegex(ValueError, 'simulation timeline origin'):
                    cas_ui.observe_return(rid, snapshot, 'baseline', HOUSEHOLD, 30)
                self.assertNotIn('return_observation', cas_ui._RECORDS[rid])
                self.assertEqual(cas_ui.result(rid)['cas_request_state'], 'accept-intent')

    def test_old_baseline_origin_cannot_be_upgraded_by_new_positive_snapshot(self):
        rid, _data = self.acknowledge()
        cas_ui.detach_client(self.peer)
        cas_ui.observe_return(rid, live_snapshot(), 'baseline', HOUSEHOLD, 30)
        cas_ui._RECORDS[rid]['return_observation']['baseline'].pop('sim_time_source')
        for phase in ('baseline', 'complete'):
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, 'baseline lacks.*timeline origin'):
                cas_ui.observe_return(rid, live_snapshot('100000'), phase, HOUSEHOLD, 30)
        self.assertEqual(cas_ui.result(rid)['cas_request_state'], 'accept-intent')

    def test_game_thread_dispatch_reads_native_snapshot_instead_of_caller_claims(self):
        rid, _data = self.acknowledge()
        cas_ui.detach_client(self.peer)
        sim = object()
        fake = Obj(_get_sim_info_by_id=lambda _id: sim)
        argument = {'cas_request_id': rid, 'phase': 'baseline', 'household_id': HOUSEHOLD, 'minimum_ticks': 30}
        with patch.object(test_driver, 'guard', return_value=argument), \
                patch.object(test_driver, 'snapshot', return_value=live_snapshot()) as producer:
            result = test_driver.dispatch(fake, 'test_cas_return_observed', SIM, '{}')
        producer.assert_called_once_with(fake, sim)
        self.assertEqual(result['baseline']['sim_now_ticks'], '100')
        with patch.object(test_driver, 'guard', return_value=dict(argument, live_return_verified=True)), \
                patch.object(test_driver, 'snapshot') as producer:
            with self.assertRaisesRegex(ValueError, 'typed CAS return'):
                test_driver.dispatch(fake, 'test_cas_return_observed', SIM, '{}')
        producer.assert_not_called()

    def test_snapshot_retains_exact_native_ids_ticks_and_explicit_missing_queries(self):
        ticks = (1 << 63) + 71
        now = Obj(absolute_ticks=lambda: ticks)
        clock = Obj(clock_speed=0, now=lambda: now)
        zone = Obj(id=25, is_in_build_buy=False, is_zone_running=True)
        persistence = Obj(get_save_slot_proto_buff=lambda: Obj(slot_id=2), get_save_slot_proto_guid=lambda: 23)
        services = Obj(get_persistence_service=lambda: persistence, game_clock_service=lambda: clock,
                       time_service=lambda: Obj(sim_now=now),
                       active_household=lambda: Obj(id=int(HOUSEHOLD)), current_zone=lambda: zone,
                       client_manager=lambda: Obj(get_first_client=lambda: Obj(id=(1 << 63) + 73)))
        result = test_driver.snapshot(Obj(services=services), None)
        self.assertEqual(result['sim_now_ticks'], str(ticks))
        self.assertEqual(result['sim_time_source'], 'services.time_service().sim_now')
        self.assertEqual(result['client_id'], str((1 << 63) + 73))
        self.assertIs(result['zone_running'], True)
        del zone.is_zone_running
        del now.absolute_ticks
        services.client_manager = lambda: Obj(get_first_client=lambda: None)
        result = test_driver.snapshot(Obj(services=services), None)
        self.assertIsNone(result['zone_running'])
        self.assertIsNone(result['sim_now_ticks'])
        self.assertIsNone(result['client_id'])
        self.assertEqual(result['runtime_queries'], {'client_id': 'returned-null', 'zone_running': 'failed',
            'sim_now': 'failed', 'sim_now_ticks': 'failed', 'game_now': 'failed', 'game_now_ticks': 'failed'})


if __name__ == '__main__':
    unittest.main()
