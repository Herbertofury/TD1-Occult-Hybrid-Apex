"""Complete-byte WAL acknowledgment preserves strict JSON and stale-write gates."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_bank_transaction as bank,cas_save_boundary
import test_cas_bank_transaction as fixture


class BankByteReadbackTests(unittest.TestCase):
    def setUp(self):
        self.game=fixture.CasBankReceiverTests();self.game.setUp();self.addCleanup(self.game.doCleanups)
        self.enterContext(patch.object(cas_save_boundary,'_READ_INDEX',None))

    def test_known_revision_still_reads_all_bytes_but_does_not_reparse_them(self):
        data=bank.load_for_write(self.game.path)
        data['records'][self.game.key]['future']={'raw':'\u00ff\x00','zero':-0.0,'ids':[2**64-1]}
        with patch.object(bank,'_read',side_effect=AssertionError('No redundant JSON parsing')):
            receipt=bank.save_from_read(self.game.path,data)
        self.assertTrue(receipt['durable'])
        self.assertEqual(receipt['file_sha256'],hashlib.sha256(self.game.path.read_bytes()).hexdigest())
        self.assertEqual(bank.load_for_write(self.game.path),data)

    def test_unknown_revision_requires_strict_existing_file_validation(self):
        data=bank.load_for_write(self.game.path)
        with patch.object(cas_save_boundary,'_READ_INDEX',None),patch.object(bank,'_read',wraps=bank._read) as read:
            bank.save_from_read(self.game.path,data)
        self.assertEqual(read.call_count,1)

    def test_changed_current_bytes_cannot_borrow_the_prior_revision(self):
        data=bank.load_for_write(self.game.path)
        current=self.game.path.read_bytes()+b' '
        self.game.path.write_bytes(current)
        with self.assertRaisesRegex(ValueError,'file hash differs'):
            bank.save_from_read(self.game.path,data)
        self.assertEqual(self.game.path.read_bytes(),current)

    def test_malformed_existing_bytes_never_qualify_even_with_their_exact_hash(self):
        bank.load_for_write(self.game.path)
        for raw in (b'{"schema":1,"records":{},"x":NaN}',b'{"schema":1,"records":{},"schema":1}'):
            self.game.path.write_bytes(raw)
            with self.assertRaises(ValueError):
                bank.atomic_save(self.game.path,{'schema':1,'records':{}},hashlib.sha256(raw).hexdigest())
            self.assertEqual(self.game.path.read_bytes(),raw)

    def test_equal_json_with_changed_durable_bytes_is_not_a_write_acknowledgment(self):
        data=bank.load_for_write(self.game.path);replace=bank.os.replace
        def changed_after_replace(source,target):
            replace(source,target)
            Path(target).write_bytes(Path(target).read_bytes()+b' ')
        with patch.object(bank.os,'replace',side_effect=changed_after_replace),self.assertRaisesRegex(ValueError,'complete JSON readback'):
            bank.save_from_read(self.game.path,data)
        self.assertFalse(bank._lease_path(self.game.path).exists())

    def test_lossy_tuples_or_integer_keys_fail_before_any_original_is_replaced(self):
        original=self.game.path.read_bytes()
        for unknown in ((1,2),{1:'would coerce to string'}):
            data=bank.load_for_write(self.game.path);data['future']=unknown
            with self.subTest(unknown=unknown),self.assertRaisesRegex(ValueError,'exact JSON'):
                bank.save_from_read(self.game.path,data)
            self.assertEqual(self.game.path.read_bytes(),original)
