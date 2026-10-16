import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from cas_owner_matrix import inventory,appearance_view,digest,physique_markers,native_bytes,page_index,resume_prefix


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

    def resume_fixture(self,directory):
        native=self.status();native.update(pid=12345,scope_id='a'*32)
        members,_=inventory(native);sid='123';oid=members[0]['owners'][0]['owner_id']
        marker=physique_markers(members)[(sid,oid)]
        value=dict(ok=True,client=dict(sim=dict(simId=sid,physiqueValues=[marker]),
            catalogs=[dict(panel='skin_details',supported=True,items=[])]),
            native_owner_view_receipt=dict(sim_id=sid,owner_id=oid,native_kind=2,independent_undo_bound=True))
        def write(name,data):
            raw=json.dumps(data).encode();(directory/name).write_bytes(raw)
            return hashlib.sha256(raw).hexdigest()
        write('matrix-0000.json',native);receipt=write('matrix-0001.json',value)
        refused='Native UI transport has no distributor client; no CAS request sent.'
        write('matrix-0002.json',dict(ok=False,message=refused,request_state='failed',ui_transition_verified=False))
        prior=dict(ok=False,cycles=2,targets=members,differences=[],cas_accept_submitted=False,save_submitted=False,
            edit_markers_requested=True,native_bytes_requested=False,native_pages_requested=True,native_page_checkpoints=[],
            error='Matrix command failed: '+refused,steps=[dict(cycle=0,sim_id=sid,owner_id=oid,native_kind=2,
                receipt_sha256=receipt,view_sha256=digest(appearance_view(value['client'])))],
            marker_edits=[dict(sim_id=sid,owner_id=oid,requested=marker,readback=marker,receipt_sha256=receipt)])
        path=directory/'matrix.json';write(path.name,prior)
        return path,native,members,prior

    def test_resume_only_uses_exact_completed_receipts_in_same_native_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,native,members,_=self.resume_fixture(Path(temporary))
            prior,baselines,continuity=resume_prefix(path,native,members,2,True,False,True)
            self.assertEqual(len(baselines),1);self.assertEqual(continuity['completed_visits'],1)
            self.assertFalse(continuity['last_request_sent']);self.assertFalse(prior['ok'])

    def test_resume_rejects_uncertain_receipts_other_runtime_or_changed_baseline(self):
        for damage in ('pending','runtime','scope','receipt','view','order','saved'):
            with self.subTest(damage=damage),tempfile.TemporaryDirectory() as temporary:
                directory=Path(temporary);path,native,members,prior=self.resume_fixture(directory)
                if damage=='pending':
                    value=json.loads((directory/'matrix-0002.json').read_text());value['request_state']='pending'
                    (directory/'matrix-0002.json').write_text(json.dumps(value))
                elif damage=='runtime':native['pid']+=1
                elif damage=='scope':native['scope_id']='b'*32
                elif damage=='receipt':prior['marker_edits'][0]['receipt_sha256']='f'*64
                elif damage=='view':prior['steps'][0]['view_sha256']='f'*64
                elif damage=='order':prior['steps'][0]['owner_id']='ghost/other'
                elif damage=='saved':prior['save_submitted']=True
                path.write_text(json.dumps(prior))
                with self.assertRaises(ValueError):resume_prefix(path,native,members,2,True,False,True)


if __name__=='__main__':unittest.main()
