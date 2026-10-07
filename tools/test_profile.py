"""Reversible, closed-game-only isolation of the complete Sims 4 user profile.

The original directory is renamed, never emptied. Test saves remain in a separate
directory after restoration. A durable external journal records interrupted swaps.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import uuid
from source_manifest import sha256, write_json


MARKER = '.apex-disposable-profile.json'
LOCK = '.apex-profile-session.lock'


def session_lock(profile, state, token):
    path = profile.parent / LOCK
    payload = json.dumps({'token': token, 'state': str(state)}).encode('utf-8')
    # Reservation is atomic across concurrent CLI processes; retain it after a crash.
    with path.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def verify_lock(profile, state, token, already_restored=False):
    path = unlinked(profile.parent / LOCK)
    if already_restored and not path.exists():
        return path
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('token') != token or unlinked(data.get('state', '')) != state:
        raise RuntimeError('Another profile session owns the lock; refusing all renames.')
    return path


def require_closed():
    if os.name != 'nt':
        raise RuntimeError('Live profile switching is supported only on Windows.')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                             "@(Get-Process -ErrorAction Stop | Where-Object { $_.ProcessName -in @('TS4_x64','TS4_DX9_x64','TS4','TS4_Launcher_x64') }).Count"],
                            capture_output=True, text=True, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.stdout.strip() != '0':
        raise RuntimeError('Close The Sims 4 normally before switching profiles; no process will be killed.')


def unlinked(path):
    path = Path(path).absolute()
    for ancestor in [path] + list(path.parents):
        if ancestor.exists():
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Profile paths must not contain symlinks/junctions: ' + str(ancestor))
    return path.resolve()


def inventory(profile):
    rows = []
    for directory, subdirs, files in os.walk(str(profile), followlinks=False):
        for name in sorted(subdirs + files):
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Refusing a linked/reparse profile entry: ' + str(path))
            if not path.is_file():
                continue
            relative = path.relative_to(profile).as_posix()
            row = {'path': relative, 'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns}
            if relative.split('/')[0].lower() == 'saves':
                row['sha256'] = sha256(path)
            rows.append(row)
    return sorted(rows, key=lambda row: row['path'])


def validate_artifacts(paths):
    rows = []
    names = set()
    for item in paths:
        path = unlinked(item)
        if not path.is_file() or path.suffix.lower() not in ('.package', '.ts4script'):
            raise ValueError('Only explicit package/script artifacts may enter the test Mods directory.')
        if path.name.lower() in names:
            raise ValueError('Artifact filename collision: ' + path.name)
        names.add(path.name.lower())
        with path.open('rb') as stream:
            if stream.read(4) not in (b'DBPF', b'PK\x03\x04'):
                raise ValueError('Invalid artifact signature: ' + path.name)
        rows.append({'source': str(path), 'name': path.name, 'sha256': sha256(path)})
    if not rows:
        raise ValueError('Supply the exact artifacts required for this test.')
    return rows


def activate(profile, state, artifacts, guard=require_closed):
    guard()
    profile = unlinked(profile)
    state = unlinked(state)
    if profile.name != 'The Sims 4' or not profile.is_dir() or (profile / MARKER).exists():
        raise ValueError('Expected an existing original The Sims 4 profile directory.')
    if profile == state or profile in state.parents or state.exists():
        raise ValueError('The new session journal must be outside the original profile and must not exist.')
    token = uuid.uuid4().hex
    original = profile.with_name('The Sims 4.ApexOriginal.' + token)
    staging = profile.with_name('The Sims 4.ApexStaging.' + token)
    test_archive = profile.with_name('The Sims 4.ApexTest.' + token)
    for target in (original, staging, test_archive):
        if target.exists() or unlinked(target).parent != profile.parent:
            raise ValueError('Unsafe or occupied sibling path: ' + str(target))
    session_lock(profile, state, token)
    journal = {'schema': 1, 'token': token, 'profile': str(profile),
               'original': str(original), 'staging': str(staging), 'test_archive': str(test_archive),
               'phase': 'preparing', 'artifacts': validate_artifacts(artifacts),
               'original_inventory': inventory(profile)}
    write_json(state, journal)
    staging.mkdir()
    (staging / 'Mods' / 'ApexTest').mkdir(parents=True)
    (staging / 'saves').mkdir()
    (staging / 'Tray').mkdir()
    write_json(staging / MARKER, {'token': token, 'disposable': True})
    (staging / 'Mods' / 'Resource.cfg').write_text(
        'Priority 500\nPackedFile *.package\nPackedFile */*.package\n', encoding='ascii')
    options = profile / 'Options.ini'
    if options.is_file():
        # Only configuration is copied. No live saves/Tray/persistent mod data.
        shutil.copy2(str(options), str(staging / 'Options.ini'))
    for row in journal['artifacts']:
        destination = staging / 'Mods' / 'ApexTest' / row['name']
        shutil.copy2(row['source'], str(destination))
        if sha256(destination) != row['sha256']:
            raise RuntimeError('Staged artifact hash changed; original profile remains intact.')
    guard()
    if inventory(profile) != journal['original_inventory']:
        raise RuntimeError('Original profile changed during staging; refusing the swap.')
    journal['phase'] = 'ready'
    write_json(state, journal)
    # Each rename is same-volume and refuses an existing target. Record intent first.
    os.rename(str(profile), str(original))
    journal['phase'] = 'original_parked'
    write_json(state, journal)
    os.rename(str(staging), str(profile))
    journal['phase'] = 'active'
    write_json(state, journal)
    return {'ok': True, 'phase': 'active', 'journal': str(state), 'original': str(original),
            'test_profile': str(profile), 'live_saves_exposed': False}


def restore(state, guard=require_closed):
    guard()
    state = unlinked(state)
    journal = json.loads(state.read_text(encoding='utf-8'))
    if journal.get('schema') != 1 or journal.get('phase') not in ('preparing', 'ready', 'original_parked', 'active', 'test_parked', 'restored'):
        raise ValueError('Journal is not in a recoverable profile-swap phase.')
    token = journal['token']
    if len(token) != 32 or any(char not in '0123456789abcdef' for char in token):
        raise ValueError('Invalid session identity.')
    profile = unlinked(journal['profile'])
    if profile.name != 'The Sims 4' or profile == state or profile in state.parents:
        raise ValueError('Unsafe journal profile/state path.')
    lock = verify_lock(profile, state, token, already_restored=journal['phase'] == 'restored')
    expected = {'original': 'The Sims 4.ApexOriginal.', 'staging': 'The Sims 4.ApexStaging.', 'test_archive': 'The Sims 4.ApexTest.'}
    paths = {}
    for field, prefix in expected.items():
        path = unlinked(journal[field])
        if path.parent != profile.parent or path.name != prefix + token:
            raise ValueError('Journal path is outside the verified sibling locations.')
        paths[field] = path
    original, staging, test_archive = (paths[key] for key in ('original', 'staging', 'test_archive'))
    if not original.exists():
        # Either swap never began or original rename-back succeeded before journal write.
        if profile.is_dir() and not (profile / MARKER).exists() and inventory(profile) == journal['original_inventory']:
            journal['phase'] = 'restored'
            write_json(state, journal)
            if lock.exists():
                lock.unlink()
            return {'ok': True, 'phase': 'restored', 'profile': str(profile), 'test_archive': str(test_archive)}
        raise RuntimeError('Original profile is not at either verified location; refusing all writes.')
    if inventory(original) != journal['original_inventory']:
        raise RuntimeError('Preserved original profile changed; investigate before any restore.')
    if profile.exists():
        marker = profile / MARKER
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('token') != token:
            raise RuntimeError('Active folder is not this session\'s test profile; refusing replacement.')
        if test_archive.exists():
            raise RuntimeError('Test archive already exists; refusing overwrite.')
        guard()
        os.rename(str(profile), str(test_archive))
        journal['phase'] = 'test_parked'
        write_json(state, journal)
    guard()
    os.rename(str(original), str(profile))
    journal['phase'] = 'restored'
    write_json(state, journal)
    if inventory(profile) != journal['original_inventory']:
        raise RuntimeError('Restore verification failed; inspect both preserved locations.')
    lock.unlink()
    return {'ok': True, 'phase': 'restored', 'profile': str(profile),
            'test_archive': str(test_archive), 'staging_retained': staging.exists()}


def status(state, verify_original=False):
    """Read-only launch preflight; never infer isolation from a folder name alone."""
    state = unlinked(state)
    journal = json.loads(state.read_text(encoding='utf-8'))
    if journal.get('schema') != 1:
        raise ValueError('Unsupported profile journal.')
    token = journal.get('token', '')
    if len(token) != 32 or any(char not in '0123456789abcdef' for char in token):
        raise ValueError('Invalid session identity.')
    profile = unlinked(journal['profile'])
    original = unlinked(journal['original'])
    if profile.name != 'The Sims 4' or profile == state or profile in state.parents:
        raise ValueError('Unsafe journal profile/state path.')
    if original.parent != profile.parent or original.name != 'The Sims 4.ApexOriginal.' + token:
        raise ValueError('Invalid preserved original location.')
    active = journal.get('phase') == 'active'
    if active:
        verify_lock(profile, state, token)
    marker = profile / MARKER
    marked = marker.is_file() and json.loads(marker.read_text(encoding='utf-8')).get('token') == token
    rows, unexpected = [], []
    if active and marked:
        expected = {('ApexTest/' + row['name']).casefold(): row for row in journal['artifacts']}
        mods = profile / 'Mods'
        for directory, subdirs, files in os.walk(str(mods), followlinks=False):
            for name in subdirs + files:
                unlinked(Path(directory) / name)
            for name in files:
                path = Path(directory) / name
                relative = path.relative_to(mods).as_posix()
                if relative.casefold() == 'resource.cfg':
                    continue
                row = expected.pop(relative.casefold(), None)
                if row is None:
                    unexpected.append(relative)
                else:
                    digest = sha256(path)
                    rows.append({'path': relative, 'sha256': digest, 'matches': digest == row['sha256']})
        unexpected.extend('missing:' + key for key in sorted(expected))
    isolated = active and marked and original.is_dir() and not unexpected and len(rows) == len(journal['artifacts']) and all(row['matches'] for row in rows)
    original_matches = None
    if verify_original:
        preserved = original if original.exists() else profile
        original_matches = inventory(preserved) == journal['original_inventory']
        if original_matches is False:
            isolated = False
    return {'ok': isolated if active else journal.get('phase') == 'restored',
            'phase': journal.get('phase'), 'profile': str(profile), 'original': str(original),
            'ready_to_launch': isolated, 'original_inventory_verified_now': original_matches,
            'original_verification_scope': 'all file paths/sizes/mtimes; SHA-256 of every save file',
            'artifacts': sorted(rows, key=lambda row: row['path']), 'unexpected_mod_files': sorted(unexpected),
            'test_save_files': sum(1 for path in (profile / 'saves').rglob('*') if path.is_file()) if isolated else None,
            'test_tray_files': sum(1 for path in (profile / 'Tray').rglob('*') if path.is_file()) if isolated else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    stage = commands.add_parser('activate')
    stage.add_argument('--profile', required=True, type=Path)
    stage.add_argument('--state', required=True, type=Path)
    stage.add_argument('--artifact', required=True, type=Path, action='append')
    revert = commands.add_parser('restore')
    revert.add_argument('--state', required=True, type=Path)
    inspect = commands.add_parser('status')
    inspect.add_argument('--state', required=True, type=Path)
    inspect.add_argument('--verify-original', action='store_true')
    args = parser.parse_args()
    if args.command == 'activate':
        result = activate(args.profile, args.state, args.artifact)
    elif args.command == 'restore':
        result = restore(args.state)
    else:
        result = status(args.state, args.verify_original)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
