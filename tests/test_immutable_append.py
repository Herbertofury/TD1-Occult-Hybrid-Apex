"""Exact immutable JSON boundary; no game objects, live files or DLL needed."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tested_immutable_append', ROOT / 'Source/apex_core/immutable_append.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class ImmutableAppendTests(unittest.TestCase):
    def sample(self):
        return {'unknown': [{'astral\U0001f9da': ['\ud800', -0.0, 0, None, False, True, 2**2048]},
                            {'text': 'native_serialized_append \\ \\" __SENTINEL__'}]}

    def journal(self):
        value = self.sample()
        return dict(native_serialized_append=value, native_serialized_sha256=sha(dump(value)),
                    schema=1, state='observed', identity={'save_guid': '30'}, future=['unchanged'])

    def receipt(self):
        journal = self.journal()
        request = dict(request_id='a'*32, transaction_id='b'*32, sequence=1)
        capsule = dict(schema=1, canonical_json=dump(journal[module.FIELD]).decode('ascii'),
                       sha256=journal['native_serialized_sha256'], **request)
        response = dict(ok=True, state='ready', immutable_append_protocol=1,
                        immutable_journal_append=capsule, journal_sha256=sha(dump(journal)),
                        record={'cas_transaction': {'journal': dict(journal, native_serialized_append=None)}})
        return response, request

    def test_complete_canonical_unicode_numeric_and_unknown_parity(self):
        plain = self.journal()
        frozen = module.freeze_journal(plain)
        self.assertEqual(b''.join(module.chunks(frozen)), dump(plain))
        self.assertEqual(frozen[module.FIELD].sha256, sha(dump(plain[module.FIELD])))
        self.assertEqual(module.thaw_journal(frozen), plain)

    def test_copy_is_constant_owned_value_without_mutable_original_alias(self):
        plain = self.journal(); original = dump(plain)
        frozen = module.freeze_journal(plain); clone = copy.deepcopy(frozen)
        self.assertIs(clone[module.FIELD], frozen[module.FIELD])
        self.assertIs(copy.copy(frozen[module.FIELD]), frozen[module.FIELD])
        plain[module.FIELD]['unknown'].clear(); plain['future'].append('source mutation')
        clone['future'].append('clone mutation')
        self.assertEqual(b''.join(module.chunks(frozen)), original)

    def test_no_base_container_or_attribute_mutation_hole(self):
        frozen = module.freeze_journal(self.journal())[module.FIELD]
        attempts = [lambda: dict.__setitem__(frozen, 'bad', 1), lambda: dict.update(frozen, bad=1),
                    lambda: list.append(frozen, 'bad'), lambda: list.__setitem__(frozen, 0, b'bad'),
                    lambda: object.__setattr__(frozen, 'canonical', b'bad'),
                    lambda: setattr(frozen, 'new_attribute', 'bad')]
        for attempt in attempts:
            with self.assertRaises((TypeError, AttributeError)):
                attempt()

    def test_each_legacy_thaw_is_independent_plain_exact_json(self):
        frozen = module.freeze_journal(self.journal()); original = b''.join(module.chunks(frozen))
        first, second = module.thaw_journal(frozen), module.thaw_journal(frozen)
        first[module.FIELD]['unknown'][0].clear()
        self.assertEqual(dump(second), original)
        self.assertEqual(b''.join(module.chunks(frozen)), original)
        module._exact(second)

    def test_nonfinite_cycles_nonstring_keys_and_subclasses_refuse(self):
        class SubDict(dict): pass
        class SubList(list): pass
        class SubInt(int): pass
        class SubStr(str): pass
        cycle = {}; cycle['cycle'] = cycle
        values = [{'a': float('nan')}, {'a': float('inf')}, {'a': -float('inf')},
                  {1: 'lossy key'}, {'a': (1, 2)}, {'a': b'bytes'}, cycle,
                  SubDict(a=1), {'a': SubList([1])}, {'a': SubInt(1)}, {SubStr('a'): 1}]
        for value in values:
            with self.assertRaises((ValueError, TypeError, RecursionError)):
                module.FrozenAppend.from_value(value, '0'*64)

    def test_capsule_is_reconstructed_and_bound_to_complete_journal(self):
        response, request = self.receipt()
        actual = module.restore_native_receipt(response, request)
        journal = actual['record']['cas_transaction']['journal']
        self.assertIs(type(journal[module.FIELD]), module.FrozenAppend)
        self.assertEqual(sha(b''.join(module.chunks(journal))), actual['journal_sha256'])

    def test_capsule_downgrade_context_hash_type_and_projection_mutations_refuse(self):
        mutations = [lambda r: r.pop('immutable_journal_append'),
                     lambda r: r.__setitem__('immutable_journal_append', None),
                     lambda r: r.pop('immutable_append_protocol'),
                     lambda r: r.__setitem__('immutable_append_protocol', True),
                     lambda r: r['immutable_journal_append'].__setitem__('request_id', 'c'*32),
                     lambda r: r['immutable_journal_append'].__setitem__('transaction_id', 'd'*32),
                     lambda r: r['immutable_journal_append'].__setitem__('sequence', True),
                     lambda r: r['immutable_journal_append'].__setitem__('schema', True),
                     lambda r: r['immutable_journal_append'].__setitem__('sha256', '0'*64),
                     lambda r: r['immutable_journal_append'].__setitem__('canonical_json', '{}'),
                     lambda r: r['immutable_journal_append'].__setitem__('extra', 'not accepted'),
                     lambda r: r.__setitem__('journal_sha256', '0'*64),
                     lambda r: r['record']['cas_transaction']['journal'].pop(module.FIELD),
                     lambda r: r['record']['cas_transaction']['journal'].__setitem__(module.FIELD, {}),
                     lambda r: r['record']['cas_transaction']['journal']['future'].append('foreign')]
        for mutate in mutations:
            response, request = self.receipt(); mutate(response)
            with self.assertRaises((ValueError, TypeError, KeyError)):
                module.restore_native_receipt(response, request)

    def test_capsule_elsewhere_cannot_silently_serialize_as_a_json_array(self):
        frozen = module.freeze_journal(self.journal())[module.FIELD]
        with self.assertRaises(TypeError):
            dump({'wrong_path': frozen})
        self.assertIsNone(module.chunks({'wrong_path': frozen}))

    def test_ascii_canonical_string_escape_growth_has_proven_bound(self):
        values = [{'unknown': '\\"'*8192}, self.sample(), {'\ud800': '\U0001f9da'*4096},
                  {'numbers': [1e15, 1e16, 5e-324, -0.0, 2**4096]}]
        for value in values:
            canonical = dump(value)
            escaped = dump(canonical.decode('ascii'))
            self.assertLessEqual(len(escaped), 2*len(canonical)+2)


if __name__ == '__main__':
    unittest.main()
