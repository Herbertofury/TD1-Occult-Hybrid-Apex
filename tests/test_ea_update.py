from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ea_update as update


class FakeNative:
    def __init__(self, window):
        self.window = window
        self.captures = []

    def windows(self):
        return [deepcopy(self.window)]

    def capture(self, window, path):
        if window != self.window:
            raise ValueError('Window changed')
        raw = ('verified captured EA pixels ' + path.suffix).encode()
        with path.open('xb') as stream:
            stream.write(raw)
        self.captures.append(path)
        return hashlib.sha256(raw).hexdigest()


class EaUpdateTests(unittest.TestCase):
    def fixture(self, work):
        target = {'pid': 123, 'image': str(work / 'EADesktop.exe'), 'creation_time': 123456,
                  'session_id': 1, 'elevated': True, 'ui_access': False, 'integrity': 12288}
        helper = dict(target, pid=os.getpid(), image=str(work / 'python.exe'))
        profile = {'state': str(work / 'reusable-profile-session.json'), 'state_sha256': 'b' * 64,
                   'token': 'c' * 32, 'profile': str(work / 'The Sims 4'),
                   'protected_original': str(work / update.test_profile.PROTECTED_NAME), 'marker_sha256': 'd' * 64}
        request = {'schema': 1, 'operation': update.OPERATION, 'nonce': 'a' * 32,
                   'expires_at': 160.0, 'ea': target, 'source_sha256': update.source_identity(),
                   'profile': profile, 'ea_version': '13.796.0.6309'}
        window = {'pid': 123, 'hwnd': 987, 'width': 1280, 'height': 1408, 'class': 'Qt5152QWindowOwnDCIcon'}
        surface = {'pid': 123, 'hwnd': 987, 'name': 'RESTART REQUIRED', 'type': 'ControlType.Button',
                   'enabled': True, 'offscreen': False, 'invoke_available': True,
                   'runtime_id': [42, 987, 7], 'bounds': [3900.0, 10.0, 120.0, 25.0]}
        def probe(pid):
            return deepcopy(target if pid == 123 else helper)
        return target, helper, profile, request, window, surface, probe

    def observation(self):
        text = update.BANNER_PREFIX + '1 day. Restart app'
        words, x = [], 20
        for word in text.split(' '):
            width = len(word) * 7
            words.append({'text': word, 'x': x, 'y': 65.0, 'width': width, 'height': 18.0})
            x += width + 5
        return {'ok': True, 'width': 1280, 'height': 1408,
                'preprocessing': {'coordinates': 'original-viewport', 'requested_scale': 2,
                                  'scale': 2, 'ocr_width': 2560, 'ocr_height': 2816},
                'lines': [{'text': 'RESTART REQUIRED', 'words': [
                    {'text': 'RESTART', 'x': 5, 'y': 5, 'width': 50, 'height': 18},
                    {'text': 'REQUIRED', 'x': 60, 'y': 5, 'width': 50, 'height': 18}]},
                    {'text': text, 'words': words}]}

    def run_worker(self, work, request, probe, profile, window, surface, **options):
        path = work / ('ea-update-' + request['nonce'] + '.request.json')
        update.broker._json_exclusive(path, request)
        native = options.pop('native', FakeNative(window))
        uia = options.pop('uia', Mock(side_effect=lambda *_args, **_kwargs: deepcopy(surface)))
        recognize = options.pop('recognize', Mock(side_effect=lambda *_args, **_kwargs: self.observation()))
        with patch.object(update.broker, 'EA_IMAGE', Path(request['ea']['image'])), \
             patch.object(update.broker, 'evidence_directory', side_effect=lambda value: Path(value).resolve()):
            result = update.worker(path, update.digest(update.__file__), update.digest(path), probe=probe,
                profile_check=lambda _state: deepcopy(profile), closed_guard=options.pop('closed_guard', Mock()),
                native_factory=lambda pids: native if pids == [123] else self.fail('Other PID targeted'),
                recognize=recognize, uia=uia, clock=options.pop('clock', lambda: 100), **options)
        return result, native, uia, path

    def test_complete_banner_uses_native_last_two_word_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary:
            _target, _helper, _profile, _request, window, _surface, _probe = self.fixture(Path(temporary))
            observation = self.observation()
            point = update.restart_point(observation, window)
            first, last = observation['lines'][-1]['words'][-2:]
            self.assertEqual(point, (round((first['x'] + last['x'] + last['width']) / 2), 74))

    def test_heading_accepts_only_one_known_arrow_ocr_token_before_exact_words(self):
        with tempfile.TemporaryDirectory() as temporary:
            window = self.fixture(Path(temporary))[4]
            expected = update.restart_point(self.observation(), window)
            for prefix in ('C', 'e', '↻', '⟳'):
                observation = self.observation()
                heading = observation['lines'][0]
                for word in heading['words']: word['x'] += 15
                heading['words'].insert(0, {'text': prefix, 'x': 5, 'y': 5, 'width': 10, 'height': 18})
                heading['text'] = prefix + ' RESTART REQUIRED'
                with self.subTest(prefix=prefix):
                    self.assertEqual(update.restart_point(observation, window), expected)

    def test_heading_rejects_unknown_multiple_or_unmeasured_prefix_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            window = self.fixture(Path(temporary))[4]
            for prefix in ('X', 'Restart', 'C C', 'C e', 'e C'):
                observation = self.observation()
                heading = observation['lines'][0]
                icon_words = [{'text': word, 'x': 5 + index * 12, 'y': 5, 'width': 10, 'height': 18}
                              for index, word in enumerate(prefix.split())]
                for word in heading['words']: word['x'] += 30
                heading['words'] = icon_words + heading['words']
                heading['text'] = prefix + ' RESTART REQUIRED'
                with self.subTest(prefix=prefix), self.assertRaisesRegex(ValueError, 'unique exact'):
                    update.restart_point(observation, window)
            unmeasured = self.observation(); unmeasured['lines'][0]['text'] = 'C RESTART REQUIRED'
            with self.assertRaisesRegex(ValueError, 'unique exact'):
                update.restart_point(unmeasured, window)
            duplicate = self.observation()
            icon_heading = deepcopy(duplicate['lines'][0])
            icon_heading['text'] = 'C RESTART REQUIRED'
            icon_heading['words'].insert(0, {'text': 'C', 'x': 1, 'y': 5, 'width': 2, 'height': 18})
            duplicate['lines'].append(icon_heading)
            with self.assertRaisesRegex(ValueError, 'unique exact'):
                update.restart_point(duplicate, window)

    def test_partial_ambiguous_scaled_and_outside_banner_never_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            window = self.fixture(Path(temporary))[4]
            variants = []
            partial = self.observation(); partial['lines'][1]['text'] = 'Restart app'; variants.append(partial)
            duplicate = self.observation(); duplicate['lines'].append(deepcopy(duplicate['lines'][1])); variants.append(duplicate)
            duplicate = self.observation(); duplicate['lines'].append(deepcopy(duplicate['lines'][0])); variants.append(duplicate)
            scaled = self.observation(); scaled['preprocessing']['coordinates'] = 'scaled-bitmap'; variants.append(scaled)
            wrong_viewport = self.observation(); wrong_viewport['width'] = 640; variants.append(wrong_viewport)
            forged = self.observation(); forged['lines'][1]['words'][-1]['text'] = 'other'; variants.append(forged)
            outside = self.observation(); outside['lines'][1]['words'][-1]['y'] = 1000; variants.append(outside)
            infinite = self.observation(); infinite['lines'][1]['words'][-1]['x'] = float('inf'); variants.append(infinite)
            boolean = self.observation(); boolean['lines'][1]['words'][-1]['x'] = True; variants.append(boolean)
            for observation in variants:
                with self.subTest(observation=observation), self.assertRaises(ValueError):
                    update.restart_point(observation, window)

    def test_typed_request_rejects_expiry_source_lifecycle_and_profile_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            target, _helper, profile, request, _window, _surface, probe = self.fixture(Path(temporary))
            options = {'pins': request['source_sha256'], 'probe': probe,
                       'profile_check': lambda _state: profile, 'expected': target['image']}
            self.assertEqual(update.validate_request(request, 100, **options), target)
            for key, value in (('nonce', '../escape'), ('expires_at', 100), ('expires_at', 161),
                               ('expires_at', float('nan')), ('expires_at', True), ('operation', 'arbitrary-command'),
                               ('source_sha256', {}), ('ea_version', 'untyped')):
                invalid = deepcopy(request); invalid[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    update.validate_request(invalid, 100, **options)
            for key, value in (('creation_time', 123457), ('session_id', 2), ('integrity', 8192), ('image', 'other.exe')):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'process changed'):
                    update.validate_request(request, 100, **dict(options, probe=lambda _pid: dict(target, **{key: value})))
            with self.assertRaisesRegex(ValueError, 'profile changed'):
                update.validate_request(request, 100, **dict(options, profile_check=lambda _state: dict(profile, state_sha256='e' * 64)))
            invalid = deepcopy(request); invalid['command'] = 'arbitrary'
            with self.assertRaisesRegex(ValueError, 'schema'):
                update.validate_request(invalid, 100, **options)

    def test_worker_two_fresh_captures_and_uia_observations_invoke_once_and_claim_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            target, _helper, profile, request, window, surface, probe = self.fixture(work)
            result, native, uia, path = self.run_worker(work, request, probe, profile, window, surface)
            self.assertTrue(result['input_attempted']); self.assertTrue(result['input_sent'])
            self.assertFalse(result['restart_verified']); self.assertFalse(result['update_verified'])
            self.assertFalse(result['windows_uac_automated'])
            self.assertEqual(len(native.captures), 2)
            self.assertEqual(len(uia.call_args_list), 3)
            self.assertEqual([call.kwargs.get('invoke', False) for call in uia.call_args_list], [False, False, True])
            self.assertTrue((work / ('ea-update-' + request['nonce'] + '.intent.json')).is_file())
            with patch.object(update.broker, 'evidence_directory', side_effect=lambda value: Path(value).resolve()):
                self.assertIs(update.validate_receipt(result, request, update.digest(path)), result)
                with patch.object(update.broker, 'EA_IMAGE', Path(target['image'])), self.assertRaises(FileExistsError):
                    update.worker(path, update.digest(update.__file__), update.digest(path), probe=probe,
                                  profile_check=lambda _state: profile, clock=lambda: 100)
            self.assertEqual(len(uia.call_args_list), 3)

    def test_ambiguous_banner_closed_game_and_unsupported_uia_fail_without_invocation(self):
        cases = ('banner', 'game', 'uia', 'window')
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                _target, _helper, profile, request, window, surface, probe = self.fixture(work)
                options = {}
                if case == 'banner':
                    observation = self.observation(); observation['lines'].append(deepcopy(observation['lines'][1]))
                    options['recognize'] = lambda *_args, **_kwargs: observation
                elif case == 'game':
                    options['closed_guard'] = Mock(side_effect=RuntimeError('The Sims 4 is still running'))
                elif case == 'uia':
                    surface['invoke_available'] = False
                else:
                    native = FakeNative(window); native.windows = lambda: [window, dict(window, hwnd=988)]
                    options['native'] = native
                result, _native, uia, _path = self.run_worker(work, request, probe, profile, window, surface, **options)
                self.assertFalse(result['ok']); self.assertFalse(result['input_sent'])
                self.assertFalse(result['input_attempted'])
                self.assertFalse(any(call.kwargs.get('invoke') for call in uia.call_args_list))
                self.assertEqual(list(work.glob('*.intent.json')), [])

    def test_fresh_link_or_uia_change_refuses_input(self):
        for changed in ('point', 'uia'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                _target, _helper, profile, request, window, surface, probe = self.fixture(work)
                options = {}
                if changed == 'point':
                    initial, fresh = self.observation(), self.observation()
                    for word in fresh['lines'][1]['words'][-2:]: word['x'] += 10
                    options['recognize'] = Mock(side_effect=[initial, fresh])
                else:
                    options['uia'] = Mock(side_effect=[surface, dict(surface, runtime_id=[42, 987, 8])])
                result, _native, uia, _path = self.run_worker(work, request, probe, profile, window, surface, **options)
                self.assertFalse(result['input_sent']); self.assertFalse(result['input_attempted'])
                self.assertFalse(any(call.kwargs.get('invoke') for call in uia.call_args_list))

    def test_expiry_during_second_ocr_leaves_no_intent_or_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            _target, _helper, profile, request, window, surface, probe = self.fixture(work)
            clock = [100.0]; reads = []
            def recognize(*_args, **_kwargs):
                reads.append(True)
                if len(reads) == 2: clock[0] = 160
                return self.observation()
            result, _native, uia, _path = self.run_worker(work, request, probe, profile, window, surface,
                clock=lambda: clock[0], recognize=recognize)
            self.assertFalse(result['input_sent']); self.assertFalse(result['input_attempted'])
            self.assertIn('expired', result['message']); uia.assert_not_called()

    def test_unelevated_or_other_session_helper_has_no_capture_or_input(self):
        for change in ({'elevated': False}, {'session_id': 2}, {'integrity': 8192}, {'ui_access': True}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                target, helper, profile, request, window, surface, _probe = self.fixture(work)
                helper.update(change)
                result, native, uia, _path = self.run_worker(work, request,
                    lambda pid: target if pid == 123 else helper, profile, window, surface)
                self.assertFalse(result['input_sent']); self.assertFalse(result['input_attempted'])
                self.assertEqual(native.captures, []); uia.assert_not_called()

    def test_worker_changed_source_request_bytes_or_late_approval_fail_before_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            _target, _helper, profile, request, _window, _surface, probe = self.fixture(work)
            path = work / ('ea-update-' + request['nonce'] + '.request.json')
            update.broker._json_exclusive(path, request)
            with patch.object(update.broker, 'evidence_directory', side_effect=lambda value: Path(value).resolve()):
                for source_hash, request_hash, now in (('0' * 64, update.digest(path), 100),
                    (update.digest(update.__file__), '0' * 64, 100), (update.digest(update.__file__), update.digest(path), 160)):
                    with self.assertRaises(ValueError):
                        update.worker(path, source_hash, request_hash, probe=probe,
                                      profile_check=lambda _state: profile, clock=lambda: now)
            self.assertEqual(list(work.glob('*.claim.json')), [])
            self.assertEqual(list(work.glob('*.intent.json')), [])

    def test_receipt_rejects_wrong_nonce_source_and_unobserved_restart_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            _target, _helper, profile, request, window, surface, probe = self.fixture(work)
            receipt, _native, _uia, path = self.run_worker(work, request, probe, profile, window, surface)
            for key, value in (('nonce', 'f' * 32), ('source_sha256', {}), ('restart_verified', True),
                               ('update_verified', True), ('windows_uac_automated', True), ('input_attempted', False)):
                invalid = deepcopy(receipt); invalid[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    update.validate_receipt(invalid, request, update.digest(path))

    def test_native_uia_script_is_fixed_and_has_no_pointer_fallback(self):
        self.assertEqual(update.UIA_SCRIPT.count('$second.pattern.Invoke()'), 1)
        self.assertIn("$_.Current.Name -ceq 'RESTART REQUIRED'", update.UIA_SCRIPT)
        self.assertIn('Assert-Lifecycle', update.UIA_SCRIPT)
        self.assertNotIn('SendInput', update.UIA_SCRIPT)
        self.assertNotIn('Stop-Process', update.UIA_SCRIPT)

    def test_fixed_profile_binding_reads_protected_original_without_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            profile = root / 'The Sims 4'; profile.mkdir()
            (profile / 'Mods').mkdir()
            original = root / update.test_profile.PROTECTED_NAME; original.mkdir()
            sentinel = original / 'owner-save.save'; sentinel.write_bytes(b'protected owner original')
            before = (sentinel.read_bytes(), sentinel.stat().st_mtime_ns)
            state = root / 'reusable-profile-session.json'
            token = 'a' * 32
            (profile / update.test_profile.MARKER).write_text(json.dumps({'token': token}))
            state.write_text(json.dumps({'schema': 2, 'mode': 'reusable-test-only', 'token': token,
                'profile': str(profile), 'protected_original': str(original), 'phase': 'active', 'artifacts': []}))
            with patch.object(update, 'DEFAULT_STATE', state):
                binding = update.profile_binding(state)
                self.assertEqual(binding['state_sha256'], update.digest(state))
                self.assertEqual(binding['protected_original'], str(original))
                other = root / 'other.json'; other.write_bytes(state.read_bytes())
                with self.assertRaisesRegex(ValueError, 'fixed reusable'):
                    update.profile_binding(other)
                (profile / update.test_profile.MARKER).write_text(json.dumps({'token': 'b' * 32}))
                with self.assertRaisesRegex(ValueError, 'disposable test profile'):
                    update.profile_binding(state)
            self.assertEqual((sentinel.read_bytes(), sentinel.stat().st_mtime_ns), before)

    def test_host_validates_worker_receipt_and_requires_separate_restart_observation(self):
        for restarted in (True, False):
            with self.subTest(restarted=restarted), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                target, _helper, profile, _request, window, surface, probe = self.fixture(work)
                closed = Mock()
                def runas(path, source_hash, request_hash):
                    update.worker(path, source_hash, request_hash, probe=probe,
                        profile_check=lambda _state: profile, closed_guard=closed,
                        native_factory=lambda _pids: FakeNative(window),
                        recognize=lambda *_args, **_kwargs: self.observation(),
                        uia=lambda *_args, **_kwargs: deepcopy(surface), clock=lambda: 100)
                observation = {'restart_verified': restarted, 'update_verified': restarted,
                               'message': 'Observed lifecycle' if restarted else 'No new lifecycle'}
                observe = Mock(return_value=observation)
                with patch.object(update.broker, 'EA_IMAGE', Path(target['image'])), \
                     patch.object(update.broker, 'evidence_directory', side_effect=lambda value: Path(value).resolve()):
                    result = update.restart_once(work, profile['state'],
                        diagnostic=lambda: {'ok': True, 'targets': [target]}, runas=runas,
                        closed_guard=closed, profile_check=lambda _state: profile,
                        clock=lambda: 100, nonce='a' * 32, version=lambda _image: '13.796.0.6309', observe=observe)
                    with self.assertRaises(FileExistsError):
                        update.restart_once(work, profile['state'], diagnostic=lambda: {'ok': True, 'targets': [target]},
                            runas=runas, closed_guard=closed, profile_check=lambda _state: profile,
                            nonce='a' * 32, version=lambda _image: '13.796.0.6309')
                self.assertTrue(result['input_sent']); self.assertTrue(result['worker_receipt_verified'])
                self.assertEqual(result['ok'], restarted); self.assertEqual(result['restart_verified'], restarted)
                self.assertEqual(result['update_verified'], restarted)
                observe.assert_called_once_with(target, '13.796.0.6309', seconds=60)

    def test_shell_runas_uses_only_fixed_isolated_worker_and_hashes(self):
        captured = {}
        def execute(pointer):
            info = pointer._obj
            captured.update(verb=info.lpVerb, arguments=info.lpParameters, show=info.nShow, mask=info.fMask)
            info.hProcess = 999
            return True
        shell = SimpleNamespace(ShellExecuteExW=Mock(side_effect=execute))
        with patch.object(update, 'os', SimpleNamespace(name='nt')), \
             patch.object(update.ctypes, 'WinDLL', return_value=shell, create=True):
            result = update.shell_runas(Path('fixed request.json'), 'a' * 64, 'b' * 64)
        self.assertEqual(result, 999)
        self.assertEqual(captured['verb'], 'runas'); self.assertEqual(captured['mask'], 0x140)
        self.assertEqual(captured['show'], 0)
        self.assertIn('-I -S', captured['arguments']); self.assertIn('--worker', captured['arguments'])
        self.assertIn('--source-hash ' + 'a' * 64, captured['arguments'])
        self.assertIn('--request-hash ' + 'b' * 64, captured['arguments'])

    def test_default_inspection_no_compatible_integrity_never_requests_elevation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target, _helper, profile, _request, _window, _surface, _probe = self.fixture(Path(temporary))
            native = Mock(side_effect=AssertionError('Incompatible token cannot capture'))
            with patch.object(update, 'profile_binding', return_value=profile), patch.object(update, 'shell_runas') as runas:
                result = update.inspect(diagnostic=lambda: {'ok': True, 'targets': [target], 'compatible_integrity': False},
                                        native_factory=native)
            self.assertTrue(result['diagnostic_only']); self.assertFalse(result['input_sent'])
            self.assertFalse(result['pending_update_confirmed']); native.assert_not_called(); runas.assert_not_called()

    def test_observation_requires_old_lifecycle_gone_and_changed_installed_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.fixture(Path(temporary))[0]
            new = dict(target, pid=456, creation_time=123999)
            def gone(_pid):
                raise OSError(87, 'No old PID')
            with patch.object(update.broker, 'EA_IMAGE', Path(target['image'])):
                result = update.observe_restart(target, '13.796.0.6309', seconds=1, probe=gone,
                    diagnostic=lambda: {'ok': True, 'targets': [new]}, version=lambda _image: '13.805.2.6319')
            self.assertTrue(result['restart_verified']); self.assertTrue(result['update_verified'])
            self.assertTrue(result['old_process_gone']); self.assertEqual(result['new_ea'], new)

    def test_delivery_same_pid_banner_or_access_denial_is_never_restart_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.fixture(Path(temporary))[0]
            clock = [0.0]
            result = update.observe_restart(target, '13.796.0.6309', seconds=1, probe=lambda _pid: target,
                diagnostic=lambda: {'ok': True, 'targets': [target]}, monotonic=lambda: clock[0],
                pause=lambda delay: clock.__setitem__(0, clock[0] + delay))
            self.assertFalse(result['restart_verified']); self.assertFalse(result['update_verified'])
            self.assertEqual(clock[0], 1)
            def denied(_pid):
                raise OSError(5, 'Access denied')
            result = update.observe_restart(target, '13.796.0.6309', seconds=1, probe=denied)
            self.assertFalse(result['old_process_gone']); self.assertFalse(result['restart_verified'])

    def test_restart_with_same_or_unknown_version_does_not_claim_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = self.fixture(Path(temporary))[0]
            new = dict(target, creation_time=123999)  # An exact reused PID has a new lifecycle.
            with patch.object(update.broker, 'EA_IMAGE', Path(target['image'])):
                for version in ('13.796.0.6309', None):
                    result = update.observe_restart(target, '13.796.0.6309', seconds=1, probe=lambda _pid: new,
                        diagnostic=lambda: {'ok': True, 'targets': [new]}, version=lambda _image: version)
                    self.assertTrue(result['restart_verified']); self.assertFalse(result['update_verified'])

    def test_cancelled_normal_elevation_and_timeout_preserve_no_restart_claim(self):
        for cancellation in (True, False):
            with self.subTest(cancellation=cancellation), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                target, _helper, profile, _request, _window, _surface, _probe = self.fixture(work)
                clock = [100.0]
                def runas(*_args):
                    if cancellation: raise OSError(1223, 'Normal UAC cancelled')
                with patch.object(update.broker, 'evidence_directory', side_effect=lambda value: Path(value).resolve()):
                    result = update.restart_once(work, profile['state'], diagnostic=lambda: {'ok': True, 'targets': [target]},
                        closed_guard=lambda: None, profile_check=lambda _state: profile, runas=runas, clock=lambda: clock[0],
                        pause=lambda delay: clock.__setitem__(0, clock[0] + delay), exited=lambda _handle: False,
                        version=lambda _image: '13.796.0.6309', nonce='a' * 32,
                        observe=Mock(side_effect=AssertionError('No receipt cannot observe a claimed restart')))
                self.assertFalse(result['input_sent']); self.assertFalse(result['restart_verified'])
                self.assertFalse(result['update_verified']); self.assertFalse(result['worker_receipt_verified'])
                self.assertEqual(len(list(work.glob('*.host-result.json'))), 1)


if __name__ == '__main__':
    unittest.main()
