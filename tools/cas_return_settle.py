"""Finish an already paused, observed Live return without replaying CAS or Play."""
import json
from pathlib import Path
import cas_bank_cli
import cas_return
import reusable_profile
from cli_identity_cache import session
from source_manifest import sha256,write_json


def validate_prior(prior,identity):
    if (not isinstance(prior,dict) or prior.get('operation')!='semantic-cas-return-to-live' or
            prior.get('ok') is not False or prior.get('outcome')!='unresolved' or
            any(prior.get(key) is not True for key in ('accept_submitted','accept_intent_observed','live_context_verified','final_paused')) or
            any(prior.get(key) for key in ('cas_bank_observe_attempted','form_bank_finish_attempted','return_metadata_completed')) or
            not cas_return.uuid_id(prior.get('cas_request_id')) or
            not isinstance(prior.get('identity'),dict) or
            any(prior['identity'].get(k)!=identity.get(k) for k in ('pid','test_token','script_sha256','profile'))):
        raise ValueError('Requires the exact unresolved, already paused Live return before bank observation; no CAS replay.')
    sid,household=prior.get('sim_id'),prior.get('household_id')
    ticks=prior.get('settle_ticks');producer=prior.get('producer_baseline',{})
    baseline=producer.get('baseline',{})
    if (not cas_return.decimal_id(sid) or not cas_return.decimal_id(household) or
            type(ticks) is not int or not 0<ticks<=100000 or producer.get('ok') is not True or
            producer.get('outcome')!='live-baseline' or producer.get('cas_request_id')!=prior['cas_request_id'] or
            not cas_return.decimal_id(baseline.get('sim_now_ticks'),zero=True)):
        raise ValueError('Retained native return baseline is unavailable.')
    steps=prior.get('steps')
    if not isinstance(steps,list) or len(steps)>4096:
        raise ValueError('Retained return step inventory is unavailable.')
    pauses=[r.get('result') for r in steps if isinstance(r,dict) and r.get('action')=='test_pause']
    paused=pauses[-1] if pauses else None
    validate_current(paused,sid,household,baseline,ticks)
    return sid,household,baseline,ticks,paused


def validate_current(snapshot,sid,household,baseline,ticks):
    if (not cas_return.live_snapshot(snapshot,sid,household) or snapshot.get('clock_speed')!=0 or
            any(snapshot.get(k)!=baseline.get(k) for k in ('client_id','zone_id','save_guid','household_id','sim_time_source')) or
            baseline.get('sim_id')!=sid or int(snapshot['sim_now_ticks'])-int(baseline['sim_now_ticks'])<ticks):
        raise ValueError('Exact paused Live identity and retained simulation progress are not verified.')


def run(state,prior_path,prior_sha,output,identity,request):
    _,journal,profile,original=reusable_profile.load(state)
    prior=cas_bank_cli._intent_file(prior_path,prior_sha,profile,original,limit=16*1024*1024)
    sid,household,baseline,ticks,paused=validate_prior(prior,identity)
    if identity.get('test_token')!=journal['token'] or Path(identity.get('profile','')).resolve()!=profile:
        raise ValueError('Return settlement does not belong to this disposable profile.')
    output=reusable_profile.writable(output)
    if output.exists() or output.suffix.lower()!='.json' or not output.parent.is_dir() or any(output==p or p in output.parents for p in (profile,original)):
        raise ValueError('Use a new external JSON settlement proof outside both profiles.')
    proof=dict(schema=1,operation='settle-observed-paused-cas-return',ok=False,identity=identity,
        original_return_sha256=prior_sha,original_cas_request_id=prior['cas_request_id'],steps=[],
        cas_accept_submitted=False,play_submitted=False,appearance_written=False,save_submitted=False,
        native_commit_result=prior.get('native_commit_outcome'),automatic_replay_allowed=False)
    with output.open('x',encoding='utf-8') as stream:json.dump(proof,stream)
    def call(action,value=None):
        row=dict(action=action,request_id=None);proof['steps'].append(row);write_json(output,proof)
        def intent(name,rid):
            if name!=action or not cas_return.uuid_id(rid) or row['request_id'] is not None:
                raise ValueError('Return metadata request has an invalid or duplicate submission UUID.')
            row['request_id']=rid;write_json(output,proof)
        result=request(state,action,sid,value=json.dumps(dict(test_token=identity['test_token'],value=value)),seconds=30,submission_observer=intent)
        row['result']=result;write_json(output,proof)
        if (result.get('ok') is not True or result.get('request_state')!='completed' or
                not row['request_id'] or result.get('request_id')!=row['request_id']):
            raise ValueError('Return metadata receipt remains unresolved; retain its UUID without replay.')
        return result
    try:
        with session(state):
            fresh=call('test_snapshot');validate_current(fresh,sid,household,baseline,ticks)
            if int(fresh['sim_now_ticks'])<int(paused['sim_now_ticks']):
                raise ValueError('Current simulation time precedes its retained paused receipt.')
            complete=call('test_cas_return_observed',dict(cas_request_id=prior['cas_request_id'],phase='complete',household_id=household,minimum_ticks=ticks))
            if complete.get('outcome')!='live-return' or complete.get('live_return_verified') is not True:
                raise ValueError('Producer did not verify completion of this exact original return.')
            proof.update(ok=True,final_paused=True,clock_progress_verified=True,producer_complete=complete,
                         simulation_progress_ticks=int(fresh['sim_now_ticks'])-int(baseline['sim_now_ticks']))
    except Exception as error:proof['error']=str(error)
    write_json(output,proof)
    return dict(ok=proof['ok'],output=str(output),proof_sha256=sha256(output),error=proof.get('error'),cas_accept_submitted=False,play_submitted=False)
