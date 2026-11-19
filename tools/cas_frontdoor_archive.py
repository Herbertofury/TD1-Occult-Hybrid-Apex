"""Preserve a closed, never-observed native-entry transaction as history.

Requires the real Source frontdoor receipt and a later exact native cold-load
comparison. This is metadata recovery, never CAS acceptance or edit restoration.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Source'))
from apex_core import cas_bank_transaction as receiver, form_bank
from apex_core.form_bank_seal import _hash
from household_stress import owners
from source_manifest import sha256,write_json
from game_lifecycle import all_save_files
from cas_transition import process_alive
import reusable_profile


def prepare(entry,data,cold):
    if (entry.get('schema')!=1 or entry.get('stage')!='native-command-returned' or
            entry.get('full_household') is not True or entry.get('native_appearance_written') is not False or
            not receiver._token(entry.get('id')) or cold.get('ok') is not True or cold.get('save_submitted') is not False):
        raise ValueError('Exact Source native-entry receipt and later read-only cold comparison required.')
    members=entry.get('members');snapshots=cold.get('snapshots')
    roster=entry.get('roster_sim_ids')
    if (not isinstance(members,list) or not 1<=len(members)<=8 or not isinstance(snapshots,dict) or
            not isinstance(roster,list) or len(roster)!=len(set(roster)) or set(snapshots)!=set(roster) or
            [row.get('sim_id') for row in members]!=roster):
        raise ValueError('Complete exact household scope is required before any archival.')
    result=copy.deepcopy(data);held={};prior_pid=None;guid=None
    for row in members:
        sid=row['sim_id'];base=row.get('owner_observation',{}).get('original_owner',{})
        identity=dict(runtime_pid=base.get('runtime_pid'),sim_id=sid,
            household_id=entry.get('household_id'),save_guid=base.get('save_guid'))
        if (base.get('complete') is not True or base.get('original_sim_id')!=sid or
                base.get('household_id')!=identity['household_id'] or
                type(identity['runtime_pid']) is not int or identity['runtime_pid']<=0 or
                not isinstance(identity['save_guid'],str) or not identity['save_guid'].isdecimal()):
            raise ValueError('Native entry lacks the exact original producer identity.')
        if prior_pid is None:prior_pid,guid=identity['runtime_pid'],identity['save_guid']
        if (prior_pid!=identity['runtime_pid'] or guid!=identity['save_guid'] or
                cold.get('identity',{}).get('pid')==prior_pid):
            raise ValueError('Entry scope must share one distinct closed prior runtime and save.')
        key=guid+':'+sid;record=result.get('records',{}).get(key)
        if not isinstance(record,dict) or record.get('switch_pending'):
            raise ValueError('A captured record is missing or a different transition is unresolved.')
        pending,transaction=record.get('pending'),record.get('cas_transaction')
        form_bank._captured_schema2_archive(record,dict(prior_pid=prior_pid,household_id=identity['household_id'],
            save_guid=guid,expected_cas_transaction_sha256=_hash(transaction)),sid)
        checkpoint=row.get('checkpoint',{})
        if (transaction.get('native_entry_intent')!=entry['id'] or checkpoint.get('ok') is not True or
                checkpoint.get('native_appearance_written') is not False or
                checkpoint.get('checkpoint_sha256')!=_hash(pending) or
                checkpoint.get('expected_pending_sha256')!=transaction['transaction_sha256']):
            raise ValueError('Native entry receipt differs from the exact retained checkpoint.')
        snapshot=snapshots[sid];raw=pending['original_owners'];native=owners(snapshot)
        if (snapshot.get('sim',{}).get('id')!=sid or snapshot.get('household_id')!=identity['household_id'] or
                snapshot.get('save_guid')!=guid or snapshot.get('clock_speed')!=0 or
                set(native)!=set(raw['stored'])|{'active'} or
                native['active']['typed_payload']!=raw['active']['fields'] or
                any(native[lane]['typed_payload']!=fields for lane,fields in raw['stored'].items())):
            raise ValueError('Cold native appearances differ from the retained entry originals; no metadata change.')
        held[key]=(pending,transaction)
    return result,held,prior_pid,guid


@reusable_profile.serialized
def archive(state,entry_path,entry_hash,cold_path,cold_hash,slot_id,save_hash,output):
    reusable_profile.legacy.require_closed()
    state,journal,profile,original=reusable_profile.load(state)
    from cas_crash import external_json
    entry_path,entry=external_json(entry_path,profile,original,entry_hash)
    cold_path,cold=external_json(cold_path,profile,original,cold_hash)
    if (cold.get('identity',{}).get('test_token')!=journal['token'] or
            Path(cold.get('identity',{}).get('profile','')).resolve()!=profile or
            type(slot_id) is not int or not 0<slot_id<0xffffffff):
        raise ValueError('Cold comparison must identify this exact marked disposable profile.')
    output=reusable_profile.writable(output);backup=output.with_name(output.stem+'-bank-before.json')
    if (output.exists() or backup.exists() or output.suffix!='.json' or not output.parent.is_dir() or
            output in (state,entry_path,cold_path) or any(output==p or p in output.parents for p in (profile,original))):
        raise ValueError('Use new external recovery and backup paths.')
    bank=reusable_profile.writable(profile/'TD1_OccultHybridApexData'/'form_bank.json')
    data=receiver.load_for_write(bank);bank_bytes=bank.read_bytes();before=copy.deepcopy(data)
    planned,held,prior_pid,guid=prepare(entry,data,cold)
    if process_alive(prior_pid) is not False or process_alive(cold['identity']['pid']) is not False:
        raise ValueError('Both observed runtimes must be closed before metadata recovery.')
    saves=all_save_files(profile);slot='Slot_{:08x}.save'.format(slot_id)
    if slot not in saves or saves[slot]['sha256']!=save_hash:
        raise ValueError('Exact normal disk save changed; no metadata recovery.')
    receipt=dict(schema=1,operation='archive-closed-source-frontdoor',ok=False,
        entry_proof=str(entry_path),entry_sha256=entry_hash,cold_proof=str(cold_path),cold_sha256=cold_hash,
        prior_pid=prior_pid,save_guid=guid,archived_sim_ids=[key.split(':')[1] for key in held],
        bank_before_sha256=sha256(bank),bank_backup=str(backup),metadata_write_submitted=False,
        appearance_mutated=False,save_written=False,cas_return_verified=False,save_reload_verified=False)
    with backup.open('xb') as stream:
        stream.write(bank_bytes);stream.flush();os.fsync(stream.fileno())
    write_json(output,receipt)
    for key,(pending,transaction) in held.items():
        record=planned['records'][key]
        record.setdefault('failed_history',[]).append(dict(pending=copy.deepcopy(pending),
            cas_transaction=copy.deepcopy(transaction),pending_sha256=_hash(pending),
            cas_transaction_sha256=_hash(transaction),closure_kind='closed-source-frontdoor',
            entry_receipt_sha256=entry_hash,cold_comparison_sha256=cold_hash,metadata_archive_only=True,
            native_write_attempted=False,appearance_mutated=False,save_written=False))
        record['pending']=None;record['cas_transaction']=None
    reusable_profile.legacy.require_closed()
    if (bank.read_bytes()!=bank_bytes or all_save_files(profile)!=saves or
            sha256(entry_path)!=entry_hash or sha256(cold_path)!=cold_hash):
        raise ValueError('Bank, saves or proof changed before recovery; no metadata write.')
    receipt['metadata_write_submitted']=True;write_json(output,receipt)
    # Retain the receiver's exact read revision and cooperative atomic writer.
    data.clear();data.update(planned);receiver.save_from_read(bank,data)
    after=json.loads(bank.read_text(encoding='utf-8'))
    receipt.update(ok=after==planned and all_save_files(profile)==saves,
        bank_lanes_unchanged=all(after['records'][k]['bank']==before['records'][k]['bank'] for k in held),
        originals_preserved_in_failed_history=True,save_files_unchanged=all_save_files(profile)==saves,
        bank_sha256=sha256(bank))
    write_json(output,receipt);return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('state','entry-path','cold-path','output'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('entry-hash','cold-hash','save-hash'):p.add_argument('--'+name,required=True)
    p.add_argument('--slot-id',type=int,required=True)
    args=vars(p.parse_args())
    print(json.dumps(archive(**args),indent=2))
