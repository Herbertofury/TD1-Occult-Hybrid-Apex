"""Production entry, history, legacy and certification gates share one journal."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_bank_transaction as receiver, form_bank, form_bank_seal, studio, outfit_hair
import test_cas_bank_transaction as fixtures


class CasTransactionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.CasBankReceiverTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_modern_finish_retains_raw_checkpoint_and_never_calls_serializer_or_setter(self):
        case = self.case; case.begin()
        before = case.path.read_bytes()
        with patch.object(receiver.sim_data, 'snapshot', side_effect=AssertionError('No serializer in finish')):
            result = form_bank.finish(case.backend, case.sim)
        self.assertFalse(result['ok']); self.assertEqual(result['outcome'], 'explicit-owner-decisions-required')
        self.assertEqual(case.path.read_bytes(), before); self.assertEqual(case.native_writes, [])

    def test_consumed_pending_with_incomplete_ack_blocks_all_legacy_writers(self):
        case = self.case; case.begin()
        value = case.data(); record = value['records'][case.key]
        record['pending'] = None
        record['cas_transaction']['journal'] = {'state': 'recovery-required'}
        form_bank.save(case.path, value)
        before = case.path.read_bytes(); fields = copy.deepcopy(case.originals['64'])
        operation = Mock(return_value={'ok': True})
        attempts = (
            lambda: form_bank.assert_idle(case.backend, case.sim),
            lambda: form_bank.begin(case.backend, case.sim),
            lambda: form_bank.update(case.backend, case.sim, '64', fields),
            lambda: form_bank.switch(case.backend, case.sim, 1, operation),
            lambda: outfit_hair.configure(case.backend, case.sim, False),
            lambda: studio._capture_native_record(case.backend, case.sim),
            lambda: form_bank_seal._record(case.path, case.key),
        )
        for index, attempt in enumerate(attempts):
            with self.subTest(index=index), self.assertRaises(ValueError): attempt()
        self.assertFalse(outfit_hair.enforce(case.backend, case.sim))
        self.assertEqual(case.path.read_bytes(), before); operation.assert_not_called()
        self.assertEqual(case.native_writes, []); self.assertEqual(case.snapshot_calls, [])

    def test_revision_from_original_read_cannot_overwrite_new_checkpoint(self):
        case = self.case
        stale = form_bank.load(case.path)
        case.begin(); before = case.path.read_bytes()
        stale['records']['30:other'] = {'unrelated': 'a stale writer cannot erase fresh pending'}
        with self.assertRaises(ValueError): form_bank.save(case.path, stale)
        self.assertEqual(case.path.read_bytes(), before)
        self.assertIsNotNone(case.record()['pending'])

    def test_leftover_lease_blocks_before_callbacks_or_native_record(self):
        case = self.case
        path = receiver._lease_path(case.path); path.write_bytes(b'interrupted writer: inspect explicitly')
        before = case.path.read_bytes()
        for attempt in (lambda: form_bank.assert_idle(case.backend, case.sim),
                        lambda: studio._capture_native_record(case.backend, case.sim)):
            with self.assertRaises(ValueError): attempt()
        self.assertFalse(outfit_hair.enforce(case.backend, case.sim))
        self.assertEqual(case.path.read_bytes(), before); self.assertTrue(path.exists())
        self.assertEqual(case.snapshot_calls, []); self.assertEqual(case.native_writes, [])

    def test_completed_receipt_copied_from_other_sim_does_not_release_legacy_gate(self):
        case = self.case; case.begin(); case.observe(); case.prepare([]); case.commit()
        value = case.data(); record = value['records'].pop(case.key)
        wrong_key = '30:99'; value['records'][wrong_key] = record
        form_bank.save(case.path, value)
        sim = case.sim; sim.id = 99
        before = case.path.read_bytes()
        with self.assertRaises(ValueError): form_bank.assert_idle(case.backend, sim)
        self.assertEqual(case.path.read_bytes(), before)

    def test_receiver_completed_transaction_allows_following_live_edit(self):
        case = self.case; case.begin(); case.observe(); case.prepare([]); case.commit()
        form_bank.assert_idle(case.backend, case.sim)
        fields = copy.deepcopy(case.originals['64']); fields['physique'] = receiver.appearance.encode('later Live edit')
        form_bank.update(case.backend, case.sim, '64', fields)
        self.assertEqual(case.record()['bank']['64'], fields)
        form_bank.assert_idle(case.backend, case.sim)


if __name__ == '__main__':
    unittest.main()
