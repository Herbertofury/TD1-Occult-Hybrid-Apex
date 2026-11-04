import base64
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core.sim_data import catalog, snapshot


class SimDataTests(unittest.TestCase):
    def test_variadic_injection_wrapper_accepts_history_read_and_delegates_other_calls(self):
        message, _ = self.fixture()
        calls = []
        def injected(function):
            def wrapper(*args, **kwargs):
                calls.append(('wrapper', args[0].id, kwargs))
                return function(*args, **kwargs)
            return wrapper
        class Sim:
            id = 7
            physique = 'edited Alien shape'
            @injected
            def _set_fit_fat(self, reason=None):
                calls.append(('native', self.id, reason))
                self.physique = 'shared fitness projection'
            def save_sim(self, **kwargs):
                self._set_fit_fat()
                return message
        sim = Sim()
        backend = Obj(services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 99)))
        snapshot(backend, sim)
        self.assertEqual(sim.physique, 'edited Alien shape')
        self.assertEqual(calls, [])
        sim._set_fit_fat(reason='ordinary native operation')
        self.assertEqual(calls, [('wrapper', 7, {'reason': 'ordinary native operation'}),
                                 ('native', 7, 'ordinary native operation')])
        self.assertEqual(sim.physique, 'shared fitness projection')

    def test_wrapped_required_argument_still_refuses_before_serialization(self):
        import functools
        def injected(function):
            @functools.wraps(function)
            def wrapper(*args, **kwargs): return function(*args, **kwargs)
            return wrapper
        class Sim:
            id = 7
            @injected
            def _set_fit_fat(self, required): pass
            def save_sim(self, **kwargs): self.fail = True
        sim = Sim()
        with self.assertRaisesRegex(ValueError, 'signature changed'): snapshot(Obj(), sim)
        self.assertFalse(hasattr(sim, 'fail'))

    def test_history_serializer_preserves_edited_physique_but_normal_saves_and_other_sims_recalculate(self):
        message, _ = self.fixture()
        calls = []
        class Sim:
            id = 7
            physique = 'edited Alien shape'
            def _set_fit_fat(self):
                calls.append(self.id)
                self.physique = 'shared fitness projection'
            def save_sim(self, **kwargs):
                self._set_fit_fat()
                other._set_fit_fat()
                return message
        sim, other = Sim(), Sim(); other.id = 8
        backend = Obj(services=Obj(get_persistence_service=lambda: Obj(get_save_slot_proto_guid=lambda: 99)))
        snapshot(backend, sim)
        self.assertEqual(sim.physique, 'edited Alien shape')
        self.assertEqual(other.physique, 'shared fitness projection')
        self.assertEqual(calls, [8])
        sim.save_sim()
        self.assertEqual(sim.physique, 'shared fitness projection')
        self.assertEqual(calls, [8, 7, 8])

    def test_failed_snapshot_releases_physique_read_scope(self):
        class Sim:
            id = 7
            count = 0
            def _set_fit_fat(self): self.count += 1
            def save_sim(self, **kwargs):
                self._set_fit_fat()
                raise ValueError('native serialization failed')
        sim = Sim()
        with self.assertRaisesRegex(ValueError, 'native serialization failed'): snapshot(Obj(), sim)
        self.assertEqual(sim.count, 0)
        sim._set_fit_fat()
        self.assertEqual(sim.count, 1)

    def test_changed_native_physique_signature_refuses_before_serializer(self):
        class Sim:
            id = 7
            def _set_fit_fat(self, required): pass
            def save_sim(self, **kwargs): self.fail = True
        sim = Sim()
        with self.assertRaisesRegex(ValueError, 'signature changed'): snapshot(Obj(), sim)
        self.assertFalse(hasattr(sim, 'fail'))

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
