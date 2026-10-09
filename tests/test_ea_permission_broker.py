from copy import deepcopy
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ea_permission_broker as broker


class PermissionBrokerTests(unittest.TestCase):
    def fixture(self, root):
        target = {'pid': 123, 'image': str(root / 'EADesktop.exe'), 'creation_time': 123456,
                  'session_id': 1, 'elevated': True, 'ui_access': False, 'integrity': 12288}
        helper = dict(target, pid=os.getpid(), image=str(root / 'python.exe'))
        request = {'schema': 1, 'nonce': 'a' * 32, 'expires_at': 190.0,
                   'ea': target, 'source_sha256': broker.source_identity(), 'launch_context': None}
        def probe(pid):
            return deepcopy(target if pid == target['pid'] else helper)
        return target, helper, request, probe

    def test_diagnostics_are_read_only_and_report_integrity_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, helper, _request, _probe = self.fixture(root)
            medium = dict(helper, elevated=False, integrity=8192)
            probe = lambda pid: dict(target if pid == target['pid'] else medium)
            result = broker.diagnose(probe=probe, inventory=lambda: [123], expected=root / 'EADesktop.exe')
            self.assertTrue(result['diagnostic_only'])
            self.assertFalse(result['input_sent'])
            self.assertFalse(result['compatible_integrity'])
            self.assertTrue(result['normal_elevation_may_help'])
            rejected = broker.diagnose(probe=probe, inventory=lambda: [123, 123], expected=root / 'EADesktop.exe')
            self.assertFalse(rejected['ok'])

    def test_request_rejects_wrong_nonce_expiry_source_and_reused_pid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, _helper, request, probe = self.fixture(root)
            options = dict(pins=request['source_sha256'], probe=probe, expected=root / 'EADesktop.exe')
            self.assertEqual(broker.validate_request(request, root, 100, **options), target)
            for field, value in (('nonce', '../bad'), ('expires_at', 99), ('expires_at', 191), ('source_sha256', {})):
                invalid = deepcopy(request)
                invalid[field] = value
                with self.assertRaises(ValueError):
                    broker.validate_request(invalid, root, 100, **options)
            reused = lambda _pid: dict(target, creation_time=target['creation_time'] + 1)
            with self.assertRaisesRegex(ValueError, 'changed'):
                broker.validate_request(request, root, 100, pins=request['source_sha256'], probe=reused, expected=root / 'EADesktop.exe')

    def test_verified_same_install_compatibility32_worker_is_retained_but_not_a_main_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, helper, _request, _probe = self.fixture(root)
            worker = dict(target, pid=124, image=str(root / 'compatibility32' / 'EADesktop.exe'))
            probe = lambda pid: dict(target if pid == 123 else worker if pid == 124 else helper)
            for pids in ([123, 124], [124, 123]):
                with self.subTest(pids=pids):
                    result = broker.diagnose(probe=probe, inventory=lambda: pids, expected=root / 'EADesktop.exe')
                    self.assertTrue(result['ok']); self.assertFalse(result['input_sent'])
                    self.assertEqual(result['targets'], [target]); self.assertEqual(result['failures'], [])
                    self.assertEqual(result['ignored_processes'][0]['identity'], worker)

    def test_unknown_other_install_worker_failed_identity_and_confusing_main_still_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, helper, _request, _probe = self.fixture(root)
            variants = [dict(target, pid=124, image=str(root / 'other-install/compatibility32/EADesktop.exe')),
                dict(target, pid=124, image=str(root / 'compatibility64/EADesktop.exe')),
                dict(target, pid=124, image=str(root / 'compatibility32/EADesktop.exe'), session_id=2),
                dict(target, pid=124), OSError(5, 'Cannot inspect EA worker')]
            for alternate in variants:
                def probe(pid):
                    if pid == 124:
                        if isinstance(alternate, Exception): raise alternate
                        return dict(alternate)
                    return dict(target if pid == 123 else helper)
                with self.subTest(alternate=alternate):
                    result = broker.diagnose(probe=probe, inventory=lambda: [123, 124], expected=root / 'EADesktop.exe')
                    self.assertFalse(result['ok']); self.assertFalse(result['input_sent'])
                    self.assertTrue(result['failures'] or len(result['targets']) != 1)

    def test_sims_context_rejects_another_games_or_old_launch_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, _helper, _request, _probe = self.fixture(root)
            context = {'offer_id': 'OFB-EAST:fixture', 'content_id': '1015806',
                       'launcher': str(root / 'TS4_Launcher_x64.exe'), 'handoff_at': 100.0,
                       'log': str(root / 'EADesktop.log'), 'record_sha256': 'b' * 64, 'ea_pid': target['pid']}
            record = {key: context[key] for key in ('offer_id', 'content_id', 'launcher', 'record_sha256', 'ea_pid')}
            record.update(source='RTP', timestamp=100.0)
            broker.validate_launch_context(context, 101, target, read_record=lambda _path: record, expected_log=root / 'EADesktop.log')
            for key, value in (('content_id', 'another'), ('record_sha256', 'c' * 64), ('ea_pid', 124), ('timestamp', 1), ('source', 'Client')):
                changed = dict(record, **{key: value})
                with self.assertRaisesRegex(ValueError, 'changed'):
                    broker.validate_launch_context(context, 101, target, read_record=lambda _path: changed, expected_log=root / 'EADesktop.log')
            with self.assertRaisesRegex(ValueError, 'expired'):
                broker.validate_launch_context(context, 200, target, read_record=lambda _path: record, expected_log=root / 'EADesktop.log')

    def test_processing_record_offset_excludes_old_handoffs_and_detects_rotation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / 'EADesktop.log'
            line = '[2026-10-08T07:00:00.000Z] PID: 123 Processing launch request: offerId[OFB-EAST:fixture] contentId[1015806] exe[' + str(root / 'TS4_Launcher_x64.exe') + '] requestSource[RTP]\n'
            log.write_text(line)
            old_size = log.stat().st_size
            with self.assertRaisesRegex(broker.LaunchRecordPending, 'fresh'):
                broker.processing_record(log, old_size)
            with log.open('a') as stream:
                stream.write(line.replace('1015806', '1019999'))
            self.assertEqual(broker.processing_record(log, old_size)['content_id'], '1019999')
            log.write_text('rotated')
            with self.assertRaisesRegex(ValueError, 'rotated'):
                broker.processing_record(log, old_size)

    def test_same_handoff_observation_waits_only_for_missing_record(self):
        clock = [100.0]
        calls = []
        plan = {'account_launch_identity': 'fixture'}
        context = {'bound': 'exact current launch'}
        def read_context(actual, handoff_at, offset):
            calls.append((actual, handoff_at, offset))
            if len(calls) < 3:
                raise broker.LaunchRecordPending('not written yet')
            return context
        result = broker.wait_launch_context(plan, 99.0, 12345, read_context=read_context,
            monotonic=lambda: clock[0], pause=lambda delay: clock.__setitem__(0, clock[0] + delay))
        self.assertIs(result, context)
        self.assertEqual(calls, [(plan, 99.0, 12345)] * 3)
        self.assertAlmostEqual(clock[0], 100.4)

    def test_same_handoff_missing_record_timeout_is_bounded_without_input(self):
        clock = [0.0]
        def pending(*_args):
            raise broker.LaunchRecordPending('still absent')
        with self.assertRaisesRegex(broker.LaunchRecordPending, 'bounded'):
            broker.wait_launch_context({}, 0.0, 55, seconds=1, read_context=pending,
                monotonic=lambda: clock[0], pause=lambda delay: clock.__setitem__(0, clock[0] + delay))
        self.assertEqual(clock[0], 1.0)
        for invalid in (0, -1, 11, True, float('nan')):
            with self.assertRaisesRegex(ValueError, 'between'):
                broker.wait_launch_context({}, 0, 55, seconds=invalid,
                    read_context=lambda *_args: self.fail('Invalid duration cannot read launch evidence.'))

    def test_same_handoff_changed_malformed_rotated_or_expired_record_never_retries(self):
        for message in ('another game', 'unsupported record', 'log rotated', 'context expired'):
            read = Mock(side_effect=ValueError(message))
            with self.assertRaisesRegex(ValueError, message):
                broker.wait_launch_context({}, 99.0, 12345, read_context=read,
                    monotonic=lambda: 100.0, pause=lambda _delay: self.fail('A rejected record cannot wait.'))
            read.assert_called_once_with({}, 99.0, 12345)

    def test_delayed_log_append_builds_only_this_exact_account_handoff_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / 'EADesktop.log'
            launcher = root / 'TS4_Launcher_x64.exe'
            handoff = 1791442800.0  # 2026-10-08T07:00:00Z
            line = ('[2026-10-08T07:00:00.000Z] PID: 123 Processing launch request: '
                    'offerId[OFB-EAST:fixture] contentId[1015806] exe[' + str(launcher) + '] requestSource[RTP]\n')
            log.write_text(line.replace('07:00:00', '06:59:00'), encoding='utf-8')
            offset = log.stat().st_size
            plan = {'account_launch_identity': {'log': str(log), 'offer_id': 'OFB-EAST:fixture',
                                               'content_id': '1015806', 'executable': str(launcher)}}
            clock = [0.0]
            def append_record(delay):
                clock[0] += delay
                with log.open('a', encoding='utf-8') as stream:
                    stream.write(line)
            validate = broker.validate_launch_context
            with patch.object(broker.time, 'time', return_value=handoff + 1), \
                 patch.object(broker, 'validate_launch_context', side_effect=lambda context, now, target:
                              validate(context, now, target, expected_log=log)):
                context = broker.wait_launch_context(plan, handoff, offset,
                    monotonic=lambda: clock[0], pause=append_record)
            self.assertEqual(context['ea_pid'], 123)
            self.assertEqual(context['content_id'], '1015806')
            self.assertEqual(context['handoff_at'], handoff)
            self.assertEqual(context['launcher'], str(launcher.resolve()))
            self.assertEqual(context['record_sha256'], broker.processing_record(log, offset)['record_sha256'])
            self.assertEqual(clock[0], 0.2)

    def test_worker_claims_once_and_keeps_receipt_bound_to_source_and_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, _helper, request, probe = self.fixture(root)
            request_path = root / ('ea-broker-' + request['nonce'] + '.request.json')
            broker._json_exclusive(request_path, request)
            calls = []
            def acknowledge(actual, work, deadline, context):
                calls.append((actual, work, deadline))
                return {'ok': True, 'acknowledged': True, 'message': 'fixture exact dialog', 'nonce': 'cannot overwrite bound nonce'}
            with patch.object(broker, 'evidence_directory', return_value=root), \
                 patch.object(broker, 'validate_request', wraps=lambda req, work, now, probe: original_validate(req, work, now, probe=probe, expected=root / 'EADesktop.exe')):
                result = broker.worker(request_path, broker._digest(broker.__file__), probe=probe, acknowledge=acknowledge, clock=lambda: 100)
                with self.assertRaises(FileExistsError):
                    broker.worker(request_path, broker._digest(broker.__file__), probe=probe, acknowledge=acknowledge, clock=lambda: 100)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result['nonce'], request['nonce'])
            self.assertEqual(result['ea'], target)
            self.assertFalse(result['game_start_verified'])
            self.assertFalse(result['windows_uac_automated'])
            broker.validate_receipt(result, request, broker._digest(request_path))

    def test_worker_refuses_unelevated_helper_and_records_failure_without_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, helper, request, _probe = self.fixture(root)
            request_path = root / ('ea-broker-' + request['nonce'] + '.request.json')
            broker._json_exclusive(request_path, request)
            helper.update(elevated=False, integrity=8192)
            probe = lambda pid: dict(target if pid == 123 else helper)
            calls = []
            with patch.object(broker, 'evidence_directory', return_value=root), \
                 patch.object(broker, 'validate_request', wraps=lambda req, work, now, probe: original_validate(req, work, now, probe=probe, expected=root / 'EADesktop.exe')):
                result = broker.worker(request_path, broker._digest(broker.__file__), probe=probe,
                    acknowledge=lambda *args: calls.append(args), clock=lambda: 100)
            self.assertFalse(result['acknowledged'])
            self.assertFalse(result['ok'])
            self.assertEqual(calls, [])
            self.assertIn('compatible helper token', result['message'])

    def test_receipt_cannot_claim_other_nonce_process_or_game_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, helper, request, _probe = self.fixture(root)
            receipt = {'schema': 1, 'nonce': request['nonce'], 'request_sha256': 'b' * 64,
                       'ea': target, 'helper': helper, 'ok': True, 'acknowledged': True,
                       'launch_context': None,
                       'game_start_verified': False, 'windows_uac_automated': False}
            for name, value in (('nonce', 'c' * 32), ('ea', dict(target, pid=124)), ('game_start_verified', True), ('windows_uac_automated', True)):
                invalid = deepcopy(receipt)
                invalid[name] = value
                with self.assertRaises(ValueError):
                    broker.validate_receipt(invalid, request, 'b' * 64)
            invalid = deepcopy(receipt)
            invalid['helper']['integrity'] = 8192
            with self.assertRaisesRegex(ValueError, 'compatible'):
                broker.validate_receipt(invalid, request, 'b' * 64)

    def test_explicit_elevation_cancellation_and_timeout_do_not_acknowledge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, _helper, _request, _probe = self.fixture(root)
            diagnostic = lambda: {'ok': True, 'targets': [target]}
            def cancelled(*_args):
                raise OSError(1223, 'Normal UAC cancelled')
            with patch.object(broker, 'evidence_directory', return_value=root):
                refused = broker.elevate_once(root, diagnostic=diagnostic, runas=cancelled, nonce='a' * 32, clock=lambda: 100)
                clock = [100.0]
                timed = broker.elevate_once(root, diagnostic=diagnostic, runas=lambda *_args: None,
                    nonce='b' * 32, clock=lambda: clock[0], pause=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
            self.assertFalse(refused['acknowledged'])
            self.assertFalse(timed['acknowledged'])
            self.assertFalse(timed['game_start_verified'])
            self.assertIn('expired', timed['message'])
            self.assertEqual(len(list(root.glob('*.host-result.json'))), 2)

    def test_exited_helper_without_receipt_records_failure_without_waiting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, _helper, _request, _probe = self.fixture(root)
            with patch.object(broker, 'evidence_directory', return_value=root):
                result = broker.elevate_once(root, diagnostic=lambda: {'ok': True, 'targets': [target]},
                    runas=lambda *_args: None, nonce='d' * 32, clock=lambda: 100, exited=lambda _handle: True,
                    pause=lambda _seconds: self.fail('An exited helper cannot wait for another loop.'))
            self.assertFalse(result['acknowledged'])
            self.assertIn('exited', result['message'])
            self.assertTrue((root / ('ea-broker-' + 'd' * 32 + '.host-result.json')).is_file())

    def test_normal_shell_elevation_uses_runas_isolated_python_and_no_hidden_consent_approval(self):
        observed = {}
        def execute(pointer):
            info = pointer._obj
            observed.update(verb=info.lpVerb, file=info.lpFile, arguments=info.lpParameters,
                            mask=info.fMask, show=info.nShow)
            info.hProcess = 1234
            return True
        shell = SimpleNamespace(ShellExecuteExW=Mock(side_effect=execute))
        with patch.object(broker, 'os', SimpleNamespace(name='nt')), \
             patch.object(broker.ctypes, 'WinDLL', return_value=shell, create=True):
            handle = broker.shell_runas(Path('fixed request.json'), 'a' * 64)
        self.assertEqual(handle, 1234)
        self.assertEqual(observed['verb'], 'runas')
        self.assertEqual(observed['mask'], 0x40 | 0x100)
        self.assertEqual(observed['show'], 0)
        self.assertIn('-I -S', observed['arguments'])
        self.assertIn('--worker', observed['arguments'])
        self.assertIn('--source-hash ' + 'a' * 64, observed['arguments'])

    def test_late_normal_uac_approval_expires_before_claim_or_ea_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _target, _helper, request, probe = self.fixture(root)
            request_path = root / ('ea-broker-' + request['nonce'] + '.request.json')
            broker._json_exclusive(request_path, request)
            calls = []
            with patch.object(broker, 'evidence_directory', return_value=root):
                with self.assertRaisesRegex(ValueError, 'expired'):
                    broker.worker(request_path, broker._digest(broker.__file__), probe=probe,
                                  acknowledge=lambda *args: calls.append(args), clock=lambda: 200)
            self.assertEqual(calls, [])
            self.assertEqual(list(root.glob('*.claim.json')), [])

    def test_elevation_validates_durable_receipt_and_rejects_nonce_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target, helper, _request, _probe = self.fixture(root)
            def elevated(request_path, source_hash):
                request = json.loads(request_path.read_bytes())
                self.assertEqual(source_hash, request['source_sha256']['ea_permission_broker.py'])
                receipt = {'schema': 1, 'nonce': request['nonce'], 'request_sha256': broker._digest(request_path),
                           'ea': target, 'helper': helper, 'ok': True, 'acknowledged': True,
                           'launch_context': None,
                           'game_start_verified': False, 'windows_uac_automated': False}
                broker._json_exclusive(root / ('ea-broker-' + request['nonce'] + '.receipt.json'), receipt)
            with patch.object(broker, 'evidence_directory', return_value=root):
                result = broker.elevate_once(root, diagnostic=lambda: {'ok': True, 'targets': [target]}, runas=elevated, nonce='a' * 32, clock=lambda: 100)
                with self.assertRaises(FileExistsError):
                    broker.elevate_once(root, diagnostic=lambda: {'ok': True, 'targets': [target]}, runas=elevated, nonce='a' * 32, clock=lambda: 100)
            self.assertTrue(result['acknowledged'])
            self.assertFalse(result['game_start_verified'])

    def test_evidence_paths_refuse_protected_original_and_non_work_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / '.work'
            work.mkdir()
            other = root / 'other'
            other.mkdir()
            protected = work / 'The Sims 4 DO NOT FUCKING TOUCH!!!'
            protected.mkdir()
            self.assertEqual(broker.evidence_directory(work, root=work), work.resolve())
            for invalid in (other, protected):
                with self.assertRaises(ValueError):
                    broker.evidence_directory(invalid, root=work)


original_validate = broker.validate_request

if __name__ == '__main__':
    unittest.main()
