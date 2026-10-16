import copy
import unittest
from cas_owner_matrix import inventory,appearance_view,digest,physique_markers


class OwnerMatrixTests(unittest.TestCase):
    def status(self):
        return dict(ok=True,selection_enabled=True,selected_native=dict(available=True,sim_id='123'),
            members=[dict(sim_id='123',owned_mask=127,imported_mask=127,separate_owners=[
                dict(owner_id='alien/alien',native_kind=2),dict(owner_id='alien/disguise',native_kind=1),
                dict(owner_id='ghost/other',native_kind=1),dict(owner_id='custom/new_future_form',native_kind=1)]),
                dict(sim_id='456',owned_mask=5,imported_mask=5,separate_owners=[dict(owner_id='native/4',native_kind=4)])])

    def test_all_members_and_same_kind_named_forms_are_distinct_targets(self):
        status=self.status();prior=copy.deepcopy(status);members,sid=inventory(status)
        self.assertEqual([len(m['owners']) for m in members],[4,1]);self.assertEqual(sid,'123')
        self.assertEqual(status,prior)

    def test_missing_duplicate_or_other_member_identity_refuses(self):
        for damage in ('duplicate-member','duplicate-owner','bad-kind','incomplete','selected'):
            with self.subTest(damage=damage):
                status=self.status()
                if damage=='duplicate-member':status['members'][1]['sim_id']='123'
                elif damage=='duplicate-owner':status['members'][0]['separate_owners'].append(dict(owner_id='alien/alien',native_kind=2))
                elif damage=='bad-kind':status['members'][0]['separate_owners'][0]['native_kind']=3
                elif damage=='incomplete':status['members'][0]['imported_mask']=5
                else:status['selected_native']['sim_id']='999'
                with self.assertRaises(ValueError):inventory(status)

    def test_unknown_sim_fields_empty_panels_and_layer_records_are_compared(self):
        client=dict(sim=dict(simId='123',newFutureField={'opaque':[1,2,3]}),catalogs=[
            dict(panel='skin_details',supported=True,items=[],preset=None,preset_query='returned-null'),
            dict(panel='tattoos',supported=True,items=[dict(dataID='9223372036854775816',layerId=2)],preset=None,preset_query='returned-null')])
        before=appearance_view(client);client['sim']['newFutureField']['opaque'][2]=4
        self.assertNotEqual(digest(before),digest(appearance_view(client)))
        self.assertIn('skin_details',before['panels']);self.assertEqual(before['sim']['newFutureField']['opaque'],[1,2,3])

    def test_duplicate_panel_is_not_silently_overwritten(self):
        client=dict(sim=dict(simId='123'),catalogs=[dict(panel='tattoo',supported=True)]*2)
        with self.assertRaises(ValueError):appearance_view(client)

    def test_markers_use_native_representable_increments_and_distinct_owners(self):
        members,_=inventory(self.status());markers=physique_markers(members)
        self.assertEqual(len(markers),5);self.assertEqual(len(set(markers.values())),5)
        for value in markers.values():
            self.assertLess(abs(value*1500-round(value*1500)),0.001)
            self.assertTrue(0.15<value<0.85)
        with self.assertRaises(ValueError):physique_markers([])


if __name__=='__main__':unittest.main()
