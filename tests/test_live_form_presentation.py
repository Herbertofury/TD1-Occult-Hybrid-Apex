import sys
from pathlib import Path
from types import SimpleNamespace as Obj, ModuleType
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import live_form_presentation as presentation


class LiveFormPresentationTests(unittest.TestCase):
    def setUp(self):
        self.proxy = Obj(definition=Obj(id=460952))
        self.holder = Obj(get_interaction_type=lambda: Obj(guid64=426489), target=self.proxy,
                          is_finishing=False, cancel=Mock(return_value=True))
        self.other = Obj(get_interaction_type=lambda: Obj(guid64=999), target=object(),
                         is_finishing=False, cancel=Mock())
        self.actor = Obj(posture_state=Obj(back=Obj(target=self.proxy)),
                         si_state=Obj(sis_actor_gen=lambda: iter((self.holder, self.other))))
        self.events = []
        self.sim = Obj(_base=object(), current_occult_types=64, get_sim_instance=lambda: self.actor,
                       appearance_tracker=Obj(evaluate_appearance_modifiers=lambda: self.events.append('modifiers')))
        self.actor.sim_info = self.sim
        for name in ('resend_current_occult_types', 'resend_physical_attributes',
                     'resend_current_outfit', 'force_resend_suntan_data'):
            setattr(self.sim, name, lambda name=name: self.events.append(name))
        module = ModuleType('interactions.interaction_finisher')
        module.FinishingType = Obj(CONDITIONAL_EXIT=3)
        self.enterContext(patch.dict(sys.modules, {'interactions.interaction_finisher': module}))

    def tracker(self, native=None):
        sim = self.sim
        events = self.events
        class Tracker:
            def switch_to_occult_type(self, target):
                events.append('native-switch')
                if native is not None:
                    return native(self, target)
                sim.current_occult_types = target
                events.append('native-trait-cleanup')
                return 'native-return'
        return Tracker()

    def owned(self, tracker):
        tracker._sim_info = self.sim
        tracker._sim_info_map = {n: Obj(_base=object()) for n in (1, 4, 64)}
        self.sim.occult_tracker = tracker
        return tracker

    def test_refresh_follows_native_trait_cleanup_and_chains_once(self):
        tracker = self.owned(self.tracker())
        self.assertTrue(presentation.install(tracker))
        before = type(tracker).switch_to_occult_type
        self.assertTrue(presentation.install(tracker))
        self.assertIs(type(tracker).switch_to_occult_type, before)
        owners = dict(tracker._sim_info_map)
        self.assertEqual(tracker.switch_to_occult_type(4), 'native-return')
        self.assertEqual(self.events[:3], ['native-switch', 'native-trait-cleanup', 'modifiers'])
        self.assertEqual(self.events.count('native-switch'), 1)
        self.assertEqual(tracker._sim_info_map, owners)
        self.holder.cancel.assert_called_once()
        self.other.cancel.assert_not_called()
        self.assertFalse(tracker._apex_live_form_presentation['pixels_verified'])

    def test_native_error_is_never_swallowed_or_replayed(self):
        def fail(*_):raise RuntimeError('native failed')
        tracker = self.owned(self.tracker(fail));presentation.install(tracker)
        with self.assertRaisesRegex(RuntimeError, 'native failed'):
            tracker.switch_to_occult_type(4)
        self.assertEqual(self.events, ['native-switch'])
        self.holder.cancel.assert_not_called()

    def test_unowned_or_same_form_calls_never_finalize(self):
        tracker = self.owned(self.tracker());presentation.install(tracker)
        with patch.object(presentation, 'finalize') as finish:
            tracker.switch_to_occult_type(64)
            tracker.switch_to_occult_type(8)
        finish.assert_not_called()

    def test_nested_native_current_trait_switches_finalize_outer_selection_only(self):
        def nested(tracker, target):
            if target == 4:tracker.switch_to_occult_type(1)
            self.sim.current_occult_types = target
        tracker = self.owned(self.tracker(nested));presentation.install(tracker)
        with patch.object(presentation, 'finalize', return_value={}) as finish:
            tracker.switch_to_occult_type(4)
        finish.assert_called_once_with(self.sim, 4)

    def test_fairy_other_mod_parts_and_native_conceal_keep_their_carry_owners(self):
        presentation.finalize(self.sim, 64)
        self.holder.cancel.assert_not_called()
        self.proxy.definition.id = 1234
        presentation.finalize(self.sim, 4)
        self.holder.cancel.assert_not_called()
        self.proxy.definition.id = 460952
        conceal = Obj(get_interaction_type=lambda: Obj(guid64=425311), is_finishing=False)
        self.actor.si_state.sis_actor_gen = lambda: iter((self.holder, conceal))
        receipt = presentation.finalize(self.sim, 4)
        self.assertTrue(receipt['native_wing_exit_in_progress'])
        self.holder.cancel.assert_not_called()

    def test_failed_cancellation_does_not_force_or_delete_a_part(self):
        self.holder.cancel.return_value = False
        receipt = presentation.finalize(self.sim, 4)
        self.assertEqual(receipt['cancelled_ea_wing_owners'], [])
        self.assertIs(self.actor.posture_state.back.target, self.proxy)
        self.holder.cancel.assert_called_once()

    def test_animation_loot_is_not_interrupted_and_cleanup_runs_after_native_completion(self):
        tracker = self.owned(self.tracker())
        self.sim.current_occult_types = 4
        test = self
        class NativeInteraction:
            sim = test.actor
            is_finishing = False
            def get_interaction_type(self):return Obj(guid64=152200)
            def _exited_pipeline(self):
                test.events.append('native-manual-dark-trait-and-cleanup')
                return 'native-exited'
        transform = NativeInteraction()
        self.actor.si_state.sis_actor_gen = lambda: iter((self.holder, transform))
        self.assertTrue(presentation.finalize(self.sim, 4)['native_transform_in_progress'])
        self.holder.cancel.assert_not_called()
        self.events.clear()
        presentation.install_completion(NativeInteraction)
        self.assertEqual(transform._exited_pipeline(), 'native-exited')
        self.assertEqual(self.events[0], 'native-manual-dark-trait-and-cleanup')
        self.holder.cancel.assert_called_once()
        self.assertEqual(tracker._apex_live_form_presentation['completed_native_interaction'], 152200)

    def test_visual_fault_is_observable_without_repeating_successful_native_switch(self):
        tracker = self.owned(self.tracker());presentation.install(tracker)
        self.actor.sim_info = object()
        self.assertEqual(tracker.switch_to_occult_type(4), 'native-return')
        self.assertIn('different SimInfo', tracker._apex_live_form_presentation['error'])
        self.assertFalse(tracker._apex_live_form_presentation['retry_safe'])
        self.assertEqual(self.events.count('native-switch'), 1)

    def test_native_cleanup_can_retire_the_actor_without_breaking_its_completed_exit(self):
        test = self
        class RetiringInteraction:
            sim = test.actor
            def get_interaction_type(self):return Obj(guid64=152200)
            def _exited_pipeline(self):
                test.actor.sim_info = None
                test.events.append('native-exited')
                return 'retired'
        presentation.install_completion(RetiringInteraction)
        self.assertEqual(RetiringInteraction()._exited_pipeline(), 'retired')
        self.assertEqual(self.events, ['native-exited'])
        self.holder.cancel.assert_not_called()

    def test_completion_does_not_catch_or_replay_original_game_or_mod_exceptions(self):
        test = self
        class FailedInteraction:
            sim = test.actor
            def get_interaction_type(self):return Obj(guid64=152200)
            def _exited_pipeline(self):
                test.events.append('native-exited')
                raise RuntimeError('original cleanup failed')
        presentation.install_completion(FailedInteraction)
        with self.assertRaisesRegex(RuntimeError, 'original cleanup failed'):
            FailedInteraction()._exited_pipeline()
        self.assertEqual(self.events, ['native-exited'])
        self.holder.cancel.assert_not_called()


if __name__ == '__main__':unittest.main()
