from pathlib import Path
import struct
import sys
import unittest
import tempfile
import json
import hashlib
from types import SimpleNamespace as Obj
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import household_io
from apex_core import form_appearance as appearance


def varint(n):
    result=bytearray()
    while n>127:result.append((n&127)|128);n>>=7
    result.append(n);return bytes(result)


def blob(n,value):return varint((n<<3)|2)+varint(len(value))+value


class HouseholdIOTests(unittest.TestCase):
    def test_complete_multisim_bytes_and_unknown_fields_survive_native_envelope_read(self):
        sims=[b'\x09'+struct.pack('<Q',id)+blob(500,b'future') for id in (11,12,13)]
        payload=blob(1,blob(3,b'Hybrid household')+b''.join(blob(6,s) for s in sims)+blob(501,b'future family'))
        for version in (1,2):
            raw=struct.pack('<I',version)+(struct.pack('<II',0,len(payload))+payload+b'footer' if version==2 else payload)
            raw=raw[:4]+struct.pack('<I',len(raw))+raw[4:]
            self.assertEqual(household_io.tray_sims(raw),sims)
            with self.assertRaises(ValueError):household_io.tray_sims(raw[:-1])

    def test_unknown_or_ambiguous_source_is_rejected_before_native_creation(self):
        for payload in (blob(1,b''),blob(1,blob(6,b'one'))+blob(1,blob(6,b'two'))):
            raw=struct.pack('<IIII',2,len(payload)+12,0,len(payload))+payload
            with self.assertRaises(ValueError):household_io.tray_sims(raw)

    def test_native_household_membership_requires_explicit_current_save_and_household(self):
        household=Obj(id=77)
        backend=Obj(services=Obj(active_household=lambda:household,get_persistence_service=lambda:Obj(get_save_slot_proto_guid=lambda:88)))
        self.assertIs(household_io.context(backend,dict(household_id='77',save_guid='88')),household)
        for request in ({},dict(household_id='78',save_guid='88'),dict(household_id='77',save_guid='89')):
            with self.assertRaises(ValueError):household_io.context(backend,request)

    def test_identity_remap_never_rewrites_a_coincident_outfit_or_resource_id(self):
        fields=[(Obj(name='sim_id',type=6,label=1),11),(Obj(name='outfit_id',type=4,label=1),11),
            (Obj(name='sim_ids',type=4,label=3),[11,12,99])]
        message=Obj(sim_id=11,outfit_id=11,sim_ids=fields[2][1],ListFields=lambda:fields)
        household_io._remap(message,{11:21,12:22})
        self.assertEqual(message.sim_id,21);self.assertEqual(message.outfit_id,11)
        self.assertEqual(message.sim_ids,[21,22,99])

    def test_loaded_clone_requires_base_appearance_stored_inventory_and_membership(self):
        raw=blob(1,b'\x08\x01\x10\x00')
        owner=Obj(skin_tone=100,flags=9)
        tracker=Obj(occult_types=3,current_occult_types=2,occult_sim_infos=[Obj(occult_type=1),Obj(occult_type=2)])
        proto=Obj(DESCRIPTOR=Obj(fields_by_name={'skin_tone':Obj()}),skin_tone=100,flags=9,
                  outfits=Obj(SerializeToString=lambda:raw),attributes=Obj(occult_tracker=tracker))
        observed=dict(skin_tone=appearance.encode(100),__outfits__=appearance.encode(('protobuf',raw)))
        mapping={1:Obj(),2:Obj()}
        backend=Obj(_form_map=lambda tracker:mapping,_coerce_flags=lambda flag:flag,
                    _get_occult_flags=lambda sim:3,_get_current_flags=lambda sim:2)
        owner.occult_tracker=Obj()
        with patch.object(appearance,'packed',return_value=observed),patch.object(household_io.hybrid_persistence,'_stored_core') as stored:
            household_io.validate_loaded(backend,owner,proto)
            self.assertEqual(stored.call_count,2)
            proto.skin_tone=101
            with self.assertRaisesRegex(ValueError,'base appearance'):household_io.validate_loaded(backend,owner,proto)
            proto.skin_tone=100;mapping.pop(2)
            with self.assertRaisesRegex(ValueError,'owner inventory'):household_io.validate_loaded(backend,owner,proto)

    def test_relationship_target_remap_is_scoped_and_leaves_resource_targets_exact(self):
        descriptor=Obj(name='target_id',type=4,label=1)
        relationship=Obj(target_id=11,ListFields=lambda:[(descriptor,11)])
        household_io._remap(relationship,{11:21},('attributes','relationship_tracker','relationships'))
        self.assertEqual(relationship.target_id,21)
        resource=Obj(target_id=11,ListFields=lambda:[(descriptor,11)])
        household_io._remap(resource,{11:21},('custom_texture',))
        self.assertEqual(resource.target_id,11)

    def test_base_native_facial_attr_is_validated_as_readable_facial_attributes(self):
        raw=blob(1,b'\x08\x01\x10\x00')
        owner=Obj(flags=9,occult_tracker=Obj(),id=77)
        tracker=Obj(occult_types=1,current_occult_types=1,occult_sim_infos=[])
        proto=Obj(DESCRIPTOR=Obj(fields_by_name={'facial_attr':Obj()}),facial_attr=b'source morphs',flags=9,
            outfits=Obj(SerializeToString=lambda:raw),attributes=Obj(occult_tracker=tracker))
        observed=dict(facial_attributes=appearance.encode(b'corrupted morphs'),__outfits__=appearance.encode(('protobuf',raw)))
        backend=Obj(_form_map=lambda tracker:{},_get_occult_flags=lambda sim:1,_get_current_flags=lambda sim:1)
        with patch.object(appearance,'packed',return_value=observed):
            with self.assertRaisesRegex(ValueError,'facial_attributes'):household_io.validate_loaded(backend,owner,proto)

    def test_native_clone_source_restores_distinct_stored_fields_after_outfit_generation(self):
        raw=blob(1,b'\x08\x01\x10\x01')+blob(1,b'\x08\x02\x10\x00')
        from apex_core.outfit_snapshot import normalize
        native_order=normalize(raw)
        sim=Obj(id=77,flags=9,occult_tracker=Obj(),skin_tone=100,facial_attributes=b'active',_base=Obj(occult_types=3,current_occult_types=1))
        stored=Obj(flags=10,skin_tone=200,facial_attributes=b'native damaged',_base=Obj(occult_types=3,current_occult_types=2))
        row=Obj(occult_type=2,flags=10)
        tracker=Obj(occult_types=3,current_occult_types=1,occult_sim_infos=[row])
        proto=Obj(DESCRIPTOR=Obj(fields_by_name={'skin_tone':Obj(),'facial_attr':Obj()}),skin_tone=100,facial_attr=b'active',flags=9,
            outfits=Obj(SerializeToString=lambda:raw),attributes=Obj(occult_tracker=tracker))
        expected=dict(skin_tone=appearance.encode(200),facial_attributes=appearance.encode(b'stored independent'),__outfits__=appearance.encode(('protobuf',raw)))
        writes=[]
        def capture(backend,owner):return dict(skin_tone=appearance.encode(owner.skin_tone),facial_attributes=appearance.encode(owner.facial_attributes),__outfits__=appearance.encode(('protobuf',native_order)))
        def restore(owner,values):
            writes.append((owner,values))
            for name,value in values.items():setattr(owner,name,value)
        def validate(*args):
            if stored.facial_attributes!=b'stored independent':raise ValueError('Stored genetics changed.')
        # Clone test uses only Alien owner inventory; the active kind must
        # identify a stored native owner for a real context write.
        tracker.current_occult_types=2;sim._base.current_occult_types=2
        backend=Obj(_form_map=lambda tracker:{2:stored},_coerce_flags=lambda flag:flag,_restore_siminfo_payload=restore,
            _get_occult_flags=lambda sim:3,_get_current_flags=lambda sim:2,
            _set_flags=lambda *a:self.fail('Matching native context must not be rebuilt.'))
        with patch.object(appearance,'packed',side_effect=capture),patch.object(household_io.hybrid_persistence,'_record_payload',return_value=expected),patch.object(household_io,'validate_loaded',side_effect=validate):
            household_io.restore_clone_appearance(backend,sim,proto)
        self.assertEqual(writes,[(stored,{'facial_attributes':b'stored independent'})])
        self.assertEqual(sim.facial_attributes,b'active')

    def test_clone_alias_and_unrestorable_readback_never_pass(self):
        sim=Obj(id=77,flags=9,occult_tracker=Obj(),_base=Obj())
        row=Obj(occult_type=2,flags=9)
        tracker=Obj(occult_types=3,current_occult_types=1,occult_sim_infos=[row])
        proto=Obj(DESCRIPTOR=Obj(fields_by_name={}),flags=9,outfits=Obj(SerializeToString=lambda:blob(1,b'\x08\x01\x10\x00')),attributes=Obj(occult_tracker=tracker))
        backend=Obj(_form_map=lambda tracker:{2:sim},_restore_siminfo_payload=lambda *a:self.fail('Aliased clone must not be written.'))
        with self.assertRaisesRegex(ValueError,'alias'):household_io.restore_clone_appearance(backend,sim,proto)
        stored=Obj(flags=9,_base=Obj());backend._form_map=lambda tracker:{2:stored}
        backend._coerce_flags=lambda flag:flag;backend._set_flags=lambda *a:None
        backend._get_occult_flags=lambda sim:3;backend._get_current_flags=lambda sim:1
        snapshot=dict(__outfits__=appearance.encode(('protobuf',proto.outfits.SerializeToString())))
        with patch.object(appearance,'packed',return_value=snapshot),patch.object(household_io.hybrid_persistence,'_record_payload',return_value=snapshot),patch.object(household_io,'validate_loaded',side_effect=ValueError('unknown genetics lost')):
            with self.assertRaisesRegex(ValueError,'unknown genetics lost'):household_io.restore_clone_appearance(backend,sim,proto)

    def test_failed_import_recovery_requires_absent_allocations_and_keeps_exact_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'household_tray_import.json'
            raw=json.dumps(dict(stage='recovery-required',household_id='77',save_guid='88',original_members=['11'],
                identity_map={'99':'22'},source_sims=['retained native source'],created=['22'])).encode()
            path.write_bytes(raw);digest=hashlib.sha256(raw).hexdigest()
            household=Obj(id=77,sim_info_gen=lambda:iter([Obj(id=11)]))
            native={22:Obj()};buffers={}
            backend=Obj(_data_directory=lambda:temporary,services=Obj(active_household=lambda:household,
                sim_info_manager=lambda:Obj(get=native.get),get_persistence_service=lambda:Obj(get_save_slot_proto_guid=lambda:88,get_sim_proto_buff=buffers.get)))
            request=dict(household_id='77',save_guid='88',journal_sha256=digest)
            with self.assertRaisesRegex(ValueError,'allocations still exist'):household_io.recover_import(backend,request)
            self.assertEqual(path.read_bytes(),raw)
            native.clear();buffers[22]=Obj()
            with self.assertRaisesRegex(ValueError,'allocations still exist'):household_io.recover_import(backend,request)
            buffers.clear()
            with self.assertRaisesRegex(ValueError,'journal changed'):household_io.recover_import(backend,dict(request,journal_sha256='0'*64))
            result=household_io.recover_import(backend,request)
            self.assertTrue(result['ok']);self.assertFalse(result['sim_removed']);self.assertFalse(result['import_replayed'])
            recovered=json.loads(path.read_text());self.assertEqual(Path(recovered['archived_journal']).read_bytes(),raw)
            self.assertEqual(recovered['archived_sha256'],digest)

    def test_native_self_registration_is_admitted_but_another_object_never_is(self):
        sim=Obj(id=22);objects={22:sim};calls=[]
        def add(owner):calls.append(owner);objects[owner.id]=owner
        manager=Obj(get=objects.get,add=add)
        household_io.register_clone(manager,sim);self.assertEqual(calls,[])
        objects.clear();household_io.register_clone(manager,sim);self.assertEqual(calls,[sim])
        objects[22]=Obj(id=22)
        with self.assertRaisesRegex(ValueError,'another object'):household_io.register_clone(manager,sim)
        self.assertEqual(calls,[sim])

    def test_queued_spawn_remains_pending_until_unpause_then_completes_without_recreation(self):
        import base64,os
        with tempfile.TemporaryDirectory() as temporary:
            ready={'instance':False,'persistence':False}
            sim=Obj(id=11,get_sim_instance=lambda:Obj() if ready['instance'] else None)
            household=Obj(id=77,account=Obj(id=1),sim_info_gen=lambda:iter([Obj(id=1),sim]))
            backend=Obj(_data_directory=lambda:temporary,services=Obj(active_household=lambda:household,
                sim_info_manager=lambda:Obj(get=lambda sid:sim if sid==11 else None),
                get_persistence_service=lambda:Obj(get_save_slot_proto_guid=lambda:88)))
            class Proto:
                def ParseFromString(self,raw):self.sim_id=9 if raw==b'native' else 10;self.household_id=77;self.attributes=Obj(occult_tracker=Obj(current_occult_types=1))
                def ListFields(self):return [(Obj(name='sim_id',type=6,label=1),self.sim_id)]
            path=Path(temporary)/'household_tray_import.json'
            proof=dict(stage='awaiting-spawn',runtime_pid=os.getpid(),household_id='77',save_guid='88',
                original_members=['1'],created=['11'],identity_map={'9':'11'},source_sims=[base64.b64encode(b'native').decode()],
                native_contexts={'11':{'active':{'available':3,'current':1},'1':{'available':3,'current':1},'2':{'available':3,'current':2}}})
            path.write_text(json.dumps(proof));raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
            request=dict(household_id='77',save_guid='88',journal_sha256=digest)
            from apex_core import test_driver
            modules={'protocolbuffers':Obj(FileSerialization_pb2=Obj(SimData=Proto))}
            context=proof['native_contexts']['11']
            narrowed={k:dict(v,available=1) for k,v in context.items()}
            with patch.dict(sys.modules,modules),patch.object(test_driver,'persistence_evidence',side_effect=lambda *a:{'persistence_verified_before_save':ready['persistence']}),patch.object(household_io,'validate_loaded') as validate,patch.object(household_io.native_occult_context,'capture',return_value=narrowed),patch.object(household_io.native_occult_context,'restore',return_value={'after':context}) as restore:
                result=household_io.finish_import(backend,request)
                self.assertTrue(result['pending']);self.assertTrue(result['unpause_required']);self.assertEqual(path.read_bytes(),raw)
                ready['instance']=True
                self.assertTrue(household_io.finish_import(backend,request)['pending']);validate.assert_not_called()
                ready['persistence']=True
                result=household_io.finish_import(backend,request)
                self.assertFalse(result['pending']);self.assertTrue(result['native_instances_verified']);validate.assert_called_once()
                self.assertFalse(result['creation_replayed']);self.assertEqual(result['created_sim_ids'],['11'])
                restore.assert_called_once_with(backend,sim,context)
                self.assertEqual(json.loads(path.read_text())['context_restores'][0]['receipt']['after'],context)
                with self.assertRaises(ValueError):household_io.finish_import(backend,request)
                # First actor can finish context restoration while the second
                # is still queued. Return the updated WAL hash, not the older
                # request hash, so one later observation needs no recreation.
                second=Obj(id=12,get_sim_instance=lambda:None)
                household.sim_info_gen=lambda:iter([Obj(id=1),sim,second])
                backend.services.sim_info_manager=lambda:Obj(get={11:sim,12:second}.get)
                proof['created'].append('12');proof['identity_map']['10']='12'
                proof['source_sims'].append(base64.b64encode(b'second').decode())
                proof['native_contexts']['12']=context
                path.write_text(json.dumps(proof));old_hash=hashlib.sha256(path.read_bytes()).hexdigest()
                pending=household_io.finish_import(backend,dict(request,journal_sha256=old_hash))
                self.assertTrue(pending['pending']);self.assertNotEqual(pending['journal_sha256'],old_hash)
                self.assertEqual(pending['journal_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
