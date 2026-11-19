import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Source'))
from apex_core import cas_bank_transaction as bank


class StrictBankReadTests(unittest.TestCase):
    def read(self,raw):
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'form_bank.json';path.write_bytes(raw)
            result=bank._read(path)
            self.assertEqual(path.read_bytes(),raw)
            return result

    def test_all_unknown_fields_and_exact_raw_file_hash_remain_present(self):
        data={'schema':1,'records':{},'future':{'name':'资源','fields':[None,True,False,0,2**64-1,10**256,
            -0.0,5e-324,1.7976931348623157e308,{'new':[1,2,3]}]}}
        raw=json.dumps(data,ensure_ascii=True,allow_nan=False,indent=3).encode('utf-8')
        actual,revision=self.read(raw)
        self.assertEqual(actual,data)
        self.assertEqual(revision,hashlib.sha256(raw).hexdigest())
        self.assertEqual(math.copysign(1,actual['future']['fields'][6]),-1)

    def test_nonfinite_values_are_rejected_at_every_depth_including_float_overflow(self):
        for token in ('NaN','Infinity','-Infinity','1e999','-1e999'):
            for shape in ('%s','{"unknown":[%s]}'):
                with self.subTest(token=token,shape=shape),self.assertRaises(ValueError):
                    self.read(('{"schema":1,"records":{},"future":'+shape%token+'}').encode())

    def test_duplicate_keys_and_invalid_root_shapes_remain_rejected(self):
        for raw in (b'{"schema":1,"schema":1,"records":{}}',
                    b'{"schema":1,"records":{},"future":{"a":1,"a":2}}',
                    b'{"schema":true,"records":{}}',b'{"schema":1,"records":[]}',
                    b'{"schema":1.0,"records":{}}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):self.read(raw)

    def test_read_validation_does_not_encode_and_hash_the_complete_document_twice(self):
        raw=b'{"schema":1,"records":{},"future":{"float":0.125}}'
        with patch.object(bank.primitive,'digest',side_effect=AssertionError('Redundant whole-document encoding')):
            data,revision=self.read(raw)
        self.assertEqual(data['future']['float'],.125)
        self.assertEqual(revision,hashlib.sha256(raw).hexdigest())


if __name__=='__main__':unittest.main()
