import copy
import csv
import hashlib
import random
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import offline_xperf as offline

HEADER='Clock type : PerfCounter\nTotal # Lost Buffers : 0\nTotal # Lost Events : 0\nNumber of Traces : 1\nLog file mode : Sequential <0x8000000>\n'

class OfflineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.work=self.root/'.work';self.work.mkdir()
        self.etl=self.work/'trace.etl';self.etl.write_bytes(b'private synthetic trace')
        self.header=self.work/'trace.header.txt';self.header.write_text(HEADER+'Trace name: '+str(self.etl)+'\n')
        self.csv=self.work/'trace.csv';self.raw=self.work/'trace.raw.csv'
        with self.raw.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=('ProcessID','SwapChainAddress','PresentRuntime','MsBetweenPresents','CPUStartQPC','TimeInQPC'))
            writer.writeheader()
            for n in range(150):writer.writerow(dict(ProcessID=123,SwapChainAddress='1',PresentRuntime='DXGI',
                MsBetweenPresents='40.00000000000000',CPUStartQPC=1000+n*4,TimeInQPC=1000+n*4))
        self.csv.write_bytes(offline.bounded_csv(self.raw,123,1000,1600,100))
        self.session='ApexOffline'+'a'*32;self.pid=123
        self.logger=self.work/'logger.txt';self.logger.write_text('Logger Name : '+self.session+'\nBuffer Size : 1024\n'
            'Minimum Buffers : 64\nMaximum Buffers : 120\nMaximum File Size : 1024\n'
            'Log File Mode : Sequential IndependentSession\nLog Filename : '+str(self.etl)+'\nTrace Flags : '+offline.PROVIDERS+'\n')
        self.logger_end=self.work/'logger-end.txt';self.logger_end.write_text(self.logger.read_text())
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.command=[str(offline.base.PRESENTMON),'--etl_file',str(self.etl),'--process_id',str(self.pid),
            '--qpc_time','--no_track_input','--no_track_gpu','--no_track_display','--no_console_stats','--output_file',str(self.raw)]
        self.capture=dict(collector_sha256=offline.base.PRESENTMON_SHA,configured_seconds=5,capture_elapsed_ns=5_100_000_000,offline_etw=dict(
            session=self.session,start_command=[str(offline.XPERF),'-start',self.session,'-on',offline.PROVIDERS]+offline.OPTIONS+['-f',str(self.etl)],
            stop_command=[str(offline.XPERF),'-stop',self.session],xperf_sha256='a'*64,
            etl_path=str(self.etl),header_path=str(self.header),max_file_mb=offline.MAX_MB,
            etl_sha256=digest(self.etl),header_sha256=digest(self.header),etl_bytes=self.etl.stat().st_size,
            logger_path=str(self.logger),logger_sha256=digest(self.logger),actual_buffers=[64,120],
            logger_end_path=str(self.logger_end),logger_end_sha256=digest(self.logger_end),
            adapter_sha256=digest(Path(offline.__file__)),
            raw_csv_path=str(self.raw),raw_csv_sha256=digest(self.raw),
            stop_succeeded=True,header_zero_loss=True,ready_qpc=1000,end_qpc=1600,qpc_frequency=100,
            session_polls_qpc=[999,1100,1300,1500,1601]))
        self.patch=patch.object(offline.base,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)

    def check(self,capture=None,command=None):
        return offline.validate_offline_capture(capture or self.capture,command or self.command,self.pid,5,self.csv)

    def test_owned_bounded_provenance_and_covering_clocks_are_accepted(self):
        self.assertIn('backend=xperf_etl',self.check())
        self.assertTrue(offline.validate_coverage(self.capture,[1050,1200,1500,1580]))

    def test_zero_loss_clock_and_single_trace_are_required(self):
        for bad in (HEADER.replace('Events : 0','Events : 1'), HEADER.replace('Buffers : 0','Buffers : 1'),
                    HEADER.replace('PerfCounter','SystemTime'),HEADER.replace('Traces : 1','Traces : 2'),
                    HEADER.replace('Sequential','Circular'), ''):
            with self.subTest(header=bad),self.assertRaises(ValueError):offline.validate_header(bad)

    def test_tampering_wrong_owner_and_bad_duration_are_refused(self):
        for mutate in (lambda d:d['offline_etw'].update(stop_succeeded=False),
                lambda d:d.update(collector_sha256='6'*64),
                lambda d:d['offline_etw'].update(session='someone-else'),
                lambda d:d['offline_etw'].update(etl_sha256='0'*64),
                lambda d:d['offline_etw'].update(actual_buffers=[30,120]),
                lambda d:d['offline_etw'].update(max_file_mb=offline.MAX_MB+1),
                lambda d:d.update(capture_elapsed_ns=1),
                lambda d:d['offline_etw'].update(stop_command=[str(offline.XPERF),'-stop'])):
            record=copy.deepcopy(self.capture);mutate(record)
            with self.subTest(record=record),self.assertRaises(ValueError):self.check(record)
        command=self.command[:];command[4]='999'
        with self.assertRaises(ValueError):self.check(command=command)
        self.etl.write_bytes(b'tampered')
        with self.assertRaises(ValueError):self.check()

    def test_csv_is_exactly_the_bounded_subset(self):
        original=self.csv.read_bytes();self.csv.write_bytes(original+b'junk')
        with self.assertRaisesRegex(ValueError,'subset'):self.check()
        self.csv.write_bytes(original);self.raw.write_bytes(self.raw.read_bytes()+b'junk')
        with self.assertRaises(ValueError):self.check()

    def test_relabelled_synthetic_or_stubbed_evidence_still_fails_closed(self):
        for field,value in (('state','synthetic_probe_only'),('synthetic_identity_stubs',True),
                ('synthetic_identity_stubs',False),('synthetic_probe_only',True),('game_measured',False)):
            record=copy.deepcopy(self.capture);record['state']='completed';record[field]=value
            with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'Synthetic'):
                self.check(record)

    def test_qpc_decimal_rounding_across_frequencies_and_large_ticks(self):
        # PresentMon 2.6.0 computes binary64 ticks * (1000.0 / frequency),
        # then prints with 14 fractional decimal places.
        for frequency in (1,3,3579545,10000000,1000000000,2**53+1,2**63-1):
            for ticks in (1,2,447,12345,2**53+1,2**64-1):
                with self.subTest(frequency=frequency,ticks=ticks):
                    text=format(float(ticks)*(1000.0/float(frequency)),'.14f')
                    self.assertTrue(offline.validate_qpc_interval(text,ticks,frequency))
        rng=random.Random(32817)
        for unused in range(1000):
            frequency=rng.randrange(1,2**63);ticks=rng.randrange(1,2**64)
            text=format(float(ticks)*(1000.0/float(frequency)),'.14f')
            self.assertTrue(offline.validate_qpc_interval(text,ticks,frequency))
        for text,ticks,frequency in (('40.00010000000000',4,100),('40',4,100),
                ('NaN',4,100),('40.00000000000000',0,100),('40.00000000000000',4,0),
                ('40.00000000000000',4,True),('40.00000000000000',4,2**63)):
            with self.subTest(text=text,ticks=ticks,frequency=frequency),self.assertRaises(ValueError):
                offline.validate_qpc_interval(text,ticks,frequency)

    def test_missing_or_mismatched_row_is_not_silently_attributed(self):
        with self.raw.open('r',newline='',encoding='utf-8') as stream:
            reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
        missing=rows[:73]+rows[74:]
        with self.raw.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(missing)
        # The generic reader alone accepts these ordered rows; QPC/metric
        # consistency must detect the missing output row.
        offline.comparison.read_frames(self.raw,123,hashlib.sha256(self.raw.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'adjacent QPC'):offline.bounded_csv(self.raw,123,1000,1600,100)

    def test_first_row_is_excluded_because_its_predecessor_is_unobserved(self):
        with self.raw.open('r',newline='',encoding='utf-8') as stream:
            reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
        rows[0]['MsBetweenPresents']='1000.00000000000000'
        with self.raw.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        output=offline.bounded_csv(self.raw,123,1000,1600,100).decode()
        self.assertNotIn('1000.00000000000000',output)

    def test_actual_logger_rejects_unhonored_limit_or_circular_mode(self):
        original=self.logger.read_text()
        for changed in (original.replace('Maximum File Size : 1024','Maximum File Size : 128'),
                        original.replace('Sequential IndependentSession','Circular IndependentSession'),
                        original.replace(str(self.etl),str(self.work/'other.etl')),
                        original.replace('0x90FFFF','0x90FFFE'),
                        original.replace(':0xf:6',':0xf:5',1),
                        original.replace(offline.PROVIDERS,offline.PROVIDERS.split('+')[0]),
                        original.replace(offline.PROVIDERS,offline.PROVIDERS+'+'+offline.PROVIDERS.split('+')[0])):
            self.logger.write_text(changed)
            record=copy.deepcopy(self.capture)
            record['offline_etw']['logger_sha256']=hashlib.sha256(self.logger.read_bytes()).hexdigest()
            with self.subTest(logger=changed),self.assertRaises(ValueError):self.check(record)

    def test_final_provider_change_is_refused(self):
        original=self.logger_end.read_text()
        self.logger_end.write_text(original.replace('0x90FFFF','0x90FFFE'))
        record=copy.deepcopy(self.capture)
        record['offline_etw']['logger_end_sha256']=hashlib.sha256(self.logger_end.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'provider'):self.check(record)

    def test_polls_and_present_bounds_must_cover_the_session(self):
        for polls in ([1001,1601],[999,1400,1601],[999,1100,1300,1500,1599],[]):
            record=copy.deepcopy(self.capture);record['offline_etw']['session_polls_qpc']=polls
            with self.subTest(polls=polls),self.assertRaises(ValueError):offline.validate_coverage(record,[1050,1200,1500,1580])
        for clocks in ([1101,1500,1580],[1050,1200,1499],[]):
            with self.subTest(clocks=clocks),self.assertRaises(ValueError):offline.validate_coverage(self.capture,clocks)

    def test_no_start_without_preflight(self):
        with patch.object(offline.base,'verify_start',side_effect=ValueError('refused')),patch.object(offline.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'refused'):offline.capture(object())
            run.assert_not_called()

    def test_uncertain_start_never_blindly_stops_a_session(self):
        executable=self.work/'xperf.exe';executable.write_bytes(b'fixture')
        state=self.work/'state.json';state.write_text('{}')
        args=SimpleNamespace(state=state,xperf_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            pid=123,mode='baseline',seconds=5,exe=self.work/'game',exe_sha256='1'*64)
        paths={key:self.work/('run'+suffix) for key,suffix in [('csv','.csv'),('log','.log'),('metadata','.json')]}
        window=dict(process_creation_filetime=42)
        with patch.object(offline,'XPERF',executable), \
                patch.object(offline.base,'verify_start',return_value=(self.work,paths,window,{},'a'*64)), \
                patch.object(offline.shutil,'disk_usage',return_value=SimpleNamespace(free=3*1024**3)), \
                patch.object(offline,'run_to_log',side_effect=subprocess.TimeoutExpired('xperf',30)) as run:
            with self.assertRaisesRegex(RuntimeError,'inspect exact owned session'):offline.capture(args)
        self.assertEqual(run.call_count,1)
        import json
        result=json.loads(paths['metadata'].read_text())
        self.assertEqual(result['state'],'invalid')
        self.assertEqual(result['start_outcome'],'uncertain')
        self.assertTrue(result['manual_inspection_required'])

    def test_catchable_interrupt_after_confirmed_start_stops_only_owned_session(self):
        executable=self.work/'xperf.exe';executable.write_bytes(b'fixture')
        state=self.work/'state.json';state.write_text('{}')
        args=SimpleNamespace(state=state,xperf_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            pid=123,mode='baseline',seconds=5,exe=self.work/'game',exe_sha256='1'*64)
        paths={key:self.work/('run'+suffix) for key,suffix in [('csv','.csv'),('log','.log'),('metadata','.json')]}
        with patch.object(offline,'XPERF',executable), \
                patch.object(offline.base,'verify_start',return_value=(self.work,paths,{'process_creation_filetime':42},{},'a'*64)), \
                patch.object(offline.shutil,'disk_usage',return_value=SimpleNamespace(free=3*1024**3)), \
                patch.object(offline,'snapshot_logger',side_effect=KeyboardInterrupt), \
                patch.object(offline,'run_to_log') as run:
            with self.assertRaises(KeyboardInterrupt):offline.capture(args)
        self.assertEqual(run.call_count,2)
        result=__import__('json').loads(paths['metadata'].read_text())
        self.assertEqual(result['state'],'invalid');self.assertTrue(result['cleanup_stop_succeeded'])
        self.assertEqual(result['capture_error_type'],'KeyboardInterrupt')
        self.assertEqual(run.call_args_list[1][0][0],[str(executable),'-stop',result['offline_etw']['session']])

    def test_interrupt_during_unconfirmed_start_never_blindly_stops(self):
        executable=self.work/'xperf.exe';executable.write_bytes(b'fixture')
        state=self.work/'state.json';state.write_text('{}')
        args=SimpleNamespace(state=state,xperf_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            pid=123,mode='baseline',seconds=5,exe=self.work/'game',exe_sha256='1'*64)
        paths={key:self.work/('run'+suffix) for key,suffix in [('csv','.csv'),('log','.log'),('metadata','.json')]}
        with patch.object(offline,'XPERF',executable), \
                patch.object(offline.base,'verify_start',return_value=(self.work,paths,{'process_creation_filetime':42},{},'a'*64)), \
                patch.object(offline.shutil,'disk_usage',return_value=SimpleNamespace(free=3*1024**3)), \
                patch.object(offline,'run_to_log',side_effect=KeyboardInterrupt) as run:
            with self.assertRaises(KeyboardInterrupt):offline.capture(args)
        self.assertEqual(run.call_count,1)
        result=__import__('json').loads(paths['metadata'].read_text())
        self.assertEqual(result['state'],'invalid');self.assertEqual(result['start_outcome'],'uncertain')
        self.assertTrue(result['manual_inspection_required'])

    def test_uncertain_cleanup_stop_is_not_retried(self):
        executable=self.work/'xperf.exe';executable.write_bytes(b'fixture')
        state=self.work/'state.json';state.write_text('{}')
        args=SimpleNamespace(state=state,xperf_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            pid=123,mode='baseline',seconds=5,exe=self.work/'game',exe_sha256='1'*64)
        paths={key:self.work/('run'+suffix) for key,suffix in [('csv','.csv'),('log','.log'),('metadata','.json')]}
        with patch.object(offline,'XPERF',executable), \
                patch.object(offline.base,'verify_start',return_value=(self.work,paths,{'process_creation_filetime':42},{},'a'*64)), \
                patch.object(offline.shutil,'disk_usage',return_value=SimpleNamespace(free=3*1024**3)), \
                patch.object(offline,'snapshot_logger',side_effect=ValueError('stop after failure')), \
                patch.object(offline,'run_to_log',side_effect=[None,subprocess.TimeoutExpired('xperf',30)]) as run:
            with self.assertRaisesRegex(ValueError,'stop after failure'):offline.capture(args)
        self.assertEqual(run.call_count,2)
        result=__import__('json').loads(paths['metadata'].read_text())
        self.assertEqual(result['state'],'invalid');self.assertTrue(result['manual_inspection_required'])
        self.assertEqual(result['cleanup_error_type'],'TimeoutExpired')

    def test_normal_stop_timeout_is_uncertain_and_never_retried(self):
        executable=self.work/'xperf.exe';executable.write_bytes(b'fixture')
        game=self.work/'game';game.write_bytes(b'fixture game')
        state=self.work/'state.json';state.write_text('{}')
        mods=self.work/'mods.json';mods.write_text('{}')
        args=SimpleNamespace(state=state,xperf_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
            pid=123,mode='baseline',seconds=5,exe=game,exe_sha256=hashlib.sha256(game.read_bytes()).hexdigest(),mod_state=mods)
        paths={key:self.work/('run'+suffix) for key,suffix in [('csv','.csv'),('log','.log'),('metadata','.json')]}
        window=dict(process_creation_filetime=42)
        def snapshot(session,etl,dest):Path(dest).write_text('fixture');return [64,120]
        with patch.object(offline,'XPERF',executable), \
                patch.object(offline.base,'verify_start',return_value=(self.work,paths,window,{},hashlib.sha256(mods.read_bytes()).hexdigest())), \
                patch.object(offline.shutil,'disk_usage',return_value=SimpleNamespace(free=3*1024**3)), \
                patch.object(offline,'snapshot_logger',side_effect=snapshot), \
                patch.object(offline.base,'window_snapshot',return_value=window), \
                patch.object(offline.reusable_profile,'load',return_value=(None,None,self.work,None)), \
                patch.object(offline,'own_session_running',return_value=True), \
                patch.object(offline,'qpc_clock',side_effect=[(999,100),(1000,100),(1100,100),(1600,100),(1601,100)]), \
                patch.object(offline.time,'monotonic',side_effect=[0,0,0,5]), \
                patch.object(offline.time,'sleep'), \
                patch.object(offline,'run_to_log',side_effect=[None,subprocess.TimeoutExpired('xperf',30)]) as run:
            with self.assertRaises(subprocess.TimeoutExpired):offline.capture(args)
        self.assertEqual(run.call_count,2)
        result=__import__('json').loads(paths['metadata'].read_text())
        self.assertEqual(result['state'],'invalid');self.assertTrue(result['manual_inspection_required'])
        self.assertIn('stop failed or timed out',result['cleanup_error'])

if __name__=='__main__':unittest.main()
