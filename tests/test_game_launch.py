from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_launch


class LaunchPlanTests(unittest.TestCase):
    def fixture(self, root, ids='<contentID>1011164</contentID>'):
        (root / 'Game' / 'Bin').mkdir(parents=True)
        (root / '__Installer').mkdir()
        for name in ('TS4_x64.exe', 'TS4_Launcher_x64.exe'):
            (root / 'Game' / 'Bin' / name).write_bytes(b'fixture')
        (root / '__Installer' / 'installerdata.xml').write_text(
            '<DiPManifest><buildMetaData><gameVersion version="fixture"/></buildMetaData><contentIDs>' + ids + '</contentIDs></DiPManifest>')

    def test_plan_uses_installed_ids_and_does_not_launch_or_claim_headless(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': True}):
                plan = game_launch.launch(root, root / 'state.json')
            self.assertIn('offerIds=1011164', plan['url'])
            self.assertIn('autoDownload=0', plan['url'])
            self.assertFalse(plan['launched'])
            self.assertFalse(plan['headless_game_runtime'])

    def test_unsafe_ids_and_nonisolated_profile_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, '<contentID>--login=bad</contentID>')
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': True}):
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    game_launch.launch_plan(root, root / 'state.json')
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': False}):
                with self.assertRaisesRegex(ValueError, 'isolated'):
                    game_launch.launch_plan(root, root / 'state.json')

    def test_headless_request_never_falls_back_to_graphical_launch(self):
        with patch.object(game_launch, 'launch_plan') as plan:
            with self.assertRaisesRegex(ValueError, 'not implemented'):
                game_launch.launch('game', 'state', execute=True, headless=True)
            plan.assert_not_called()

    def test_ea_identifier_delimiters_are_literal_commas(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, '<contentID>1011164</contentID><contentID>1015875</contentID>')
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': True}):
                plan = game_launch.launch_plan(root, root / 'state.json')
            self.assertIn('offerIds=1011164,1015875&', plan['url'])
            self.assertNotIn('%2C', plan['url'])

    def test_process_start_requires_a_new_pid_and_exact_installed_path(self):
        clock = [0.0]
        def pause(seconds):
            clock[0] += seconds
        executable = Path('Game/Bin/TS4_x64.exe').resolve()
        def wrong():
            return [{'Id': 10, 'Path': str(executable)}, {'Id': 11, 'Path': str(executable.parent / 'other.exe')}]
        result = game_launch.observe_start(executable, {10}, 2, wrong, lambda: clock[0], pause)
        self.assertFalse(result['process_started'])
        result = game_launch.observe_start(executable, {10}, 2, lambda: [{'Id': 12, 'Path': str(executable)}], lambda: clock[0], pause)
        self.assertTrue(result['process_started'])
        self.assertEqual(result['pid'], 12)


if __name__ == '__main__':
    unittest.main()
