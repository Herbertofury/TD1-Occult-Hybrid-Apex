"""Retire only a closed disposable native-readback failure, preserving all data.

This is metadata archival after an unsaved exit, never native reconciliation,
replay, appearance acceptance, or proof that unsaved edits survived. The old
raw/planned/partially applied transaction remains immutable and inspectable.
"""
import copy
import json
import os
from pathlib import Path
import sys

import cas_crash
import reusable_profile
from game_lifecycle import all_save_files
from source_manifest import sha256, write_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import bank_history, cas_bank_transaction as receiver, cas_commit_plan as primitive
from cas_journal_archive import closed_raw


def validate_record(record, failure, identity):
    pending, transaction = record.get('pending'), record.get('cas_transaction')
    if (failure.get('ok') is not False or failure.get('request_state') != 'failed' or
            not receiver._token(failure.get('request_id')) or
            failure.get('submitted_request_id') != failure['request_id'] or
            not isinstance(failure.get('message'), str) or not failure['message'].startswith(
                'CAS native reconcile or bank commit failed; originals and returned state require inspection: ') or
            not isinstance(pending, dict) or pending.get('schema') != 2 or pending.get('state') != 'captured' or
            pending.get('identity') != identity or type(pending.get('runtime_pid')) is not int or
            pending['runtime_pid'] != identity['runtime_pid'] or record.get('switch_pending') is not None or
            not isinstance(transaction, dict) or transaction.get('identity') != identity or
            transaction.get('phase') != 'recovery-required' or transaction.get('metadata_commit') is not None or
            transaction.get('prior_bank') != record.get('bank') or
            transaction.get('checkpoint_sha256') != primitive.digest(pending) or
            transaction.get('record_guard_sha256') != receiver._record_guard(record) or
            transaction.get('hair_checkpoint_sha256') != primitive.digest(transaction.get('hair_checkpoint'))):
        raise ValueError('Only an exact uncommitted closed native-readback failure can be archived.')
    envelope = {name: transaction.get(name) for name in ('transaction_id', 'identity',
        'checkpoint_sha256', 'record_guard_sha256', 'hair_checkpoint_sha256')}
    if (not receiver._token(transaction.get('transaction_id')) or
            primitive.digest(receiver._native_context_envelope(transaction, envelope)) != transaction.get('transaction_sha256')):
        raise ValueError('Failed transaction envelope differs; retain the active gate.')
    journal = transaction.get('journal')
    if (not isinstance(journal, dict) or journal.get('schema') != 1 or journal.get('state') != 'recovery-required' or
            journal.get('identity') != identity or journal.get('native_write_attempted') is not True or
            journal.get('native_write_possible') is not True or journal.get('bank_committed') is not False or
            journal.get('bank_commit_attempted') is not False or journal.get('bank_commit_acknowledged') is not False or
            journal.get('bank_commit_outcome') != 'not-attempted' or journal.get('automatic_replay_allowed') is not False or
            journal.get('pending_sha256') != primitive.digest(pending) or
            journal.get('original_owners') != pending.get('original_owners') or
            journal.get('raw_return_sha256') != primitive.digest(journal.get('raw_return')) or
            journal.get('plan_sha256') != primitive.digest(journal.get('plan')) or
            journal.get('failed_phase') != 'native reconcile or bank commit' or
            failure['message'].split(': ', 1)[1] != journal.get('error')):
        raise ValueError('Committed, uncertain or changed native-write history cannot be archived here.')
    for raw in (pending['original_owners'], journal['raw_return'], journal.get('pre_write_owners')):
        closed_raw(raw, identity)
    primitive._consistent(pending['original_owners'])
    return transaction


@reusable_profile.serialized
def archive(state, failure_proof, failure_sha256, exit_proof, exit_sha256,
            expected_bank_sha256, slot_id, expected_save_sha256, output):
    reusable_profile.legacy.require_closed()
    state, marked, profile, original = reusable_profile.load(state)
    failed_path, failed = cas_crash.external_json(failure_proof, profile, original, failure_sha256)
    closed_path, closed = cas_crash.external_json(exit_proof, profile, original, exit_sha256)
    process = closed.get('identity', {})
    identity = {'runtime_pid': process.get('pid'), 'sim_id': closed.get('requested_sim_id'),
                'household_id': closed.get('requested_household_id'), 'save_guid': closed.get('requested_save_guid')}
    if (closed.get('ok') is not True or closed.get('operation') != 'normal-exit-without-saving' or
            any(closed.get(name) is not True for name in ('normal_exit_verified', 'game_exit_verified',
                'save_files_unchanged_verified', 'exit_without_save_input_accepted')) or
            closed.get('save_requested') is not False or closed.get('save_and_exit_input_accepted') is not False or
            closed.get('final_process_alive') is not False or process.get('test_token') != marked['token'] or
            Path(process.get('profile', '')).resolve() != profile or
            type(identity['runtime_pid']) is not int or not 0 < identity['runtime_pid'] <= 0xffffffff or
            cas_crash.cas_transition.process_alive(identity['runtime_pid']) is not False or
            any(not primitive._id(identity[name]) for name in ('sim_id', 'household_id', 'save_guid')) or
            type(slot_id) is not int or not 0 < slot_id < 0xffffffff):
        raise ValueError('This exact marked disposable requires a verified normal unsaved process exit.')
    saves = all_save_files(profile)
    save = reusable_profile.writable(profile / 'saves' / ('Slot_{:08x}.save'.format(slot_id)))
    if (not saves or saves != closed.get('before_all_saves') or saves != closed.get('after_all_saves') or
            not primitive._hash(expected_save_sha256) or sha256(save) != expected_save_sha256):
        raise ValueError('Save/backup inventory changed after unsaved exit; no metadata altered.')
    bank = reusable_profile.writable(profile / 'TD1_OccultHybridApexData/form_bank.json')
    if not primitive._hash(expected_bank_sha256) or sha256(bank) != expected_bank_sha256:
        raise ValueError('Failed bank bytes changed; retain the active gate.')
    data = receiver.load_for_write(bank)
    key = identity['save_guid'] + ':' + identity['sim_id']
    record = data['records'].get(key)
    if not isinstance(record, dict):
        raise ValueError('Failed original native owner record is unavailable.')
    validate_record(record, failed, identity)
    output = reusable_profile.writable(output)
    backup = reusable_profile.writable(output.with_name(output.stem + '-bank-before.json'))
    if (output.exists() or backup.exists() or output.suffix.casefold() != '.json' or
            not output.parent.is_dir() or output in (state, failed_path, closed_path) or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use new external evidence filenames outside both game profiles.')
    before = copy.deepcopy(data)
    with backup.open('xb') as stream:
        stream.write(bank.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    leaf = {'pending': copy.deepcopy(record['pending']), 'cas_transaction': copy.deepcopy(record['cas_transaction']),
        'failed_commit_proof_sha256': failure_sha256, 'unsaved_exit_proof_sha256': exit_sha256,
        'metadata_archive_only': True, 'appearance_mutated': False, 'save_written': False,
        'replay_authorized': False, 'prior_native_write_attempted': True,
        'unsaved_edit_retention_verified': False, 'reason': 'closed-uncommitted-native-readback-failure'}
    archived = bank_history.store(bank, leaf)
    if bank_history.resolve(bank, archived) != leaf:
        raise ValueError('Complete immutable failed-transaction archive readback differs.')
    record.setdefault('failed_history', []).append(archived)
    record['pending'] = None; record['cas_transaction'] = None
    bank_history.externalize(bank, record)
    receipt = dict(schema=1, ok=False, operation='archive-closed-uncommitted-native-readback-failure',
        identity=identity, failure_proof_sha256=failure_sha256, unsaved_exit_proof_sha256=exit_sha256,
        original_bank_backup=str(backup), original_bank_sha256=expected_bank_sha256,
        retained_complete_transaction=archived, metadata_write_submitted=False,
        appearance_mutated=False, save_written=False, save_reload_verified=False, replay_authorized=False,
        unsaved_edit_retention_verified=False)
    write_json(output, receipt)
    reusable_profile.legacy.require_closed()
    if (sha256(bank) != expected_bank_sha256 or all_save_files(profile) != saves or
            sha256(failed_path) != failure_sha256 or sha256(closed_path) != exit_sha256):
        raise ValueError('Bank, saves or evidence changed before archival; no metadata write submitted.')
    receipt['metadata_write_submitted'] = True; write_json(output, receipt)
    receiver.save_from_read(bank, data)
    after = receiver.load_for_write(bank)
    other_same = {k:v for k,v in before['records'].items() if k != key} == {k:v for k,v in after['records'].items() if k != key}
    receipt.update(ok=after == data and other_same and all_save_files(profile) == saves,
        save_files_unchanged=all_save_files(profile) == saves, other_records_unchanged=other_same,
        bank_lanes_unchanged=after['records'][key]['bank'] == before['records'][key]['bank'],
        complete_failed_transaction_retained=bank_history.resolve(bank, archived) == leaf,
        bank_sha256=sha256(bank))
    write_json(output, receipt)
    return receipt
