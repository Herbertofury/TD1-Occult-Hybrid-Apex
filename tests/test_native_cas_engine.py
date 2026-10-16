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
        self.arm = dict(operation='arm', scope_id='a'*32, members=[dict(sim_id='123', owned_mask=127)])
        self.status = dict(ok=True, pid=555, game_files_written=False, native_patch_qualified=False,
            production_ready=False, installed=True, armed=True, selection_enabled=False,
            members=[dict(sim_id='123', owned_mask=127, imported_mask=127, kinds=[1,2,4,8,16,32,64])])

    def test_complete_scope_status_and_explicit_activation_are_typed(self):
        for value in (self.arm, dict(operation='status'), dict(operation='activate', scope_id='a'*32)):
            engine.argument(value)
        self.assertEqual(engine.reply(self.status, 555), self.status)

    def test_bad_scope_ids_masks_duplicate_members_and_pointers_refuse(self):
        for sid in ('0', '01', '18446744073709551616', '１２３', 123, True):
            bad=copy.deepcopy(self.arm);bad['members'][0]['sim_id']=sid
            with self.subTest(sid=sid), self.assertRaises(ValueError):engine.argument(bad)
        for mask in (0,1,2,128,True,'127'):
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

    def test_full_owner_bytes_require_the_capture_digest_and_canonical_encoding(self):
        import hashlib
        raw=b'\1\2';seed=dict(operation='seed',scope_id='a'*32,sim_id='123',native_hex=raw.hex(),sha256=hashlib.sha256(raw).hexdigest())
        engine.argument(seed)
        for key,value in (('native_hex','010'),('native_hex','0A02'),('native_hex','zz'),('sha256','a'*64),('sim_id','0')):
            with self.subTest(key=key),self.assertRaises(ValueError):engine.argument(dict(seed,**{key:value}))

    def test_entry_supplies_complete_source_bytes_before_native_activation_without_disk_exports(self):
        import base64, hashlib
        from apex_core import overlay_loader, sim_data, form_appearance
        sims=[Obj(id=123,forms={1:Obj(id=1),2:Obj(id=2)}),Obj(id=456,forms={1:Obj(id=3),2:Obj(id=4)})]
        backend=Obj(__file__='matching-script',_form_map=lambda sim:sim.forms,
            services=Obj(active_household=lambda:Obj(sim_info_gen=lambda:iter(sims))))
        for sim in sims:sim.occult_tracker=sim
        status=dict(ok=True,armed=True,scope_id='a'*32,members=[dict(sim_id=str(s.id),owned_mask=3,imported_mask=0,kinds=[]) for s in sims])
        calls=[]
        def native(module, path, argument):
            engine.argument(argument);calls.append(argument['operation'])
            if argument['operation']=='seed':
                row=next(r for r in status['members'] if r['sim_id']==argument['sim_id'])
                row.update(imported_mask=3,kinds=[1,2])
            if argument['operation']=='activate':
                self.assertTrue(all(r['imported_mask']==3 for r in status['members']));status['selection_enabled']=True
            return copy.deepcopy(status)
        def capture(backend,sim):
            raw=str(sim.id).encode('ascii')
            return dict(native_base64=base64.b64encode(raw).decode('ascii'),native_sha256=hashlib.sha256(raw).hexdigest(),native_message_type='fixture.SimData')
        with patch.object(overlay_loader,'_CALLS',{'loaded':True}), \
                patch.object(overlay_loader,'native_cas_engine_control',side_effect=native), \
                patch.dict(sys.modules,{'paths':Obj(DLL_PATH='game-dlls')}), \
                patch.object(sim_data,'snapshot',side_effect=capture), \
                patch.object(form_appearance,'packed',side_effect=lambda backend,owner:{'skin_tone':form_appearance.encode(owner.id)}):
            result=engine.seed_members(backend)
        self.assertEqual(calls,['status','seed','seed','activate'])
        self.assertTrue(result['existing_appearances_unchanged']);self.assertEqual(len(result['members']),2)

    def test_unarmed_overlay_never_serializes_the_household(self):
        from apex_core import overlay_loader, sim_data
        with patch.object(overlay_loader,'_CALLS',None),patch.object(sim_data,'snapshot') as snapshot:
            self.assertEqual(engine.seed_members(Obj()),{'enabled':False});snapshot.assert_not_called()
