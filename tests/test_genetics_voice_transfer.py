"""Selective paste against the inspected native GeneticData voice contract."""
import copy
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from apex_core import appearance_transfer as transfer, form_appearance as appearance
from apex_core import genetics_snapshot
import test_genetics_snapshot as wire


def native_message():
    file = descriptor_pb2.FileDescriptorProto(name='genetic_voice_contract.proto', package='Native', syntax='proto2')
    def message(name, fields):
        item = file.message_type.add(name=name)
        for name, number, kind, label, nested in fields:
            field = item.field.add(name=name, number=number, type=kind, label=label)
            if nested: field.type_name = '.Native.' + nested
    message('Part', [('id',1,4,1,''),('body_type',2,13,1,''),('color',3,4,1,'')])
    message('Parts', [('parts',1,11,3,'Part')])
    message('GeneticData', [('sculpts',1,12,1,''),('physique',2,9,1,''),
        ('voice_pitch',3,2,1,''),('voice_actor',4,13,1,''),('parts_list',5,11,1,'Parts'),
        ('growth_parts_list',6,11,1,'Parts')])
    pool = descriptor_pool.DescriptorPool(); pool.Add(file)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName('Native.GeneticData'))


GeneticData = native_message()
def f32(value): return struct.unpack('<f', struct.pack('<f', value))[0]


class GeneticVoiceTransferTests(unittest.TestCase):
    def setUp(self):
        self.source_pitch, self.target_pitch = f32(.8), f32(.5571260452270508)
        self.source_raw = self.genetics(b'source-scultps', f32(.56), 1)
        self.target_raw = self.genetics(b'target-scultps', self.target_pitch, 2)
        self.source = {'genetic_data': appearance.encode(self.source_raw),
            'voice_pitch': appearance.encode(self.source_pitch), 'voice_actor': appearance.encode(1)}
        self.target = {'genetic_data': appearance.encode(self.target_raw),
            'voice_pitch': appearance.encode(self.target_pitch), 'voice_actor': appearance.encode(2)}
        self.choice = {'fields': [], 'outfits': 'none', 'source_outfit': None, 'target_outfit': None, 'body_types': []}

    def genetics(self, sculpts, pitch, actor):
        data = GeneticData(sculpts=sculpts, physique='independent genetic base', voice_pitch=pitch, voice_actor=actor)
        data.parts_list.parts.add(id=(1 << 64)-7, body_type=2, color=(1 << 64)-1)
        data.growth_parts_list.parts.add(id=300336, body_type=78, color=(1 << 63)+91)
        return data.SerializeToString() + wire.message(99, b'future genetic root field')

    def merge(self, fields, source=None, target=None):
        return transfer.merge(None, target or self.target, source or self.source, dict(self.choice, fields=fields))

    def native_readback(self, desired):
        # Independent protobuf model of the observed EA setter/getter: voice
        # mirrors are supplied from the actual scalar properties.
        data = GeneticData(); raw = appearance.decode(desired['genetic_data'])
        data.ParseFromString(raw[1] if isinstance(raw, tuple) else raw)
        data.voice_pitch = appearance.decode(desired['voice_pitch'])
        data.voice_actor = appearance.decode(desired['voice_actor'])
        return data.SerializeToString()

    def test_genetics_without_voice_preserves_destination_voice_and_all_source_body_future_data(self):
        before = copy.deepcopy((self.target, self.source))
        result = self.merge(['genetic_data'])
        raw = appearance.decode(result['genetic_data'])
        self.assertEqual(raw, self.native_readback(result))
        data = GeneticData.FromString(raw)
        self.assertEqual(data.sculpts, b'source-scultps');self.assertEqual(data.voice_pitch, self.target_pitch)
        self.assertEqual(data.voice_actor,2);self.assertEqual(data.parts_list.parts[0].color,(1<<64)-1)
        self.assertIn(wire.message(99,b'future genetic root field'),raw)
        self.assertEqual((self.target,self.source),before)

    def test_selected_voice_pitch_updates_only_destination_genetic_voice_mirror(self):
        result = self.merge(['voice_pitch'])
        raw = appearance.decode(result['genetic_data']);data=GeneticData.FromString(raw)
        self.assertEqual(raw,self.native_readback(result));self.assertEqual(data.sculpts,b'target-scultps')
        self.assertEqual(data.voice_pitch,self.source_pitch);self.assertEqual(data.voice_actor,2)

    def test_selected_actor_preserves_pitch_and_destination_body(self):
        result=self.merge(['voice_actor']);raw=appearance.decode(result['genetic_data']);data=GeneticData.FromString(raw)
        self.assertEqual(raw,self.native_readback(result));self.assertEqual(data.voice_actor,1)
        self.assertEqual(data.voice_pitch,self.target_pitch);self.assertEqual(data.sculpts,b'target-scultps')

    def test_full_genetics_and_voice_use_actual_selected_source_scalar_even_if_embedded_pitch_was_stale(self):
        result=self.merge(['genetic_data','voice_pitch','voice_actor']);raw=appearance.decode(result['genetic_data'])
        self.assertEqual(raw,self.native_readback(result));self.assertEqual(GeneticData.FromString(raw).voice_pitch,self.source_pitch)
        self.assertEqual(GeneticData.FromString(self.source_raw).voice_pitch,f32(.56))

    def test_protobuf_wrapper_and_unknown_byte_order_are_retained(self):
        raw=self.source_raw;unknown=wire.message(100,b'unknown before known fields')
        source=dict(self.source,genetic_data=appearance.encode(('protobuf',unknown+raw)))
        value=appearance.decode(self.merge(['genetic_data'],source=source)['genetic_data'])
        self.assertEqual(value[0],'protobuf');self.assertTrue(value[1].startswith(unknown))
        self.assertTrue(value[1].endswith(wire.message(99,b'future genetic root field')))

    def test_ambiguous_known_fields_or_missing_scalar_refuse_purely_before_native_mutation(self):
        for raw in (self.source_raw+b'\x1d'+struct.pack('<f',.1),self.source_raw+b'\x20\x01',
                    self.source_raw+wire.message(3,b'wrong wire type')):
            with self.subTest(raw=raw[-8:]),self.assertRaisesRegex(ValueError,'ambiguous'):
                self.merge(['genetic_data'],source=dict(self.source,genetic_data=appearance.encode(raw)))
        target=dict(self.target);target.pop('voice_pitch')
        with self.assertRaisesRegex(ValueError,'available native pitch'):self.merge(['genetic_data'],target=target)

    def test_unsupported_opaque_layout_and_absent_mirror_fields_remain_exact(self):
        for raw in (b'opaque future layout',wire.genetic([wire.part(1,2)],[])):
            source=dict(self.source,genetic_data=appearance.encode(raw))
            self.assertEqual(appearance.decode(self.merge(['genetic_data'],source=source)['genetic_data']),raw)

    def test_invalid_native_scalar_values_never_become_genetic_bytes(self):
        for pitch,actor in ((True,1),(float('nan'),1),(float('inf'),1),(1e100,1),(.5,True),(.5,-1),(.5,1<<32)):
            with self.subTest(pitch=pitch,actor=actor),self.assertRaises(ValueError):
                genetics_snapshot.mirror_voice(self.source_raw,pitch,actor)


if __name__=='__main__':unittest.main()
