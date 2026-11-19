import base64
import copy
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from household_cli import blob, integer
from live_color_probe import chunks
from tray_complete_appearance import ACTIVE, complete
import tray_library


def fixed(number, value):
    from household_cli import varint
    return varint(number * 8 + 1) + struct.pack('<Q', value)


class CompleteLibraryAppearanceTests(unittest.TestCase):
    def setUp(self):
        names = ['sim_id', 'attributes', 'first_name', 'last_name', 'age', 'gender'] + list(ACTIVE)
        self.fields = {name: i + 1 for i, name in enumerate(names)}
        schema = []
        for name in names:
            row = dict(name=name, number=self.fields[name], type='bytes', repeated=False)
            if name == 'sim_id': row['type'] = 'fixed64'
            if name == 'attributes': row.update(type='message', message_type='Attributes')
            schema.append(row)
        self.catalog = dict(native_message_type='Sim', field_schemas={'Sim': schema, 'Attributes': [
            dict(name='occult_tracker', number=91, type='message', repeated=False),
            dict(name='trait_tracker', number=92, type='message', repeated=False)]})
        self.source = [self.sim(sid, b'canonical-' + str(sid).encode()) for sid in (11, 12)]
        self.target = [self.sim(sid, b'game-export') for sid in (21, 22)]
        self.records = [dict(sim_id=str(sid), native_sim=base64.b64encode(raw).decode(), native_sha256=hashlib.sha256(raw).hexdigest())
                        for sid, raw in zip((11, 12), self.source)]
        body = blob(3, b'Native household') + b''.join(blob(6, raw) for raw in self.target) + blob(500, b'future-family')
        payload = blob(1, body) + integer(3, 21) + blob(900, b'future-envelope')
        self.template = struct.pack('<IIII', 2, 12 + len(payload) + 5, 0, len(payload)) + payload + struct.pack('<I', 2) + b'\0'

    def sim(self, sid, value):
        f = self.fields
        # A nested unknown extension and future sibling must retain raw bytes.
        tracker = blob(7, b'forms-with-unknown-' + value) + blob(500001777, value)
        attributes = blob(91, tracker) + blob(92, b'six-occult-traits') + blob(777, b'native-other-tracker')
        return (fixed(f['sim_id'], sid) + blob(f['attributes'], attributes) + blob(f['first_name'], b'Same') +
                blob(f['last_name'], b'Family') + integer(f['age'], 16) + integer(f['gender'], 2) +
                b''.join(blob(f[name], value + b'-' + name.encode()) for name in ACTIVE) + blob(600, b'unknown-identity-' + str(sid).encode()))

    def test_real_envelope_and_each_unknown_form_extension_survive_distinct_member_completion(self):
        result, proof = complete(self.template, self.records, {'11': '21', '12': '22'}, self.catalog)
        actual = [base64.b64decode(raw) for raw in tray_library.sims(result)['sims']]
        for i, raw in enumerate(actual):
            self.assertIn(b'canonical-' + str(i + 11).encode(), raw)
            self.assertIn(b'unknown-identity-' + str(i + 21).encode(), raw)
            self.assertIn(b'native-other-tracker', raw)
            self.assertNotIn(b'game-export', raw)
        self.assertIn(b'future-envelope', result); self.assertIn(b'future-family', result)
        self.assertEqual(result[-5:], self.template[-5:])
        self.assertFalse(proof['native_library_load_verified'])
        self.assertEqual([r['tray_sim_id'] for r in proof['members']], ['21', '22'])

    def test_incomplete_duplicate_or_wrong_bijection_refused(self):
        for mapping in ({'11': '21'}, {'11': '21', '12': '21'}, {'11': '21', '12': '99'}):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                complete(self.template, self.records, mapping, self.catalog)

    def test_hash_identity_or_demographic_mismatch_refused(self):
        changed = copy.deepcopy(self.records); changed[0]['native_sha256'] = '0' * 64
        with self.assertRaises(ValueError): complete(self.template, changed, {'11': '21', '12': '22'}, self.catalog)
        changed = copy.deepcopy(self.records); changed[0]['sim_id'] = '99'
        with self.assertRaises(ValueError): complete(self.template, changed, {'99': '21', '12': '22'}, self.catalog)
        raw = self.source[0].replace(b'Same', b'Diff')
        changed = copy.deepcopy(self.records); changed[0].update(native_sim=base64.b64encode(raw).decode(), native_sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError, 'demographic'):
            complete(self.template, changed, {'11': '21', '12': '22'}, self.catalog)

    def test_missing_future_schema_contract_and_duplicate_schema_number_refused(self):
        changed = copy.deepcopy(self.catalog); changed['field_schemas']['Sim'].pop()
        with self.assertRaisesRegex(ValueError, 'incomplete'): complete(self.template, self.records, {'11': '21', '12': '22'}, changed)
        changed = copy.deepcopy(self.catalog); changed['field_schemas']['Sim'][0]['number'] = 2
        with self.assertRaisesRegex(ValueError, 'duplicate'): complete(self.template, self.records, {'11': '21', '12': '22'}, changed)

    def test_v1_or_unrecognized_native_footer_refused(self):
        raw = bytearray(self.template); struct.pack_into('<I', raw, 0, 1)
        with self.assertRaises(ValueError): complete(bytes(raw), self.records, {'11': '21', '12': '22'}, self.catalog)
        with self.assertRaisesRegex(ValueError, 'footer'):
            complete(self.template[:-1] + b'X', self.records, {'11': '21', '12': '22'}, self.catalog)


if __name__ == '__main__': unittest.main()
