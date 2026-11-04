import base64
import copy
import hashlib
import unittest
from apex_core import cas_owner_payload as payload,form_appearance as appearance
import test_cas_owner_payload as fixtures


class OwnerRecordPayloadTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.OwnerPayloadTests();fixture.setUp()
        self.capture=fixture.capture;self.fields=fixture.fields;self.root=fixture.root
        self.root_schema=fixture.descriptors
        self.attributes=dict(name='attributes',number=101,type='message',repeated=False,message_type='fixture.Attributes')
        self.tracker=dict(name='occult_tracker',number=37,type='message',repeated=False,message_type='fixture.Tracker')
        self.records=dict(name='occult_sim_infos',number=41,type='message',repeated=True,message_type='fixture.Record')
        self.kind=dict(name='occult_type',number=1,type='uint32',repeated=False)
        self.root_schema.append(self.attributes)
        child=[dict(row,name='facial_attributes' if row['name']=='facial_attr' else row['name'])
               for row in self.root_schema if row['name'] not in ('sim_id','attributes')]
        self.capture['field_schemas'].update({'fixture.Attributes':[self.tracker],
            'fixture.Tracker':[self.records],'fixture.Record':[self.kind]+child})
        self.record_unknown=b'\xb2\x06\x06record';self.attribute_unknown=b'\x90\x06\x01'
        self.other=payload._encode(self.kind,2)+b'\x92\x06\x05other'
        self.selected=payload._encode(self.kind,64)+self.record_unknown

    def encode(self,descriptor,raw):return payload._encode(dict(descriptor,repeated=False),('protobuf',raw))

    def capture_with_records(self,rows):
        # Membership/current metadata remains exact while only the selected
        # appearance record changes. Unknown messages retain their raw bytes.
        tracker=b'\x08\x7f\x10\x02'+b''.join(self.encode(self.records,row) for row in rows)
        attributes=self.attribute_unknown+self.encode(self.tracker,tracker)
        raw=self.root+self.encode(self.attributes,attributes)
        self.capture.update(native_base64=base64.b64encode(raw).decode('ascii'),native_sha256=hashlib.sha256(raw).hexdigest())

    def inspect(self,result):
        raw=bytes.fromhex(result['native_hex']);root=payload._chunks(raw)
        attribute=next(r[2] for r in root if r[0]==101);attributes=payload._chunks(attribute)
        tracker=next(r[2] for r in attributes if r[0]==37);rows=payload._chunks(tracker)
        records=[r[2] for r in rows if r[0]==41]
        return raw,root,attribute,rows,records

    def test_selected_record_keeps_complete_genetics_and_unrelated_data_exact(self):
        self.capture_with_records([self.other,self.selected]);before=copy.deepcopy((self.capture,self.fields))
        result=payload.project_record(self.capture,self.fields,64)
        raw,root,attributes,tracker,records=self.inspect(result)
        self.assertEqual(records[0],self.other);self.assertIn(self.record_unknown,records[1])
        self.assertIn(self.attribute_unknown,attributes);self.assertIn(b'\xa2\x06\x06future',raw)
        self.assertEqual([(r[0],r[2]) for r in tracker if r[0] in (1,2)],[(1,127),(2,2)])
        selected={r[0]:r for r in payload._chunks(records[1])}
        self.assertEqual(selected[1][2],64);self.assertEqual(selected[28][2],b'\xa0\x06\x7c')
        self.assertEqual(selected[12][2],b'unique shape')
        self.assertEqual((self.capture,self.fields),before)

    def test_human_only_detached_dto_can_receive_full_record_without_changing_live_membership(self):
        result=payload.project_record(self.capture,self.fields,1)
        raw,root,attributes,tracker,records=self.inspect(result)
        self.assertEqual(len(records),1);self.assertEqual(payload._chunks(records[0])[0][2],1)
        self.assertFalse(any(r[0] in (1,2) for r in tracker))  # No invented membership/current fields.
        self.assertEqual(root[0][3],self.root[:9])

    def test_duplicate_record_missing_schema_and_invalid_kind_refuse(self):
        self.capture_with_records([self.selected,self.selected])
        with self.assertRaises(ValueError):payload.project_record(self.capture,self.fields,64)
        self.capture_with_records([self.selected]);self.capture['field_schemas']['fixture.Record'].pop()
        with self.assertRaises(ValueError):payload.project_record(self.capture,self.fields,64)
        for kind in (0,3,True,128):
            with self.assertRaises(ValueError):payload.project_record(self.capture,self.fields,kind)


if __name__=='__main__':unittest.main()
