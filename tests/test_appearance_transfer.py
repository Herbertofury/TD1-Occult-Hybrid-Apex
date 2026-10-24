from pathlib import Path
import base64
import copy
import hashlib
import json
import sys
import unittest
from types import SimpleNamespace as Obj
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import appearance_transfer as transfer, form_appearance as appearance
import test_studio as fixture
from test_studio import Message as BaseMessage, OutfitRecords


class Record(Obj):
    def CopyFrom(self, other):
        self.__dict__.clear(); self.__dict__.update(copy.deepcopy(other.__dict__))


class Message(BaseMessage):
    def __init__(self, raw):
        super().__init__(raw)
        self.outfits = OutfitRecords(Record(**item.__dict__) for item in self.outfits)


class TransferTests(unittest.TestCase):
    def setUp(self):
        transfer._CLIPS.clear(); transfer._UPLOADS.clear()
        self.fixture = fixture.StudioTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.backend = self.fixture.backend; self.backend._studio_parse_snapshot = Message
        self.target = appearance.packed(self.backend, self.fixture.sim)
        self.source = copy.deepcopy(self.target); self.source['skin_tone'] = appearance.encode(500)
        src = Message(appearance.decode(self.source['__outfits__'])[1]); src.outfits[0].parts.ids[1] = 123456
        self.source['__outfits__'] = appearance.encode(('protobuf', src.SerializeToString()))
        self.choice = dict(fields=[], outfits='one', source_outfit=0, target_outfit=1, body_types=[2])

    def test_only_selected_categories_preserve_all_other_rows_arrays_fields_and_numbered_outfits(self):
        result = transfer.merge(self.backend, self.target, self.source, self.choice)
        self.assertEqual({k:v for k,v in result.items() if k!='__outfits__'}, {k:v for k,v in self.target.items() if k!='__outfits__'})
        before, after = Message(appearance.decode(self.target['__outfits__'])[1]), Message(appearance.decode(result['__outfits__'])[1])
        self.assertEqual(after.outfits[0].parts.ids, before.outfits[0].parts.ids)
        self.assertEqual(after.outfits[1].parts.ids, [999,123456])
        self.assertEqual(after.outfits[1].object_ids.object_id, [3,4])
        self.assertEqual(after.outfits[1].layer_ids.layer_id, [5,6])
        self.assertEqual(after.outfits[1].part_shifts.color_shift, [0,19])
        self.assertEqual(after.outfits[1].outfit_id, before.outfits[1].outfit_id)

    def test_whole_outfit_keeps_destination_identity_category_and_other_outfits(self):
        result = transfer.merge(self.backend, self.target, self.source, dict(self.choice, body_types=[]))
        after = Message(appearance.decode(result['__outfits__'])[1])
        self.assertEqual((after.outfits[1].outfit_id,after.outfits[1].category), (2,1))
        self.assertEqual(after.outfits[1].parts.ids,[999,123456])

    def test_missing_skin_detail_enters_native_category_order_without_reordering_unselected_parts(self):
        dst=Message(appearance.decode(self.target['__outfits__'])[1]);dst.outfits[1].body_types_list.body_types[:]=[7,115]
        src=Message(appearance.decode(self.source['__outfits__'])[1]);src.outfits[0].body_types_list.body_types[1]=38
        target=dict(self.target,__outfits__=appearance.encode(('protobuf',dst.SerializeToString())))
        source=dict(self.source,__outfits__=appearance.encode(('protobuf',src.SerializeToString())))
        after=Message(appearance.decode(transfer.merge(self.backend,target,source,dict(self.choice,body_types=[38]))['__outfits__'])[1]).outfits[1]
        self.assertEqual(after.body_types_list.body_types,[7,38,115])
        self.assertEqual(after.parts.ids,[999,123456,888])
        self.assertEqual(after.object_ids.object_id,[3,4,4]);self.assertEqual(after.part_shifts.color_shift,[0,19,19])

    def test_field_only_skin_paste_does_not_touch_outfits_or_physique(self):
        result=transfer.merge(self.backend,self.target,self.source,dict(self.choice,fields=['skin_tone'],outfits='none',body_types=[]))
        self.assertEqual(result,dict(self.target,skin_tone=appearance.encode(500)))

    def test_empty_requested_source_category_removes_only_that_destination_slot(self):
        src=Message(appearance.decode(self.source['__outfits__'])[1]);src.outfits[0].body_types_list.body_types[1]=35
        source=dict(self.source,__outfits__=appearance.encode(('protobuf',src.SerializeToString())))
        result=transfer.merge(self.backend,self.target,source,self.choice)
        self.assertEqual(Message(appearance.decode(result['__outfits__'])[1]).outfits[1].parts.ids,[999])

    def test_whole_wardrobe_retains_existing_destination_outfit_ids(self):
        result=transfer.merge(self.backend,self.target,self.source,dict(self.choice,outfits='all',body_types=[]))
        after=Message(appearance.decode(result['__outfits__'])[1]);self.assertEqual([o.outfit_id for o in after.outfits],[1,2])

    def test_unknown_fields_gameplay_and_untyped_selectors_are_rejected_before_mutation(self):
        for choice in (dict(self.choice,fields=['occult_types']),dict(self.choice,source_outfit=True),dict(self.choice,body_types=[True]),dict(self.choice,fields=[{}]),dict(self.choice,outfits='all')):
            with self.subTest(choice=choice),self.assertRaises(ValueError):transfer.merge(self.backend,self.target,self.source,choice)
        self.assertEqual(appearance.packed(self.backend,self.fixture.sim),self.target)

    def test_clipboard_is_an_immutable_bounded_copy_with_exact_identity(self):
        clip=transfer.capture(self.source,dict(kind='sim',sim_id='1234',form=2,label='Alien'))
        self.source['skin_tone']=appearance.encode(999)
        self.assertEqual(transfer.get(clip['id'],clip['sha256'])['fields']['skin_tone'],appearance.encode(500))
        with self.assertRaises(ValueError):transfer.get(clip['id'],'0'*64)
        for _ in range(8):transfer.capture(self.target,dict(kind='sim',sim_id='1234',form=1,label='Human'))
        with self.assertRaises(ValueError):transfer.get(clip['id'],clip['sha256'])

    def test_import_staging_validates_complete_hash_and_rejects_duplicate_chunks(self):
        raw=transfer.canonical(dict(fields=self.source,source=dict(kind='tray',sim_id='1234',form=2,label='Tray Alien')))
        begin=transfer.upload('begin',dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        req=dict(upload_id=begin['upload_id'],index=0,data=base64.b64encode(raw[:30]).decode())
        transfer.upload('chunk',req)
        with self.assertRaises(ValueError):transfer.upload('chunk',req)
        with self.assertRaises(ValueError):transfer.upload('finish',dict(upload_id=begin['upload_id']))
        for index,pos in enumerate(range(30,len(raw),3072),1):transfer.upload('chunk',dict(upload_id=begin['upload_id'],index=index,data=base64.b64encode(raw[pos:pos+3072]).decode()))
        result=transfer.upload('finish',dict(upload_id=begin['upload_id']));self.assertEqual(result['fields'],self.source)
        self.assertEqual(appearance.packed(self.backend,self.fixture.sim),self.target)

    def test_generated_wardrobe_preview_reports_detached_ids_and_keeps_all_sim_fields_unchanged(self):
        from unittest.mock import patch
        from apex_core import studio
        generated=Message(appearance.decode(self.source['__outfits__'])[1]);generated.outfits[0].outfit_id=990
        fields=dict(self.source,__outfits__=appearance.encode(('protobuf',generated.SerializeToString())))
        status=studio.dispatch(self.backend,'studio_status','1234',None)
        with patch('apex_core.werewolf_defaults.prepare',return_value=fields),patch('apex_core.human_werewolf.preview_form',return_value=32):
            pending=studio.dispatch(self.backend,'studio_werewolf_ea_preview','1234',None)
        self.assertEqual(pending['preview_outfit_inventory'][0]['outfit_id'],'990')
        self.assertEqual(appearance.packed(self.backend,self.fixture.sim),self.target)
        current=studio.dispatch(self.backend,'studio_status','1234',None)
        self.assertEqual(current['outfit_inventory'][0]['outfit_id'],'1')
        self.assertEqual(current['preview_outfit_inventory'][0]['outfit_id'],'990')

    def test_complete_studio_upload_publishes_real_destination_history_and_no_sim_changes(self):
        from unittest.mock import patch
        from apex_core import studio
        raw=transfer.canonical(dict(fields=self.source,source=dict(kind='tray',sim_id='7777',form=2,label='Tray Alien')))
        with patch.object(studio,'ChangeJournal',wraps=studio.ChangeJournal) as journals:
            begin=self.fixture.request('studio_clipboard_begin',json.dumps(dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())))
            for index,pos in enumerate(range(0,len(raw),3072)):
                self.fixture.request('studio_clipboard_chunk',json.dumps(dict(upload_id=begin['upload_id'],index=index,data=base64.b64encode(raw[pos:pos+3072]).decode())))
            self.assertEqual(journals.call_count,0,'Transport chunks opened full appearance history.')
            result=self.fixture.request('studio_clipboard_finish',json.dumps(dict(upload_id=begin['upload_id'])))
            self.assertEqual(journals.call_count,1)
        self.assertTrue(result['ok']);self.assertIn('history_nodes',result)
        self.assertEqual(result['inspected_form_flags'],32)
        self.assertEqual(result['appearance_clipboard']['source']['sim_id'],'7777')
        self.assertEqual(result['clipboard_outfits'][0]['parts'][1]['cas_part_id'],'123456')
        self.assertEqual(transfer.get(result['appearance_clipboard']['id'],result['appearance_clipboard']['sha256'])['fields'],self.source)
        self.assertEqual(appearance.packed(self.backend,self.fixture.sim),self.target)

    def test_inactive_cross_form_paste_apply_and_undo_preserve_live_owner(self):
        f=self.fixture
        source=Message(f.sim.raw);source.outfits[0].parts.ids[1]=123456;f.sim.raw=source.SerializeToString()
        copy_reply=f.request('studio_copy_appearance');clip=copy_reply['appearance_clipboard']
        status=f.stored_form();original=appearance.packed(f.backend,f.vampire);active=appearance.packed(f.backend,f.sim)
        request=dict(clipboard_id=clip['id'],clipboard_sha256=clip['sha256'],selection=self.choice,
                     lane=status['history_lane'],appearance_sha256=status['appearance_sha256'])
        preview=f.stored_request('studio_paste_preview',json.dumps(request))
        self.assertEqual(appearance.packed(f.backend,f.vampire),original)
        f.stored_request('studio_apply',preview['preview_id'])
        self.assertEqual(Message(f.vampire.raw).outfits[1].parts.ids[1],123456)
        f.stored_request('studio_apply',f.stored_request('studio_undo')['preview_id'])
        self.assertEqual(appearance.packed(f.backend,f.vampire),original)
        self.assertEqual(appearance.packed(f.backend,f.sim),active)

    def test_stale_destination_paste_is_refused_without_a_pending_change(self):
        f=self.fixture;copy_reply=f.request('studio_copy_appearance');clip=copy_reply['appearance_clipboard'];status=f.request('studio_status')
        request=dict(clipboard_id=clip['id'],clipboard_sha256=clip['sha256'],selection=self.choice,
            lane=status['history_lane'],appearance_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'destination changed'):f.request('studio_paste_preview',json.dumps(request))
        self.assertEqual(appearance.packed(f.backend,f.sim),self.target)


if __name__=='__main__':unittest.main()
