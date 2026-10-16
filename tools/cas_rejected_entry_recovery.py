"""Archive metadata for a proved pre-entry rejection in a paused test Live session.

No native appearance, save, script, DLL, or protected profile is written. Actual
CAS entry, partial native import, changed owners, or ambiguous receipts refuse.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import cas_bank_transaction as writer, form_bank, form_appearance as appearance
from apex_core.form_bank_seal import _hash
from household_stress import owners
from source_manifest import sha256, write_json
from game_lifecycle import all_save_files
from cas_transition import process_alive
import reusable_profile


def need(value, message):
    if not value: raise ValueError(message)


def plan(entry, native, status, diagnostic, bank, preparation):
    identity = entry.get('identity', {});pid = identity.get('pid')
    need(entry.get('outcome') == 'entry-rejected' and entry.get('entry_accepted') is False and
         entry.get('handshake_verified') is False and entry.get('entry_submitted') is True,
         'Only a terminal rejected entry with no native handshake can be recovered.')
    failed = [row.get('result', {}) for row in entry.get('steps', []) if row.get('action') == 'test_cas']
    need(len(failed) == 1 and failed[0].get('ok') is False and failed[0].get('request_state') == 'failed' and
         failed[0].get('message') == 'A prior CAS pair preparation is unresolved; no replay authorized.',
         'The exact pre-preparation rejection is required; no generic error authorizes reset.')
    need(native.get('ok') is True and native.get('differences') == [] and
         all(native.get('identity', {}).get(key) == identity.get(key)
             for key in ('pid', 'script_sha256', 'test_token', 'profile')), 'Fresh exact native originals are required.')
    need(status.get('ok') is True and status.get('pid') == pid and status.get('selection_enabled') is False and
         status.get('selected_native', {}).get('available') is False and
         all(row.get('imported_mask') == 0 and not row.get('native_view_bound') for row in status.get('members', [])),
         'A native import/view may have started; metadata must be retained.')
    need(diagnostic.get('ok') is True and diagnostic.get('native_peers') == [] and
         diagnostic.get('requests') == [] and diagnostic.get('queued_operations') == 0 and
         diagnostic.get('socket_transport', {}).get('native_connection_verified') is False,
         'Native CAS activity or unresolved UI work blocks recovery.')
    need(preparation.get('stage') == 'unresolved' and type(preparation.get('runtime_pid')) is int and
         preparation['runtime_pid'] != pid and all(preparation.get(key) is False for key in
         ('appearance_written', 'current_kind_written', 'trait_written', 'forms_created', 'save_written')),
         'The retained preparation must be an older non-appearance operation.')
    snapshots = native['snapshots'];members = preparation.get('members', [])
    need(set(snapshots) == {row.get('sim_id') for row in members} ==
         {row.get('sim_id') for row in status.get('members', [])}, 'Exact full household coverage is required.')
    result = copy.deepcopy(bank)
    for row in members:
        sid = row['sim_id'];snapshot = snapshots[sid];key = preparation['save_guid'] + ':' + sid
        record = result['records'][key];transaction = record.get('cas_transaction', {})
        need(snapshot.get('clock_speed') == 0 and snapshot.get('zone_running') is True and
             snapshot.get('household_id') == preparation['household_id'] and snapshot.get('save_guid') == preparation['save_guid'],
             'The exact native Live household must remain paused.')
        need('native_entry_intent' not in transaction and not record.get('switch_pending'),
             'A native entry intent or another transition was already started.')
        form_bank._captured_schema2_archive(record, dict(prior_pid=pid, household_id=preparation['household_id'],
            save_guid=preparation['save_guid'], expected_cas_transaction_sha256=_hash(transaction)), sid)
        raw = record['pending']['original_owners'];current = owners(snapshot)
        expected = dict(raw['stored'], active=raw['active']['fields'])
        need(set(current) == set(expected) == set(row['original_appearances']), 'Every active/stored owner must be present.')
        for lane, fields in expected.items():
            actual = appearance.fingerprint(current[lane]['typed_payload'])
            need(actual == appearance.fingerprint(fields) == appearance.fingerprint(row['original_appearances'][lane]),
                 'A native appearance changed; no metadata may be cleared.')
        record.setdefault('failed_history', []).append(dict(state='rejected-before-native-entry',
            pending=copy.deepcopy(record['pending']), cas_transaction=copy.deepcopy(transaction),
            entry_request_id=failed[0]['request_id'], preparation_sha256=_hash(preparation),
            metadata_archive_only=True, appearance_restored=False))
        record['pending'] = None;record['cas_transaction'] = None
    return result


def run(args):
    from apex_cli import owned_request, verified_identity
    from cli_identity_cache import session
    _, journal, profile, original = reusable_profile.load(args.state)
    output = reusable_profile.writable(args.output)
    need(not output.exists() and output.suffix == '.json' and output.parent.is_dir() and
         all(root != output and root not in output.parents for root in (profile, original)), 'Use a new external recovery receipt.')
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    entry, native = read(args.entry_proof), read(args.native_proof)
    prep = reusable_profile.writable(profile / 'TD1_OccultHybridApexData/household_cas_entry.json')
    bank_path = reusable_profile.writable(prep.with_name('form_bank.json'))
    preparation = read(prep);bank = writer.load_for_write(bank_path)
    bank_bytes, prep_bytes = bank_path.read_bytes(), prep.read_bytes()
    bank_hash, prep_hash = sha256(bank_path), sha256(prep)
    backup = output.with_name(output.stem + '-bank-before.json')
    need(not backup.exists(), 'Recovery bank backup already exists; do not replay.')
    with session(args.state):
        identity = verified_identity(args.state)
        need(all(identity.get(key) == entry.get('identity', {}).get(key) for key in
             ('pid', 'script_sha256', 'test_token', 'profile')), 'Rejected receipt belongs to another runtime.')
        need(identity['test_token'] == journal['token'] and process_alive(preparation['runtime_pid']) is False,
             'The old preparation runtime must be absent.')
        from household_stress import validate, differences
        fresh = {}
        for sid in native.get('snapshots', {}):
            row = owned_request(args.state, 'test_snapshot', sid, value=json.dumps(
                dict(test_token=journal['token'], value='forms')))
            validate(row, sid, list(native['snapshots']), preparation['household_id'], preparation['save_guid'])
            fresh[sid] = row
        need(fresh and differences(native['snapshots'], fresh) == [], 'Native owners changed after the retained comparison.')
        native = dict(native, snapshots=fresh)
        diagnostic = owned_request(args.state, 'cas_ui_diagnostics')
        status = owned_request(args.state, 'test_native_cas_engine', value=json.dumps(
            dict(test_token=journal['token'], value=dict(operation='status'))))
        updated = plan(entry, native, status, diagnostic, bank, preparation)
        saves = all_save_files(profile)
        archive = reusable_profile.writable(prep.with_name('household_cas_entry.' + prep_hash + '.json'))
        need(archive.parent == prep.parent and prep.parent.parent == profile, 'Preparation archive escaped the disposable profile.')
        if archive.exists(): need(archive.read_bytes() == prep_bytes, 'Preparation archive differs.')
        with backup.open('xb') as stream:stream.write(bank_bytes)
        receipt = dict(ok=False, operation='recover-proved-rejected-cas-entry', identity=identity,
            entry_sha256=sha256(args.entry_proof), native_sha256=sha256(args.native_proof),
            bank_before_sha256=bank_hash, preparation_sha256=prep_hash, preparation_archive=str(archive),
            metadata_write_started=False, appearance_modified=False, save_written=False)
        write_json(output, receipt)
        with writer._writer_lease(bank_path) as lease:
            need(bank_path.read_bytes() == bank_bytes and prep.read_bytes() == prep_bytes and
                 all_save_files(profile) == saves, 'Metadata or saves changed before the writer lease.')
            receipt['metadata_write_started'] = True;write_json(output, receipt)
            os.replace(str(prep), str(archive))
            writer.atomic_save(bank_path, updated, expected_file_sha256=bank_hash, _lease=lease)
        receipt.update(ok=read(bank_path) == updated and all_save_files(profile) == saves,
            bank_lanes_unchanged=all(updated['records'][key]['bank'] == bank['records'][key]['bank'] for key in bank['records']),
            all_saves_unchanged=all_save_files(profile) == saves, originals_preserved=True)
        write_json(output, receipt)
        return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('state', 'entry-proof', 'native-proof', 'output'):parser.add_argument('--' + name, required=True, type=Path)
    print(json.dumps(run(parser.parse_args()), indent=2))
