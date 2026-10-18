import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_form_catalog as catalog


def rows():
    result = [dict(owner_id='native/'+str(kind), native_kind=kind,
                   ui_token=0x20000000+i) for i, kind in enumerate(catalog.NATIVE)]
    identities = [(owner, kind) for owner, kind in catalog._PRIMARY.items() if '_' in owner]
    identities += [(owner, 1) for owner in sorted(catalog._HUMAN_LOOKS) if '_' in owner]
    identities += [('active/2', 2), ('fairy/fairy_alternate', 64),
                   ('werewolf/werewolf_human_cc', 32), ('ghost/ghost_ghost', 1),
                   ('servo/servo_robot', 1), ('reaper/reaper_reaper', 1),
                   ('reaper/reaper_unrobed', 1), ('plantsim/plantsim_plant', 1),
                   ('skeleton/skeleton_skeleton', 1), ('scarecrow/scarecrow_scarecrow', 1),
                   ('imaginary_friend/imaginary_friend_pegacorn', 1)]
    for identity, kind in identities:
        result.append(dict(owner_id=identity, native_kind=kind, ui_token=0x20000000+len(result)))
    return result


class CatalogTests(unittest.TestCase):
    def test_one_human_and_no_hidden_data_loss_or_input_mutation(self):
        original = rows(); before = copy.deepcopy(original)
        value = catalog.project(original, 'native/1', 'active/2')
        self.assertEqual(original, before)
        self.assertEqual([r['owner_id'] for r in value['forms'] if r['form_id']=='human/shared'], ['native/1'])
        visible = {r['owner_id'] for r in value['forms']}
        retained = {r['owner_id'] for r in value['retained_looks']}
        self.assertFalse(visible & retained)
        self.assertEqual(visible | retained, {r['owner_id'] for r in original})
        self.assertIn('alien/alien_disguise', retained)
        self.assertIn('vampire/vampire_base', retained)
        self.assertIn('native/2', retained)
        self.assertEqual(value['selected_form_id'], 'alien/alien')
        self.assertFalse(value['appearance_written'])

    def test_special_form_using_human_genus_is_still_its_own_form(self):
        value = catalog.project(rows(), 'native/1', 'ghost/ghost_ghost')
        ghost = next(r for r in value['forms'] if r['owner_id']=='ghost/ghost_ghost')
        self.assertEqual(ghost['native_kind'], 1)
        self.assertEqual(ghost['label'], 'Ghost')
        self.assertNotEqual(ghost['form_id'], 'human/shared')
        self.assertNotEqual(ghost['form_id'], 'vampire/dark')
        self.assertEqual(value['selected_form_id'], ghost['form_id'])

    def test_actual_alternates_and_human_looking_werewolf_remain(self):
        forms = catalog.project(rows(), 'native/1', 'native/4')['forms']
        ids = {r['owner_id'] for r in forms}
        self.assertIn('fairy/fairy_alternate', ids)
        self.assertIn('werewolf/werewolf_human_cc', ids)
        self.assertIn('reaper/reaper_unrobed', ids)
        self.assertNotIn('werewolf/werewolf_human', ids)

    def test_selected_named_primary_retains_exact_binding_without_copy(self):
        value = catalog.project(rows(), 'native/1', 'vampire/vampire_dark')
        self.assertEqual(next(r for r in value['forms'] if r['form_id']=='vampire/dark')['owner_id'],
                         'vampire/vampire_dark')
        self.assertIn('native/4', {r['owner_id'] for r in value['retained_looks']})

    def test_explicit_active_human_binding_does_not_create_second_human(self):
        original = rows()+[dict(owner_id='active/1', native_kind=1, ui_token=0x20010000)]
        value = catalog.project(original, 'active/1', 'active/1')
        self.assertEqual([r['owner_id'] for r in value['forms'] if r['form_id']=='human/shared'], ['active/1'])
        self.assertIn('native/1', {r['owner_id'] for r in value['retained_looks']})

    def test_unknown_explicit_form_is_preserved_and_duplicate_owners_refused(self):
        original = rows()+[dict(owner_id='future_mod/custom_form', native_kind=1, ui_token=0x20010000)]
        value = catalog.project(original, 'native/1', 'future_mod/custom_form')
        self.assertIn('future_mod/custom_form', {r['owner_id'] for r in value['forms']})
        with self.assertRaises(ValueError):
            catalog.project(original+[copy.deepcopy(original[0])], 'native/1', 'native/2')

    def test_storage_identity_cannot_substitute_another_rendering_kind(self):
        original = rows()
        next(r for r in original if r['owner_id']=='active/2')['native_kind'] = 4
        with self.assertRaises(ValueError):
            catalog.project(original, 'native/1', 'active/2')

    def test_displayed_bindings_match_native_writeback_not_selected_archive(self):
        bindings={str(kind):'native/'+str(kind) for kind in catalog.NATIVE}
        bindings['2']='active/2'
        value=catalog.project(rows(),'native/1','alien/alien_alien',bindings)
        self.assertEqual(next(r for r in value['forms'] if r['form_id']=='alien/alien')['owner_id'],'active/2')
        self.assertIn('alien/alien_alien',{r['owner_id'] for r in value['retained_looks']})
        for invalid in (dict(bindings,**{'1':'ghost/ghost_ghost'}),dict(bindings,**{'4':'active/2'}),{}):
            with self.assertRaises(ValueError):catalog.project(rows(),'native/1','active/2',invalid)


if __name__ == '__main__':
    unittest.main()
