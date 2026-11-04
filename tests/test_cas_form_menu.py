"""Browsing variants must not authorize a form change or hide a failed readback."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_controls, cas_ui


class FormMenuTests(unittest.TestCase):
    def test_exact_family_and_all_are_typed_data_only_commands(self):
        for family in ('all', 'imaginary_friend', 'ghost', 'future_mod'):
            request = dict(operation='form-menu', family=family)
            _, wire = cas_ui.envelope('12', request)
            self.assertEqual(wire.split('|')[2:], ['form-menu','0','0','0',family])
        for value in ('', 'Ghost', 'ghost/look', '../ghost', 'ghost|save', None, 1, 'a'*65):
            with self.assertRaises(ValueError):
                cas_controls.wire(dict(operation='form-menu', family=value), None)

    def test_exact_variant_menu_requires_unique_nonempty_families_and_no_appearance_write(self):
        request = dict(operation='form-menu', family='imaginary_friend')
        control = dict(operation='form-menu', variant_family='imaginary_friend', appearance_written=False,
            life_states=[dict(family='human', variants=[dict(owner_id='native/1')]),
                         dict(family='imaginary_friend', variants=[dict(owner_id='imaginary_friend/pegacorn')])])
        self.assertIsNone(cas_controls.validate(dict(control=control), request))
        for name, value in (('variant_family','ghost'), ('appearance_written',True), ('life_states',[]),
                            ('life_states',[control['life_states'][0]]),
                            ('life_states',[control['life_states'][1]]*2),
                            ('life_states',[dict(family='imaginary_friend',variants=[])])):
            changed=copy.deepcopy(control);changed[name]=value
            with self.assertRaises(cas_controls.PostconditionMismatch):
                cas_controls.validate(dict(control=changed), request)
        control['variant_family']=''
        self.assertIsNone(cas_controls.validate(dict(control=control),dict(operation='form-menu',family='all')))
