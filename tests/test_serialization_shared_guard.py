from pathlib import Path
import sys
import threading
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import hybrid_persistence as persistence
from test_hybrid_persistence import Records
from test_outfit_snapshot import outfit


class SerializationSharedGuardTests(unittest.TestCase):
    def setUp(self):
        self.native_calls, self.trait_calls = [], []
        calls, traits = self.native_calls, self.trait_calls
        class Tracker:
            def _copy_shared_attributes(self, destination, kind, source, source_kind):
                calls.append((self, destination, kind, source, source_kind))
                destination.genetic_data = b'irreversibly filtered native genetics'
            @staticmethod
            def _copy_trait_ids(destination, source):
                traits.append((destination, source)); destination.base_trait_ids = source.base_trait_ids
        self.Tracker = Tracker
        self.stored = Obj(id=1, blob=outfit(0, 11), genetic_data=b'full opaque genetics', base_trait_ids=(5,))
        self.live = Obj(id=2, blob=outfit(0, 12), genetic_data=b'live genes', base_trait_ids=(5, 9), occult_types=5)
        self.tracker = Tracker(); self.tracker.sim_info = self.live
        self.tracker._sim_info_map = {1: self.stored}; self.tracker._occult_form_available = False
        self.tracker.OCCULT_DATA = {4: object()}
        self.backend = Obj(_v8_read_outfit_blob=lambda owner: owner.blob,
                           _restore_siminfo_payload=Mock(side_effect=AssertionError('Irreversible restore attempted')))
        self.utils = Obj(get_occult_types_for_save=lambda owner: 5, recalc_occult_form_availability=lambda *a, **k: None)
        self.enterContext(patch.object(persistence, '_appearance_backend', return_value=self.backend))

    def test_serializer_retains_appearance_without_invoking_irreversible_native_merge(self):
        def original(tracker):
            tracker._copy_shared_attributes(self.stored, 1, self.live, 1)
            return Obj(occult_types=5, occult_sim_infos=Records())
        persistence.save_with_retention(original, self.tracker, self.utils)
        self.assertEqual(self.stored.genetic_data, b'full opaque genetics')
        self.assertEqual(self.stored.base_trait_ids, (5, 9))
        self.assertEqual(self.native_calls, [])
        self.backend._restore_siminfo_payload.assert_not_called()
        # Ordinary transforms retain the complete original native behavior.
        self.tracker._copy_shared_attributes(self.stored, 1, self.live, 1)
        self.assertEqual(len(self.native_calls), 1)

    def test_exception_releases_scope_before_the_next_normal_native_call(self):
        def original(tracker):
            tracker._copy_shared_attributes(self.stored, 1, self.live, 1)
            raise RuntimeError('disk error')
        with self.assertRaisesRegex(RuntimeError, 'disk error'):
            persistence.save_with_retention(original, self.tracker, self.utils)
        self.tracker._copy_shared_attributes(self.stored, 1, self.live, 1)
        self.assertEqual(len(self.native_calls), 1)
        self.assertEqual(persistence._SERIALIZERS.contexts, [])

    def test_another_tracker_and_thread_keep_native_behavior(self):
        another = self.Tracker()
        def original(tracker):
            another._copy_shared_attributes(self.stored, 1, self.live, 1)
            # Use another destination so this test's captured owner stays exact.
            self.stored.genetic_data = b'full opaque genetics'
            thread = threading.Thread(target=lambda: tracker._copy_shared_attributes(Obj(), 1, self.live, 1))
            thread.start(); thread.join()
            tracker._copy_shared_attributes(self.stored, 1, self.live, 1)
            return Obj(occult_types=5, occult_sim_infos=Records())
        persistence.save_with_retention(original, self.tracker, self.utils)
        self.assertEqual(len(self.native_calls), 2)
        self.assertEqual(len(self.trait_calls), 1)

    def test_unregistered_native_owner_refuses_before_any_copy_or_generation(self):
        def original(tracker):
            tracker._copy_shared_attributes(Obj(), 1, self.live, 1)
        with self.assertRaisesRegex(ValueError, 'owner differs'):
            persistence.save_with_retention(original, self.tracker, self.utils)
        self.assertEqual(self.native_calls, [])
        self.assertEqual(self.trait_calls, [])

    def test_installation_is_idempotent(self):
        self.assertTrue(persistence.install_shared_guard(self.tracker))
        first = self.Tracker._copy_shared_attributes
        self.assertTrue(persistence.install_shared_guard(self.tracker))
        self.assertIs(self.Tracker._copy_shared_attributes, first)
