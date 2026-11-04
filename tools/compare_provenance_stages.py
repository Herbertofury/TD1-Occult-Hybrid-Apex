"""Opt-in staged frame comparison with paired filesystem provenance.

The original stage comparator and manifests remain unchanged. This wrapper
requires offline captures and exact, separately collected before/after mod
observations; it never proves a package was loaded or a profile was opened.
"""
import argparse
import hashlib
import json
import ntpath
from pathlib import Path

import compare_frame_runs as frames
import compare_hitch_stages as stages
import hitch_stage
import mod_provenance as provenance

MAX_RUNS=1560
FLAGS=('game_profile_opened_proven','package_load_proven','loaded_memory_bytes_proven',
       'transient_changes_between_observations_ruled_out')

def inventory_digest(rows):
    """Canonical hash for the control's complete non-Apex Mods inventory."""
    raw=json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
    return hashlib.sha256(raw).hexdigest()

def _path(value,directory,work):
    if not isinstance(value,str) or not value:raise ValueError('Evidence path is required')
    path=Path(value)
    if not path.is_absolute():path=Path(directory)/path
    path=provenance._unlinked(path)
    if not provenance._inside(path,work):raise ValueError('Strict evidence must stay inside private .work')
    return path

def _read(value,directory,work,limit):
    path=_path(value,directory,work)
    data,sha=provenance.read_json_file(path,work,limit)
    return path,data,sha

def compare_strict(manifest,directory,work):
    """Validate all declared proofs, then delegate metric evaluation unchanged."""
    if (not isinstance(manifest,dict) or set(manifest)!={'schema','experiment','proofs'} or
            type(manifest['schema']) is not int or manifest['schema']!=1):
        raise ValueError('Strict comparison needs exact schema, experiment and proofs')
    work=provenance._unlinked(work)
    experiment_path,experiment,experiment_sha=_read(manifest['experiment'],directory,work,4*1024*1024)
    if (not isinstance(experiment,dict) or set(experiment)!={'schema','scenario','stages','comparisons'} or
            type(experiment.get('schema')) is not int or experiment['schema']!=2):
        raise ValueError('An existing schema-2 staged experiment is required')
    scenario=frames.validate_scenario(experiment['scenario'])
    ladder=hitch_stage.validate_ladder(experiment['stages'])
    for stage in ladder:
        if (stage['loaded']['apex_overlay_loaded'] and
                not any(row['path'].casefold().endswith('.dll') for row in stage['artifacts'])):
            raise ValueError('An overlay stage needs its declared DLL artifact under Mods; game-Bin-only DLLs are unsupported')
    comparisons=experiment['comparisons']
    if not isinstance(comparisons,list) or len(comparisons)>len(ladder)-1:
        raise ValueError('Invalid comparison list')
    run_specs=[];previous_end=0
    for index,comparison in enumerate(comparisons):
        if (not isinstance(comparison,dict) or set(comparison)!={'control','candidate','runs'} or
                comparison['control']!=ladder[index]['id'] or comparison['candidate']!=ladder[index+1]['id'] or
                not isinstance(comparison['runs'],list) or not 4<=len(comparison['runs'])<=40 or len(comparison['runs'])%2):
            raise ValueError('Every declared comparison must contain its adjacent stage pair and bounded runs')
        stage_map={ladder[index]['id']:ladder[index],ladder[index+1]['id']:ladder[index+1]}
        order=[]
        for run in comparison['runs']:
            if (not isinstance(run,dict) or set(run)!={'kind','capture','csv','actions','mod_state','started_ns','ended_ns','scenario'} or
                    run.get('kind') not in stage_map or run.get('scenario')!=scenario or
                    type(run.get('started_ns')) is not int or type(run.get('ended_ns')) is not int or
                    not previous_end<run['started_ns']<run['ended_ns']):
                raise ValueError('Run does not belong to its declared adjacent stages')
            previous_end=run['ended_ns'];order.append(run['kind'])
            run_specs.append((run,stage_map[run['kind']]))
        pairs=[tuple(order[i:i+2]) for i in range(0,len(order),2)]
        if any(set(pair)!=set(stage_map) for pair in pairs) or len(set(pairs))!=2:
            raise ValueError('Both adjacent stage orders are required')
    if len(run_specs)>MAX_RUNS:raise ValueError('Too many declared runs')
    proofs=manifest['proofs']
    if not isinstance(proofs,list) or len(proofs)!=len(run_specs):
        raise ValueError('Exactly one provenance pair is required for every declared run')
    by_capture={}
    for proof in proofs:
        if (not isinstance(proof,dict) or set(proof)!={'capture_sha256','before','before_sha256','after','after_sha256','action_trace_sha256'} or
                any(not frames._hash(proof.get(k)) for k in ('capture_sha256','before_sha256','after_sha256','action_trace_sha256')) or
                proof['capture_sha256'] in by_capture or
                any(not isinstance(proof[k],str) or not proof[k] for k in ('before','after'))):
            raise ValueError('Each capture needs one unique before/after provenance pair')
        by_capture[proof['capture_sha256']]=proof
    run_info=[];capture_seen=set();file_pins=[(experiment_path,experiment_sha)]
    for run,stage in run_specs:
        capture_path,capture,capture_sha=_read(run.get('capture'),experiment_path.parent,work,4*1024*1024)
        if capture_sha in capture_seen or capture_sha not in by_capture:
            raise ValueError('Capture was reused or has no unique provenance pair')
        capture_seen.add(capture_sha)
        if not isinstance(capture,dict) or capture.get('capture_backend')!='xperf_etl':
            raise ValueError('Strict comparison supports only offline xperf captures')
        run_info.append((run,stage,capture_path,capture_sha,by_capture[capture_sha]))
        file_pins.append((capture_path,capture_sha))
    if capture_seen!=set(by_capture):raise ValueError('A provenance pair is unused')
    if not run_info:
        result=stages.compare(experiment,experiment_path.parent)
        result.update(strict_provenance_mode=True,provenance_pairs_checked=0,
            other_mods_inventory_sha256=None,game_profile_opened_proven=False,package_load_proven=False,
            complete_apex_absence_proven=False,loaded_memory_bytes_proven=False,
            transient_changes_between_observations_ruled_out=False,
            stage_artifact_hashes_match_observations=False,loaded_flags_independently_verified=False,
            save_content_independently_verified=False)
        result['experiment_sha256']=experiment_sha
        return result
    baseline_info=next((x for x in run_info if x[1]['id']==ladder[0]['id']),None)
    if baseline_info is None:raise ValueError('An observed control inventory is required')
    _,baseline,baseline_sha=_read(baseline_info[4]['before'],directory,work,provenance.MAX_EVIDENCE)
    if baseline_sha!=baseline_info[4]['before_sha256']:raise ValueError('Control observation hash differs')
    provenance.validate_observation(baseline)
    baseline_rows=baseline['mods']['files'];base_by_name={row['path'].casefold():row for row in baseline_rows}
    base_identity=(ntpath.normcase(baseline['identity']['profile']),baseline['identity']['token'],
                   ntpath.normcase(baseline['exe_path']))
    base_window=baseline['window']
    base_layout=(base_window['client_size'],base_window['window_rect'],base_window['dpi'],
                 base_window['foreground_hwnd']==base_window['hwnd'])
    known_artifacts={row['path'].casefold() for stage in ladder for row in stage['artifacts']}
    if set(base_by_name)&known_artifacts:
        raise ValueError('Control inventory contains a declared stage artifact')
    base_sha=inventory_digest(baseline_rows)
    if scenario['other_mods_sha256']!=base_sha:
        raise ValueError('Scenario other-mods hash differs from the observed control inventory')
    used_observations=set();reports=[];previous_qpc_end=0;frequency=baseline['qpc_frequency']
    for spec,stage,capture_path,capture_sha,proof in run_info:
        _,capture,capture_now=_read(str(capture_path),directory,work,4*1024*1024)
        if capture_now!=capture_sha:raise ValueError('Capture metadata changed during validation')
        before_path,before,before_sha=_read(proof['before'],directory,work,provenance.MAX_EVIDENCE)
        after_path,after,after_sha=_read(proof['after'],directory,work,provenance.MAX_EVIDENCE)
        if before_sha!=proof['before_sha256'] or after_sha!=proof['after_sha256']:
            raise ValueError('Observation file differs from its pinned hash')
        if before_sha==after_sha or before_sha in used_observations or after_sha in used_observations:
            raise ValueError('Each run requires fresh, unreused before and after observations')
        used_observations.update((before_sha,after_sha))
        for observed in (before,after):
            if any(observed.get(flag) is not False for flag in FLAGS):
                raise ValueError('Unsupported profile or package load proof claim')
            if ('synthetic_probe_only' in observed or 'synthetic_identity_stubs' in observed or
                    observed.get('game_measured') is False):
                raise ValueError('Synthetic observations are not valid game evidence')
            identity=observed.get('identity',{});window=observed.get('window',{})
            if (not isinstance(identity,dict) or not isinstance(window,dict) or
                    not isinstance(identity.get('profile'),str) or not isinstance(observed.get('exe_path'),str) or
                    (ntpath.normcase(identity['profile']),identity.get('token'),ntpath.normcase(observed['exe_path']))!=base_identity or
                    (window.get('client_size'),window.get('window_rect'),window.get('dpi'),
                     window.get('foreground_hwnd')==window.get('hwnd'))!=base_layout):
                raise ValueError('Observed profile, executable or viewport differs across stages')
        expected=provenance.compare(before,after,capture)
        if before['qpc_frequency']!=frequency or after['qpc_frequency']!=frequency or before['start_qpc']<=previous_qpc_end:
            raise ValueError('Observed runs overlap or do not share a stable QPC clock')
        previous_qpc_end=after['end_qpc']
        expected.update(prior_sha256=before_sha,capture_metadata_sha256=capture_sha)
        if after.get('comparison')!=expected:
            raise ValueError('After observation does not bind the exact prior observation and capture')
        action_path,action_trace,action_sha=_read(spec.get('actions'),experiment_path.parent,work,4*1024*1024)
        if (action_sha!=proof['action_trace_sha256'] or not isinstance(action_trace,dict) or
                'synthetic_identity_stubs' in action_trace or 'synthetic_probe_only' in action_trace or
                action_trace.get('game_measured') is False or
                action_trace.get('capture_sha256')!=capture_sha or type(action_trace.get('target_pid')) is not int or
                action_trace.get('target_pid')!=before['process_id'] or type(action_trace.get('process_creation_filetime')) is not int or
                action_trace.get('process_creation_filetime')!=before['process_creation_filetime'] or
                action_trace.get('clock')!='QPC' or action_trace.get('ui_transitions_verified') is not True):
            raise ValueError('Action trace is not bound to the capture and exact process')
        mod_path,mod_state,mod_sha=_read(spec.get('mod_state'),experiment_path.parent,work,4*1024*1024)
        if (capture.get('benchmark_mode')!='stage' or capture.get('stage_id')!=stage['id'] or
                capture.get('stage_sha256')!=hitch_stage.digest(stage) or capture.get('mod_state_sha256')!=mod_sha or
                not isinstance(mod_state,dict) or 'synthetic_identity_stubs' in mod_state or
                'synthetic_probe_only' in mod_state or mod_state.get('game_measured') is False or
                hitch_stage.validate_mod_state(mod_state,before['process_id'],before['process_creation_filetime'])!=stage or
                mod_state.get('other_mods_sha256')!=base_sha):
            raise ValueError('Capture or mod-state is not bound to the exact stage')
        csv_path=_path(spec.get('csv'),experiment_path.parent,work)
        csv_identity=provenance.hash_file(csv_path,work)
        analysis=capture.get('analysis')
        if (not isinstance(analysis,dict) or not frames._hash(analysis.get('csv_sha256')) or
                csv_identity['bytes']>frames.MAX_CSV or csv_identity['sha256']!=analysis['csv_sha256']):
            raise ValueError('Comparator CSV differs from the capture metadata')
        actual={row['path'].casefold():row for row in after['mods']['files']}
        artifacts={row['path'].casefold():row['sha256'] for row in stage['artifacts']}
        if set(actual)!=set(base_by_name)|set(artifacts):
            raise ValueError('Observed Mods files differ from control plus stage artifacts')
        for name,row in base_by_name.items():
            if actual[name]!=row:raise ValueError('A non-Apex control file changed across stages')
        if any(actual[name]['sha256']!=sha for name,sha in artifacts.items()):
            raise ValueError('Observed stage artifact hash differs')
        reports.append(dict(stage_id=stage['id'],stage_sha256=hitch_stage.digest(stage),capture_sha256=capture_sha,
            before_sha256=before_sha,after_sha256=after_sha,mod_state_sha256=mod_sha,
            csv_sha256=csv_identity['sha256'],action_trace_sha256=action_sha,stage_artifacts_observed=len(artifacts)))
        file_pins.extend(((before_path,before_sha),(after_path,after_sha),(mod_path,mod_sha),
                          (csv_path,csv_identity['sha256']),(action_path,action_sha)))
    # The original comparator independently validates ETL/CSV/action evidence,
    # order, stage declarations, and halts metric evaluation at a slowdown.
    result=stages.compare(experiment,experiment_path.parent)
    for path,sha in file_pins:
        if provenance.hash_file(path,work)['sha256']!=sha:
            raise ValueError('Experiment or provenance evidence changed during comparison')
    evaluated={run['capture_sha256'] for pair in result['comparisons'] for run in pair['runs']}
    for report in reports:
        report['metric_evaluated']=report['capture_sha256'] in evaluated
        report['full_etl_validation_performed']=report['metric_evaluated']
    result.update(strict_provenance_mode=True,provenance_pairs_checked=len(reports),
        other_mods_inventory_sha256=base_sha,provenance_reports=reports,
        game_profile_opened_proven=False,package_load_proven=False,complete_apex_absence_proven=False,
        loaded_memory_bytes_proven=False,transient_changes_between_observations_ruled_out=False,
        stage_artifact_hashes_match_observations=True,loaded_flags_independently_verified=False,
        save_content_independently_verified=False,
        experiment_sha256=experiment_sha)
    result['limitations'].extend([
        'Provenance records and stage feature/load declarations remain caller-supplied, not cryptographic attestations.',
        'Full ETL validation does not mean a legacy parser log was bound; see parse_log_verification for each evaluated run.',
        'The observed control can still contain undeclared Apex components; exact profile opening and actual package loading are not proven.',
        'Only snapshots outside the capture window are compared; intervening changes and loaded in-memory bytes are not proven.',
        'Every declared proof is validated up front; metric evaluation still stops at the first observed slowdown.'])
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();work=provenance._unlinked(frames.ROOT/'.work')
    path=_path(str(args.manifest),Path.cwd(),work)
    manifest,manifest_sha=provenance.read_json_file(path,work,4*1024*1024)
    output=_path(str(args.output.parent),Path.cwd(),work)/args.output.name
    if output.exists() or not output.parent.is_dir() or ':' in output.name:
        raise ValueError('A fresh output inside private .work is required')
    result=compare_strict(manifest,path.parent,work);result['strict_manifest_sha256']=manifest_sha
    if provenance.hash_file(path,work)['sha256']!=manifest_sha:
        raise ValueError('Strict manifest changed during comparison')
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'state':result['state'],'output':str(output),'performance_pass':False}))

if __name__=='__main__':main()
