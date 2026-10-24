"""Archive failed CAS metadata only after a pinned unsaved restart.

Complete originals remain in failed history. No appearance, save or bank lane is
restored here, and a response loss never authorizes another abandonment request.
"""
import hashlib
import json
import math
from pathlib import Path
import time

import apex_cli
import cas_transition
import game_lifecycle
import reusable_profile
from cas_return import decimal_id, uuid_id, native_live_context, live_snapshot, SIM_TIME_SOURCE
from game_discard import failed_context
from source_manifest import sha256, write_json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def hash_value(value):
    return isinstance(value, str) and len(value) == 64 and all(char in '0123456789abcdef' for char in value)


PREBINDING_REFUSAL = 'CAS checkpoint has no exact original native-Sim receiver capability; replay is blocked.'
PERSISTENCE_CHECKS = frozenset(('account_save_eligible', 'active_household_membership',
    'household_proto_exists', 'household_proto_identity', 'household_proto_membership',
    'manager_identity', 'runtime_household_identity', 'sim_proto_exists',
    'sim_proto_household_identity', 'sim_proto_identity'))


def _strict_live(value, sim_id, household_id, save_guid, speed):
    persistence = value.get('persistence') if isinstance(value, dict) else None
    checks = persistence.get('checks') if isinstance(persistence, dict) else None
    household = persistence.get('household_sim_ids') if isinstance(persistence,dict) else None
    saved = persistence.get('persisted_household_sim_ids') if isinstance(persistence,dict) else None
    return (live_snapshot(value, sim_id, household_id) and value.get('save_guid') == save_guid and
        value.get('clock_speed') == speed and isinstance(checks, dict) and
        set(checks)==PERSISTENCE_CHECKS and all(checks.get(name) is True for name in PERSISTENCE_CHECKS) and
        persistence.get('errors') == [] and persistence.get('persistence_verified_before_save') is True and
        persistence.get('save_reload_verified') is False and
        isinstance(household,list) and household.count(sim_id)==1 and
        isinstance(saved,list) and saved.count(sim_id)==1)


def prebinding_failure_context(path, expected_hash, failed_path, failed_hash, failed, old,
                               profile, original, sim_id, household_id, save_guid):
    """One terminal pre-binding refusal after native return; never unknown recovery."""
    path = reusable_profile.writable(path)
    if (not hash_value(expected_hash) or path == failed_path or
            any(path == root or root in path.parents for root in (profile, original)) or
            not path.is_file() or not 0 < path.stat().st_size <= 12 * 1024 * 1024 or sha256(path) != expected_hash):
        raise ValueError('Observer refusal proof is missing, unsafe or changed.')
    observer = json.loads(path.read_text(encoding='utf-8'))
    owner = failed.get('cas_bank_observe_request_id')
    if (not isinstance(observer, dict) or set(observer) != {'schema','identity','original_request_id',
            'request_resubmitted','result','source_proof_sha256'} or type(observer['schema']) is not int or
            observer['schema'] != 1 or observer['request_resubmitted'] is not False or
            not uuid_id(owner) or observer['original_request_id'] != owner or
            observer['source_proof_sha256'] != failed_hash or not isinstance(observer['identity'], dict) or
            any(observer['identity'].get(name) != old.get(name) for name in
                ('pid','test_token','script_sha256','profile'))):
        raise ValueError('Observer refusal is not the exact original runtime/proof/UUID without resubmission.')
    result = observer['result']
    if (not isinstance(result, dict) or set(result) != {'ok','message','request_id','request_state','save_reload_verified'} or
            result.get('ok') is not False or result.get('request_state') != 'failed' or
            result.get('request_id') != owner or result.get('message') != PREBINDING_REFUSAL or
            result.get('save_reload_verified') is not False):
        raise ValueError('Only the exact terminal pre-binding capability refusal permits metadata recovery.')
    if (type(failed.get('schema')) is not int or failed['schema'] != 1 or
            failed.get('operation') != 'semantic-cas-return-to-live' or failed.get('ok') is not False or
            failed.get('outcome') != 'live-return-cas-observation-unresolved' or
            failed.get('sim_id') != sim_id or failed.get('household_id') != household_id or
            not uuid_id(failed.get('cas_request_id')) or failed.get('cas_transaction_phase') != 'captured' or
            any(failed.get(name) is not True for name in ('accept_submitted','accept_intent_observed',
                'cas_peer_disappearance_verified','clock_progress_verified','final_paused','live_context_verified',
                'return_metadata_completed','no_input_replay','cas_bank_observe_attempted')) or
            any(failed.get(name) is not False for name in ('process_exit_verified','input_submitted',
                'form_bank_finish_attempted','form_bank_completion_verified','cas_bank_observation_verified',
                'appearance_persistence_verified','save_reload_verified')) or
            failed.get('cas_bank_observation_receipt') != result or
            failed.get('cas_bank_observation_receipt_sha256') != digest(result) or
            not hash_value(failed.get('checkpoint_sha256')) or not hash_value(failed.get('expected_pending_sha256')) or
            not isinstance(failed.get('crash'), dict) or failed['crash'].get('outcome') not in ('absent','unchanged')):
        raise ValueError('Pre-binding refusal lacks the exact native-return-only captured receipt.')
    owners = failed.get('owner_requests')
    matching = [row for row in owners if isinstance(row,dict) and row.get('action') == 'cas_bank_observe'] if isinstance(owners,list) else []
    if (not isinstance(owners,list) or len(owners)>256 or len(matching)!=1 or matching[0].get('request_id')!=owner or
            any(not isinstance(row,dict) or row.get('action') in ('cas_bank_prepare','cas_bank_commit',
                'cas_session_finish','test_save','test_save_current','test_save_and_exit') for row in owners)):
        raise ValueError('Pre-binding recovery requires exactly one retained observer and no finish/commit/Save command.')
    status = failed.get('form_bank_status')
    transaction = status.get('cas_transaction') if isinstance(status,dict) else None
    if (not isinstance(status,dict) or status.get('pending_schema') != 2 or status.get('pending_state')!='captured' or
            status.get('captured') is not True or status.get('switch_pending') is not False or
            not isinstance(transaction,dict) or transaction.get('phase')!='captured' or transaction.get('ok') is not True or
            transaction.get('expected_pending_sha256') != failed['expected_pending_sha256'] or
            transaction.get('checkpoint_sha256') != failed['checkpoint_sha256'] or
            transaction.get('raw_return_sha256') is not None or transaction.get('plan_sha256') is not None or
            any(transaction.get(name) is not False for name in ('native_write_attempted','native_write_possible',
                'metadata_commit_persisted','membership_or_traits_modified','writer_lease_present'))):
        raise ValueError('Failed observer does not retain a never-observed, unwritten schema2 status.')
    observation = failed.get('return_observation')
    baseline = observation.get('baseline') if isinstance(observation,dict) else None
    final = observation.get('final') if isinstance(observation,dict) else None
    if (not isinstance(observation,dict) or observation.get('ok') is not True or
            observation.get('live_return_verified') is not True or observation.get('cas_request_id') != failed['cas_request_id'] or
            observation.get('appearance_persistence_verified') is not False or
            observation.get('commit_submission_verified') is not False or not isinstance(baseline,dict) or not isinstance(final,dict) or
            any(row.get('sim_time_source') != SIM_TIME_SOURCE or row.get('sim_id') != sim_id or
                row.get('household_id') != household_id or row.get('save_guid') != save_guid or
                not decimal_id(row.get('sim_now_ticks'),zero=True) for row in (baseline,final)) or
            any(baseline.get(name)!=final.get(name) or not decimal_id(final.get(name)) for name in ('client_id','zone_id')) or
            type(failed.get('settle_ticks')) is not int or failed['settle_ticks']<=0 or
            any(row.get('minimum_ticks')!=failed['settle_ticks'] for row in (baseline,final)) or
            type(observation.get('advanced_ticks')) is not int or observation['advanced_ticks']<failed['settle_ticks'] or
            int(final['sim_now_ticks'])-int(baseline['sim_now_ticks'])!=observation['advanced_ticks']):
        raise ValueError('Pre-binding recovery requires positive actual simulation progression for this exact native return.')
    playing=failed.get('settled_snapshot')
    if (not _strict_live(playing,sim_id,household_id,save_guid,1) or
            any(playing.get(name)!=final.get(name) for name in ('client_id','zone_id')) or
            not int(baseline['sim_now_ticks'])<int(playing['sim_now_ticks'])<=int(final['sim_now_ticks'])):
        raise ValueError('Exact native Sim was not observed unpaused during actual return progression.')
    steps = failed.get('steps')
    pauses = [row.get('result') for row in steps if isinstance(row,dict) and row.get('action')=='test_pause'] if isinstance(steps,list) else []
    if (not isinstance(steps,list) or len(steps)>1024 or len(pauses)!=1 or
            not _strict_live(pauses[0],sim_id,household_id,save_guid,0) or
            any(pauses[0].get(name)!=final.get(name) for name in ('client_id','zone_id','sim_now_ticks'))):
        raise ValueError('Original native Sim and all persistence checks were not verified paused after return.')
    return path, pauses[0]


def normal_prebinding_exit_context(path, expected_hash, failed_path, observer_path, old, returned,
                                  profile, original, sim_id, household_id, save_guid, slot_id, save_hash):
    """Normal lifecycle exit is allowed only for the separately certified refusal."""
    if path is None or not hash_value(expected_hash): raise ValueError('Pre-binding archive needs a pinned normal unsaved exit.')
    path=reusable_profile.writable(path)
    if (path in (failed_path,observer_path) or any(path==root or root in path.parents for root in (profile,original)) or
            not path.is_file() or not 0<path.stat().st_size<=12*1024*1024 or sha256(path)!=expected_hash):
        raise ValueError('Pre-binding normal exit proof is missing, unsafe or changed.')
    proof=json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(proof,dict) or type(proof.get('schema')) is not int or proof['schema']!=1 or
            proof.get('operation')!='normal-exit-without-saving' or proof.get('outcome')!='normal-exit-without-saving' or
            any(proof.get(name) is not True for name in ('ok','normal_exit_verified','game_exit_verified',
                'save_files_unchanged_verified','exit_without_save_input_accepted')) or
            any(proof.get(name) is not False for name in ('final_process_alive','save_requested',
                'save_and_exit_input_accepted','save_completed_file_verified','save_reload_verified')) or
            proof.get('rewritten_normal_slots')!={} or not isinstance(proof.get('identity'),dict) or
            any(proof['identity'].get(name)!=old.get(name) for name in ('pid','test_token','script_sha256','profile')) or
            any(proof.get(name)!=value for name,value in (('requested_sim_id',sim_id),
                ('requested_household_id',household_id),('requested_save_guid',save_guid))) or
            not isinstance(proof.get('cas_shutdown_guard'),dict) or proof['cas_shutdown_guard'].get('safe') is not True or
            proof['cas_shutdown_guard'].get('blocking_native_requests')!=[] or
            not isinstance(proof.get('crash'),dict) or proof['crash'].get('outcome') not in ('absent','unchanged')):
        raise ValueError('Pre-binding recovery needs the exact normal unsaved exit with no Save or unresolved CAS.')
    before,after=proof.get('before_all_saves'),proof.get('after_all_saves')
    if (not isinstance(before,dict) or len(before)!=18 or before!=after or
            len({name.casefold() for name in before if isinstance(name,str)})!=18 or
            any(not isinstance(name,str) or Path(name).name!=name or not isinstance(row,dict) or
                set(row)!={'sha256','bytes','mtime_ns'} or not hash_value(row.get('sha256')) or
                type(row.get('bytes')) is not int or row['bytes']<0 or type(row.get('mtime_ns')) is not int or
                row['mtime_ns']<0 for name,row in before.items())):
        raise ValueError('All 18 normal-exit save/backup records must remain exactly unchanged.')
    matching=[row for name,row in before.items() if name.casefold()=='slot_{:08x}.save'.format(slot_id)]
    if len(matching)!=1 or matching[0]['sha256']!=save_hash:
        raise ValueError('Pre-binding exit normal save hash differs.')
    native=proof.get('unsaved_exit_native_before')
    if (not _strict_live(native,sim_id,household_id,save_guid,0) or
            any(native.get(name)!=returned.get(name) for name in ('client_id','zone_id','save_slot')) or
            int(native['sim_now_ticks'])<int(returned['sim_now_ticks'])):
        raise ValueError('Normal exit did not retain the exact returned native Sim paused.')
    return path


def failed_entry_crash_context(proof, identity, sim_id, household_id, save_guid, slot_id, profile, original):
    """An entry crash authorizes metadata archival only, never replay or repair."""
    if (not isinstance(proof, dict) or proof.get('schema') != 1
            or proof.get('operation') != 'observe-native-cas-entry' or proof.get('ok') is not False
            or proof.get('outcome') != 'crash' or proof.get('entry_submitted') is not True
            or proof.get('entry_accepted') is not True or proof.get('handshake_verified') is not True
            or proof.get('inventory_verified') is not False or proof.get('no_input_replay') is not True
            or proof.get('requested_sim_id') != sim_id or not isinstance(proof.get('identity'), dict)
            or any(proof['identity'].get(field) != identity.get(field)
                   for field in ('pid', 'test_token', 'script_sha256', 'profile'))):
        raise ValueError('Metadata archive requires the exact failed native CAS entry, not a successful or unknown session.')
    crash = proof.get('crash')
    if (not isinstance(crash, dict) or crash.get('outcome') != 'preserved' or crash.get('preserved') is not True
            or not isinstance(crash.get('after'), dict) or not hash_value(crash['after'].get('sha256'))
            or crash.get('before', {}).get('sha256') == crash['after']['sha256']):
        raise ValueError('CAS entry crash evidence is absent or unchanged.')
    path = reusable_profile.writable(crash.get('path', ''))
    if (any(path == root or root in path.parents for root in (profile, original))
            or not path.is_file() or not 1 <= path.stat().st_size <= cas_transition.MAX_CRASH_BYTES
            or sha256(path) != crash['after']['sha256']):
        raise ValueError('Preserved CAS entry crash is missing, changed or unsafe.')
    steps = proof.get('steps')
    if not isinstance(steps, list) or len(steps) > 1024:
        raise ValueError('CAS entry observations are missing or oversized.')
    entries = [row.get('result') for row in steps if isinstance(row, dict) and row.get('action') == 'test_cas']
    if len(entries) != 1 or not isinstance(entries[0], dict) or entries[0].get('ok') is not True:
        raise ValueError('CAS entry was not acknowledged exactly once.')
    before = entries[0].get('before')
    # This immutable entry leaf predates later clock-origin contracts. Its
    # typed native context is archival authority, never proof of new progress.
    if (not native_live_context(before, sim_id, household_id) or before.get('save_guid') != save_guid
            or before.get('save_slot') != slot_id or before.get('clock_speed') != 0):
        raise ValueError('Failed CAS entry does not retain the exact paused native Sim, household and normal save slot.')
    return before


def read_bank(profile, key):
    path = reusable_profile.writable(profile / 'TD1_OccultHybridApexData' / 'form_bank.json')
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Retained CAS bank is absent or oversized.')
    data = json.loads(path.read_text(encoding='utf-8'))
    record = data.get('records', {}).get(key)
    if not isinstance(record, dict) or not isinstance(record.get('pending'), dict):
        raise ValueError('No retained failed CAS metadata exists for this exact Sim/save.')
    if record.get('switch_pending'):
        raise ValueError('A different form transition remains unresolved; do not abandon it.')
    return path, data, record


def captured_schema2(record, prior_identity, sim_id, household_id, save_guid):
    """Host preflight only; Source revalidates every raw original/envelope."""
    pending, transaction = record.get('pending'), record.get('cas_transaction')
    old = {'runtime_pid': prior_identity['pid'], 'sim_id': sim_id,
           'household_id': household_id, 'save_guid': save_guid}
    if (not isinstance(pending, dict) or type(pending.get('schema')) is not int or pending['schema'] != 2 or
            pending.get('state') != 'captured' or type(pending.get('runtime_pid')) is not int or
            pending['runtime_pid'] != old['runtime_pid'] or pending.get('identity') != old or
            not isinstance(transaction, dict) or type(transaction.get('schema')) is not int or
            transaction['schema'] != 1 or transaction.get('identity') != old or
            transaction.get('owner_key') != save_guid + ':' + sim_id or
            not uuid_id(transaction.get('transaction_id')) or transaction.get('phase') != 'captured' or
            transaction.get('journal') is not None or transaction.get('full_native_original_appended') is not False or
            any(name in transaction for name in ('metadata_commit', 'metadata_guard_sha256',
                'native_original_append', 'post_original_serializer_owners', 'native_write_attempted',
                'native_write_possible', 'original_serializer_appearance_side_effects'))):
        raise ValueError('Schema2 metadata archive requires the exact never-observed old checkpoint/journal.')
    raw = pending.get('original_owners')
    if (not isinstance(raw, dict) or raw.get('identity') != old or not isinstance(raw.get('stored'), dict) or
            not 1 <= len(raw['stored']) <= 32 or not isinstance(raw.get('active'), dict) or
            raw['active'].get('lane') != pending.get('lane') or pending.get('lane') not in raw['stored']):
        raise ValueError('Old captured raw originals lack exact separate owner identity.')
    return hashlib.sha256(json.dumps(transaction, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode('ascii')).hexdigest()


def unsaved_exit_context(path, expected_hash, failed_path, failed_hash, failed, old,
                         profile, original, sim_id, household_id, save_guid, slot_id, save_hash):
    """Bind a closed failed session; this function submits no exit or save."""
    if path is None or not hash_value(expected_hash):
        raise ValueError('Schema2 archival requires a separate hash-pinned normal unsaved-exit proof.')
    path = reusable_profile.writable(path)
    if (path == failed_path or any(path == root or root in path.parents for root in (profile, original)) or
            not path.is_file() or path.stat().st_size > 12 * 1024 * 1024 or sha256(path) != expected_hash):
        raise ValueError('Normal unsaved-exit proof is missing, unsafe or changed.')
    proof = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(proof, dict):
        raise ValueError('Normal unsaved-exit evidence must be a typed record.')
    retained = proof.get('failed_return_proof') if isinstance(proof, dict) else None
    before, after = proof.get('before_saves'), proof.get('after_saves')
    if (type(proof.get('schema')) is not int or proof['schema'] != 1 or
            proof.get('operation') != 'normal-discard-failed-cas-session' or
            proof.get('outcome') != 'normal-exit-without-saving' or
            any(proof.get(name) is not True for name in ('ok', 'normal_exit_verified',
                'game_exit_verified', 'save_files_unchanged_verified', 'finalized', 'discard_input_accepted')) or
            any(proof.get(name) is not False for name in ('save_submitted', 'appearance_mutated',
                'cas_accept_repeated', 'final_process_alive')) or
            not isinstance(proof.get('identity'), dict) or
            any(proof['identity'].get(name) != old.get(name) for name in
                ('pid', 'test_token', 'script_sha256', 'profile')) or
            any(proof.get(name) != value for name, value in
                (('sim_id', sim_id), ('household_id', household_id), ('save_guid', save_guid))) or
            proof.get('retained_cas_request_id') != failed.get('cas_request_id') or
            not uuid_id(proof.get('retained_cas_request_id')) or not isinstance(retained, dict) or
            retained.get('sha256') != failed_hash or
            Path(retained.get('path', '')).resolve() != failed_path or
            not isinstance(before, dict) or not before or before != after or
            any(not isinstance(name, str) for name in before)):
        raise ValueError('Schema2 archival requires the exact closed failed session with no Save or accept replay.')
    matches = [row for name, row in before.items() if name.casefold() == 'slot_{:08x}.save'.format(slot_id)]
    if (len(matches) != 1 or not isinstance(matches[0], dict) or matches[0].get('sha256') != save_hash):
        raise ValueError('Unsaved-exit normal save-file hash differs; no metadata archived.')
    return path


def observe(state, output, identity, request, failed_return_proof, expected_proof_sha256,
            expected_save_sha256, sim_id, household_id, save_guid, slot_id, seconds=30,
            transport=None, alive=cas_transition.process_alive, monotonic=time.monotonic,
            allow_auto_save_slot_metadata_only=False, unsaved_exit_proof=None,
            expected_unsaved_exit_proof_sha256=None, pause=time.sleep,
            observer_failure_proof=None, expected_observer_failure_sha256=None):
    started = monotonic()
    if (not all(decimal_id(value) for value in (sim_id, household_id, save_guid))
            or not all(hash_value(value) for value in (expected_proof_sha256, expected_save_sha256))
            or type(slot_id) is not int or not 0 < slot_id < 0xffffffff
            or type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 60
            or type(allow_auto_save_slot_metadata_only) is not bool):
        raise ValueError('Use an exact retained proof, current existing save hash and bounded recovery identities.')
    prebinding = observer_failure_proof is not None or expected_observer_failure_sha256 is not None
    if prebinding and (observer_failure_proof is None or not hash_value(expected_observer_failure_sha256)):
        raise ValueError('Observer refusal proof and its exact SHA-256 must be supplied together.')
    if prebinding and (unsaved_exit_proof is None or not hash_value(expected_unsaved_exit_proof_sha256)):
        raise ValueError('Pre-binding observer refusal requires its separate exact unsaved-exit proof.')
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff
            or identity.get('test_token') != journal['token'] or script is None or identity.get('script_sha256') != script
            or Path(identity.get('profile', '')).resolve() != profile):
        raise ValueError('New runtime does not match the exact disposable profile/script.')
    output, failed_path = reusable_profile.writable(output), reusable_profile.writable(failed_return_proof)
    if (output.exists() or output.suffix.lower() != '.json' or not output.parent.is_dir()
            or output == journal_path or any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use a new external recovery proof outside both profiles and the journal.')
    if (any(failed_path == root or root in failed_path.parents for root in (profile, original))
            or not failed_path.is_file() or failed_path.stat().st_size > 12 * 1024 * 1024
            or sha256(failed_path) != expected_proof_sha256):
        raise ValueError('Failed CAS return proof is missing, unsafe or changed.')
    failed = json.loads(failed_path.read_text(encoding='utf-8'))
    old = failed.get('identity')
    if (not isinstance(old, dict) or type(old.get('pid')) is not int or not 0 < old['pid'] <= 0xffffffff
            or old['pid'] == identity['pid'] or old.get('test_token') != journal['token']
            or Path(old.get('profile', '')).resolve() != profile or not hash_value(old.get('script_sha256'))):
        raise ValueError('Recovery requires a distinct old runtime in this same disposable profile.')
    observer_path, returned = None, None
    if prebinding:
        observer_path, returned = prebinding_failure_context(observer_failure_proof,expected_observer_failure_sha256,
            failed_path,expected_proof_sha256,failed,old,profile,original,sim_id,household_id,save_guid)
    elif failed.get('operation') == 'observe-native-cas-entry':
        failed_entry_crash_context(failed, old, sim_id, household_id, save_guid, slot_id, profile, original)
    elif failed.get('operation') == 'observe-native-cas-post-entry-crash':
        from cas_crash import validate
        validate(failed, old, sim_id, household_id, save_guid, slot_id, profile, original)
    else:
        failed_context(failed, old, sim_id, household_id, save_guid)
    old_alive = alive(old['pid'])
    if old_alive is not False:
        raise ValueError('Old CAS runtime is still alive or its process state is unknown.')
    key = save_guid + ':' + sim_id
    bank_path, before, before_record = read_bank(profile, key)
    pending_hash, lanes_hash = digest(before_record['pending']), digest(before_record.get('bank', {}))
    schema2 = type(before_record['pending'].get('schema')) is int and before_record['pending']['schema'] == 2
    transaction_hash, exit_path = None, None
    if schema2:
        transaction_hash = captured_schema2(before_record, old, sim_id, household_id, save_guid)
        if failed.get('operation') != 'semantic-cas-return-to-live':
            raise ValueError('Schema2 captured archival is limited to the exact failed existing-Sim CAS return.')
        if prebinding:
            # The raw checkpoint and its transaction envelope are separate
            # identities. CAS observe is pinned to the envelope, whereas the
            # metadata archive must retain the exact original raw checkpoint.
            # Receiver checkpoints use ASCII-escaped canonical JSON. The
            # existing UTF-8 pending_hash remains the separate archive guard.
            checkpoint_hash = hashlib.sha256(json.dumps(before_record['pending'], sort_keys=True,
                ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')).hexdigest()
            transaction = before_record['cas_transaction']
            if (checkpoint_hash != failed['checkpoint_sha256'] or
                    transaction.get('checkpoint_sha256') != checkpoint_hash or
                    transaction.get('transaction_sha256') != failed['expected_pending_sha256']):
                raise ValueError('Pre-binding failure does not belong to this exact retained checkpoint.')
            exit_path=normal_prebinding_exit_context(unsaved_exit_proof,expected_unsaved_exit_proof_sha256,
                failed_path,observer_path,old,returned,profile,original,sim_id,household_id,save_guid,slot_id,expected_save_sha256)
        else:
            exit_path = unsaved_exit_context(unsaved_exit_proof, expected_unsaved_exit_proof_sha256,
                failed_path, expected_proof_sha256, failed, old, profile, original, sim_id,
                household_id, save_guid, slot_id, expected_save_sha256)
    elif prebinding:
        raise ValueError('Pre-binding refusal recovery applies only to captured schema2 metadata.')
    elif (before_record.get('cas_transaction') is not None or unsaved_exit_proof is not None or
            expected_unsaved_exit_proof_sha256 is not None):
        raise ValueError('Modern journal/exit bindings cannot use legacy metadata archival.')
    save_path = reusable_profile.writable(profile / 'saves' / ('Slot_{:08x}.save'.format(slot_id)))
    if not save_path.is_file() or sha256(save_path) != expected_save_sha256:
        raise ValueError('Existing save changed after the failed unsaved session; no metadata abandoned.')
    proof = {'schema': 1, 'operation': 'archive-unsaved-failed-cas-metadata', 'ok': False,
        'outcome': 'unresolved', 'identity': identity, 'prior_identity': old,
        'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid, 'slot_id': slot_id,
        'failed_return_proof_sha256': expected_proof_sha256, 'expected_save_sha256': expected_save_sha256,
        'pending_sha256': pending_hash, 'bank_lanes_sha256': lanes_hash,
        'cas_transaction_sha256': transaction_hash, 'checkpoint_schema': 2 if schema2 else 1,
        'unsaved_exit_proof_sha256': expected_unsaved_exit_proof_sha256,
        'observer_failure_proof_sha256': expected_observer_failure_sha256,
        'prebinding_refusal_recovery': prebinding,
        'steps': [], 'owner_requests': [], 'archive_submitted': False,
        'archive_request_id': None, 'request_status_poll_count': 0,
        'appearance_mutated': False, 'save_submitted': False, 'bank_lanes_changed': False,
        'allow_auto_save_slot_metadata_only': allow_auto_save_slot_metadata_only,
        'disk_slot_verified': False, 'save_reload_verified': False,
        'clock_progress_verified': False, 'simulation_progress_verified': False,
        'failed_history_retained_verified': False, 'finalized': False}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2)
    transport = apex_cli.get if transport is None else transport
    deadline = started + seconds
    active_call = {'action': None, 'request_id': None}

    def record(action, result):
        proof['steps'].append({'action': action, 'result': result})
        write_json(output, proof)
        return result

    def pinned(path, query=None, timeout=12):
        if monotonic() >= deadline:
            raise TimeoutError('Recovery wait expired; retain the owner identity without replay.')
        if alive(identity['pid']) is not True or alive(old['pid']) is not False:
            raise ValueError('Current or prior runtime process state changed; recovery refused.')
        if path in ('/api/command', '/api/native') and isinstance(query, dict):
            if (not uuid_id(query.get('request_id')) or query.get('action') != active_call['action']
                    or active_call['request_id'] is not None):
                raise ValueError('Recovery submits each predetermined owner UUID once; no replay allowed.')
            active_call['request_id'] = query['request_id']
            proof['owner_requests'].append({'action': query.get('action'), 'request_id': query['request_id']})
            if query['action'] == 'test_cas_abandon_unsaved':
                proof['archive_request_id'] = query['request_id']
            write_json(output, proof)
        if path == '/api/requests/status':
            if (not isinstance(query, dict) or query.get('request_id') != active_call['request_id']
                    or not uuid_id(active_call['request_id'])):
                raise ValueError('Recovery completion must observe its exact retained owner UUID.')
            # Status reads have no native action. Recheck the runtime before
            # each read, including reads performed by owned_request itself.
            pinned('/api/bridge', timeout=timeout)
        if monotonic() >= deadline:
            raise TimeoutError('Recovery observer deadline expired; the original UUID was retained.')
        result = transport(path, query, timeout=min(timeout, 2, max(.01, deadline - monotonic())))
        if path == '/api/bridge' and (not isinstance(result, dict) or any(result.get(field) != identity.get(field)
                for field in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('New runtime identity changed during recovery.')
        if path == '/api/requests/status':
            proof['request_status_poll_count'] += 1
            record('observe-owner:' + active_call['action'], result)
            if (not isinstance(result, dict) or result.get('request_id') != active_call['request_id']
                    or result.get('state') not in ('pending', 'running', 'unknown', 'completed', 'failed', 'cancelled')):
                raise ValueError('Recovery completion status is untyped or has another owner UUID.')
            if result['state'] in ('completed', 'failed', 'cancelled'):
                terminal = result.get('result')
                if (not isinstance(terminal, dict) or type(terminal.get('ok')) is not bool
                        or 'request_id' in terminal and terminal['request_id'] != active_call['request_id']):
                    raise ValueError('Recovery terminal result is untyped or has another owner UUID.')
                pinned('/api/bridge', timeout=timeout)
        return result

    def call(action, value=None):
        active_call.update(action=action, request_id=None)
        if monotonic() >= deadline:
            raise TimeoutError('Recovery wait expired before submission; no request repeated.')
        try:
            result = request(state, action, sim_id=sim_id, value=value,
                seconds=min(2, max(.01, deadline - monotonic())), transport=pinned)
        except OSError as error:
            if active_call['request_id'] is None:
                raise
            result = {'ok': False, 'outcome': 'unresolved', 'request_id': active_call['request_id'],
                      'transport_error': str(error)}
        record(action, result)
        owner = active_call['request_id']
        if (not uuid_id(owner) or not isinstance(result, dict)
                or 'request_id' in result and result['request_id'] != owner):
            raise ValueError('Recovery result lacks the exact persisted owner UUID; no request repeated.')
        if ('request_state' in result and result['request_state'] not in
                ('pending', 'running', 'unknown', 'completed', 'failed', 'cancelled')):
            raise ValueError('Recovery original request has an untyped completion state; no replay.')
        if result.get('request_state') in ('failed', 'cancelled'):
            raise ValueError('Recovery original request failed or was cancelled; no request repeated.')
        unresolved = (result.get('outcome') == 'unresolved'
                      or result.get('request_state') in ('pending', 'running', 'unknown'))
        if unresolved:
            while monotonic() < deadline:
                try:
                    row = pinned('/api/requests/status', {'request_id': owner})
                except OSError as error:
                    record('observe-owner:' + action, {'ok': False, 'request_id': owner,
                        'response_lost_or_failed': True, 'error': str(error)})
                    pause(min(.25, max(0, deadline - monotonic())))
                    continue
                if row['state'] in ('completed', 'failed', 'cancelled'):
                    result = dict(row['result'], request_id=owner, request_state=row['state'])
                    if row['state'] != 'completed':
                        result['ok'] = False
                    record('completed-owner:' + action, result)
                    break
                pause(min(.25, max(0, deadline - monotonic())))
            else:
                raise TimeoutError('Recovery original UUID remained unresolved within the advertised deadline; no replay.')
        if (result.get('ok') is not True or result.get('request_state') in
                ('pending', 'running', 'unknown', 'failed', 'cancelled') or result.get('outcome') == 'unresolved'):
            raise ValueError('Recovery observation/action is unresolved; no submission repeated.')
        return result

    envelope = lambda value: json.dumps({'test_token': journal['token'], 'value': value})
    try:
        baseline = call('test_snapshot', envelope(None))
        native_slot = baseline.get('save_slot')
        metadata_sentinel = (allow_auto_save_slot_metadata_only and type(native_slot) is int
                             and (native_slot == 0xffffffff or schema2 and native_slot == 0))
        if (not native_live_context(baseline, sim_id, household_id) or baseline.get('save_guid') != save_guid
                or baseline.get('clock_speed') != 0 or type(native_slot) is not int
                or native_slot != slot_id and not metadata_sentinel):
            raise ValueError('Exact original Sim/household/GUID is not paused in the required native slot.')
        proof.update(native_save_slot=native_slot, disk_slot_verified=native_slot == slot_id,
                     native_live_identity_verified=True)
        if game_lifecycle.shutdown_cas_state(call('cas_ui_diagnostics')).get('safe') is not True:
            raise ValueError('A current CAS session/request remains unresolved; recovery refused.')
        fresh_record = read_bank(profile, key)[2]
        if (sha256(save_path) != expected_save_sha256 or digest(fresh_record['pending']) != pending_hash or
                schema2 and (captured_schema2(fresh_record, old, sim_id, household_id, save_guid) != transaction_hash or
                    sha256(exit_path) != expected_unsaved_exit_proof_sha256)):
            raise ValueError('Save, exact journal or retained exit proof changed during recovery preflight.')
        if prebinding and (sha256(failed_path)!=expected_proof_sha256 or sha256(observer_path)!=expected_observer_failure_sha256):
            raise ValueError('Pinned pre-binding failure evidence changed before metadata archival.')
        value = {'expected_pending_sha256': pending_hash, 'prior_pid': old['pid'],
            'expected_save_sha256': expected_save_sha256, 'slot_id': slot_id,
            'save_guid': save_guid, 'household_id': household_id,
            'failed_return_proof_sha256': expected_proof_sha256}
        if schema2:
            value.update(expected_cas_transaction_sha256=transaction_hash,
                unsaved_exit_proof_sha256=expected_unsaved_exit_proof_sha256)
        if allow_auto_save_slot_metadata_only:
            value['allow_auto_save_slot_metadata_only'] = True
        proof['archive_submitted'] = True
        write_json(output, proof)
        receipt = call('test_cas_abandon_unsaved', envelope(value))
        after = json.loads(bank_path.read_text(encoding='utf-8'))
        current_record = after.get('records', {}).get(key, {})
        proof['bank_lanes_changed'] = digest(current_record.get('bank', {})) != lanes_hash
        proof['save_file_unchanged_verified'] = sha256(save_path) == expected_save_sha256
        entries = current_record.get('failed_history', [])
        proof['failed_history_retained_verified'] = any(isinstance(item, dict)
            and item.get('pending_sha256') == pending_hash
            and item.get('failed_return_proof_sha256') == expected_proof_sha256
            and item.get('pending') == before_record['pending'] and
            (not schema2 or item.get('cas_transaction') == before_record['cas_transaction'] and
                item.get('cas_transaction_sha256') == transaction_hash and
                item.get('unsaved_exit_proof_sha256') == expected_unsaved_exit_proof_sha256) for item in entries)
        other_before = {k: v for k, v in before.get('records', {}).items() if k != key}
        other_after = {k: v for k, v in after.get('records', {}).items() if k != key}
        proof['other_records_unchanged_verified'] = other_before == other_after
        proof['ok'] = (receipt.get('abandoned') is True and receipt.get('appearance_mutated') is False
            and receipt.get('save_written') is False and current_record.get('pending') is None
            and (not schema2 or receipt.get('cas_transaction_archived') is True and
                current_record.get('cas_transaction') is None)
            and not proof['bank_lanes_changed'] and proof['save_file_unchanged_verified']
            and proof['failed_history_retained_verified'] and proof['other_records_unchanged_verified'])
        proof['outcome'] = 'failed-transaction-archived-without-appearance-writes' if proof['ok'] else 'archive-postconditions-failed'
    except (OSError, ValueError, RuntimeError, TimeoutError, TypeError, KeyError) as error:
        proof['error'] = str(error)
    proof.update(finalized=True, elapsed_seconds=monotonic() - started)
    write_json(output, proof)
    return {'ok': proof['ok'], 'outcome': proof['outcome'], 'proof': str(output),
        'proof_sha256': sha256(output), 'appearance_mutated': False,
        'disk_slot_verified': proof['disk_slot_verified'], 'save_reload_verified': False,
        'clock_progress_verified': False, 'simulation_progress_verified': False,
        'failed_history_retained_verified': proof['failed_history_retained_verified'],
        'message': 'Failed CAS originals archived; save and appearance banks unchanged.' if proof['ok'] else proof.get('error', 'Recovery postconditions failed; inspect retained proof before retrying.')}
