"""Real receiver checkpoints at the shared native client-command boundary."""
import copy
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_frontdoor as entry, cas_bank_transaction as bank
import test_cas_bank_transaction as fixture


class NativeEntryTests(unittest.TestCase):
    def setUp(self):
        self.game = fixture.CasBankReceiverTests(); self.game.setUp()
        self.addCleanup(self.game.doCleanups)
        self.backend, self.sim = self.game.backend, self.game.sim
        # These receiver fixtures do not supply the real persistence service;
        # its independent native admission contract has dedicated tests.
        from apex_core import cas_save_boundary
        self.save_boundary = self.enterContext(patch.object(cas_save_boundary, 'require_installed', return_value=True))
        self.sim.get_sim_instance = lambda: object()
        self.other = copy.deepcopy(self.sim); self.other.id = 11
        self.other.occult_tracker.forms = copy.deepcopy(self.game.forms)
        self.sim.occult_tracker.forms = self.game.forms
        self.members = [self.sim, self.other]
        self.backend._get_sim_info_by_id = lambda sid: next((s for s in self.members if str(s.id) == str(sid)), None)
        self.backend._form_map = lambda tracker: tracker.forms
        self.zone = Obj(is_zone_running=True, is_in_build_buy=False)
        self.backend.services.current_zone = lambda: self.zone
        self.backend.services.get_active_sim = lambda: self.sim
        self.backend.services.active_household = lambda: Obj(id=20, sim_info_gen=lambda: iter(self.members))
        self.backend.services.client_manager = lambda: Obj(get_first_client=lambda: Obj(id=50))
        self.calls = []
        def native(command, connection):
            if command.startswith('sims.exit2cas'):
                receipt = self.backend._APEX_CAS_FRONTDOOR_RECEIPT
                self.assertEqual(receipt['stage'], 'native-submit-intent')
                for sim in self.members:
                    path, key = fixture.form_bank.context(self.backend, sim)
                    record = json.loads(path.read_text())['records'][key]
                    self.assertEqual(record['cas_transaction']['native_entry_intent'], receipt['id'])
            self.calls.append((command, connection)); return 'native-result'
        self.commands = Obj(client_cheat=native)
        self.enterContext(patch.object(entry.cas_ui, 'capture_original_owner',
                                      side_effect=lambda _b, sim: {'original_owner': {'complete': True, 'original_sim_id': str(sim.id)}}))
        self.prepare = self.enterContext(patch.object(entry.cas_entry_context, 'prepare', return_value={'ok': True}))
        self.assertTrue(entry.install(self.backend, self.commands))

    def test_cached_python_alias_reaches_new_native_hook_and_captures_every_member_first(self):
        def cached_client_cheat(command, connection):
            return self.commands.client_cheat(command, connection)
        result = cached_client_cheat('sims.exit2cas 10 20', 50)
        self.assertEqual(result, 'native-result')
        self.assertEqual([row['sim_id'] for row in self.backend._APEX_CAS_FRONTDOOR_RECEIPT['members']], ['10', '11'])
        self.prepare.assert_called_once_with(self.backend, self.sim, False)
        self.assertEqual(self.game.snapshot_calls, []); self.assertEqual(self.game.native_writes, [])
        self.assertTrue(all(bank.status(self.backend, sim)['blocked'] for sim in self.members))

    def test_full_household_and_career_routes_keep_exact_arguments(self):
        command = 'sims.exit2caswithhouseholdid 10 20 career'
        self.commands.client_cheat(command, 50)
        self.assertEqual(self.calls, [(command, 50)])
        self.prepare.assert_called_once_with(self.backend, self.sim, True)

    def test_manual_phone_capture_is_reused_only_while_all_native_owners_are_unchanged(self):
        held = bank.begin(self.backend, self.sim)
        self.commands.client_cheat('sims.exit2cas 10 20 10', 50)
        receipt = self.backend._APEX_CAS_FRONTDOOR_RECEIPT
        self.assertEqual(receipt['members'][0]['checkpoint']['expected_pending_sha256'], held['expected_pending_sha256'])
        self.assertTrue(receipt['members'][0]['checkpoint']['reused_fresh_capture'])

    def test_changed_live_capture_blocks_before_any_new_companion_checkpoint_or_native_call(self):
        bank.begin(self.backend, self.sim); self.game.edit(2)
        with self.assertRaisesRegex(ValueError, 'appearances changed'):
            self.commands.client_cheat('sims.exit2cas 10 20', 50)
        self.assertEqual(self.calls, []); self.prepare.assert_not_called()
        self.assertFalse(bank.status(self.backend, self.other)['blocked'])

    def test_prior_native_submission_is_never_repeated(self):
        self.commands.client_cheat('sims.exit2cas 10 20', 50)
        with self.assertRaisesRegex(ValueError, 'unused native entry'):
            self.commands.client_cheat('sims.exit2cas 10 20', 50)
        self.assertEqual(len(self.calls), 1)

    def test_native_exception_retains_intent_and_prevents_replay(self):
        commands = Obj(client_cheat=lambda *_a: (_ for _ in ()).throw(OSError('native handoff uncertain')))
        entry.install(self.backend, commands)
        with self.assertRaisesRegex(OSError, 'handoff uncertain'):
            commands.client_cheat('sims.exit2cas 10 20', 50)
        self.assertEqual(self.backend._APEX_CAS_FRONTDOOR_RECEIPT['stage'], 'native-submit-intent')
        with self.assertRaisesRegex(ValueError, 'unused native entry'):
            commands.client_cheat('sims.exit2cas 10 20', 50)

    def test_submitted_checkpoint_supports_explicit_return_commit_and_preserves_companion(self):
        self.commands.client_cheat('sims.exit2cas 10 20', 50)
        selected = self.backend._APEX_CAS_FRONTDOOR_RECEIPT['members'][0]
        self.game.epoch = selected['checkpoint']['expected_pending_sha256']
        self.game.edit(64); self.game.observe()
        self.game.prepare([(64, 'accept-returned')]); result = self.game.commit()
        self.assertTrue(result['all_native_owners_verified'])
        self.assertTrue(bank.assert_idle(self.backend, self.sim))
        self.assertTrue(bank.status(self.backend, self.other)['blocked'])

    def test_observed_transaction_cannot_be_reused_as_an_entry_capture(self):
        self.game.begin(); self.game.edit(64); self.game.observe()
        with self.assertRaisesRegex(ValueError, 'unused native entry'):
            self.commands.client_cheat('sims.exit2cas 10 20', 50)
        self.assertEqual(self.calls, [])

    def test_prepared_cli_scope_reuses_exact_captures_without_recapturing_or_reprojecting(self):
        for sim in self.members: bank.begin(self.backend, sim)
        with entry.prepared(self.backend, self.sim, True, {'ok': True}):
            self.commands.client_cheat('sims.exit2caswithhouseholdid 10 20', 50)
        self.prepare.assert_not_called()
        self.assertTrue(all(row['checkpoint']['reused_fresh_capture'] for row in self.backend._APEX_CAS_FRONTDOOR_RECEIPT['members']))
        self.assertIsNone(getattr(entry._LOCAL, 'prepared', None))

    def test_wrong_prepared_scope_wrong_thread_and_foreign_client_fail_before_checkpoint(self):
        for command, connection in [('sims.exit2cas 10 20', 51), ('sims.exit2cas 10 21', 50),
                                    ('sims.exit2cas 10 20 11', 50)]:
            with self.subTest(command=command, connection=connection), self.assertRaises(ValueError):
                self.commands.client_cheat(command, connection)
        with entry.prepared(self.backend, self.sim, True, {'ok': True}), self.assertRaises(ValueError):
            self.commands.client_cheat('sims.exit2cas 10 20', 50)
        self.backend._APEX_GAME_THREAD_IDENT = threading.current_thread().ident + 1
        with self.assertRaisesRegex(ValueError, 'game thread'):
            self.commands.client_cheat('sims.exit2cas 10 20', 50)
        self.assertEqual(self.calls, [])

    def test_non_cas_commands_delegate_without_touching_live_services_or_bank(self):
        self.backend.services.current_zone = lambda: self.fail('non-CAS command read Live state')
        self.assertEqual(self.commands.client_cheat('cas.fulleditmode', 50), 'native-result')
        self.prepare.assert_not_called(); self.assertFalse(bank.status(self.backend, self.sim)['blocked'])

    def test_unsupported_save_boundary_refuses_before_any_checkpoint_or_native_cas_submission(self):
        self.save_boundary.side_effect = ValueError('native save admission contract changed')
        with self.assertRaisesRegex(ValueError, 'save admission contract changed'):
            self.commands.client_cheat('sims.exit2caswithhouseholdid 10 20', 50)
        self.assertEqual(self.calls, [])
        self.prepare.assert_not_called()
        self.assertTrue(all(not bank.status(self.backend, member)['blocked'] for member in self.members))

    def test_unknown_modes_and_noncanonical_identities_never_reach_native(self):
        for command in ('sims.exit2cas 010 20', 'sims.exit2cas -1 20', 'sims.exit2cas 10 20 extra',
                        'sims.exit2caswithhouseholdid 10 20 foo', 'sims.exit2cas 10', 'sims.exit2cas 10 20 0'):
            with self.subTest(command=command), self.assertRaises(ValueError):
                self.commands.client_cheat(command, 50)
        self.assertEqual(self.calls, [])

    def test_install_is_idempotent_and_keeps_prior_wrapper(self):
        current = self.commands.client_cheat
        self.assertTrue(entry.install(self.backend, self.commands))
        self.assertIs(current, self.commands.client_cheat)

    def test_ordinary_route_receipt_satisfies_real_host_household_return_contract(self):
        from apex_core import test_driver
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        from cas_household_commit import entry_receipt
        self.backend._APEX_CAS_FRONTDOOR_READY = True
        def native_entry(target, _connection):
            self.commands.client_cheat('sims.exit2caswithhouseholdid ' + target + ' 20', _connection)
            return True
        modules = {'server_commands.cas_commands': Obj(modify_in_cas=native_entry,
            modify_in_cas_with_household_id=native_entry),
            'server_commands.argument_helpers': Obj(OptionalTargetParam=lambda value: value),
            'sims4.commands': Obj(client_cheat=self.commands.client_cheat)}
        with patch.object(test_driver, 'guard', return_value='native-full'), patch.dict(sys.modules, modules):
            result = test_driver.dispatch(self.backend, 'test_cas', '10', '{}')
        document = {'operation': 'observe-native-cas-entry', 'entry_submitted': True, 'entry_accepted': True,
            'steps': [{'action': 'test_cas', 'result': result}]}
        scope, rows = entry_receipt(document)
        self.assertEqual(scope['household_id'], '20'); self.assertEqual(scope['roster_sim_ids'], ['10', '11'])
        self.assertEqual(set(rows), {'10', '11'})


if __name__ == '__main__': unittest.main()
