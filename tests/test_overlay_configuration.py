import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import apex_cli
import overlay_configuration as config
import reusable_profile as profiles
import test_profile
from source_manifest import sha256, write_json


INI = b'[Overlay]\r\n; Keep these comments and spaces.\r\nAutoStart = 1  \r\n; F11 is the owner preference.\r\nToggleKey=F11\r\n'


class OverlayConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / 'The Sims 4'
        self.original = self.root / profiles.PROTECTED_NAME
        (self.original / 'saves').mkdir(parents=True)
        (self.original / 'Mods').mkdir()
        (self.original / 'saves/precious.save').write_bytes(b'owner original save')
        (self.original / 'Mods/precious.package').write_bytes(b'owner original mods')
        (self.profile / 'saves').mkdir(parents=True)
        (self.profile / 'Tray').mkdir()
        (self.profile / 'saves/test.save').write_bytes(b'disposable save retained')
        (self.profile / 'Tray/test.trayitem').write_bytes(b'disposable sim retained')
        write_json(self.profile / test_profile.MARKER, {'token': 'a' * 32})
        self.state = self.root / 'work/state.json'
        self.state.parent.mkdir()
        self.rows = []
        fixtures = {'Apex/ApexOccultHybrid.package': b'DBPF hybrid',
                    'Apex/ApexOccultHybrid.ts4script': b'PK script',
                    'Apex/ApexCASUnlocks.package': b'DBPF unlocks',
                    'Apex/ApexCASBridge.package': b'DBPF CAS bridge',
                    'Apex/ApexPlantSimPermanent.package': b'DBPF optional',
                    'Apex/Native/ApexOverlay.dll': b'MZ DLL',
                    config.RELATIVE: INI, 'Apex/Native/overlay-manifest.json': b'{"native":"identity"}',
                    'MCCC/mc_cmd_center.package': b'DBPF MCCC', 'MCCC/mc_cas.ts4script': b'PK MCCC CAS'}
        for relative, raw in fixtures.items():
            target = self.profile / 'Mods' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            source = self.state.parent / ('source-' + hashlib.sha256(raw).hexdigest())
            source.write_bytes(raw)
            row = {'name': target.name, 'relative': relative, 'source': str(source),
                   'bytes': len(raw), 'sha256': sha256(target), 'future_metadata': {'keep': relative}}
            if relative.startswith('MCCC/'):
                row['test_addon'] = 'mccc-2026.5.0'
            self.rows.append(row)
        (self.profile / 'Mods/MCCC/mc_settings.cfg').write_bytes(b'{"owner_setting":true}')
        self.bundle = {'sha256': 'b' * 64, 'source': 'baseline-candidate.zip', 'target_game': 'fixture'}
        write_json(self.state, {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'active', 'generation': 3,
                    'token': 'a' * 32, 'profile': str(self.profile), 'protected_original': str(self.original),
                    'artifacts': self.rows, 'bundle': self.bundle})
        self.initial_profile = self.inventory(self.profile)
        self.initial_original = self.inventory(self.original)

    def inventory(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def assert_preserved(self, changed=True):
        current = self.inventory(self.profile)
        before = copy.deepcopy(self.initial_profile)
        if changed:
            current.pop('Mods/' + config.RELATIVE)
            before.pop('Mods/' + config.RELATIVE)
        self.assertEqual(current, before)
        self.assertEqual(self.inventory(self.original), self.initial_original)

    def test_off_and_on_preserve_every_other_artifact_and_restore_exact_ini_bytes(self):
        result = config.configure(self.state, False, guard=lambda: None)
        self.assertTrue(result['ready_to_launch'])
        self.assertFalse(result['overlay_autostart_enabled'])
        self.assertTrue(result['changed'])
        target = self.profile / 'Mods' / config.RELATIVE
        self.assertEqual(target.read_bytes(), INI.replace(b'AutoStart = 1', b'AutoStart = 0'))
        journal = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(len(journal['artifacts']), len(self.rows))
        self.assertEqual(journal['bundle'], self.bundle)
        changed_rows = [row for row, prior in zip(journal['artifacts'], self.rows) if row != prior]
        self.assertEqual(len(changed_rows), 1)
        self.assertEqual(changed_rows[0]['relative'], config.RELATIVE)
        self.assertEqual(changed_rows[0]['future_metadata'], {'keep': config.RELATIVE})
        self.assertTrue(profiles.writable(changed_rows[0]['source']).is_file())
        override = result['configuration_override']
        self.assertEqual(sha256(override['receipt']), override['receipt_sha256'])
        receipt = json.loads(Path(override['receipt']).read_text(encoding='utf-8'))
        self.assertEqual(receipt['baseline_bundle'], self.bundle)
        self.assertEqual(receipt['before_sha256'], hashlib.sha256(INI).hexdigest())
        self.assertEqual(receipt['expected_installed_sha256'], sha256(target))
        self.assertFalse(result['complete_bundle_verified'])
        self.assert_preserved()
        second = config.configure(self.state, True, guard=lambda: None)
        self.assertTrue(second['ready_to_launch'])
        self.assertEqual(target.read_bytes(), INI)
        self.assertEqual(json.loads(self.state.read_text())['bundle'], self.bundle)
        self.assert_preserved(changed=False)
        receipt2 = json.loads(Path(second['configuration_override']['receipt']).read_text())
        self.assertEqual(receipt2['previous_override'], override)

    def test_running_game_refuses_before_profile_journal_or_recovery_changes(self):
        state_before = self.state.read_bytes()
        def running():
            raise RuntimeError('game running')
        with self.assertRaisesRegex(RuntimeError, 'game running'):
            config.configure(self.state, False, guard=running)
        self.assertEqual(self.state.read_bytes(), state_before)
        self.assertFalse((self.state.parent / 'artifact-recovery').exists())
        self.assertFalse(self.state.with_name(self.state.name + '.operation-lock').exists())
        self.assert_preserved(changed=False)

    def test_tampered_ini_or_other_artifact_refuses_without_overriding_pinned_hash(self):
        for relative in (config.RELATIVE, 'MCCC/mc_cas.ts4script'):
            target = self.profile / 'Mods' / relative
            original = target.read_bytes()
            target.write_bytes(original + b'tamper')
            before = self.inventory(self.profile)
            state_before = self.state.read_bytes()
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'pinned'):
                config.configure(self.state, False, guard=lambda: None)
            self.assertEqual(self.inventory(self.profile), before)
            self.assertEqual(self.state.read_bytes(), state_before)
            target.write_bytes(original)
        self.assert_preserved(changed=False)

    def test_unknown_mod_file_prevents_configuration_change(self):
        intruder = self.profile / 'Mods/unknown.package'
        intruder.write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError, 'pinned'):
            config.configure(self.state, False, guard=lambda: None)
        self.assertEqual((self.profile / 'Mods' / config.RELATIVE).read_bytes(), INI)
        self.assertEqual(intruder.read_bytes(), b'unknown')

    def test_no_op_preserves_generation_journal_and_does_not_create_override_receipt(self):
        before = self.state.read_bytes()
        result = config.configure(self.state, True, guard=lambda: None)
        self.assertFalse(result['changed'])
        self.assertEqual(self.state.read_bytes(), before)
        self.assertFalse((self.state.parent / 'artifact-recovery').exists())
        self.assert_preserved(changed=False)

    def test_ini_validation_rejects_missing_duplicate_unknown_and_inherited_settings(self):
        invalid = [b'[Overlay]\nToggleKey=F11\n',
                   b'[Overlay]\nAutoStart=1\nAutoStart=0\nToggleKey=F11\n',
                   b'[Overlay]\nAutoStart=1\nToggleKey=F11\nUnknown=1\n',
                   b'[DEFAULT]\nAutoStart=1\n[Overlay]\nToggleKey=F11\n',
                   b'[overlay]\nAutoStart=1\nToggleKey=F11\n',
                   b'[Overlay]\nautostart=1\nToggleKey=F11\n',
                   b'[Overlay]\nAutoStart=true\nToggleKey=F11\n',
                   b'[Overlay]\nAutoStart=1 ; inline loader does not support this\nToggleKey=F11\n',
                   b'[Overlay]\nAutoStart=1\nToggleKey=F25\n',
                   b'[Overlay]\nAutoStart:1\nToggleKey=F11\n', b'\xef\xbb\xbf' + INI,
                   b'x' * (config.MAX_BYTES + 1)]
        for raw in invalid:
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                config.edited_ini(raw, False)
        with self.assertRaises(ValueError):
            config.edited_ini(INI, 0)

    def test_interrupted_install_retains_override_receipt_for_existing_recovery(self):
        replacement = profiles.os.replace
        def interrupt(source, target):
            if Path(target).name == 'ApexOverlay.ini':
                raise OSError('interrupted INI replacement')
            return replacement(source, target)
        with patch.object(profiles.os, 'replace', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                config.configure(self.state, False, guard=lambda: None)
        pending = json.loads(self.state.read_text())
        self.assertEqual(len(pending['pending_artifacts']), len(self.rows))
        receipt = next(row['configuration_override'] for row in pending['pending_artifacts'] if row['relative'] == config.RELATIVE)
        self.assertEqual(sha256(receipt['receipt']), receipt['receipt_sha256'])
        self.assertTrue(profiles.recover(self.state, guard=lambda: None)['ready_to_launch'])
        active = json.loads(self.state.read_text())
        self.assertEqual(next(row['configuration_override'] for row in active['artifacts'] if row['relative'] == config.RELATIVE), receipt)
        self.assertEqual(active['bundle'], self.bundle)
        self.assert_preserved()

    def test_game_opening_during_staging_is_refused_before_ini_replacement(self):
        calls = []
        def closed_then_running():
            calls.append(True)
            if len(calls) == 3:
                raise RuntimeError('game opened during staging')
        before = self.state.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'game opened'):
            config.configure(self.state, False, guard=closed_then_running)
        self.assertEqual(self.state.read_bytes(), before)
        self.assert_preserved(changed=False)

    def test_protected_original_cannot_be_used_as_state_or_active_profile(self):
        with self.assertRaisesRegex(ValueError, 'read-only'):
            config.configure(self.original / 'state.json', False, guard=lambda: None)
        journal = json.loads(self.state.read_text())
        journal['profile'] = str(self.original)
        write_json(self.state, journal)
        with self.assertRaisesRegex(ValueError, 'read-only'):
            config.configure(self.state, False, guard=lambda: None)
        self.assert_preserved(changed=False)

    def test_profile_cli_routes_on_off_without_game_commands(self):
        for operation, expected in (('off', False), ('on', True)):
            args = apex_cli.parser().parse_args(['profile', 'overlay-autostart', operation, '--state', str(self.state)])
            with patch.object(config, 'configure', return_value={'ok': True}) as configure, \
                    patch.object(apex_cli, 'owned_request') as request:
                self.assertTrue(apex_cli.execute(args)['ok'])
                self.assertEqual(configure.call_args.args, (self.state, expected))
                request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
