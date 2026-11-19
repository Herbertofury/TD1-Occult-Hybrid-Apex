from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import body_hair_initialization as hair


class BodyHairInitializationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        test = self
        class Native:
            def refresh_hair_growth_commodities(self, stat_cache=None):
                self.request_client_level_change(78, self.requested)
                return 'statistic refresh completed'
            def request_client_level_change(self, body_type, new_level):
                test.calls.append((body_type, new_level))
                return 'native request'
        self.cls = Native
        self.sim = Obj(current_occult_types=2, _base=Obj(get_current_growth_level=lambda part: 1))
        self.tracker = Obj(_sim_info=self.sim, _sim_info_map={1: Obj(), 2: Obj(), 4: Obj()})
        self.sim.occult_tracker = self.tracker
        self.native = Native()
        self.native._sim_info, self.native.requested = self.sim, 1
        self.assertTrue(hair.install(Native))

    def test_refresh_updates_statistics_without_reapplying_same_level_swatch(self):
        self.assertEqual(self.native.refresh_hair_growth_commodities({'stat': 1}), 'statistic refresh completed')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.tracker._apex_body_hair_refresh_retention[0]['form_flags'], 2)
        self.assertEqual(hair._REFRESHES.owners, ())

    def test_actual_growth_and_shaving_outside_refresh_remain_native(self):
        self.assertEqual(self.native.request_client_level_change(78, 1), 'native request')
        self.native.request_client_level_change(78, 0)
        self.assertEqual(self.calls, [(78, 1), (78, 0)])

    def test_different_level_inside_refresh_is_not_suppressed(self):
        self.native.requested = 2
        self.native.refresh_hair_growth_commodities()
        self.assertEqual(self.calls, [(78, 2)])

    def test_native_single_pair_and_unreadable_growth_level_are_preserved(self):
        self.tracker._sim_info_map.pop(4)
        self.native.refresh_hair_growth_commodities()
        self.assertEqual(self.calls, [(78, 1)])
        self.tracker._sim_info_map[4] = Obj()
        def failed(part):
            raise RuntimeError('native getter refused')
        self.sim._base.get_current_growth_level = failed
        self.native.refresh_hair_growth_commodities()
        self.assertEqual(self.calls, [(78, 1), (78, 1)])

    def test_other_body_types_and_owner_changes_never_gain_authority(self):
        original = self.cls.request_client_level_change
        def refresh(owner, stat_cache=None):
            original(owner, 42, 1)
            owner._sim_info.current_occult_types = 4
            original(owner, 78, 1)
        # Exercise the bound held context without replacing the installed hook.
        hair._REFRESHES.owners = ((self.native, self.sim, self.tracker, self.tracker._sim_info_map, 2),)
        try:
            refresh(self.native)
        finally:
            hair._REFRESHES.owners = ()
        self.assertEqual(self.calls, [(42, 1), (78, 1)])

    def test_install_is_idempotent_and_unknown_signature_stays_native(self):
        wrapped = self.cls.refresh_hair_growth_commodities
        self.assertTrue(hair.install(self.cls))
        self.assertIs(wrapped, self.cls.refresh_hair_growth_commodities)
        class Unknown:
            def refresh_hair_growth_commodities(self, required, another_required): pass
            def request_client_level_change(self, body_type, new_level): pass
        self.assertFalse(hair.install(Unknown))

    def test_installed_ea_required_cache_argument_is_supported(self):
        test = self
        class Native:
            def refresh_hair_growth_commodities(self, stat_cache):
                self.request_client_level_change(78, 1)
                return stat_cache
            def request_client_level_change(self, body_type, new_level):
                test.calls.append((body_type, new_level))
        self.assertTrue(hair.install(Native))
        native = Native(); native._sim_info = self.sim
        self.assertEqual(native.refresh_hair_growth_commodities('native-cache'), 'native-cache')
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
