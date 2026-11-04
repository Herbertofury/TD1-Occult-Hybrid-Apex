"""Readiness checks use disposable filesystem fixtures and never launch a game."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import game_launch
import reusable_profile
import test_profile


class ReusableReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / 'The Sims 4 DO NOT TOUCH'
        self.original.mkdir()
        (self.original / 'owner-data').write_bytes(b'original fixture')
        (self.profile / 'Mods').mkdir(parents=True)
        (self.profile / 'saves').mkdir()
        (self.profile / 'Tray').mkdir()
        self.cfg = self.profile / 'Mods' / 'Resource.cfg'
        self.cfg.write_bytes(b'Priority 500\n')
        self.token = 'a' * 32
        (self.profile / test_profile.MARKER).write_text(json.dumps({'disposable': True, 'token': self.token}))
        self.state = self.root / 'session' / 'control-profile.json'
        self.state.parent.mkdir()
        self.journal = {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active',
                        'profile': str(self.profile), 'protected_original': str(self.original),
                        'token': self.token, 'artifacts': [], 'bundle': [], 'generation': 1}
        self.save_journal()

    def save_journal(self):
        self.state.write_text(json.dumps(self.journal), encoding='utf-8')

    def status(self, verify_original=False):
        return test_profile.status(self.state, verify_original)

    def test_missing_mod_directory_blocks_status_and_launch(self):
        self.cfg.unlink()
        (self.profile / 'Mods').rmdir()
        result = self.status()
        self.assertFalse(result['ready_to_launch'])
        self.assertEqual(result['resource_config']['state'], 'missing_mods_directory')
        with self.assertRaisesRegex(ValueError, 'exact isolated test profile'):
            game_launch.launch_plan(self.root / 'unused-installation', self.state)

    def test_missing_or_nonregular_resource_config_blocks_readiness(self):
        self.cfg.unlink()
        self.assertFalse(self.status()['ready_to_launch'])
        self.assertEqual(self.status()['resource_config']['state'], 'missing_resource_config')
        self.cfg.mkdir()
        self.assertFalse(self.status()['ready_to_launch'])

    def test_resource_config_read_error_propagates(self):
        original_sha256 = reusable_profile.sha256
        def fail_on_config(path):
            if Path(path) == self.cfg:
                raise OSError('synthetic read failure')
            return original_sha256(path)
        with patch.object(reusable_profile, 'sha256', side_effect=fail_on_config):
            with self.assertRaisesRegex(OSError, 'synthetic read failure'):
                self.status()

    def test_mod_directory_walk_error_propagates(self):
        def fail_walk(path, followlinks=False, onerror=None):
            onerror(OSError('synthetic directory read failure'))
            return iter(())
        with patch.object(reusable_profile.os, 'walk', side_effect=fail_walk):
            with self.assertRaisesRegex(OSError, 'synthetic directory read failure'):
                self.status()

    def test_legacy_unpinned_config_has_no_invented_grammar_claim(self):
        for raw in (b'Priority 500\n', b'Priority 500\r\nPackedFile *.package\r\n',
                    b'unknown legacy syntax\n', b''):
            self.cfg.write_bytes(raw)
            result = self.status()
            self.assertTrue(result['ready_to_launch'])
            self.assertEqual(result['resource_config']['state'], 'present_unpinned_unverified')
            self.assertEqual(result['resource_config']['sha256'], reusable_profile.sha256(self.cfg))

    def test_config_pin_enforces_exact_bytes_and_bad_pin_refuses(self):
        self.journal['resource_cfg_sha256'] = reusable_profile.sha256(self.cfg)
        self.save_journal()
        self.assertEqual(self.status()['resource_config']['state'], 'pinned_match')
        self.cfg.write_bytes(b'Priority 501\n')
        result = self.status()
        self.assertFalse(result['ready_to_launch'])
        self.assertEqual(result['resource_config']['state'], 'pinned_mismatch')
        self.journal['resource_cfg_sha256'] = None
        self.save_journal()
        result = self.status()
        self.assertFalse(result['ready_to_launch'])
        self.assertEqual(result['resource_config']['state'], 'invalid_resource_config_pin')

    def test_missing_original_baseline_is_explicitly_unverified(self):
        self.assertTrue(self.status()['ready_to_launch'])
        result = self.status(verify_original=True)
        self.assertFalse(result['ready_to_launch'])
        self.assertIsNone(result['original_inventory_verified_now'])
        self.assertEqual(result['original_verification_error'], 'original_inventory_baseline_unavailable')

    def test_present_original_baseline_can_still_be_verified(self):
        previous = self.root / 'previous.json'
        previous.write_text(json.dumps({'original_inventory': test_profile.inventory(self.original)}))
        self.journal['previous_state'] = str(previous)
        self.save_journal()
        result = self.status(verify_original=True)
        self.assertTrue(result['ready_to_launch'])
        self.assertTrue(result['original_inventory_verified_now'])
        (self.original / 'owner-data').write_bytes(b'changed fixture')
        result = self.status(verify_original=True)
        self.assertFalse(result['ready_to_launch'])
        self.assertFalse(result['original_inventory_verified_now'])

    def test_valid_legacy_config_reaches_real_launch_plan_without_launch(self):
        install = self.root / 'fixture-install'
        (install / 'Game' / 'Bin').mkdir(parents=True)
        (install / '__Installer').mkdir()
        (install / 'Game' / 'Bin' / 'TS4_Launcher_x64.exe').write_bytes(b'fixture launcher')
        (install / 'Game' / 'Bin' / 'TS4_x64.exe').write_bytes(b'fixture game')
        (install / '__Installer' / 'installerdata.xml').write_text(
            '<installer><contentIDs><contentID>123</contentID></contentIDs></installer>')
        with patch.object(game_launch, 'account_launch_identity',
                          return_value={'offer_id': 'fixture', 'content_id': '123'}):
            result = game_launch.launch(install, self.state, execute=False)
        self.assertFalse(result['launched'])
        self.assertEqual(result['isolation']['resource_config']['state'], 'present_unpinned_unverified')


if __name__ == '__main__':
    unittest.main()
