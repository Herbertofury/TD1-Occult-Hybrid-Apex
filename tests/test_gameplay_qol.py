import enum
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import gameplay_qol


class State(enum.IntEnum):
    UNDEFINED = -1
    DISABLED = 0
    LIMITED_ONLY = 1
    FULL = 3


class Group(enum.IntEnum):
    DEFAULT = 0


class Settings:
    def __init__(self, value=State.UNDEFINED): self.value = value
    def get_setting(self, kind, group): return self.value
    def set_setting(self, value, group): self.value = value


class QolTests(unittest.TestCase):
    def setUp(self):
        self.q = importlib.reload(gameplay_qol)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.guid = 123
        self.service = types.SimpleNamespace(global_autonomy_settings=Settings())
        self.death = types.ModuleType('interactions.utils.death')
        self.death._is_death_enabled = True
        self.death.toggle_death = lambda enabled: setattr(self.death, '_is_death_enabled', enabled)
        self.sun_buff, self.other_buff = object(), object()
        tracking = types.SimpleNamespace(sunlight_buffs=[types.SimpleNamespace(buff_type=self.sun_buff)])
        trait = type('trait_OccultVampire', (), {'day_night_tracking': tracking})
        self.sim = types.SimpleNamespace(id=7, is_dead=False, death_type=0, trait_tracker=[trait])
        self.instance = types.SimpleNamespace(is_dying=False, get_autonomy_state_setting=lambda: self.service.global_autonomy_settings.value)
        self.sim.get_sim_instance = lambda: self.instance
        self.sim.get_traits = lambda: list(self.sim.trait_tracker)
        self.instance.sim_info = self.sim
        self.backend = types.SimpleNamespace(
            _data_directory=lambda: self.temp.name,
            _tuning_traits=lambda kind: [trait], OccultType=types.SimpleNamespace(VAMPIRE=4),
            services=types.SimpleNamespace(autonomy_service=lambda: self.service,
                get_persistence_service=lambda: types.SimpleNamespace(get_save_slot_proto_guid=lambda: self.guid),
                active_household=lambda: types.SimpleNamespace(sim_info_gen=lambda: [self.sim])))
        settings = types.ModuleType('autonomy.settings')
        settings.AutonomyState, settings.AutonomySettingsGroup = State, Group
        utils = types.ModuleType('interactions.utils'); utils.death = self.death
        modules = {'autonomy': types.ModuleType('autonomy'), 'autonomy.settings': settings,
                   'interactions': types.ModuleType('interactions'), 'interactions.utils': utils,
                   'interactions.utils.death': self.death}
        self.modules = patch.dict(sys.modules, modules); self.modules.start(); self.addCleanup(self.modules.stop)

    def test_pause_resume_restores_inherited_setting(self):
        self.assertTrue(self.q.dispatch(self.backend, self.sim, 'qol_autonomy_pause')['qol']['autonomy']['paused_by_apex'])
        self.q.dispatch(self.backend, self.sim, 'qol_autonomy_pause')
        self.q.dispatch(self.backend, self.sim, 'qol_autonomy_resume')
        self.assertEqual(self.service.global_autonomy_settings.value, State.UNDEFINED)

    def test_preexisting_disabled_autonomy_remains_disabled_after_resume(self):
        self.service.global_autonomy_settings.value = State.DISABLED
        self.q._autonomy(self.backend, True); self.q._autonomy(self.backend, False)
        self.assertEqual(self.service.global_autonomy_settings.value, State.DISABLED)

    def test_foreign_autonomy_edit_is_retained(self):
        self.q._autonomy(self.backend, True)
        self.service.global_autonomy_settings.value = State.LIMITED_ONLY
        with self.assertRaisesRegex(ValueError, 'Another mod'): self.q._autonomy(self.backend, False)
        self.assertEqual(self.service.global_autonomy_settings.value, State.LIMITED_ONLY)

    def test_new_autonomy_service_never_restores_old_world_setting(self):
        self.q._autonomy(self.backend, True)
        self.service = types.SimpleNamespace(global_autonomy_settings=Settings(State.FULL))
        self.assertFalse(self.q._autonomy(self.backend, False)['paused_by_apex'])
        self.assertEqual(self.service.global_autonomy_settings.value, State.FULL)

    def test_death_restore_retains_preexisting_disabled_setting(self):
        self.death._is_death_enabled = False
        self.q._death(True); self.q._death(True); self.q._death(False)
        self.assertFalse(self.death._is_death_enabled)

    def test_death_prevention_is_not_revival(self):
        self.instance.is_dying = True
        result = self.q.dispatch(self.backend, self.sim, 'qol_death_prevent')['qol']
        self.assertTrue(result['household_safety'][0]['is_dying'])
        self.assertFalse(result['death']['already_dying_sims_recovered'])
        self.assertFalse(self.death._is_death_enabled)

    def test_foreign_death_edit_is_retained(self):
        self.q._death(True); self.death._is_death_enabled = True
        with self.assertRaisesRegex(ValueError, 'Another mod'): self.q._death(False)
        self.assertTrue(self.death._is_death_enabled)

    def test_preferences_are_scoped_to_save_and_sim(self):
        self.q._load(self.backend); self.q._persist(self.backend, self.sim, 'sunlight', True)
        self.assertIn('7', self.q._SUN)
        self.assertNotIn('8', self.q._SUN)
        self.guid = 124; self.q._load(self.backend)
        self.assertFalse(self.q._SUN)
        self.guid = 123; self.q._load(self.backend)
        self.assertIn('7', self.q._SUN)

    def test_invalid_preferences_fail_before_mutation(self):
        Path(self.temp.name, 'gameplay_qol.json').write_text(json.dumps({'schema': 1, 'saves': {'123': {'7': {'sunlight': 'true'}}}}))
        with self.assertRaises(ValueError): self.q.dispatch(self.backend, self.sim, 'qol_autonomy_pause')
        self.assertEqual(self.service.global_autonomy_settings.value, State.UNDEFINED)

    def test_no_external_payload_accepted(self):
        with self.assertRaises(ValueError): self.q.dispatch(self.backend, self.sim, 'qol_death_prevent', '{}')
        self.assertTrue(self.death._is_death_enabled)

    def install_hooks(self):
        class Tracker:
            def _add_remove_day_night_buffs(self, buffs, add):
                return [(b.buff_type, add) for b in buffs]
        class Weather:
            def provide_route_events(self, route_event_context, sim, path, start_time=0, end_time=None):
                context = route_event_context
                self.observed_end_time = end_time
                enter, exit = self.umbrella_route_events.enter_carry_event, self.exit
                if not context.route_event_already_scheduled(enter, provider=self): context.events.append(enter)
                if not context.route_event_already_scheduled(exit, provider=self): context.events.append(exit)
        class Time:
            def __init__(self): self.calls = []
            def is_in_sunlight(self, sim):
                self.calls.append(sim)
                return True
        tracker_mod = types.ModuleType('traits.trait_tracker'); tracker_mod.TraitTracker = Tracker
        weather_mod = types.ModuleType('weather.weather_aware_component'); weather_mod.WeatherAwareComponent = Weather
        time_mod = types.ModuleType('time_service'); time_mod.TimeService = Time
        self.Time = Time
        with patch.dict(sys.modules, {'traits.trait_tracker': tracker_mod, 'weather.weather_aware_component': weather_mod,
                                     'time_service': time_mod}):
            self.q.install(self.backend); self.q.install(self.backend)
        return Tracker, Weather

    def test_daywalker_exposure_protects_only_opted_in_actual_vampires_and_delegates_other_sims(self):
        self.install_hooks(); time = self.Time()
        self.assertTrue(time.is_in_sunlight(self.instance))
        self.q._SUN.add('7')
        self.assertFalse(time.is_in_sunlight(self.instance))
        self.assertEqual(time.calls, [self.instance])
        other = types.SimpleNamespace(sim_info=types.SimpleNamespace(id=8, get_traits=self.sim.get_traits))
        self.assertTrue(time.is_in_sunlight(other))
        self.sim.get_traits = lambda: [object()]  # e.g. a PlantSim, no vampire trait
        self.assertTrue(time.is_in_sunlight(self.instance))
        self.q._SUN.clear()
        self.assertTrue(time.is_in_sunlight(self.instance))

    def test_daywalker_exposure_tracks_save_scoped_preferences_without_disk_access_in_callback(self):
        self.install_hooks(); self.q._persist(self.backend, self.sim, 'sunlight', True)
        time = self.Time()
        with patch.object(self.q, '_path', side_effect=AssertionError('callback disk access')):
            self.assertFalse(time.is_in_sunlight(self.instance))
        self.guid = 124; self.q._load(self.backend)
        self.assertTrue(time.is_in_sunlight(self.instance))

    def test_explicit_status_proves_the_installed_predicate_without_mutating_the_clock(self):
        self.install_hooks(); time = self.Time(); self.backend.services.time_service = lambda: time
        self.q._SUN.add('7')
        result = self.q.status(self.backend, self.sim)['sunlight_exposure']
        self.assertEqual(result, {'query': 'returned', 'apex_exposure_hook_installed': True,
            'effective_in_sunlight': False, 'previous_callback_in_sunlight': True})

    def test_sun_hook_filters_only_enabled_sim_vampire_buffs(self):
        Tracker, _ = self.install_hooks(); tracker = Tracker(); tracker._sim_info = self.sim
        self.q._SUN.add('7')
        buffs = [types.SimpleNamespace(buff_type=b) for b in (self.sun_buff, self.other_buff)]
        self.assertEqual(tracker._add_remove_day_night_buffs(buffs, True), [(self.other_buff, True)])
        self.assertEqual(len(tracker._add_remove_day_night_buffs(buffs, False)), 2)
        tracker._sim_info = types.SimpleNamespace(id=8)
        self.assertEqual(len(tracker._add_remove_day_night_buffs(buffs, True)), 2)

    def test_umbrella_hook_preserves_putaway_and_other_sims(self):
        _, Weather = self.install_hooks(); weather = Weather(); enter, exit = object(), object()
        weather.umbrella_route_events = types.SimpleNamespace(enter_carry_event=enter); weather.exit = exit
        context = types.SimpleNamespace(events=[], route_event_already_scheduled=lambda *a, **kw: False)
        self.q._UMBRELLA.add('7')
        weather.provide_route_events(context, types.SimpleNamespace(sim_info=self.sim), None)
        self.assertEqual(context.events, [exit])
        self.assertIsNone(weather.observed_end_time)
        context.events.clear()
        weather.provide_route_events(context, types.SimpleNamespace(sim_info=types.SimpleNamespace(id=8)), None)
        self.assertEqual(context.events, [enter, exit])
        self.assertIsNone(weather.observed_end_time)

    def test_umbrella_disabled_path_preserves_native_optional_arguments(self):
        _, Weather = self.install_hooks(); weather = Weather()
        weather.umbrella_route_events = types.SimpleNamespace(enter_carry_event=object()); weather.exit = object()
        context = types.SimpleNamespace(events=[], route_event_already_scheduled=lambda *a, **kw: False)
        weather.provide_route_events(context, types.SimpleNamespace(sim_info=self.sim), None, end_time=23)
        self.assertEqual(weather.observed_end_time, 23)


if __name__ == '__main__': unittest.main()
