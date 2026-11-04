"""Strict comparison tests use only fabricated trace/profile evidence in temp."""
import copy
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import compare_provenance_stages as strict
import compare_hitch_stages as legacy
import hitch_stage
import mod_provenance as provenance
import offline_xperf as offline

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value),encoding='utf-8')

def definition(name,features,artifacts,package=False):
    return dict(id=name,features=features,artifacts=artifacts,
        loaded=dict(apex_script_loaded=bool(features),apex_cas_package_loaded=package,apex_overlay_loaded=False))

class StrictStageTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.work=self.root/'.work';self.work.mkdir()
        self.profile=str(self.root/'The Sims 4');self.exe=str(self.root/'TS4_x64.exe')
        self.base=[dict(path='Resource.cfg',bytes=8,sha256='9'*64)]
        self.control=definition('vanilla',[],[])
        self.hybrid=definition('hybrid',['hybrid'],[dict(path='Apex/ApexOccultHybrid.ts4script',sha256='a'*64)])
        self.scenario=dict(name='synthetic',game_exe_sha256='1'*64,hardware_sha256='2'*64,
            save_sha256='3'*64,other_mods_sha256=strict.inventory_digest(self.base),settings_sha256='5'*64,
            profile_id='test-only',resolution=[1920,1080],dpi=96,display_mode='windowed',refresh_hz=60,
            fps_cap=60,renderer='dx11',cache_state='warm',game_mode='CAS',actions=['body','tattoo','down','up'])
        self.experiment=dict(schema=2,scenario=self.scenario,stages=[self.control,self.hybrid],comparisons=[])
        self.proofs=[];self.runs=[]
        for i,stage in enumerate((self.control,self.hybrid,self.hybrid,self.control)):
            self.runs.append(self.build_run(i,stage))
        self.experiment['comparisons'].append(dict(control='vanilla',candidate='hybrid',runs=self.runs))
        self.exp_path=self.work/'experiment.json';self.refresh_experiment()
        self.manifest=dict(schema=1,experiment=str(self.exp_path),proofs=self.proofs)
        self.root_patch=patch.object(offline.base,'ROOT',self.root);self.root_patch.start();self.addCleanup(self.root_patch.stop)

    def refresh_experiment(self):write(self.exp_path,self.experiment)

    def build_run(self,i,stage):
        pid=100+i;creation=pid*100;prefix=self.work/('run%d'%i);base_qpc=10000+i*10000
        ready=base_qpc+1000;end=base_qpc+4000
        etl=Path(str(prefix)+'.etl');etl.write_bytes(('trace%d'%i).encode())
        parse_log=Path(str(prefix)+'.parse.log');parse_log.write_text('Started recording.\nStopped recording.\n')
        header=Path(str(prefix)+'.header');header.write_text('Clock type : PerfCounter\nTotal # Lost Buffers : 0\n'
            'Total # Lost Events : 0\nNumber of Traces : 1\nLog file mode : Sequential\nTrace name: '+str(etl)+'\n')
        session='ApexOffline'+('%032x'%i)
        logger=Path(str(prefix)+'.logger');logger.write_text('Logger Name : '+session+'\nBuffer Size : 1024\n'
            'Minimum Buffers : 64\nMaximum Buffers : 120\nMaximum File Size : 1024\n'
            'Log File Mode : Sequential IndependentSession\nLog Filename : '+str(etl)+'\nTrace Flags : '+offline.PROVIDERS+'\n')
        logger_end=Path(str(prefix)+'.logger-end');logger_end.write_bytes(logger.read_bytes())
        raw=Path(str(prefix)+'.raw.csv');filtered=Path(str(prefix)+'.csv')
        gap=20 if not stage['features'] else 21
        with raw.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=('ProcessID','SwapChainAddress','PresentRuntime',
                'MsBetweenPresents','CPUStartQPC','TimeInQPC'));writer.writeheader()
            for n in range(150):writer.writerow(dict(ProcessID=pid,SwapChainAddress='1',PresentRuntime='DXGI',
                MsBetweenPresents=format(gap*10.0,'.14f'),CPUStartQPC=ready+n*gap,TimeInQPC=ready+n*gap))
        filtered.write_bytes(offline.bounded_csv(raw,pid,ready,end,100))
        window=dict(process_id=pid,process_creation_filetime=creation,image_path=self.exe,hwnd=200+i,
            window_class='Canvas-synthetic',ui_thread=20+i,client_size=[1920,1080],
            window_rect=[0,0,1920,1080],dpi=96,foreground_hwnd=200+i)
        mod_state=dict(schema=2,target_pid=pid,process_creation_filetime=creation,
            other_mods_sha256=self.scenario['other_mods_sha256'],inventory_and_loaded_modules_observed=True,
            observation_method='temporary synthetic fixture',stage=stage,stage_sha256=hitch_stage.digest(stage),**stage['loaded'])
        mods_path=Path(str(prefix)+'.mods.json');write(mods_path,mod_state)
        capture=dict(state='completed',ready_seen=True,window_identity_and_geometry_unchanged=True,
            target_pid=pid,collector_sha256=offline.base.PRESENTMON_SHA,configured_seconds=30,
            capture_elapsed_ns=30_000_000_000,benchmark_mode='stage',stage_id=stage['id'],
            stage_sha256=hitch_stage.digest(stage),game_exe_sha256=self.scenario['game_exe_sha256'],
            game_exe_hash_unchanged=True,mod_state_sha256=digest(mods_path),capture_backend='xperf_etl',
            profile=self.profile,window_before=copy.deepcopy(window),window_after=copy.deepcopy(window),
            analysis=dict(valid=True,event_loss_warning=False,swapchains=[{}],csv_sha256=digest(filtered)),
            collector_command=[str(offline.base.PRESENTMON),'--etl_file',str(etl),'--process_id',str(pid),
                '--qpc_time','--no_track_input','--no_track_gpu','--no_track_display','--no_console_stats','--output_file',str(raw)],
            offline_etw=dict(session=session,start_command=[str(offline.XPERF),'-start',session,'-on',offline.PROVIDERS]+
                offline.OPTIONS+['-f',str(etl)],stop_command=[str(offline.XPERF),'-stop',session],
                xperf_sha256='f'*64,etl_path=str(etl),header_path=str(header),max_file_mb=offline.MAX_MB,
                etl_sha256=digest(etl),header_sha256=digest(header),etl_bytes=etl.stat().st_size,
                logger_path=str(logger),logger_sha256=digest(logger),actual_buffers=[64,120],
                logger_end_path=str(logger_end),logger_end_sha256=digest(logger_end),
                adapter_sha256=digest(Path(offline.__file__)),raw_csv_path=str(raw),raw_csv_sha256=digest(raw),
                parse_log_path=str(parse_log),parse_log_sha256=digest(parse_log),
                stop_succeeded=True,header_zero_loss=True,ready_qpc=ready,end_qpc=end,qpc_frequency=100,
                session_polls_qpc=[ready-1]+list(range(ready+100,end,100))+[end+1]))
        cpath=Path(str(prefix)+'.capture.json');write(cpath,capture)
        actions=dict(capture_sha256=digest(cpath),target_pid=pid,process_creation_filetime=creation,
            clock='QPC',ui_transitions_verified=True,events=[dict(action=name,observed=True,
                start_qpc=ready+100+n*100,end_qpc=ready+150+n*100) for n,name in enumerate(self.scenario['actions'])])
        apath=Path(str(prefix)+'.actions.json');write(apath,actions)
        observed_files=copy.deepcopy(self.base)+[dict(path=row['path'],bytes=42,sha256=row['sha256']) for row in stage['artifacts']]
        observed_files.sort(key=lambda x:(x['path'].casefold(),x['path']))
        identity=dict(profile=self.profile,token='1'*32,journal_sha256='2'*64,marker_sha256='3'*64)
        modules=[dict(path=self.exe,base=4096,size=10,file=dict(bytes=10,sha256='1'*64))]
        before=dict(schema=1,state='observed',identity=identity,process_id=pid,process_creation_filetime=creation,
            exe_path=self.exe,exe_sha256='1'*64,window=window,mods=dict(files=observed_files,
                files_count=len(observed_files),bytes=sum(x['bytes'] for x in observed_files),full_hash_passes=2,seconds=0.1),
            modules=modules,start_qpc=base_qpc+800,end_qpc=base_qpc+900,qpc_frequency=100,scan_seconds=0.1,
            game_profile_opened_proven=False,package_load_proven=False,loaded_memory_bytes_proven=False,
            transient_changes_between_observations_ruled_out=False,observation_scope='synthetic fixture')
        after=copy.deepcopy(before);after.update(start_qpc=base_qpc+4100,end_qpc=base_qpc+4200)
        before_path=Path(str(prefix)+'.before.json');after_path=Path(str(prefix)+'.after.json');write(before_path,before)
        comparison=provenance.compare(before,after,capture);comparison.update(prior_sha256=digest(before_path),capture_metadata_sha256=digest(cpath))
        after['comparison']=comparison;write(after_path,after)
        self.proofs.append(dict(capture_sha256=digest(cpath),before=str(before_path),before_sha256=digest(before_path),
            after=str(after_path),after_sha256=digest(after_path),action_trace_sha256=digest(apath)))
        return dict(kind=stage['id'],capture=str(cpath),csv=str(filtered),actions=str(apath),mod_state=str(mods_path),
            started_ns=10000+i*2000,ended_ns=11000+i*2000,scenario=copy.deepcopy(self.scenario))

    def compare(self):return strict.compare_strict(self.manifest,self.work,self.work)

    def rewrite_pair(self,index,change):
        proof=self.proofs[index];before_path=Path(proof['before']);after_path=Path(proof['after'])
        before=json.loads(before_path.read_text());after=json.loads(after_path.read_text());change(before);change(after)
        write(before_path,before);capture=json.loads(Path(self.runs[index]['capture']).read_text())
        expected=provenance.compare(before,after,capture);expected.update(prior_sha256=digest(before_path),capture_metadata_sha256=proof['capture_sha256'])
        after['comparison']=expected;write(after_path,after)
        proof.update(before_sha256=digest(before_path),after_sha256=digest(after_path))

    def make_legacy(self,index):
        run=self.runs[index];capture_path=Path(run['capture']);capture=json.loads(capture_path.read_text())
        evidence=capture['offline_etw'];evidence.pop('parse_log_path');evidence.pop('parse_log_sha256')
        evidence['adapter_sha256']=offline.LEGACY_ADAPTER_SHA256;write(capture_path,capture)
        action_path=Path(run['actions']);action=json.loads(action_path.read_text())
        action['capture_sha256']=digest(capture_path);write(action_path,action)
        self.proofs[index].update(capture_sha256=digest(capture_path),action_trace_sha256=digest(action_path))
        self.rewrite_pair(index,lambda observation:None)

    def test_real_comparator_with_synthetic_files_stops_at_slowdown(self):
        report=self.compare()
        self.assertEqual(report['state'],'slowdown_observed');self.assertEqual(report['stopped_at_stage'],'hybrid')
        self.assertEqual(report['provenance_pairs_checked'],4)
        self.assertTrue(all(row['metric_evaluated'] for row in report['provenance_reports']))
        for key in ('game_profile_opened_proven','package_load_proven','complete_apex_absence_proven',
                    'loaded_memory_bytes_proven','transient_changes_between_observations_ruled_out','performance_pass',
                    'loaded_flags_independently_verified','save_content_independently_verified'):
            self.assertFalse(report[key],key)
        self.assertTrue(report['stage_artifact_hashes_match_observations'])
        self.assertTrue(all(run['parse_log_verification']=='sha256_loss_checked'
                            for pair in report['comparisons'] for run in pair['runs']))

    def test_strict_legacy_runs_remain_explicitly_unverified(self):
        for index in range(4):self.make_legacy(index)
        report=self.compare()
        self.assertEqual(report['provenance_pairs_checked'],4)
        self.assertTrue(all(run['parse_log_verification']=='legacy_unverified'
                            for pair in report['comparisons'] for run in pair['runs']))
        self.assertTrue(any('no bound parser log' in text for text in report['limitations']))

    def test_strict_comparison_refuses_mixed_parse_log_generations(self):
        self.make_legacy(1)
        with self.assertRaisesRegex(ValueError,'Collector, options'):self.compare()

    def test_legacy_mode_and_empty_strict_experiment_remain_available(self):
        empty=copy.deepcopy(self.experiment);empty['comparisons']=[];write(self.exp_path,empty)
        self.assertEqual(legacy.compare(empty,self.work)['state'],'awaiting_measurements')
        report=strict.compare_strict(dict(schema=1,experiment=str(self.exp_path),proofs=[]),self.work,self.work)
        self.assertEqual(report['state'],'awaiting_measurements');self.assertEqual(report['provenance_pairs_checked'],0)

    def review_fixture(self):
        ui=definition('ui',['hybrid','ui'],[dict(path='Apex/ApexOccultHybrid.ts4script',sha256='b'*64)])
        self.experiment['stages'].append(ui)
        extra=[self.build_run(i,s) for i,s in enumerate((self.hybrid,ui,ui,self.hybrid),start=4)]
        self.experiment['comparisons'].append(dict(control='hybrid',candidate='ui',runs=extra))
        self.refresh_experiment()
        declaration=dict(schema=1,reviews=[dict(control_stage_sha256=hitch_stage.digest(self.hybrid),
            candidate_stage_sha256=hitch_stage.digest(ui),
            replaced_artifacts=legacy.transition_continuity(self.hybrid,ui)['replaced_artifacts'],
            review_evidence_sha256='e'*64)])
        path=self.work/'continuity-review.json';write(path,declaration)
        return path

    def test_review_path_in_private_work_is_bound_and_existing_parse_log_proof_survives(self):
        path=self.review_fixture()
        report=strict.compare_strict(self.manifest,self.work,self.work,continuity_review=path)
        self.assertEqual(report['continuity_review_declarations_sha256'],digest(path))
        self.assertEqual(report['state'],'slowdown_observed')
        self.assertEqual(report['not_evaluated'],['ui'])
        self.assertTrue(all(run['parse_log_verification']=='sha256_loss_checked'
                            for pair in report['comparisons'] for run in pair['runs']))
        self.assertFalse(report['performance_pass'])

    def test_review_path_outside_work_is_refused(self):
        path=self.root/'outside-review.json';write(path,dict(schema=1,reviews=[]))
        with patch.object(provenance,'_unlinked',wraps=provenance._unlinked) as unlinked:
            with self.assertRaisesRegex(ValueError,'inside private'):
                strict.compare_strict(self.manifest,self.work,self.work,continuity_review=path)
        self.assertNotIn(str(path),[str(call[0][0]) for call in unlinked.call_args_list])

    def test_duplicate_key_review_and_simulated_link_are_refused(self):
        path=self.work/'review-invalid.json';path.write_text('{"schema":1,"schema":1,"reviews":[]}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            strict.compare_strict(self.manifest,self.work,self.work,continuity_review=path)
        write(path,dict(schema=1,reviews=[]))
        original=provenance._unlinked
        def reject_link(value):
            if Path(value)==path:raise ValueError('simulated reparse entry')
            return original(value)
        with patch.object(provenance,'_unlinked',side_effect=reject_link):
            with self.assertRaisesRegex(ValueError,'reparse'):
                strict.compare_strict(self.manifest,self.work,self.work,continuity_review=path)

    def test_changed_review_file_rejected_after_comparison(self):
        path=self.review_fixture(); original=strict.stages.compare
        def mutate(*args,**kwargs):
            result=original(*args,**kwargs);write(path,dict(schema=1,reviews=[]));return result
        with patch.object(strict.stages,'compare',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'changed during comparison'):
                strict.compare_strict(self.manifest,self.work,self.work,continuity_review=path)

    def test_strict_entry_passes_bound_review_to_evaluated_replacement(self):
        path=self.review_fixture()
        def simulated_analysis(run,scenario,directory,stage):
            value=10
            return dict(kind=run['kind'],started_ns=run['started_ns'],ended_ns=run['ended_ns'],
                capture_sha256=digest(run['capture']),trace_sha256=digest(run['actions']),csv_sha256=digest(run['csv']),
                collector_sha256='f'*64,present_runtime='DXGI',collector_options=[],configured_seconds=30,
                statistics=dict(p95_ms=value,p99_ms=value,max_ms=value,over_33_3ms_per_1000=0),
                action_windows=[dict(action=name,max_ms=value,frames=10,over_33_3ms=0,
                    over_33_3ms_per_1000=0,duration_ms=1,p95_ms=value,p99_ms=value)
                    for name in scenario['actions']])
        # Strict file/observation checks are real synthetic-fixture checks;
        # metric/ETL analysis is stubbed solely to reach the later stage.
        with patch.object(strict.stages.frames,'analyze_run',side_effect=simulated_analysis):
            report=strict.compare_strict(self.manifest,self.work,self.work,continuity_review=path)
        self.assertEqual(len(report['comparisons']),2)
        self.assertTrue(report['comparisons'][1]['continuity']['review_declaration_matched'])
        self.assertFalse(report['comparisons'][1]['continuity']['retention_proven'])
        self.assertFalse(report['performance_pass'])

    def test_review_declaration_cannot_bypass_bound_parser_loss(self):
        path=self.review_fixture();run=self.runs[0]
        capture_path=Path(run['capture']);capture=json.loads(capture_path.read_text())
        log=Path(capture['offline_etw']['parse_log_path'])
        log.write_bytes('warning: 5 overflowed present events detected.\n'.encode('utf-16'))
        capture['offline_etw']['parse_log_sha256']=digest(log);write(capture_path,capture)
        action_path=Path(run['actions']);action=json.loads(action_path.read_text())
        action['capture_sha256']=digest(capture_path);write(action_path,action)
        self.proofs[0].update(capture_sha256=digest(capture_path),action_trace_sha256=digest(action_path))
        self.rewrite_pair(0,lambda observation:None)
        with self.assertRaisesRegex(ValueError,'reports loss'):
            strict.compare_strict(self.manifest,self.work,self.work,continuity_review=path)

    def test_empty_comparison_rechecks_review_file(self):
        empty=copy.deepcopy(self.experiment);empty['comparisons']=[];write(self.exp_path,empty)
        path=self.work/'review-empty.json';write(path,dict(schema=1,reviews=[]))
        original=strict.stages.compare
        def mutate(*args,**kwargs):
            result=original(*args,**kwargs);write(path,dict(schema=1,reviews=[{}]));return result
        with patch.object(strict.stages,'compare',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'changed during comparison'):
                strict.compare_strict(dict(schema=1,experiment=str(self.exp_path),proofs=[]),
                    self.work,self.work,continuity_review=path)

    def test_missing_extra_duplicate_and_reused_proofs_are_refused(self):
        for change in ('missing','extra','duplicate','reuse'):
            value=copy.deepcopy(self.manifest)
            if change=='missing':value['proofs'].pop()
            elif change=='extra':value['proofs'].append(copy.deepcopy(value['proofs'][0]))
            elif change=='duplicate':value['proofs'][1]['capture_sha256']=value['proofs'][0]['capture_sha256']
            else:
                value['proofs'][1]['before']=value['proofs'][0]['before']
                value['proofs'][1]['before_sha256']=value['proofs'][0]['before_sha256']
            with self.subTest(change=change),self.assertRaises(ValueError):strict.compare_strict(value,self.work,self.work)

    def test_wrong_stage_artifact_hash_and_extra_file_are_refused(self):
        def change(row):row['mods']['files'][0 if row['mods']['files'][0]['path'].startswith('Apex/') else 1]['sha256']='b'*64
        self.rewrite_pair(1,change)
        with self.assertRaisesRegex(ValueError,'artifact hash'):self.compare()

    def test_extra_or_changed_other_mods_are_refused(self):
        def add(row):
            row['mods']['files'].append(dict(path='unlisted.package',bytes=3,sha256='f'*64))
            row['mods']['files'].sort(key=lambda x:(x['path'].casefold(),x['path']))
            row['mods']['files_count']+=1;row['mods']['bytes']+=3
        self.rewrite_pair(1,add)
        with self.assertRaisesRegex(ValueError,'differ from control'):self.compare()

    def test_changed_control_file_across_stages_is_refused(self):
        def change(row):
            for item in row['mods']['files']:
                if item['path']=='Resource.cfg':item['sha256']='8'*64
        self.rewrite_pair(1,change)
        with self.assertRaisesRegex(ValueError,'control file changed'):self.compare()

    def test_control_digest_is_derived_from_observed_full_inventory(self):
        self.experiment['scenario']['other_mods_sha256']='0'*64
        for run in self.runs:run['scenario']['other_mods_sha256']='0'*64
        self.refresh_experiment()
        with self.assertRaisesRegex(ValueError,'observed control inventory'):self.compare()

    def test_profile_or_viewport_changes_between_stages_are_refused(self):
        proof=self.proofs[1];before_path=Path(proof['before']);after_path=Path(proof['after'])
        saved_before=before_path.read_bytes();saved_after=after_path.read_bytes();original=copy.deepcopy(proof)
        for change in ('profile','viewport'):
            before=json.loads(saved_before);after=json.loads(saved_after)
            for row in (before,after):
                if change=='profile':row['identity']['profile']=str(self.root/'other'/'The Sims 4')
                else:row['window']['window_rect']=[20,0,1940,1080]
            write(before_path,before);write(after_path,after)
            proof.update(before_sha256=digest(before_path),after_sha256=digest(after_path))
            try:
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,'profile, executable or viewport'):
                    self.compare()
            finally:before_path.write_bytes(saved_before);after_path.write_bytes(saved_after);proof.update(original)

    def test_known_stage_artifact_cannot_hide_in_control(self):
        def add(row):
            row['mods']['files'].append(dict(path='Apex/ApexOccultHybrid.ts4script',bytes=42,sha256='a'*64))
            row['mods']['files'].sort(key=lambda x:(x['path'].casefold(),x['path']))
            row['mods']['files_count']+=1;row['mods']['bytes']+=42
        self.rewrite_pair(0,add)
        with self.assertRaisesRegex(ValueError,'Control inventory contains'):self.compare()

    def test_overlay_declared_without_a_mods_dll_is_refused(self):
        self.experiment['stages'][1]['loaded']['apex_overlay_loaded']=True;self.refresh_experiment()
        with self.assertRaisesRegex(ValueError,'DLL artifact under Mods'):self.compare()

    def test_tampered_after_capture_csv_and_mod_state_are_refused(self):
        for name in ('after','capture','csv','mod_state','actions'):
            path=Path(self.proofs[0]['after'] if name=='after' else self.runs[0][name]);original=path.read_bytes()
            path.write_bytes(original+b' ')
            try:
                with self.subTest(name=name),self.assertRaises(ValueError):self.compare()
            finally:path.write_bytes(original)

    def test_synthetic_or_false_load_proof_claims_are_refused(self):
        for key,value in (('synthetic_probe_only',False),('package_load_proven',True)):
            before=Path(self.proofs[0]['before']);after=Path(self.proofs[0]['after'])
            raw_before=before.read_bytes();raw_after=after.read_bytes();original=copy.deepcopy(self.proofs[0])
            self.rewrite_pair(0,lambda row:row.update({key:value}))
            try:
                with self.subTest(key=key),self.assertRaises(ValueError):self.compare()
            finally:before.write_bytes(raw_before);after.write_bytes(raw_after);self.proofs[0].update(original)

    def test_marked_synthetic_action_or_mod_state_are_refused(self):
        run=self.runs[1];proof=self.proofs[1];action_path=Path(run['actions'])
        action_original=action_path.read_bytes();old_action_sha=proof['action_trace_sha256']
        action=json.loads(action_original);action['synthetic_identity_stubs']=False;write(action_path,action)
        proof['action_trace_sha256']=digest(action_path)
        with self.assertRaisesRegex(ValueError,'Action trace'):self.compare()
        action_path.write_bytes(action_original);proof['action_trace_sha256']=old_action_sha
        mod_path=Path(run['mod_state']);mods=json.loads(mod_path.read_text());mods['synthetic_probe_only']=False;write(mod_path,mods)
        capture_path=Path(run['capture']);capture=json.loads(capture_path.read_text());capture['mod_state_sha256']=digest(mod_path);write(capture_path,capture)
        proof['capture_sha256']=digest(capture_path)
        after_path=Path(proof['after']);after=json.loads(after_path.read_text());after['comparison']['capture_metadata_sha256']=digest(capture_path);write(after_path,after)
        proof['after_sha256']=digest(after_path)
        action=json.loads(action_path.read_text());action['capture_sha256']=digest(capture_path);write(action_path,action)
        proof['action_trace_sha256']=digest(action_path)
        with self.assertRaisesRegex(ValueError,'exact stage'):self.compare()

    def test_action_evidence_outside_private_work_is_refused(self):
        outside=self.root/'outside.json';outside.write_text('{}');self.runs[0]['actions']=str(outside);self.refresh_experiment()
        with self.assertRaisesRegex(ValueError,'private .work'):self.compare()

    def test_capture_stage_identity_and_snapshot_qpc_are_bound(self):
        capture_path=Path(self.runs[1]['capture']);capture=json.loads(capture_path.read_text())
        capture['stage_id']='wrong-stage';write(capture_path,capture);self.proofs[1]['capture_sha256']=digest(capture_path)
        after_path=Path(self.proofs[1]['after']);after=json.loads(after_path.read_text())
        after['comparison']['capture_metadata_sha256']=digest(capture_path);write(after_path,after)
        self.proofs[1]['after_sha256']=digest(after_path)
        action_path=Path(self.runs[1]['actions']);actions=json.loads(action_path.read_text())
        actions['capture_sha256']=digest(capture_path);write(action_path,actions)
        self.proofs[1]['action_trace_sha256']=digest(action_path)
        with self.assertRaisesRegex(ValueError,'exact stage'):self.compare()

    def test_before_scan_cannot_overlap_the_recording(self):
        proof=self.proofs[0];before_path=Path(proof['before']);before=json.loads(before_path.read_text())
        capture=json.loads(Path(self.runs[0]['capture']).read_text())
        before['end_qpc']=capture['offline_etw']['ready_qpc']+1;write(before_path,before);proof['before_sha256']=digest(before_path)
        with self.assertRaisesRegex(ValueError,'QPC ordering'):self.compare()

    def test_qpc_observations_cannot_overlap_between_runs(self):
        prior_after=json.loads(Path(self.proofs[0]['after']).read_text())
        proof=self.proofs[1];before_path=Path(proof['before']);after_path=Path(proof['after'])
        before=json.loads(before_path.read_text());before['start_qpc']=prior_after['end_qpc']-1;write(before_path,before)
        proof['before_sha256']=digest(before_path)
        after=json.loads(after_path.read_text());after['comparison']['prior_sha256']=digest(before_path);write(after_path,after)
        proof['after_sha256']=digest(after_path)
        with self.assertRaisesRegex(ValueError,'runs overlap'):self.compare()

    def test_all_declared_proofs_checked_but_later_metrics_are_not_evaluated(self):
        third=definition('ui',['hybrid','maru-ui'],[dict(path='Apex/ApexCAS.package',sha256='b'*64),
            dict(path='Apex/ApexOccultHybrid.ts4script',sha256='a'*64)],package=True)
        self.experiment['stages'].append(third)
        runs=[self.build_run(i,stage) for i,stage in enumerate((self.hybrid,third,third,self.hybrid),start=4)]
        self.experiment['comparisons'].append(dict(control='hybrid',candidate='ui',runs=runs));self.refresh_experiment()
        report=self.compare()
        self.assertEqual(report['provenance_pairs_checked'],8)
        self.assertEqual(report['not_evaluated'],['ui'])
        self.assertEqual([r['metric_evaluated'] for r in report['provenance_reports']],[True]*4+[False]*4)
        self.assertEqual([r['full_etl_validation_performed'] for r in report['provenance_reports']],[True]*4+[False]*4)
        missing=copy.deepcopy(self.manifest);missing['proofs'].pop()
        with self.assertRaisesRegex(ValueError,'every declared run'):strict.compare_strict(missing,self.work,self.work)
        self.experiment['comparisons'][1]['runs'][0]['scenario']['cache_state']='cold';self.refresh_experiment()
        with self.assertRaisesRegex(ValueError,'adjacent stages'):self.compare()

    def test_cli_writes_only_fresh_private_report(self):
        manifest_path=self.work/'strict.json';write(manifest_path,self.manifest)
        output=self.work/'report.json'
        with patch.object(strict.frames,'ROOT',self.root), \
                patch.object(sys,'argv',['compare_provenance_stages.py','--manifest',str(manifest_path),'--output',str(output)]), \
                contextlib.redirect_stdout(io.StringIO()):
            strict.main();saved=output.read_bytes();report=json.loads(saved)
            self.assertTrue(report['strict_provenance_mode']);self.assertFalse(report['package_load_proven'])
            self.assertEqual(report['strict_manifest_sha256'],digest(manifest_path))
            with self.assertRaisesRegex(ValueError,'fresh output'):strict.main()
            self.assertEqual(saved,output.read_bytes())

    def test_cli_accepts_relative_private_review_and_rejects_outside(self):
        review=self.review_fixture();manifest_path=self.work/'strict-review.json';write(manifest_path,self.manifest)
        output=self.work/'reviewed-report.json'
        args=['compare_provenance_stages.py','--manifest',str(manifest_path),'--output',str(output),
              '--continuity-review',review.name]
        with patch.object(strict.frames,'ROOT',self.root),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
            strict.main()
        report=json.loads(output.read_text());self.assertEqual(report['continuity_review_declarations_sha256'],digest(review))
        self.assertEqual(report['state'],'slowdown_observed')
        outside=self.root/'outside.json';write(outside,dict(schema=1,reviews=[]))
        second=self.work/'rejected-report.json';args[-3]=str(second);args[-1]=str(outside)
        with patch.object(strict.frames,'ROOT',self.root),patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'inside private'):strict.main()
        self.assertFalse(second.exists())

if __name__=='__main__':unittest.main()
