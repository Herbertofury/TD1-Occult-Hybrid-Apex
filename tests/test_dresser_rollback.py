import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.dresser_parts import OutfitRollbackError, read_rows, write_rows


class FaultList(list):
    def __init__(self, values, failing_extensions=()):
        super().__init__(values)
        self.extension = 0
        self.failing_extensions = set(failing_extensions)

    def extend(self, values):
        self.extension += 1
        if self.extension in self.failing_extensions:
            raise RuntimeError('injected extend failure {}'.format(self.extension))
        return super().extend(values)


def item(parts=None, shifts=None):
    return Obj(parts=Obj(ids=[10, 20] if parts is None else parts),
               body_types_list=Obj(body_types=[1, 2]),
               part_shifts=Obj(color_shift=[3, 4] if shifts is None else shifts),
               object_ids=Obj(object_id=[5, 6]),
               layer_ids=Obj(layer_id=[7, 8]),
               opaque=b'KEEP')


def arrays(value):
    return [list(value.parts.ids), list(value.body_types_list.body_types),
            list(value.part_shifts.color_shift), list(value.object_ids.object_id),
            list(value.layer_ids.layer_id)]


class FaultTests(unittest.TestCase):
    def test_success_keeps_all_other_rows_and_opaque_data(self):
        target = item()
        rows = read_rows(target)
        rows[0]['id'] = 30
        write_rows(target, rows)
        self.assertEqual(arrays(target), [[30, 20], [1, 2], [3, 4], [5, 6], [7, 8]])
        self.assertEqual(target.opaque, b'KEEP')

    def test_forward_failure_with_working_rollback_keeps_original_arrays(self):
        target = item(shifts=FaultList([3, 4], (1,)))
        initial = arrays(target)
        rows = read_rows(target)
        rows[0].update(id=30, body_type=9)
        with self.assertRaisesRegex(RuntimeError, 'injected extend failure 1'):
            write_rows(target, rows)
        self.assertEqual(arrays(target), initial)

    def test_each_forward_array_failure_restores_every_array(self):
        for position, field in enumerate(('ids', 'body_types', 'color_shift', 'object_id', 'layer_id')):
            with self.subTest(position=position):
                target = item()
                containers = (target.parts, target.body_types_list, target.part_shifts,
                              target.object_ids, target.layer_ids)
                original = getattr(containers[position], field)
                setattr(containers[position], field, FaultList(original, (1,)))
                initial = arrays(target)
                rows = read_rows(target)
                rows[0].update(id=30, body_type=9, color_shift=15, object_id=16, layer_id=17)
                with self.assertRaisesRegex(RuntimeError, 'injected extend failure 1'):
                    write_rows(target, rows)
                self.assertEqual(arrays(target), initial)

    def test_failed_rollback_still_attempts_restoring_other_arrays(self):
        # Parts writes successfully, then fails on its rollback. Shifts causes
        # the original error; body types must still be restored independently.
        target = item(parts=FaultList([10, 20], (2,)), shifts=FaultList([3, 4], (1,)))
        target.object_ids.object_id = FaultList([5, 6])
        target.layer_ids.layer_id = FaultList([7, 8])
        initial = arrays(target)
        rows = read_rows(target)
        rows[0].update(id=30, body_type=9, color_shift=15)
        with self.assertRaisesRegex(OutfitRollbackError, 'rollback') as error:
            write_rows(target, rows)
        self.assertIsInstance(error.exception, RuntimeError)
        self.assertNotIsInstance(error.exception, ValueError)
        self.assertEqual(error.exception.failed_fields, ('parts.ids',))
        self.assertIsInstance(error.exception.__cause__, RuntimeError)
        self.assertEqual(str(error.exception.__cause__), 'injected extend failure 1')
        self.assertEqual(arrays(target)[1:], initial[1:])
        self.assertEqual(target.object_ids.object_id.extension, 1)
        self.assertEqual(target.layer_ids.layer_id.extension, 1)
        self.assertEqual(target.opaque, b'KEEP')

    def test_multiple_rollback_failures_list_every_failed_field(self):
        target = item(parts=FaultList([10, 20], (2,)), shifts=FaultList([3, 4], (1, 2)))
        rows = read_rows(target)
        with self.assertRaises(OutfitRollbackError) as error:
            write_rows(target, rows)
        self.assertEqual(error.exception.failed_fields, ('parts.ids', 'part_shifts.color_shift'))
        self.assertIn('parts.ids', str(error.exception))
        self.assertIn('part_shifts.color_shift', str(error.exception))
        self.assertEqual(str(error.exception.__cause__), 'injected extend failure 1')
        self.assertEqual(target.body_types_list.body_types, [1, 2])
        self.assertEqual(target.object_ids.object_id, [5, 6])
        self.assertEqual(target.layer_ids.layer_id, [7, 8])


if __name__ == '__main__':
    unittest.main(verbosity=2)
