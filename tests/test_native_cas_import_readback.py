import copy
import hashlib
import os
import sys
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import patch
from apex_core import native_cas_engine as engine, cas_owner_decode, form_appearance as appearance,overlay_loader


class NativeImportReadbackTests(unittest.TestCase):
    def fixture(self):
        scope='a'*32;pid=os.getpid();members=[];expected={};pages={};decoded={}
        for sid in ('123','456'):
            identities={'active/2':2,'ghost/manifested':1,'native/1':1,'native/2':2}
            members.append(dict(sim_id=sid,owned_mask=3,graph_generation=7,graph_selected_owner_id='active/2'))
            rows=[]
            for oid,kind in sorted(identities.items()):
                fields=dict(physique=appearance.encode(sid+oid),genetic_data=appearance.encode(b'\xa0\x06\x01'),
                            __outfits__=appearance.encode(('protobuf',b'\xa0\x06\x01')))
                expected[(sid,oid)]=dict(native_kind=kind,fields=fields)
                raw=(sid+oid).encode('ascii');decoded[raw]=fields
                rows.append(dict(owner_id=oid,native_kind=kind,native_hex=raw.hex(),bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),revision=0,linked_targets=[]))
            pages[sid]=dict(ok=True,schema=1,scope='native-owner-export-page',pid=pid,scope_id=scope,
                sim_id=sid,generation=7,owned_mask=3,selected_owner_id='active/2',total_owners=4,start_index=0,
                complete=True,after_owner_id='',next_owner_id=None,owners=rows,
                appearance_written=False,model_harvested=False,game_files_written=False,
                native_patch_qualified=False,production_ready=False,source='committed-native-appearance')
        status=dict(ok=True,selection_enabled=True,pid=pid,scope_id=scope,members=members)
        def read(raw,sid,template):
            self.assertTrue(raw.startswith(sid.encode('ascii')))
            self.assertTrue(all(row['value'] in ('',0,0.0) for row in template.values()))
            return dict(fields=copy.deepcopy(decoded[raw]))
        return status,expected,pages,decoded,read

    def test_every_member_native_active_and_named_owner_compares_to_fresh_original(self):
        status,expected,pages,decoded,read=self.fixture();before=copy.deepcopy(expected);calls=[]
        def call(value):calls.append(value);return copy.deepcopy(pages[value['sim_id']])
        with patch.object(cas_owner_decode,'read',side_effect=read):
            result=engine._verify_imported_owners(call,status,expected)
        self.assertTrue(result['ok']);self.assertEqual(len(result['owners']),8)
        self.assertTrue(result['pre_entry_fields_verified']);self.assertFalse(result['appearance_written'])
        self.assertEqual(expected,before);self.assertEqual({v['sim_id'] for v in calls},{'123','456'})
        self.assertTrue(all(v['operation']=='export-owner-page' for v in calls))

    def test_genetic_loss_on_any_named_owner_refuses_before_entry(self):
        status,expected,pages,decoded,read=self.fixture()
        decoded[b'456ghost/manifested']=dict(decoded[b'456ghost/manifested'],genetic_data=appearance.encode(b''))
        with patch.object(cas_owner_decode,'read',side_effect=read):
            with self.assertRaisesRegex(ValueError,'456/ghost/manifested: genetic_data'):
                engine._verify_imported_owners(lambda value:pages[value['sim_id']],status,expected)

    def test_other_process_generation_missing_owner_and_roster_cannot_pass(self):
        for change in ('pid','generation','missing-owner','roster','inactive'):
            with self.subTest(change=change):
                status,expected,pages,decoded,read=self.fixture()
                if change=='pid':pages['123']['pid']+=1
                elif change=='generation':pages['123']['generation']+=1
                elif change=='missing-owner':pages['123']['owners'].pop()
                elif change=='roster':status['members'].pop()
                else:status['selection_enabled']=False
                with patch.object(cas_owner_decode,'read',side_effect=read):
                    with self.assertRaises(ValueError):
                        engine._verify_imported_owners(lambda value:pages[value['sim_id']],status,expected)

    def return_fixture(self):
        status,expected,pages,decoded,read=self.fixture()
        for row in status['members']:row['native_view_fault']=False
        scope=dict(pid=os.getpid(),scope_id=status['scope_id'],epochs={'123':'c'*64,'456':'d'*64},owners={
            key:dict(native_kind=row['native_kind'],layout=cas_owner_decode.layout(row['fields'])) for key,row in expected.items()})
        return status,pages,read,scope

    def test_complete_return_keeps_named_raw_bytes_and_checkpoint_identity(self):
        status,pages,read,scope=self.return_fixture();calls=[]
        def call(module,dll,value):
            calls.append(value['operation'])
            return copy.deepcopy(status if value['operation']=='status' else pages[value['sim_id']])
        with patch.object(engine,'_LAYOUT_SCOPE',scope),patch.object(cas_owner_decode,'read',side_effect=read), \
                patch.object(overlay_loader,'native_cas_engine_control',side_effect=call), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
            result=engine.returned_owners(Obj(__file__='fixture'),Obj(id=123),'c'*64)
        self.assertEqual(calls,['status','export-owner-page','status']);self.assertEqual(len(result['owners']),4)
        self.assertEqual(result['checkpoint_epoch'],'c'*64);self.assertFalse(result['appearance_written'])
        ghost=next(row for row in result['owners'] if row['owner_id']=='ghost/manifested')
        self.assertEqual(bytes.fromhex(ghost['native_hex']),b'123ghost/manifested')
        self.assertEqual(ghost['fields']['physique'],appearance.encode('123ghost/manifested'))

    def test_stale_return_epoch_fault_or_changed_generation_never_publishes_partial_forms(self):
        for damage in ('epoch','pid','fault','generation','missing'):
            with self.subTest(damage=damage):
                status,pages,read,scope=self.return_fixture();calls=[]
                if damage=='pid':scope['pid']+=1
                if damage=='fault':status['members'][0]['native_view_fault']=True
                if damage=='missing':pages['123']['owners'].pop()
                def call(module,dll,value):
                    calls.append(value['operation']);result=copy.deepcopy(status if value['operation']=='status' else pages[value['sim_id']])
                    if damage=='generation' and len(calls)==3:result['members'][0]['graph_generation']+=1
                    return result
                with patch.object(engine,'_LAYOUT_SCOPE',scope),patch.object(cas_owner_decode,'read',side_effect=read), \
                        patch.object(overlay_loader,'native_cas_engine_control',side_effect=call), \
                        patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
                    with self.assertRaises(ValueError):
                        engine.returned_owners(Obj(__file__='fixture'),Obj(id=123),'e'*64 if damage=='epoch' else 'c'*64)


if __name__=='__main__':unittest.main()
