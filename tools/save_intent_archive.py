"""Archive an old test save intent after a proven normal, unsaved closure.

No save, appearance or form-bank edits. The live native receiver must be paused
and idle; its cooperative bank writer lease excludes participating save writers.
An abandoned intent is retained verbatim, never relabeled as a rejected save.
"""
import copy
import json
from pathlib import Path
import sys

import cas_transition
import reusable_profile
from source_manifest import sha256, write_json


def validate_record(record, failure, closure, token, save_hash, old_absent):
    if not isinstance(record, dict) or record.get('state') not in ('save-intent', 'save-submitted', 'save-unresolved'):
        raise ValueError('One unresolved native save intent is required.')
    identity = record.get('identity', {})
    identity_fields = ('pid', 'test_token', 'script_sha256', 'profile')
    if (identity.get('test_token') != token or type(identity.get('pid')) is not int or
            old_absent is not True or failure.get('identity', {}).get('pid') != identity['pid'] or
            any(source.get('identity', {}).get(field) != identity.get(field)
                for source in (failure, closure) for field in identity_fields) or
            failure.get('identity', {}).get('test_token') != token or
            closure.get('identity', {}).get('pid') != identity['pid'] or
            closure.get('identity', {}).get('test_token') != token or
            closure.get('ok') is not True or closure.get('normal_exit_verified') is not True or
            closure.get('exit_without_save_input_accepted') is not True or
            closure.get('save_files_unchanged_verified') is not True or
            closure.get('game_exit_verified') is not True or
            failure.get('save_completed_file_verified') is True):
        raise ValueError('Old runtime absence and exact normal unsaved closure must be proven.')
    intent = (failure.get('form_bank_seal') or {}).get('intent_id')
    # The observer retains the scheduling reply inside its durable step trace.
    if intent is None:
        for step in failure.get('steps', []):
            if step.get('action') == 'test_save':
                intent = (step.get('result', {}).get('form_bank_seal') or {}).get('intent_id')
    if intent != record.get('intent_id'):
        raise ValueError('Failed observer does not identify this retained save intent.')
    target = record.get('target', {})
    slot = target.get('slot_id')
    if type(slot) is not int or not 0 < slot < 0xffffffff:
        raise ValueError('Existing normal target slot is untyped.')
    name = 'Slot_{:08x}.save'.format(slot)
    closed_hash = closure.get('after_all_saves', {}).get(name, {}).get('sha256')
    if (record.get('before_file', {}).get('sha256') != save_hash or closed_hash != save_hash or
            target.get('expected_save_sha256') != save_hash):
        raise ValueError('Target save differs from its pre-intent and normal-exit bytes.')
    return slot


def archive(state, failure_path, failure_hash, closure_path, closure_hash, sim_id, output,
            request, identity_provider, process_alive=cas_transition.process_alive):
    from cli_identity_cache import session
    _, journal, profile, original = reusable_profile.load(state)
    def external(path, expected):
        path = reusable_profile.writable(path)
        if any(path == root or root in path.parents for root in (profile, original)) or sha256(path) != expected:
            raise ValueError('Pinned external proof required.')
        return json.loads(path.read_text(encoding='utf-8'))
    failure, closure = external(failure_path, failure_hash), external(closure_path, closure_hash)
    output = reusable_profile.writable(output)
    backup = output.with_name(output.stem + '-seals-before.json')
    if output.exists() or backup.exists() or any(output == root or root in output.parents for root in (profile, original)):
        raise ValueError('New external archive evidence is required.')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
    from apex_core.cas_bank_transaction import _writer_lease
    with session(state):
        identity = identity_provider(state)
        live = request(state, 'test_snapshot', sim_id, value=json.dumps({'test_token': journal['token'], 'value': None}))
        if (live.get('ok') is not True or live.get('clock_speed') != 0 or live.get('zone_running') is not True or
                live.get('sim', {}).get('id') != sim_id):
            raise ValueError('Exact paused native Live Sim is required before metadata archival.')
        diagnostic = request(state, 'cas_ui_diagnostics', sim_id)
        from game_lifecycle import shutdown_cas_state
        if shutdown_cas_state(diagnostic).get('safe') is not True:
            raise ValueError('Active or unresolved CAS blocks save-intent archival.')
        data_dir = reusable_profile.writable(profile / 'TD1_OccultHybridApexData')
        path = reusable_profile.writable(data_dir / 'form_bank_seals.json')
        bank = reusable_profile.writable(data_dir / 'form_bank.json')
        with _writer_lease(bank):
            raw = path.read_bytes()
            if len(raw) > 32 * 1024 * 1024:
                raise ValueError('Sidecar journal exceeds its bound.')
            store = json.loads(raw.decode('utf-8'))
            key = live['save_guid'] + ':' + sim_id
            record = store.get('records', {}).get(key)
            old_pid = (record or {}).get('identity', {}).get('pid')
            if old_pid == identity['pid']:
                raise ValueError('A current-runtime save cannot be abandoned.')
            slot = (record or {}).get('target', {}).get('slot_id')
            if type(slot) is not int:
                raise ValueError('Retained normal target is absent.')
            save = reusable_profile.writable(profile / 'saves' / ('Slot_{:08x}.save'.format(slot)))
            save_hash = sha256(save)
            validate_record(record, failure, closure, journal['token'], save_hash, process_alive(old_pid) is False)
            if record['target'].get('save_guid') != live['save_guid'] or record['target'].get('household_id') != live['household_id']:
                raise ValueError('Native save/household identity differs from the old target.')
            changed = copy.deepcopy(store)
            del changed['records'][key]
            archives = changed.setdefault('abandoned_save_operations', [])
            if not isinstance(archives, list) or len(archives) >= 64:
                raise ValueError('Archive journal requires inspection before another append.')
            archives.append({'state': 'abandoned-after-normal-unsaved-exit', 'record': record,
                             'failure_sha256': failure_hash, 'closure_sha256': closure_hash,
                             'normal_save_sha256': save_hash, 'observed_current_pid': identity['pid']})
            with backup.open('xb') as stream: stream.write(raw)
            if path.read_bytes() != raw or sha256(save) != save_hash or process_alive(old_pid) is not False:
                raise ValueError('Save, sidecar or old runtime changed; nothing archived.')
            write_json(path, changed)
            if json.loads(path.read_text(encoding='utf-8')) != changed or sha256(save) != save_hash:
                raise ValueError('Archive readback changed; retain original sidecar backup.')
            proof = {'ok': True, 'operation': 'archive-unsaved-prior-save-intent', 'intent_id': record['intent_id'],
                     'old_pid': old_pid, 'current_pid': identity['pid'], 'save_guid': live['save_guid'],
                     'normal_save_sha256': save_hash, 'native_save_submitted': False,
                     'appearance_modified': False, 'form_bank_modified': False,
                     'backup': str(backup), 'backup_sha256': sha256(backup),
                     'sidecar_after_sha256': sha256(path), 'record_retained_verbatim': True}
            write_json(output, proof)
            return proof
