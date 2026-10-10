import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apex_cli
import cas_bank_cli


class CasBankCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / 'state.json'
        self.active, self.original = self.root / 'test', self.root / 'original'
        self.original.mkdir()
        self.output = self.root / 'proof.json'
        self.load = patch.object(cas_bank_cli.reusable_profile, 'load',
            return_value=(self.state, {'token': 'a' * 32}, self.active, self.original))
        self.load.start(); self.addCleanup(self.load.stop)

    def args(self, operation='begin', extra=()):
        return apex_cli.parser().parse_args(['cas-bank', operation, '--state', str(self.state),
            '--sim-id', '18446744073709551615', '--output', str(self.output), *extra])

    def intent(self, name, value):
        path = self.root / name
        path.write_bytes(json.dumps(value).encode('utf-8'))
        return str(path), hashlib.sha256(path.read_bytes()).hexdigest()

    def test_request_id_is_durable_before_one_native_submission(self):
        calls = []
        def request(state, action, **kwargs):
            self.assertEqual(state, self.state); self.assertEqual(action, 'cas_bank_begin')
            self.assertIsNone(kwargs['value'])
            kwargs['submission_observer'](action, 'b' * 32)
            written = json.loads(self.output.read_bytes())
            self.assertEqual(written['request_id'], 'b' * 32)
            self.assertEqual(written['outcome'], 'submission-possible')
            calls.append(action)
            return {'ok': True, 'native_appearance_written': False}
        result = cas_bank_cli.run(self.args(), request)
        self.assertTrue(result['ok']); self.assertEqual(calls, ['cas_bank_begin'])
        self.assertEqual(json.loads(self.output.read_bytes())['request_id'], 'b' * 32)

    def test_lost_poll_retains_request_identity_without_replay(self):
        calls = []
        def request(_state, action, **kwargs):
            calls.append(action); kwargs['submission_observer'](action, 'b' * 32)
            raise OSError('Poll disappeared after native operation')
        result = cas_bank_cli.run(self.args('observe', ['--expected-pending-sha256', 'c' * 64]), request)
        self.assertFalse(result['ok']); self.assertEqual(result['outcome'], 'unresolved')
        self.assertEqual(result['request_id'], 'b' * 32); self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads(self.output.read_bytes())['request_id'], 'b' * 32)

    def test_pre_transport_rejection_is_saved_as_not_submitted(self):
        result = cas_bank_cli.run(self.args(), lambda *a, **k: (_ for _ in ()).throw(ValueError('Old bridge')))
        self.assertEqual(result['outcome'], 'not-submitted'); self.assertIsNone(result['request_id'])

    def test_wrong_or_null_response_identity_cannot_erase_submitted_uuid(self):
        for index, returned_id in enumerate((None, 'f' * 32)):
            self.output = self.root/('wrong-id-%d.json' % index)
            def request(_state, action, **kwargs):
                kwargs['submission_observer'](action, 'b' * 32)
                return {'ok': True, 'request_id': returned_id}
            result = cas_bank_cli.run(self.args(), request)
            self.assertFalse(result['ok']); self.assertEqual(result['outcome'], 'unresolved')
            self.assertEqual(result['request_id'], 'b' * 32)
            self.assertEqual(result['submitted_request_id'], 'b' * 32)
            self.assertEqual(json.loads(self.output.read_bytes())['request_id'], 'b' * 32)

    def test_multiple_changed_forms_and_per_outfit_hair_intent_are_typed(self):
        path, digest = self.intent('decisions.json', [{'lane': '1', 'action': 'accept-returned'},
                                                    {'lane': '64', 'action': 'restore-original'}])
        hair, hair_hash = self.intent('hair.json', {'1': [{'category': 9, 'ordinal': 1,
            'outfit_id': '18446744073709551615'}]})
        args = self.args('prepare', ['--expected-pending-sha256', 'c' * 64,
            '--expected-raw-return-sha256', 'd' * 64, '--dispositions-file', path,
            '--dispositions-sha256', digest, '--hair-targets-file', hair, '--hair-targets-sha256', hair_hash])
        observed = []
        cas_bank_cli.run(args, lambda *a, **k: observed.append(json.loads(k['value'])) or {'ok': True})
        self.assertEqual(observed[0]['hair_targets']['1'][0]['outfit_id'], '18446744073709551615')
        self.assertEqual(len(observed[0]['dispositions']), 2)

    def test_appearance_bytes_duplicate_lanes_and_unknown_form_never_reach_transport(self):
        for index, decisions in enumerate((
            [{'lane': '1', 'action': 'accept-returned', 'fields': {'skin_tone': 5}}],
            [{'lane': '1', 'action': 'accept-returned'}, {'lane': '1', 'action': 'restore-original'}],
            [{'lane': '1024', 'action': 'accept-returned'}])):
            with self.subTest(index=index):
                path, digest = self.intent('bad%d.json' % index, decisions)
                args = self.args('prepare', ['--expected-pending-sha256', 'c' * 64,
                    '--expected-raw-return-sha256', 'd' * 64, '--dispositions-file', path, '--dispositions-sha256', digest])
                with self.assertRaises(ValueError):
                    cas_bank_cli.run(args, lambda *a, **k: self.fail('Invalid external payload submitted'))
                self.assertFalse(self.output.exists())

    def test_tampered_intent_and_duplicate_json_keys_refuse_before_command(self):
        path, digest = self.intent('decisions.json', [])
        Path(path).write_bytes(b'[{"lane":"1","lane":"2","action":"accept-returned"}]')
        args = self.args('prepare', ['--expected-pending-sha256', 'c' * 64,
            '--expected-raw-return-sha256', 'd' * 64, '--dispositions-file', path, '--dispositions-sha256', digest])
        with self.assertRaises(ValueError):
            cas_bank_cli.run(args, lambda *a, **k: self.fail('Tampered input submitted'))
        args.dispositions_sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            cas_bank_cli.run(args, lambda *a, **k: self.fail('Duplicate JSON submitted'))

    def test_existing_receipt_or_original_profile_output_prevents_any_command(self):
        self.output.write_bytes(b'prior')
        with self.assertRaises(ValueError):
            cas_bank_cli.run(self.args(), lambda *a, **k: self.fail('Existing output mutated'))
        self.assertEqual(self.output.read_bytes(), b'prior')
        self.output = self.original / 'no-write.json'
        with self.assertRaises(ValueError):
            cas_bank_cli.run(self.args(), lambda *a, **k: self.fail('Original profile mutated'))
        self.assertEqual(list(self.original.iterdir()), [])

    def test_extra_operation_hash_stale_shape_and_bad_ids_are_refused(self):
        for args in (self.args('begin', ['--expected-plan-sha256', 'e' * 64]),
                     self.args('commit', ['--expected-pending-sha256', 'c' * 64]),
                     self.args('observe', ['--expected-pending-sha256', 'C' * 64])):
            with self.assertRaises(ValueError):
                cas_bank_cli.run(args, lambda *a, **k: self.fail('Invalid command submitted'))
        args = self.args(); args.sim_id = '0007'
        with self.assertRaises(ValueError):
            cas_bank_cli.run(args, lambda *a, **k: self.fail('Invalid Sim ID submitted'))

    def test_hair_cannot_authorize_restored_lane_or_external_fields(self):
        for value in ({'64': [{'category': 0, 'ordinal': 0, 'outfit_id': '7'}]},
                      {'1': [{'category': 0, 'ordinal': 0, 'outfit_id': '7', 'hair': []}]},
                      {'1': [{'category': True, 'ordinal': 0, 'outfit_id': '7'}]},
                      {'1': [{'category': 0, 'ordinal': 0, 'outfit_id': '07'}]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cas_bank_cli._hair_targets(value, {'1'})


if __name__ == '__main__':
    unittest.main()
