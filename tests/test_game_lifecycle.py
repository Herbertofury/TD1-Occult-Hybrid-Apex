from pathlib import Path
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
