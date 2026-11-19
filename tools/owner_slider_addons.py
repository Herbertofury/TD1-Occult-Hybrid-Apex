"""Copy the owner's slider/preset packages into the existing disposable profile.

No original writes, renames or game input. Exact package hashes are retained in
the profile journal; a candidate replacement must retain these test inputs.
"""
from pathlib import Path
import os
import reusable_profile as profiles
import test_profile
from source_manifest import sha256

ADDON = 'owner-sliders-presets-v1'
MAX_FILES = 10000
MAX_BYTES = 4 * 1024 ** 3


def preparation(state):
    state, data, profile, original = profiles.load(state)
    if not profiles.status(state)['ready_to_launch']:
        raise ValueError('Existing disposable artifacts must verify before adding sliders.')
    source = test_profile.unlinked(original / 'Mods' / 'Sliders And Presets')
    if not source.is_dir():
        raise ValueError('The protected original slider/preset folder is missing.')
    files = []
    for directory, subdirs, names in os.walk(source, followlinks=False):
        for name in subdirs + names:
            test_profile.unlinked(Path(directory) / name)
        for name in names:
            path = Path(directory) / name
            if path.suffix.lower() != '.package':
                raise ValueError('Only package files belong to this explicit test recipe.')
            files.append(path)
    if not 0 < len(files) <= MAX_FILES or sum(p.stat().st_size for p in files) > MAX_BYTES:
        raise ValueError('Slider/preset test recipe exceeds its file/byte bounds.')
    incoming = list(data['artifacts'])
    old = {profiles.artifact_relative(row).casefold(): row for row in incoming}
    names, additions, inventory = set(), [], []
    for path in sorted(files):
        name = path.name
        if name.casefold() in names:
            raise ValueError('Duplicate package filenames need explicit disambiguation before copying.')
        names.add(name.casefold())
        with path.open('rb') as stream:
            if stream.read(4) != b'DBPF':
                raise ValueError('Slider/preset source is not a DBPF package: ' + name)
        row = dict(source=str(path), name=name, sha256=sha256(path), bytes=path.stat().st_size,
                   test_addon=ADDON, original_relative=path.relative_to(original).as_posix())
        relative = profiles.artifact_relative(row)
        prior = old.get(relative.casefold())
        if prior is not None:
            if prior['sha256'] != row['sha256']:
                raise ValueError('An existing test artifact collides with this source package.')
        else:
            incoming.append(row); additions.append(relative)
        inventory.append(row)
    return state, data, profile, original, incoming, additions, inventory


def plan(state):
    state, data, profile, original, incoming, additions, inventory = preparation(state)
    return dict(ok=True, operation='plan-owner-sliders-presets', packages=len(inventory),
                bytes=sum(row['bytes'] for row in inventory), additions=additions,
                inventory=inventory, profile=str(profile), original_written=False,
                game_contacted=False, installed=False)


@profiles.serialized
def install(state, guard=test_profile.require_closed):
    guard()
    state, data, profile, original, incoming, additions, inventory = preparation(state)
    saves = {p.relative_to(profile).as_posix(): sha256(p) for p in (profile / 'saves').rglob('*') if p.is_file()}
    result = profiles.install_rows(state, incoming, guard) if additions else profiles.status(state)
    if any(sha256(row['source']) != row['sha256'] for row in inventory):
        raise RuntimeError('An original source changed during copying; test inputs are not certified.')
    after = {p.relative_to(profile).as_posix(): sha256(p) for p in (profile / 'saves').rglob('*') if p.is_file()}
    if saves != after:
        raise RuntimeError('Disposable save hashes changed during package installation.')
    return dict(ok=result['ok'], operation='install-owner-sliders-presets', packages=len(inventory),
                bytes=sum(row['bytes'] for row in inventory), added=len(additions), installed=True,
                profile=str(profile), source=str(original / 'Mods' / 'Sliders And Presets'),
                original_written=False, original_source_hashes_unchanged=True,
                save_files_unchanged=True, game_contacted=False)
