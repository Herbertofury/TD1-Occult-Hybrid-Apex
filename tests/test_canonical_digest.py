"""Persistent CAS hashes must survive accelerated encoding byte-for-byte."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_commit_plan as plan, cas_bank_transaction as bank


VECTORS = (
    {'schema': 1, 'forms': {'alien': {'parts': [18446744073709551615, 0, 17],
        'name': '\u4ed9\u5973 \U0001f9da', 'paint': 'AA=='}}, 'future': {'new_field': False}},
    {'floats': [-0.0, 0.1, 1e-300, 1e300], 'absent': None, 'empty': {}, 'flags': [True, False]},
    {'surrogate': '\ud800', 'escapes': '\t\n"\\', 'keys': {'z': 1, 'a': 2}},
)


def prior_digest(value):
    result = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    for chunk in encoder.iterencode(value):
        result.update(chunk.encode('ascii'))
    return result.hexdigest()


class CanonicalHashCompatibility(unittest.TestCase):
    def test_historical_field_encodings_match_in_both_runtimes(self):
        for accelerator in (json.encoder.c_make_encoder, None):
            with patch.object(json.encoder, 'c_make_encoder', accelerator):
                for value in VECTORS:
                    with self.subTest(accelerated=accelerator is not None, value=value):
                        before = copy.deepcopy(value)
                        self.assertEqual(plan.digest(value), prior_digest(value))
                        self.assertEqual(value, before)

    def test_large_future_field_is_not_skipped_or_normalized(self):
        value = {'opaque_future': ['x' * 1003, '\u00e9\U0001f9da', 2**64-1] * 300,
                 'forms': {'human': {'paint': ''}, 'alien': {'paint': 'AA=='}}}
        expected = prior_digest(value)
        self.assertEqual(plan.digest(value), expected)
        value['opaque_future'][-1] -= 1
        self.assertNotEqual(plan.digest(value), expected)

    def test_invalid_documents_remain_refused(self):
        cycle = []; cycle.append(cycle)
        for value in (float('nan'), float('inf'), -float('inf'), {'raw': b'bytes'},
                      {'arbitrary': object()}, {'keys': {1: True, '1': False}}, cycle):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                plan.digest(value)

    def test_record_guard_excludes_only_its_two_original_lanes(self):
        value = copy.deepcopy({'bank': VECTORS[0], 'history': [VECTORS[1]], 'future': VECTORS[2],
                 'pending': {'native': 'previous'}, 'cas_transaction': {'journal': [1, 2]}})
        before = copy.deepcopy(value)
        expected = prior_digest({k: v for k, v in value.items() if k not in ('pending', 'cas_transaction')})
        self.assertEqual(bank._record_guard(value), expected)
        self.assertEqual(value, before)
        value['pending']['native'] = 'next'; value['cas_transaction']['journal'].append(3)
        self.assertEqual(bank._record_guard(value), expected)
        value['future']['keys']['a'] = 3
        self.assertNotEqual(bank._record_guard(value), expected)


if __name__ == '__main__':
    unittest.main()
