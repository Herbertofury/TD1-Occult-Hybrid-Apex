"""Portable, synthetic regression coverage for offline parse-log provenance.

Copies of this test live under tests/ and discover the repository tools/ sibling.
No process, game, profile, collector, ETW session or network call is used.
"""
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tests'))
import capture_frame_intervals as base
import compare_frame_runs as frames
import compare_hitch_stages as stages
import hitch_stage
import offline_xperf as offline
import test_compare_frame_runs as compare_fixtures


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path,value):path.write_text(json.dumps(value),encoding='utf-8')

class PortableParseLogTests(unittest.TestCase):
    def setUp(self):
        self.fixture=compare_fixtures.MatchedFrameComparisonTests('runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.work=self.root/'.work';self.work.mkdir()
        self.root_patch=patch.object(base,'ROOT',self.root);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.logs=[]
        for index,run in enumerate(self.fixture.manifest['runs']):self.prepare_run(index,run)
    def prepare_run(self,index,run):
        capture_path=Path(run['capture']);capture=json.loads(capture_path.read_text())
        pid=capture['target_pid'];prefix=self.work/('run%d' % index);etl=Path(str(prefix)+'.etl')
        header=Path(str(prefix)+'.header.txt');logger=Path(str(prefix)+'.logger.txt')
        logger_end=Path(str(prefix)+'.logger-end.txt');raw=Path(str(prefix)+'.presentmon.raw.csv')
        log=Path(str(prefix)+'.parse.log');self.logs.append(log)
        etl.write_bytes(('synthetic-etl-%d' % index).encode())
        header.write_text('Clock type : PerfCounter\nTotal # Lost Buffers : 0\nTotal # Lost Events : 0\n'
                          'Number of Traces : 1\nLog file mode : Sequential\nTrace name: '+str(etl)+'\n')
        session='ApexOffline'+('%032x' % (index+1))
        logger.write_text('Logger Name : '+session+'\nBuffer Size : 1024\nMinimum Buffers : 64\n'
            'Maximum Buffers : 120\nMaximum File Size : 1024\nLog File Mode : Sequential IndependentSession\n'
            'Log Filename : '+str(etl)+'\nTrace Flags : '+offline.PROVIDERS+'\n')
        logger_end.write_text(logger.read_text());log.write_bytes('Started recording.\nStopped recording.\n'.encode('utf-16'))
        with raw.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=('ProcessID','SwapChainAddress','PresentRuntime',
                'MsBetweenPresents','CPUStartQPC','TimeInQPC'));writer.writeheader()
            for n in range(150):writer.writerow(dict(ProcessID=pid,SwapChainAddress='1',PresentRuntime='DXGI',
                MsBetweenPresents='40.00000000000000',CPUStartQPC=1000+n*4,TimeInQPC=1000+n*4))
        csv_path=Path(run['csv']);csv_path.write_bytes(offline.bounded_csv(raw,pid,1000,1600,100))
        command=[str(base.PRESENTMON),'--etl_file',str(etl),'--process_id',str(pid),'--qpc_time',
            '--no_track_input','--no_track_gpu','--no_track_display','--no_console_stats','--output_file',str(raw)]
        capture.update(capture_backend='xperf_etl',collector_sha256=base.PRESENTMON_SHA,configured_seconds=5,
            capture_elapsed_ns=5_100_000_000,collector_command=command,
            offline_etw=dict(session=session,start_command=[str(offline.XPERF),'-start',session,'-on',offline.PROVIDERS]+
                offline.OPTIONS+['-f',str(etl)],stop_command=[str(offline.XPERF),'-stop',session],xperf_sha256='a'*64,
                adapter_sha256=digest(Path(offline.__file__)),etl_path=str(etl),header_path=str(header),
                max_file_mb=offline.MAX_MB,etl_sha256=digest(etl),header_sha256=digest(header),etl_bytes=etl.stat().st_size,
                logger_path=str(logger),logger_sha256=digest(logger),logger_end_path=str(logger_end),
                logger_end_sha256=digest(logger_end),actual_buffers=[64,120],raw_csv_path=str(raw),raw_csv_sha256=digest(raw),
                stop_succeeded=True,header_zero_loss=True,ready_qpc=1000,end_qpc=1600,qpc_frequency=100,
                session_polls_qpc=[999,1100,1300,1500,1601],parse_log_path=str(log),parse_log_sha256=digest(log)))
        capture['analysis']['csv_sha256']=digest(csv_path)
        self.update_capture(run,capture)
    def update_capture(self,run,capture):
        path=Path(run['capture']);write_json(path,capture)
        action_path=Path(run['actions']);action=json.loads(action_path.read_text())
        action['capture_sha256']=digest(path);write_json(action_path,action)
    def make_legacy(self,index):
        run=self.fixture.manifest['runs'][index];path=Path(run['capture']);capture=json.loads(path.read_text())
        e=capture['offline_etw'];e.pop('parse_log_path');e.pop('parse_log_sha256');e['adapter_sha256']=offline.LEGACY_ADAPTER_SHA256
        self.update_capture(run,capture)
    def make_stage_manifest(self):
        scenario=self.fixture.scenario;flags={'apex_script_loaded':False,'apex_cas_package_loaded':False,'apex_overlay_loaded':False}
        ladder=[{'id':'vanilla','features':[],'artifacts':[],'loaded':flags},
                {'id':'feature','features':['core'],'artifacts':[{'path':'Apex/core.package','sha256':'a'*64}],
                 'loaded':dict(flags,apex_cas_package_loaded=True)}]
        runs=[]
        for run in self.fixture.manifest['runs']:
            item=copy.deepcopy(run);stage=ladder[0 if run['kind']=='baseline' else 1];item['kind']=stage['id']
            mods_path=Path(item['mod_state']);mods=json.loads(mods_path.read_text())
            mods.update(schema=2,stage=stage,stage_sha256=hitch_stage.digest(stage));mods.update(stage['loaded'])
            mods.pop('apex_candidate_sha256',None);write_json(mods_path,mods)
            cap_path=Path(item['capture']);capture=json.loads(cap_path.read_text())
            capture.update(benchmark_mode='stage',stage_id=stage['id'],stage_sha256=hitch_stage.digest(stage),
                           mod_state_sha256=digest(mods_path));self.update_capture(item,capture);runs.append(item)
        return dict(schema=2,scenario=scenario,stages=ladder,
                    comparisons=[dict(control='vanilla',candidate='feature',runs=runs)])
    def test_actual_full_comparison_checked_and_tail_values(self):
        report=frames.compare(self.fixture.manifest,self.root)
        self.assertTrue(all(r['parse_log_verification']=='sha256_loss_checked' for r in report['runs']))
        self.assertEqual(report['runs'][0]['statistics']['p95_ms'],40)
        self.assertEqual(report['runs'][0]['statistics']['p99_ms'],40)
        self.assertEqual(report['runs'][0]['statistics']['max_ms'],40)
        self.assertTrue(any('no bound parser log' in x for x in report['limitations']))
        self.assertFalse(report['performance_pass'])
    def test_actual_full_comparison_accepts_prior_records_with_explicit_limit(self):
        for index in range(4):self.make_legacy(index)
        report=frames.compare(self.fixture.manifest,self.root)
        self.assertTrue(all(r['parse_log_verification']=='legacy_unverified' for r in report['runs']))
        self.assertTrue(all('parse_log=legacy_unverified' in r['collector_options'] for r in report['runs']))
    def test_actual_full_comparison_rejects_mixed_generation(self):
        self.make_legacy(1)
        with self.assertRaisesRegex(ValueError,'Collector options'):frames.compare(self.fixture.manifest,self.root)
    def test_actual_full_comparison_refuses_tampered_or_missing_log(self):
        self.logs[0].write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'parse log differs'):frames.compare(self.fixture.manifest,self.root)
        self.logs[0].unlink()
        with self.assertRaises(FileNotFoundError):frames.compare(self.fixture.manifest,self.root)
    def test_actual_full_comparison_refuses_bound_utf16_overflow(self):
        log=self.logs[0];log.write_bytes('warning: 5 overflowed present events detected.\n'.encode('utf-16'))
        run=self.fixture.manifest['runs'][0];capture=json.loads(Path(run['capture']).read_text())
        capture['offline_etw']['parse_log_sha256']=digest(log);self.update_capture(run,capture)
        with self.assertRaisesRegex(ValueError,'reports loss'):frames.compare(self.fixture.manifest,self.root)
    def test_actual_full_comparison_refuses_bound_invalid_utf16(self):
        log=self.logs[0];log.write_bytes(b'\xff\xfew')
        run=self.fixture.manifest['runs'][0];capture=json.loads(Path(run['capture']).read_text())
        capture['offline_etw']['parse_log_sha256']=digest(log);self.update_capture(run,capture)
        with self.assertRaisesRegex(ValueError,'encoding'):frames.compare(self.fixture.manifest,self.root)
    def test_actual_full_comparison_refuses_missing_new_binding(self):
        run=self.fixture.manifest['runs'][0];capture=json.loads(Path(run['capture']).read_text())
        capture['offline_etw'].pop('parse_log_sha256');self.update_capture(run,capture)
        with self.assertRaisesRegex(ValueError,'required'):frames.compare(self.fixture.manifest,self.root)
    def test_actual_stage_comparison_keeps_status_and_refuses_mixing(self):
        manifest=self.make_stage_manifest();report=stages.compare(manifest,self.root)
        self.assertTrue(all(r['parse_log_verification']=='sha256_loss_checked' for r in report['comparisons'][0]['runs']))
        item=manifest['comparisons'][0]['runs'][1];capture=json.loads(Path(item['capture']).read_text())
        e=capture['offline_etw'];e.pop('parse_log_path');e.pop('parse_log_sha256');e['adapter_sha256']=offline.LEGACY_ADAPTER_SHA256
        self.update_capture(item,capture)
        with self.assertRaisesRegex(ValueError,'Collector, options'):stages.compare(manifest,self.root)
    def test_actual_stage_comparison_accepts_legacy_only_with_limit(self):
        for index in range(4):self.make_legacy(index)
        report=stages.compare(self.make_stage_manifest(),self.root)
        self.assertTrue(all(r['parse_log_verification']=='legacy_unverified' for r in report['comparisons'][0]['runs']))
        self.assertTrue(any('no bound parser log' in text for text in report['limitations']))

if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
