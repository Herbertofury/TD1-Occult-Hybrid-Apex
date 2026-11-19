"""Three exact CC addons through the retained test profile's guarded journal.

Default invocation only plans. Installation preserves the full existing artifact
set and uses reusable_profile's lock, recovery blobs and repeated closed-game
checks. It never creates or restores a profile, touches protected originals, or
submits game input.
"""
import argparse
import json
from pathlib import Path

import cas_resource_catalog as catalog
import reusable_profile as profiles
import test_profile
from source_manifest import sha256, write_json

INVENTORY_SHA256 = '874d073f14b2a1009d105b157bb058351a2019c42aaa521a5bb4b52f6d609b1a'
SCRIPT_SHA256 = 'a0dff198bd8bf778c440883baf58d83e695b0a26e3d2b7a491e315fcbabf34ce'
ADDON = 'cc-static-candidate-2026-10-08'
ASSETS = {
    'LeahLillith_HollywoodLashes_BODYHAIRARM.package': 'a00cc5223ad13d30e18f816d0a8977e637676c0b787e8648ddc72ead5817430f',
    'jellypawsAngelFreckles.package': 'b2bfff7768c1e0f0b431b5256bf0cd150d2689a7636b0ae55929850898c52f8b',
    '(FUKKIE) woji earrings.package': '43591eeb23ee267a1c3ffd5da71fc40e20f4482e7f496a0bbf4673ebb5764238',
}

# Independently copied from the owner's read-only library after bounded CASP
# inspection. Both packages contain enabled four-channel controls and LRLE
# textures. This recipe identifies test inputs; it does not certify rendering.
COLOR_ADDON = 'live-color-compatible-cc'
COLOR_ASSETS = {
    '[Magic Hand] Lipstick N91.package': '4e5d1113e2bdcafb330776fc40e15315aa1a3e759d27cb7d1779110a7d2570be',
    'Simbience_Hello Sunshine! Swirl Blush.package': 'eeee18ae983e0f8f7cf71e1a44ca5c34e8b54c76a197578424cd0d8ba5f33c6f',
}


def asset_rows():
    cache = test_profile.unlinked(catalog.CACHE_ROOT)
    inventory = catalog.safe_cache_file(cache, 'cc-candidate-inventory.json')
    if inventory.stat().st_size > 256 * 1024 or sha256(inventory) != INVENTORY_SHA256:
        raise ValueError('The sealed three-CC inventory hash or size differs.')
    data = json.loads(inventory.read_text(encoding='utf-8'))
    items = data.get('items')
    if (data.get('schema') != 1 or data.get('operation') != 'read-only-cc-candidate-inventory' or
            not isinstance(items, list) or len(items) != len(ASSETS)):
        raise ValueError('Expected the exact read-only three-CC inventory.')
    rows, names = [], set()
    for item in items:
        name, expected = item.get('original_filename'), item.get('sha256')
        if name not in ASSETS or expected != ASSETS[name] or name.casefold() in names:
            raise ValueError('CC inventory filename/hash set differs from the supported assets.')
        names.add(name.casefold())
        source = catalog.safe_cache_file(cache, 'packages/' + expected + '.package')
        if test_profile.unlinked(item['sealed_copy']) != source:
            raise ValueError('A CC source must be its exact independent sealed cache copy.')
        if source.stat().st_size != item.get('bytes') or source.stat().st_size > 4 * 1024 * 1024 or sha256(source) != expected:
            raise ValueError('A sealed CC copy hash/size differs.')
        with source.open('rb') as stream:
            if stream.read(4) != b'DBPF':
                raise ValueError('A sealed CC copy is not a package.')
        row = {'name': name, 'source': str(source), 'bytes': source.stat().st_size,
               'sha256': expected, 'test_addon': ADDON}
        profiles.artifact_relative(row)  # Existing plain-basename ApexTest/ guard.
        rows.append(row)
    return rows


def save_hashes(profile):
    base = test_profile.unlinked(profile / 'saves')
    return {path.relative_to(base).as_posix(): sha256(test_profile.unlinked(path))
            for path in base.rglob('*') if path.is_file()}


def preparation(state):
    state, data, profile, original = profiles.load(state)
    if not profiles.status(state)['ready_to_launch']:
        raise ValueError('An unchanged marked reusable test profile is required.')
    scripts = [row for row in data['artifacts']
               if profiles.artifact_relative(row) == 'Apex/ApexOccultHybrid.ts4script']
    if len(scripts) != 1 or scripts[0]['sha256'] != SCRIPT_SHA256:
        raise ValueError('CC addons require the exact sealed A0 candidate script.')
    incoming = list(data['artifacts'])  # install_rows replaces the whole set.
    existing = {profiles.artifact_relative(row).casefold(): row for row in incoming}
    additions = []
    for row in asset_rows():
        relative = profiles.artifact_relative(row)
        prior = existing.get(relative.casefold())
        if prior is not None:
            if prior['name'] != row['name'] or prior['sha256'] != row['sha256']:
                raise ValueError('A CC addon target collides with an existing journal artifact.')
            continue
        incoming.append(row)
        additions.append({'relative': relative, 'name': row['name'], 'sha256': row['sha256'],
                          'bytes': row['bytes'], 'source': row['source']})
    return state, data, profile, original, incoming, additions


def plan(state):
    state, data, profile, _original, _incoming, additions = preparation(state)
    return {'schema': 1, 'ok': True, 'operation': 'plan-three-cc-addons',
            'state': str(state), 'profile': str(profile), 'changes_required': bool(additions),
            'profile_writes': 0, 'protected_original_policy': 'read/copy-only',
            'script_sha256': SCRIPT_SHA256, 'existing_artifacts_preserved': len(data['artifacts']),
            'generation': data['generation'], 'additions': additions,
            'scope': 'Plan only. Installation requires a closed game and preserves the current save.'}


@profiles.serialized
def install(state, guard=test_profile.require_closed):
    guard()
    state, data, profile, _original, incoming, additions = preparation(state)
    before_saves = save_hashes(profile)
    before_artifacts = list(data['artifacts'])
    before_bundle = data.get('bundle')
    before_token = data['token']
    if additions:
        status = profiles.install_rows(state, incoming, guard)
    else:
        status = profiles.status(state)
    _state, after, _profile, _original = profiles.load(state)
    after_saves = save_hashes(profile)
    preserved = all(row in after['artifacts'] for row in before_artifacts)
    sealed = after.get('bundle') == before_bundle and after['token'] == before_token
    if not preserved or not sealed or after_saves != before_saves:
        raise RuntimeError('CC addon installation did not preserve the prior artifacts/seal/save bytes.')
    return dict(status, schema=1, operation='install-three-cc-addons',
                additions=additions, already_installed=not additions,
                existing_artifacts_preserved_verified=preserved,
                candidate_seal_preserved_verified=sealed,
                save_files_unchanged_verified=True, save_requested=False,
                script_sha256=SCRIPT_SHA256, before_save_hashes=before_saves,
                after_save_hashes=after_saves,
                scope='Exact CC assets only; no game CC load/copy/color acceptance is claimed.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--install', action='store_true', help='Apply only through existing closed-game journal guards')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.output is not None:
        _state, _data, profile, original = profiles.load(args.state)
        output = profiles.writable(args.output)
        if output == _state:
            raise ValueError('Proof output cannot replace the reusable profile journal.')
        if any(output == p or p in output.parents for p in (profile, original)):
            raise ValueError('Proof output must stay outside both game profiles.')
    result = install(args.state) if args.install else plan(args.state)
    if args.output is not None:
        write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
