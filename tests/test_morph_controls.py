import copy
import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import morph_controls as morph, form_appearance as appearance
import test_studio as fixtures


def modifier(key=123, amount=.25, extra=b'\x4a\x03xyz'):
    return b'\x08'+morph.encoded_varint(key)+(b'\x15'+struct.pack('<f',amount) if amount is not None else b'')+extra


def group(number, payload):
    return morph.encoded_varint((number<<3)|2)+morph.encoded_varint(len(payload))+payload


class MorphTests(unittest.TestCase):
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
