import base64
import copy
import hashlib
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_owner_payload as payload, form_appearance as appearance


class OwnerPayloadTests(unittest.TestCase):
    def setUp(self):
        self.descriptors = [dict(name=name, number=number, type=kind, repeated=False)
            for name, number, kind in [('sim_id', 1, 'fixed64'), ('physique', 12, 'string'),
                ('facial_attr', 18, 'bytes'), ('outfits', 21, 'message'),
                ('skin_tone', 10, 'uint64'), ('voice_pitch', 9, 'float'),
                ('genetic_data', 28, 'message')]]
        # Opaque root/child fields represent later patches and unrelated data.
        self.unknown = b'\xa2\x06\x06future'  # field 100, length 6
        self.root = (b'\x09' + (2**64-9).to_bytes(8, 'little') + self.unknown +
                     b'\x62\x03old\xaa\x01\x03\xa0\x06\x01')
        self.capture = dict(native_message_type='EA.Sims4.Persistence.SimData',
            native_base64=base64.b64encode(self.root).decode('ascii'),
            native_sha256=hashlib.sha256(self.root).hexdigest(),
            field_schemas={'EA.Sims4.Persistence.SimData': self.descriptors})
        self.fields = dict(physique=appearance.encode('unique shape'),
            facial_attributes=appearance.encode(b'\x00\xffopaque morphs'),
            __outfits__=appearance.encode(('protobuf', b'\xa0\x06\x7b')),
            skin_tone=appearance.encode(2**64-1), voice_pitch=appearance.encode(0.625),
            genetic_data=appearance.encode(('protobuf', b'\xa0\x06\x7c')))

    def test_every_projected_field_and_unknown_bytes_are_owned_by_detached_result(self):
        before = copy.deepcopy((self.capture, self.fields))
        result = payload.project(self.capture, self.fields)
        raw = bytes.fromhex(result['native_hex'])
        rows = {number: (wire, value, chunk) for number, wire, value, chunk in payload._chunks(raw)}
        self.assertEqual(rows[1][2], self.root[:9])
        self.assertEqual(rows[100][2], self.unknown)
        self.assertEqual(rows[12][1], b'unique shape')
        self.assertEqual(rows[18][1], b'\x00\xffopaque morphs')
        self.assertEqual(rows[21][1], b'\xa0\x06\x7b')
        self.assertEqual(rows[28][1], b'\xa0\x06\x7c')
        self.assertEqual(rows[10][1], 2**64-1)
        self.assertEqual(rows[9][2][-4:], struct.pack('<f', 0.625))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['sha256'])
        self.assertEqual((self.capture, self.fields), before)

    def test_same_base_kind_does_not_merge_different_named_owner_messages(self):
        results = {}
        from apex_core import lifestates
        for state, spec in lifestates.SPECIAL.items():
            for variant in spec['variants']:
                owner = payload.owner_id(state, variant)
                changed = dict(self.fields, physique=appearance.encode(owner))
                results[owner] = payload.project(self.capture, changed)
        self.assertEqual(len({row['sha256'] for row in results.values()}), len(results))
        self.assertIn('imaginary_friend/real', results)
        self.assertIn('servo/robot', results)

    def test_descriptor_field_numbers_are_discovered_and_unrelated_fields_stay_exact(self):
        self.descriptors[1]['number'] = 200
        result = payload.project(self.capture, self.fields)
        rows = payload._chunks(bytes.fromhex(result['native_hex']))
        self.assertIn((200, 2, b'unique shape'), [row[:3] for row in rows])
        self.assertIn((12, 2, b'old'), [row[:3] for row in rows])

    def test_bad_digest_missing_schema_or_incomplete_appearance_refuse_without_partial_result(self):
        bad = copy.deepcopy(self.capture); bad['native_sha256'] = 'a'*64
        with self.assertRaises(ValueError): payload.project(bad, self.fields)
        bad = copy.deepcopy(self.capture); bad['field_schemas'][bad['native_message_type']].pop()
        with self.assertRaises(ValueError): payload.project(bad, self.fields)
        with self.assertRaises(ValueError): payload.project(self.capture, {'physique': appearance.encode('partial')})
        bad = copy.deepcopy(self.capture); bad['field_schemas'][bad['native_message_type']].append(self.descriptors[0])
        with self.assertRaises(ValueError): payload.project(bad, self.fields)
        self.assertEqual(base64.b64decode(self.capture['native_base64']), self.root)

    def test_named_owner_aliases_are_canonical_without_forging_native_bits(self):
        self.assertEqual(payload.owner_id('robot', 'personal_cc'), 'servo/personal_cc')
        for identity in ('', '../human', 'Ghost', 'a/b', 'a'*65, True):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                payload.owner_id('ghost', identity)

    def test_scalar_ranges_and_message_framing_refuse(self):
        for name, value in [('skin_tone', -1), ('skin_tone', True), ('voice_pitch', 1e308),
                            ('physique', 7), ('genetic_data', ('protobuf', b'\x80'))]:
            bad = dict(self.fields, **{name: appearance.encode(value)})
            with self.subTest(name=name), self.assertRaises(ValueError): payload.project(self.capture, bad)

    def test_real_native_tattoo_mapping_keeps_each_record_and_unknown_child_fields(self):
        descriptor=dict(name='parts_custom_tattoos',number=75,type='message',repeated=True,message_type='fixture.Tattoo')
        self.descriptors.append(descriptor)
        self.capture['field_schemas']['fixture.Tattoo']=[
            dict(name='body_type',number=1,type='uint32',repeated=False),
            dict(name='texture_id',number=2,type='uint64',repeated=False)]
        self.root += payload._encode(dict(descriptor,repeated=False),('protobuf',b'\x08\x07\x10\x09\xa0\x06\x7b'))
        self.capture.update(native_base64=base64.b64encode(self.root).decode('ascii'),native_sha256=hashlib.sha256(self.root).hexdigest())
        fields=dict(self.fields,parts_custom_tattoos=appearance.encode({7:2**64-1,900:123456789}))
        raw=bytes.fromhex(payload.project(self.capture,fields)['native_hex'])
        records=[payload._chunks(value) for number,_wire,value,_chunk in payload._chunks(raw) if number==75]
        self.assertEqual(len(records),2)
        self.assertEqual([row[:3] for row in records[0]],[(100,0,123),(1,0,7),(2,0,2**64-1)])
        self.assertEqual([row[:3] for row in records[1]],[(1,0,900),(2,0,123456789)])
        empty=dict(fields,parts_custom_tattoos=appearance.encode({}))
        self.assertFalse(any(row[0]==75 for row in payload._chunks(bytes.fromhex(payload.project(self.capture,empty)['native_hex']))))
        for mapping in ({-1:1},{1:-1},{True:1},{1:True}):
            with self.subTest(mapping=mapping),self.assertRaises(ValueError):
                payload.project(self.capture,dict(fields,parts_custom_tattoos=appearance.encode(mapping)))

    def test_repeated_messages_retain_their_complete_opaque_payloads(self):
        descriptor=dict(name='tattoos',number=75,type='message',repeated=True)
        raw=payload._encode(descriptor,[('protobuf',b'\x08\x01\xa0\x06\x63'),('protobuf',b'\x08\x02')])
        self.assertEqual([row[2] for row in payload._chunks(raw)],[b'\x08\x01\xa0\x06\x63',b'\x08\x02'])
        with self.assertRaises(ValueError):payload._encode(descriptor,b'not a repeated sequence')
