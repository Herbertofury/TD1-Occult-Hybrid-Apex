from pathlib import Path
import copy
import math
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_controls


class CasWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.request = dict(operation='workspace', x=0.3, y=0.2, scale=1.2, locked=True, collapsed=False)
        self.layout = dict(x=0.3, y=0.2, scale=1.2, locked=True, collapsed=False, dragging=False)
        self.client = dict(control=dict(operation='workspace', layout=self.layout, visible=True, appearance_written=False))

    def test_complete_typed_wire_moves_ui_without_a_game_service_or_panel(self):
        def no_panel(*args): raise AssertionError('Workspace attempted native CAS panel lookup')
        self.assertEqual(cas_controls.wire(self.request, no_panel), (0, 0, 0, '0.3,0.2,1.2,1,0'))
        self.assertIsNone(cas_controls.validate(self.client, self.request))

    def test_each_missing_or_extra_field_is_refused(self):
        for field in self.request:
            request = dict(self.request); del request[field]
            with self.assertRaises((ValueError, KeyError)): cas_controls.wire(request, None)
        with self.assertRaises(ValueError): cas_controls.wire(dict(self.request, url='x'), None)

    def test_nonfinite_unbounded_or_untyped_coordinates_never_become_wire(self):
        for field in ('x', 'y', 'scale'):
            for value in (math.nan, math.inf, -math.inf, True, None, '0.5', -1, 2):
                request = dict(self.request); request[field] = value
                with self.assertRaises(ValueError): cas_controls.wire(request, None)
        for field in ('locked', 'collapsed'):
            for value in (0, 1, None, 'false'):
                request = dict(self.request); request[field] = value
                with self.assertRaises(ValueError): cas_controls.wire(request, None)

    def test_small_positions_are_canonical_decimal_not_exponents(self):
        request = dict(self.request, x=1e-9, y=-0.0)
        self.assertEqual(cas_controls.wire(request, None)[3], '0.000000001,0,1.2,1,0')

    def test_readback_cannot_claim_moved_layout_from_requested_values(self):
        for field, value in (('x', 0.4), ('y', 0.8), ('scale', 1), ('locked', False), ('collapsed', True)):
            client = copy.deepcopy(self.client); client['control']['layout'][field] = value
            with self.assertRaises(cas_controls.PostconditionMismatch): cas_controls.validate(client, self.request)
        for field, value in (('visible', False), ('appearance_written', True)):
            client = copy.deepcopy(self.client); client['control'][field] = value
            with self.assertRaises(ValueError): cas_controls.validate(client, self.request)
        self.layout['dragging'] = True
        with self.assertRaises(ValueError): cas_controls.validate(self.client, self.request)


if __name__ == '__main__': unittest.main()
