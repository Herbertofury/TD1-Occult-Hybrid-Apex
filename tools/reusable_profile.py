"""One reusable Apex test profile; the owner's protected original is read-only.

This mode never renames/restores an original profile. Only token-marked test
artifacts may be changed. Retired disposable profiles are consolidated into a
content-addressed recovery store before their verified duplicate folders go away.
"""
import json
import os
from pathlib import Path
import shutil
import uuid
from contextlib import contextmanager
from source_manifest import sha256, write_json
import test_profile as legacy

PROTECTED_NAME = legacy.PROTECTED_NAME


@contextmanager
def mutation_lock(state):
    state = writable(state)
    if any(part.casefold() == 'the sims 4' for part in state.parts):
        raise ValueError('Mutation journal and lock must remain outside the game profile.')
    lock = writable(state.with_name(state.name + '.operation-lock'))
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('xb') as stream:
        stream.write(json.dumps({'state': str(state), 'pid': os.getpid()}).encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
    try:
        yield
    finally:
        lock.unlink()


def serialized(function):
    def wrapped(*args, **kwargs):
        state = kwargs.get('state')
        if state is None:
            state = args[2] if function.__name__ == 'adopt' else args[0]
        with mutation_lock(state):
            return function(*args, **kwargs)
    return wrapped


def writable(path):
    path = legacy.unlinked(path)
    if any(part.casefold() == PROTECTED_NAME.casefold() for part in path.parts):
        raise ValueError('The protected original is strictly read-only; no writes or renames are allowed.')
    return path


def load(state):
    state = writable(state)
    data = json.loads(state.read_text(encoding='utf-8'))
    if data.get('schema') != 2 or data.get('mode') != 'reusable-test-only':
        raise ValueError('Expected reusable-test-only journal.')
    token = data.get('token', '')
    if len(token) != 32 or any(char not in '0123456789abcdef' for char in token):
        raise ValueError('Invalid disposable profile identity.')
    profile = writable(data['profile'])
    original = legacy.unlinked(data['protected_original'])
    if profile.name != 'The Sims 4' or original.name != PROTECTED_NAME or original.parent != profile.parent:
        raise ValueError('Reusable test/original paths do not match the owner\'s protected sibling layout.')
    if state == profile or profile in state.parents or original == state or original in state.parents:
        raise ValueError('Journal must stay outside both profiles.')
    if not original.is_dir():
        raise ValueError('Protected original location changed; inspect before test actions.')
    marker = profile / legacy.MARKER
    if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('token') != data.get('token'):
        raise ValueError('Active folder is not this session\'s disposable test profile.')
    for rows in (data['artifacts'], data.get('pending_artifacts', [])):
        names = set()
        for row in rows:
            name, digest = row['name'], row['sha256']
            if Path(name).name != name or '/' in name or '\\' in name or Path(name).suffix.lower() not in ('.package', '.ts4script'):
                raise ValueError('Journal artifact must have a plain package/script filename.')
            if name.casefold() in names or len(digest) != 64 or any(char not in '0123456789abcdef' for char in digest):
                raise ValueError('Invalid or duplicate journal artifact identity.')
            names.add(name.casefold())
    return state, data, profile, original


def status(state, verify_original=False):
    state, data, profile, original = load(state)
    expected = {('ApexTest/' + row['name']).casefold(): row for row in data['artifacts']}
    artifacts, unexpected = [], []
    for directory, subdirs, files in os.walk(str(profile / 'Mods'), followlinks=False):
        for name in subdirs + files:
            writable(Path(directory) / name)
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(profile / 'Mods').as_posix()
            if relative.casefold() == 'resource.cfg':
                continue
            expected_row = expected.pop(relative.casefold(), None)
            if expected_row is None:
                unexpected.append(relative)
            else:
                digest = sha256(path)
                artifacts.append({'path': relative, 'sha256': digest, 'matches': digest == expected_row['sha256']})
    unexpected.extend('missing:' + name for name in expected)
    ready = data.get('phase') == 'active' and not unexpected and len(artifacts) == len(data['artifacts']) and all(row['matches'] for row in artifacts)
    original_matches = None
    if verify_original:
        baseline = json.loads(Path(data['previous_state']).read_text(encoding='utf-8'))['original_inventory']
        original_matches = legacy.inventory(original) == baseline
        if not original_matches:
            ready = False
    return {'ok': ready, 'phase': data['phase'], 'mode': data['mode'], 'profile': str(profile),
            'original': str(original), 'original_policy': 'read-only; owner alone renames/restores',
            'ready_to_launch': ready, 'original_inventory_verified_now': original_matches,
            'artifacts': sorted(artifacts, key=lambda row: row['path']), 'unexpected_mod_files': sorted(unexpected),
            'test_save_files': sum(1 for path in (profile / 'saves').rglob('*') if path.is_file()),
            'test_tray_files': sum(1 for path in (profile / 'Tray').rglob('*') if path.is_file())}


@serialized
def adopt(previous_state, profile, state, protected_original, artifacts=None, guard=legacy.require_closed):
    guard()
    profile, state = writable(profile), writable(state)
    original = legacy.unlinked(protected_original)
    empty_profile = profile.is_dir() and not any(profile.iterdir())
    if profile.name != 'The Sims 4' or (profile.exists() and not empty_profile) or state.exists():
        raise ValueError('Adoption requires an unoccupied game profile path and a new external journal.')
    if original.name != PROTECTED_NAME or original.parent != profile.parent or not original.is_dir():
        raise ValueError('Expected the owner\'s protected original sibling, which will remain read-only.')
    if profile in state.parents or original in state.parents:
        raise ValueError('Journal must be outside both profiles.')
    retained = legacy.test_seed(previous_state, profile)
    writable(retained)
    previous = json.loads(legacy.unlinked(previous_state).read_text(encoding='utf-8'))
    data = {'schema': 2, 'mode': 'reusable-test-only', 'phase': 'adopting',
            'profile': str(profile), 'protected_original': str(original),
            'token': previous['token'], 'previous_state': str(legacy.unlinked(previous_state)),
            'artifacts': previous['artifacts'], 'retained_source': str(retained), 'generation': 0}
    before = legacy.inventory(retained)
    write_json(state, data)
    guard()
    if empty_profile:
        profile.rmdir()  # Nonrecursive: refuses if EA/the owner added any file meanwhile.
    os.rename(str(retained), str(profile))
    if legacy.inventory(profile) != before:
        raise RuntimeError('Test-profile rename verification failed; both original and test data are preserved.')
    data['phase'] = 'active'
    write_json(state, data)
    if artifacts:
        _install(state, artifacts, guard)
    return status(state)


@serialized
def install(state, artifacts, guard=legacy.require_closed):
    return _install(state, artifacts, guard)


def _install(state, artifacts, guard):
    guard()
    state, data, profile, _original = load(state)
    if not status(state)['ready_to_launch']:
        raise ValueError('Unknown/changed test mods prevent replacement; no files were changed.')
    incoming = legacy.validate_artifacts(artifacts)
    old = {row['name'].casefold(): row for row in data['artifacts']}
    destination = writable(profile / 'Mods' / 'ApexTest')
    recovery = writable(state.parent / 'artifact-recovery')
    recovery.mkdir(exist_ok=True)
    for row in old.values():
        path = writable(destination / row['name'])
        backup = recovery / (row['sha256'] + path.suffix)
        if not backup.exists():
            shutil.copy2(str(path), str(backup))
        if sha256(backup) != row['sha256']:
            raise RuntimeError('Prior test artifact recovery verification failed.')
    pending = []
    for row in incoming:
        stage = writable(recovery / (row['sha256'] + '.incoming' + Path(row['name']).suffix))
        if not stage.exists():
            with stage.open('xb') as output, Path(row['source']).open('rb') as source:
                shutil.copyfileobj(source, output)
        if sha256(stage) != row['sha256']:
            raise RuntimeError('Staged test artifact changed; refusing replacement.')
        pending.append((stage, row))
    guard()
    data['phase'] = 'installing'
    data['pending_artifacts'] = incoming
    write_json(state, data)
    return finish_install(state, data, profile, pending, guard)


def finish_install(state, data, profile, pending, guard):
    destination = writable(profile / 'Mods' / 'ApexTest')
    old = {row['name'].casefold(): row for row in data['artifacts']}
    incoming = data['pending_artifacts']
    for stage, row in pending:
        target = writable(destination / row['name'])
        if target.exists():
            prior = old.get(row['name'].casefold())
            allowed = {row['sha256']}
            if prior is not None:
                allowed.add(prior['sha256'])
            if sha256(target) not in allowed:
                raise RuntimeError('Test artifact changed after preflight; refusing replacement.')
            if sha256(target) == row['sha256']:
                continue
        # Copying the verified recovery blob leaves it available after an interrupted install.
        temporary = writable(destination / ('.apex-stage-' + data['token']))
        if temporary.exists():
            raise RuntimeError('Interrupted temporary artifact requires explicit recovery.')
        with temporary.open('xb') as output, stage.open('rb') as source:
            shutil.copyfileobj(source, output)
        if sha256(temporary) != row['sha256']:
            raise RuntimeError('Temporary artifact verification failed.')
        guard()
        os.replace(str(temporary), str(target))
    desired = {row['name'].casefold() for row in incoming}
    for name, row in old.items():
        if name not in desired:
            path = writable(destination / row['name'])
            if not path.exists():
                continue
            if sha256(path) != row['sha256']:
                raise RuntimeError('Retired test artifact changed; refusing removal.')
            guard()
            path.unlink()  # Exact tool-owned test artifact is verified in recovery first.
    data['artifacts'] = incoming
    data.pop('pending_artifacts', None)
    data['generation'] += 1
    data['phase'] = 'active'
    write_json(state, data)
    return status(state)


@serialized
def recover(state, guard=legacy.require_closed):
    guard()
    state, data, profile, _original = load(state)
    if data['phase'] != 'installing' or not data.get('pending_artifacts'):
        raise ValueError('No interrupted artifact installation to recover.')
    old = {row['name'].casefold(): row['sha256'] for row in data['artifacts']}
    desired = {row['name'].casefold(): row['sha256'] for row in data['pending_artifacts']}
    mods = profile / 'Mods'
    for path in mods.rglob('*'):
        writable(path)
        if not path.is_file() or path.relative_to(mods).as_posix().casefold() == 'resource.cfg':
            continue
        if path == mods / 'ApexTest' / ('.apex-stage-' + data['token']):
            continue
        if path.parent != mods / 'ApexTest' or sha256(path) not in {old.get(path.name.casefold()), desired.get(path.name.casefold())}:
            raise ValueError('Unknown test mods prevent recovery; no files changed.')
    pending = []
    for row in data['pending_artifacts']:
        stage = writable(state.parent / 'artifact-recovery' / (row['sha256'] + '.incoming' + Path(row['name']).suffix))
        if sha256(stage) != row['sha256']:
            raise RuntimeError('Recovery artifact verification failed.')
        pending.append((stage, row))
    temporary = writable(mods / 'ApexTest' / ('.apex-stage-' + data['token']))
    if temporary.exists():
        # Exact journal-owned scratch file; complete incoming contents remain verified above.
        temporary.unlink()
    return finish_install(state, data, profile, pending, guard)


@serialized
def preserve_settings(state, guard=legacy.require_closed):
    guard()
    state, data, profile, original = load(state)
    if not status(state)['ready_to_launch']:
        raise ValueError('Settings copy requires a verified reusable test profile.')
    source = legacy.unlinked(original / 'UserSetting.ini')
    if not source.is_file() or source.stat().st_size > 1024 * 1024:
        raise ValueError('Expected a bounded original UserSetting.ini to copy read-only.')
    source_before = (source.stat().st_size, source.stat().st_mtime_ns, sha256(source))
    target = writable(profile / 'UserSetting.ini')
    recovery = writable(state.parent / 'artifact-recovery')
    recovery.mkdir(exist_ok=True)
    if target.exists():
        digest = sha256(target)
        backup = writable(recovery / (digest + '.UserSetting.ini'))
        if not backup.exists():
            shutil.copy2(str(target), str(backup))
        if sha256(backup) != digest:
            raise RuntimeError('Test settings recovery verification failed.')
    temporary = writable(profile / ('.apex-settings-' + data['token']))
    with temporary.open('xb') as output, source.open('rb') as input_stream:
        shutil.copyfileobj(input_stream, output)
    if sha256(temporary) != source_before[2] or source_before != (source.stat().st_size, source.stat().st_mtime_ns, sha256(source)):
        raise RuntimeError('Read-only settings source changed; test settings were not replaced.')
    guard()
    os.replace(str(temporary), str(target))
    data['settings_copy'] = {'source': str(source), 'sha256': source_before[2],
                             'scope': 'Exact UserSetting.ini copy; existing pack/welcome acknowledgements preserved without inventing flags.'}
    write_json(state, data)
    return {'ok': True, 'settings_copy': data['settings_copy'], 'original_written': False,
            'announcement_ui_verified': False}


@serialized
def consolidate(state, previous_states, guard=legacy.require_closed):
    guard()
    state, data, profile, _original = load(state)
    recovery = writable(state.parent / 'test-profile-recovery')
    recovery.mkdir(exist_ok=True)
    manifest_path = recovery / 'files.json'
    recovered = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'schema': 1, 'files': []}
    removed = []
    for previous_state in previous_states:
        retained = legacy.test_seed(previous_state, profile)
        writable(retained)
        before = legacy.inventory(retained)
        for row in before:
            path = legacy.unlinked(retained / row['path'])
            digest = sha256(path)
            backup = writable(recovery / (digest + '.bin'))
            if not backup.exists():
                with backup.open('xb') as output, path.open('rb') as source:
                    shutil.copyfileobj(source, output)
            if sha256(backup) != digest:
                raise RuntimeError('Disposable test recovery verification failed; source folder preserved.')
            recovered['files'].append({'test_profile': retained.name, 'path': row['path'],
                                       'sha256': digest, 'bytes': row['bytes'], 'mtime_ns': row['mtime_ns']})
        write_json(manifest_path, recovered)
        guard()
        if legacy.inventory(retained) != before:
            raise RuntimeError('Disposable profile changed during consolidation; refusing removal.')
        # Paths, token marker, restored prior journal, every file hash and sibling
        # boundary are verified above. The protected original can never match.
        shutil.rmtree(str(retained))
        removed.append(retained.name)
    return {'ok': True, 'test_profile': str(profile), 'consolidated_test_folders': removed,
            'recovery_manifest': str(manifest_path), 'original_policy': 'read-only; never renamed or modified'}
