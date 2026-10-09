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
        self.identity = {'offer_id': 'OFB-EAST:fixture', 'content_id': '1011164'}

    def identity_patch(self):
        return patch.object(game_launch, 'account_launch_identity', return_value=self.identity)

    def test_plan_uses_installed_ids_and_does_not_launch_or_claim_headless(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self.fixture(root)
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': True}), self.identity_patch():
                plan = game_launch.launch(root, root / 'state.json')
            self.assertIn('offerIds=1011164&', plan['url'])
            self.assertNotIn('OFB-EAST:', plan['url'])
            self.assertIn('autoDownload=0', plan['url'])
            self.assertFalse(plan['launched'])
            self.assertFalse(plan['headless_game_runtime'])

    def test_unsafe_ids_and_nonisolated_profile_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self.fixture(root, '<contentID>--login=bad</contentID>')
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': True}):
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    game_launch.launch_plan(root, root / 'state.json', offer_id='OFB-EAST:109552414')
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': False}):
                with self.assertRaisesRegex(ValueError, 'isolated'):
                    game_launch.launch_plan(root, root / 'state.json')

    def test_headless_request_never_falls_back_to_graphical_launch(self):
        with patch.object(game_launch, 'launch_plan') as plan:
            with self.assertRaisesRegex(ValueError, 'not implemented'):
                game_launch.launch('game', 'state', execute=True, headless=True)
            plan.assert_not_called()

    def test_only_account_verified_content_id_is_used_and_other_offers_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, '<contentID>1011164</contentID><contentID>1015875</contentID>')
            with patch.object(game_launch.test_profile, 'status', return_value={'ready_to_launch': True}), self.identity_patch():
                with self.assertRaisesRegex(ValueError, 'differs'):
                    game_launch.launch_plan(root, root / 'state.json', 'OFB-EAST:another-account-edition')
                plan = game_launch.launch_plan(root, root / 'state.json')
                self.identity['content_id'] = '1015806'
                with self.assertRaisesRegex(ValueError, 'not in'):
                    game_launch.launch_plan(root, root / 'state.json')
            self.assertIn('offerIds=1011164&', plan['url'])
            self.assertNotIn(',', plan['url'])
            self.assertEqual(plan['installer_content_ids'], ['1011164', '1015875'])

    def test_account_identity_requires_successful_client_play_for_exact_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            log = root / 'EADesktop.log'
            self.fixture(root)
            executable = root / 'Game' / 'Bin' / 'TS4_Launcher_x64.exe'
            success = 'Successful launch. IDs: offerKey.offerId=[OFB-EAST:fixture], slug=[the-sims-4]\n'
            processing = 'Processing launch request: offerId[OFB-EAST:fixture] contentId[1011164] exe[{}] requestSource[Client]\n'
            log.write_text(success + processing.format(executable))
            self.assertEqual(game_launch.account_launch_identity(root, log)['content_id'], '1011164')
            for raw in (processing.format(executable), success + processing.format(root / 'other.exe'),
                        (success + processing.format(executable)).replace('requestSource[Client]', 'requestSource[RTP]')):
                log.write_text(raw)
                with self.assertRaisesRegex(ValueError, 'No verified'):
                    game_launch.account_launch_identity(root, log)

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

    def test_delayed_start_at_52_seconds_is_observed_without_new_handoff(self):
        clock = [0.0]; probes = []
        executable = Path('Game/Bin/TS4_x64.exe').resolve()
        def inventory():
            probes.append(clock[0])
            return [] if clock[0] < 52 else [{'Id': 29596, 'Path': str(executable)}]
        result = game_launch.observe_start(executable, set(), 60, inventory, lambda: clock[0],
            lambda seconds: clock.__setitem__(0, clock[0] + seconds))
        self.assertTrue(result['process_started']); self.assertEqual(result['pid'], 29596)
        self.assertEqual(result['elapsed_seconds'], 52); self.assertFalse(result['retry_attempted'])

    def test_deadline_final_snapshot_retains_unresolved_process_inventory_and_never_sleeps_past_bound(self):
        clock = [0.0]; executable = Path('Game/Bin/TS4_x64.exe').resolve()
        result = game_launch.observe_start(executable, {10}, 2,
            lambda: [{'Id': 10, 'Path': str(executable)}], lambda: clock[0],
            lambda seconds: clock.__setitem__(0, clock[0] + seconds))
        self.assertFalse(result['process_started']); self.assertEqual(result['outcome'], 'start-unresolved')
        self.assertEqual(result['final_process_inventory'], [{'Id': 10, 'Path': str(executable)}])
        self.assertEqual(clock[0], 2); self.assertEqual(result['process_observation_count'], 3)
        self.assertFalse(result['retry_attempted'])
        for seconds in (True, False, 0, -1, 61, float('nan'), float('inf')):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                game_launch.observe_start(executable, set(), seconds, lambda: self.fail('Invalid limit cannot inspect processes.'))


if __name__ == '__main__':
    unittest.main()
