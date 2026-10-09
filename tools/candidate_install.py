"""Verify and install a complete candidate in the one marked test profile."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile
from source_manifest import sha256, write_json
import reusable_profile as profiles
import test_profile


def read_bundle(bundle):
    bundle = test_profile.unlinked(bundle)
    if bundle.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Candidate ZIP exceeds the bounded limit.')
    raw = bundle.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > 256 or sum(row.file_size for row in infos) > 64 * 1024 * 1024:
            raise ValueError('Candidate ZIP expansion exceeds the bounded limit.')
        names = [row.filename for row in infos]
        if len(set(name.casefold() for name in names)) != len(names):
            raise ValueError('Duplicate candidate ZIP members.')
        for row in infos:
            path = PurePosixPath(row.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in row.filename or ':' in row.filename or row.is_dir() or stat.S_ISLNK(row.external_attr >> 16):
                raise ValueError('Unsafe candidate ZIP member.')
        manifest_name = 'Manifests/candidate-manifest.json'
        if manifest_name not in names or archive.getinfo(manifest_name).file_size > 1024 * 1024:
            raise ValueError('Missing bounded candidate manifest.')
        manifest = json.loads(archive.read(manifest_name))
        rows = manifest.get('files', [])
        if manifest.get('schema') != 1 or not rows or len({row['file'] for row in rows}) != len(rows):
            raise ValueError('Invalid candidate manifest.')
        if set(names) != {manifest_name} | {row['file'] for row in rows}:
            raise ValueError('Candidate inventory does not match its manifest.')
        payloads = {}
        for row in rows:
            payload = archive.read(row['file'])
            if len(payload) != row['bytes'] or hashlib.sha256(payload).hexdigest() != row['sha256']:
                raise ValueError('Candidate member hash mismatch: ' + row['file'])
            payloads[row['file']] = payload
    prefix = 'Mods/Apex/'
    required = {prefix + name for name in ('ApexOccultHybrid.package', 'ApexCASUnlocks.package',
                'ApexOccultHybrid.ts4script', 'Native/ApexOverlay.dll', 'Native/ApexOverlay.ini', 'Native/overlay-manifest.json')}
    if not required.issubset(payloads):
        raise ValueError('Candidate lacks the complete standalone package/script/F11 set.')
    native = json.loads(payloads[prefix + 'Native/overlay-manifest.json'])
    script = payloads[prefix + 'ApexOccultHybrid.ts4script']
    dll = payloads[prefix + 'Native/ApexOverlay.dll']
    if native.get('schema') != 1 or native.get('protocol') != 1 or native.get('file') != 'ApexOverlay.dll' or native.get('sha256') != hashlib.sha256(dll).hexdigest() or native.get('verified_script_sha256') != hashlib.sha256(script).hexdigest():
        raise ValueError('F11 sidecar and script identities do not match.')
    if dll[:2] != b'MZ':
        raise ValueError('Native sidecar is not a PE image.')
    with zipfile.ZipFile(io.BytesIO(script)) as archive:
        if archive.testzip() is not None or archive.read('td1_occult_hybrid_apex.pyc')[:4] != b'\x42\x0d\x0d\x0a':
            raise ValueError('Candidate script lacks valid Sims Python 3.7 bytecode.')
    for name in ('ApexOccultHybrid.package', 'ApexCASUnlocks.package'):
        if payloads[prefix + name][:4] != b'DBPF':
            raise ValueError('Candidate package is not DBPF.')
    return bundle, hashlib.sha256(raw).hexdigest(), manifest, payloads


@profiles.serialized
def install(state, bundle, experimental_ui=False, optional=False, guard=test_profile.require_closed):
    guard()
    state, data, profile, _original = profiles.load(state)
    if not profiles.status(state)['ready_to_launch']:
        raise ValueError('The marked test profile contains unknown/changed mods.')
    bundle, digest, manifest, payloads = read_bundle(bundle)
    # Exact separately installed test recipes survive a candidate replacement.
    # Their removal remains an explicit add-on operation.
    from test_cc_addons import ADDON as CC_ADDON, ASSETS as CC_ASSETS
    addons = []
    for row in data['artifacts']:
        if row.get('test_addon') == 'mccc-2026.5.0':
            addons.append(row)
        elif row.get('test_addon') == CC_ADDON:
            if row.get('name') not in CC_ASSETS or row.get('sha256') != CC_ASSETS[row['name']]:
                raise ValueError('The retained CC add-on recipe differs; no candidate replacement.')
            addons.append(row)
    selected = {name[5:]: raw for name, raw in payloads.items() if name.startswith('Mods/Apex/')}
    if experimental_ui and 'Mods/Apex/ApexCASBridge.package' in payloads:
        raise ValueError('CAS Bridge and the old Color Studio replace the same CAS UI resource; install only the version-matched bridge.')
    if experimental_ui:
        selected['Apex/ApexColorStudio.package'] = payloads['ExperimentalUI/ApexColorStudio.package']
    if optional:
        for name, raw in payloads.items():
            if name.startswith('Optional/') and name.endswith('.package'):
                selected['Apex/' + Path(name).name] = raw
    recovery = profiles.writable(state.parent / 'artifact-recovery')
    recovery.mkdir(exist_ok=True)
    rows = []
    for relative, payload in sorted(selected.items()):
        row = {'name': Path(relative).name, 'relative': relative, 'sha256': hashlib.sha256(payload).hexdigest(),
               'source': str(bundle), 'bytes': len(payload)}
        profiles.artifact_relative(row)
        stage = profiles.recovery_path(state, row, True)
        if not stage.exists():
            with stage.open('xb') as stream:
                stream.write(payload)
        if sha256(stage) != row['sha256']:
            raise ValueError('Candidate recovery staging mismatch.')
        # install_rows consumes immutable staged blobs; no unbounded extraction.
        row['source'] = str(stage)
        rows.append(row)
    # Test add-ons have their own explicit removal command. A candidate update
    # must retain the exact already-verified MCCC recipe and its user settings.
    rows.extend(addons)
    receipt = {'sha256': digest, 'source': str(bundle), 'target_game': manifest['target_game'],
               'experimental_ui': experimental_ui, 'optional': optional}
    return profiles.install_rows(state, rows, guard, bundle=receipt)


@profiles.serialized
def backup(state, guard=test_profile.require_closed):
    guard()
    state, data, profile, original = profiles.load(state)
    destination = profiles.writable(state.parent / 'test-data-recovery')
    destination.mkdir(exist_ok=True)
    manifest = {'schema': 1, 'token': data['token'], 'files': [], 'original_saves': []}
    prior_path = destination / 'latest.json'
    prior = json.loads(prior_path.read_text(encoding='utf-8')) if prior_path.exists() else None
    if prior is not None:
        prior_digest = sha256(prior_path)
        archived = destination / ('manifest-' + prior_digest + '.json')
        if not archived.exists():
            archived.write_bytes(prior_path.read_bytes())
        if sha256(archived) != prior_digest:
            raise ValueError('Prior recovery manifest was not preserved.')
    for directory in ('saves', 'Tray', 'TD1_OccultHybridApexData', 'TD1_Occult_Hybrid_Apex'):
        root = profiles.writable(profile / directory)
        for path in sorted(root.rglob('*')):
            profiles.writable(path)
            if not path.is_file():
                continue
            digest = sha256(path)
            target = profiles.writable(destination / (digest + '.bin'))
            if not target.exists():
                with path.open('rb') as source, target.open('xb') as output:
                    import shutil
                    shutil.copyfileobj(source, output)
            if sha256(target) != digest or sha256(path) != digest:
                raise ValueError('Test save/Tray recovery verification failed.')
            manifest['files'].append({'path': path.relative_to(profile).as_posix(), 'sha256': digest, 'bytes': path.stat().st_size})
    # Record only save identities of the protected original, entirely read-only.
    for path in sorted((original / 'saves').rglob('*')):
        test_profile.unlinked(path)
        if path.is_file():
            manifest['original_saves'].append({'path': path.relative_to(original).as_posix(), 'sha256': sha256(path)})
    unchanged = prior is not None and prior['original_saves'] == manifest['original_saves']
    if prior is not None and not unchanged:
        raise ValueError('Protected original save identities changed since the prior backup; inspect before testing.')
    write_json(destination / 'latest.json', manifest)
    return {'ok': True, 'recovery_manifest': str(destination / 'latest.json'),
            'test_files': len(manifest['files']), 'original_written': False,
            'original_saves_unchanged_since_prior_backup': unchanged}
