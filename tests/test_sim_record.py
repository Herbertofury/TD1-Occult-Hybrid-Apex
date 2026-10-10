import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import sim_record
import test_sim_data
from apex_core.sim_data import catalog

class SimRecordTests(unittest.TestCase):
    def fixture(self): return catalog(test_sim_data.SimDataTests().fixture()[0])
    def test_exact_record_unknown_bytes_absent_schema_and_uint64_round_trip(self):
        original = self.fixture()
        self.assertEqual(sim_record.restore(sim_record.archive(original)), original)
    def test_corrupted_bounded_compression_cannot_be_treated_as_a_complete_record(self):
        archived = sim_record.archive(self.fixture())
        archived['bytes'] -= 1
        with self.assertRaisesRegex(ValueError, 'corrupt/truncated'):
            sim_record.restore(archived)
        archived['bytes'] = sim_record.MAX_RECORD + 1
        with self.assertRaisesRegex(ValueError, 'bound'):
            sim_record.restore(archived)
    def test_new_schema_field_and_unknown_wire_change_are_explicit(self):
        original = self.fixture(); newer = copy.deepcopy(original)
        newer['field_schemas']['EA.TestSimData'].append(dict(name='next_patch', number=9000))
        newer['data']['fields'].append(dict(name='next_patch', number=9000, present=False))
        delta = sim_record.delta(sim_record.archive(original), sim_record.archive(newer))
        self.assertTrue(delta['schema_changed']); self.assertEqual(delta['changed_native_fields'], ['next_patch'])
        newer = copy.deepcopy(original); newer['native_sha256'] = 'a' * 64
        self.assertTrue(sim_record.delta(sim_record.archive(original), sim_record.archive(newer))['unknown_wire_changes_possible'])
