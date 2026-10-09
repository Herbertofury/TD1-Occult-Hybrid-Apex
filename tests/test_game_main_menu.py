from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from game_main_menu import target
from test_game_load import screen


class MainMenuTargetTests(unittest.TestCase):
    def test_live_menu_exit_target_is_unsaved_main_menu_only(self):
        menu = ['MENU', 'Save', 'Save As...', 'Exit to Main Menu', 'Exit Game']
        value = target(screen(menu), 'menu')
        self.assertEqual(value['y'], 218)
        for labels in (['Exit to Main Menu'], menu + ['SAVE GAME?'], menu + ['Exit to Main Menu']):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                target(screen(labels), 'menu')

    def test_confirmation_requires_complete_main_menu_question(self):
        labels = ['SAVE GAME?', 'Are you sure you want to exit to the main menu?',
                  'Save and Exit', 'Exit to Main Menu', 'Cancel']
        self.assertEqual(target(screen(labels), 'confirmation')['y'], 218)
        for index in range(len(labels)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                target(screen(labels[:index] + labels[index + 1:]), 'confirmation')
        labels[1] = 'Are you sure you want to exit the game?'
        with self.assertRaises(ValueError):
            target(screen(labels), 'confirmation')

    def test_actual_wrapped_save_before_main_menu_question_is_required_in_full(self):
        labels = ['SAVE GAME?', 'Would you like to save your game before exiting to the',
                  'main menu?', 'Save and Exit', 'Exit to Main Menu', 'Cancel']
        self.assertEqual(target(screen(labels), 'confirmation')['y'], 252)
        for remove in (1, 2):
            with self.assertRaises(ValueError):
                target(screen(labels[:remove] + labels[remove + 1:]), 'confirmation')

    def test_nonfinite_outside_and_boolean_rectangles_refused(self):
        labels = ['MENU', 'Save', 'Save As...', 'Exit to Main Menu', 'Exit Game']
        for field, value in (('x', float('nan')), ('height', True), ('width', 2000), ('y', -1)):
            observed = screen(labels); observed['lines'][3]['words'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                target(observed, 'menu')
