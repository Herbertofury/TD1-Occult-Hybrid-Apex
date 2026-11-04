"""Isolated real-caller tests with synthetic native outfit containers."""
import copy
import sys
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Source'))
sys.path.insert(0, str(ROOT / 'tests'))
from apex_core import appearance_transfer, form_appearance, outfit_hair, form_bank
from apex_core.dresser_parts import OutfitRollbackError, read_rows
from test_dresser_rollback import FaultList, item, arrays


def outfit(parts=None, shifts=None):
    result = item(parts=parts, shifts=shifts)
    result.category = 0
    result.outfit_id = 11
    return result


def faulty_destination():
    return outfit(parts=FaultList([10, 20], (2,)), shifts=FaultList([3, 4], (1,)))


def make_message(row):
    message = Obj(outfits=[row])
    message.SerializeToString = Mock(return_value=b'fixture output')
    return message


class CallerFaultTests(unittest.TestCase):
    def test_selective_appearance_merge_never_serializes_or_returns_partial_output(self):
        destination = faulty_destination()
        source = outfit()
        source.parts.ids[0] = 30
        src, dst = make_message(source), make_message(destination)
        backend = Obj(_studio_parse_snapshot=lambda raw: src if raw == b'source' else dst,
                      _restore_siminfo_payload=Mock())
        target = {'__outfits__': form_appearance.encode(('protobuf', b'target'))}
        origin = {'__outfits__': form_appearance.encode(('protobuf', b'source'))}
        target_before, origin_before = copy.deepcopy(target), copy.deepcopy(origin)
        selection = dict(fields=[], outfits='one', source_outfit=0, target_outfit=0, body_types=[1])
        with self.assertRaises(OutfitRollbackError) as error:
            appearance_transfer.merge(backend, target, origin, selection)
        self.assertEqual(error.exception.failed_fields, ('parts.ids',))
        self.assertIsInstance(error.exception.__cause__, RuntimeError)
        self.assertEqual(target, target_before)
        self.assertEqual(origin, origin_before)
        dst.SerializeToString.assert_not_called()
        backend._restore_siminfo_payload.assert_not_called()
        # The array whose rollback failed remains damaged in this retained
        # parser object; this test does not establish parser ownership safety.
        self.assertEqual(arrays(destination)[0], [])
        self.assertEqual(arrays(destination)[1:], [[1, 2], [3, 4], [5, 6], [7, 8]])

    def test_hair_reconcile_never_serializes_partial_output_after_double_failure(self):
        destination = faulty_destination()
        message = make_message(destination)
        backend = Obj(_studio_parse_snapshot=lambda raw: message,
            _v8_resolve_body_type=lambda name: (1, {}, '') if name == 'HAIR' else (None, {}, ''))
        fields = {'__outfits__': form_appearance.encode(('protobuf', b'fixture'))}
        before = copy.deepcopy(fields)
        original = outfit()
        original.parts.ids[0] = 30
        held = [{'category': 0, 'ordinal': 0, 'outfit_id': '11',
                 'hair': [{'index': 0, 'row': read_rows(original)[0]}]}]
        with self.assertRaises(OutfitRollbackError) as error:
            outfit_hair.reconcile(backend, fields, held, lane='32')
        self.assertEqual(error.exception.failed_fields, ('parts.ids',))
        self.assertEqual(fields, before)
        message.SerializeToString.assert_not_called()
        self.assertEqual(arrays(destination)[0], [])
        self.assertEqual(arrays(destination)[1:], [[1, 2], [3, 4], [5, 6], [7, 8]])

    def test_event_boundary_reports_failure_without_success(self):
        owner = Obj(id=123)
        logs = []
        backend = Obj(_APEX_GAME_THREAD_IDENT=threading.current_thread().ident,
                      _get_sim_info_by_id=lambda value: owner,
                      _log=logs.append)
        boundary = types.ModuleType('apex_core.cas_save_boundary')
        boundary.hair_policy_enabled = lambda backend, sim: True
        def injected_failure(backend, sim):
            raise OutfitRollbackError(('parts.ids',)) from RuntimeError('injected forward failure')
        with patch.object(form_bank, 'context', return_value=(None, 'test-owner')), \
                patch.dict(outfit_hair._ERRORS, {}, clear=True), \
                patch.dict(sys.modules, {'apex_core.cas_save_boundary': boundary}), \
                patch.object(outfit_hair, '_BACKEND', backend), \
                patch.object(outfit_hair, 'enforce', side_effect=injected_failure):
            self.assertIsNone(outfit_hair._event(owner, None, None))
            self.assertIn('parts.ids', outfit_hair._ERRORS['test-owner'])
        self.assertEqual(len(logs), 1)
        self.assertIn('rollback failed', logs[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
