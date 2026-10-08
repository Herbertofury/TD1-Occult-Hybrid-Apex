import base64
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.sim_data import catalog, snapshot


class SimDataTests(unittest.TestCase):
    def fixture(self):
        fields = [Obj(name='id', number=1, type=4, label=1, message_type=None, enum_type=None),
                  Obj(name='apparently_irrelevant', number=2, type=8, label=1, message_type=None, enum_type=None),
                  Obj(name='unknown_payload', number=3, type=12, label=1, message_type=None, enum_type=None)]
        descriptor = Obj(full_name='EA.TestSimData', fields=fields)
        raw = b'\x08\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01\x18\x02\xc0\x3e\x07'
        message = Obj(DESCRIPTOR=descriptor, ListFields=lambda: [(fields[0], (1 << 64) - 1), (fields[2], b'\x00\xff')],
                      SerializeToString=lambda: raw)
        return message, raw

    def test_all_fields_including_absent_and_unknown_bytes_remain_visible(self):
        message, raw = self.fixture()
        result = catalog(message)
        self.assertEqual(base64.b64decode(result['native_base64']), raw)
        fields = result['data']['fields']
        self.assertEqual([row['name'] for row in fields], ['id', 'apparently_irrelevant', 'unknown_payload'])
        self.assertEqual(fields[0]['value'], str((1 << 64) - 1))
        self.assertFalse(fields[1]['present'])
        self.assertEqual(base64.b64decode(fields[2]['value']['value']), b'\x00\xff')
        self.assertTrue(result['unknown_fields_retained_in_native_bytes'])
        self.assertFalse(result['runtime_only_fields_complete'])

    def test_complete_serializer_contract_without_cloning_or_disk_save(self):
        message, _ = self.fixture()
        observed = []
        sim = Obj(id=7, save_sim=lambda **kwargs: observed.append(kwargs) or message)
        backend = Obj(services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 99)))
        result = snapshot(backend, sim)
        self.assertEqual(observed, [{'for_cloning': False, 'full_service': True}])
        self.assertFalse(result['save_file_written'])
        self.assertEqual(result['save_guid'], '99')

    def test_repeated_nested_schema_does_not_drop_fields_or_precision(self):
        nested, _ = self.fixture()
        field = Obj(name='children', number=1, type=11, label=3, message_type=nested.DESCRIPTOR, enum_type=None)
        outer = Obj(DESCRIPTOR=Obj(full_name='EA.Root', fields=[field]), SerializeToString=lambda: b'root',
                    ListFields=lambda: [(field, [nested, nested])])
        result = catalog(outer)
        self.assertEqual(len(result['data']['fields'][0]['value']), 2)
        self.assertEqual(len(result['field_schemas']['EA.TestSimData']), 3)
