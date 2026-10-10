"""Native lifecycle fixtures; no game, save, sidecar or profile access."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
from apex_core import form_appearance as appearance, hybrid_persistence as persistence
from test_native_witch_persistence import Owner, NativeRecord, BaseWrapper


class NativeTransitionTests(unittest.TestCase):
    def setUp(self):
        self.live = Owner(100, 'latest unsaved Live', 1000)
        self.live.current_occult_types = 32
        self.owners = {kind: Owner(kind + 200, 'independent form ' + str(kind), kind + 2000)
                       for kind in (1, 2, 4, 8, 16, 32, 64, 128)}
        self.native_calls, self.shared_calls, self.trait_calls = [], [], []
        test = self
        class Tracker:
            def __init__(self):
                self._sim_info_map = test.owners
                self._sim_info = self.sim_info = test.live
            @staticmethod
            def _copy_trait_ids(destination, source):
                test.trait_calls.append((destination, source))
                destination.gameplay_progress = source.gameplay_progress + 1
            def _copy_shared_attributes(self, destination, kind, source, source_kind):
                test.shared_calls.append((destination, kind, source, source_kind))
                destination.physique = 'destructive shared physique'
                destination.blob = test.live.blob
            def _switch_to_occult_type_internal(self, target):
                test.native_calls.append(target)
                old = self._sim_info.current_occult_types
                self._sim_info_map[old].blob = self._sim_info.blob
                self._sim_info.current_occult_types = target
                owner = self._sim_info_map[target]
                self._copy_shared_attributes(owner, target, self._sim_info, old)
                # Native appearance effects can run after the shared helper.
                test.restore(self._sim_info, appearance.payload(appearance.packed(test.backend, owner)))
                self._sim_info.voice_effect = 888
                self._sim_info.current_outfit = (7, 0)
                self._sim_info.gameplay_progress += 20
                return 'native-result'
            def on_sim_ready_to_simulate(self, sim):
                sim.voice_effect = 777
                return 'native-ready-result'
        self.Tracker = Tracker
        self.tracker = Tracker()
        self.backend = Obj(_v8_read_outfit_blob=lambda owner: owner.blob,
                           _restore_siminfo_payload=Mock(side_effect=self.restore),
                           _resend_all_visuals=Mock())
        self.enterContext(patch.object(persistence, '_appearance_backend', return_value=self.backend))
        self.before = {kind: appearance.packed(self.backend, owner) for kind, owner in self.owners.items()}
        self.active = appearance.packed(self.backend, self.live)
        self.assertTrue(persistence.install_transition_guard(self.tracker))

    def restore(self, owner, values):
        for name, value in values.items():
            if name == '__outfits__':
                owner.blob = value[1]
            else:
                setattr(owner, name, value)

    def test_native_deferred_switch_keeps_every_independent_owner_and_latest_live_source(self):
        self.assertEqual(self.tracker._switch_to_occult_type_internal(2), 'native-result')
        for kind, owner in self.owners.items():
            self.assertEqual(appearance.packed(self.backend, owner), self.active if kind == 32 else self.before[kind])
        self.assertEqual(appearance.packed(self.backend, self.live), self.before[2])
        self.assertEqual(self.live.current_occult_types, 2)
        self.assertEqual(self.live.current_outfit, (7, 0))
        self.assertEqual(self.live.gameplay_progress, 365)
        self.assertEqual(self.owners[2].gameplay_progress, 346)
        self.assertEqual(self.native_calls, [2])
        self.assertEqual(self.shared_calls, [])
        self.assertEqual(len(self.trait_calls), 1)
        self.assertTrue(self.tracker._apex_native_transition_retention['all_stored_and_active_verified'])
        self.assertFalse(self.tracker._apex_native_transition_retention['bank_read'])
        self.assertEqual(persistence._SERIALIZERS.contexts, [])

    def test_same_form_trait_initialization_keeps_latest_live_edits(self):
        self.tracker._switch_to_occult_type_internal(32)
        self.assertEqual(appearance.packed(self.backend, self.owners[32]), self.active)
        self.assertEqual(appearance.packed(self.backend, self.live), self.active)
        self.assertEqual(appearance.packed(self.backend, self.owners[1]), self.before[1])

    def test_load_trait_projection_does_not_replace_complete_stored_source_genetics(self):
        self.tracker._apex_native_load_pending = True
        self.live.genetic_data = b'filtered active native load genetics'
        self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(appearance.packed(self.backend, self.owners[32]), self.before[32])
        self.assertEqual(appearance.packed(self.backend, self.live), self.before[2])

    def test_immutable_record_retains_parts_and_outfits_already_filtered_before_first_guard(self):
        record = NativeRecord(occult_type=32)
        BaseWrapper.copy_physical_attributes(record, self.owners[32])
        persistence._write_tattoos(record, self.owners[32].parts_custom_tattoos)
        record.outfits.ParseFromString(self.owners[32].blob)
        expected = self.before[32]
        self.owners[32].genetic_data = b'already filtered genetics'
        self.owners[32].blob = self.owners[2].blob
        persistence._remember_load_owners(self.tracker, {32: record})
        self.tracker._apex_native_load_pending = True
        self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(appearance.packed(self.backend, self.owners[32]), expected)
        self.assertEqual(appearance.packed(self.backend, self.live), self.before[2])
        self.tracker.on_sim_ready_to_simulate(self.live)
        self.assertEqual(appearance.packed(self.backend, self.owners[32]), expected)

    def test_immutable_load_owner_replacement_refuses_without_replaying_native_transition(self):
        persistence._remember_load_owners(self.tracker, {})
        self.tracker._apex_native_load_pending = True
        self.owners[32] = Owner(555, 'foreign wrapper', 555)
        with self.assertRaisesRegex(ValueError, 'load appearance ownership changed'):
            self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(self.native_calls, [])
        self.backend._restore_siminfo_payload.assert_not_called()

    def test_same_form_load_keeps_stored_payload_and_native_active_projection_separate(self):
        self.tracker._apex_native_load_pending = True
        self.live.genetic_data = b'filtered active native load genetics'
        filtered = appearance.packed(self.backend, self.live)
        self.tracker._switch_to_occult_type_internal(32)
        self.assertEqual(appearance.packed(self.backend, self.owners[32]), self.before[32])
        self.assertEqual(appearance.packed(self.backend, self.live), filtered)

    def test_ready_boundary_restores_loaded_voice_after_native_effect_then_releases_load_scope(self):
        self.tracker._apex_native_load_pending = True
        self.assertEqual(self.tracker.on_sim_ready_to_simulate(self.live), 'native-ready-result')
        self.assertEqual(self.live.voice_effect, self.owners[32].voice_effect)
        self.assertTrue(self.tracker._apex_native_load_appearance_retention['verified'])
        self.assertEqual(appearance.packed(self.backend, self.live), self.before[32])
        self.assertFalse(self.tracker._apex_native_load_pending)
        self.live.genetic_data = b'new unsaved Live genetics after readiness'
        self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(self.owners[32].genetic_data, b'new unsaved Live genetics after readiness')

    def test_trait_load_rejected_genetics_retains_sim_then_ready_uses_immutable_record(self):
        record = NativeRecord(occult_type=32)
        BaseWrapper.copy_physical_attributes(record, self.owners[32])
        persistence._write_tattoos(record, self.owners[32].parts_custom_tattoos)
        record.outfits.ParseFromString(self.owners[32].blob)
        persistence._remember_load_owners(self.tracker, {32: record})
        self.tracker._apex_native_load_pending = True
        self.owners[32].genetic_data = b'filtered before traits complete'

        def filtered_restore(owner, values):
            values = dict(values)
            if owner is self.owners[32]:
                values.pop('genetic_data', None)
            self.restore(owner, values)

        self.backend._restore_siminfo_payload.side_effect = filtered_restore
        self.assertEqual(self.tracker._switch_to_occult_type_internal(32), 'native-result')
        failure = self.tracker._apex_native_transition_failure
        self.assertTrue(failure['deferred_until_native_ready'])
        self.assertEqual(failure['desired_stored']['32'], self.before[32])
        self.assertFalse(hasattr(self.tracker, '_apex_native_transition_retention'))
        self.assertEqual(self.native_calls, [32])
        self.assertEqual(persistence._SERIALIZERS.contexts, [])
        self.backend._restore_siminfo_payload.side_effect = self.restore
        self.assertEqual(self.tracker.on_sim_ready_to_simulate(self.live), 'native-ready-result')
        self.assertEqual(appearance.packed(self.backend, self.owners[32]), self.before[32])
        self.assertEqual(appearance.packed(self.backend, self.live), self.before[32])
        self.assertTrue(self.tracker._apex_native_load_appearance_retention['verified'])

    def test_native_trait_load_exception_still_propagates_without_replay(self):
        self.tracker._apex_native_load_pending = True
        self.tracker._copy_shared_attributes = Mock(side_effect=RuntimeError('native trait setup failed'))
        with self.assertRaisesRegex(RuntimeError, 'native trait setup failed'):
            self.tracker._switch_to_occult_type_internal(32)
        self.assertEqual(self.native_calls, [32])
        self.assertFalse(self.tracker._apex_native_transition_failure['deferred_until_native_ready'])

    def test_loading_owner_replacement_never_softens_structural_failure(self):
        self.tracker._apex_native_load_pending = True
        self.tracker._copy_shared_attributes = Mock(side_effect=lambda *args: self.owners.pop(128))
        with self.assertRaisesRegex(ValueError, 'changed ownership'):
            self.tracker._switch_to_occult_type_internal(32)
        self.assertEqual(self.native_calls, [32])
        self.backend._restore_siminfo_payload.assert_not_called()
        self.assertFalse(self.tracker._apex_native_transition_failure['deferred_until_native_ready'])

    def test_ready_outside_load_keeps_native_effect_and_aliased_load_owner_never_writes(self):
        self.tracker.on_sim_ready_to_simulate(self.live)
        self.assertEqual(self.live.voice_effect, 777)
        self.backend._restore_siminfo_payload.assert_not_called()
        self.tracker._apex_native_load_pending = True
        self.owners[32] = self.live
        self.assertEqual(self.tracker.on_sim_ready_to_simulate(self.live), 'native-ready-result')
        self.backend._restore_siminfo_payload.assert_not_called()
        self.assertFalse(self.tracker._apex_native_load_appearance_failure['verified'])
        self.assertIn('aliased', self.tracker._apex_native_load_appearance_failure['error'])
        self.assertFalse(self.tracker._apex_native_load_pending)

    def test_unknown_stored_form_and_opaque_fields_are_retained(self):
        original = self.owners[128]
        self.tracker._switch_to_occult_type_internal(8)
        self.assertIs(self.tracker._sim_info_map[128], original)
        self.assertEqual(appearance.packed(self.backend, original), self.before[128])
        self.assertEqual(original.pelt_layers, b'not-an-occult-proto-field')
        self.assertEqual(original.custom_texture, 123)

    def test_unavailable_method_and_repeat_installation_have_no_extra_hook(self):
        first = self.Tracker._switch_to_occult_type_internal
        self.assertTrue(persistence.install_transition_guard(self.tracker))
        self.assertIs(first, self.Tracker._switch_to_occult_type_internal)
        self.assertFalse(persistence.install_transition_guard(Obj()))

    def test_single_native_pair_keeps_native_behavior(self):
        self.tracker._sim_info_map = {32: self.owners[32], 2: self.owners[2]}
        self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(len(self.shared_calls), 1)
        self.assertEqual(self.live.voice_effect, 888)
        self.backend._restore_siminfo_payload.assert_not_called()

    def test_unavailable_backend_keeps_original_native_call(self):
        with patch.object(persistence, '_appearance_backend', return_value=None):
            self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(self.native_calls, [2])
        self.assertEqual(len(self.shared_calls), 1)

    def test_native_exception_is_not_replayed_and_preserves_original_diagnostic(self):
        self.tracker._copy_shared_attributes = Mock(side_effect=RuntimeError('native failed'))
        with self.assertRaisesRegex(RuntimeError, 'native failed'):
            self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(self.native_calls, [2])
        self.backend._restore_siminfo_payload.assert_not_called()
        failure = self.tracker._apex_native_transition_failure
        self.assertEqual(failure['original_stored']['2'], self.before[2])
        self.assertEqual(failure['original_active'], self.active)
        self.assertFalse(failure['retry_safe'])
        self.assertEqual(persistence._SERIALIZERS.contexts, [])

    def test_replaced_owner_refuses_before_appearance_restoration(self):
        def replace(*args):
            self.owners[2] = Owner(999, 'replacement', 999)
        self.tracker._copy_shared_attributes = Mock(side_effect=replace)
        with self.assertRaisesRegex(ValueError, 'changed ownership'):
            self.tracker._switch_to_occult_type_internal(2)
        self.backend._restore_siminfo_payload.assert_not_called()
        self.assertEqual(self.native_calls, [2])

    def test_final_resend_mutation_is_a_failure_instead_of_a_false_pass(self):
        self.backend._resend_all_visuals.side_effect = lambda sim: setattr(self.owners[1], 'custom_texture', 987)
        with self.assertRaisesRegex(ValueError, 'final appearance readback'):
            self.tracker._switch_to_occult_type_internal(2)
        self.assertEqual(self.native_calls, [2])
        self.assertFalse(self.tracker._apex_native_transition_failure['retry_safe'])
        self.assertEqual(persistence._SERIALIZERS.contexts, [])


class ImmediateSelectionQueueTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'Source/td1_occult_hybrid_apex.py').read_text(encoding='utf-8-sig'))
        methods = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('_switch_to', '_switch_human')]
        module = ast.Module(body=methods, type_ignores=[])
        self.scope = {'OccultType': Obj(HUMAN=1), '_int_value': int,
                      '_get_current_flags': lambda sim: int(sim.current_occult_types), '_set_flags': Mock()}
        exec(compile(module, 'owned-immediate-selection-fixture', 'exec'), self.scope)
        self.sim = Obj(current_occult_types=2)
        self.tracker = Obj(_sim_info=self.sim, _pending_occult_type=64)
        self.tracker.switch_to_occult_type = Mock(side_effect=lambda value: setattr(self.sim, 'current_occult_types', value))
        self.tracker.set_pending_occult_type = Mock(side_effect=lambda value: setattr(self.tracker, '_pending_occult_type', value))

    def test_verified_immediate_selection_clears_old_queue_after_native_readback(self):
        self.assertTrue(self.scope['_switch_to'](self.tracker, 32))
        self.tracker.switch_to_occult_type.assert_called_once_with(32)
        self.tracker.set_pending_occult_type.assert_called_once_with(None)
        self.assertEqual(self.sim.current_occult_types, 32)
        self.assertIsNone(self.tracker._pending_occult_type)
        self.scope['_set_flags'].assert_not_called()

    def test_human_uses_same_verified_contract(self):
        self.assertTrue(self.scope['_switch_human'](self.tracker))
        self.tracker.set_pending_occult_type.assert_called_once_with(None)
        self.assertEqual(self.sim.current_occult_types, 1)

    def test_native_failure_keeps_queue_and_does_not_fabricate_success(self):
        self.tracker.switch_to_occult_type.side_effect = RuntimeError('native failure')
        self.assertFalse(self.scope['_switch_to'](self.tracker, 32))
        self.tracker.set_pending_occult_type.assert_not_called()
        self.assertEqual(self.tracker._pending_occult_type, 64)
        self.scope['_set_flags'].assert_not_called()

    def test_nonconverged_switch_and_unreadable_queue_never_report_success(self):
        self.tracker.switch_to_occult_type.side_effect = None
        self.assertFalse(self.scope['_switch_to'](self.tracker, 32))
        self.tracker.set_pending_occult_type.assert_not_called()
        del self.tracker._pending_occult_type
        self.tracker.switch_to_occult_type.reset_mock()
        self.assertFalse(self.scope['_switch_to'](self.tracker, 32))
        self.tracker.switch_to_occult_type.assert_not_called()

    def test_queue_clear_readback_must_succeed(self):
        self.tracker.set_pending_occult_type.side_effect = None
        self.assertFalse(self.scope['_switch_to'](self.tracker, 32))
        self.assertEqual(self.tracker._pending_occult_type, 64)


if __name__ == '__main__':
    unittest.main()
