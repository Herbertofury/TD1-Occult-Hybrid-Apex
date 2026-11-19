from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import hybrid_persistence as persistence


class Record:
    def __init__(self, kind=0, raw=b''):
        self.occult_type, self.raw = kind, raw
    def CopyFrom(self, other):
        self.occult_type, self.raw = other.occult_type, other.raw
    def SerializeToString(self):
        return self.raw


class Occults:
    HUMAN = 1
    def __iter__(self):
        return iter((1, 2))


class LoadRecordImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.incoming = Record(2, b'independent stored alien genetics and unknown future fields')
        self.data = Obj(occult_types=3, current_occult_types=2, pending_occult_type=None,
                        occult_form_available=True, occult_sim_infos=[self.incoming])
        self.sim = Obj(occult_types=3, current_occult_types=2, _base=Obj(raw=b'distinct active genetics'))
        self.form = Obj(_base=Obj(raw=b'independent stored native base'), load_outfits=Mock())
        self.tracker = Obj(sim_info=self.sim, _sim_info=self.sim, _sim_info_map={1: Obj(), 2: self.form, 4: Obj()},
            OCCULT_DATA={2: Obj()}, _generate_sim_info=Mock(return_value=self.form), has_occult_type=lambda kind: True)
        self.cache = Obj(OccultDataCache=Obj(process_custom_occults=lambda: None))
        self.destinations = []
        def copy_physical(destination, source):
            self.destinations.append(destination)
            destination.raw = source.raw
        self.base = Obj(copy_physical_attributes=copy_physical)
        self.enterContext(patch.object(persistence, 'install_transition_guard', return_value=True))
        self.retained = self.enterContext(patch.object(persistence, '_remember_load_owners'))
        self.enterContext(patch('apex_core.form_bank_seal.note_loaded'))

    def test_active_preparation_and_native_mutation_cannot_replace_retained_source(self):
        def native(tracker, data):
            data.occult_sim_infos[0].raw = b'native loader rewrote its input'
            return 'native result'
        result = persistence.load_with_retention(native, self.tracker, self.data, self.cache,
                                                None, Occults(), self.base)
        self.assertEqual(result, 'native result')
        source = self.retained.call_args.args[1][2]
        self.assertEqual(source.raw, b'independent stored alien genetics and unknown future fields')
        self.assertIsNot(source, self.incoming)
        self.assertIsNot(source, self.destinations[0])
        self.assertEqual(self.destinations[0].raw, b'distinct active genetics')
        self.assertEqual(self.sim._base.raw, b'distinct active genetics')
        self.assertEqual(self.form._base.raw, b'independent stored native base')
        self.assertTrue(self.tracker._apex_native_load_pending)

    def test_native_exception_does_not_publish_a_mutated_load_authority(self):
        with self.assertRaisesRegex(RuntimeError, 'native failed'):
            persistence.load_with_retention(Mock(side_effect=RuntimeError('native failed')), self.tracker,
                                           self.data, self.cache, None, Occults(), self.base)
        self.retained.assert_not_called()
        self.assertEqual(self.incoming.raw, b'independent stored alien genetics and unknown future fields')


if __name__ == '__main__':
    unittest.main()
