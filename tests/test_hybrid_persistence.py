from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.hybrid_persistence import save_with_retention, load_with_retention


class Record:
    def __init__(self, kind=0, raw=b''):
        self.occult_type, self.raw = kind, raw
    def CopyFrom(self, other):
        self.occult_type, self.raw = other.occult_type, other.raw


class Records(list):
    def add(self):
        record = Record()
        self.append(record)
        return record


class PersistencePortTests(unittest.TestCase):
    def tracker(self):
        sim = Obj(occult_types=1|4|128, current_occult_types=1)
        return Obj(sim_info=sim, _sim_info=sim, _occult_form_available=False, OCCULT_DATA={4: object()})

    def test_save_exception_restores_every_temporary_flag(self):
        tracker = self.tracker()
        utils = Obj(get_occult_types_for_save=lambda item: 5,
                    recalc_occult_form_availability=lambda item, saving: setattr(item, '_occult_form_available', True))
        def failing(item):
            raise RuntimeError('disk save failed')
        with self.assertRaises(RuntimeError):
            save_with_retention(failing, tracker, utils)
        self.assertEqual(tracker.sim_info.occult_types, 133)
        self.assertFalse(tracker._occult_form_available)

    def test_unknown_saved_record_and_membership_are_retained(self):
        tracker = self.tracker()
        tracker._apex_unresolved_occult_records = (Record(128, b'unknown-form-with-CC'),)
        utils = Obj(get_occult_types_for_save=lambda item: 5, recalc_occult_form_availability=lambda *a, **kw: None)
        result = save_with_retention(lambda item: Obj(occult_types=5, occult_sim_infos=Records()), tracker, utils)
        self.assertEqual(result.occult_types, 133)
        self.assertEqual(result.occult_sim_infos[0].raw, b'unknown-form-with-CC')

    def test_current_unknown_record_is_never_overwritten_by_retained_copy(self):
        tracker = self.tracker()
        tracker._apex_unresolved_occult_records = (Record(128, b'older'),)
        utils = Obj(get_occult_types_for_save=lambda item: 5, recalc_occult_form_availability=lambda *a, **kw: None)
        result = save_with_retention(lambda item: Obj(occult_types=133, occult_sim_infos=Records([Record(128, b'new intentional state')])), tracker, utils)
        self.assertEqual(len(result.occult_sim_infos), 1)
        self.assertEqual(result.occult_sim_infos[0].raw, b'new intentional state')

    def test_load_retains_unrecognized_record_without_form_generation(self):
        class Enum:
            HUMAN = 1
            def __iter__(self):
                return iter((1, 4, 128))
        tracker = self.tracker()
        tracker._generate_sim_info = Mock(side_effect=AssertionError('unexpected generation'))
        tracker.has_occult_type = lambda value: False
        data = Obj(occult_types=133, current_occult_types=1, pending_occult_type=128,
                   occult_form_available=True, occult_sim_infos=[Record(128, b'opaque-form')])
        cache = Obj(OccultDataCache=Obj(process_custom_occults=lambda: None))
        result = load_with_retention(lambda *a: 'original-return', tracker, data, cache, None, Enum(), None)
        self.assertEqual(result, 'original-return')
        self.assertEqual(tracker._sim_info.occult_types, 133)
        self.assertEqual(tracker._apex_unresolved_occult_records[0].raw, b'opaque-form')
        self.assertEqual(tracker._pending_occult_type, 128)
