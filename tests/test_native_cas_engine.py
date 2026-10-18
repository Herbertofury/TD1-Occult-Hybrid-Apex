import copy
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import native_cas_engine as engine


class NativeEngineTests(unittest.TestCase):
    def setUp(self):
        scope=patch.object(engine,'_LAYOUT_SCOPE',None);scope.start();self.addCleanup(scope.stop)
        self.arm = dict(operation='arm', scope_id='a'*32, members=[dict(sim_id='123', owned_mask=127)])
        self.status = dict(ok=True, pid=555, game_files_written=False, native_patch_qualified=False,
            production_ready=False, installed=True, armed=True, selection_enabled=False,
            members=[dict(sim_id='123', owned_mask=127, imported_mask=127, kinds=[1,2,4,8,16,32,64])])

    def test_complete_scope_status_and_explicit_activation_are_typed(self):
        for value in (self.arm, dict(operation='status'), dict(operation='activate', scope_id='a'*32)):
            engine.argument(value)
        self.assertEqual(engine.reply(self.status, 555), self.status)

    def test_committed_native_exports_are_complete_and_bound_to_one_owner_generation(self):
        import hashlib
        raw=b'complete-native-appearance-with-opaque-fields'
        row=dict(schema=1,sim_id='123',owner_id='fairy/alternate',generation=7,native_kind=64,
            bytes=len(raw),native_hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest(),
            appearance_written=False,model_harvested=False,source='committed-native-appearance')
        status=copy.deepcopy(self.status)
        status['members'][0].update(graph_generation=7,separate_owners=[dict(owner_id='fairy/alternate',native_kind=64)])
        status['owner_export']=row
        engine.argument(dict(operation='export-owner',scope_id='a'*32,sim_id='123',owner_id='fairy/alternate',expected_generation=7))
        result=engine.reply(copy.deepcopy(status),555)
        self.assertEqual(result['owner_export']['native_hex'],raw.hex())
        for key,value in (('generation',8),('owner_id','alien/alternate'),('native_kind',2),
                          ('appearance_written',True),('model_harvested',True),('bytes',len(raw)-1),
                          ('native_hex',raw.hex().upper()),('sha256','a'*64)):
            broken=copy.deepcopy(status);broken['owner_export'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):engine.reply(broken,555)

    def test_available_native_descriptor_must_agree_with_exported_sim_identity(self):
        import hashlib
        from apex_core import sim_data
        raw=b'native-appearance'
        parsed=[]
        class Message:
            sim_id=123
            def ParseFromString(self,value):parsed.append(value)
        status=copy.deepcopy(self.status)
        status['members'][0].update(graph_generation=7,separate_owners=[dict(owner_id='native/2',native_kind=2)])
        status['owner_export']=dict(schema=1,sim_id='123',owner_id='native/2',generation=7,native_kind=2,
            bytes=len(raw),native_hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest(),
            appearance_written=False,model_harvested=False,source='committed-native-appearance')
        module=Obj(SimData=Message)
        with patch.dict(sys.modules,{'protocolbuffers':Obj(FileSerialization_pb2=module)}), \
             patch.object(sim_data,'catalog',return_value=dict(field_schemas={'all':True})):
            result=engine.reply(copy.deepcopy(status),555)
            self.assertEqual(result['owner_export_catalog_query'],'returned-value')
            self.assertEqual(parsed,[raw])
            self.assertEqual(result['owner_export_catalog']['field_schemas'],{'all':True})
            Message.sim_id=999
            with self.assertRaisesRegex(ValueError,'another Sim identity'):engine.reply(copy.deepcopy(status),555)

    def test_bad_scope_ids_masks_duplicate_members_and_pointers_refuse(self):
        for sid in ('0', '01', '18446744073709551616', '１２３', 123, True):
            bad=copy.deepcopy(self.arm);bad['members'][0]['sim_id']=sid
            with self.subTest(sid=sid), self.assertRaises(ValueError):engine.argument(bad)
        for mask in (0,2,128,True,'127'):
            bad=copy.deepcopy(self.arm);bad['members'][0]['owned_mask']=mask
            with self.subTest(mask=mask), self.assertRaises(ValueError):engine.argument(bad)
        bad=copy.deepcopy(self.arm);bad['members']*=2
        with self.assertRaises(ValueError):engine.argument(bad)
        with self.assertRaises(ValueError):engine.argument(dict(self.arm, address=0x140000000))

    def test_readiness_cannot_cover_only_part_of_the_forms_or_another_process(self):
        for key, value in (('pid',556),('pid',True),('production_ready',True),('native_patch_qualified',True),('game_files_written',True)):
            with self.subTest(key=key), self.assertRaises(ValueError):engine.reply(dict(self.status, **{key:value}),555)
        for key, value in (('kinds',[1,2,4]),('kinds',[1,2,4,8,16,32,32]),('imported_mask',3)):
            bad=copy.deepcopy(self.status);bad['members'][0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):engine.reply(bad,555)

    def test_incomplete_capture_is_reported_without_permission_to_switch(self):
        bad=copy.deepcopy(self.status);bad['members'][0].update(imported_mask=0,error='Missing Fairy')
        self.assertEqual(engine.reply(bad,555),bad)
        self.assertFalse(engine.selection_ready(None,'123',127,4))

    def test_complete_import_and_activation_do_not_qualify_the_old_conversion_route(self):
        from apex_core import overlay_loader
        status=copy.deepcopy(self.status)
        status.update(selection_enabled=True,selected_native=dict(available=True,sim_id='123'))
        with patch.object(overlay_loader,'native_cas_engine_control',return_value=status), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='fixture')}):
            self.assertFalse(engine.selection_ready(Obj(__file__='fixture'),'123',127,4))
            status.update(independent_owner_view_ready=True,selection_route='quarantined-kind-conversion')
            self.assertFalse(engine.selection_ready(Obj(__file__='fixture'),'123',127,4))

    def test_full_owner_bytes_require_the_capture_digest_and_canonical_encoding(self):
        import hashlib
        raw=b'\1\2';seed=dict(operation='seed',scope_id='a'*32,sim_id='123',native_hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest())
        engine.argument(seed)
        for key,value in (('native_hex','010'),('native_hex','0A02'),('native_hex','zz'),('sha256','a'*64),('sim_id','0')):
            with self.subTest(key=key),self.assertRaises(ValueError):engine.argument(dict(seed,**{key:value}))

    def test_entry_supplies_complete_source_bytes_before_native_activation_without_disk_exports(self):
        import base64, hashlib
        from apex_core import overlay_loader, sim_data, form_appearance, lifestate_forms,cas_owner_payload,cas_bank_transaction
        sims=[Obj(id=123,forms={1:Obj(id=1),2:Obj(id=2)}),Obj(id=456,forms={1:Obj(id=3),2:Obj(id=4)})]
        backend=Obj(__file__='matching-script',_form_map=lambda sim:sim.forms,_get_current_flags=lambda sim:2,
            services=Obj(active_household=lambda:Obj(sim_info_gen=lambda:iter(sims))))
        for sim in sims:sim.occult_tracker=sim
        status=dict(ok=True,armed=True,scope_id='a'*32,members=[dict(sim_id=str(s.id),owned_mask=3,imported_mask=0,kinds=[]) for s in sims])
        calls=[]
        def native(module, path, argument):
            engine.argument(argument);calls.append(argument['operation'])
            if argument['operation']=='seed':
                row=next(r for r in status['members'] if r['sim_id']==argument['sim_id'])
                row.update(imported_mask=3,kinds=[1,2])
            if argument['operation']=='seed-active':
                row=next(r for r in status['members'] if r['sim_id']==argument['sim_id'])
                row['active_entry_source_seeded']=True
            if argument['operation']=='seed-canonical':
                row=next(r for r in status['members'] if r['sim_id']==argument['sim_id'])
                row['canonical_source_seeded_mask']=row.get('canonical_source_seeded_mask',0)|argument['native_kind']
            if argument['operation']=='activate':
                self.assertTrue(all(r['imported_mask']==3 for r in status['members']));status['selection_enabled']=True
                for row in status['members']:
                    row.update(logical_owner_ids={'1':'native/1','2':'active/2'},human_owner_id='native/1')
            return copy.deepcopy(status)
        def capture(backend,sim):
            raw=str(sim.id).encode('ascii')
            return dict(native_base64=base64.b64encode(raw).decode('ascii'),native_sha256=hashlib.sha256(raw).hexdigest(),native_message_type='fixture.SimData')
        with patch.object(engine,'_verify_imported_owners',return_value=dict(ok=True,owners=[])), \
                patch.object(cas_bank_transaction,'status',side_effect=lambda backend,sim:
                    dict(phase='captured',expected_pending_sha256=('a' if sim.id==123 else 'b')*64)), \
                patch.object(overlay_loader,'_CALLS',{'loaded':True}), \
                patch.object(overlay_loader,'native_cas_engine_control',side_effect=native), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='game-dlls')}), \
                patch.object(sim_data,'snapshot',side_effect=capture), \
                patch.object(lifestate_forms,'native_cas_owners',return_value=[]), \
                patch.object(cas_owner_payload,'project_record',return_value=dict(native_hex='0102',sha256=hashlib.sha256(b'\1\2').hexdigest())), \
                patch.object(form_appearance,'packed',side_effect=lambda backend,owner:{
                    'skin_tone':form_appearance.encode(owner.id),
                    '__outfits__':form_appearance.encode(('protobuf',b'\xa0\x06\x01'))}):
            result=engine.seed_members(backend)
        self.assertEqual(calls,['status','seed','seed-canonical','seed-canonical','seed-active',
                               'seed','seed-canonical','seed-canonical','seed-active','activate'])
        self.assertTrue(result['existing_appearances_unchanged']);self.assertEqual(len(result['members']),2)
        self.assertEqual(engine._LAYOUT_SCOPE['epochs'],{'123':'a'*64,'456':'b'*64})

    def test_unarmed_overlay_never_serializes_the_household(self):
        from apex_core import overlay_loader, sim_data
        with patch.object(overlay_loader,'_CALLS',None),patch.object(sim_data,'snapshot') as snapshot:
            self.assertEqual(engine.seed_members(Obj()),{'enabled':False});snapshot.assert_not_called()
