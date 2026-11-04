import copy
import hashlib
import io
import contextlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

TOOLS=Path(__file__).resolve().parents[1]/'tools'
if TOOLS.is_dir():sys.path.insert(0,str(TOOLS))
import mod_provenance as audit


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.profile=self.root/'The Sims 4';self.profile.mkdir();self.mods=self.profile/'Mods';self.mods.mkdir()
        (self.mods/'Resource.cfg').write_bytes(b'PackedFile *.package\n')
        (self.mods/'sub').mkdir();self.mod=self.mods/'sub'/'a.package';self.mod.write_bytes(b'ABCD')
        self.token='a'*32;self.marker=self.profile/'.apex-disposable-profile.json'
        self.marker.write_text(json.dumps({'disposable':True,'token':self.token}))
        self.journal=self.root/'journal.json'
        self.journal.write_text(json.dumps({'schema':2,'mode':'reusable-test-only','phase':'active',
            'token':self.token,'profile':str(self.profile),'artifacts':[]}))
        self.exe=self.root/'TS4_x64.exe';self.exe.write_bytes(b'synthetic executable')
        self.extra=self.root/'module.dll';self.extra.write_bytes(b'synthetic library')
        self.sha=hashlib.sha256(self.exe.read_bytes()).hexdigest();self.pid=44;self.creation=99
        self.window=dict(process_id=self.pid,process_creation_filetime=self.creation,image_path=str(self.exe),hwnd=4,
                         ui_thread=5,window_class='Canvas-synthetic',client_size=[100,100],
                         window_rect=[0,0,100,100],dpi=96,foreground_hwnd=1)
        self.modules=[dict(path=str(self.exe),base=4096,size=50),dict(path=str(self.extra),base=8192,size=20)]

    def tearDown(self):self.temp.cleanup()

    def snapshot(self,window=None,modules=None):
        return audit.observe(self.journal,self.profile,self.token,self.pid,self.exe,self.sha,self.creation,
            window or (lambda *args:copy.deepcopy(self.window)),modules or (lambda *args:copy.deepcopy(self.modules)))

    def capture(self,first,second):
        return dict(state='completed',capture_backend='xperf_etl',target_pid=self.pid,game_exe_sha256=self.sha,
            profile=str(self.profile),window_before=first['window'],window_after=second['window'],
            offline_etw=dict(ready_qpc=first['end_qpc'],end_qpc=second['start_qpc'],
                qpc_frequency=first['qpc_frequency']))

    def test_matching_observations_hash_every_mod_and_module_without_claiming_load(self):
        first=self.snapshot();second=self.snapshot();report=audit.compare(first,second,self.capture(first,second))
        self.assertEqual(first['mods']['files_count'],2)
        self.assertEqual(first['mods']['full_hash_passes'],2)
        self.assertEqual(len(first['modules']),2)
        self.assertEqual(report['state'],'matching_observed_snapshots')
        for key in ('game_profile_opened_proven','package_load_proven','loaded_memory_bytes_proven',
                    'transient_changes_between_observations_ruled_out','performance_pass','etl_validity_independently_proven'):
            self.assertFalse(report[key],key)
        self.assertTrue(report['capture_metadata_bound'])

    def test_changed_same_size_same_mtime_and_new_or_missing_mod_are_detected(self):
        initial=self.snapshot();stamp=self.mod.stat().st_mtime_ns
        self.mod.write_bytes(b'WXYZ');os.utime(str(self.mod),ns=(stamp,stamp))
        changed=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Mod contents changed'):audit.compare(initial,changed,self.capture(initial,changed))
        self.mod.write_bytes(b'ABCD');(self.mods/'new.package').write_bytes(b'x')
        changed=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Mod contents changed'):audit.compare(initial,changed,self.capture(initial,changed))

    def test_two_hash_passes_reject_a_change_while_scanning(self):
        original=audit.hash_file;calls=[]
        def changing(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if Path(path)==self.mod and not calls:
                calls.append(1);self.mod.write_bytes(b'WXYZ')
            return result
        with patch.object(audit,'hash_file',side_effect=changing):
            with self.assertRaisesRegex(ValueError,'between full hash passes'):audit.inventory_mods(self.mods)

    def test_directory_bound_is_enforced_while_streaming(self):
        (self.mods/'extra-one').write_bytes(b'x');(self.mods/'extra-two').write_bytes(b'y')
        with os.scandir(str(self.mods)) as entries:rows=list(entries)
        consumed=[]
        class StrictScanner:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def __iter__(self):
                for item in rows:
                    consumed.append(item)
                    if len(consumed)>3:raise AssertionError('Directory was read beyond the entry bound')
                    yield item
        with patch.object(audit,'MAX_FILES',2),patch.object(audit.os,'scandir',return_value=StrictScanner()):
            with self.assertRaisesRegex(ValueError,'entry bound'):audit.inventory_mods(self.mods)
        self.assertEqual(len(consumed),3)

    def test_known_oversized_file_is_rejected_before_any_content_read(self):
        with patch.object(audit,'MAX_BYTES',3),patch.object(audit.os,'fdopen',side_effect=AssertionError('Opened content stream')):
            with self.assertRaisesRegex(ValueError,'exceeds'):audit.hash_file(self.mod,self.mods)

    def test_file_descriptor_is_closed_if_stream_construction_fails(self):
        original_close=os.close
        with patch.object(audit.os,'fdopen',side_effect=RuntimeError('stream failed')), \
                patch.object(audit.os,'close',wraps=original_close) as close:
            with self.assertRaisesRegex(RuntimeError,'stream failed'):audit.hash_file(self.mod,self.mods)
            close.assert_called_once()

    def test_foreign_marker_or_inactive_journal_is_rejected(self):
        self.marker.write_text(json.dumps({'disposable':True,'token':'b'*32}))
        with self.assertRaisesRegex(ValueError,'marker'):self.snapshot()
        self.marker.write_text(json.dumps({'disposable':True,'token':self.token}))
        state=json.loads(self.journal.read_text());state['phase']='restored';self.journal.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError,'active'):self.snapshot()

    def test_duplicate_json_fields_are_rejected(self):
        self.journal.write_text('{"schema":2,"schema":2}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.snapshot()

    def test_boolean_schema_and_fractional_pass_counts_are_refused(self):
        first=self.snapshot();second=self.snapshot();capture=self.capture(first,second)
        invalid=copy.deepcopy(first);invalid['schema']=True
        with self.assertRaisesRegex(ValueError,'incomplete'):audit.compare(invalid,second,capture)
        for row in (first,second):row['mods']['full_hash_passes']=2.0
        with self.assertRaisesRegex(ValueError,'incomplete'):audit.compare(first,second,capture)

    def test_large_prior_evidence_is_bounded_separately_from_markers(self):
        path=self.root/'large.json';raw=json.dumps({'fixture':'a'*(1100*1024)}).encode('utf-8');path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'size bound'):audit.read_json_file(path)
        value,digest=audit.read_json_file(path,limit=audit.MAX_EVIDENCE)
        self.assertEqual(len(value['fixture']),1100*1024)
        self.assertEqual(digest,hashlib.sha256(raw).hexdigest())

    def test_reparse_entries_are_rejected_before_inventory(self):
        old=Path.lstat;target=self.mod
        def fake(path):
            item=old(path)
            if path==target:
                return types.SimpleNamespace(st_mode=item.st_mode,st_file_attributes=getattr(item,'st_file_attributes',0)|audit.REPARSE)
            return item
        with patch.object(Path,'lstat',fake):
            with self.assertRaisesRegex(ValueError,'reparse'):audit.inventory_mods(self.mods)

    def test_hardlinks_are_rejected(self):
        link=self.mods/'other.package'
        try:os.link(str(self.mod),str(link))
        except OSError as error:self.skipTest('Hardlink creation unavailable: '+str(error))
        with self.assertRaisesRegex(ValueError,'link'):audit.inventory_mods(self.mods)

    def test_changed_window_lifetime_or_module_inventory_is_rejected(self):
        bad=copy.deepcopy(self.window);bad['process_creation_filetime']=100
        with self.assertRaisesRegex(ValueError,'identity'):self.snapshot(window=lambda *args:bad)
        calls=[]
        def moved(*args):
            calls.append(1);value=copy.deepcopy(self.modules)
            if len(calls)>1:value[-1]['base']+=1
            return value
        with self.assertRaisesRegex(ValueError,'modules changed'):self.snapshot(modules=moved)

    def test_module_content_changes_are_detected(self):
        first=self.snapshot();self.extra.write_bytes(b'synthetic LIBRARY')
        second=self.snapshot()
        with self.assertRaisesRegex(ValueError,'modules changed'):audit.compare(first,second,self.capture(first,second))

    def test_capture_boundaries_prevent_reuse_or_scans_during_recording(self):
        first=self.snapshot();second=self.snapshot();capture=self.capture(first,second)
        with self.assertRaisesRegex(ValueError,'QPC ordering'):audit.compare(first,first,capture)
        for field,value in (('ready_qpc',first['end_qpc']-1),('end_qpc',second['start_qpc']+1),
                            ('qpc_frequency',first['qpc_frequency']+1)):
            altered=copy.deepcopy(capture);altered['offline_etw'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'QPC ordering'):
                audit.compare(first,second,altered)
        altered=copy.deepcopy(capture);altered['target_pid']+=1
        with self.assertRaisesRegex(ValueError,'identity'):audit.compare(first,second,altered)
        for key,value in (('synthetic_identity_stubs',False),('synthetic_probe_only',False),('game_measured',False)):
            altered=copy.deepcopy(capture);altered[key]=value
            with self.subTest(field=key),self.assertRaisesRegex(ValueError,'identity'):
                audit.compare(first,second,altered)

    def test_incomplete_observations_are_not_accepted_as_evidence(self):
        first=self.snapshot();second=self.snapshot();capture=self.capture(first,second)
        for key in ('identity','window','modules'):
            a=copy.deepcopy(first);b=copy.deepcopy(second);a.pop(key);b.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):audit.compare(a,b,capture)
        a=copy.deepcopy(first);b=copy.deepcopy(second);a['mods'].pop('files');b['mods'].pop('files')
        with self.assertRaisesRegex(ValueError,'incomplete'):audit.compare(a,b,capture)
        a=copy.deepcopy(first);b=copy.deepcopy(second)
        a['mods']['files'][0].pop('sha256');b['mods']['files'][0].pop('sha256')
        with self.assertRaisesRegex(ValueError,'SHA-256'):audit.compare(a,b,capture)
        a=copy.deepcopy(first);b=copy.deepcopy(second)
        a['modules'][0]['file'].pop('sha256');b['modules'][0]['file'].pop('sha256')
        with self.assertRaisesRegex(ValueError,'hash incomplete'):audit.compare(a,b,capture)

    def test_bad_executable_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            audit.observe(self.journal,self.profile,self.token,self.pid,self.exe,'0'*64,self.creation,
                lambda *args:self.window,lambda *args:self.modules)
        with self.assertRaisesRegex(ValueError,'include the exact executable'):
            self.snapshot(modules=lambda *args:[dict(path=str(self.extra),base=1,size=10)])

    def test_synthetic_cli_brackets_capture_and_preserves_existing_output(self):
        tools=self.root/'tools';tools.mkdir();work=self.root/'.work';work.mkdir()
        fake_frame=types.ModuleType('capture_frame_intervals')
        fake_frame.window_snapshot=lambda *args:copy.deepcopy(self.window)
        before=work/'before.json';after=work/'after.json';capture_path=work/'capture.json'
        common=['mod_provenance.py','--state',str(self.journal),'--profile',str(self.profile),'--token',self.token,
            '--pid',str(self.pid),'--creation',str(self.creation),'--exe',str(self.exe),'--exe-sha256',self.sha,'--run']
        def run(arguments):
            with patch.object(sys,'argv',common+arguments),patch.object(sys,'path',list(sys.path)), \
                    patch.dict(sys.modules,{'capture_frame_intervals':fake_frame}), \
                    patch.object(audit,'__file__',str(tools/'mod_provenance.py')), \
                    patch.object(audit,'windows_modules',return_value=copy.deepcopy(self.modules)), \
                    contextlib.redirect_stdout(io.StringIO()):
                audit.main()
        run(['--output',str(before)])
        first=json.loads(before.read_text());saved=before.read_bytes()
        capture=dict(state='completed',capture_backend='xperf_etl',target_pid=self.pid,
            game_exe_sha256=self.sha,profile=str(self.profile),window_before=first['window'],
            window_after=first['window'],offline_etw=dict(ready_qpc=first['end_qpc'],
            end_qpc=first['end_qpc']+1,qpc_frequency=first['qpc_frequency']))
        capture_path.write_text(json.dumps(capture))
        run(['--output',str(after),'--compare-to',str(before),'--capture-metadata',str(capture_path)])
        result=json.loads(after.read_text())['comparison']
        self.assertTrue(result['capture_metadata_bound'])
        self.assertFalse(result['game_profile_opened_proven'])
        self.assertEqual(result['prior_sha256'],hashlib.sha256(saved).hexdigest())
        self.assertEqual(result['capture_metadata_sha256'],hashlib.sha256(capture_path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'Fresh output'):run(['--output',str(before)])
        self.assertEqual(before.read_bytes(),saved)

    @unittest.skipUnless(os.name=='nt','Windows Toolhelp verification')
    def test_real_toolhelp_enumerates_only_the_synthetic_test_process(self):
        rows=audit.windows_modules(os.getpid())
        self.assertTrue(rows)
        self.assertTrue(any(Path(x['path']).name.casefold()==Path(sys.executable).name.casefold() for x in rows))
        self.assertTrue(all(x['base']>0 and x['size']>0 for x in rows))


if __name__=='__main__':unittest.main()
