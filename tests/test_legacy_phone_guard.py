"""Legacy entry guards use the real durable receiver fixture, never a game."""
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import legacy_phone_guard as guard, form_bank
import test_cas_bank_transaction as fixture


class LegacyGuardTests(unittest.TestCase):
    def setUp(self):
        self.game = fixture.CasBankReceiverTests()
        self.game.setUp()
        self.addCleanup(self.game.doCleanups)
        self.backend, self.sim = self.game.backend, self.game.sim
        self.target = Obj(sim_info=self.sim)
        self.resolve = Mock(return_value=self.target)
        self.backend.services.client_manager = lambda: Obj(get_first_client=lambda: Obj(active_sim=self.target))
        self.enterContext(patch.dict(sys.modules, {
            'td1_occult_hybrid_apex': self.backend,
            'server_commands.argument_helpers': Obj(get_optional_target=self.resolve)}))

    def test_pending_originals_block_command_direct_sim_and_queued_interaction_before_native_body(self):
        guard.command_idle('target', 50)
        guard.sim_info_idle(self.sim)
        self.game.begin()
        for call in (lambda: guard.command_idle('target', 50), lambda: guard.sim_info_idle(self.sim),
                     lambda: guard.interaction_idle(Obj(picker_target='TargetSim', get_participant=lambda _p: self.target))):
            with self.assertRaisesRegex(ValueError, 'Pending form transaction'):
                call()
        self.assertEqual(self.game.native_writes, [])
        self.assertEqual(self.game.snapshot_calls, [])

    def test_wrong_thread_fails_before_target_resolution_and_same_id_foreign_object_is_refused(self):
        self.backend._APEX_GAME_THREAD_IDENT = -1
        with self.assertRaisesRegex(ValueError, 'canonical Apex game thread'):
            guard.command_idle('target', 50)
        self.resolve.assert_not_called()
        self.backend._APEX_GAME_THREAD_IDENT = __import__('threading').current_thread().ident
        self.resolve.return_value = Obj(sim_info=Obj(id=self.sim.id))
        with self.assertRaisesRegex(ValueError, 'manager-owned'):
            guard.command_idle('target', 50)

    def test_settings_final_execution_blocks_pending_created_after_dialog_and_foreign_owner_pending(self):
        updates = []
        guard.settings_idle()
        def response():
            guard.settings_idle()
            updates.append('native config update')
        self.game.begin()
        with self.assertRaises(ValueError):
            response()
        self.assertEqual(updates, [])
        data = self.game.data()
        pending = data['records'][self.game.key]['pending']
        transaction = data['records'][self.game.key]['cas_transaction']
        data['records'][self.game.key]['pending'] = None
        data['records'][self.game.key].pop('cas_transaction')
        data['records']['30:99'].update(pending=pending, cas_transaction=transaction)
        form_bank.save(self.game.path, data)
        with self.assertRaisesRegex(ValueError, 'global settings'):
            response()
        self.assertEqual(updates, [])

    def test_guard_import_is_passive_and_retired_commands_do_not_resolve_targets_or_import_backend(self):
        output = Mock()
        with patch.dict(sys.modules, {'td1_occult_hybrid_apex': None,
                                     'sims4.commands': Obj(CheatOutput=lambda _connection: output)}):
            importlib.reload(guard)
            self.assertIs(guard.retired(50), False)
        self.resolve.assert_not_called()
        self.assertIn('disabled', output.call_args.args[0])
        self.assertEqual(self.game.native_writes, [])


if __name__ == '__main__':
    unittest.main()
