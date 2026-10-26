"""Historical-validation reuse cannot bypass changed receipts or live gates."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_bank_transaction as bank
import test_cas_bank_transaction as fixture


class CompletedReceiptCacheTests(unittest.TestCase):
    def setUp(self):
        self.game=fixture.CasBankReceiverTests();self.game.setUp();self.addCleanup(self.game.doCleanups)
        bank._COMPLETED_RECEIPTS.clear();self.addCleanup(bank._COMPLETED_RECEIPTS.clear)
        self.game.begin();self.game.observe();self.game.prepare([]);self.game.commit()
        self.receipt=copy.deepcopy(self.game.record()['cas_transaction'])
        bank._COMPLETED_RECEIPTS.clear()

    def test_exact_full_receipt_reuses_validation_without_retaining_mutable_objects(self):
        with patch.object(bank,'_completed_uncached',wraps=bank._completed_uncached) as validate:
            self.assertTrue(bank._completed(self.receipt))
            self.assertTrue(bank._completed(copy.deepcopy(self.receipt)))
            self.assertEqual(validate.call_count,1)
        snapshot=next(iter(bank._COMPLETED_RECEIPTS.values()))
        self.assertIsNot(snapshot,self.receipt)
        self.assertIsNot(snapshot['journal'],self.receipt['journal'])
        self.assertEqual(snapshot,self.receipt)

    def test_warm_receipt_does_not_encode_or_hash_historical_payloads(self):
        self.assertTrue(bank._completed(self.receipt))
        with patch.object(bank,'_receipt_cache_key',side_effect=AssertionError('No re-encoding')):
            self.assertTrue(bank._completed(copy.deepcopy(self.receipt)))

    def test_mutating_original_after_cache_cannot_mutate_snapshot(self):
        self.assertTrue(bank._completed(self.receipt))
        original=copy.deepcopy(self.receipt)
        self.receipt['identity']['sim_id']='999'
        self.assertFalse(bank._completed(self.receipt))
        self.assertTrue(bank._completed(original))

    def test_unknown_json_scalars_use_exact_types_on_cache_hits(self):
        self.receipt['future_metadata']={'value':True}
        with patch.object(bank,'_completed_uncached',wraps=bank._completed_uncached) as validate:
            self.assertTrue(bank._completed(self.receipt))
            changed=copy.deepcopy(self.receipt);changed['future_metadata']['value']=1
            self.assertTrue(bank._completed(changed))
            changed['future_metadata']['value']=1.0
            self.assertTrue(bank._completed(changed))
            self.assertEqual(validate.call_count,3)

    def test_float_zero_sign_change_cannot_reuse_a_different_canonical_receipt(self):
        self.receipt['future_metadata']=0.0
        with patch.object(bank,'_completed_uncached',wraps=bank._completed_uncached) as validate:
            self.assertTrue(bank._completed(self.receipt))
            changed=copy.deepcopy(self.receipt);changed['future_metadata']=-0.0
            self.assertTrue(bank._completed(changed))
            self.assertEqual(validate.call_count,2)

    def test_mutated_identity_or_payload_cannot_reuse_valid_history(self):
        self.assertTrue(bank._completed(self.receipt))
        for mutation in ('identity','payload','ack'):
            changed=copy.deepcopy(self.receipt)
            if mutation=='identity':changed['identity']['sim_id']='999'
            elif mutation=='payload':changed['journal']['raw_return']['stored']['1']['physique']['value']='other Sim'
            else:changed['metadata_commit']['native_verified_receipt_sha256']='0'*64
            with self.subTest(mutation=mutation):self.assertFalse(bank._completed(changed))
        self.assertTrue(bank._completed(self.receipt))

    def test_tuple_list_json_collision_still_runs_strict_validation(self):
        self.assertTrue(bank._completed(self.receipt))
        changed=copy.deepcopy(self.receipt)
        changed['journal']['plan']['dispositions']=tuple(changed['journal']['plan']['dispositions'])
        self.assertIsNone(bank._receipt_cache_key(changed))
        self.assertFalse(bank._completed(changed))

    def test_pending_cas_and_switch_gates_win_even_with_a_cached_completed_receipt(self):
        self.assertTrue(bank._completed(self.receipt))
        for field in ('pending','switch_pending'):
            record=dict(cas_transaction=self.receipt,pending=None,switch_pending=None);record[field]={}
            with self.subTest(field=field),patch.object(bank,'_completed',side_effect=AssertionError('Pending must block first')):
                self.assertTrue(bank._blocked(record))

    def test_unknown_metadata_change_requires_full_validation_again(self):
        with patch.object(bank,'_completed_uncached',wraps=bank._completed_uncached) as validate:
            self.assertTrue(bank._completed(self.receipt))
            changed=copy.deepcopy(self.receipt);changed['future_metadata']={'opaque':['retained',123]}
            self.assertTrue(bank._completed(changed))
            self.assertEqual(validate.call_count,2)

    def test_validator_replacement_does_not_inherit_an_earlier_positive_cache(self):
        self.assertTrue(bank._completed(self.receipt))
        with patch.object(bank,'_completed_uncached',return_value=False) as validate:
            self.assertFalse(bank._completed(self.receipt));validate.assert_called_once()

    def test_positive_cache_is_bounded_and_does_not_cache_rejections(self):
        bad=copy.deepcopy(self.receipt);bad['schema']=99
        self.assertFalse(bank._completed(bad));self.assertFalse(bank._COMPLETED_RECEIPTS)
        for index in range(bank._COMPLETED_RECEIPT_LIMIT+1):
            changed=copy.deepcopy(self.receipt);changed['future_metadata']=index
            self.assertTrue(bank._completed(changed))
        self.assertLessEqual(len(bank._COMPLETED_RECEIPTS),bank._COMPLETED_RECEIPT_LIMIT)
        self.assertTrue(bank._completed(changed))
