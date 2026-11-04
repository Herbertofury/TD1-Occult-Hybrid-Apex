import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import compare_frame_runs as perf


class MatchedFrameComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.scenario = dict(name='body-tattoo-scroll', game_exe_sha256='1'*64,
            hardware_sha256='2'*64, save_sha256='3'*64, other_mods_sha256='4'*64,
            settings_sha256='5'*64, profile_id='disposable-1', resolution=[1920,1080],
            dpi=96, display_mode='windowed', refresh_hz=60, fps_cap=60, renderer='dx11',
            cache_state='warm', game_mode='CAS', actions=['body', 'tattoo', 'down', 'up'])
        self.manifest = dict(schema=1, scenario=self.scenario, runs=[])
        for i, kind in enumerate(('baseline', 'apex', 'apex', 'baseline')):
            pid = 100+i
            path = self.root / ('frames%d.csv' % i)
            with path.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=('ProcessID','SwapChainAddress','PresentRuntime','MsBetweenPresents','CPUStartQPC','TimeInQPC'))
                writer.writeheader()
                for n in range(150):
                    writer.writerow(dict(ProcessID=pid, SwapChainAddress='1', PresentRuntime='DXGI',
                        MsBetweenPresents=10 if kind=='baseline' else (50 if n==149 else 11), CPUStartQPC=1000+n*10,TimeInQPC=1000+n*10))
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            enabled=kind=='apex'
            mods=dict(schema=1,target_pid=pid,process_creation_filetime=pid*100,
                other_mods_sha256=self.scenario['other_mods_sha256'],
                inventory_and_loaded_modules_observed=True,observation_method='test fixture',
                apex_script_loaded=enabled,apex_cas_package_loaded=enabled,apex_overlay_loaded=enabled,
                apex_candidate_sha256='7'*64 if enabled else None)
            mpath=self.root/('mods%d.json' % i);mpath.write_text(json.dumps(mods))
            window=dict(process_id=pid,process_creation_filetime=pid*100,image_path='TS4_x64.exe',
                        hwnd=200+i,window_class='Canvas-1',ui_thread=20+i,client_size=[1920,1080],
                        window_rect=[0,0,1920,1080],dpi=96,foreground_hwnd=200+i)
            capture=dict(state='completed',ready_seen=True,window_identity_and_geometry_unchanged=True,
                target_pid=pid,collector_sha256='6'*64,configured_seconds=30,
                benchmark_mode=kind,game_exe_sha256=self.scenario['game_exe_sha256'],game_exe_hash_unchanged=True,
                mod_state_sha256=hashlib.sha256(mpath.read_bytes()).hexdigest(),
                collector_command=['PresentMon.exe','--process_id',str(pid),'--qpc_time','--timed','30',
                    '--output_file',str(path),'--session_name','test%d' % i],window_before=copy.deepcopy(window),
                window_after=copy.deepcopy(window),analysis=dict(valid=True,
                    event_loss_warning=False,swapchains=[{}],csv_sha256=sha))
            cpath=self.root/('capture%d.json' % i);cpath.write_text(json.dumps(capture))
            trace=dict(capture_sha256=hashlib.sha256(cpath.read_bytes()).hexdigest(),target_pid=pid,
                process_creation_filetime=pid*100,clock='QPC',ui_transitions_verified=True,
                events=[dict(action=name,observed=True,start_qpc=1100+n*100,end_qpc=1150+n*100)
                        for n,name in enumerate(self.scenario['actions'])])
            apath=self.root/('actions%d.json' % i);apath.write_text(json.dumps(trace))
            self.manifest['runs'].append(dict(kind=kind,capture=str(cpath),csv=str(path),
                actions=str(apath),mod_state=str(mpath),started_ns=10000+i*2000,ended_ns=11000+i*2000,
                scenario=copy.deepcopy(self.scenario)))

    def test_matched_counterbalanced_pairs_report_intervals_not_fps_or_success(self):
        result=perf.compare(self.manifest,self.root)
        self.assertEqual([x['order'] for x in result['pairs']], [['baseline','apex'],['apex','baseline']])
        self.assertFalse(result['displayed_fps_measured'])
        self.assertFalse(result['hitch_free_claimed'])
        self.assertFalse(result['performance_pass'])
        self.assertEqual(result['runs'][1]['statistics']['max_ms'],50)
        self.assertIsNone(result['runs'][1]['statistics']['p99_9_ms'])
        self.assertEqual(result['runs'][1]['statistics']['over_33_3ms_per_1000'],1000/150)
        action=result['pairs'][0]['action_windows'][1]
        self.assertEqual(action['action'], 'tattoo')
        self.assertEqual(action['baseline_frames'], 5)
        self.assertEqual(action['apex_frames'], 5)
        self.assertEqual(action['p50_delta_ms'], 1)
        self.assertEqual(action['max_delta_ms'], 1)

    def test_offline_backend_is_comparator_compatible_without_forging_live_options(self):
        import offline_xperf as offline
        work=self.root/'.work';work.mkdir()
        etl=work/'trace.etl';etl.write_bytes(b'synthetic etl')
        header=work/'header.txt';header.write_text('Clock type : PerfCounter\nTotal # Lost Buffers : 0\n'
            'Total # Lost Events : 0\nNumber of Traces : 1\nLog file mode : Sequential\nTrace name: '+str(etl)+'\n')
        run=self.manifest['runs'][0];cpath=Path(run['capture']);capture=json.loads(cpath.read_text())
        session='ApexOffline'+'a'*32;pid=capture['target_pid'];csv_path=Path(run['csv']).resolve()
        raw=work/'trace.raw.csv';raw.write_bytes(csv_path.read_bytes())
        with raw.open('r',newline='',encoding='utf-8') as stream:
            reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
        for row in rows:row['MsBetweenPresents']='200.00000000000000'
        with raw.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        csv_path.write_bytes(offline.bounded_csv(raw,pid,1000,2500,50))
        capture['analysis']['csv_sha256']=hashlib.sha256(csv_path.read_bytes()).hexdigest()
        logger=work/'logger.txt';logger.write_text('Logger Name : '+session+'\nBuffer Size : 1024\n'
            'Minimum Buffers : 64\nMaximum Buffers : 120\nMaximum File Size : 1024\n'
            'Log File Mode : Sequential IndependentSession\nLog Filename : '+str(etl)+'\nTrace Flags : '+offline.PROVIDERS+'\n')
        logger_end=work/'logger-end.txt';logger_end.write_text(logger.read_text())
        capture.update(capture_backend='xperf_etl',collector_sha256=offline.base.PRESENTMON_SHA,capture_elapsed_ns=30_000_000_000,
            collector_command=[str(offline.base.PRESENTMON),'--etl_file',str(etl),'--process_id',str(pid),
                '--qpc_time','--no_track_input','--no_track_gpu','--no_track_display','--no_console_stats','--output_file',str(raw)],
            offline_etw=dict(session=session,start_command=[str(offline.XPERF),'-start',session,'-on',offline.PROVIDERS]+
                offline.OPTIONS+['-f',str(etl)],stop_command=[str(offline.XPERF),'-stop',session],
                xperf_sha256='a'*64,etl_path=str(etl),header_path=str(header),max_file_mb=offline.MAX_MB,
                etl_sha256=hashlib.sha256(etl.read_bytes()).hexdigest(),header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
                logger_path=str(logger),logger_sha256=hashlib.sha256(logger.read_bytes()).hexdigest(),actual_buffers=[64,120],
                logger_end_path=str(logger_end),logger_end_sha256=hashlib.sha256(logger_end.read_bytes()).hexdigest(),
                adapter_sha256=hashlib.sha256(Path(offline.__file__).read_bytes()).hexdigest(),
                raw_csv_path=str(raw),raw_csv_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                etl_bytes=etl.stat().st_size,stop_succeeded=True,header_zero_loss=True,ready_qpc=1000,end_qpc=2500,
                qpc_frequency=50,session_polls_qpc=[999]+list(range(1099,2500,100))+[2501]))
        cpath.write_text(json.dumps(capture))
        apath=Path(run['actions']);actions=json.loads(apath.read_text())
        actions['capture_sha256']=hashlib.sha256(cpath.read_bytes()).hexdigest();apath.write_text(json.dumps(actions))
        with patch.object(offline.base,'ROOT',self.root):
            result=perf.analyze_run(run,self.scenario,self.root)
            self.assertIn('backend=xperf_etl',result['collector_options'])
            capture['synthetic_identity_stubs']=True;cpath.write_text(json.dumps(capture))
            actions['capture_sha256']=hashlib.sha256(cpath.read_bytes()).hexdigest();apath.write_text(json.dumps(actions))
            with self.assertRaisesRegex(ValueError,'Synthetic'):perf.analyze_run(run,self.scenario,self.root)
            del capture['synthetic_identity_stubs'];cpath.write_text(json.dumps(capture))
            actions['capture_sha256']=hashlib.sha256(cpath.read_bytes()).hexdigest();apath.write_text(json.dumps(actions))
            etl.write_bytes(b'tampered')
            with self.assertRaises(ValueError):perf.analyze_run(run,self.scenario,self.root)

    def test_changed_content_display_action_or_cache_invalidates_comparison(self):
        for field, value in (('hardware_sha256','a'*64),('save_sha256','b'*64),
                ('other_mods_sha256','c'*64),('settings_sha256','d'*64),('resolution',[1280,720]),
                ('fps_cap',None),('display_mode','fullscreen'),('cache_state','cold'),('actions',['up','down'])):
            with self.subTest(field=field):
                data=copy.deepcopy(self.manifest);data['runs'][1]['scenario'][field]=value
                with self.assertRaisesRegex(ValueError,'scenario differs'):
                    perf.compare(data,self.root)

    def test_action_coverage_and_observation_required(self):
        path=Path(self.manifest['runs'][1]['actions'])
        for transform in (lambda x:x.update(ui_transitions_verified=False),
                          lambda x:x['events'][0].update(start_qpc=999),
                          lambda x:x['events'][1].update(action='up'),
                          lambda x:x.update(process_creation_filetime=999)):
            trace=json.loads(path.read_text());old=copy.deepcopy(trace);transform(trace);path.write_text(json.dumps(trace))
            with self.assertRaises(ValueError):perf.compare(self.manifest,self.root)
            path.write_text(json.dumps(old))

    def test_missing_qpc_mixed_swapchain_and_stale_csv_rejected(self):
        path=Path(self.manifest['runs'][0]['csv']);raw=path.read_bytes()
        path.write_bytes(raw+b'junk')
        with self.assertRaisesRegex(ValueError,'CSV'):
            perf.compare(self.manifest,self.root)
        path.write_bytes(raw)
        content=path.read_text();path.write_text(content.replace('CPUStartQPC','NoClock'))
        with self.assertRaisesRegex(ValueError,'QPC'):
            perf.read_frames(path,100,hashlib.sha256(path.read_bytes()).hexdigest())
        path.write_bytes(raw)
        lines=path.read_text().splitlines();fields=lines[-1].split(',');fields[1]='2';lines[-1]=','.join(fields)
        path.write_text('\n'.join(lines)+'\n')
        with self.assertRaisesRegex(ValueError,'swapchains'):
            perf.read_frames(path,100,hashlib.sha256(path.read_bytes()).hexdigest())

    def test_unbalanced_order_overlapping_runs_and_loss_rejected(self):
        data=copy.deepcopy(self.manifest);data['runs'][2:]=copy.deepcopy(data['runs'][:2])
        data['runs'][2]['started_ns']=14000;data['runs'][2]['ended_ns']=15000
        data['runs'][3]['started_ns']=16000;data['runs'][3]['ended_ns']=17000
        with self.assertRaisesRegex(ValueError,'both baseline'):
            perf.compare(data,self.root)
        data=copy.deepcopy(self.manifest);data['runs'][1]['started_ns']=data['runs'][0]['ended_ns']
        with self.assertRaisesRegex(ValueError,'overlap'):
            perf.compare(data,self.root)
        path=Path(self.manifest['runs'][0]['capture']);data=json.loads(path.read_text());data['analysis']['event_loss_warning']=True
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'lossy'):
            perf.compare(self.manifest,self.root)

    def test_baseline_requires_confirmed_absence_of_all_apex_components(self):
        path=Path(self.manifest['runs'][0]['mod_state'])
        mods=json.loads(path.read_text());mods['apex_overlay_loaded']=True
        path.write_text(json.dumps(mods))
        cpath=Path(self.manifest['runs'][0]['capture']);capture=json.loads(cpath.read_text())
        capture['mod_state_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();cpath.write_text(json.dumps(capture))
        tpath=Path(self.manifest['runs'][0]['actions']);trace=json.loads(tpath.read_text())
        trace['capture_sha256']=hashlib.sha256(cpath.read_bytes()).hexdigest();tpath.write_text(json.dumps(trace))
        with self.assertRaisesRegex(ValueError,'mod-state'):
            perf.compare(self.manifest,self.root)

    def test_capture_evidence_is_bound_to_game_mode_and_mod_state(self):
        path=Path(self.manifest['runs'][0]['capture']);original=json.loads(path.read_text())
        for key,value in (('game_exe_sha256','f'*64),('game_exe_hash_unchanged',False),('benchmark_mode','apex'),('mod_state_sha256','0'*64)):
            with self.subTest(key=key):
                data=copy.deepcopy(original);data[key]=value;path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError,'incomplete, invalid'):
                    perf.compare(self.manifest,self.root)

    def test_after_window_disagreement_and_command_duration_rejected(self):
        path=Path(self.manifest['runs'][0]['capture']);original=json.loads(path.read_text())
        for action in (lambda x:x['window_after'].update(foreground_hwnd=999),
                       lambda x:x.update(configured_seconds=40)):
            with self.subTest(action=action):
                data=copy.deepcopy(original);action(data);path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):perf.compare(self.manifest,self.root)

    def test_different_collector_options_cannot_be_compared(self):
        path=Path(self.manifest['runs'][0]['capture'])
        capture=json.loads(path.read_text());capture['collector_command'].append('--no_track_gpu')
        path.write_text(json.dumps(capture))
        trace_path=Path(self.manifest['runs'][0]['actions']);trace=json.loads(trace_path.read_text())
        trace['capture_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();trace_path.write_text(json.dumps(trace))
        with self.assertRaisesRegex(ValueError,'options or duration'):
            perf.compare(self.manifest,self.root)

    def test_reused_capture_and_identical_timestamps_are_not_independent_trials(self):
        data=copy.deepcopy(self.manifest)
        data['runs'][3]['capture']=data['runs'][0]['capture']
        data['runs'][3]['csv']=data['runs'][0]['csv']
        data['runs'][3]['actions']=data['runs'][0]['actions']
        data['runs'][3]['mod_state']=data['runs'][0]['mod_state']
        with self.assertRaisesRegex(ValueError,'reused'):
            perf.compare(data,self.root)

    def test_hitch_crossing_action_end_is_included_using_present_qpc(self):
        spec = self.manifest['runs'][1]
        path = Path(spec['csv'])
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream); fields = reader.fieldnames; rows = list(reader)
        for n, row in enumerate(rows): row['CPUStartQPC'] = str(500 + n * 10)
        rows[15]['MsBetweenPresents'] = '400'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        cpath = Path(spec['capture']); captured = json.loads(cpath.read_text())
        captured['analysis']['csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        cpath.write_text(json.dumps(captured))
        tpath = Path(spec['actions']); trace = json.loads(tpath.read_text())
        trace['capture_sha256'] = hashlib.sha256(cpath.read_bytes()).hexdigest()
        trace['events'][0].update(start_qpc=1101, end_qpc=1145)
        tpath.write_text(json.dumps(trace))
        result = perf.analyze_run(spec, self.scenario, self.root)
        self.assertEqual(result['action_windows'][0]['max_ms'], 400)
        self.assertEqual(result['action_windows'][0]['selection'], 'present-interval-overlap')

    def test_present_timestamp_is_required_for_action_alignment(self):
        path = Path(self.manifest['runs'][0]['csv'])
        path.write_text(path.read_text().replace('TimeInQPC', 'NoPresentClock'))
        with self.assertRaisesRegex(ValueError, 'QPC'):
            perf.read_frames(path, 100, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_distinct_metadata_cannot_reuse_the_same_raw_csv(self):
        first, duplicate = self.manifest['runs'][0], self.manifest['runs'][3]
        duplicate['csv'], duplicate['mod_state'] = first['csv'], first['mod_state']
        captured = json.loads(Path(first['capture']).read_text())
        captured['collector_command'][-1] = 'fresh-session-but-old-csv'
        cpath = Path(duplicate['capture']); cpath.write_text(json.dumps(captured))
        trace = json.loads(Path(first['actions']).read_text())
        trace['capture_sha256'] = hashlib.sha256(cpath.read_bytes()).hexdigest()
        Path(duplicate['actions']).write_text(json.dumps(trace))
        with self.assertRaisesRegex(ValueError, 'Raw CSV'):
            perf.compare(self.manifest, self.root)


if __name__=='__main__':unittest.main()
