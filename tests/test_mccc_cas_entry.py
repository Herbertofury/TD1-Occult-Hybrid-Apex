"""Real frontdoor receiver with synthetic pinned third-party callback fixtures.

No installed MCCC code is copied/executed by these tests. Host-version fixture
instruction hashes replace only the inspected production instruction/flag pins;
the callback/global/signature/constant contracts remain checked independently.
"""
import copy
import hashlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as Obj
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_frontdoor as entry, cas_bank_transaction as bank, test_driver
import test_cas_frontdoor as fixture


class McccCallbackEntryTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.NativeEntryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.backend, self.sim = self.f.backend, self.f.sim
        for ident in (12, 13, 14):
            other = copy.deepcopy(self.f.other)
            other.id = ident
            self.f.members.append(other)
        self.backend._APEX_CAS_FRONTDOOR_READY = True
        self.profile = Path(self.f.game.temp.name) / 'The Sims 4'
        path = self.profile / 'Mods' / 'MCCC' / 'mc_cmd_center.ts4script'
        path.parent.mkdir(parents=True)
        member = b'B\r\r\n' + b'\0' * 12 + b'synthetic fixture member'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('mc_cmd_center_dlg.pyc', member)
        self.archive = path
        self.enterContext(patch.object(entry, '_MCCC_ARCHIVE_SHA256', hashlib.sha256(path.read_bytes()).hexdigest()))
        self.enterContext(patch.object(entry, '_MCCC_MEMBER_SHA256', hashlib.sha256(member).hexdigest()))
        self.commands = ModuleType('sims4.commands')
        self.commands.__dict__.update(_commands=self.f.commands, __enable_native_commands=True,
                                     logger=Obj(assert_log=lambda *_a, **_k: None))
        exec('def client_cheat(s, context):\n'
             '    logger.assert_log(context, "Invoking client command with invalid context. command: {}, context: {}", s, context, owner="tingyul")\n'
             '    if __enable_native_commands:\n'
             '        _commands.client_cheat(s, context)\n', self.commands.__dict__)
        self.module = ModuleType('mc_cmd_center_dlg')
        self.module.__dict__[entry._MCCC_ALIAS] = self.commands.client_cheat
        exec('class SimMenuNavigation:\n'
             '    def __init__(self, *args, **kwargs):\n'
             '        raise AssertionError("No dialog may be constructed")\n'
             '    def _modify_household_in_cas(self, source_dialog):\n'
             '        ' + entry._MCCC_ALIAS + '("sims.exit2caswithhouseholdid {} {}".format(self._sim_info.id, self._sim_info.household_id), self._client.id)\n', self.module.__dict__)
        self.version = ModuleType('mc_cmd_version')
        self.version.VERSION = '2026.5.0'
        self.modules = {'mc_cmd_center_dlg': self.module, 'mc_cmd_version': self.version,
                        'sims4.commands': self.commands, '_commands': self.f.commands}
        self.enterContext(patch.dict(sys.modules, self.modules))
        callback = self.module.SimMenuNavigation._modify_household_in_cas
        for name, function in (('_MCCC_CALLBACK', callback), ('_MCCC_CLIENT', self.commands.client_cheat)):
            contract = dict(getattr(entry, name), sha256=hashlib.sha256(function.__code__.co_code).hexdigest(),
                            flags=function.__code__.co_flags)
            self.enterContext(patch.object(entry, name, contract))

    def run_entry(self, client=None):
        return entry.mccc_full_entry(self.backend, self.sim, client or Obj(id=50), self.profile)

    def assert_no_entry(self):
        self.assertEqual(self.f.calls, [])
        self.assertTrue(all(not bank.status(self.backend, sim)['blocked'] for sim in self.f.members))

    def test_real_cached_alias_reaches_normal_frontdoor_and_fresh_captures_all_five(self):
        result = self.run_entry()
        self.assertTrue(result['ok'])
        self.assertEqual(self.f.calls, [('cas.fulleditmode', 50), ('sims.exit2caswithhouseholdid 10 20', 50)])
        receipt = result['native_frontdoor']
        self.assertEqual(receipt['stage'], 'native-command-returned')
        self.assertEqual([row['sim_id'] for row in receipt['members']], ['10', '11', '12', '13', '14'])
        self.assertTrue(all(not row['checkpoint'].get('reused_fresh_capture') for row in receipt['members']))
        self.assertTrue(all(bank.status(self.backend, sim)['blocked'] for sim in self.f.members))
        self.assertEqual(self.f.game.native_writes, [])
        self.assertEqual(self.f.game.snapshot_calls, [])
        self.assertFalse(result['mccc_callback']['dialog_constructor_invoked'])
        self.assertFalse(result['mccc_callback']['visible_menu_exercised'])
        self.assertFalse(result['mccc_callback']['all_mccc_routes_verified'])
        self.assertFalse(result['cas_visible_verified'])
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from cas_household_commit import entry_receipt
        scope, rows = entry_receipt({'operation': 'observe-native-cas-entry', 'entry_accepted': True,
            'entry_submitted': True, 'steps': [{'action': 'test_cas', 'result': result}]})
        self.assertEqual(len(rows), 5)
        self.assertEqual(scope['household_id'], '20')

    def test_driver_mode_invokes_callback_without_importing_native_cas_command_route(self):
        self.backend.__file__ = 'synthetic backend fixture'
        identity = {'profile': str(self.profile), 'test_token': 'a' * 32}
        with patch.object(test_driver, 'guard', return_value='mccc-full'), \
                patch.object(test_driver, 'runtime_identity', return_value=identity):
            result = test_driver.dispatch(self.backend, 'test_cas', '10', '{}')
        self.assertTrue(result['mccc_callback']['actual_callback_invoked'])
        self.assertEqual(len(result['household_form_checkpoints']['members']), 5)

    def test_driver_requires_marked_disposable_identity_before_callback(self):
        self.backend.__file__ = 'synthetic backend fixture'
        with patch.object(test_driver, 'guard', return_value='mccc-full'), \
                patch.object(test_driver, 'runtime_identity', return_value={'profile': str(self.profile)}), \
                self.assertRaisesRegex(ValueError, 'marked disposable'):
            test_driver.dispatch(self.backend, 'test_cas', '10', '{}')
        self.assert_no_entry()

    def test_changed_method_constants_refuse_even_when_instruction_hash_is_identical(self):
        callback = self.module.SimMenuNavigation._modify_household_in_cas
        before = callback.__code__.co_code
        callback.__code__ = callback.__code__.replace(co_consts=(None, 'sims.exit2cas {} {}'))
        self.assertEqual(before, callback.__code__.co_code)
        with self.assertRaisesRegex(ValueError, 'bytecode, constants or signature'):
            self.run_entry()
        self.assert_no_entry()

    def test_changed_instruction_signature_defaults_and_loaded_version_refuse(self):
        callback = self.module.SimMenuNavigation._modify_household_in_cas
        callback.__defaults__ = (None,)
        with self.assertRaisesRegex(ValueError, 'defaults'):
            self.run_entry()
        callback.__defaults__ = None
        self.version.VERSION = 'future-version'
        with self.assertRaisesRegex(ValueError, 'already loaded'):
            self.run_entry()
        self.assert_no_entry()

    def test_changed_archive_or_unsupported_native_boundary_refuses_without_native_input(self):
        original = self.archive.read_bytes()
        self.archive.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'archive differs'):
            self.run_entry()
        self.archive.write_bytes(original)
        self.f.commands.client_cheat = lambda *_a: None
        with self.assertRaisesRegex(ValueError, 'not protected'):
            self.run_entry()
        self.assert_no_entry()

    def test_changed_or_disabled_cached_client_alias_refuses_without_input(self):
        self.commands.__dict__['__enable_native_commands'] = False
        with self.assertRaisesRegex(ValueError, 'cached game-command alias'):
            self.run_entry()
        self.commands.__dict__['__enable_native_commands'] = True
        self.commands.client_cheat = lambda *_a: None
        with self.assertRaisesRegex(ValueError, 'cached game-command alias'):
            self.run_entry()
        self.assert_no_entry()

    def test_foreign_client_and_prior_unconsumed_checkpoint_fail_before_callback(self):
        with self.assertRaisesRegex(ValueError, 'exact running Live household/client'):
            self.run_entry(Obj(id=51))
        self.assert_no_entry()
        bank.begin(self.backend, self.f.other)
        with self.assertRaises(ValueError):
            self.run_entry()
        self.assertEqual(self.f.calls, [])

    def test_no_fresh_receipt_cannot_be_faked_and_unresolved_attempt_is_not_replayed(self):
        calls = []
        def noop(command, connection):
            calls.append((command, connection))
        noop._apex_cas_frontdoor = self.backend
        self.f.commands.client_cheat = noop
        self.backend._APEX_CAS_FRONTDOOR_RECEIPT = {'id': 'f' * 32, 'stage': 'native-command-returned'}
        with self.assertRaisesRegex(ValueError, 'fresh acknowledged normal frontdoor'):
            self.run_entry()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.backend._APEX_MCCC_CAS_TEST_ATTEMPT['stage'], 'callback-invoked')
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.run_entry()
        self.assertEqual(len(calls), 2)

    def test_native_exception_retains_original_frontdoor_intent_and_does_not_replay(self):
        calls = []
        def uncertain(command, connection):
            calls.append((command, connection))
            if command.startswith('sims.exit2cas'):
                raise OSError('native handoff uncertain')
        native = Obj(client_cheat=uncertain)
        entry.install(self.backend, native)
        self.commands.__dict__['_commands'] = native
        with patch.dict(sys.modules, {'_commands': native}):
            with self.assertRaisesRegex(OSError, 'handoff uncertain'):
                self.run_entry()
            self.assertEqual(self.backend._APEX_CAS_FRONTDOOR_RECEIPT['stage'], 'native-submit-intent')
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                self.run_entry()
        self.assertEqual(len(calls), 2)

    def test_missing_durable_frontdoor_packet_is_not_a_successful_receipt(self):
        publish = entry.publish
        def corrupt(path, packet):
            publish(path, packet)
            if packet.get('stage') == 'native-command-returned':
                path.write_text('{}')
        with patch.object(entry, 'publish', side_effect=corrupt), \
                self.assertRaisesRegex(ValueError, 'differs from its durable evidence'):
            self.run_entry()
        self.assertEqual(len(self.f.calls), 2)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.run_entry()
        self.assertEqual(len(self.f.calls), 2)

    def test_real_successful_callback_cannot_reenter_before_household_reconciliation(self):
        self.run_entry()
        before = list(self.f.calls)
        with self.assertRaises(ValueError):
            self.run_entry()
        self.assertEqual(self.f.calls, before)


if __name__ == '__main__':
    unittest.main()
