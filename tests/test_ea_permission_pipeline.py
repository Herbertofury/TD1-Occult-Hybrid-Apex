from datetime import datetime
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ea_permission_broker as broker


class PermissionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.log = self.root / 'EADesktop.log'
        self.launcher = self.root / 'Game' / 'Bin' / 'TS4_Launcher_x64.exe'
        self.lines = [
            self.line('00.999', 'Handling game launch request (InitialRequest): IDs=[offerKey.offerId=[], offerId=[], contentIds=[1015806], slug=[]], offerKey.externalType=[], requestOwner=[EA], requestSource=[RTP], gameArguments=[]'),
            self.line('01.000', '[GAME] Got exePath=[' + str(self.launcher) + '] cmdArgs=[] from defaultLauncher.'),
            self.line('01.000', '[GAME] Issuing launch: workingDirectory[' + str(self.launcher.parent) + '] offer[OFB-EAST:109552414] content[1015806] gameArgs []'),
            self.line('01.001', 'Successful launch. IDs: offerKey.offerId=[OFB-EAST:109552414], offerId=[], contentIds=[1015806], slug=[the-sims-4]'),
        ]
        self.timestamp = datetime.fromisoformat('2026-10-08T19:05:00.999+00:00').timestamp()

    def line(self, second, message, pid=6012, tid=46420):
        return ('   384\t[2026-10-08T19:05:' + second + 'Z]\tPID:  ' + str(pid) +
                '\tTID: ' + str(tid) + '\tINFO    \t(fixture::launch)\t' + message)

    def legacy(self, content='1015806'):
        return ('[2026-10-08T19:04:00.000Z] PID: 6012 Processing launch request: '
                'offerId[OFB-EAST:109552414] contentId[' + content + '] exe[' +
                str(self.launcher) + '] requestSource[RTP]')

    def serialization(self, second='01.023'):
        return self.line(second, 'Processing launch request: offerId[OFB-EAST:109552414] contentId[1015806] exe[' +
                         str(self.launcher) + '] cwd[' + str(self.launcher.parent) +
                         '] args[] locale[en_US] isTrial[false] isElevated[false] requestSource[RTP] isLauncherElevated[false]')

    def parse(self, lines, offset=0):
        self.log.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return broker.processing_record(self.log, offset)

    def reject(self, lines):
        with self.assertRaises(ValueError) as error:
            self.parse(lines)
        self.assertNotIsInstance(error.exception, broker.LaunchRecordPending)

    def test_exact_four_record_pipeline_and_matching_repeat_keep_stable_digest(self):
        expected = {'offer_id': 'OFB-EAST:109552414', 'content_id': '1015806',
                    'launcher': str(self.launcher.resolve()), 'source': 'RTP',
                    'ea_pid': 6012, 'timestamp': self.timestamp,
                    'record_sha256': hashlib.sha256('\n'.join(self.lines).encode()).hexdigest()}
        self.assertEqual(self.parse(self.lines), expected)
        repeated = self.lines + [self.lines[1].replace('01.000', '01.001')]
        self.assertEqual(self.parse([self.legacy(), 'unrelated status'] + repeated, offset=None), expected)
        self.assertEqual(broker.processing_record(self.log), expected)

    def test_real_pipeline_matching_legacy_postlude_is_one_intent_in_both_read_modes(self):
        # EA 13.805: InitialRequest/defaultLauncher/Issuing/Successful,
        # repeated lookup, then legacy serialization 24 ms after InitialRequest.
        sequence = self.lines + [self.lines[1].replace('01.000', '01.001'), self.serialization()]
        real = [line.replace('19:05:00.999', '19:38:44.265')
                .replace('19:05:01.000', '19:38:44.266')
                .replace('19:05:01.001', '19:38:44.267')
                .replace('19:05:01.023', '19:38:44.289')
                .replace('PID:  6012', 'PID: 31300').replace('TID: 46420', 'TID: 47220')
                for line in sequence]
        expected = hashlib.sha256('\n'.join(real[:4]).encode()).hexdigest()
        observed = self.parse(real)
        self.assertEqual(observed['ea_pid'], 31300)
        self.assertEqual(observed['content_id'], '1015806')
        self.assertEqual(observed['record_sha256'], expected)
        self.assertEqual(broker.processing_record(self.log), observed)

    def test_serialization_append_keeps_original_context_and_four_line_digest_stable(self):
        record = self.parse(self.lines)
        context = {key: record[key] for key in ('offer_id', 'content_id', 'launcher', 'record_sha256', 'ea_pid')}
        context.update(handoff_at=self.timestamp - 0.5, log=str(self.log))
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write(self.serialization() + '\n')
        self.assertEqual(broker.processing_record(self.log, 0), record)
        self.assertEqual(broker.processing_record(self.log), record)
        broker.validate_launch_context(context, self.timestamp + 1, {'pid': 6012}, expected_log=self.log)

    def test_serialization_requires_same_pid_tid_and_full_same_pipeline_identity(self):
        postlude = self.serialization()
        changes = [('PID:  6012', 'PID:  6013'), ('TID: 46420', 'TID: 46421'),
                   ('TID: 46420', 'TID: invalid'), ('contentId[1015806]', 'contentId[1019999]'),
                   ('offerId[OFB-EAST:109552414]', 'offerId[OFB-EAST:other]'),
                   ('requestSource[RTP]', 'requestSource[Client]'), ('args[]', 'args[-arg]'),
                   ('cwd[' + str(self.launcher.parent) + ']', 'cwd[' + str(self.root / 'Other') + ']'),
                   ('exe[' + str(self.launcher) + ']', 'exe[' + str(self.root / 'Other' / 'TS4_Launcher_x64.exe') + ']'),
                   ('isLauncherElevated[false]', 'isLauncherElevated[false] override[third-party]')]
        for old, new in changes:
            with self.subTest(new=new):
                self.reject(self.lines + [postlude.replace(old, new)])

    def test_serialization_is_after_success_monotonic_and_within_two_seconds(self):
        for at in (0, 1, 2, 3):
            with self.subTest(at=at):
                self.reject(self.lines[:at] + [self.serialization()] + self.lines[at:])
        for second in ('00.998', '01.000', '03.000'):
            with self.subTest(second=second):
                self.reject(self.lines + [self.serialization(second)])
        accepted = self.parse(self.lines + [self.serialization('02.999')])
        self.assertEqual(accepted['record_sha256'], hashlib.sha256('\n'.join(self.lines).encode()).hexdigest())

    def test_independent_second_initial_or_legacy_intent_is_never_deduped(self):
        complete = self.lines + [self.serialization()]
        self.reject(complete + [self.serialization('01.024')])
        self.reject(complete + self.lines)
        self.reject(self.lines + [self.serialization(), self.legacy('1019999')])
        # A legacy marker between required pipeline records is never a postlude.
        self.reject(self.lines[:2] + [self.serialization()] + self.lines[2:])
        with self.assertRaises(ValueError):
            self.parse(complete + [self.serialization('01.024')], offset=None)

    def test_unrelated_later_legacy_does_not_preserve_old_worker_context(self):
        record = self.parse(self.lines + [self.serialization()])
        context = {key: record[key] for key in ('offer_id', 'content_id', 'launcher', 'record_sha256', 'ea_pid')}
        context.update(handoff_at=self.timestamp - 0.5, log=str(self.log))
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write(self.serialization('03.000') + '\n')
        with self.assertRaises(ValueError):
            broker.validate_launch_context(context, self.timestamp + 4, {'pid': 6012}, expected_log=self.log)

    def test_legacy_latest_record_and_offsets_remain_supported(self):
        self.assertEqual(self.parse([self.legacy(), self.legacy('1019999')])['content_id'], '1019999')
        old_size = self.log.stat().st_size
        with self.assertRaises(broker.LaunchRecordPending):
            broker.processing_record(self.log, old_size)
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write('\n'.join(self.lines) + '\n')
        self.assertEqual(broker.processing_record(self.log, old_size)['content_id'], '1015806')

    def test_every_incomplete_prefix_is_pending_and_never_uses_older_legacy(self):
        for length in range(1, 4):
            with self.subTest(length=length), self.assertRaises(broker.LaunchRecordPending):
                self.parse([self.legacy()] + self.lines[:length], offset=None)
        with self.assertRaises(broker.LaunchRecordPending):
            self.parse(['unrelated status'])

    def test_other_initial_or_legacy_request_cannot_splice_or_supersede_fresh_pipeline(self):
        for other in (self.lines[0], self.legacy(), self.lines[0].replace('1015806', '1019999')):
            for at in (1, 2, 3, 4):
                with self.subTest(other=other, at=at):
                    self.reject(self.lines[:at] + [other] + self.lines[at:])
        latest = self.parse(self.lines + self.lines, offset=None)
        self.assertEqual(latest['record_sha256'], hashlib.sha256('\n'.join(self.lines).encode()).hexdigest())

    def test_newer_completed_pipeline_revalidates_its_own_hash(self):
        earlier = [line.replace('19:05:', '19:04:') for line in self.lines]
        current = self.parse(earlier + self.lines, offset=None)
        self.assertEqual(current['record_sha256'], hashlib.sha256('\n'.join(self.lines).encode()).hexdigest())
        with self.assertRaises(broker.LaunchRecordPending):
            self.parse(earlier + self.lines[:1], offset=None)

    def test_no_offset_uses_latest_boundary_ignoring_old_legacy_and_pipeline_history(self):
        history = self.lines + [self.legacy()] + self.lines
        latest = self.parse(history, offset=None)
        self.assertEqual(latest['record_sha256'], hashlib.sha256('\n'.join(self.lines).encode()).hexdigest())
        last_legacy = self.legacy('1019999').replace('19:04:00.000', '19:08:47.861')
        self.assertEqual(self.parse(history + [last_legacy], offset=None)['content_id'], '1019999')
        self.assertEqual(broker.processing_record(self.log)['timestamp'],
                         datetime.fromisoformat('2026-10-08T19:08:47.861+00:00').timestamp())
        self.reject(self.lines + [last_legacy])

    def test_no_offset_newer_incomplete_or_malformed_initial_never_falls_back_to_legacy(self):
        history = self.lines + [self.legacy().replace('19:04:00.000', '19:08:47.861')]
        initial = self.lines[0].replace('19:05:', '19:09:')
        with self.assertRaises(broker.LaunchRecordPending):
            self.parse(history + [initial], offset=None)
        with self.assertRaisesRegex(ValueError, 'InitialRequest'):
            self.parse(history + [initial.replace('requestOwner=[EA]', 'requestOwner=[Other]')], offset=None)

    def test_initial_record_requires_exact_ea_rtp_single_id_and_empty_arguments(self):
        changes = [('requestOwner=[EA]', 'requestOwner=[Other]'),
                   ('requestSource=[RTP]', 'requestSource=[Client]'),
                   ('gameArguments=[]', 'gameArguments=[-arg]'),
                   ('contentIds=[1015806]', 'contentIds=[1015806, 1019999]'),
                   ('contentIds=[1015806]', 'contentIds=[]'),
                   ('offerKey.externalType=[]', 'offerKey.externalType=[ThirdParty]'),
                   ('offerKey.offerId=[]', 'offerKey.offerId=[OFB-EAST:other]'),
                   ('offerId=[]', 'offerId=[OFB-EAST:other]'),
                   ('slug=[]', 'slug=[another-game]'),
                   ('(InitialRequest)', '(OverrideRequest)')]
        for old, new in changes:
            with self.subTest(new=new):
                self.reject([self.lines[0].replace(old, new)] + self.lines[1:])

    def test_all_record_headers_require_one_exact_positive_pid_tid(self):
        for index in range(4):
            for old, new in (('PID:  6012', 'PID:  6013'), ('TID: 46420', 'TID: 46421'),
                             ('PID:  6012', 'PID:  0'), ('TID: 46420', 'TID: 4294967296'),
                             ('TID: 46420', 'TID: invalid'), ('00.999Z', '00.999+00:00')):
                if old not in self.lines[index]:
                    continue
                changed = list(self.lines); changed[index] = changed[index].replace(old, new)
                with self.subTest(index=index, new=new):
                    self.reject(changed)
        duplicate = list(self.lines)
        duplicate[1] += '\t[2026-10-08T19:05:01.000Z] PID: 6012 TID: 46420 '
        self.reject(duplicate)

    def test_timestamp_order_and_two_second_span_apply_to_every_relevant_record(self):
        for index, second in ((1, '00.998'), (2, '00.999'), (3, '00.999'), (3, '03.000')):
            changed = list(self.lines)
            old = '01.001' if index == 3 else '01.000'
            changed[index] = changed[index].replace(old, second)
            with self.subTest(index=index, second=second):
                self.reject(changed)
        boundary = list(self.lines); boundary[3] = boundary[3].replace('01.001', '02.999')
        self.assertEqual(self.parse(boundary)['timestamp'], self.timestamp)
        self.reject(self.lines + [self.lines[1].replace('01.000', '03.000')])

    def test_default_launcher_has_no_override_arguments_relative_or_other_game_path(self):
        variants = [self.lines[1].replace('cmdArgs=[]', 'cmdArgs=[-arg]'),
                    self.lines[1].replace('defaultLauncher.', 'thirdPartyLauncher.'),
                    self.lines[1].replace('TS4_Launcher_x64.exe', 'OtherGame.exe'),
                    self.lines[1].replace(str(self.launcher), 'TS4_Launcher_x64.exe'),
                    self.lines[1] + ' override=[third-party]']
        for exe in variants:
            with self.subTest(exe=exe):
                self.reject([self.lines[0], exe] + self.lines[2:])
        changed = self.lines + [self.lines[1].replace(str(self.launcher), str(self.root / 'Elsewhere' / 'TS4_Launcher_x64.exe'))]
        self.reject(changed)

    def test_issued_identity_working_directory_and_arguments_must_match(self):
        changes = [('content[1015806]', 'content[1019999]'),
                   ('content[1015806]', 'content[1015806,1019999]'),
                   ('gameArgs []', 'gameArgs [-arg]'),
                   (str(self.launcher.parent), str(self.root / 'Elsewhere')),
                   (str(self.launcher.parent), 'Game/Bin'),
                   ('offer[OFB-EAST:109552414]', 'offer[]')]
        for old, new in changes:
            changed = list(self.lines); changed[2] = changed[2].replace(old, new)
            with self.subTest(new=new):
                self.reject(changed)

    def test_success_has_the_same_single_content_offer_and_sims_slug(self):
        for old, new in (('contentIds=[1015806]', 'contentIds=[1019999]'),
                         ('contentIds=[1015806]', 'contentIds=[1015806,1019999]'),
                         ('offerKey.offerId=[OFB-EAST:109552414]', 'offerKey.offerId=[OFB-EAST:other]'),
                         ('offerId=[]', 'offerId=[OFB-EAST:other]'),
                         ('slug=[the-sims-4]', 'slug=[another-game]')):
            changed = list(self.lines); changed[3] = changed[3].replace(old, new)
            with self.subTest(new=new):
                self.reject(changed)

    def test_out_of_order_or_duplicate_launch_and_success_are_not_accepted(self):
        for order in ((0, 2, 1, 3), (0, 1, 3, 2), (0, 1, 2, 2, 3), (0, 1, 2, 3, 3)):
            with self.subTest(order=order):
                self.reject([self.lines[index] for index in order])

    def test_existing_context_account_path_freshness_and_lease_gates_stay_unchanged(self):
        self.parse(self.lines)
        handoff = self.timestamp - 0.5
        plan = {'account_launch_identity': {'offer_id': 'OFB-EAST:109552414',
                'content_id': '1015806', 'executable': str(self.launcher), 'log': str(self.log)}}
        validate = broker.validate_launch_context
        with patch.object(broker, 'validate_launch_context', side_effect=lambda context, now, target:
                          validate(context, now, target, expected_log=self.log)):
            context = broker.make_launch_context(plan, handoff, 0, now=self.timestamp + 1)
        validate(context, self.timestamp + 1, {'pid': 6012}, expected_log=self.log)
        for field, value in (('offer_id', 'OFB-EAST:other'), ('content_id', '1019999'),
                             ('executable', str(self.root / 'Other' / 'TS4_Launcher_x64.exe'))):
            changed = {'account_launch_identity': dict(plan['account_launch_identity'], **{field: value})}
            with self.subTest(field=field), self.assertRaises(ValueError):
                broker.make_launch_context(changed, handoff, 0, now=self.timestamp + 1)
        with self.assertRaisesRegex(ValueError, 'expired'):
            validate(context, handoff + 90.001, {'pid': 6012}, expected_log=self.log)
        with self.assertRaises(ValueError):
            validate(context, self.timestamp + 1, {'pid': 6013}, expected_log=self.log)
        with self.assertRaises(ValueError):
            broker.make_launch_context(plan, self.timestamp + 3, 0, now=self.timestamp + 3)

    def test_partial_pipeline_wait_keeps_original_offset_and_requires_all_four_records(self):
        self.log.write_text(self.legacy() + '\n', encoding='utf-8')
        offset = self.log.stat().st_size
        self.log.write_text(self.log.read_text() + '\n'.join(self.lines[:2]) + '\n', encoding='utf-8')
        clock = [0.0]
        calls = []
        def read_context(_plan, handoff, observed_offset):
            calls.append((handoff, observed_offset))
            return broker.processing_record(self.log, observed_offset)
        def append(delay):
            clock[0] += delay
            with self.log.open('a', encoding='utf-8') as stream:
                stream.write('\n'.join(self.lines[2:]) + '\n')
        result = broker.wait_launch_context({}, self.timestamp - 0.5, offset,
            read_context=read_context, monotonic=lambda: clock[0], pause=append)
        self.assertEqual(result['content_id'], '1015806')
        self.assertEqual(calls, [(self.timestamp - 0.5, offset)] * 2)
        self.assertEqual(clock[0], 0.2)


if __name__ == '__main__':
    unittest.main()
