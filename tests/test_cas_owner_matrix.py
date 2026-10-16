import copy
import hashlib
import unittest
from cas_owner_matrix import inventory,appearance_view,digest,physique_markers,native_bytes,page_index


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

    def snapshot(self,raw=b'\x08\x7b\xf8\xff\x01\x11'):
        return dict(ok=True,owner_export=dict(schema=1,sim_id='123',owner_id='ghost/other',native_kind=1,
            generation=17,appearance_written=False,model_harvested=False,source='committed-native-appearance',
            bytes=len(raw),native_hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest()))

    def test_complete_snapshot_compares_unknown_future_bytes_without_projection(self):
        owner=dict(owner_id='ghost/other',native_kind=1)
        prior=native_bytes(self.snapshot(),'123',owner,17)
        changed=native_bytes(self.snapshot(b'\x08\x7b\xf8\xff\x01\x12'),'123',owner,17)
        self.assertNotEqual(prior,changed)
        self.assertEqual(prior,b'\x08\x7b\xf8\xff\x01\x11')

    def test_complete_snapshot_rejects_stale_owner_or_partial_data(self):
        owner=dict(owner_id='ghost/other',native_kind=1)
        for key,value in [('sim_id','456'),('owner_id','ghost/living'),('native_kind',2),('native_kind',True),
                          ('generation',16),('bytes',2),('sha256','0'*64),('native_hex','08'),
                          ('appearance_written',True),('model_harvested',True),('schema',True)]:
            with self.subTest(key=key,value=value):
                snapshot=self.snapshot();snapshot['owner_export'][key]=value
                with self.assertRaises(ValueError):native_bytes(snapshot,'123',owner,17)

    def test_cycle_pages_cover_every_member_and_exact_owner(self):
        members,_=inventory(self.status())
        value=dict(ok=True,appearance_written=False,model_harvested=False,save_submitted=False,members=[
            dict(identity=dict(sim_id=m['sim_id']),owners=[dict(owner_id=o['owner_id'],native_kind=o['native_kind'],
                sha256=hashlib.sha256((m['sim_id']+o['owner_id']).encode()).hexdigest()) for o in m['owners']]) for m in members])
        self.assertEqual(len(page_index(value,members)),5)
        for damage in ('missing','duplicate','kind','write'):
            changed=copy.deepcopy(value)
            if damage=='missing':changed['members'].pop()
            elif damage=='duplicate':changed['members'][0]['owners'].append(changed['members'][0]['owners'][0])
            elif damage=='kind':changed['members'][0]['owners'][0]['native_kind']=1
            else:changed['appearance_written']=True
            with self.subTest(damage=damage),self.assertRaises(ValueError):page_index(changed,members)


if __name__=='__main__':unittest.main()
