"""Complete, same-peer navigation failures release only their own UI intent."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_ui, cas_socket
from test_cas_slider_postcondition import producer_client
import test_cas_catalog_readback as readback_fixture


def client():
    value = producer_client()
    value['sim'].update(allOccultTypes=127, occultType=4)
    value['form_strip'].update(native_generation='91', session=7)
    return value


class NavigationPostconditionTests(unittest.TestCase):
    def setUp(self):
        cas_ui._RECORDS.clear(); cas_ui._PEERS.clear()
        self.addCleanup(cas_ui._RECORDS.clear); self.addCleanup(cas_ui._PEERS.clear)
        self.peer = cas_ui.attach_client('12', clock=lambda: 0)
        status = cas_ui.submit('12', {'operation': 'status'}, clock=lambda: 0)['cas_request_id']
        cas_ui.poll_client(self.peer, clock=lambda: 0)
        cas_ui.receive_socket(self.peer, status, json.dumps(dict(protocol=1, ok=True,
            cas_request_id=status, client=client())), clock=lambda: 0)
        self.request = dict(operation='catalog-input', key='pagedown', focus_catalog=True)
        self.rid = cas_ui.submit('12', self.request, clock=lambda: 0)['cas_request_id']
        cas_ui.poll_client(self.peer, clock=lambda: 0)
        value = client()
        receipt = dict(key=34, sim_id='12', owner_id='active/2', menu_state=value['menu_state'],
            menu_state_before=value['menu_state'], source_route='shared-keyboard-handler',
            index_before=101, index_after=149, count=176, columns=6, page_step=48, click_dispatched=False)
        workspace = dict(error='', context='12|active/2', outfit=dict(category=0, index=0),
            keyboard=dict(index=149, pending=0, queued=0, receipt=receipt, visibility=dict(available=False)))
        value.update(catalog_workspace=workspace, control=dict(operation='catalog-input',
            handler_invoked=True, focus_requested=True, appearance_write_possible=False, workspace=workspace))
        self.packet = dict(protocol=1, ok=True, cas_request_id=self.rid, operation='catalog-input',
            scope='native-cas-client', mutation_started=False, client=value)

    def timeout_packet(self):
        result = copy.deepcopy(self.packet); result['ok'] = False
        result['message'] = 'Native catalog navigation did not publish its focused card before the bounded deadline'
        context = copy.deepcopy(cas_ui._RECORDS[self.rid]['navigation_owner_lease']['context'])
        result['navigation_publication'] = dict(protocol=1, request_id=self.rid, peer_nonce=self.peer,
            before=context, after=copy.deepcopy(context), key=34, target_index=149, elapsed_ms=10000,
            published=False, appearance_written=False)
        return result

    def test_original_complete_ui_failure_consumes_one_ack_without_retry(self):
        raw = json.dumps(self.packet)
        def acknowledge(peer, rid, payload):
            return cas_ui.receive_socket(peer, rid, payload, clock=lambda: 1)['acknowledgement_accepted']
        reply, _ = cas_socket.packet('ACK|' + self.peer + '|' + self.rid + '|' + raw,
            self.peer, attach=None, poll=None, acknowledge=acknowledge)
        self.assertEqual(reply, 'ACK|' + self.rid)
        failed = cas_ui.result(self.rid)
        for key in ('ok', 'mutation_started', 'retry_submitted', 'postcondition_verified', 'ui_transition_verified'):
            self.assertIs(failed[key], False)
        self.assertEqual(failed['cas_request_state'], 'failed')
        self.assertEqual(failed['outcome'], 'native-postcondition-failed')
        self.assertEqual(failed['native_acknowledgement'], self.packet)
        self.assertEqual(failed['native_acknowledgement_sha256'], cas_ui._baseline_hash(self.packet))
        cas_ui.receive_socket(self.peer, self.rid, raw, clock=lambda: 1)
        self.assertEqual(cas_ui.result(self.rid), failed)
        following = cas_ui.submit('12', {'operation': 'status'}, clock=lambda: 1)
        self.assertNotEqual(following['cas_request_id'], self.rid)
        self.assertIsNotNone(cas_ui.poll_client(self.peer, clock=lambda: 1))

    def test_typed_timeout_is_definite_failure_and_retains_original_complete_evidence(self):
        packet = self.timeout_packet()
        result = cas_ui.receive_socket(self.peer, self.rid, json.dumps(packet), clock=lambda: 11)
        self.assertTrue(result['acknowledgement_accepted'])
        failed = cas_ui.result(self.rid)
        self.assertEqual(failed['cas_request_state'], 'failed')
        self.assertEqual(failed['native_acknowledgement'], packet)
        self.assertFalse(failed['retry_submitted']); self.assertFalse(failed['mutation_started'])

    def test_visible_published_navigation_still_uses_normal_success_validation(self):
        self.packet['client']['catalog_workspace']['keyboard']['visibility'] = dict(
            available=True, fully_visible=True, focus_visible=True)
        cas_ui.receive_socket(self.peer, self.rid, json.dumps(self.packet), clock=lambda: 1)
        self.assertTrue(cas_ui.result(self.rid)['ok'])
        self.assertEqual(cas_ui.result(self.rid)['cas_request_state'], 'completed')

    def test_semantic_non_enter_route_has_the_same_narrow_failure_classifier(self):
        row = cas_ui._RECORDS[self.rid]
        row['request'] = dict(operation='catalog-key', key='pagedown')
        row['wire'] = row['wire'].replace('|catalog-input|', '|catalog-key|')
        self.packet['operation'] = 'catalog-key'
        control = self.packet['client']['control']
        control.clear(); control.update(operation='catalog-key', appearance_written=False,
            workspace=self.packet['client']['catalog_workspace'])
        control['workspace']['keyboard']['receipt']['source_route'] = 'semantic-navigation'
        cas_ui.receive_socket(self.peer, self.rid, json.dumps(self.packet), clock=lambda: 1)
        self.assertEqual(cas_ui.result(self.rid)['cas_request_state'], 'failed')

    def test_foreign_incomplete_movement_or_appearance_possible_stays_pending(self):
        original_lease = copy.deepcopy(cas_ui._RECORDS[self.rid]['navigation_owner_lease'])
        modes = ('sim', 'household', 'owner', 'session', 'layer', 'generation', 'menu', 'outfit', 'mask', 'shell',
            'gesture', 'unbound', 'catalog', 'workspace', 'possible-write', 'mutation', 'click', 'count',
            'movement', 'pending', 'queued', 'receipt-extra', 'envelope-extra', 'route', 'lease', 'enter', 'peer')
        for mode in modes:
            with self.subTest(mode=mode):
                row = cas_ui._RECORDS[self.rid]; row.update(state='pending', result=None,
                    navigation_owner_lease=copy.deepcopy(original_lease), request=copy.deepcopy(self.request), peer=self.peer)
                packet = copy.deepcopy(self.packet); c = packet['client']; w = c['catalog_workspace']
                r = w['keyboard']['receipt']
                if mode == 'sim': c['sim']['simId'] = '13'
                elif mode == 'household': c['sim']['householdId'] = '23'
                elif mode == 'owner': c['form_strip']['selected_owner_id'] = 'native/4'
                elif mode == 'session': c['owner_pair_observation']['session'] += 1
                elif mode == 'layer': c['sim']['occultLayer'] = 1
                elif mode == 'generation': c['form_strip']['native_generation'] = '92'
                elif mode == 'menu': c['menu_state'] += 1
                elif mode == 'outfit': c['outfit']['outfit_index'] = 1
                elif mode == 'mask': c['sim']['allOccultTypes'] = 65
                elif mode == 'shell': c['sim']['occultType'] = 2
                elif mode == 'gesture': c['form_strip']['gesture_pending'] = True
                elif mode == 'unbound': c['form_strip']['native_owner_state'] = 'pending'
                elif mode == 'catalog': c['catalogs'].pop()
                elif mode == 'workspace': w['error'] = 'unknown'
                elif mode == 'possible-write': c['control']['appearance_write_possible'] = True
                elif mode == 'mutation': packet['mutation_started'] = True
                elif mode == 'click': r['click_dispatched'] = True
                elif mode == 'count': r['count'] = True
                elif mode == 'movement': r['index_after'] = 150
                elif mode == 'pending': w['keyboard']['pending'] = 34
                elif mode == 'queued': w['keyboard']['queued'] = 1
                elif mode == 'receipt-extra': r['foreign'] = 'unknown'
                elif mode == 'envelope-extra': packet['foreign'] = 'unknown'
                elif mode == 'route': r['source_route'] = 'stage-keyboard-event'
                elif mode == 'lease': row.pop('navigation_owner_lease')
                elif mode == 'enter': row['request']['key'] = 'enter'
                else: row['navigation_owner_lease']['peer'] = 'f' * 64
                with self.assertRaises((ValueError, TypeError, KeyError)):
                    cas_ui.receive_socket(self.peer, self.rid, json.dumps(packet), clock=lambda: 1)
                self.assertEqual(row['state'], 'pending')

    def test_timeout_missing_corrupt_or_foreign_proof_remains_quarantined(self):
        good = self.timeout_packet()
        for mode in ('before', 'after', 'nonce', 'uuid', 'elapsed', 'bool-elapsed', 'key', 'target', 'published',
                     'write', 'extra', 'protocol', 'message', 'unknown-after', 'null-after'):
            with self.subTest(mode=mode):
                packet = copy.deepcopy(good); p = packet['navigation_publication']
                if mode in ('before', 'after'): p[mode]['native_generation'] = '92'
                elif mode == 'nonce': p['peer_nonce'] = 'f' * 64
                elif mode == 'uuid': p['request_id'] = 'f' * 32
                elif mode == 'elapsed': p['elapsed_ms'] = 9999
                elif mode == 'bool-elapsed': p['elapsed_ms'] = True
                elif mode == 'key': p['key'] = 13
                elif mode == 'target': p['target_index'] = 150
                elif mode == 'published': p['published'] = True
                elif mode == 'write': p['appearance_written'] = True
                elif mode == 'extra': p['unknown'] = True
                elif mode == 'protocol': p['protocol'] = True
                elif mode == 'message': packet['message'] = 'unknown'
                elif mode == 'unknown-after': p['after']['unknown'] = 1
                else: p['after'] = None
                with self.assertRaises(ValueError):
                    cas_ui.receive_socket(self.peer, self.rid, json.dumps(packet), clock=lambda: 11)
                self.assertEqual(cas_ui._RECORDS[self.rid]['state'], 'pending')

    def test_changed_terminal_ack_is_not_reclassified_or_replayed(self):
        cas_ui.receive_socket(self.peer, self.rid, json.dumps(self.packet), clock=lambda: 1)
        failed = cas_ui.result(self.rid)
        self.packet['client']['catalog_workspace']['keyboard']['receipt']['count'] = 177
        with self.assertRaises(ValueError):
            cas_ui.receive_socket(self.peer, self.rid, json.dumps(self.packet), clock=lambda: 2)
        self.assertEqual(cas_ui.result(self.rid), failed)

    def test_authenticated_completed_thin_status_can_lease_navigation_without_full_inventory(self):
        # The prior thin record is admitted through its real peer/nonce guard.
        cas_ui._RECORDS.clear(); cas_ui._PEERS.clear()
        fixture = readback_fixture.HostReadbackTests(); fixture.setUp()
        self.addCleanup(cas_ui._RECORDS.clear); self.addCleanup(cas_ui._PEERS.clear)
        packet = fixture.packet()
        cas_ui.receive_socket(fixture.token, fixture.rid, json.dumps(packet), clock=lambda: 1)
        rid = cas_ui.submit('12', dict(operation='catalog-key', key='pagedown'), clock=lambda: 1)['cas_request_id']
        self.assertEqual(cas_ui._RECORDS[rid]['navigation_owner_lease'],
            dict(peer=fixture.token, context=fixture.context))


if __name__ == '__main__': unittest.main()
