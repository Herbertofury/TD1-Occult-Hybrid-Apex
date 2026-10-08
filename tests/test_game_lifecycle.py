from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ea_native_permission
import game_lifecycle


def observed(labels, width=1278, height=1376):
    return {'ok': True, 'width': width, 'height': height,
            'lines': [{'text': text, 'words': [{'text': text, 'x': 500, 'y': 400 + index * 30,
                                               'width': 150, 'height': 20}]} for index, text in enumerate(labels)]}


class LifecycleTests(unittest.TestCase):
    def resume_surface(self):
        return observed(['HOME', 'MARKETPLACE', 'RESUME GAME', 'LOAD GAME', 'NEW GAME', 'GALLERY'])

    def loaded_snapshot(self, sim_id='285159751289798669'):
        return {'ok': True, 'save_slot': 2, 'save_guid': '1841692672',
                'zone_id': '285159751312710719', 'household_id': '285159751289798668',
                'in_build_buy': False, 'sim': {'id': sim_id, 'instanced': True}}

    def run_resume(self, *, inputs=None, snapshots=None, frames=None, sim_id=None,
                   seconds=1, mismatched_viewport=False):
        inputs = list(inputs or [{'ok': True}])
        snapshots = list(snapshots or [self.loaded_snapshot()])
        frames = list(frames or [self.resume_surface()])
        calls, clock = [], [0.0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile, original = root / 'profile', root / 'original'
            (profile / 'saves').mkdir(parents=True); original.mkdir()
            (profile / 'saves/Slot_00000002.save').write_bytes(b'previously saved test household')
            (original / 'owner-save').write_bytes(b'protected original')
            def request(_state, action, **kwargs):
                calls.append((action, kwargs))
                if action == 'test_input':
                    return inputs.pop(0)
                if action == 'test_snapshot':
                    result = snapshots.pop(0) if snapshots else {'ok': False}
                    if isinstance(result, Exception):
                        raise result
                    return result
                return {'ok': True}
            def capture(_state, _image, _request):
                calls.append(('capture', {}))
                return {'ok': True, 'width': 1277 if mismatched_viewport else 1278,
                        'height': 1376, 'sha256': 'a' * 64}
            def ocr(_image):
                return frames.pop(0) if len(frames) > 1 else frames[0]
            with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                    {'token': 'a' * 32, 'artifacts': []}, profile, original)):
                result = game_lifecycle.resume('state', root / 'proof.json', {'pid': 42}, request,
                    sim_id=sim_id, seconds=seconds, capture=capture, ocr=ocr,
                    processes=lambda: [{'Id': 42}], monotonic=lambda: clock[0],
                    pause=lambda duration: clock.__setitem__(0, clock[0] + duration))
            proof = json.loads((root / 'proof.json').read_text(encoding='utf-8'))
            self.assertEqual((original / 'owner-save').read_bytes(), b'protected original')
            self.assertEqual((profile / 'saves/Slot_00000002.save').read_bytes(), b'previously saved test household')
        return result, proof, calls

    def test_resume_requires_complete_home_surface_not_just_a_matching_word(self):
        self.assertEqual(game_lifecycle.button(self.resume_surface(), 'resume')['y'], 470)
        for labels in (['RESUME GAME'], ['HOME', 'MARKETPLACE', 'LOAD GAME', 'NEW GAME', 'GALLERY'],
                       ['HOME', 'MARKETPLACE', 'RESUME GAME', 'RESUME', 'LOAD GAME', 'NEW GAME', 'GALLERY']):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                game_lifecycle.button(observed(labels), 'resume')

    def test_resume_rejects_pack_card_and_duplicate_resume_even_with_background_menu(self):
        for extra in ('EXPANSION PACK', 'BUY NOW', 'RESUME GAME', 'Cancel'):
            frame = self.resume_surface()
            frame['lines'].append(observed([extra])['lines'][0])
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                game_lifecycle.button(frame, 'resume')
        failed_ocr = dict(self.resume_surface(), ok=False)
        with self.assertRaises(ValueError):
            game_lifecycle.button(failed_ocr, 'resume')

    def test_resume_proves_existing_live_household_after_one_press_and_waits_for_loading(self):
        expected = '285159751289798669'
        result, proof, calls = self.run_resume(sim_id=expected,
            snapshots=[ValueError('Load the disposable household before in-game commands.'), self.loaded_snapshot(expected)])
        self.assertTrue(result['ok'])
        self.assertTrue(result['household_loaded_verified'])
        self.assertFalse(result['save_reload_verified'])
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 1)
        snapshot_calls = [kwargs for action, kwargs in calls if action == 'test_snapshot']
        self.assertEqual([row['sim_id'] for row in snapshot_calls], [expected, expected])
        self.assertEqual(proof['loaded_household']['sim']['id'], expected)

    def test_resume_successful_input_does_not_repeat_when_household_proof_is_wrong(self):
        invalid = self.loaded_snapshot('other Sim')
        result, proof, calls = self.run_resume(sim_id='285159751289798669', snapshots=[invalid])
        self.assertFalse(result['ok'])
        self.assertTrue(result['resume_input_accepted'])
        self.assertFalse(proof['household_loaded_verified'])
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)

    def test_resume_ambiguous_or_other_native_failure_cannot_replay_input(self):
        for failure in ({'ok': False}, {'ok': False, 'input_version': 2, 'input_submitted': False, 'native_code': -7},
                        {'ok': False, 'input_version': 2, 'input_submitted': True, 'native_code': -2}):
            result, _proof, calls = self.run_resume(inputs=[failure])
            with self.subTest(failure=failure):
                self.assertFalse(result['ok'])
                self.assertEqual(sum(action == 'test_input' for action, _ in calls), 1)
                self.assertFalse(any(action == 'test_snapshot' for action, _ in calls))

    def test_resume_only_explicit_minus_two_before_input_can_reobserve_and_retry(self):
        refusal = {'ok': False, 'input_version': 2, 'input_submitted': False, 'native_code': -2}
        result, _proof, calls = self.run_resume(inputs=[refusal, {'ok': True}])
        self.assertTrue(result['ok'])
        self.assertEqual(sum(action == 'test_input' for action, _ in calls), 2)
        self.assertEqual(sum(action == 'capture' for action, _ in calls), 2)
        actions = [action for action, _ in calls]
        self.assertEqual(actions[:5], ['overlay_hide', 'capture', 'test_input', 'capture', 'test_input'])

    def test_resume_never_clicks_a_pack_card_or_a_changed_viewport(self):
        card = self.resume_surface()
        card['lines'].append(observed(['BUY NOW'])['lines'][0])
        for options in ({'frames': [card]}, {'mismatched_viewport': True}):
            result, _proof, calls = self.run_resume(**options)
            with self.subTest(options=options):
                self.assertFalse(result['ok'])
                self.assertFalse(any(action == 'test_input' for action, _ in calls))

    def test_loaded_household_rejects_scratch_slot_unsaved_game_and_non_live_sim(self):
        good = self.loaded_snapshot()
        prior = {'Slot_00000002.save': {}}
        self.assertTrue(game_lifecycle.loaded_household(good, prior))
        for change in ({'save_slot': 0xffffffff}, {'save_slot': 0}, {'save_slot': 3},
                       {'household_id': None}, {'in_build_buy': True},
                       {'sim': {'id': good['sim']['id'], 'instanced': False}}):
            with self.subTest(change=change):
                self.assertFalse(game_lifecycle.loaded_household(dict(good, **change), prior))

    def test_confirmation_requires_complete_prompt_and_one_save_and_exit(self):
        frame = observed(['SAVE GAME?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Exit Game', 'Cancel'])
        self.assertEqual(game_lifecycle.button(frame, 'confirmation')['y'], 470)
        frame['lines'].append(frame['lines'][2])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            game_lifecycle.button(frame, 'confirmation')
        with self.assertRaisesRegex(ValueError, 'not recognized'):
            game_lifecycle.button(observed(['Exit Game', 'Save and Exit']), 'confirmation')

    def test_confirmation_cannot_be_mistaken_for_main_menu(self):
        frame = observed(['MENU', 'Save', 'Save As...', 'Exit Game', 'SAVE GAME?'])
        with self.assertRaisesRegex(ValueError, 'main menu'):
            game_lifecycle.button(frame, 'menu')
        with self.assertRaisesRegex(ValueError, 'viewport'):
            game_lifecycle.button(observed(['MENU', 'Save', 'Save As...', 'Exit Game'], width=400), 'menu')

    def test_ea_access_error_cannot_trigger_the_permission_handler(self):
        frame = observed(['You don’t have access', 'Log in to a different account or restart the app to try again.', 'OK', 'CLOSE'])
        with self.assertRaisesRegex(ValueError, 'exact EA'):
            ea_native_permission.dialog_button(frame)
        exact = observed(['This game requires permissions',
            'This game requires administrative privileges. Do you want to grant access and launch the game?', 'OK', 'CLOSE'])
        self.assertEqual(ea_native_permission.dialog_button(exact), (575, 470))

    def test_shutdown_proves_real_slot_rewrite_and_never_touches_scratch_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile, original = root / 'profile', root / 'original'
            (profile / 'saves').mkdir(parents=True); original.mkdir()
            slot = profile / 'saves/Slot_00000002.save'; slot.write_bytes(b'original test save')
            scratch = profile / 'saves/Slot_ffffffff.save'; scratch.write_bytes(b'CAS scratch original')
            frames = [observed(['MENU', 'Save', 'Save As...', 'Exit Game']),
                      observed(['SAVE GAME?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Exit Game', 'Cancel'])]
            calls = []
            def request(_state, action, **kwargs):
                calls.append((action, kwargs))
                if action == 'test_input' and len([row for row in calls if row[0] == 'test_input']) == 2:
                    slot.write_bytes(b'native rewritten save')
                return {'ok': True}
            def capture(_state, _image, _request):
                return {'ok': True, 'width': 1278, 'height': 1376, 'sha256': 'a' * 64}
            with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                    {'token': 'a' * 32, 'artifacts': []}, profile, original)):
                result = game_lifecycle.shutdown('state', root / 'proof.json', {'pid': 42}, request,
                    capture=capture, ocr=lambda _: frames.pop(0), processes=lambda: [], pause=lambda _: None)
            self.assertTrue(result['ok'])
            self.assertFalse(result['save_reload_verified'])
            self.assertEqual(scratch.read_bytes(), b'CAS scratch original')
            self.assertEqual([action for action, _ in calls], ['overlay_hide', 'test_input', 'test_input'])

    def test_only_explicit_native_refusal_before_button_down_can_be_reobserved_and_retried(self):
        self.assertTrue(game_lifecycle.refused_before_input(dict(input_version=2,input_submitted=False,input_state=-7)))
        self.assertTrue(game_lifecycle.refused_before_input(dict(input_version=2,input_submitted=False,native_code=-2)))
        for result in ({'ok':False},dict(input_version=2,input_submitted=False,input_state=-5),
                       dict(input_version=2,input_submitted=True,input_state=-7),dict(input_version=1,input_submitted=False,input_state=-7)):
            self.assertFalse(game_lifecycle.refused_before_input(result))

    def test_process_exit_without_save_rewrite_is_not_a_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            profile, original = root / 'profile', root / 'original'
            (profile / 'saves').mkdir(parents=True); original.mkdir()
            (profile / 'saves/Slot_00000002.save').write_bytes(b'unchanged test save')
            frames = [observed(['MENU', 'Save', 'Save As...', 'Exit Game']),
                      observed(['SAVE GAME?', 'Are you sure you want to exit the game?', 'Save and Exit', 'Exit Game', 'Cancel'])]
            with patch.object(game_lifecycle.reusable_profile, 'load', return_value=(None,
                    {'token': 'a' * 32, 'artifacts': []}, profile, original)):
                result = game_lifecycle.shutdown('state', root / 'proof.json', {'pid': 42}, lambda *_a, **_k: {'ok': True},
                    capture=lambda *_: {'ok': True, 'width': 1278, 'height': 1376},
                    ocr=lambda _: frames.pop(0), processes=lambda: [], pause=lambda _: None)
            self.assertTrue(result['game_exit_verified'])
            self.assertFalse(result['save_completed_file_verified'])
            self.assertFalse(result['ok'])
