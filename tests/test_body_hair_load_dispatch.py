from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import body_hair_initialization as hair, form_appearance as appearance
from test_native_witch_persistence import Owner


class BodyHairLoadDispatchTests(unittest.TestCase):
    def setUp(self):
        self.sim = Owner(100, 'saved active alien with CC and unknown genetics', 100)
        self.sim.current_occult_types = 2
        self.forms = {k: Owner(100+k, 'stored-' + str(k), 100+k) for k in (1, 2, 4)}
        self.backend = Obj(_v8_read_outfit_blob=lambda owner: owner.blob)
        self.expected = {k: (o, appearance.packed(self.backend, o)) for k, o in self.forms.items()}
        self.expected[2] = (self.forms[2], appearance.packed(self.backend, self.sim))
        self.tracker = Obj(_sim_info_map=self.forms, _sim_info=self.sim,
                          _apex_native_load_owners=(self.forms, self.sim, self.expected))
        self.sim.occult_tracker = self.tracker
        self.native = Obj(_sim_info=self.sim, _pending_requests={78: 2, 79: 1, 42: 4})
        self.sim.body_type_level_tracker = self.native
        self.calls = []
        def original(native):
            self.calls.append(dict(native._pending_requests))
            if 78 in native._pending_requests:
                self.sim.genetic_data = b'replaced preferred swatch by provisional queued load'
            native._pending_requests = None
            return 'native result'
        self.original = original
        self.enterContext(patch('apex_core.hybrid_persistence._appearance_backend', return_value=self.backend))
        hair.checkpoint_load(self.tracker)

    def test_checkpointed_load_requests_cannot_replace_restored_cas_appearance(self):
        self.assertEqual(hair._dispatch(self.original, self.native), 'native result')
        self.assertEqual(self.calls, [{42: 4}])
        self.assertTrue(self.tracker._apex_body_hair_load_dispatch['appearance_unchanged'])
        self.assertEqual(self.tracker._apex_body_hair_load_dispatch['suppressed'], [78, 79])

    def test_later_changed_growth_request_stays_native(self):
        self.native._pending_requests[78] = 3
        hair._dispatch(self.original, self.native)
        self.assertEqual(self.calls, [{78: 3, 42: 4}])
        self.assertFalse(self.tracker._apex_body_hair_load_dispatch['appearance_unchanged'])

    def test_new_live_edit_survives_the_older_load_queue(self):
        self.sim.physique = 'fresh user edit after loading'
        hair._dispatch(self.original, self.native)
        self.assertEqual(self.calls, [{42: 4}])
        self.assertEqual(self.sim.physique, 'fresh user edit after loading')
        self.assertTrue(self.tracker._apex_body_hair_load_dispatch['appearance_unchanged'])
        self.assertFalse(self.tracker._apex_body_hair_load_dispatch['load_appearance_verified'])

    def test_later_genuine_same_level_request_is_not_the_initialization_request(self):
        self.native._apex_body_hair_request_versions = {78: 1}
        hair._dispatch(self.original, self.native)
        self.assertEqual(self.calls, [{78: 2, 42: 4}])
        self.assertEqual(self.tracker._apex_body_hair_load_dispatch['suppressed'], [79])

    def test_queue_without_a_load_checkpoint_and_later_same_level_requests_stay_native(self):
        hair._dispatch(self.original, self.native)
        self.native._pending_requests = {78: 2}
        hair._dispatch(self.original, self.native)
        self.assertEqual(self.calls, [{42: 4}, {78: 2}])
        hair.checkpoint_load(self.tracker)
        self.assertIs(self.tracker._apex_body_hair_load_requests, False)

    def test_changed_form_or_wrapper_cannot_replay_another_owners_load_requests(self):
        self.sim.current_occult_types = 4
        hair._dispatch(self.original, self.native)
        self.assertEqual(self.calls, [{78: 2, 79: 1, 42: 4}])

    def test_native_failure_is_called_once_and_consumes_the_initialization_scope(self):
        def failed(native):
            self.calls.append(dict(native._pending_requests))
            raise RuntimeError('native failed')
        with self.assertRaisesRegex(RuntimeError, 'native failed'):
            hair._dispatch(failed, self.native)
        self.assertEqual(self.calls, [{42: 4}])
        self.assertIs(self.tracker._apex_body_hair_load_requests, False)
        self.assertEqual(self.tracker._apex_body_hair_load_dispatch['native_call_count'], 1)


if __name__ == '__main__': unittest.main()
