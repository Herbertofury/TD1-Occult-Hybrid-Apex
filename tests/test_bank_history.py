import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import bank_history, cas_bank_transaction as receiver, cas_commit_plan


class BankHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'form_bank.json'

    def test_more_than_32_edits_preserve_complete_future_fields_and_active_wal(self):
        rows = [{'index': i, 'future': {'raw': '\u00ff\x00', 'ids': [2**64-1],
                 'empty': None}, 'appearance': {'unknown': [i, True]}} for i in range(100)]
        record = {'cas_transaction_history': copy.deepcopy(rows), 'pending': {'raw': 'original'},
                  'cas_transaction': {'journal': {'state': 'applying', 'opaque': 'retain'}}}
        before = copy.deepcopy(record)
        bank_history.externalize(self.path, record)
        self.assertEqual(record['pending'], before['pending'])
        self.assertEqual(record['cas_transaction'], before['cas_transaction'])
        self.assertEqual([bank_history.resolve(self.path, x) for x in record['cas_transaction_history']], rows)
        refs = copy.deepcopy(record)
        bank_history.externalize(self.path, record)
        self.assertEqual(record, refs)

    def test_tampered_missing_and_malformed_archive_never_returns_partial_originals(self):
        ref = bank_history.store(self.path, {'all': {'fields': [1, 2, 3]}})
        path = self.path.parent / 'form-bank-history' / (ref['sha256'] + '.json')
        raw = path.read_bytes(); path.write_bytes(raw.replace(b'1', b'9', 1))
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            bank_history.resolve(self.path, ref)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            bank_history.resolve(self.path, ref)
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            bank_history.resolve(self.path, dict(ref, sha256='../untrusted'))

    def test_write_failure_keeps_active_rows_and_does_not_publish_missing_reference(self):
        record = {'switch_history': [{'opaque': 'complete'}]}
        with patch.object(bank_history.os, 'fsync', side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):
                bank_history.externalize(self.path, record)
        self.assertEqual(record, {'switch_history': [{'opaque': 'complete'}]})

    def test_streaming_hash_matches_existing_canonical_contract(self):
        data = {'unicode': '\u00ff', 'future': [0, -7, True, None, 1.25], 'nested': {'raw': '\x00'}}
        raw = json.dumps(data, sort_keys=True, ensure_ascii=True, allow_nan=False,
                         separators=(',', ':')).encode('ascii')
        self.assertEqual(cas_commit_plan.digest(data), hashlib.sha256(raw).hexdigest())

    def test_bank_larger_than_old_48_mib_cutoff_round_trips_without_truncation(self):
        data = {'schema': 1, 'records': {'1:2': {'future_raw': 'x' * (49 * 1024 * 1024)}}}
        receipt = receiver.atomic_save(self.path, data, expected_file_sha256=None)
        loaded = receiver.load_for_write(self.path)
        self.assertEqual(loaded, data)
        self.assertEqual(loaded._bank_file_sha256, receipt['file_sha256'])
        self.assertFalse(self.path.with_suffix('.pending').exists())

    def test_more_than_old_256_sim_record_cutoff_retains_all_foreign_fields(self):
        data={'schema':1,'records':{str(i)+':2':{'future':{'opaque':[i,'kept']}} for i in range(400)}}
        receiver.atomic_save(self.path,data,expected_file_sha256=None)
        self.assertEqual(receiver.load_for_write(self.path),data)

    def test_legacy_history_archives_old_complete_rows_and_keeps_latest_completion_inline(self):
        prior={'native_unknown':{'all_bytes':'kept'},'state':'completed'}
        last={'state':'completed','new_field':[1,2,3]}
        record={'history':[prior,last]}
        bank_history.externalize(self.path,record)
        self.assertTrue(bank_history.reference(record['history'][0]))
        self.assertEqual(bank_history.resolve(self.path,record['history'][0]),prior)
        self.assertEqual(record['history'][-1],last)
