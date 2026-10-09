"""Closed disposable only: archive a never-observed CAS checkpoint after crash.

Uses the same Source checkpoint validator and cooperative atomic bank writer.
No native producer is restored and no disk-load or gameplay claim is made.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

import cas_crash
import reusable_profile
from game_lifecycle import all_save_files
from source_manifest import sha256, write_json


@reusable_profile.serialized
def archive(state, crash_proof, expected_proof_sha256, slot_id, expected_save_sha256, output, entry_only=False):
    reusable_profile.legacy.require_closed()
    journal_path, journal, profile, original = reusable_profile.load(state)
    path, proof = cas_crash.external_json(crash_proof, profile, original, expected_proof_sha256)
    identity = proof.get('identity', {})
    if (identity.get('test_token') != journal['token'] or
            Path(identity.get('profile', '')).resolve() != profile or
            cas_crash.cas_transition.process_alive(identity.get('pid')) is not False or
            type(slot_id) is not int or not 0 < slot_id < 0xffffffff):
        raise ValueError('Exact closed crashed disposable runtime and normal disk slot required.')
    if type(entry_only) is not bool:
        raise ValueError('Closed captured archival must use an explicit typed scope.')
    if entry_only:
        entry = proof
        before = cas_crash.entry_receipt(entry).get('before', {})
        cas_crash.entry_context(entry, identity, entry.get('requested_sim_id'), before.get('household_id'),
            before.get('save_guid'), before.get('save_slot'))
        proof = dict(identity=identity, sim_id=entry['requested_sim_id'], household_id=before['household_id'],
            save_guid=before['save_guid'], slot_id=before['save_slot'])
    else:
        cas_crash.validate(proof, identity, proof.get('sim_id'), proof.get('household_id'),
            proof.get('save_guid'), proof.get('slot_id'), profile, original)
        _, entry = cas_crash.external_json(proof['entry_proof'], profile, original, proof['entry_proof_sha256'])
    checkpoint = cas_crash.entry_receipt(entry).get('form_checkpoint', {})
    output = reusable_profile.writable(output)
    backup = reusable_profile.writable(output.with_name(output.stem + '-bank-before.json'))
    if (output.exists() or backup.exists() or output.suffix.lower() != '.json' or
            not output.parent.is_dir() or output in (journal_path, path) or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use new external crash archival evidence outside both profiles.')
    save = reusable_profile.writable(profile / 'saves' / ('Slot_{:08x}.save'.format(slot_id)))
    if not save.is_file() or sha256(save) != expected_save_sha256:
        raise ValueError('Normal disk save changed; captured metadata retained.')
    source = Path(__file__).resolve().parents[1] / 'Source'
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from apex_core import form_bank, cas_bank_transaction as receiver
    from apex_core.form_bank_seal import _hash
    bank = reusable_profile.writable(profile / 'TD1_OccultHybridApexData' / 'form_bank.json')
    data = receiver.load_for_write(bank)
    key = proof['save_guid'] + ':' + proof['sim_id']
    record = data.get('records', {}).get(key)
    if not isinstance(record, dict) or record.get('switch_pending'):
        raise ValueError('No exact captured CAS metadata, or another transition is unresolved.')
    pending, transaction = record.get('pending'), record.get('cas_transaction')
    argument = dict(prior_pid=identity['pid'], household_id=proof['household_id'],
        save_guid=proof['save_guid'], expected_cas_transaction_sha256=_hash(transaction))
    form_bank._captured_schema2_archive(record, argument, proof['sim_id'])
    if (checkpoint.get('ok') is not True or checkpoint.get('native_appearance_written') is not False or
            checkpoint.get('checkpoint_sha256') != _hash(pending) or
            checkpoint.get('expected_pending_sha256') != transaction['transaction_sha256']):
        raise ValueError('Crash entry does not bind this exact never-observed checkpoint.')
    bank_bytes = bank.read_bytes()
    before_saves = all_save_files(profile)
    before_data = copy.deepcopy(data)
    receipt = dict(schema=1, operation='archive-closed-captured-cas-metadata' if entry_only else 'archive-closed-crashed-cas-metadata', ok=False,
        identity=identity, closure_evidence_sha256=expected_proof_sha256,
        crash_verified=not entry_only, normal_exit_verified=False,
        closure_scope='Exact prior process absent, all game processes closed, current disk save hash and never-observed checkpoint; no native return or save/reload proof.',
        original_bank_sha256=hashlib.sha256(bank_bytes).hexdigest(), original_bank_backup=str(backup),
        disk_slot_id=slot_id, expected_save_sha256=expected_save_sha256,
        native_slot_at_entry=proof['slot_id'], metadata_write_submitted=False,
        appearance_mutated=False, save_written=False, loaded_file_verified=False, save_reload_verified=False)
    with backup.open('xb') as stream:
        stream.write(bank_bytes)
    write_json(output, receipt)
    failed = dict(pending=copy.deepcopy(pending), cas_transaction=copy.deepcopy(transaction),
        pending_sha256=_hash(pending), cas_transaction_sha256=_hash(transaction),
        failed_return_proof_sha256=expected_proof_sha256, closure_evidence_sha256=expected_proof_sha256,
        closure_kind='captured-entry' if entry_only else 'native-crash',
        checkpoint_schema=2, metadata_archive_only=True, native_write_attempted=False,
        native_serializer_called=False, appearance_mutated=False, save_written=False)
    record.setdefault('failed_history', []).append(failed)
    record['pending'] = None
    record['cas_transaction'] = None
    reusable_profile.legacy.require_closed()
    if (sha256(path) != expected_proof_sha256 or all_save_files(profile) != before_saves or
            bank.read_bytes() != bank_bytes):
        raise ValueError('Crash, saves or bank changed before archival; no bank write.')
    receipt['metadata_write_submitted'] = True
    write_json(output, receipt)
    receiver.save_from_read(bank, data)
    after = json.loads(bank.read_text(encoding='utf-8'))
    expected = copy.deepcopy(before_data)
    expected['records'][key] = copy.deepcopy(record)
    receipt.update(ok=after == expected and all_save_files(profile) == before_saves,
        bank_lanes_unchanged=after['records'][key]['bank'] == before_data['records'][key]['bank'],
        save_files_unchanged=all_save_files(profile) == before_saves,
        bank_sha256=sha256(bank), originals_preserved_in_failed_history=True)
    write_json(output, receipt)
    return receipt
