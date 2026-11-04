import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_discard
import game_lifecycle


def live():
    return {'ok': True, 'household_id': '22', 'save_guid': '33', 'zone_id': '44',
        'client_id': '5', 'clock_speed': 0, 'zone_running': True, 'in_build_buy': False,
        'sim_now_ticks': '100', 'runtime_queries': {name: 'returned-value'
            for name in ('client_id', 'zone_running', 'sim_now_ticks')}}


def diagnostic():
    return {'ok': True, 'native_initializer_observed': True,
        'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021,
            'native_connection_verified': False, 'startup_error': None},
        'native_peers': [], 'requests': [{'cas_request_id': 'a' * 32,
            'state': 'accept-intent', 'operation': 'accept', 'age_seconds': 8}]}


def observation(labels):
    return {'ok': True, 'width': 800, 'height': 600,
        'lines': [{'text': label, 'words': [{'x': 100, 'y': index * 25 + 5,
            'width': 100, 'height': 15}]} for index, label in enumerate(labels)]}


class DiscardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile, self.original = self.root / 'The Sims 4', self.root / 'protected'
        self.profile.mkdir(); self.original.mkdir()
        self.identity = {'pid': 8, 'test_token': 'b' * 32, 'script_sha256': 'c' * 64,
            'profile': str(self.profile)}
        self.journal = {'token': 'b' * 32, 'artifacts': [
            {'name': 'ApexOccultHybrid.ts4script', 'sha256': 'c' * 64}]}
        self.failed = {'schema': 1, 'operation': 'semantic-cas-return-to-live',
            'ok': False, 'outcome': 'unresolved', 'accept_submitted': True,
            'accept_intent_observed': True, 'cas_peer_disappearance_verified': True,
            'process_exit_verified': False, 'input_submitted': False,
            'sim_id': '11', 'household_id': '22', 'cas_request_id': 'a' * 32,
            'identity': self.identity, 'crash': {'outcome': 'unchanged'},
            'steps': [{'action': 'test_snapshot', 'result': live()}]}
        self.failed_path = self.root / 'failed.json'
        self.failed_path.write_text(json.dumps(self.failed), encoding='utf-8')
        self.pin = hashlib.sha256(self.failed_path.read_bytes()).hexdigest()
        self.saved = {'Slot_00000002.save': {'sha256': 'd' * 64, 'bytes': 40, 'mtime_ns': 1}}
        self.actions, self.time, self.active = [], 0., True
        self.capture_number = 0
        self.request_failure = None
        self.crash_result = {'outcome': 'unchanged'}

    def request(self, _state, action, **kwargs):
        self.actions.append(action)
        if action == self.request_failure:
            raise OSError('Lost response after submission')
        if action == 'cas_ui_diagnostics': return diagnostic()
        if action == 'test_snapshot': return live()
        if action == 'overlay_hide': return {'ok': True, 'visible': False}
        if action == 'test_input':
            value = json.loads(kwargs['value'])['value']
            if value['y'] == 112: self.active = False  # Confirmation Exit Game.
            return {'ok': True, 'input_version': 2, 'input_submitted': True, 'input_state': 4}
        return {'ok': True}

    def capture(self, _state, _image, _request):
        self.capture_number += 1
        return {'ok': True, 'capture_completed_verified': True, 'width': 800, 'height': 600}

    def ocr(self, _image):
        if self.capture_number == 1: return observation(['Paused'])
        if self.capture_number == 2: return observation(['Menu', 'Save', 'Save As', 'Exit Game'])
        return observation(['Save Game?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Cancel', 'Exit Game'])

    def sleep(self, seconds): self.time += seconds

    def run_observer(self, **extra):
        with patch.object(game_discard.reusable_profile, 'load', return_value=(self.root / 'state.json', self.journal, self.profile, self.original)), \
                patch.object(game_discard.game_lifecycle, 'save_files', side_effect=lambda _profile: copy.deepcopy(self.saved)), \
                patch.object(game_discard.cas_transition, 'read_crash', return_value=({'state': 'absent'}, None)), \
                patch.object(game_discard.cas_transition, 'preserve_crash', side_effect=lambda *_args: self.crash_result):
            return game_discard.observe(self.root / 'state.json', self.root / 'out.json', self.identity,
                self.request, self.failed_path, self.pin, '11', '22', '33', capture=self.capture,
                ocr=self.ocr, alive=lambda _pid: self.active, monotonic=lambda: self.time,
                pause=self.sleep, **extra)

    def test_normal_discard_never_saves_and_all_files_unchanged(self):
        result = self.run_observer()
        self.assertTrue(result['ok'])
        self.assertTrue(result['save_files_unchanged_verified'])
        self.assertEqual(self.actions.count('test_quit'), 1)
        self.assertEqual(self.actions.count('test_input'), 2)
        self.assertNotIn('test_save', self.actions)
        self.assertEqual(diagnostic()['requests'][0]['state'], 'accept-intent')

    def test_lost_quit_response_is_not_repeated(self):
        self.request_failure = 'test_quit'
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(self.actions.count('test_quit'), 1)
        self.assertNotIn('test_input', self.actions)

    def test_lost_input_response_is_not_repeated(self):
        self.request_failure = 'test_input'
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertEqual(self.actions.count('test_input'), 1)

    def test_pinned_proof_change_refuses_before_transport(self):
        self.failed_path.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_observer()
        self.assertEqual(self.actions, [])

    def test_wrong_identity_success_or_remaining_cas_refuses(self):
        for change in ({'ok': True}, {'cas_peer_disappearance_verified': False}, {'sim_id': '12'},
                {'input_submitted': True}, {'accept_intent_observed': False}, {'identity': {}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                game_discard.failed_context(dict(self.failed, **change), self.identity, '11', '22', '33')

    def test_missing_sim_live_requires_paused_typed_exact_context(self):
        for change in ({'sim': {'id': '11'}}, {'clock_speed': 1}, {'clock_speed': False},
                {'zone_running': False}, {'household_id': '23'}, {'save_guid': '34'},
                {'client_id': None}, {'runtime_queries': {}}):
            with self.subTest(change=change):
                self.assertFalse(game_discard.missing_sim_live(dict(live(), **change), '22', '33'))

    def test_other_unresolved_slot_or_any_peer_refuses(self):
        for state in ('pending', 'accept-intent', 'unknown'):
            value = diagnostic()
            value['requests'].append({'cas_request_id': 'e' * 32, 'state': state,
                'operation': 'status', 'age_seconds': 1})
            with self.subTest(state=state), self.assertRaises(ValueError):
                game_discard.discard_cas_state(value, 'a' * 32)
        value = diagnostic(); value['native_peers'] = [{'sim_id': '11', 'age_seconds': 999}]
        with self.assertRaises(ValueError): game_discard.discard_cas_state(value, 'a' * 32)

    def test_unknown_duplicate_or_changed_intent_refuses(self):
        for change in ({'state': 'completed'}, {'operation': 'status'}, {'cas_request_id': 'e' * 32}):
            value = diagnostic(); value['requests'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                game_discard.discard_cas_state(value, 'a' * 32)
        value = diagnostic(); value['requests'].append(copy.deepcopy(value['requests'][0]))
        with self.assertRaises(ValueError): game_discard.discard_cas_state(value, 'a' * 32)

    def test_confirmation_discard_uses_exit_not_save_and_exit(self):
        value = observation(['Save Game?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Cancel', 'Exit Game'])
        self.assertNotEqual(game_lifecycle.button(value, 'confirmation'), game_lifecycle.button(value, 'confirmation-discard'))
        value['lines'].pop(2)
        with self.assertRaises(ValueError): game_lifecycle.button(value, 'confirmation-discard')

    def test_changed_live_context_refuses_before_quit(self):
        base = self.request
        def changed(state, action, **kwargs):
            result = base(state, action, **kwargs)
            return dict(result, zone_id='45') if action == 'test_snapshot' else result
        self.request = changed
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertNotIn('test_quit', self.actions)

    def test_save_change_overrides_normal_exit(self):
        base = self.request
        def changed(state, action, **kwargs):
            result = base(state, action, **kwargs)
            if action == 'test_input' and not self.active:
                self.saved['Slot_00000002.save']['sha256'] = 'e' * 64
            return result
        self.request = changed
        result = self.run_observer()
        self.assertTrue(result['normal_exit_verified'])
        self.assertFalse(result['ok'])
        self.assertFalse(result['save_files_unchanged_verified'])

    def test_changed_refused_crash_overrides_exit(self):
        self.crash_result = {'outcome': 'refused', 'preserved': False,
            'after': {'state': 'read', 'sha256': 'e' * 64}}
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertTrue(result['game_exit_verified'])
        self.assertFalse(result['normal_exit_verified'])

    def test_other_active_cas_request_refuses_without_input(self):
        base = self.request
        def changed(state, action, **kwargs):
            result = base(state, action, **kwargs)
            if action == 'cas_ui_diagnostics':
                result['requests'].append({'cas_request_id': 'e' * 32, 'operation': 'panel',
                    'state': 'pending', 'age_seconds': 1})
            return result
        self.request = changed
        result = self.run_observer()
        self.assertFalse(result['ok'])
        self.assertNotIn('overlay_hide', self.actions)
        self.assertNotIn('test_quit', self.actions)
        self.assertNotIn('test_input', self.actions)


if __name__ == '__main__': unittest.main()
