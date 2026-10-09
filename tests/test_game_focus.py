from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from game_focus import input_result, validate


class GameFocusLeaseTests(unittest.TestCase):
    def fixture(self):
        binding = {'pid': 123, 'test_token': 'b' * 32, 'script_sha256': 'c' * 64}
        process = {'pid': 123, 'image': str(Path('Game/Bin/TS4_x64.exe')),
                   'creation_time': 12, 'session_id': 1, 'elevated': True,
                   'ui_access': False, 'integrity': 12288}
        pins = {'game_focus.py': 'd' * 64}
        request = {'schema': 1, 'nonce': 'a' * 32, 'expires_at': 190,
                   'state': 'external.json', 'state_sha256': 'e' * 64,
                   'sources': pins, 'binding': binding, 'game': process}
        return request, pins, dict(binding), process

    def test_exact_bound_bridge_process_and_fresh_lease_accepted(self):
        request, pins, identity, process = self.fixture()
        self.assertEqual(validate(request, 100, pins, identity, process, 'e' * 64), request['binding'])

    def test_expired_nonfinite_or_overlong_lease_refused(self):
        request, pins, identity, process = self.fixture()
        for expiry in (100, 99, 191, True, float('nan'), float('inf')):
            with self.subTest(expiry=expiry):
                altered = deepcopy(request); altered['expires_at'] = expiry
                with self.assertRaises(ValueError):
                    validate(altered, 100, pins, identity, process, 'e' * 64)

    def test_reused_pid_changed_image_or_token_identity_refused(self):
        request, pins, identity, process = self.fixture()
        for field, value in (('pid', 124), ('creation_time', 13), ('session_id', 2),
                             ('integrity', 8192), ('image', 'other.exe')):
            with self.subTest(field=field):
                changed = dict(process); changed[field] = value
                with self.assertRaises(ValueError):
                    validate(request, 100, pins, identity, changed, 'e' * 64)
        for field in identity:
            changed = dict(identity); changed[field] = 'wrong'
            with self.assertRaises(ValueError):
                validate(request, 100, pins, changed, process, 'e' * 64)

    def test_journal_or_sources_changed_after_preparation_refused(self):
        request, pins, identity, process = self.fixture()
        with self.assertRaises(ValueError):
            validate(request, 100, {}, identity, process, 'e' * 64)
        with self.assertRaises(ValueError):
            validate(request, 100, pins, identity, process, 'f' * 64)

    def test_wrong_shape_nonce_boolean_pid_or_arbitrary_process_refused(self):
        request, pins, identity, process = self.fixture()
        variants = []
        for field, value in (('nonce', '../a'), ('nonce', ''), ('schema', True)):
            altered = deepcopy(request); altered[field] = value; variants.append(altered)
        altered = deepcopy(request); altered['command'] = 'arbitrary'; variants.append(altered)
        altered = deepcopy(request); altered['binding']['pid'] = True; variants.append(altered)
        for altered in variants:
            with self.assertRaises(ValueError):
                validate(altered, 100, pins, identity, process, 'e' * 64)
        altered = deepcopy(request); altered['game']['image'] = process['image'] = 'other.exe'
        with self.assertRaises(ValueError):
            validate(altered, 100, pins, identity, process, 'e' * 64)

    def test_typed_one_input_accepts_only_existing_bounded_game_contract(self):
        request, pins, identity, process = self.fixture()
        request['input'] = {'request_id': 'f' * 32, 'argument':
            {'command': 1, 'x': 925, 'y': 648, 'width': 1278, 'height': 1376}}
        validate(request, 100, pins, identity, process, 'e' * 64)
        for field, value in (('command', 4), ('x', -1), ('y', 1376), ('width', True), ('height', 8193)):
            altered = deepcopy(request); altered['input']['argument'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(altered, 100, pins, identity, process, 'e' * 64)
        altered = deepcopy(request); altered['input']['request_id'] = '../bad'
        with self.assertRaises(ValueError):
            validate(altered, 100, pins, identity, process, 'e' * 64)
        altered = deepcopy(request); altered['input']['argument']['script'] = 'arbitrary'
        with self.assertRaises(ValueError):
            validate(altered, 100, pins, identity, process, 'e' * 64)

    def test_keyboard_contract_cannot_send_arbitrary_keys_or_mouse_values(self):
        request, pins, identity, process = self.fixture()
        request['input'] = {'request_id': 'f' * 32, 'argument':
            {'command': 2, 'x': 27, 'y': 0, 'width': 1278, 'height': 1376}}
        validate(request, 100, pins, identity, process, 'e' * 64)
        for field, value in (('x', 65), ('y', 1)):
            altered = deepcopy(request); altered['input']['argument'][field] = value
            with self.assertRaises(ValueError):
                validate(altered, 100, pins, identity, process, 'e' * 64)


class GameInputResultTests(unittest.TestCase):
    def completed(self):
        native = {'ok': True, 'request_id': 'f' * 32, 'input_state': 4,
                  'native_code': 0, 'input_submitted': True}
        return {'ok': True, 'host_binding_verified': True,
                'worker_receipt_verified': True, 'helper_started': True,
                'worker': {'input_sent': True, 'input_attempted': True,
                           'native_input': native}}

    def project(self, result):
        return input_result(result, 'f' * 32, Path('proof.json'), 'a' * 64)

    def test_bound_completed_input_retains_original_native_ack_and_proof(self):
        result = self.project(self.completed())
        self.assertTrue(result['ok'])
        self.assertTrue(result['input_submitted'])
        self.assertEqual(result['request_id'], 'f' * 32)
        self.assertEqual(result['elevated_input_proof_sha256'], 'a' * 64)

    def test_identity_source_journal_or_expiry_failure_preserves_completed_ack_but_refuses_success(self):
        for message in ('identity changed', 'source changed', 'journal changed', 'lease expired'):
            result = self.completed()
            result.update(ok=False, host_binding_verified=False, message=message)
            projected = self.project(result)
            with self.subTest(message=message):
                self.assertFalse(projected['ok'])
                self.assertEqual(projected['outcome'], 'unresolved')
                self.assertTrue(projected['input_submitted'])
                self.assertTrue(projected['native_acknowledgment']['ok'])
                self.assertEqual(projected['message'], message)

    def test_foreground_loss_after_ack_does_not_claim_success_or_no_input(self):
        result = self.completed(); result['ok'] = False
        projected = self.project(result)
        self.assertFalse(projected['ok'])
        self.assertTrue(projected['input_submitted'])
        self.assertEqual(projected['outcome'], 'unresolved')

    def test_launched_helper_exit_timeout_or_invalid_receipt_remains_unknown(self):
        for message in ('helper exited without a receipt', 'lease expired', 'invalid receipt'):
            projected = self.project({'ok': False, 'input_sent': False,
                'helper_launch_attempted': True, 'helper_started': True,
                'worker_receipt_verified': False, 'message': message})
            with self.subTest(message=message):
                self.assertIsNone(projected['input_submitted'])
                self.assertEqual(projected['outcome'], 'unresolved')

    def test_accepted_dispatch_without_handle_is_unknown(self):
        projected = self.project({'ok': False, 'helper_launch_attempted': True,
            'helper_started': False, 'helper_launch_refused': False})
        self.assertIsNone(projected['input_submitted'])
        self.assertEqual(projected['outcome'], 'unresolved')

    def test_windows_positively_refused_helper_launch_is_pre_input(self):
        projected = self.project({'ok': False, 'helper_launch_attempted': True,
            'helper_launch_refused': True, 'worker_receipt_verified': False})
        self.assertFalse(projected['input_submitted'])
        self.assertEqual(projected['outcome'], 'refused-before-input')

    def test_verified_worker_pre_input_refusal_is_distinct_from_response_loss(self):
        projected = self.project({'ok': False, 'worker_receipt_verified': True,
            'worker': {'input_sent': False, 'input_attempted': True,
                'native_input': {'ok': False, 'native_code': -2, 'input_state': 0,
                                 'input_submitted': False}}})
        self.assertFalse(projected['input_submitted'])
        self.assertEqual(projected['outcome'], 'refused-before-input')
        self.assertEqual(projected['native_acknowledgment']['native_code'], -2)

    def test_native_partial_or_lost_completion_is_unknown_despite_native_false_flag(self):
        projected = self.project({'ok': False, 'worker_receipt_verified': True,
            'worker': {'input_sent': None, 'input_attempted': True,
                'native_input': {'ok': False, 'native_code': 0, 'input_state': -1,
                                 'input_submitted': False}}})
        self.assertIsNone(projected['input_submitted'])
        self.assertEqual(projected['outcome'], 'unresolved')
        self.assertFalse(projected['native_acknowledgment']['input_submitted'])
