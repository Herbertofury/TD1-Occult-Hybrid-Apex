"""Verify saved bank appearances against native owners after a real restart.

Only native reads and one typed play/pause pair occur. No cached studio lane,
Sim serializer, form creation/restoration, save, CAS entry or pointer input is used.
Complete returned records remain in external content-addressed JSON evidence;
only appearance fingerprints are compared across simulation progression.
"""
import base64
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import apex_cli
import cas_return
import cas_transition
import reusable_profile
from source_manifest import sha256, write_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_appearance, outfit_snapshot

FORMS = (1, 2, 4, 8, 16, 32, 64)
MEMBERS = {2: 'ALIEN', 4: 'VAMPIRE', 8: 'MERMAID', 16: 'WITCH', 32: 'WEREWOLF', 64: 'FAIRY'}
PERSISTENCE_CHECKS = {'active_household_membership', 'runtime_household_identity', 'manager_identity',
    'account_save_eligible', 'sim_proto_exists', 'sim_proto_identity', 'sim_proto_household_identity',
    'household_proto_exists', 'household_proto_identity', 'household_proto_membership'}
MAX_RAW_BYTES = 64 * 1024 * 1024
MAX_PROOF_BYTES = 2 * 1024 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':')).encode('ascii')


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(char in '0123456789abcdef' for char in value)


def typed_value(row, depth=0):
    """Validate appearance encodings without constructing game resource objects."""
    if not isinstance(row, dict) or set(row) != {'kind', 'value'} or depth > 8:
        raise ValueError('Invalid typed appearance value.')
    kind, value = row['kind'], row['value']
    if kind == 'value' and (value is None or type(value) in (bool, str, int) or
                            type(value) is float and math.isfinite(value)):
        return
    if kind in ('bytes', 'protobuf') and isinstance(value, str) and len(value) <= 12 * 1024 * 1024:
        base64.b64decode(value, validate=True)
        return
    if kind in ('tuple', 'list') and isinstance(value, list) and len(value) <= 1024:
        for item in value:
            typed_value(item, depth + 1)
        return
    if kind == 'resourcekey' and isinstance(value, list) and len(value) == 3 and all(type(item) is int and 0 <= item < 1 << 64 for item in value):
        return
    if kind in ('mapping', 'dict'):
        pairs = value if kind == 'mapping' else [[{'kind': 'value', 'value': key}, item] for key, item in value.items()] if isinstance(value, dict) else None
        if not isinstance(pairs, list) or len(pairs) > 1024:
            raise ValueError('Invalid typed appearance mapping.')
        keys = set()
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError('Invalid typed appearance mapping pair.')
            typed_value(pair[0], depth + 1); typed_value(pair[1], depth + 1)
            if pair[0]['kind'] != 'value' or type(pair[0]['value']) not in (str, int, bool) or pair[0]['value'] in keys:
                raise ValueError('Invalid or duplicate appearance mapping key.')
            keys.add(pair[0]['value'])
        return
    raise ValueError('Unsupported typed appearance value; no field was dropped.')


def appearance_fingerprint(fields):
    """Same normalized field/hash contract as form_appearance.fingerprint."""
    if (not isinstance(fields, dict) or '__outfits__' not in fields or
            set(fields) - set(form_appearance.FIELDS + ('__outfits__',))):
        raise ValueError('A complete supported appearance payload is required.')
    for row in fields.values():
        typed_value(row)
    outfits = fields['__outfits__']
    if outfits['kind'] != 'protobuf':
        raise ValueError('Native outfit appearance must retain its complete protobuf bytes.')
    raw = base64.b64decode(outfits['value'], validate=True)
    if not raw:
        raise ValueError('Native outfit appearance bytes are absent.')
    canonical = copy.deepcopy(fields)
    canonical['__outfits__'] = form_appearance.encode(('protobuf', outfit_snapshot.normalize(raw)))
    genetics = canonical.get('genetic_data')
    if genetics is not None and genetics['kind'] in ('bytes', 'protobuf'):
        from apex_core.genetics_snapshot import normalize
        projected = normalize(base64.b64decode(genetics['value'], validate=True))
        canonical['genetic_data'] = form_appearance.encode(
            projected if genetics['kind'] == 'bytes' else ('protobuf', projected))
    identities = {name: hashlib.sha256(encoded(row)).hexdigest() for name, row in canonical.items()}
    return {'appearance_sha256': hashlib.sha256(encoded(identities)).hexdigest(),
            'field_sha256': identities, 'readable_fields': sorted(fields)}


def read_json(path, maximum):
    path = reusable_profile.writable(path)
    before = path.stat()
    with path.open('rb') as stream:
        raw = stream.read() if maximum is None else stream.read(maximum + 1)
    after = path.stat()
    if (not raw or maximum is not None and len(raw) > maximum or (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size) or len(raw) != after.st_size):
        raise ValueError('Input JSON is oversized or changed during its read.')
    return json.loads(raw.decode('utf-8'), parse_constant=lambda _value: (_ for _ in ()).throw(ValueError('Non-finite JSON input.'))), hashlib.sha256(raw).hexdigest(), len(raw)


def closed_reference(path, expected_sha, profile, original, journal, identity):
    path = reusable_profile.writable(path)
    if any(path == root or root in path.parents for root in (profile, original)) or not digest(expected_sha):
        raise ValueError('Use an exact external closed-session proof and its SHA-256.')
    proof, actual_sha, size = read_json(path, 24 * 1024 * 1024)
    if not isinstance(proof, dict):
        raise ValueError('Closed-session proof must be a typed JSON object.')
    old = proof.get('identity') if isinstance(proof, dict) else None
    if (actual_sha != expected_sha or type(proof.get('schema')) is not int or proof['schema'] != 1 or proof.get('operation') != 'normal-save-and-exit' or
            proof.get('outcome') != 'normal-save-and-exit' or
            any(proof.get(name) is not True for name in ('ok', 'game_exit_verified', 'normal_exit_verified',
                'save_and_exit_input_accepted', 'save_completed_file_verified')) or proof.get('final_process_alive') is not False or
            not isinstance(old, dict) or type(old.get('pid')) is not int or not 0 < old['pid'] <= 0xffffffff or
            old['pid'] == identity['pid'] or old.get('test_token') != journal['token'] or
            not digest(old.get('script_sha256')) or not isinstance(old.get('profile'), str) or Path(old['profile']).resolve() != profile):
        raise ValueError('Closed-session proof is not an exact successful prior disposable PID/token/save exit.')
    inputs = proof.get('inputs')
    if not isinstance(inputs, list) or not any(isinstance(row, dict) and row.get('name') == 'ApexOccultHybrid.ts4script' and row.get('sha256') == old['script_sha256']
               for row in inputs):
        raise ValueError('Closed proof does not bind its prior installed script.')
    crash = proof.get('crash')
    if not isinstance(crash, dict) or crash.get('preserved') is not False or crash.get('outcome') not in ('unchanged', 'absent'):
        raise ValueError('Closed proof has unresolved or changed crash evidence.')
    before, after, changed = proof.get('before_saves'), proof.get('after_saves'), proof.get('rewritten_normal_slots')
    if not all(isinstance(row, dict) for row in (before, after, changed)) or set(changed) != {'Slot_00000002.save'}:
        raise ValueError('Reload verification requires only the rewritten existing Slot02 target.')
    calculated = {name: row for name, row in after.items() if row != before.get(name)}
    row = after.get('Slot_00000002.save')
    if (calculated != changed or changed.get('Slot_00000002.save') != row or not isinstance(row, dict) or
            not digest(row.get('sha256')) or type(row.get('bytes')) is not int or not 0 < row['bytes'] <= 256 * 1024 * 1024 or
            type(row.get('mtime_ns')) is not int or row['mtime_ns'] < 0):
        raise ValueError('Closed proof slot rewrite references differ.')
    return {'path': str(path), 'sha256': actual_sha, 'bytes': size, 'prior_identity': old, 'save': row}


def certified_closed_reference(path, expected_sha, save_path, expected_save_sha,
                               profile, original, journal, identity, sim_id, household_id, save_guid):
    """A controlled sealed save followed by the same process's normal no-save exit."""
    def external(source, expected):
        source = reusable_profile.writable(source)
        if not digest(expected) or any(source == root or root in source.parents for root in (profile, original)):
            raise ValueError('Use hash-pinned external save and unsaved-exit proofs.')
        value, actual, size = read_json(source, 24 * 1024 * 1024)
        if actual != expected or not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1:
            raise ValueError('Certified save/exit proof hash or schema differs.')
        return value, {'path': str(source), 'sha256': actual, 'bytes': size}
    closed, closed_pin = external(path, expected_sha)
    saved, save_pin = external(save_path, expected_save_sha)
    old = closed.get('identity'); saved_identity = saved.get('identity')
    if (not isinstance(old, dict) or not isinstance(saved_identity, dict) or type(old.get('pid')) is not int or type(saved_identity.get('pid')) is not int or
            not 0 < old['pid'] <= 0xffffffff or old['pid'] == identity['pid'] or
            any(saved_identity.get(name) != old.get(name) for name in ('pid', 'test_token', 'script_sha256', 'profile')) or
            old.get('test_token') != journal['token'] or old.get('script_sha256') != identity['script_sha256'] or
            not digest(old.get('script_sha256')) or not isinstance(old.get('profile'), str) or Path(old['profile']).resolve() != profile):
        raise ValueError('Controlled save, normal exit and current bridge must bind the exact prior PID/token/source/profile.')
    for value in (closed, saved):
        inputs = value.get('inputs')
        if (not isinstance(inputs, list) or not any(isinstance(row, dict) and row.get('name') == 'ApexOccultHybrid.ts4script' and
                row.get('sha256') == old['script_sha256'] for row in inputs) or 'error' in value):
            raise ValueError('Certified proof has failed observations or lacks the exact installed script.')
        crash = value.get('crash')
        before_crash = value.get('before_crash' if value is closed else 'crash_before')
        if (not isinstance(crash, dict) or crash.get('preserved') is not False or crash.get('outcome') not in ('absent', 'unchanged') or
                not isinstance(before_crash, dict) or before_crash.get('state') not in ('absent', 'read') or
                crash.get('before') != before_crash or not isinstance(crash.get('after'), dict) or
                crash['after'].get('state') != before_crash['state'] or
                before_crash['state'] == 'read' and (not digest(before_crash.get('sha256')) or
                    crash['after'].get('sha256') != before_crash['sha256'])):
            raise ValueError('Certified save/exit has unresolved or changed crash evidence.')
    if (closed.get('operation') != 'normal-exit-without-saving' or closed.get('outcome') != 'normal-exit-without-saving' or
            any(closed.get(name) is not True for name in ('ok', 'normal_exit_verified', 'game_exit_verified',
                'exit_without_save_input_accepted', 'save_files_unchanged_verified')) or
            closed.get('final_process_alive') is not False or closed.get('save_requested') is not False or
            closed.get('save_and_exit_input_accepted') is not False or
            closed.get('save_completed_file_verified') is not False or
            any(closed.get('requested_' + name) != expected for name, expected in
                (('sim_id', sim_id), ('household_id', household_id), ('save_guid', save_guid)))):
        raise ValueError('Certified save requires an exact normal exit without another Save input.')
    inventory = closed.get('before_all_saves')
    if (not isinstance(inventory, dict) or not 0 < len(inventory) <= 1024 or
            closed.get('after_all_saves') != inventory):
        raise ValueError('All disposable save/backup files must remain unchanged through exit.')
    for name, row in inventory.items():
        if (not isinstance(name, str) or Path(name).name != name or not isinstance(row, dict) or not digest(row.get('sha256')) or
                type(row.get('bytes')) is not int or not 0 <= row['bytes'] <= 512 * 1024 * 1024 or
                type(row.get('mtime_ns')) is not int or row['mtime_ns'] < 0):
            raise ValueError('Unsaved-exit save inventory is incomplete or untyped.')
    target = saved.get('target')
    if (saved.get('operation') != 'explicit-existing-disposable-save' or saved.get('outcome') != 'existing-target-save-file-observed' or
            any(saved.get(name) is not True for name in ('ok', 'save_command_attempted', 'save_submitted',
                'save_completed_file_verified', 'native_target_slot_verified', 'form_bank_seal_verified', 'crash_clear_verified', 'finalized')) or
            saved.get('process_exit_verified') is not False or not cas_return.uuid_id(saved.get('save_request_id')) or
            not isinstance(target, dict) or type(target.get('slot_id')) is not int or target['slot_id'] != 2 or
            any(target.get(name) != expected for name, expected in
                (('sim_id', sim_id), ('household_id', household_id), ('save_guid', save_guid)))):
        raise ValueError('Controlled save has no exact completed sealed Slot02/Sim/household/GUID target.')
    from apex_core.test_driver import _save_target, _save_live_context
    _save_target(target)
    before, after = saved.get('target_before'), saved.get('target_after')
    expected_path = str(profile / 'saves' / 'Slot_00000002.save')
    if (not isinstance(before, dict) or not isinstance(after, dict) or before.get('path') != expected_path or after.get('path') != expected_path or
            not digest(before.get('sha256')) or not digest(after.get('sha256')) or before['sha256'] == after['sha256'] or
            type(before.get('bytes')) is not int or not 0 < before['bytes'] <= 256 * 1024 * 1024 or
            type(before.get('mtime_ns')) is not int or before['mtime_ns'] < 0 or
            target.get('expected_save_sha256') != before['sha256'] or type(after.get('bytes')) is not int or
            not 0 < after['bytes'] <= 256 * 1024 * 1024 or type(after.get('mtime_ns')) is not int or after['mtime_ns'] < 0 or
            inventory.get('Slot_00000002.save') != {name: after[name] for name in ('sha256', 'bytes', 'mtime_ns')}):
        raise ValueError('Controlled target file differs from the unchanged normal-exit inventory.')
    native = _save_live_context(saved.get('native_after'), target)
    if native['save_slot'] != 2:
        raise ValueError('Controlled save did not read back the exact native normal slot.')
    exit_native = _save_live_context(closed.get('unsaved_exit_native_before'), target)
    if (type(exit_native.get('clock_speed')) is not int or exit_native['clock_speed'] != 0 or exit_native['save_slot'] != 2):
        raise ValueError('Normal unsaved exit did not bind the paused native controlled-save target.')
    receipt = saved.get('form_bank_seal')
    if (not isinstance(receipt, dict) or receipt.get('ok') is not True or receipt.get('state') != 'sealed' or
            not cas_return.uuid_id(receipt.get('intent_id')) or not digest(receipt.get('seal_sha256')) or
            not digest(receipt.get('bank_record_sha256')) or receipt.get('file_sha256') != after['sha256']):
        raise ValueError('Controlled save has no exact successful appearance seal receipt.')
    return {**closed_pin, 'prior_identity': old, 'save': {name: after[name] for name in ('sha256', 'bytes', 'mtime_ns')},
            'reference_kind': 'controlled-sealed-save-and-normal-unsaved-exit', 'controlled_save': save_pin,
            'seal_receipt': receipt, 'save_target': target}


def completed_bank_history(selected, reference, sim_id, household_id, save_guid):
    """Current sealed all-owner receipts take precedence over legacy history."""
    transaction = selected.get('cas_transaction')
    if transaction is not None:
        from apex_core.cas_bank_transaction import _completed
        from apex_core.cas_commit_plan import _serialized_append
        expected_identity = {'runtime_pid': reference['prior_identity']['pid'],
                             'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid}
        if (reference.get('reference_kind') != 'controlled-sealed-save-and-normal-unsaved-exit' or
                not _completed(transaction) or transaction['identity'] != expected_identity):
            raise ValueError('Reload requires the exact completed, sealed all-owner CAS transaction.')
        journal = transaction['journal']
        native = journal.get('native_serialized_append')
        _serialized_append(native, expected_identity)
        desired = journal['plan']['desired']
        if (journal.get('complete_serializer_appended') is not True or
                not isinstance(native, dict) or native.get('sim_id') != sim_id or native.get('save_guid') != save_guid or
                native.get('native_serializer_called') is not True or native.get('save_file_written') is not False or
                not catalog_identity(native, sim_id, household_id) or
                hashlib.sha256(encoded(native)).hexdigest() != journal.get('native_serialized_sha256') or
                set(desired) != {str(form) for form in FORMS} or
                any(appearance_fingerprint(selected['bank'][lane]) != appearance_fingerprint(fields)
                    for lane, fields in desired.items())):
            raise ValueError('Completed all-owner native record, identities or current bank differ from the approved plan.')
        return {'state': 'completed', 'source': 'sealed-all-owner-cas-transaction',
                'transaction_id': transaction['transaction_id'], 'plan_sha256': journal['plan_sha256'],
                'native_serialized_sha256': journal['native_serialized_sha256'],
                'membership': list(MEMBERS), 'identity': expected_identity}
    history = selected['history'][-1]
    native = history.get('native_after') if isinstance(history, dict) else None
    if (not isinstance(history, dict) or history.get('state') != 'completed' or not isinstance(native, dict) or
            native.get('sim_id') != sim_id or native.get('save_guid') != save_guid or
            not catalog_identity(native, sim_id, household_id) or not isinstance(history.get('membership'), list) or
            any(type(flags) is not int for flags in history['membership']) or set(history['membership']) != set(MEMBERS)):
        raise ValueError('Bank has no exact completed six-occult transaction for this saved Sim/GUID.')
    return history


def validate_certified_sidecar(reference, profile, identity, selected, key):
    """Bind the expected bank to the actual seal, never merely a receipt label."""
    if reference.get('reference_kind') != 'controlled-sealed-save-and-normal-unsaved-exit':
        return
    from apex_core.form_bank_seal import CONTRACT
    store, checksum, size = read_json(profile / 'TD1_OccultHybridApexData/form_bank_seals.json', 48 * 1024 * 1024)
    records = store.get('records') if isinstance(store, dict) else None
    row = records.get(key) if isinstance(records, dict) else None
    receipt = reference['seal_receipt']
    names = ('intent_id', 'identity', 'contract_sha256', 'target', 'bank_record_sha256', 'appearances', 'file_sha256')
    if (not isinstance(store, dict) or type(store.get('schema')) is not int or store['schema'] != 1 or
            not isinstance(row, dict) or row.get('state') not in ('sealed', 'reconciled') or row.get('sealed') is not True or
            row.get('contract_sha256') != CONTRACT or not all(name in row for name in names) or
            not isinstance(row.get('identity'), dict) or any(row['identity'].get(name) != reference['prior_identity'].get(name)
                for name in ('pid', 'test_token', 'script_sha256', 'profile')) or row.get('target') != reference['save_target'] or
            any(row.get(name) != receipt.get(name) for name in ('intent_id', 'seal_sha256', 'file_sha256', 'bank_record_sha256')) or
            row.get('bank_record_sha256') != hashlib.sha256(encoded(selected)).hexdigest() or row.get('appearances') != selected['bank'] or
            hashlib.sha256(encoded({name: row[name] for name in names})).hexdigest() != row.get('seal_sha256')):
        raise ValueError('Actual appearance sidecar, seal identity, current bank or file hash differs from the certified proof.')
    if row['state'] == 'reconciled':
        recovery = row.get('reconciliation')
        if not isinstance(recovery, dict) or recovery.get('ok') is not True or type(recovery.get('pid')) is not int or recovery['pid'] != identity['pid']:
            raise ValueError('Reconciled appearance sidecar belongs to an unknown or different reload PID.')
    reference['sidecar'] = {'path': str(profile / 'TD1_OccultHybridApexData/form_bank_seals.json'),
                            'sha256': checksum, 'bytes': size, 'state': row['state'], 'seal_sha256': row['seal_sha256']}


def membership(rows):
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError('Native membership read inventory is unavailable.')
    found, coverage = {}, []
    for row in rows:
        if not isinstance(row, dict) or type(row.get('flags')) is not int or row['flags'] in found:
            raise ValueError('Native membership identities are untyped or duplicate.')
        found[row['flags']] = row
    for flags, name in MEMBERS.items():
        row = found.get(flags)
        valid = (isinstance(row, dict) and row.get('occult') == name and row.get('query') == 'returned-value' and row.get('has_occult') is True)
        coverage.append({'flags': flags, 'occult': name, 'verified': valid, 'native': row})
    return coverage, all(row['verified'] for row in coverage)


def compare_appearance(actual, expected):
    if not isinstance(actual, dict) or not isinstance(actual.get('typed_payload'), dict):
        return {'verified': False, 'reason': 'Complete native appearance payload was not returned.'}
    observed = appearance_fingerprint(actual['typed_payload'])
    if any(actual.get(name) != observed[name] for name in ('appearance_sha256', 'field_sha256', 'readable_fields')):
        raise ValueError('Returned appearance fingerprint differs from its complete native payload.')
    changed = [name for name in sorted(set(expected['field_sha256']) | set(observed['field_sha256']))
               if expected['field_sha256'].get(name) != observed['field_sha256'].get(name)]
    return {'verified': not changed and observed['appearance_sha256'] == expected['appearance_sha256'],
            'expected': expected, 'native': observed, 'changed_fields': changed}


def catalog_identity(record, sim_id, household_id):
    data = record.get('data') if isinstance(record, dict) else None
    fields = data.get('fields') if isinstance(data, dict) else None
    if not isinstance(fields, list):
        return False
    for name, expected in (('sim_id', sim_id), ('household_id', household_id)):
        found = [row for row in fields if isinstance(row, dict) and row.get('name') == name]
        if len(found) != 1 or found[0].get('present') is not True or found[0].get('value') != expected:
            return False
    return True


def observe(state, output, identity, request, save_exit_proof, expected_proof_sha256,
            sim_id, household_id, save_guid, seconds=60, settle_ticks=750,
            transport=None, alive=cas_transition.process_alive, monotonic=time.monotonic, pause=time.sleep,
            save_proof=None, expected_save_proof_sha256=None):
    if (not all(cas_return.decimal_id(value) for value in (sim_id, household_id, save_guid)) or
            type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 120 or
            type(settle_ticks) is not int or not 1 <= settle_ticks <= 6000):
        raise ValueError('Use exact Sim/household/save identities and bounded native progression.')
    started = monotonic(); deadline = started + seconds; cleanup_reserve = min(4, seconds / 3)
    journal_path, journal, profile, original = reusable_profile.load(state)
    script = next((row['sha256'] for row in journal['artifacts'] if row['name'] == 'ApexOccultHybrid.ts4script'), None)
    if (not isinstance(identity, dict) or type(identity.get('pid')) is not int or not 0 < identity['pid'] <= 0xffffffff or
            identity.get('test_token') != journal['token'] or not digest(script) or identity.get('script_sha256') != script or
            not isinstance(identity.get('profile'), str) or Path(identity['profile']).resolve() != profile):
        raise ValueError('Reload bridge differs from the exact disposable PID/token/profile/script.')
    output = reusable_profile.writable(output)
    if (output.exists() or output.suffix.casefold() != '.json' or not output.parent.is_dir() or output == journal_path or
            any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use a new external JSON reload proof outside both profiles and the journal.')
    if (save_proof is None) != (expected_save_proof_sha256 is None):
        raise ValueError('Supply both controlled-save proof and its exact SHA-256, or neither for the legacy SaveAndExit verifier.')
    reference = (closed_reference(save_exit_proof, expected_proof_sha256, profile, original, journal, identity)
        if save_proof is None else certified_closed_reference(save_exit_proof, expected_proof_sha256,
            save_proof, expected_save_proof_sha256, profile, original, journal, identity, sim_id, household_id, save_guid))
    slot = reusable_profile.writable(profile / 'saves/Slot_00000002.save')
    if sha256(slot) != reference['save']['sha256'] or slot.stat().st_size != reference['save'].get('bytes'):
        raise ValueError('Reloaded Slot02 bytes differ from the pinned successful save/exit proof.')
    bank_path = reusable_profile.writable(profile / 'TD1_OccultHybridApexData/form_bank.json')
    bank, bank_sha, bank_bytes = read_json(bank_path, None)
    if not isinstance(bank, dict):
        raise ValueError('Saved form bank must be a typed JSON object.')
    key = save_guid + ':' + sim_id
    records = bank.get('records') if isinstance(bank, dict) else None
    selected = records.get(key) if isinstance(records, dict) else None
    if (type(bank.get('schema')) is not int or bank['schema'] != 1 or not isinstance(selected, dict) or selected.get('pending') is not None or
            selected.get('switch_pending') is not None or type(selected.get('runtime_pid')) is not int or
            selected['runtime_pid'] != reference['prior_identity']['pid'] or
            not isinstance(selected.get('bank'), dict) or set(selected['bank']) != {str(form) for form in FORMS} or
            not isinstance(selected.get('history'), list) or
            (not selected['history'] and selected.get('cas_transaction') is None)):
        raise ValueError('Saved bank key/lanes/prior PID or transaction ownership is unavailable.')
    history = completed_bank_history(selected, reference, sim_id, household_id, save_guid)
    if selected.get('native_rebase_requires_cas_completion') is not None and selected.get('native_rebase_requires_cas_completion') is not False:
        raise ValueError('A fresh native rebase is not completed CAS evidence.')
    validate_certified_sidecar(reference, profile, identity, selected, key)
    expected = {lane: appearance_fingerprint(fields) for lane, fields in selected['bank'].items()}
    crash_before, _ = cas_transition.read_crash(profile)
    if crash_before.get('state') not in ('absent', 'read'):
        raise ValueError('Native crash baseline is unavailable or exceeds its bound; no game requests were sent.')
    if transport is None:
        transport = apex_cli.get
    proof = {'schema': 1, 'operation': 'native-form-save-reload-verification', 'ok': False, 'outcome': 'unresolved',
        'identity': identity, 'journal': str(journal_path), 'inputs': journal['artifacts'], 'closed_session': reference,
        'sim_id': sim_id, 'household_id': household_id, 'save_guid': save_guid, 'slot_id': 2,
        'bank': {'path': str(bank_path), 'sha256': bank_sha, 'bytes': bank_bytes, 'key': key,
                 'runtime_pid': selected['runtime_pid'], 'history_count': len(selected['history']),
                 'completed_history_sha256': hashlib.sha256(encoded(history)).hexdigest(), 'expected': expected},
        'seconds': seconds, 'settle_ticks': settle_ticks, 'steps': [], 'owner_requests': [],
        'phases': [], 'raw_bytes_retained': 0, 'clock_progress_verified': False, 'final_paused': False,
        'play_attempted': False, 'pause_attempted': False, 'save_reload_verified': False,
        'initial_appearances_verified': False, 'settled_appearances_verified': False,
        'profile_read_only': True, 'appearance_mutated': False, 'formbank_mutated': False,
        'save_submitted': False, 'cas_submitted': False, 'input_submitted': False,
        'crash_before': crash_before, 'process_exit_verified': False,
        'scope': 'Each saved bank lane compared with complete native stored-owner appearance before and after tick progression; full Sim gameplay data is retained but not compared.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(proof, stream, indent=2, ensure_ascii=False, allow_nan=False)
    baseline = None; active_step = None; wrapper_ids = {}; play_attempted = pause_attempted = False

    def record():
        if len(encoded(proof)) > MAX_PROOF_BYTES:
            raise ValueError('Reload proof metadata exceeded its bound.')
        write_json(output, proof)

    def remaining(reserve=False):
        left = deadline - monotonic() - (cleanup_reserve if reserve else 0)
        if left <= 0:
            raise TimeoutError('Reload verification deadline expired; no request replay permitted.')
        return left

    def running():
        if not alive(identity['pid']):
            proof['process_exit_verified'] = True
            raise ProcessLookupError('Verified Sims PID exited during reload verification.')

    def pinned_transport(path, query=None, timeout=12):
        timeout = min(timeout, 2, remaining())
        if path in ('/api/command', '/api/native') and isinstance(query, dict):
            if not cas_return.uuid_id(query.get('request_id')) or len(proof['owner_requests']) >= 256:
                raise ValueError('Owner request inventory is unavailable or exceeds its bound.')
            row = {'action': query.get('action'), 'request_id': query['request_id']}
            proof['owner_requests'].append(row)
            if active_step is not None:
                active_step['owner_requests'].append(row)
            record()  # Exact UUID is durable before the first transport write.
        result = transport(path, query, timeout=timeout)
        if path == '/api/bridge' and (not isinstance(result, dict) or any(result.get(name) != identity[name]
                for name in ('pid', 'test_token', 'script_sha256'))):
            raise ValueError('Pinned reload bridge changed PID/token/script.')
        return result

    def call(action, value=None):
        nonlocal active_step
        running(); remaining()
        step = {'action': action, 'owner_requests': [], 'state': 'attempted', 'elapsed_seconds': max(0, monotonic() - started)}
        proof['steps'].append(step); active_step = step; record()
        try:
            result = request(state, action, sim_id=sim_id,
                             value=json.dumps({'test_token': journal['token'], 'value': value}),
                             seconds=min(2, remaining()), transport=pinned_transport)
            if not isinstance(result, dict):
                raise ValueError('Reload owner result is untyped.')
            step.update(state='observed', request_id=result.get('request_id'), ok=result.get('ok'),
                        request_state=result.get('request_state'))
            record()
            if result.get('request_state') in ('pending', 'running', 'unknown') or result.get('outcome') == 'unresolved':
                raise RuntimeError('Owner result is unresolved; retain its UUID, never resubmit it.')
            return result
        except (OSError, ValueError, RuntimeError) as error:
            step.update(state='unresolved', error=str(error)); record(); raise
        finally:
            active_step = None

    def same_live(live):
        if not isinstance(live, dict) or live.get('sim_time_source') != cas_return.SIM_TIME_SOURCE:
            raise ValueError('Native reload progression requires the verified simulation timeline origin.')
        if (not cas_return.live_snapshot(live, sim_id, household_id) or live.get('save_guid') != save_guid or
                type(live.get('save_slot')) is not int or live['save_slot'] != 2):
            raise ValueError('Native reloaded Live Sim/household/GUID/Slot02 context differs.')
        if baseline is not None and any(live.get(name) != baseline[name] for name in ('client_id', 'zone_id')):
            raise ValueError('Native client/zone changed during reload verification.')
        persisted = live.get('persistence')
        if (not isinstance(persisted, dict) or persisted.get('persistence_verified_before_save') is not True or
                not isinstance(persisted.get('checks'), dict) or not PERSISTENCE_CHECKS.issubset(persisted['checks']) or
                any(persisted['checks'][name] is not True for name in PERSISTENCE_CHECKS) or
                not isinstance(persisted.get('household_sim_ids'), list) or not isinstance(persisted.get('persisted_household_sim_ids'), list) or
                sim_id not in persisted.get('household_sim_ids', []) or sim_id not in persisted.get('persisted_household_sim_ids', [])):
            raise ValueError('Native Sim/household persistence checks are incomplete or failed.')
        return live

    def retain(result, phase, form):
        raw = encoded(result)
        if len(raw) > 8 * 1024 * 1024 or proof['raw_bytes_retained'] + len(raw) > MAX_RAW_BYTES:
            raise ValueError('Complete native record exceeds the external evidence budget; no partial record retained.')
        checksum = hashlib.sha256(raw).hexdigest()
        target = reusable_profile.writable(output.with_name(output.stem + '-' + phase + '-form-' + str(form) + '-' + checksum + '.json'))
        with target.open('xb') as stream:
            stream.write(raw)
        proof['raw_bytes_retained'] += len(raw)
        return {'path': str(target), 'sha256': checksum, 'bytes': len(raw)}

    def phase(name, paused_context):
        active_form = paused_context['sim'].get('current_form')
        if type(active_form) is not int or active_form not in FORMS or paused_context.get('clock_speed') != 0:
            raise ValueError('Appearance phase requires a fresh paused native active-form identity.')
        rows = []; phase_result = {'phase': name, 'forms': rows, 'verified': False,
            'paused_active_form_flags': active_form, 'active_live_comparison_observed': False}; proof['phases'].append(phase_result); record()
        for flags in FORMS:
            running(); remaining(reserve=True)
            result = call('test_form_snapshot', {'form_flags': flags, 'save_guid': save_guid,
                          'household_id': household_id, 'include_native_record': flags == FORMS[0]})
            raw = retain(result, name, flags)
            row = {'form_flags': flags, 'raw': raw, 'verified': False}; rows.append(row); record()
            live = same_live(result.get('live_context'))
            if (live.get('clock_speed') != 0 or type(live['sim'].get('current_form')) is not int or
                    live['sim']['current_form'] != active_form or type(result.get('current_form_flags')) is not int or
                    result['current_form_flags'] != active_form):
                raise ValueError('Paused active native form changed during the appearance phase; no active-owner coverage inferred.')
            if (type(result.get('form_flags')) is not int or result['form_flags'] != flags or result.get('sim_id') != sim_id or
                    result.get('bank_read') is not False or result.get('form_created') is not False or
                    result.get('appearance_mutated') is not False):
                raise ValueError('Explicit native form ownership/source differs or a mutation was reported.')
            coverage, members_ok = membership(result.get('native_membership'))
            row.update(membership=coverage, six_memberships_verified=members_ok,
                       native_wrapper_id=result.get('native_wrapper_id'), source=result.get('source'),
                       stored_form_present=result.get('stored_form_present'))
            if result.get('ok') is not True:
                if result.get('outcome') != 'missing-native-form' or result.get('source') != 'native-form-map':
                    raise ValueError('Native form read failed without a typed missing-owner receipt.')
                row['reason'] = 'missing-native-form'; record(); continue
            if not cas_return.decimal_id(result.get('native_wrapper_id')):
                raise ValueError('Native appearance wrapper identity is unavailable.')
            if name == 'initial':
                wrapper_ids[flags] = result['native_wrapper_id']
            elif flags in wrapper_ids and wrapper_ids[flags] != result['native_wrapper_id']:
                raise ValueError('Native appearance wrapper changed across simulation progression.')
            comparison = compare_appearance(result.get('appearance'), expected[str(flags)])
            row['appearance'] = comparison
            active = result.get('current_form_flags')
            if type(active) is not int or active not in FORMS:
                raise ValueError('Native current form identity is unavailable.')
            row['active_live_appearance'] = compare_appearance(result.get('active_live_appearance'), expected[str(flags)]) if active == flags else None
            if active == flags:
                phase_result['active_live_comparison_observed'] = True
            owner_ok = result.get('source') == 'native-form-map' and result.get('stored_form_present') is True
            row['verified'] = owner_ok and members_ok and comparison['verified'] and (active != flags or row['active_live_appearance']['verified'])
            if not owner_ok:
                row['reason'] = 'stored-native-owner-unverified'
            if flags == FORMS[0]:
                native = result.get('native_record')
                if (not isinstance(native, dict) or type(native.get('schema')) is not int or native['schema'] != 1 or native.get('source') != 'native-existing-save-buffer' or
                        any(native.get(key) != expected_id for key, expected_id in (('sim_id', sim_id), ('household_id', household_id), ('save_guid', save_guid))) or
                        native.get('unknown_fields_retained_in_native_bytes') is not True or not isinstance(native.get('field_schemas'), dict) or
                        not isinstance(native.get('native_base64'), str) or not catalog_identity(native, sim_id, household_id)):
                    raise ValueError('Complete native persistence bytes/schema evidence is unavailable.')
                raw_native = base64.b64decode(native.get('native_base64', ''), validate=True)
                if (not 0 < len(raw_native) <= 4 * 1024 * 1024 or type(native.get('native_bytes')) is not int or
                        native['native_bytes'] != len(raw_native) or hashlib.sha256(raw_native).hexdigest() != native.get('native_sha256')):
                    raise ValueError('Native persistence byte identity differs from its read-only record.')
                phase_result['native_persistence_record_verified'] = True
            record()
        phase_result['verified'] = (len(rows) == len(FORMS) and all(row['verified'] for row in rows) and
                                    phase_result.get('native_persistence_record_verified') is True and
                                    phase_result['active_live_comparison_observed'])
        record(); return phase_result['verified']

    def pause_once():
        nonlocal pause_attempted
        same_live(call('test_snapshot'))  # No clock action after a cross-save/household change.
        pause_attempted = True; proof['pause_attempted'] = True; record()
        paused = same_live(call('test_pause'))
        if paused.get('clock_speed') != 0:
            raise RuntimeError('Paused native clock readback was not verified; no pause replay allowed.')
        proof['final_paused'] = True; record()
        return paused

    try:
        running(); remaining(reserve=True)
        from game_lifecycle import shutdown_cas_state
        diagnostic = call('cas_ui_diagnostics'); proof['cas_preflight'] = diagnostic; record()
        if shutdown_cas_state(diagnostic)['safe'] is not True:
            raise ValueError('Native CAS or unresolved ownership is present; reload clock verification was not started.')
        baseline = same_live(call('test_snapshot')); proof['baseline_live'] = baseline; record()
        if baseline['clock_speed'] != 0:
            raise ValueError('Start reload verification with the disposable Live session paused.')
        proof['initial_appearances_verified'] = phase('initial', baseline)
        play_attempted = True; proof['play_attempted'] = True; record()
        played = same_live(call('test_play'))
        if played.get('clock_speed') != 1:
            raise RuntimeError('Native play readback was not verified; no play replay allowed.')
        play_ticks, played_at = int(played['sim_now_ticks']), monotonic()
        while True:
            pause(min(.2, remaining(reserve=True)))
            current = same_live(call('test_snapshot'))
            if current.get('clock_speed') != 1:
                raise ValueError('Native clock left normal play during settling.')
            if int(current['sim_now_ticks']) - play_ticks >= settle_ticks and monotonic() - played_at >= .5:
                proof['clock_progress_verified'] = True
                proof['native_progress'] = {'from_ticks': str(play_ticks), 'to_ticks': current['sim_now_ticks'],
                                            'sim_time_source': current['sim_time_source'],
                                            'elapsed_seconds': monotonic() - played_at}
                record(); break
        paused = pause_once()
        proof['settled_paused_live'] = paused; record()
        proof['settled_appearances_verified'] = phase('settled', paused)
        proof['save_file_unchanged_verified'] = sha256(slot) == reference['save']['sha256']
        proof['bank_unchanged_verified'] = sha256(bank_path) == bank_sha
        proof['certified_reference_unchanged_verified'] = (reference.get('reference_kind') != 'controlled-sealed-save-and-normal-unsaved-exit' or
            all(sha256(Path(pin['path'])) == pin['sha256'] for pin in
                (reference, reference['controlled_save'], reference['sidecar'])))
        proof['save_reload_verified'] = (proof['initial_appearances_verified'] and proof['settled_appearances_verified'] and
            proof['clock_progress_verified'] and proof['final_paused'] and proof['save_file_unchanged_verified'] and proof['bank_unchanged_verified'] and
            proof['certified_reference_unchanged_verified'])
        proof['ok'] = proof['save_reload_verified']
        proof['outcome'] = 'native-appearances-persisted' if proof['ok'] else 'native-appearance-mismatch'
    except (OSError, ValueError, RuntimeError) as error:
        proof['error'] = str(error)
    finally:
        if play_attempted and not pause_attempted:
            try:
                pause_once()
            except (OSError, ValueError, RuntimeError) as error:
                proof['pause_cleanup_error'] = str(error)
        try:
            running()
        except (OSError, ValueError, RuntimeError) as error:
            proof['final_process_error'] = str(error)
            proof.update(ok=False, save_reload_verified=False)
        try:
            proof['crash'] = cas_transition.preserve_crash(profile, output, crash_before)
            crash = proof['crash']; after = crash.get('after', {})
            changed = (isinstance(after, dict) and
                       ((after.get('state') == 'read' and after.get('sha256') != crash_before.get('sha256')) or
                        after.get('state') == 'oversized'))
            proof['crash_clear_verified'] = (crash.get('outcome') in ('absent', 'unchanged') and
                                             after.get('state') in ('absent', 'read') and not changed)
            if changed:
                proof.update(ok=False, save_reload_verified=False,
                             outcome='crash' if crash.get('preserved') is True else 'changed-crash-report-refused')
            elif not proof['crash_clear_verified']:
                proof.update(ok=False, save_reload_verified=False, outcome='crash-observation-unresolved')
        except (OSError, ValueError, RuntimeError) as error:
            proof['crash_observation_error'] = str(error)
            proof.update(ok=False, save_reload_verified=False)
        proof['elapsed_seconds'] = max(0, monotonic() - started); proof['finalized'] = True; record()
    return {'ok': proof['ok'], 'outcome': proof['outcome'], 'proof': str(output), 'proof_sha256': sha256(output),
            'save_reload_verified': proof['save_reload_verified'], 'initial_appearances_verified': proof['initial_appearances_verified'],
            'settled_appearances_verified': proof['settled_appearances_verified'], 'clock_progress_verified': proof['clock_progress_verified'],
            'final_paused': proof['final_paused'], 'message': proof.get('error',
                'Native stored appearances and six memberships checked against the saved bank before and after simulation progression.')}
