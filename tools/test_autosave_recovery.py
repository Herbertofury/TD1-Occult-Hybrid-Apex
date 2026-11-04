"""Explicit recovery of six disposable autosave files after an unsaved failure.

Normal slots, the protected original and mod sidecars are never destinations.
Every replaced autosave is preserved before the first replacement. Interrupted
operations retain their receipts and are not replayed automatically.
"""
import json
import os
from pathlib import Path
import shutil

import reusable_profile
import test_profile
from game_lifecycle import all_save_files
from source_manifest import sha256, write_json

AUTOSAVES = {'Slot_ffffffff.save'} | {'Slot_ffffffff.save.ver' + str(i) for i in range(5)}


def pinned_json(path, expected, state, profile, original):
    path = reusable_profile.writable(path)
    if (path == state or any(path == root or root in path.parents for root in (profile, original))
            or path.suffix.lower() != '.json' or not path.is_file()
            or not 0 < path.stat().st_size <= 12 * 1024 * 1024
            or not isinstance(expected, str) or len(expected) != 64 or sha256(path) != expected):
        raise ValueError('Recovery requires an exact external JSON receipt hash.')
    return path, json.loads(path.read_text(encoding='utf-8'))


@reusable_profile.serialized
def recover(state, backup_manifest, backup_sha256, exit_proof, exit_sha256,
            output, guard=test_profile.require_closed):
    guard()
    state, journal, profile, original = reusable_profile.load(state)
    output = reusable_profile.writable(output)
    if (output.exists() or output == state or output.suffix.lower() != '.json'
            or not output.parent.is_dir()
            or any(output == root or root in output.parents for root in (profile, original))):
        raise ValueError('Use a new external autosave recovery receipt.')
    backup_path, backup = pinned_json(backup_manifest, backup_sha256, state, profile, original)
    exit_path, exited = pinned_json(exit_proof, exit_sha256, state, profile, original)
    identity = exited.get('identity', {})
    legacy_unsaved = (exited.get('operation') == 'normal-discard-failed-cas-session'
                      and exited.get('save_submitted') is False)
    normal_unsaved = (exited.get('operation') == 'normal-exit-without-saving'
                      and exited.get('outcome') == 'normal-exit-without-saving'
                      and exited.get('save_requested') is False
                      and exited.get('exit_without_save_input_accepted') is True
                      and exited.get('final_process_alive') is False
                      and isinstance(exited.get('before_all_saves'), dict)
                      and bool(exited['before_all_saves'])
                      and exited['before_all_saves'] == exited.get('after_all_saves'))
    if (not (legacy_unsaved or normal_unsaved)
            or exited.get('ok') is not True or exited.get('normal_exit_verified') is not True
            or exited.get('game_exit_verified') is not True
            or exited.get('save_files_unchanged_verified') is not True
            or identity.get('test_token') != journal['token']
            or Path(identity.get('profile', '')).resolve() != profile
            or backup.get('schema') != 1 or backup.get('token') != journal['token']):
        raise ValueError('Recovery needs this disposable profile and a verified normal unsaved exit.')
    expected_store = reusable_profile.writable(state.parent / 'test-data-recovery')
    if backup_path.parent != expected_store:
        raise ValueError('Use this journal\'s content-addressed test-data backup.')
    candidates = [row for row in backup.get('files', []) if isinstance(row, dict)
                  and row.get('path') in {'saves/' + name for name in AUTOSAVES}]
    if len(candidates) != 6 or len({row['path'] for row in candidates}) != 6:
        raise ValueError('Backup must contain each of the six exact existing autosave files once.')
    before = all_save_files(profile)
    if normal_unsaved and before != exited['after_all_saves']:
        raise ValueError('Disposable save/backup inventory changed after normal unsaved exit.')
    if not AUTOSAVES <= set(before):
        raise ValueError('All six existing autosaves are required; no new save is created.')
    for name, row in exited.get('after_saves', {}).items():
        if name in AUTOSAVES or before.get(name) != row:
            raise ValueError('A normal save changed after unsaved exit; recovery refused.')
    if not exited.get('after_saves'):
        raise ValueError('Unsaved exit lacks its exact unchanged normal save inventory.')
    rows = []
    for row in candidates:
        digest = row.get('sha256')
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in '0123456789abcdef' for c in digest)
                or type(row.get('bytes')) is not int or row['bytes'] <= 0):
            raise ValueError('Autosave backup metadata is invalid.')
        source = reusable_profile.writable(expected_store / (digest + '.bin'))
        target = reusable_profile.writable(profile / row['path'])
        if source.stat().st_size != row['bytes'] or sha256(source) != digest:
            raise ValueError('Autosave backup bytes differ; no replacement authorized.')
        current = before[target.name]['sha256']
        preserved = reusable_profile.writable(expected_store / (current + '.bin'))
        if not preserved.exists():
            with target.open('rb') as incoming, preserved.open('xb') as saved:
                shutil.copyfileobj(incoming, saved)
        if sha256(preserved) != current or sha256(target) != current:
            raise ValueError('Failed autosave preservation changed; no replacement authorized.')
        rows.append({'file': target.name, 'before_sha256': current, 'restored_sha256': digest,
                     'preserved': str(preserved), 'replacement_submitted': False})
    receipt = {'schema': 1, 'operation': 'recover-disposable-autosaves-only', 'ok': False,
               'token': journal['token'], 'generation': journal['generation'],
               'backup_sha256': backup_sha256, 'normal_exit_sha256': exit_sha256,
               'before': before, 'files': rows, 'normal_slots_written': False,
               'protected_original_written': False, 'automatic_replay_allowed': False}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, sort_keys=True)
    for row in rows:
        guard()
        target = reusable_profile.writable(profile / 'saves' / row['file'])
        if sha256(target) != row['before_sha256']:
            raise ValueError('Autosave changed after preservation; do not replay this receipt.')
        stage = reusable_profile.writable(expected_store / (row['restored_sha256'] + '.restore-stage'))
        with (expected_store / (row['restored_sha256'] + '.bin')).open('rb') as incoming, stage.open('xb') as prepared:
            shutil.copyfileobj(incoming, prepared)
            prepared.flush()
            os.fsync(prepared.fileno())
        if sha256(stage) != row['restored_sha256']:
            raise ValueError('Autosave staging hash differs; retained receipt must be inspected.')
        row['replacement_submitted'] = True
        write_json(output, receipt)
        os.replace(str(stage), str(target))
        row['replacement_verified'] = sha256(target) == row['restored_sha256']
        write_json(output, receipt)
        if not row['replacement_verified']:
            raise ValueError('Autosave replacement verification failed; no further replacement.')
    after = all_save_files(profile)
    normal_before = {k: v for k, v in before.items() if k not in AUTOSAVES}
    normal_after = {k: v for k, v in after.items() if k not in AUTOSAVES}
    receipt.update(after=after, normal_slots_unchanged=normal_before == normal_after)
    receipt['ok'] = receipt['normal_slots_unchanged'] and all(row.get('replacement_verified') for row in rows)
    write_json(output, receipt)
    return {k: receipt[k] for k in ('ok', 'operation', 'normal_slots_unchanged', 'protected_original_written')} | {
        'proof': str(output), 'proof_sha256': sha256(output), 'autosaves_restored': len(rows)}
