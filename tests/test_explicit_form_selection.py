"""Do not erase a successful explicit selection through legacy form cleanup."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
import td1_occult_hybrid_apex as backend


class ExplicitFormSelectionTests(unittest.TestCase):
    def execute(self,action,switch_ok=True,availability_resets=False):
        sim=Obj(id=42,current_occult_types=1 if action=='switch' else 16)
        tracker=sim.occult_tracker=Obj(_sim_info=sim)
        target=2 if action=='switch' else 1
        def switch(*args):
            if switch_ok:sim.current_occult_types=target
            return switch_ok
        def available(*args):
            if availability_resets:sim.current_occult_types=1
            return True
        def cleanup(*args):sim.current_occult_types=1
        with patch.object(backend,'OccultType',Obj(HUMAN=1)), \
             patch.object(backend,'_get_sim_info_by_id',return_value=sim), \
             patch.object(backend,'_parse_occult',return_value=2), \
             patch.object(backend,'_safe_name',return_value='ALIEN'), \
             patch.object(backend,'_sim_label',return_value='Test Sim'), \
             patch.object(backend,'_add_occult',return_value=[]) as add, \
             patch.object(backend,'_switch_to',side_effect=switch) as nonhuman, \
             patch.object(backend,'_switch_human',side_effect=switch) as human, \
             patch.object(backend,'_set_tracker_form_available',side_effect=available) as availability, \
             patch.object(backend,'_recalc',side_effect=cleanup) as recalc:
            result=backend._BASE_RUN_ACTION(action,sim_id='42',occult='ALIEN')
        return result,sim,recalc,availability,human,nonhuman,add

    def test_existing_alien_selection_does_not_run_invalid_form_cleanup(self):
        result,sim,recalc,availability,human,nonhuman,add=self.execute('switch')
        self.assertTrue(result['ok']);self.assertEqual(sim.current_occult_types,2)
        recalc.assert_not_called();nonhuman.assert_called_once();availability.assert_called_once()

    def test_human_selection_from_spellcaster_respects_native_result(self):
        result,sim,recalc,availability,human,nonhuman,add=self.execute('human')
        self.assertTrue(result['ok']);self.assertEqual(sim.current_occult_types,1)
        recalc.assert_not_called();human.assert_called_once();availability.assert_not_called();add.assert_not_called()

    def test_rejected_native_selection_cannot_report_success_or_cleanup(self):
        for action in ('human','switch'):
            with self.subTest(action=action):
                result,sim,recalc,availability,human,nonhuman,add=self.execute(action,switch_ok=False)
                self.assertFalse(result['ok']);recalc.assert_not_called();availability.assert_not_called()

    def test_selection_changed_after_availability_write_is_rejected(self):
        result,sim,recalc,*rest=self.execute('switch',availability_resets=True)
        self.assertFalse(result['ok']);self.assertEqual(sim.current_occult_types,1);recalc.assert_not_called()


if __name__=='__main__':unittest.main()
