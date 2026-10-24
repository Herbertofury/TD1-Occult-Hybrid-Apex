from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.test_driver import live_render_state, native_transform


class LiveRenderObservationTests(unittest.TestCase):
    def setUp(self):
        self.target = Obj(id=900, definition=Obj(id=460952))
        self.hold = Obj(target=self.target, is_finishing=False,
                        get_interaction_type=lambda: Obj(guid64=426489))
        self.display = Obj(get_outfit=Mock(return_value=Obj(part_ids=(101, 202))))
        self.actor = Obj(id=123, si_state=Obj(sis_actor_gen=lambda: iter((self.hold,))),
                         posture_state=Obj(left=None, right=Obj(target=None), back=Obj(target=self.target)))
        self.sim = Obj(id=123, current_occult_types=4, get_sim_instance=lambda: self.actor,
                       get_current_outfit=lambda: (0, 0), _client_outfits=self.display,
                       appearance_tracker=Obj(appearance_override_sim_info=self.display), occult_tracker=Obj())
        self.actor.sim_info = self.sim
        self.backend = Obj()

    def test_reports_stale_display_override_and_native_wing_owner_without_mutation(self):
        with patch('apex_core.form_appearance.evidence', side_effect=lambda _b, s: {'owner': id(s)}):
            result = live_render_state(self.backend, self.sim)
        self.assertTrue(result['client_uses_appearance_override'])
        self.assertNotEqual(result['server_appearance'], result['client_appearance_source'])
        self.assertEqual(result['running_interactions'], [dict(affordance=426489, target_id='900', finishing=False)])
        self.assertEqual(result['carry_owners'][-1], dict(track='back', object_id='900', definition_id=460952))
        self.assertIs(self.actor.posture_state.back.target, self.target)
        self.assertIs(self.sim.appearance_tracker.appearance_override_sim_info, self.display)
        self.assertFalse(result['appearance_written'])
        self.assertFalse(result['interactions_cancelled'])
        self.assertFalse(result['background_tasks'])
        self.assertFalse(result['pixels_verified'])

    def test_native_display_without_override_is_the_actual_selected_owner(self):
        self.sim._client_outfits = self.sim
        self.sim.get_outfit = self.display.get_outfit
        self.sim.appearance_tracker.appearance_override_sim_info = None
        with patch('apex_core.form_appearance.evidence', return_value={'same': True}):
            result = live_render_state(self.backend, self.sim)
        self.assertFalse(result['client_uses_appearance_override'])
        self.assertEqual(result['server_appearance'], result['client_appearance_source'])

    def test_foreign_actor_and_unreviewed_outfit_source_are_refused(self):
        self.actor.sim_info = object()
        with self.assertRaisesRegex(ValueError, 'actor does not belong'):
            live_render_state(self.backend, self.sim)
        self.actor.sim_info = self.sim
        self.sim._client_outfits = object()
        with self.assertRaisesRegex(ValueError, 'source differs'):
            live_render_state(self.backend, self.sim)
        self.display.get_outfit.assert_not_called()

    def test_large_runtime_collections_are_not_silently_truncated(self):
        self.display.get_outfit.return_value.part_ids = tuple(range(513))
        with self.assertRaisesRegex(ValueError, 'outfit exceeds'):
            live_render_state(self.backend, self.sim)
        self.display.get_outfit.return_value.part_ids = ()
        self.actor.si_state.sis_actor_gen = lambda: iter([self.hold] * 65)
        with self.assertRaisesRegex(ValueError, 'interactions exceed'):
            live_render_state(self.backend, self.sim)


class NativeTransformTests(unittest.TestCase):
    def test_unknown_or_foreign_requests_never_reach_native_interactions(self):
        with self.assertRaisesRegex(ValueError, 'reviewed native transformation'):
            native_transform(Obj(), Obj(), {'affordance_id': 1, 'household_id': '9', 'save_guid': '10'})
        with self.assertRaisesRegex(ValueError, 'active household/save'):
            native_transform(Obj(), Obj(household_id=2), {'affordance_id': 425308, 'household_id': '9', 'save_guid': '10'})

    def test_original_test_queue_runs_once_and_failure_is_not_replayed(self):
        from types import ModuleType
        resources = ModuleType('sims4.resources');resources.Types = Obj(INTERACTION=99)
        sims4 = ModuleType('sims4');sims4.resources = resources
        context = ModuleType('interactions.context')
        context.InteractionContext = Mock();context.InteractionContext.SOURCE_PIE_MENU = 7
        priority = ModuleType('interactions.priority');priority.Priority = Obj(High=5)
        interactions = ModuleType('interactions')
        affordance = Obj(guid64=425308)
        household = object();client = object()
        sim = Obj(id=123, household_id=9, household=household)
        actor = Obj(sim_info=sim, push_super_affordance=Mock(return_value=False))
        sim.get_sim_instance = lambda: actor
        manager = Obj(get=Mock(return_value=affordance))
        backend = Obj(services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 10),
                                  active_household=lambda: household, get_instance_manager=lambda _: manager,
                                  client_manager=lambda: Obj(get_first_client=lambda: client)))
        modules = {'sims4': sims4, 'sims4.resources': resources, 'interactions': interactions,
                   'interactions.context': context, 'interactions.priority': priority}
        with patch.dict(sys.modules, modules):
            result = native_transform(backend, sim, {'affordance_id': 425308, 'household_id': '9', 'save_guid': '10'})
        self.assertFalse(result['ok'])
        self.assertFalse(result['interaction_submitted'])
        self.assertFalse(result['retry_safe'])
        self.assertTrue(result['native_tests_preserved'])
        self.assertFalse(result['direct_form_setter_called'])
        self.assertFalse(result['transformation_completed_verified'])
        actor.push_super_affordance.assert_called_once_with(affordance, actor, context.InteractionContext.return_value)
        context.InteractionContext.assert_called_once_with(actor, 7, 5, client=client)


if __name__ == '__main__':
    unittest.main()
