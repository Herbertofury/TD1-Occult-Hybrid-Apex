"""Native CAS pair ordering preserves every protobuf record, including unknowns."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import hybrid_persistence as persistence
from test_native_witch_persistence import NativeData, NativeRecord


class NativePairOrderTests(unittest.TestCase):
    def data(self, mask=17, order=(1, 2, 4, 8, 32, 64, 16)):
        data = NativeData(occult_types=mask, current_occult_types=1)
        data.MergeFromString(b'\xa2\x06\x03top')
        for key in order:
            record = NativeRecord(occult_type=key, physique=str(key))
            record.MergeFromString(b'\xa2\x06\x03new')
            record.outfits.outfits.add(outfit_id=(1 << 63) + key, category=0)
            data.occult_sim_infos.add().CopyFrom(record)
        return data

    def test_human_witch_pair_first_retains_all_seven_records_and_top_unknowns(self):
        data, tracker = self.data(), SimpleNamespace()
        original = data.SerializeToString()
        raw = {item.occult_type: item.SerializeToString() for item in data.occult_sim_infos}
        actual = persistence._native_pair_first(tracker, data)
        self.assertEqual([item.occult_type for item in actual.occult_sim_infos], [1, 16, 2, 4, 8, 32, 64])
        self.assertEqual({item.occult_type: item.SerializeToString() for item in actual.occult_sim_infos}, raw)
        self.assertEqual(data.SerializeToString(), original)
        first, last = NativeData(), NativeData()
        first.CopyFrom(data); last.CopyFrom(actual)
        del first.occult_sim_infos[:]; del last.occult_sim_infos[:]
        self.assertEqual(first.SerializeToString(), last.SerializeToString())

    def test_every_actual_single_known_pair_can_be_first_without_secondary_reordering(self):
        for alternate in (2, 4, 8, 16, 32, 64):
            for mask in (alternate, 1 | alternate):
                with self.subTest(alternate=alternate, mask=mask):
                    data = self.data(mask=mask)
                    original = data.SerializeToString()
                    raw = {item.occult_type: item.SerializeToString() for item in data.occult_sim_infos}
                    actual = persistence._native_pair_first(SimpleNamespace(), data)
                    self.assertEqual([item.occult_type for item in actual.occult_sim_infos][:2], [1, alternate])
                    self.assertEqual([item.occult_type for item in actual.occult_sim_infos][2:],
                        [item.occult_type for item in data.occult_sim_infos if item.occult_type not in (1, alternate)])
                    self.assertEqual(actual.occult_types, mask)
                    self.assertEqual({item.occult_type: item.SerializeToString() for item in actual.occult_sim_infos}, raw)
                    self.assertEqual(data.SerializeToString(), original)
                    first, last = NativeData(), NativeData()
                    first.CopyFrom(data); last.CopyFrom(actual)
                    del first.occult_sim_infos[:]; del last.occult_sim_infos[:]
                    self.assertEqual(first.SerializeToString(), last.SerializeToString())

    def test_missing_pair_unknown_or_multiple_mask_never_invents_owner_or_projection(self):
        for mask, order in ((17, (1, 2)), (16, (1, 2)), (17, (16, 2)), (16, (16, 2)),
                            (127, (1, 2, 16)), (126, (1, 2, 16)), (145, (1, 2, 16)),
                            (144, (1, 2, 16)), (0, (1, 2, 16)), (1, (1, 2, 16))):
            data = self.data(mask, order)
            self.assertIs(persistence._native_pair_first(SimpleNamespace(), data), data)

    def test_conflicting_duplicate_still_retains_sources_and_refuses(self):
        data, tracker = self.data(), SimpleNamespace()
        data.occult_sim_infos.add(occult_type=16, physique='different')
        original = data.SerializeToString()
        with self.assertRaisesRegex(ValueError, 'refusing ambiguous owner selection'):
            persistence._native_pair_first(tracker, data)
        self.assertEqual(data.SerializeToString(), original)
        self.assertFalse(tracker._apex_occult_record_failure['conflict_resolved'])
        self.assertEqual(len(tracker._apex_conflicting_occult_records), 8)


if __name__ == '__main__':
    unittest.main()
