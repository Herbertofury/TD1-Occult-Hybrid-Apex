"""Foreign form traits must not redirect a hybrid; native effects still run."""
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import foreign_current_trait as fix


class ForeignCurrentTraitTests(unittest.TestCase):
    def setUp(self):
        self.alien, self.mermaid, self.membership = object(), object(), object()
        class Sim:
            def __init__(self):
                self.current_occult_types, self.occult_types = 2, 3
                self.traits, self.removals, self.effect_updates = [], [], 0
            def remove_trait(self, trait, **kwargs):
                self.removals.append((trait, kwargs))
                if trait not in self.traits: return False
                self.traits.remove(trait)
                for kind, data in self.occult_tracker.OCCULT_DATA.items():
                    if trait is data.occult_trait: self.occult_tracker.membership_removals.append(kind)
                    if trait is data.current_occult_trait: self.occult_tracker.switch_to_occult_type(1)
                self.effect_updates += 1
                return True
        class Tracker:
            def __init__(self, sim):
                self._sim_info = sim
                self._sim_info_map = {1: Obj(), 2: Obj(), 8: Obj()}
                self.switches, self.membership_removals = [], []
            def switch_to_occult_type(self, kind):
                self.switches.append(kind)
                self._sim_info.current_occult_types = kind
        self.sim = Sim(); self.tracker = self.sim.occult_tracker = Tracker(self.sim)
        self.tracker.OCCULT_DATA = {2: Obj(current_occult_trait=self.alien, occult_trait=self.membership),
                                   8: Obj(current_occult_trait=self.mermaid, occult_trait=object())}
        self.sim.traits = [self.alien, self.mermaid, self.membership]
        self.assertTrue(fix.install(self.tracker))

    def test_mermaid_trait_cleanup_keeps_active_alien_and_native_effects(self):
        self.assertTrue(self.sim.remove_trait(self.mermaid, force=True))
        self.assertEqual(self.sim.current_occult_types, 2)
        self.assertEqual(self.sim.occult_types, 3)
        self.assertEqual(self.sim.traits, [self.alien, self.membership])
        self.assertEqual(self.sim.removals, [(self.mermaid, {'force': True})])
        self.assertEqual(self.sim.effect_updates, 1)
        self.assertEqual(self.tracker.switches, [])
        self.assertEqual(fix._SCOPES.stack, [])

    def test_removing_active_current_trait_keeps_native_human_transform(self):
        self.assertTrue(self.sim.remove_trait(self.alien))
        self.assertEqual(self.tracker.switches, [1]); self.assertEqual(self.sim.current_occult_types, 1)

    def test_explicit_human_selection_outside_trait_cleanup_remains_native(self):
        self.tracker.switch_to_occult_type(1)
        self.assertEqual(self.tracker.switches, [1]); self.assertEqual(self.sim.current_occult_types, 1)

    def test_membership_removal_is_never_suppressed(self):
        self.sim.remove_trait(self.membership)
        self.assertEqual(self.tracker.membership_removals, [2])

    def test_single_occult_pair_keeps_native_behavior(self):
        del self.tracker._sim_info_map[1]
        self.sim.remove_trait(self.mermaid)
        self.assertEqual(self.tracker.switches, [1])

    def test_missing_foreign_owner_and_ambiguous_tuning_stay_native(self):
        del self.tracker._sim_info_map[8]
        self.tracker._sim_info_map[4] = Obj()
        self.sim.remove_trait(self.mermaid)
        self.assertEqual(self.tracker.switches, [1])

    def test_native_exception_propagates_once_and_releases_scope(self):
        original = type(self.sim).remove_trait._apex_original
        def failed_switch(kind): raise ValueError('native trait effect failed')
        self.tracker.switch_to_occult_type = failed_switch
        with self.assertRaisesRegex(ValueError, 'native trait effect failed'):
            self.sim.remove_trait(self.mermaid)
        self.assertEqual(len(self.sim.removals), 1)
        self.assertEqual(fix._SCOPES.stack, [])

    def test_repeat_install_does_not_stack_guards_or_repeat_removal(self):
        method = type(self.sim).remove_trait; switch = type(self.tracker).switch_to_occult_type
        self.assertTrue(fix.install(self.tracker))
        self.assertIs(type(self.sim).remove_trait, method)
        self.assertIs(type(self.tracker).switch_to_occult_type, switch)
        self.sim.remove_trait(self.mermaid)
        self.assertEqual(len(self.sim.removals), 1)


if __name__ == '__main__': unittest.main()
