import copy
import json
from pathlib import Path
import struct
import sys
import unittest
import hashlib
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import morph_controls as morph, form_appearance as appearance
import test_studio as fixtures


def modifier(key=123, amount=.25, extra=b'\x4a\x03xyz'):
    return b'\x08'+morph.encoded_varint(key)+(b'\x15'+struct.pack('<f',amount) if amount is not None else b'')+extra


def group(number, payload):
    return morph.encoded_varint((number<<3)|2)+morph.encoded_varint(len(payload))+payload


class MorphTests(unittest.TestCase):
    def test_base_body_edit_updates_only_same_genetic_key_preventing_native_aged_relocation(self):
        fields=self.fields()
        base=group(2,modifier(999,.75))+group(3,modifier(123,.5))+group(5,modifier(999,.2))+b'\xba\x06\x03new'
        gene=group(1,base)+b'\x12\x03fat'+b'\x42\x03ccx'
        fields['genetic_data']=appearance.encode(gene)
        after=morph.replace(fields,self.request(fields,group=3,before=.5))
        chunks=morph.chunks(appearance.decode(after['genetic_data']))
        self.assertEqual([c[3] for c in chunks if c[0]!=1],[b'\x12\x03fat',b'\x42\x03ccx'])
        rows=morph.inspect(dict(facial_attributes=appearance.encode(chunks[0][2])))
        self.assertEqual([r['value'] for r in rows],[.75,.625,struct.unpack('<f',struct.pack('<f',.2))[0]])
        self.assertEqual([r['group'] for r in rows],[2,3,5])
        self.assertTrue(chunks[0][2].endswith(b'\xba\x06\x03new'))
    def test_aged_modifier_edit_keeps_genetic_base_byte_exact(self):
        fields=self.fields();fields['genetic_data']=appearance.encode(group(1,group(2,modifier(123,.25))))
        after=morph.replace(fields,self.request(fields,group=4,before=.75))
        self.assertEqual(after['genetic_data'],fields['genetic_data'])
    def test_new_base_modifier_is_added_to_same_owner_genetic_blob_without_copying_unrelated_sculpts(self):
        fields=self.fields();fields['genetic_data']=appearance.encode(b'\x42\x03ccx')
        after=morph.add(fields,3,'999',.375)
        raw=appearance.decode(after['genetic_data']);self.assertTrue(raw.startswith(b'\x42\x03ccx'))
        child=[c[2] for c in morph.chunks(raw) if c[0]==1][0]
        rows=morph.inspect(dict(facial_attributes=appearance.encode(child)))
        self.assertEqual([(r['group'],r['key'],r['value']) for r in rows],[(3,'999',.375)])
    def test_duplicate_genetic_key_refuses_before_altering_either_packet(self):
        fields=self.fields();fields['genetic_data']=appearance.encode(group(1,group(3,modifier(123,.5))+group(3,modifier(123,.6))))
        before=copy.deepcopy(fields)
        with self.assertRaisesRegex(ValueError,'Duplicate genetic'):morph.replace(fields,self.request(fields,group=3,before=.5))
        self.assertEqual(fields,before)
    def test_native_index_zero_sentinel_does_not_block_valid_resource_lookup(self):
        from types import SimpleNamespace as Obj
        zero=Obj(type=0xC5F6763E,group=0,instance=0)
        valid=Obj(type=0xC5F6763E,group=0,instance=123)
        loaded=[]
        def loader(key):
            loaded.append(key);return Obj(load_raw=lambda silent_fail:b'effective')
        resources=Obj(list=lambda type:[zero,valid],ResourceLoader=loader)
        package=Obj(resources=resources)
        with patch.dict(sys.modules,{'sims4':package,'sims4.resources':resources}):
            result=morph.effective_modifier(Obj(),'C5F6763E:00000000:000000000000007B',hashlib.sha256(b'effective').hexdigest())
        self.assertEqual(result,'123');self.assertEqual(loaded,[valid])
    def test_new_zero_modifier_preserves_unknown_fields_and_all_existing_groups(self):
        fields=self.fields();before=appearance.decode(fields['facial_attributes'])
        after=morph.add(fields,3,str(2**64-1),.625)
        prior = [row[3] for row in morph.chunks(before)]
        actual = [row[3] for row in morph.chunks(appearance.decode(after['facial_attributes']))]
        self.assertEqual([row for row in actual if row in prior], prior)
        self.assertEqual(after['physique'],fields['physique'])
        self.assertEqual([r for r in morph.inspect(after) if r['key']==str(2**64-1)][0]['value'],.625)
    def test_new_body_modifier_precedes_aged_groups_in_face_and_genetic_packets(self):
        raw = group(2,modifier(12,.1))+group(3,modifier(13,.2))+group(5,modifier(15,.3))+b'\x42\x03ccx'
        fields = {'facial_attributes': appearance.encode(raw), 'genetic_data': appearance.encode(group(1,raw))}
        after = morph.add(fields,3,'99',.375)
        facial = appearance.decode(after['facial_attributes'])
        genetic = morph.chunks(appearance.decode(after['genetic_data']))[0][2]
        self.assertEqual(facial,genetic)
        self.assertEqual([n for n,k,p,c in morph.chunks(facial)],[2,3,3,5,8])
    def test_modifier_addition_refuses_existing_group_key_but_keeps_other_group_independent(self):
        fields=self.fields()
        with self.assertRaises(ValueError):morph.add(fields,2,'123',.5)
        self.assertEqual(len(morph.inspect(morph.add(fields,3,'456',.5))),len(morph.inspect(fields))+1)
        for group,key,value in ((True,'999',.5),(6,'999',.5),(2,'0',.5),(2,str(2**64),.5),(2,'999',float('nan')),(2,'999',1e100)):
            with self.assertRaises(ValueError):morph.add(fields,group,key,value)
    def test_effective_definition_hash_is_required_and_losing_override_is_not_added(self):
        from types import SimpleNamespace
        backend=SimpleNamespace(_studio_modifier_resource=lambda tgi:b'loaded definition')
        tgi='C5F6763E:00000000:000000000000007B'
        self.assertEqual(morph.effective_modifier(backend,tgi,hashlib.sha256(b'loaded definition').hexdigest()),'123')
        with self.assertRaisesRegex(ValueError,'another definition'):morph.effective_modifier(backend,tgi,'0'*64)
    def test_resource_verified_add_preview_live_and_undo_retain_the_original_full_packet(self):
        fixture=fixtures.StudioTests('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.sim.physique='0.1,0.2,0.3,'
        fixture.sim.facial_attributes=appearance.decode(self.fields()['facial_attributes'])
        before=fixture.sim.facial_attributes;fixture.backend._studio_modifier_resource=lambda tgi:b'modifier'
        status=fixture.request('studio_shape_inspect')
        request=dict(group=3,value=.625,resource_tgi='C5F6763E:00000000:00000000000003E7',
                     resource_sha256=hashlib.sha256(b'modifier').hexdigest(),lane=status['history_lane'],appearance_sha256=status['appearance_sha256'])
        draft=fixture.request('studio_shape_add_preview',json.dumps(request));self.assertEqual(before,fixture.sim.facial_attributes)
        fixture.request('studio_cancel',draft['preview_id'])
        result=fixture.request('studio_shape_add_live',json.dumps(request));self.assertTrue(result['live_shape_applied'])
        undo=fixture.request('studio_undo');fixture.request('studio_apply',undo['preview_id'])
        self.assertEqual(before,fixture.sim.facial_attributes)
    def fields(self):
        raw=b'\x0a\x03abc'+group(2,modifier())+group(3,modifier(123,.5))+group(4,modifier(123,.75))+group(5,modifier(456,0))+b'\xba\x06\x03new'
        return dict(facial_attributes=appearance.encode(raw),physique=appearance.encode('0.1,0.2,0.30,0,0,0,0,0,0'),
                    skin_tone=appearance.encode(900))
    def request(self,fields,**changes):
        row=morph.inspect(fields)[0]
        request={key:row[key] for key in ('field','group','index','key')}
        request.update(before=row['value'],value=.625);request.update(changes)
        return request
    def test_all_four_groups_and_every_physique_component_are_inspected(self):
        rows=morph.inspect(self.fields())
        self.assertEqual([row['group'] for row in rows[:4]],[2,3,4,5])
        self.assertEqual(len(rows),13)
        self.assertEqual([row['label'] for row in rows[4:7]],['Heavy','Fit','Lean'])
    def test_one_amount_changes_and_all_other_groups_sculpts_unknown_fields_remain_exact(self):
        fields=self.fields(); original=copy.deepcopy(fields); after=morph.replace(fields,self.request(fields))
        before_chunks=morph.chunks(appearance.decode(fields['facial_attributes']))
        after_chunks=morph.chunks(appearance.decode(after['facial_attributes']))
        self.assertEqual(fields,original)
        self.assertEqual([row[3] for row in before_chunks if row[0]!=2],[row[3] for row in after_chunks if row[0]!=2])
        self.assertEqual(morph.inspect(after)[0]['value'],.625)
        self.assertEqual(after['physique'],fields['physique']);self.assertEqual(after['skin_tone'],fields['skin_tone'])
        child=morph.modifier(after_chunks[1][2])[2];self.assertEqual(child[-1][-1],b'\x4a\x03xyz')
    def test_duplicate_resource_key_requires_exact_group_and_ordinal(self):
        fields=self.fields();after=morph.replace(fields,self.request(fields,group=4,before=.75))
        self.assertEqual([row['value'] for row in morph.inspect(after)[:4]],[.25,.5,.625,0])
    def test_absent_amount_defaults_to_zero_without_dropping_unknown_child_fields(self):
        fields=dict(facial_attributes=appearance.encode(group(2,modifier(amount=None))))
        after=morph.replace(fields,self.request(fields,before=0))
        self.assertEqual(morph.inspect(after)[0]['value'],.625)
        self.assertIn(b'\x4a\x03xyz',appearance.decode(after['facial_attributes']))
    def test_full_uint64_keys_and_fixed64_keys_remain_exact(self):
        key=2**64-1;raw=b'\x09'+struct.pack('<Q',key)+b'\x15'+struct.pack('<f',.25)
        fields=dict(facial_attributes=appearance.encode(group(2,raw)))
        after=morph.replace(fields,self.request(fields))
        self.assertEqual(morph.inspect(after)[0]['key'],str(key));self.assertIn(raw[:9],appearance.decode(after['facial_attributes']))
    def test_invalid_stale_ambiguous_and_nonfinite_requests_leave_fields_unchanged(self):
        fields=self.fields();before=copy.deepcopy(fields)
        for change in (dict(index=True),dict(group=6),dict(key='124'),dict(before=.2),dict(value=float('inf')),dict(value=1e100),dict(extra=True)):
            with self.subTest(change=change),self.assertRaises(ValueError):morph.replace(fields,self.request(fields,**change))
        self.assertEqual(fields,before)
        for raw in (b'\x12\x02\x08',group(2,modifier()+b'\x15'+struct.pack('<f',.2)),group(2,modifier(amount=float('nan')))):
            with self.assertRaises(ValueError):morph.inspect(dict(facial_attributes=appearance.encode(raw)))
    def test_physique_edit_preserves_every_other_text_component_and_field(self):
        fields=self.fields();row=morph.inspect(fields)[5]
        request={key:row[key] for key in ('field','group','index','key')};request.update(before=.2,value=.6)
        after=morph.replace(fields,request)
        self.assertEqual(appearance.decode(after['physique']),'0.1,0.6,0.30,0,0,0,0,0,0')
        self.assertEqual(after['facial_attributes'],fields['facial_attributes'])
    def test_native_trailing_comma_is_preserved_and_empty_components_are_not_invented(self):
        fields=dict(physique=appearance.encode('0.1,0.2,0.3,'))
        rows=morph.inspect(fields);self.assertEqual(len(rows),3)
        row=rows[1];request={key:row[key] for key in ('field','group','index','key')};request.update(before=.2,value=.6)
        self.assertEqual(appearance.decode(morph.replace(fields,request)['physique']),'0.1,0.6,0.3,')
        self.assertEqual(morph.inspect(dict(physique=appearance.encode(''))),[])

    def test_native_fixed_precision_is_journaled_before_the_native_setter_readback(self):
        fields = dict(physique=appearance.encode('0.002,0.000,0.000,0.040,0.000,'))
        row = morph.inspect(fields)[1]
        request = {key: row[key] for key in ('field', 'group', 'index', 'key')}
        request.update(before=0, value=.12)
        after = morph.replace(fields, request)
        self.assertEqual(appearance.decode(after['physique']), '0.002,0.120,0.000,0.040,0.000,')
        request['value'] = .123456
        self.assertEqual(morph.inspect(morph.replace(fields, request))[1]['value'], .123)
    def test_preview_cancel_live_apply_and_undo_use_the_full_appearance_journal(self):
        fixture=fixtures.StudioTests('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.sim.physique='0.1,0.2,0.3,0,0,0,0,0,0'
        fixture.sim.facial_attributes=appearance.decode(self.fields()['facial_attributes']);original=fixture.sim.facial_attributes
        status=fixture.request('studio_shape_inspect');row=status['shape_editor'][0]
        request={key:row[key] for key in ('field','group','index','key')}
        request.update(before=row['value'],value=.625,lane=status['history_lane'],appearance_sha256=status['appearance_sha256'])
        preview=fixture.request('studio_shape_preview',json.dumps(request))
        self.assertEqual(fixture.sim.facial_attributes,original)
        fixture.request('studio_cancel',preview['preview_id']);self.assertEqual(fixture.sim.facial_attributes,original)
        accepted=fixture.request('studio_shape_live',json.dumps(request));self.assertTrue(accepted['live_shape_applied']);self.assertIsNone(accepted['pending_preview'])
        self.assertNotEqual(fixture.sim.facial_attributes,original)
        undo=fixture.request('studio_undo');fixture.request('studio_apply',undo['preview_id'])
        self.assertEqual(fixture.sim.facial_attributes,original)


if __name__=='__main__':unittest.main()
