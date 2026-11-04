import copy
import hashlib
from types import SimpleNamespace as Obj
import sys
import unittest
from unittest.mock import patch
from apex_core import cas_owner_decode as decoder,form_appearance as appearance
from apex_core import native_cas_engine as engine


class OwnerDecodeTests(unittest.TestCase):
    def setUp(self):
        self.template=dict(__outfits__=appearance.encode(('protobuf',b'old outfits')),
            facial_attributes=appearance.encode(b'old face'),genetic_data=appearance.encode(b'old genetics'),
            pelt_layers=appearance.encode(b'old pelt'),parts_custom_tattoos=appearance.encode({7:99}),
            physique=appearance.encode('old shape'),skin_tone=appearance.encode(123),
            skin_tone_val_shift=appearance.encode(0.0),voice_pitch=appearance.encode(0.9),
            voice_actor=appearance.encode(12),voice_effect=appearance.encode(0),custom_texture=appearance.encode(0))
        types=dict(outfits=11,facial_attr=12,genetic_data=11,pelt_layers=11,parts_custom_tattoos=11,
            physique=9,skin_tone=4,skin_tone_val_shift=2,voice_pitch=2,voice_actor=13,voice_effect=4,custom_texture=4)
        self.message=Obj(DESCRIPTOR=Obj(full_name='EA.Sims4.Persistence.SimData',fields_by_name={
            name:Obj(type=kind,label=3 if name=='parts_custom_tattoos' else 1) for name,kind in types.items()}),
            sim_id=123,household_id=999,age=0,first_name='DTO construction default',
            outfits=Obj(SerializeToString=lambda:b'\xa0\x06\x7b'),facial_attr=b'new face\x00\xff',
            genetic_data=Obj(SerializeToString=lambda:b'\xa0\x06\x7c'),
            pelt_layers=Obj(SerializeToString=lambda:b'\xa0\x06\x7d'),
            parts_custom_tattoos=[Obj(body_type=7,texture_id=2**64-1),Obj(body_type=8,texture_id=100)],
            physique='new shape',skin_tone=2**64-1,skin_tone_val_shift=0.25,voice_pitch=0.625,
            voice_actor=2**32-1,voice_effect=2**64-1,custom_texture=2**64-1)

    def test_every_captured_field_is_decoded_without_gameplay_defaults(self):
        before=copy.deepcopy(self.template)
        result=decoder.from_message(self.message,self.template);values=appearance.payload(result)
        self.assertEqual(set(result),set(self.template));self.assertEqual(self.template,before)
        self.assertEqual(values['physique'],'new shape');self.assertEqual(values['skin_tone'],2**64-1)
        self.assertEqual(values['voice_actor'],2**32-1);self.assertEqual(values['voice_pitch'],0.625)
        self.assertEqual(values['__outfits__'],('protobuf',b'\xa0\x06\x7b'))
        self.assertEqual(values['genetic_data'],b'\xa0\x06\x7c')
        self.assertEqual(values['pelt_layers'],b'\xa0\x06\x7d')
        self.assertEqual(values['parts_custom_tattoos'],{7:2**64-1,8:100})
        self.assertNotIn('age',result);self.assertNotIn('first_name',result);self.assertNotIn('household_id',result)

    def test_format_cache_keeps_no_old_appearance_values(self):
        layout=decoder.layout(self.template)
        self.assertEqual(set(layout),set(self.template));self.assertEqual(layout['physique'],appearance.encode(''))
        self.assertEqual(layout['genetic_data'],appearance.encode(b''))
        values=appearance.payload(decoder.from_message(self.message,layout))
        self.assertEqual(values['physique'],'new shape');self.assertEqual(values['genetic_data'],b'\xa0\x06\x7c')
        self.assertNotIn('old shape',str(layout));self.assertNotIn('old genetics',str(layout))

    def test_installed_message_defaults_replace_old_values_instead_of_replaying_them(self):
        self.message.voice_pitch=0.0;self.message.parts_custom_tattoos=[]
        values=appearance.payload(decoder.from_message(self.message,self.template))
        self.assertEqual(values['voice_pitch'],0.0);self.assertEqual(values['parts_custom_tattoos'],{})

    def test_missing_field_or_wrong_wrapper_type_does_not_return_a_partial_owner(self):
        for damage in ('missing','repeated','wrong-bytes','no-outfits','other-message'):
            with self.subTest(damage=damage):
                message=copy.deepcopy(self.message);template=copy.deepcopy(self.template)
                if damage=='missing':del message.DESCRIPTOR.fields_by_name['voice_effect']
                elif damage=='repeated':message.DESCRIPTOR.fields_by_name['voice_effect'].label=3
                elif damage=='wrong-bytes':template['genetic_data']=appearance.encode('not bytes')
                elif damage=='no-outfits':del template['__outfits__']
                else:message.DESCRIPTOR.full_name='Other.Message'
                with self.assertRaises(ValueError):decoder.from_message(message,template)

    def test_duplicate_tattoo_nonfinite_and_out_of_range_values_refuse(self):
        for field,value in [('parts_custom_tattoos',[Obj(body_type=7,texture_id=1)]*2),
                            ('parts_custom_tattoos',[Obj(body_type=7.5,texture_id=1)]),
                            ('voice_pitch',float('nan')),('voice_pitch','bad'),('voice_actor',2**32),
                            ('skin_tone',-1),('voice_effect',True)]:
            with self.subTest(field=field,value=value):
                message=copy.deepcopy(self.message);setattr(message,field,value)
                with self.assertRaises(ValueError):decoder.from_message(message,self.template)

    def test_raw_unknown_bytes_are_retained_and_another_sim_is_never_decoded(self):
        raw=b'\x09'+(123).to_bytes(8,'little')+b'\xa2\x06\x06future'
        original=self.message
        class Factory:
            def __new__(cls):
                result=copy.deepcopy(original)
                result.ParseFromString=lambda value:None
                return result
        with patch.dict(sys.modules,{'protocolbuffers':Obj(FileSerialization_pb2=Obj(SimData=Factory))}):
            result=decoder.read(raw,'123',self.template)
            self.assertIs(result['native_bytes'],raw);self.assertEqual(result['native_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertFalse(result['appearance_written']);self.assertFalse(result['whole_sim_restore_authorized'])
            with self.assertRaises(ValueError):decoder.read(raw,'456',self.template)
        for value,sid in [(b'','123'),(b'x'*(512*1024+1),'123'),(raw,'0123'),(raw,str(2**64))]:
            with self.assertRaises(ValueError):decoder.read(value,sid,self.template)

    def page(self):
        raw=b'complete native DTO'
        return dict(ok=True,schema=1,scope='native-owner-export-page',pid=555,scope_id='a'*32,
            sim_id='123',generation=17,owned_mask=1,selected_owner_id='ghost/manifested',after_owner_id='',
            start_index=0,total_owners=1,owners=[dict(owner_id='ghost/manifested',native_kind=1,revision=3,
                linked_targets=[],native_hex=raw.hex(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())],
            complete=True,next_owner_id=None,appearance_written=False,model_harvested=False,
            game_files_written=False,native_patch_qualified=False,production_ready=False,source='committed-native-appearance')

    def test_matching_receiver_layout_decodes_page_without_granting_bank_authority(self):
        page=self.page();fields=decoder.from_message(self.message,self.template)
        scope=dict(pid=555,scope_id='a'*32,owners={('123','ghost/manifested'):dict(native_kind=1,layout=decoder.layout(self.template))})
        def read(raw,sid,layout):return dict(fields=fields,native_sha256=hashlib.sha256(raw).hexdigest())
        with patch.object(engine,'_LAYOUT_SCOPE',scope),patch.object(decoder,'read',side_effect=read):
            result=engine.reply(page,555)
        self.assertEqual(result['owner_appearance_query'],'returned-value')
        self.assertEqual(result['owner_appearances'][0]['fields'],fields)
        self.assertFalse(result['bank_commit_authorized']);self.assertFalse(result['appearance_written'])

    def test_stale_layout_or_decode_failure_retains_raw_page_and_discards_stale_decoded_fields(self):
        for stale in (True,False):
            with self.subTest(stale=stale):
                page=self.page();expected=copy.deepcopy(page['owners']);page['owner_appearances']=['stale fields']
                scope=dict(pid=556 if stale else 555,scope_id='a'*32,owners={
                    ('123','ghost/manifested'):dict(native_kind=1,layout=decoder.layout(self.template))})
                with patch.object(engine,'_LAYOUT_SCOPE',scope),patch.object(decoder,'read',side_effect=ValueError('schema changed')):
                    result=engine.reply(page,555)
                self.assertEqual(result['owner_appearance_query'],'unavailable' if stale else 'failed')
                self.assertEqual(result['owners'],expected);self.assertNotIn('owner_appearances',result)
                self.assertFalse(result['bank_commit_authorized'])


if __name__=='__main__':unittest.main()
