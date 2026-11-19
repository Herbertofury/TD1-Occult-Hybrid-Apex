"""Archive one closed disposable raw-observed capacity failure, without replay.

This cannot recover a planned/interrupted native write, or certify lost unsaved
edits. Original checkpoint, raw return, complete transaction and old bank bytes
remain durable; only the active metadata gate is retired after normal closure.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

import cas_crash
import reusable_profile
from game_lifecycle import all_save_files
from source_manifest import sha256, write_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_bank_transaction as receiver, cas_commit_plan as primitive, bank_history, form_appearance


def closed_raw(raw, expected):
    # The production _identity/_validate_raw deliberately require the current
    # native runtime. Closed archival validates old records independently; it
    # never spoofs os.getpid or relaxes that live receiver invariant.
    if (not isinstance(raw, dict) or set(raw) != {'identity', 'stored', 'active'} or
            raw.get('identity') != expected or not isinstance(raw.get('stored'), dict) or not raw['stored'] or
            not isinstance(raw.get('active'), dict) or set(raw['active']) != {'lane', 'fields'} or
            type(raw['identity'].get('runtime_pid')) is not int):
        raise ValueError('Closed raw native owner structure or identity differs.')
    for lane, fields in raw['stored'].items():
        if lane not in ('1', '2', '4', '8', '16', '32', '64'):
            raise ValueError('Closed raw native owner has an unknown lane.')
        form_appearance.fingerprint(fields)
    if raw['active']['lane'] not in raw['stored']:
        raise ValueError('Closed active appearance has no retained native owner.')
    form_appearance.fingerprint(raw['active']['fields'])
    primitive.digest(raw)


def validate_record(record, proof):
    pending, transaction = record.get('pending'), record.get('cas_transaction')
    identity = proof.get('identity', {})
    expected = {'runtime_pid': identity.get('pid'), 'sim_id': proof.get('sim_id'),
                'household_id': proof.get('household_id'), 'save_guid': proof.get('live_snapshot', {}).get('save_guid')}
    terminal = proof.get('cas_bank_observation_receipt', {})
    if (proof.get('ok') is not False or proof.get('operation') != 'semantic-cas-return-to-live' or
            proof.get('live_context_verified') is not True or proof.get('final_paused') is not True or
            terminal.get('ok') is not False or terminal.get('request_state') != 'failed' or
            terminal.get('request_id') != proof.get('cas_bank_observe_request_id') or
            terminal.get('message') != 'CAS raw observation or serializer append failed; originals and returned state require inspection: Form bank capacity reached; prior originals retained.' or
            record.get('switch_pending') is not None or not isinstance(pending, dict) or
            pending.get('schema') != 2 or pending.get('state') != 'captured' or pending.get('identity') != expected or
            not isinstance(transaction, dict) or transaction.get('identity') != expected or
            transaction.get('phase') != 'raw-observed' or transaction.get('metadata_commit') is not None or
            type(transaction.get('schema')) is not int or transaction['schema'] != 1 or
            not receiver._token(transaction.get('transaction_id')) or
            transaction.get('owner_key') != str(expected['save_guid']) + ':' + str(expected['sim_id']) or
            transaction.get('full_native_original_appended') is not False or
            transaction.get('transaction_sha256') != proof.get('expected_pending_sha256') or
            transaction.get('checkpoint_sha256') != primitive.digest(pending) or
            transaction.get('record_guard_sha256') != receiver._record_guard(record) or
            transaction.get('prior_bank') != record.get('bank') or
            transaction.get('hair_checkpoint_sha256') != primitive.digest(transaction.get('hair_checkpoint'))):
        raise ValueError('Only the exact closed, unplanned raw-observed capacity failure may be archived.')
    if (type(expected['runtime_pid']) is not int or not 0 < expected['runtime_pid'] <= 0xffffffff or
            not all(primitive._id(expected[name]) for name in ('save_guid','household_id','sim_id'))):
        raise ValueError('Closed prior runtime and canonical native owner identities are required.')
    envelope = {name: transaction[name] for name in ('transaction_id', 'identity',
        'checkpoint_sha256', 'record_guard_sha256', 'hair_checkpoint_sha256')}
    if primitive.digest(envelope) != transaction['transaction_sha256']:
        raise ValueError('Raw-observed transaction envelope changed; complete originals retained.')
    journal = transaction.get('journal')
    keys = {'schema', 'state', 'identity', 'pending_sha256', 'original_owners', 'raw_return',
            'raw_return_sha256', 'native_write_attempted', 'bank_committed', 'automatic_replay_allowed'}
    if (not isinstance(journal, dict) or set(journal) != keys or journal.get('schema') != 1 or
            journal.get('state') != 'raw-observed' or journal.get('identity') != expected or
            any(journal.get(name) is not False for name in ('native_write_attempted', 'bank_committed', 'automatic_replay_allowed')) or
            journal.get('pending_sha256') != primitive.digest(pending) or
            journal.get('original_owners') != pending.get('original_owners') or
            journal.get('raw_return_sha256') != primitive.digest(journal.get('raw_return'))):
        raise ValueError('Native writes, a plan or an altered raw journal prohibit metadata archival.')
    for raw in (pending['original_owners'], journal['raw_return']):
        closed_raw(raw, expected)
    primitive._consistent(pending['original_owners'])
    return expected


@reusable_profile.serialized
def archive(state, failure_proof, failure_sha256, closure_proof, closure_sha256,
            slot_id, expected_save_sha256, output):
    reusable_profile.legacy.require_closed()
    journal_path, journal, profile, original = reusable_profile.load(state)
    failed_path, proof = cas_crash.external_json(failure_proof, profile, original, failure_sha256)
    closed_path, closed = cas_crash.external_json(closure_proof, profile, original, closure_sha256)
    identity = proof.get('identity', {})
    if (identity.get('test_token') != journal['token'] or Path(identity.get('profile', '')).resolve() != profile or
            cas_crash.cas_transition.process_alive(identity.get('pid')) is not False or
            closed.get('ok') is not True or closed.get('operation') != 'normal-unsaved-closure' or
            closed.get('prior_pid') != identity.get('pid') or closed.get('process_closed_verified') is not True or
            closed.get('save_files_unchanged_verified') is not True or closed.get('save_written') is not False or
            type(slot_id) is not int or not 0 < slot_id < 0xffffffff):
        raise ValueError('Exact marked disposable, closed old process and unsaved closure evidence are required.')
    save = reusable_profile.writable(profile / 'saves' / ('Slot_{:08x}.save'.format(slot_id)))
    if not save.is_file() or sha256(save) != expected_save_sha256 or closed.get('normal_disk_save_sha256') != expected_save_sha256:
        raise ValueError('Normal disk save changed; no metadata altered.')
    output = reusable_profile.writable(output)
    backup = reusable_profile.writable(output.with_name(output.stem + '-bank-before.json'))
    if (output.exists() or backup.exists() or output.suffix.casefold() != '.json' or
            not output.parent.is_dir() or output in (journal_path, failed_path, closed_path) or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use new external evidence filenames outside both game profiles.')
    bank = reusable_profile.writable(profile / 'TD1_OccultHybridApexData/form_bank.json')
    data = receiver.load_for_write(bank)
    key = str(proof.get('live_snapshot', {}).get('save_guid')) + ':' + str(proof.get('sim_id'))
    record = data.get('records', {}).get(key)
    if not isinstance(record, dict):
        raise ValueError('Exact failed native owner record is unavailable.')
    validate_record(record, proof)
    before = copy.deepcopy(data)
    raw_bank = bank.read_bytes()
    saves = all_save_files(profile)
    with backup.open('xb') as stream:
        stream.write(raw_bank); stream.flush(); os.fsync(stream.fileno())
    leaf = {'pending': copy.deepcopy(record['pending']), 'cas_transaction': copy.deepcopy(record['cas_transaction']),
        'failed_return_proof_sha256': failure_sha256, 'closure_proof_sha256': closure_sha256,
        'metadata_archive_only': True, 'appearance_mutated': False, 'native_write_attempted': False,
        'save_written': False, 'replay_authorized': False, 'reason': 'closed-raw-observed-capacity-failure'}
    archived = bank_history.store(bank, leaf)
    if bank_history.resolve(bank, archived) != leaf:
        raise ValueError('Complete immutable archive readback failed; active gate retained.')
    record.setdefault('failed_history', []).append(archived)
    record['pending'] = None
    record['cas_transaction'] = None
    bank_history.externalize(bank, record)
    receipt = {'schema':1, 'ok':False, 'operation':'archive-closed-raw-observed-capacity-failure',
        'identity':identity, 'failure_proof_sha256':failure_sha256, 'closure_proof_sha256':closure_sha256,
        'original_bank_backup':str(backup), 'original_bank_sha256':hashlib.sha256(raw_bank).hexdigest(),
        'retained_complete_transaction':archived, 'metadata_write_submitted':False,
        'appearance_mutated':False, 'save_written':False, 'save_reload_verified':False, 'replay_authorized':False}
    write_json(output, receipt)
    reusable_profile.legacy.require_closed()
    if (bank.read_bytes() != raw_bank or all_save_files(profile) != saves or
            sha256(failed_path) != failure_sha256 or sha256(closed_path) != closure_sha256):
        raise ValueError('Bank, saves or evidence changed before archival; no metadata write submitted.')
    receipt['metadata_write_submitted'] = True
    write_json(output, receipt)
    receiver.save_from_read(bank, data)
    after = receiver.load_for_write(bank)
    same = after == data and all_save_files(profile) == saves
    other_same = {k:v for k,v in before['records'].items() if k != key} == {k:v for k,v in after['records'].items() if k != key}
    receipt.update(ok=same and other_same and after['records'][key]['bank'] == before['records'][key]['bank'],
        save_files_unchanged=saves == all_save_files(profile), other_records_unchanged=other_same,
        bank_lanes_unchanged=after['records'][key]['bank'] == before['records'][key]['bank'],
        bank_sha256=sha256(bank), active_bank_bytes=bank.stat().st_size,
        complete_failed_transaction_retained=bank_history.resolve(bank, archived) == leaf)
    write_json(output, receipt)
    return receipt
