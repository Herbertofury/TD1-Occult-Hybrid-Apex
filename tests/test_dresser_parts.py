from pathlib import Path
import copy
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.dresser_parts import DresserParts, read_rows, write_rows


def outfit(shifts=None):
    return Obj(parts=Obj(ids=[99, 88]), body_types_list=Obj(body_types=[7, 2]),
               part_shifts=Obj(color_shift=[] if shifts is None else shifts),
               object_ids=Obj(object_id=[123, 456]), layer_ids=Obj(layer_id=[3, 4]),
               unknown_field=b'PRESERVE', outfitflags_array=[10, 11, 12])


class DresserPortTests(unittest.TestCase):
    def test_uint64_colors_order_absence_and_unrelated_fields_survive(self):
        for shifts in (None, [2**64-1, 0]):
            item = outfit(shifts)
            original = copy.deepcopy(item)
            rows = read_rows(item)
            write_rows(item, rows)
            self.assertEqual(item, original)
            self.assertEqual([row['id'] for row in rows], [99, 88])
            self.assertEqual(rows[0]['color_shift'], None if shifts is None else 2**64-1)

    def test_ambiguous_arrays_are_not_silently_truncated_or_padded(self):
        item = outfit([1])
        original = copy.deepcopy(item)
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            read_rows(item)
        self.assertEqual(item, original)

    def test_invalid_mixed_state_is_rejected_before_any_message_write(self):
        item = outfit([1, 2])
        original = copy.deepcopy(item)
        rows = read_rows(item)
        rows[1]['color_shift'] = None
        with self.assertRaises(ValueError):
            write_rows(item, rows)
        self.assertEqual(item, original)

    def test_authorized_dresser_slot_operations_keep_part_color_alignment(self):
        model = DresserParts([7, 2], [99, 88], [2**64-1, 0])
        self.assertFalse(model.add_part_shift(7, 99, 2**64-1))
        self.assertTrue(model.add_part_shift(7, 99, 2**63+5))
        self.assertEqual(model.get_color_shift(7), 2**63+5)
        self.assertTrue(model.remove_body_type(2))
        self.assertEqual(model._part_ids, [99])
        self.assertEqual(model._color_shifts, [2**63+5])
        with self.assertRaises(ValueError):
            model.add_part_shift(7, 99, float(2**63))
