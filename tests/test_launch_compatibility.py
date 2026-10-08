from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import launch_compatibility as compatibility


class FakeLayers:
    def __init__(self, values):
        self.values, self.writes = values, []
        self.fail_once = False

    def read(self, name):
        return self.values.get(name)

    def write(self, name, value):
        self.values[name] = value
        self.writes.append((name, value))
        if self.fail_once:
            self.fail_once = False
            raise OSError('interrupted after registry write')


class CompatibilityTests(unittest.TestCase):
    def test_removes_only_admin_token_preserving_other_compatibility(self):
        self.assertEqual(compatibility.without_forced_admin('~ RUNASADMIN WIN7RTM HIGHDPIAWARE'), '~ WIN7RTM HIGHDPIAWARE')
        self.assertEqual(compatibility.without_forced_admin('~ runasadmin'), None)
        self.assertEqual(compatibility.without_forced_admin('RUNASADMINISTER'), 'RUNASADMINISTER')
        self.assertEqual(compatibility.without_forced_admin(' WIN7RTM '), ' WIN7RTM ')

    def test_crash_recovery_and_restore_are_exact_and_refuse_new_user_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'GameInstall'
            binary = root / 'Game' / 'Bin'
            binary.mkdir(parents=True)
            values = {}
            for name in compatibility.EXECUTABLES:
                path = binary / name
                path.write_bytes(b'exact executable fixture')
                values[str(path)] = '~ RUNASADMIN WIN7RTM'
            original = dict(values)
            layers = FakeLayers(values)
            layers.fail_once = True
            receipt = Path(temporary) / 'compatibility.json'
            with patch.object(compatibility.reusable_profile, 'load', return_value=(None, {}, Path(temporary) / 'profile', Path(temporary) / 'original')), \
                 patch.object(compatibility.test_profile, 'require_closed'):
                with self.assertRaisesRegex(OSError, 'interrupted'):
                    compatibility.configure('state', root, receipt, layers=layers, manifest=lambda _p: 'asInvoker')
                result = compatibility.configure('state', root, receipt, layers=layers, manifest=lambda _p: 'asInvoker')
                self.assertEqual(result['phase'], 'applied')
                self.assertFalse(result['launch_verified'])
                self.assertEqual(set(values.values()), {'~ WIN7RTM'})
                selected = next(iter(values))
                values[selected] = '~ WIN10RTM'
                before = len(layers.writes)
                with self.assertRaisesRegex(ValueError, 'changed externally'):
                    compatibility.configure('state', root, receipt, restore=True, layers=layers, manifest=lambda _p: 'asInvoker')
                self.assertEqual(len(layers.writes), before)
                values[selected] = '~ WIN7RTM'
                result = compatibility.configure('state', root, receipt, restore=True, layers=layers, manifest=lambda _p: 'asInvoker')
                self.assertEqual(result['phase'], 'restored')
                self.assertEqual(values, original)

    def test_never_overrides_manifest_privilege_requirement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            binary = root / 'Game' / 'Bin'
            binary.mkdir(parents=True)
            for name in compatibility.EXECUTABLES:
                (binary / name).write_bytes(b'fixture')
            layers = FakeLayers({str(binary / name): 'RUNASADMIN' for name in compatibility.EXECUTABLES})
            with self.assertRaisesRegex(ValueError, 'requests elevation'):
                compatibility.plan(root, layers, lambda _p: 'requireAdministrator')
            self.assertEqual(layers.writes, [])
