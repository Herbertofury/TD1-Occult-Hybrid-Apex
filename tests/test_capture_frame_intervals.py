import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import capture_frame_intervals as capture


class CapturePreflightTests(unittest.TestCase):
    def state(self,mode):
        on=mode=='apex'
        result=dict(schema=1,target_pid=123,process_creation_filetime=42,
            inventory_and_loaded_modules_observed=True,observation_method='synthetic test',
            other_mods_sha256='a'*64,apex_script_loaded=on,apex_cas_package_loaded=on,
            apex_overlay_loaded=on,apex_candidate_sha256='b'*64 if on else None)
        if on:
            result['native_service_profile']=dict(enabled=False,inflight=0,installed=False)
            result['native_gfx_snapshot_profile']=dict(enabled=False,inflight=0,prepared=False,active_heap_hooks=False)
        return result

    def test_baseline_does_not_require_an_apex_bridge_or_apex_profiler(self):
        self.assertTrue(capture.validate_mod_state(self.state('baseline'),'baseline',123,42))

    def test_apex_profile_requires_inactive_diagnostics(self):
        state=self.state('apex')
        self.assertTrue(capture.validate_mod_state(state,'apex',123,42))
        for section,key,value in (('native_service_profile','enabled',True),
                ('native_service_profile','inflight',False),('native_service_profile','installed',True),
                ('native_gfx_snapshot_profile','prepared',True),('native_gfx_snapshot_profile','active_heap_hooks',True)):
            with self.subTest(section=section,key=key):
                changed=copy.deepcopy(state);changed[section][key]=value
                with self.assertRaisesRegex(ValueError,'profilers'):
                    capture.validate_mod_state(changed,'apex',123,42)

    def test_wrong_pid_identity_unobserved_inventory_or_component_mismatch_refused(self):
        state=self.state('baseline')
        for key,value in (('target_pid',124),('process_creation_filetime',43),
                ('inventory_and_loaded_modules_observed',False),('apex_script_loaded',True),
                ('apex_cas_package_loaded',True),('apex_overlay_loaded',True),('apex_candidate_sha256','b'*64)):
            with self.subTest(key=key):
                changed=copy.deepcopy(state);changed[key]=value
                with self.assertRaises(ValueError):capture.validate_mod_state(changed,'baseline',123,42)

    def test_no_capture_without_both_explicit_signals(self):
        for run,ready in ((False,False),(True,False),(False,True)):
            with self.subTest(run=run,ready=ready),patch.object(capture.subprocess,'Popen') as start:
                with self.assertRaisesRegex(ValueError,'explicit'):
                    capture.verify_start(argparse.Namespace(run=run,parent_ready=ready))
                start.assert_not_called()

    def test_window_matching_checks_geometry_focus_and_exact_process(self):
        original=dict(process_id=123,image_path='game',process_creation_filetime=42,hwnd=2,
            window_class='Canvas-1',ui_thread=3,client_size=[1920,1080],window_rect=[0,0,1920,1080],
            dpi=96,foreground_hwnd=2)
        self.assertTrue(capture.same_window(original,copy.deepcopy(original)))
        for key in original:
            changed=copy.deepcopy(original);changed[key]=None
            self.assertFalse(capture.same_window(original,changed),key)

    def test_loss_parser_never_calls_nonzero_loss_safe(self):
        for text,expected in [('warning: permissions',False),('0 events lost',False),
                ('Lost 0 events',False),('Lost 15 events',True),('12 buffers were dropped',True)]:
            self.assertEqual(capture.event_loss(text),expected,text)

    def test_presentmon_ring_overflow_is_not_treated_as_lossless(self):
        for count in ('1', '001', '16384', '4294967295'):
            self.assertTrue(capture.event_loss('WARNING:\t'+count+' OVERFLOWED  PRESENT EVENTS DETECTED.'))
        for text in ('no overflow', 'warning: 0 overflowed present events detected.',
                     'warning: consider increasing present event circular buffer size',
                     'warning: 123 overflowed widget events detected.'):
            self.assertFalse(capture.event_loss(text),text)
        self.assertTrue(capture.event_loss('0 events were lost.\nwarning: 2 overflowed present events detected.'))

    def test_ring_overflow_invalidates_capture_even_with_usable_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);paths={name:folder/(name+ext) for name,ext in
                (('csv','.csv'),('log','.log'),('metadata','.json'))}
            before=dict(process_creation_filetime=42)
            args=argparse.Namespace(pid=123,mode='baseline',seconds=10,exe=folder/'synthetic.exe',exe_sha256='1'*64)
            class Collector:
                pid=1000;returncode=0
                def __init__(self,command,stdout,stderr,creationflags):
                    self.polls=0
                    stdout.buffer.write('Started recording.\nwarning: 2 overflowed present events detected.\n'.encode('utf-16'))
                    stdout.buffer.flush();paths['csv'].write_text('mock valid CSV')
                def poll(self):
                    self.polls+=1
                    return None if self.polls==1 else 0
            with patch.object(capture,'verify_start',return_value=(folder,paths,before,self.state('baseline'),'a'*64)), \
                    patch.object(capture,'window_snapshot',return_value=before), \
                    patch.object(capture,'sha',return_value='1'*64), \
                    patch.object(capture.comparison,'read_frames',return_value=([16]*150,list(range(150)),'DXGI')), \
                    patch.object(capture.subprocess,'Popen',side_effect=Collector),patch.object(capture.time,'sleep'):
                with self.assertRaisesRegex(ValueError,'evidence checks'):capture.capture(args)
            result=json.loads(paths['metadata'].read_text())
            self.assertEqual(result['state'],'invalid')
            self.assertTrue(result['collector_event_loss_warning'])
            self.assertFalse(result['analysis']['valid'])

    def test_real_diagnostic_encodings_preserve_loss_and_refuse_unknown_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'raw.log'
            for encoding in ('utf-8','utf-8-sig','utf-16','utf-16-be'):
                raw='Started recording.\nwarning: 3016 ETW events were lost.\n'.encode(encoding)
                if encoding=='utf-16-be':raw=b'\xfe\xff'+raw
                path.write_bytes(raw)
                self.assertTrue(capture.event_loss(capture.read_collector_log(path)),encoding)
            for raw in (b'\xffbroken',b'w\x00a\x00r\x00n\x00',b'\xff\xfew'):
                path.write_bytes(raw)
                self.assertEqual(capture.read_collector_log(path,partial=True),'')
                with self.assertRaisesRegex(ValueError,'encoding'):capture.read_collector_log(path)

    def test_utf16_loss_invalidates_capture_even_with_usable_csv_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);paths={name:folder/(name+ext) for name,ext in
                (('csv','.csv'),('log','.log'),('metadata','.json'))}
            before=dict(process_creation_filetime=42)
            args=argparse.Namespace(pid=123,mode='baseline',seconds=10,exe=folder/'TS4_x64.exe',exe_sha256='1'*64)
            class Collector:
                pid=1000
                returncode=0
                def __init__(self,command,stdout,stderr,creationflags):
                    self.polls=0
                    stdout.buffer.write('Started recording.\nwarning: 3016 ETW events were lost.\n'.encode('utf-16'))
                    stdout.buffer.flush();paths['csv'].write_text('mock valid CSV')
                def poll(self):
                    self.polls+=1
                    return None if self.polls==1 else 0
            with patch.object(capture,'verify_start',return_value=(folder,paths,before,self.state('baseline'),'a'*64)), \
                    patch.object(capture,'window_snapshot',return_value=before), \
                    patch.object(capture,'sha',return_value='1'*64), \
                    patch.object(capture.comparison,'read_frames',return_value=([16]*150,list(range(150)),'DXGI')), \
                    patch.object(capture.subprocess,'Popen',side_effect=Collector),patch.object(capture.time,'sleep'):
                with self.assertRaisesRegex(ValueError,'evidence checks'):capture.capture(args)
            result=json.loads(paths['metadata'].read_text())
            self.assertEqual(result['state'],'invalid')
            self.assertTrue(result['collector_event_loss_warning'])
            self.assertTrue(result['analysis']['event_loss_warning'])
            self.assertFalse(result['analysis']['valid'])

    def test_mock_collector_uses_qpc_and_writes_a_complete_baseline_without_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);paths={name:folder/(name+ext) for name,ext in
                (('csv','.csv'),('log','.log'),('metadata','.json'))}
            before=dict(process_id=123,image_path='game',process_creation_filetime=42,hwnd=2,
                window_class='Canvas-1',ui_thread=3,client_size=[1920,1080],window_rect=[0,0,1920,1080],
                dpi=96,foreground_hwnd=2)
            args=argparse.Namespace(pid=123,mode='baseline',seconds=10,exe=folder/'TS4_x64.exe',exe_sha256='1'*64)
            mod_path=folder/'mod-state.json';mod_path.write_text(json.dumps(self.state('baseline')))
            mod_sha=hashlib.sha256(mod_path.read_bytes()).hexdigest()
            calls=[]
            class Collector:
                pid=1000
                returncode=0
                def __init__(self,command,stdout,stderr,creationflags):
                    calls.append(command);self.polls=0
                    stdout.write('Started recording.\n');stdout.flush()
                    path=Path(command[command.index('--output_file')+1])
                    with path.open('w',newline='',encoding='utf-8') as stream:
                        writer=csv.DictWriter(stream,fieldnames=('ProcessID','SwapChainAddress','PresentRuntime',
                                                               'MsBetweenPresents','CPUStartQPC','TimeInQPC'))
                        writer.writeheader()
                        for n in range(150):writer.writerow(dict(ProcessID=123,SwapChainAddress='1',
                            PresentRuntime='DXGI',MsBetweenPresents=16,CPUStartQPC=1000+n,TimeInQPC=1000+n))
                def poll(self):
                    self.polls+=1
                    return None if self.polls==1 else 0
            with patch.object(capture,'verify_start',return_value=(folder,paths,before,self.state('baseline'),mod_sha)), \
                    patch.object(capture,'window_snapshot',return_value=before), \
                    patch.object(capture,'sha',side_effect=lambda p:'1'*64 if Path(p)==args.exe else hashlib.sha256(Path(p).read_bytes()).hexdigest()), \
                    patch.object(capture.subprocess,'Popen',side_effect=Collector),patch.object(capture.time,'sleep'):
                result=capture.capture(args)
            self.assertEqual(result['state'],'completed')
            self.assertFalse(result['displayed_fps_measured'])
            self.assertEqual(result['analysis']['csv_sha256'],hashlib.sha256(paths['csv'].read_bytes()).hexdigest())
            self.assertIn('--qpc_time',calls[0])
            self.assertIn('--no_track_gpu', calls[0]); self.assertIn('--no_track_display', calls[0])
            self.assertNotIn('--v1_metrics', calls[0]);self.assertNotIn('--v2_metrics', calls[0])
            self.assertEqual(calls[0][calls[0].index('--process_id')+1],'123')
            self.assertFalse(result['appearance_write_requested']);self.assertEqual(result['ui_input_submitted'],0)
            self.assertEqual(json.loads(paths['metadata'].read_text())['state'],'completed')
            scenario=dict(name='body-tattoo',game_exe_sha256='1'*64,hardware_sha256='2'*64,
                save_sha256='3'*64,other_mods_sha256='a'*64,settings_sha256='5'*64,profile_id='test',
                resolution=[1920,1080],dpi=96,display_mode='windowed',refresh_hz=60,fps_cap=60,
                renderer='dx11',cache_state='warm',game_mode='CAS',actions=['body'])
            trace=dict(capture_sha256=hashlib.sha256(paths['metadata'].read_bytes()).hexdigest(),
                target_pid=123,process_creation_filetime=42,clock='QPC',ui_transitions_verified=True,
                events=[dict(action='body',observed=True,start_qpc=1100,end_qpc=1120)])
            trace_path=folder/'trace.json';trace_path.write_text(json.dumps(trace))
            spec=dict(kind='baseline',capture=str(paths['metadata']),csv=str(paths['csv']),
                actions=str(trace_path),mod_state=str(mod_path),started_ns=1,ended_ns=2,scenario=scenario)
            analyzed=capture.comparison.analyze_run(spec,scenario,folder)
            self.assertEqual(analyzed['statistics']['frames'],150)
            self.assertEqual(analyzed['action_windows'][0]['frames'],20)

    def test_window_failure_stops_only_the_owned_collector(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);paths={name:folder/(name+ext) for name,ext in
                (('csv','.csv'),('log','.log'),('metadata','.json'))}
            before=dict(process_creation_filetime=42)
            args=argparse.Namespace(pid=123,mode='baseline',seconds=10,exe=folder/'TS4_x64.exe',exe_sha256='1'*64)
            class Collector:
                pid=1000
                def __init__(self,command,stdout,stderr,creationflags):
                    self.terminated=False;stdout.write('Started recording.\n');stdout.flush()
                def poll(self):return None
                def terminate(self):self.terminated=True
                def wait(self,timeout):return 0
            process=[]
            def start(*args,**kwargs):process.append(Collector(*args,**kwargs));return process[-1]
            with patch.object(capture,'verify_start',return_value=(folder,paths,before,self.state('baseline'),'a'*64)), \
                    patch.object(capture,'window_snapshot',side_effect=ValueError('window gone')), \
                    patch.object(capture.subprocess,'Popen',side_effect=start):
                with self.assertRaisesRegex(ValueError,'window gone'):capture.capture(args)
            self.assertTrue(process[0].terminated)
            self.assertEqual(json.loads(paths['metadata'].read_text())['state'],'invalid')


if __name__=='__main__':unittest.main()
