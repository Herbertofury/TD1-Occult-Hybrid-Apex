"""Retire one failed switch after exact unsaved closure; no native replay."""
import copy
from pathlib import Path
import sys
import re
import cas_crash
import reusable_profile
from game_lifecycle import all_save_files
from source_manifest import sha256,write_json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_bank_transaction as receiver,form_appearance,bank_history


def validate(record,proof,sim_id,household_id,save_guid):
    pending=record.get('switch_pending');identity=proof.get('identity',{})
    if (any(not isinstance(i,str) or not re.fullmatch(r'[1-9][0-9]{0,19}',i) or int(i)>=1<<64 for i in (sim_id,household_id,save_guid)) or
        type(identity.get('pid')) is not int or not 0<identity['pid']<1<<32 or
        receiver._blocked(dict(record,switch_pending=None),save_guid+':'+sim_id) or
        not isinstance(pending,dict) or pending.get('schema')!=2 or
        pending.get('state') not in ('native-did-not-converge','recovery-required') or
        pending.get('runtime_pid')!=identity.get('pid') or pending.get('sim_id')!={'query':'returned-value','value':sim_id} or
        pending.get('native_operation_attempted') is not True or pending.get('manager_identity_verified') is not True or
        proof.get('operation')!='normal-exit-without-saving' or proof.get('save_requested') is not False or
        proof.get('game_exit_verified') is not True or proof.get('final_process_alive') is not False or
        proof.get('save_files_unchanged_verified') is not True or
        proof.get('requested_sim_id')!=sim_id or proof.get('requested_household_id')!=household_id or
        proof.get('requested_save_guid')!=save_guid or
        proof.get('before_all_saves')!=proof.get('after_all_saves') or not proof.get('before_all_saves')):
        raise ValueError('Exact failed switch and unsaved closure required; no metadata retired.')
    for name in ('stored_originals','desired_stored'):
        rows=pending.get(name)
        if not isinstance(rows,dict) or not rows or any(k not in ('1','2','4','8','16','32','64') for k in rows):
            raise ValueError('Complete known switch owner preimages required.')
        for fields in rows.values():form_appearance.fingerprint(fields)
    for name in ('active_original','desired_active'):form_appearance.fingerprint(pending[name])
    if pending.get('source') not in pending['stored_originals'] or pending.get('target') not in pending['stored_originals']:
        raise ValueError('Switch source/target has no retained native preimage.')
    return pending


@reusable_profile.serialized
def archive(state,bank,bank_sha,closure,closure_sha,sim_id,household_id,save_guid,slot_id,save_sha,output):
    reusable_profile.legacy.require_closed()
    _,session,profile,original=reusable_profile.load(state)
    _,proof=cas_crash.external_json(closure,profile,original,closure_sha)
    identity=proof.get('identity',{})
    if identity.get('test_token')!=session['token'] or Path(identity.get('profile','')).resolve()!=profile:
        raise ValueError('Closure belongs to another disposable profile.')
    bank=reusable_profile.writable(bank);output=reusable_profile.writable(output)
    if bank.name!='form_bank.json' or profile not in bank.parents or sha256(bank)!=bank_sha:
        raise ValueError('Exact active-profile form bank/hash required.')
    if output.exists() or output.suffix!='.json' or any(output==p or p in output.parents for p in (profile,original)):
        raise ValueError('Use one new external archive receipt.')
    if type(slot_id)is not int or not 0<slot_id<0xffffffff or sha256(profile/'saves'/('Slot_%08x.save'%slot_id))!=save_sha:
        raise ValueError('Original normal disposable save differs.')
    if all_save_files(profile)!=proof['after_all_saves']:raise ValueError('A save changed after closure.')
    data=receiver.load_for_write(bank);record=data['records'].get(save_guid+':'+sim_id)
    if not isinstance(record,dict):raise ValueError('Exact switch record is absent.')
    pending=validate(record,proof,sim_id,household_id,save_guid)
    history=record.setdefault('switch_history',[])
    if not isinstance(history,list):raise ValueError('Switch history has no typed index.')
    backup=reusable_profile.writable(output.with_suffix('.bank-before.json'))
    if backup.exists():raise ValueError('Archive preimage exists; inspect instead of replaying.')
    raw=bank.read_bytes()
    if sha256(bank)!=bank_sha:raise ValueError('Bank changed before its recovery preimage was written.')
    with backup.open('xb') as stream:
        stream.write(raw);stream.flush()
        import os
        os.fsync(stream.fileno())
    retained=copy.deepcopy(pending)
    retained.update(state='abandoned-unsaved-runtime',closure_sha256=closure_sha,native_appearance_restored=False,
        save_reload_verified=False,original_normal_save_sha256=save_sha)
    history.append(retained);record['switch_pending']=None
    bank_history.externalize(bank,record)
    reusable_profile.legacy.require_closed()
    receiver.save_from_read(bank,data)
    result=dict(ok=True,archived_switch_request_id=pending['request_id'],bank_before_sha256=bank_sha,
        bank_after_sha256=sha256(bank),preimage=str(backup),preimage_sha256=sha256(backup),
        original_normal_save_sha256=save_sha,native_appearance_restored=False,save_file_written=False,
        cas_completion_certified=False,old_bank_replay_authorized=False)
    write_json(output,result);return result
