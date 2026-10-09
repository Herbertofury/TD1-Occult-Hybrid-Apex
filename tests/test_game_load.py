import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools')]
import game_load
import game_lifecycle
from test_game_save import SaveFixture, SIM, HOUSEHOLD, GUID


def screen(labels):
    return {'ok': True, 'width': 1278, 'height': 1376,
            'lines': [{'text': label, 'words': [{'text': label, 'x': 400, 'y': 100 + 35 * index,
                                               'width': 350, 'height': 25}]} for index, label in enumerate(labels)]}


def load_screen(name):
    observed = screen(['LOAD GAME', name, 'PLAY'])
    observed['lines'][2]['words'][0].update(x=900, y=135, width=75)
    return observed


class LoadMenuTests(unittest.TestCase):
    def test_complete_home_required_and_modal_never_dismissed(self):
        home = ['HOME', 'MARKETPLACE', 'LOAD GAME', 'NEW GAME', 'GALLERY']
        self.assertEqual(game_load.menu_target(screen(home), 'home', 'My test')['command'], 1)
        for labels in (['Load Game'], home + ['BUY NOW'], home + ['LOAD GAME']):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                game_load.menu_target(screen(labels), 'home', 'My test')

    def test_exact_unique_name_and_play_not_load_label(self):
        labels = ['LOAD GAME', 'My test', 'PLAY']
        self.assertEqual(game_load.menu_target(load_screen('My test'), 'play', 'My test')['y'], 148)
        for values in (['LOAD GAME', 'Other save', 'PLAY'], labels + ['My test'],
                       ['LOAD GAME', 'My test', 'LOAD']):
            with self.subTest(values=values), self.assertRaises(ValueError):
                game_load.menu_target(screen(values), 'play', 'My test')

    def test_unmeasured_nonfinite_or_outside_target_refused(self):
        for bounds in ({'x': float('nan')}, {'x': -1}, {'width': 2000}, {'height': True}):
            item = load_screen('My test')
            item['lines'][2]['words'][0].update(bounds)
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                game_load.menu_target(item, 'play', 'My test')

    def test_play_is_scoped_to_named_row_even_with_autosave_and_background_home(self):
        observed = load_screen('My Saved Game I')
        observed['lines'] += screen(['HOME', 'MARKETPLACE'])['lines']
        observed['lines'].append({'text': 'Play', 'words': [{'x': 900, 'y': 250, 'width': 75, 'height': 25}]})
        self.assertEqual(game_load.menu_target(observed, 'play', 'My Saved Game 1')['y'], 148)
        observed['lines'].append({'text': 'Play', 'words': [{'x': 1000, 'y': 135, 'width': 75, 'height': 25}]})
        with self.assertRaisesRegex(ValueError, 'unique measured'):
            game_load.menu_target(observed, 'play', 'My Saved Game 1')

    def test_other_name_aliases_and_duplicate_matching_row_are_refused(self):
        with self.assertRaises(ValueError):
            game_load.menu_target(load_screen('My Saved Game Z'), 'play', 'My Saved Game 2')
        observed = load_screen('My Saved Game I')
        observed['lines'] += load_screen('My Saved Game 1')['lines'][1:2]
        with self.assertRaises(ValueError):
            game_load.menu_target(observed, 'play', 'My Saved Game 1')


class LoadTests(SaveFixture):
    def run_load(self, *, slot=2, inputs=None, wrong_hash=False, changed_identity=False,
                 active_cas=False, snapshots=None):
        calls, clock = [], [0.0]
        name = 'Apex Disposable Test'
        live = {'ok': True, 'save_slot': slot, 'save_guid': GUID, 'household_id': HOUSEHOLD,
                'in_build_buy': False, 'zone_running': True, 'zone_id': '42', 'client_id': '7', 'clock_speed': 0,
                'sim': {'id': SIM, 'instanced': True},
                'runtime_queries': {'client_id': 'returned-value', 'zone_running': 'returned-value'},
                'persistence': {'persistence_verified_before_save': True, 'checks': {
                    key: True for key in ('active_household_membership', 'runtime_household_identity',
                    'manager_identity', 'account_save_eligible', 'sim_proto_exists', 'sim_proto_identity',
                    'sim_proto_household_identity', 'household_proto_exists', 'household_proto_identity',
                    'household_proto_membership')}}}
        snapshots = list(snapshots or [{'ok': False}, live, live])
        inputs = list(inputs or [{'ok': True}, {'ok': True}])
        diagnostics = {'ok': True, 'native_initializer_observed': False, 'native_peers': [], 'requests': [],
                       'socket_transport': {'bound': True, 'host': '127.0.0.1', 'port': 8021,
                                            'startup_error': None, 'native_connection_verified': False}}
        if active_cas:
            diagnostics['native_peers'] = [{'sim_id': SIM, 'age_seconds': 0}]
        frames = [screen(['HOME', 'MARKETPLACE', 'LOAD GAME', 'NEW GAME', 'GALLERY']),
                  load_screen(name)]
        def request(_state, action, **kwargs):
            calls.append((action, kwargs))
            if action == 'test_snapshot':
                return copy.deepcopy(snapshots.pop(0) if len(snapshots) > 1 else snapshots[0])
            if action == 'test_input':
                return inputs.pop(0)
            if action == 'cas_ui_diagnostics':
                return diagnostics
            if action == 'overlay_hide':
                return {'ok': True, 'visible': False}
            raise AssertionError('Unexpected load action ' + action)
        def capture(_state, _image, _request):
            return {'ok': True, 'width': 1278, 'height': 1376}
        current = dict(self.identity, pid=43) if changed_identity else self.identity
        with patch.object(game_load.game_capture, 'prepare_window'):
            result = game_load.observe(self.state, self.root / 'load-proof.json', self.identity, request,
                SIM, HOUSEHOLD, GUID, 2, name, '0' * 64 if wrong_hash else self.digest,
                seconds=1, capture=capture, ocr=lambda _image: frames.pop(0),
                identity_provider=lambda _state: current, alive=lambda _pid: True,
                metadata_reader=lambda _path, _hash: {'slot_id': 2, 'slot_name': name,
                    'save_guid': GUID, 'active_household_id': HOUSEHOLD},
                monotonic=lambda: clock[0], pause=lambda value: clock.__setitem__(0, clock[0] + value))
        proof = json.loads((self.root / 'load-proof.json').read_bytes())
        self.assertEqual(self.original_save.read_bytes(), b'owner save must never change')
        self.assertEqual(self.slot.read_bytes(), b'existing disposable test save')
        return result, proof, calls

    def test_exact_native_slot_persistence_live_and_pause_required(self):
        result, proof, calls = self.run_load()
        self.assertTrue(result['ok']); self.assertTrue(proof['save_files_unchanged'])
        self.assertEqual(sum(action == 'test_input' for action, _kw in calls), 2)
        self.assertTrue(proof['native_slot_verified'])
        self.assertFalse(proof['save_file_written'])

    def test_autosave_sentinel_never_inferred_as_normal_slot(self):
        result, proof, _calls = self.run_load(slot=0xffffffff)
        self.assertFalse(result['ok']); self.assertFalse(proof['native_slot_verified'])
        self.assertIn('Actual native save slot differs', result['message'])

    def test_exact_save_hash_refusal_before_any_transport(self):
        with self.assertRaisesRegex(ValueError, 'existing save changed'):
            self.run_load(wrong_hash=True)
        self.assertFalse((self.root / 'load-proof.json').exists())

    def test_changed_process_or_active_cas_prevents_any_input(self):
        for flag in ('changed_identity', 'active_cas'):
            with self.subTest(flag=flag):
                path = self.root / 'load-proof.json'
                if path.exists(): path.unlink()
                result, _proof, calls = self.run_load(**{flag: True})
                self.assertFalse(result['ok'])
                self.assertFalse(any(action == 'test_input' for action, _kw in calls))

    def test_rejected_or_ambiguous_input_not_repeated(self):
        result, proof, calls = self.run_load(inputs=[{'ok': False, 'outcome': 'unresolved'}])
        self.assertFalse(result['ok'])
        self.assertEqual(sum(action == 'test_input' for action, _kw in calls), 1)
        self.assertFalse(proof['input_replay_attempted'])

    def test_map_without_instanced_live_is_not_completion(self):
        result, proof, calls = self.run_load(snapshots=[{'ok': False}])
        self.assertFalse(result['ok']); self.assertFalse(proof['native_live_verified'])
        self.assertEqual(sum(action == 'test_input' for action, _kw in calls), 2)
        self.assertIn('neighborhood map remains unresolved', result['message'])


if __name__ == '__main__':
    unittest.main()
