from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_form_isolation as fix, hybrid_persistence as retention


class NativeFormIsolationTests(unittest.TestCase):
    def setUp(self):
        class Tracker:
            def _copy_shared_attributes(self, destination, destination_kind, source, source_kind):
                self.original_calls += 1
                destination.physique = source.physique
                destination.hidden = source.hidden
                return 'native-result'
            @staticmethod
            def _copy_trait_ids(destination, source):
                destination.gender_traits = source.gender_traits
        self.tracker = Tracker()
        self.tracker.original_calls = 0
        self.tracker._sim_info = Obj(_base=object(), physique='live', hidden='live-hidden', gender_traits=(10,))
        self.tracker._sim_info_map = {kind: Obj(_base=object(), physique=str(kind), hidden='hidden-'+str(kind),
                                                  gender_traits=()) for kind in (1, 2, 4)}
        self.assertTrue(fix.install(self.tracker))

    def call(self, kind=4, source_kind=2, destination=None):
        destination = self.tracker._sim_info_map[kind] if destination is None else destination
        return self.tracker._copy_shared_attributes(destination, kind, self.tracker._sim_info, source_kind)

    def test_existing_alien_to_vampire_copy_never_writes_appearance(self):
        vampire = self.tracker._sim_info_map[4]
        self.assertIsNone(self.call())
        self.assertEqual((vampire.physique, vampire.hidden), ('4', 'hidden-4'))
        self.assertEqual(vampire.gender_traits, (10,))
        self.assertEqual(self.tracker.original_calls, 0)
        self.assertFalse(self.tracker._apex_native_form_isolation_receipt['appearance_restore_performed'])

    def test_every_distinct_existing_pair_keeps_independent_values_without_a_guard(self):
        for target in (1, 2, 4):
            for source in (1, 2, 4):
                if target != source:
                    self.call(target, source)
        self.assertEqual(self.tracker.original_calls, 0)
        self.assertEqual(self.tracker._apex_native_form_isolation_receipt['count'], 6)
        self.assertEqual([o.physique for o in self.tracker._sim_info_map.values()], ['1', '2', '4'])

    def test_new_form_initialization_stays_native_until_owner_registered(self):
        new = Obj(_base=object(), physique='new', hidden='new-hidden', gender_traits=())
        self.assertEqual(self.call(destination=new), 'native-result')
        self.assertEqual((new.physique, new.hidden), ('live', 'live-hidden'))
        self.assertEqual(self.tracker.original_calls, 1)

    def test_single_occult_and_same_form_copy_keep_native_behavior(self):
        self.assertEqual(self.call(2, 2), 'native-result')
        del self.tracker._sim_info_map[1]
        self.assertEqual(self.call(), 'native-result')
        self.assertEqual(self.tracker.original_calls, 2)

    def test_aliased_native_base_and_foreign_source_keep_native_behavior(self):
        self.tracker._sim_info_map[4]._base = self.tracker._sim_info._base
        self.assertEqual(self.call(), 'native-result')
        self.tracker._sim_info_map[4]._base = object()
        source = Obj(_base=object(), physique='foreign', hidden='foreign', gender_traits=())
        self.assertEqual(self.tracker._copy_shared_attributes(self.tracker._sim_info_map[4], 4, source, 2), 'native-result')

    def test_repeated_install_under_fallback_wrapper_does_not_stack(self):
        self.assertTrue(retention.install_shared_guard(self.tracker))
        method = type(self.tracker)._copy_shared_attributes
        for _ in range(4):
            self.assertTrue(fix.install(self.tracker))
            self.assertTrue(retention.install_shared_guard(self.tracker))
        self.assertIs(type(self.tracker)._copy_shared_attributes, method)
        self.call()
        self.assertEqual(self.tracker._apex_native_form_isolation_receipt['count'], 1)

    def test_native_trait_copy_failure_propagates_without_copy_or_restore(self):
        # Rebuild the class with a failing native static helper before install.
        class Broken(type(self.tracker)):
            _copy_shared_attributes = type(self.tracker)._copy_shared_attributes._apex_original
            @staticmethod
            def _copy_trait_ids(destination, source):
                raise RuntimeError('trait copy failed')
        self.tracker.__class__ = Broken
        self.assertTrue(fix.install(self.tracker))
        with self.assertRaisesRegex(RuntimeError, 'trait copy failed'):
            self.call()
        self.assertEqual(self.tracker.original_calls, 0)
        self.assertEqual(self.tracker._sim_info_map[4].physique, '4')

    def test_fallback_scope_delegates_to_prevention_patch_without_duplicate_trait_copy(self):
        self.assertTrue(retention.install_shared_guard(self.tracker))
        vampire, sim = self.tracker._sim_info_map[4], self.tracker._sim_info
        previous = getattr(retention._SERIALIZERS, 'contexts', None)
        retention._SERIALIZERS.contexts = [(self.tracker, {4: (vampire, {})}, (sim, {}))]
        try:
            self.call()
        finally:
            if previous is None:
                del retention._SERIALIZERS.contexts
            else:
                retention._SERIALIZERS.contexts = previous
        self.assertEqual(self.tracker.original_calls, 0)
        self.assertEqual(vampire.physique, '4')
        self.assertEqual(self.tracker._apex_native_form_isolation_receipt['count'], 1)


if __name__ == '__main__':
    unittest.main()
