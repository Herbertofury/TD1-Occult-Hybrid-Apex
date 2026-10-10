"""Exercise the real canonical router and callback gates without importing Sims."""
import ast
import json
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
import apex_core


def extracted_owner():
    tree = ast.parse((ROOT / 'Source' / 'td1_occult_hybrid_apex.py').read_bytes())
    helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and
               node.name.startswith(('_apex_assert_', '_apex_preflight_', '_apex_legacy_',
                                     '_apex_guard_legacy_', '_apex_install_legacy_',
                                     '_apex_cas_transaction_'))]
    router = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run_action'][-1]
    module = ModuleType('apex_cas_route_fixture')
    module.__dict__.update(json=json, sys=sys, threading=threading,
                           _APEX_GAME_THREAD_IDENT=threading.current_thread().ident)
    compiled = ast.Module(body=helpers + [router], type_ignores=[])
    exec(compile(ast.fix_missing_locations(compiled), 'actual-apex-owner-router', 'exec'), module.__dict__)
    return module


class CasTransactionRouteTests(unittest.TestCase):
    def setUp(self):
        self.module = extracted_owner()
        self.enterContext(patch.dict(sys.modules, {self.module.__name__: self.module}))
        self.first = Obj(id=11)
        self.second = Obj(id=22)
        self.sims = {'11': self.first, '22': self.second}
        self.blocked = set()
        self.checked = []
        def resolve(value=None):
            return self.first if value in (None, '') else self.sims.get(str(value))
        def idle(backend, sim):
            self.assertIs(backend, self.module)
            self.assertIs(resolve(sim.id), sim)
            self.checked.append(sim.id)
            if sim.id in self.blocked:
                raise ValueError('Retained CAS metadata acknowledgment is unresolved.')
            return True
        self.receiver = Obj(assert_idle=idle,
            begin=Mock(return_value={'ok': True, 'raw_durable': True}),
            status=Mock(return_value={'ok': True, 'blocked': True}),
            observe=Mock(return_value={'ok': True, 'raw_return_durable': True}),
            prepare=Mock(return_value={'ok': True, 'explicit_intent': True}),
            commit=Mock(return_value={'ok': True, 'save_reload_verified': False}))
        self.enterContext(patch.object(apex_core, 'cas_bank_transaction', self.receiver, create=True))
        self.legacy = Mock(return_value={'ok': True})
        namespace = self.module.__dict__
        namespace.update(services=Obj(sim_info_manager=lambda: Obj(get_all=lambda: tuple(self.sims.values()))),
            _get_sim_info_by_id=resolve, _get_active_sim_info=lambda: self.first,
            _household_sim_infos=lambda sim: (self.first, self.second),
            _sim_id=lambda sim: sim.id, _MCCC_GUARD_MEMORY={'11': {}, '22': {}},
            _MCCC_SHIELD={'sim_ids': ['11', '22']},
            _load_json_file=lambda *_args: {'records': [{'sim_id': 11}, {'sim_id': 22}]},
            _READ_ONLY_ACTIONS={'status', 'diagnostics', 'list_sims'},
            _APEX_PRE_OWNER_RUN_ACTION=self.legacy)

    def route(self, action, value=None, sim_id='11'):
        return self.module.run_action(action, sim_id=sim_id, value=value)

    def test_ui_routes_resolve_current_sim_and_dispatch_typed_intent(self):
        called = Mock(return_value={'ok': True, 'clock_proof_validated': True})
        with patch.object(apex_core, 'phone_cas', Obj(ui_dispatch=called), create=True):
            for action in ('cas_bank_ui_review', 'cas_bank_ui_prepare', 'cas_bank_ui_commit'):
                value = {'expected_pending_sha256': 'a' * 64}
                self.assertTrue(self.route(action, json.dumps(value))['ok'])
                called.assert_called_with(self.module, '11', action, value)
            self.assertTrue(self.route('cas_bank_ui_status')['ok'])
            called.assert_called_with(self.module, '11', 'cas_bank_ui_status', None)
        self.legacy.assert_not_called()

    def test_ui_invalid_payload_or_absent_sim_never_reaches_clock_actor(self):
        called = Mock()
        with patch.object(apex_core, 'phone_cas', Obj(ui_dispatch=called), create=True):
            for action in ('cas_bank_ui_review', 'cas_bank_ui_prepare', 'cas_bank_ui_commit'):
                for value in (None, '[]', '{"a":1,"a":2}', '{"a":NaN}'):
                    self.assertFalse(self.route(action, value)['ok'])
                self.assertFalse(self.route(action, '{}', sim_id='missing')['ok'])
            self.assertFalse(self.route('cas_bank_ui_status', '{}')['ok'])
        called.assert_not_called()
        self.legacy.assert_not_called()

    def test_five_routes_delegate_only_the_owned_native_sim(self):
        for action in ('begin', 'status'):
            self.assertTrue(self.route('cas_bank_' + action)['ok'])
            getattr(self.receiver, action).assert_called_once_with(self.module, self.first)
        request = {'expected_pending_sha256': 'a' * 64}
        for action in ('observe', 'prepare', 'commit'):
            self.assertTrue(self.route('cas_bank_' + action, json.dumps(request))['ok'])
            getattr(self.receiver, action).assert_called_once_with(self.module, self.first, request)
        self.legacy.assert_not_called()

    def test_begin_and_status_reject_caller_checkpoint_bytes(self):
        for action in ('begin', 'status'):
            self.assertFalse(self.route('cas_bank_' + action, '{"original_owners": {}}')['ok'])
            getattr(self.receiver, action).assert_not_called()

    def test_bad_json_rejected_before_receiver(self):
        for value in ('[]', '{}x', '{"hash":1,"hash":2}', '{"nested":{"lane":1,"lane":2}}',
                      '{"number":NaN}', '{"number":Infinity}', ' ' * (256 * 1024 + 1)):
            with self.subTest(value=value[:40]):
                self.assertFalse(self.route('cas_bank_prepare', value)['ok'])
        self.receiver.prepare.assert_not_called()

    def test_receiver_failure_does_not_fall_back_or_claim_completion(self):
        self.receiver.commit.side_effect = ValueError('Lost metadata acknowledgment')
        result = self.route('cas_bank_commit', '{}')
        self.assertFalse(result['ok'])
        self.assertFalse(result['save_reload_verified'])
        self.legacy.assert_not_called()

    def test_read_only_routes_remain_available_while_checkpoint_blocked(self):
        self.blocked.add(11)
        for action in ('status', 'diagnostics', 'health', 'drift_status', 'copy_skin', 'auto_off'):
            self.assertTrue(self.route(action)['ok'])
        self.assertEqual(self.checked, [])
        self.assertTrue(self.route('cas_bank_status')['ok'])

    def test_legacy_mutations_and_unknown_future_actions_are_gated(self):
        self.blocked.add(11)
        for action in ('paste_cas', 'apply_saved_form', 'repair', 'normalize', 'add', 'remove',
                       'generate_form', 'delete_form', 'copy_current_to_form', 'copy_human_to_form',
                       'toggle_flag', 'restore_memory', 'fix_occult_drift', 'mccc_dresser_clean',
                       'cas_restore', 'future_unclassified_mutation'):
            with self.subTest(action=action):
                self.assertFalse(self.route(action)['ok'])
        self.legacy.assert_not_called()

    def test_household_preflight_checks_later_member_before_legacy_write(self):
        self.blocked.add(22)
        for action in ('cas_prepare_household', 'cas_restore_household', 'mccc_cas_restore', 'mccc_cas_shield_on'):
            self.checked.clear()
            self.assertFalse(self.route(action)['ok'])
            self.assertEqual(self.checked, [11, 22])
        self.legacy.assert_not_called()

    def test_global_repair_preflight_prevents_partial_first_sim_edit(self):
        self.blocked.add(22)
        self.assertFalse(self.route('repair_all')['ok'])
        self.assertEqual(self.checked, [11, 22])
        self.legacy.assert_not_called()

    def test_stale_primary_object_refused_before_any_write(self):
        old = Obj(id=11)
        with self.assertRaisesRegex(ValueError, 'manager-owned'):
            self.module._apex_preflight_appearance_targets((old,))
        self.assertEqual(self.checked, [])

    def test_duplicate_or_oversized_selection_refused(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.module._apex_preflight_appearance_targets((self.first, self.first))
        with self.assertRaisesRegex(ValueError, 'bound'):
            self.module._apex_preflight_appearance_targets((self.first,) * 4097)

    def test_wrong_thread_refuses_receiver_and_callback(self):
        self.module._APEX_GAME_THREAD_IDENT += 1
        self.assertFalse(self.route('cas_bank_begin')['ok'])
        self.receiver.begin.assert_not_called()
        called = Mock()
        guarded = self.module._apex_guard_legacy_callable(called, 'one')
        with self.assertRaisesRegex(ValueError, 'game thread'):
            guarded(self.first)
        called.assert_not_called()

    def test_callback_gates_all_restore_targets_before_original(self):
        self.blocked.add(22)
        for scope, args in (('one', (self.second,)), ('household', (self.first,)),
                            ('all', ()), ('guard-memory', ()), ('disk-cas', (self.first,)),
                            ('shield-restore', (self.first,)), ('shield-arm', (self.first,))):
            with self.subTest(scope=scope):
                called = Mock()
                guarded = self.module._apex_guard_legacy_callable(called, scope)
                with self.assertRaisesRegex(ValueError, 'unresolved'):
                    guarded(*args)
                called.assert_not_called()

    def test_explicit_single_sim_shield_arm_does_not_inherit_household(self):
        self.blocked.add(22)
        called = Mock(return_value='armed one')
        guarded = self.module._apex_guard_legacy_callable(called, 'shield-arm')
        self.assertEqual(guarded(self.first, household=False), 'armed one')
        self.assertEqual(self.checked, [11])

    def test_disk_restore_preflight_mirrors_original_integer_identity(self):
        self.blocked.add(22)
        self.module._load_json_file = lambda *_args: {'records': [{'sim_id': '00022'}]}
        called = Mock()
        guarded = self.module._apex_guard_legacy_callable(called, 'disk-cas')
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            guarded(self.first)
        self.assertEqual(self.checked, [22])
        called.assert_not_called()

    def test_malformed_disk_selection_refused_before_callback(self):
        for record in (None, {'sim_id': 'unparseable'}):
            self.module._load_json_file = lambda *_args, record=record: {'records': [record]}
            called = Mock()
            with self.assertRaisesRegex(ValueError, 'malformed'):
                self.module._apex_guard_legacy_callable(called, 'disk-cas')(self.first)
            called.assert_not_called()

    def test_disk_restore_active_fallback_is_gated_when_household_omits_it(self):
        self.blocked.add(11)
        self.module._household_sim_infos = lambda _sim: (self.second,)
        self.module._load_json_file = lambda *_args: {'records': [{'sim_id': 11}]}
        called = Mock()
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.module._apex_guard_legacy_callable(called, 'disk-cas')(self.first)
        self.assertEqual(self.checked, [11])
        called.assert_not_called()

    def test_install_wraps_all_concrete_callback_boundaries(self):
        names = ('_repair_sim', '_normalize_sim_state', '_cas_prepare_one', '_cas_prepare_keep_one',
                 '_cas_restore_one', '_restore_guard_one', '_restore_guard_household', '_repair_all',
                 '_restore_cas_recovery_snapshot', '_mccc_cas_shield_arm',
                 '_mccc_guard_restore_household', '_apex6_mccc_arm', '_apex6_mccc_restore')
        originals = {}
        for name in names:
            originals[name] = Mock()
            self.module.__dict__[name] = originals[name]
        self.module._apex_install_legacy_transaction_gates()
        self.blocked.add(22)
        for name in names:
            args = () if name in ('_repair_all', '_mccc_guard_restore_household') else (self.second,)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.module.__dict__[name](*args)
            originals[name].assert_not_called()


if __name__ == '__main__':
    unittest.main()
