"""One explicit A0 script transition for the retained disposable profile.

Default invocation only plans. --install retains all fourteen current inputs,
replaces the script and its existing native manifest's script binding through
the reusable journal, and writes a separate immutable migration receipt. The
original seal, bank and every save remain unchanged. No game input is submitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import build_script
import candidate_install
import reusable_profile as profiles
import test_profile
from source_manifest import sha256, write_json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source'))
from apex_core import form_bank_seal as seal, test_driver

SCRIPT = 'Apex/ApexOccultHybrid.ts4script'
NATIVE = 'Apex/Native/overlay-manifest.json'
RECEIPT = 'form_bank_script_upgrade.json'


def save_hashes(profile):
    base = test_profile.unlinked(profile / 'saves')
    return {path.relative_to(base).as_posix(): sha256(test_profile.unlinked(path))
            for path in base.rglob('*') if path.is_file()}


def artifact_evidence(data, profile):
    rows = []
    for row in data['artifacts']:
        relative = profiles.artifact_relative(row)
        path = test_profile.unlinked(profile / 'Mods' / relative)
        if sha256(path) != row['sha256']:
            raise ValueError('Retained artifact changed while planning the migration.')
        rows.append({'relative': relative, 'sha256': row['sha256'], 'bytes': path.stat().st_size})
    rows.sort(key=lambda row: row['relative'])
    seal.upgrade_artifacts(rows)
    return rows


def validate_target(raw, manifest):
    members = seal.upgrade_archive(raw, manifest)
    # Python 3.7 marshal output also reflects strings interned by earlier
    # compilations in the same process. Reproduce the complete original source
    # batch in its recorded order before comparing the audited recovery code.
    names = [row['module'] for row in manifest['modules']]
    compiled, compiler = build_script.compile_payloads(
        [(name, members[name]) for name in names], build_script.DEFAULT_OUTPUT / 'python.exe')
    audited = {name[:-3] + '.pyc' for name in set(seal.UPGRADE_MODULE_PINS) | {'apex_core/form_bank_seal.py'}}
    if compiler != manifest['compiler'] or any(members[name] != value for name, value in compiled if name in audited):
        raise ValueError('Target build bytecode/compiler does not match fresh audited-source compilation.')
    return hashlib.sha256(raw).hexdigest()


def archive_evidence(path, expected, state, profile, original):
    if path is None and expected is None:
        return None
    if path is None or not seal._sha(expected):
        raise ValueError('Use both the exact metadata-archive proof and its SHA-256.')
    path = test_profile.unlinked(path)
    if path == state or any(path == base or base in path.parents for base in (profile, original)) or path.suffix.lower() != '.json':
        raise ValueError('The metadata-archive proof must be an external JSON file.')
    before = path.stat()
    with path.open('rb') as source: raw = source.read(12 * 1024 * 1024 + 1)
    after = path.stat()
    if (not 0 < len(raw) <= 12 * 1024 * 1024 or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or
            hashlib.sha256(raw).hexdigest() != expected):
        raise ValueError('The exact metadata-archive proof changed or exceeds its bound.')
    return {'sha256': expected, 'raw': raw.decode('utf-8')}


def certified_row(profile, token, expected, evidence=None):
    if not seal._sha(expected):
        raise ValueError('Supply the exact certified A0 seal SHA-256.')
    data_dir = test_profile.unlinked(profile / 'TD1_OccultHybridApexData')
    path = test_profile.unlinked(data_dir / 'form_bank_seals.json')
    data = seal._store(path)
    rows = [(key, row) for key, row in data['records'].items()
            if isinstance(row, dict) and row.get('seal_sha256') == expected]
    if len(rows) != 1:
        raise ValueError('The exact A0 seal is missing or ambiguous.')
    key, row = rows[0]
    identity, target = row.get('identity'), row.get('target')
    if (not isinstance(identity, dict) or row.get('state') not in ('sealed', 'reconciled') or
            row.get('sealed') is not True or row.get('contract_sha256') != seal.CONTRACT or
            identity.get('script_sha256') != seal.UPGRADE_PREDECESSOR or identity.get('profile') != str(profile) or
            identity.get('test_token') != token or type(identity.get('pid')) is not int or identity['pid'] <= 0 or
            any(name not in row for name in seal._SEAL_FIELDS) or
            seal._hash({name: row[name] for name in seal._SEAL_FIELDS}) != expected):
        raise ValueError('The A0 seal/native/profile/contract identity differs.')
    test_driver._save_target(target)
    if key != target['save_guid'] + ':' + target['sim_id']:
        raise ValueError('The seal save GUID/Sim ownership differs from the bank key.')
    bank = seal._record(data_dir / 'form_bank.json', key)
    current_hash = seal._hash(bank)
    changed = current_hash != row['bank_record_sha256']
    leaf = bank.get('failed_history', [None])[-1] if bank.get('failed_history') else None
    if leaf is not None:
        from apex_core.bank_history import resolve
        leaf = resolve(data_dir / 'form_bank.json', leaf)
    authority = {'bank_record_sha256': row['bank_record_sha256'], 'current_bank_record_sha256': current_hash,
        'failed_history_leaf_sha256': seal._hash(leaf) if changed and isinstance(leaf, dict) else None,
        'metadata_archive_proof': evidence}
    if changed and evidence is None:
        raise ValueError('The certified bank changed; newer edits were preserved. Use exact metadata-archive evidence only for unchanged appearances.')
    seal.upgrade_bank_authority(bank, row, authority, data_dir / 'form_bank.json')
    if test_driver._save_file_evidence(profile, target['slot_id'])['sha256'] != row['file_sha256']:
        raise ValueError('The certified save changed; newer saves were preserved.')
    return data_dir, path, key, row, authority


def preparation(state, bundle, expected_seal, metadata_archive_proof=None, metadata_archive_sha256=None):
    state, data, profile, original = profiles.load(state)
    if not profiles.status(state)['ready_to_launch']:
        raise ValueError('An exact unchanged marked reusable test profile is required.')
    marker_path = profile / test_profile.MARKER
    if marker_path.stat().st_size > 4096:
        raise ValueError('The disposable marker exceeds its bound.')
    marker = seal._read(marker_path)
    if marker.get('disposable') is not True or marker.get('token') != data['token']:
        raise ValueError('The exact disposable profile marker is required.')
    current = artifact_evidence(data, profile)
    by_relative = {row['relative']: row for row in current}
    if SCRIPT not in by_relative or NATIVE not in by_relative:
        raise ValueError('The retained script/native manifest pair is absent.')
    bundle, bundle_hash, _bundle_manifest, payloads = candidate_install.read_bundle(bundle)
    raw = payloads['Mods/' + SCRIPT]
    manifest_name = 'Manifests/ApexOccultHybrid.ts4script.manifest.json'
    if manifest_name not in payloads or len(payloads[manifest_name]) > 1024 * 1024:
        raise ValueError('The target has no bounded script build manifest.')
    manifest = json.loads(payloads[manifest_name])
    target_hash = validate_target(raw, manifest)
    if target_hash == seal.UPGRADE_PREDECESSOR:
        raise ValueError('The target must be the new audited epoch, not the A0 predecessor.')
    evidence = archive_evidence(metadata_archive_proof, metadata_archive_sha256, state, profile, original)
    data_dir, seal_path, key, old, bank_authority = certified_row(profile, data['token'], expected_seal, evidence)
    native_path = test_profile.unlinked(profile / 'Mods' / NATIVE)
    native = seal._read(native_path)
    dll = test_profile.unlinked(native_path.with_name('ApexOverlay.dll'))
    if (native.get('schema') != 1 or native.get('protocol') != 1 or native.get('file') != 'ApexOverlay.dll' or
            native.get('sha256') != sha256(dll) or native.get('verified_script_sha256') != by_relative[SCRIPT]['sha256']):
        raise ValueError('The current native manifest does not bind its retained DLL and script.')
    native['verified_script_sha256'] = target_hash
    native_raw = seal._bytes(native)
    replacements = {SCRIPT: raw, NATIVE: native_raw}
    receipt_path = test_profile.unlinked(data_dir / RECEIPT)
    if receipt_path.exists():
        value = seal._read(receipt_path)
        if (not isinstance(value, dict) or set(value) != {'schema', 'receipt', 'receipt_sha256'} or
                type(value.get('schema')) is not int or value['schema'] != 1 or not isinstance(value['receipt'], dict) or
                seal._hash(value['receipt']) != value['receipt_sha256']):
            raise ValueError('An existing migration receipt is altered; no overwrite is allowed.')
        receipt = value['receipt']
        before, after = receipt.get('artifacts_before'), receipt.get('artifacts_after')
        seal.upgrade_artifacts(before); seal.upgrade_artifacts(after)
        expected_fields = {'epoch': seal.UPGRADE_EPOCH, 'predecessor_sha256': seal.UPGRADE_PREDECESSOR,
            'target_sha256': target_hash, 'profile': str(profile), 'test_token': data['token'], 'key': key,
            'old_seal_sha256': expected_seal, 'old_seal_file_sha256': sha256(seal_path),
            'bank_record_sha256': old['bank_record_sha256'], 'file_sha256': old['file_sha256'],
            'current_bank_record_sha256': bank_authority['current_bank_record_sha256'],
            'failed_history_leaf_sha256': bank_authority['failed_history_leaf_sha256'],
            'metadata_archive_proof': evidence,
            'target': old['target'], 'build_manifest': manifest, 'build_manifest_sha256': seal._hash(manifest)}
        if (set(receipt) != set(expected_fields) | {'artifacts_before', 'artifacts_after', 'generation_before'} or
                any(receipt.get(name) != value for name, value in expected_fields.items()) or
                type(receipt.get('generation_before')) is not int or receipt['generation_before'] < 0):
            raise ValueError('An existing migration receipt is from another seal/epoch/profile/target.')
        already = current == after
        if (current != before and not already or data['generation'] != receipt['generation_before'] + int(already)):
            raise ValueError('The migration journal has newer artifacts/generation; no replay is allowed.')
        rebuilt = [dict(row, sha256=hashlib.sha256(replacements[row['relative']]).hexdigest(),
                        bytes=len(replacements[row['relative']])) if row['relative'] in replacements else row for row in before]
        if rebuilt != after:
            raise ValueError('The migration receipt changed a retained artifact outside its exact targets.')
    else:
        if by_relative[SCRIPT]['sha256'] != seal.UPGRADE_PREDECESSOR:
            raise ValueError('A migration requires the exact installed A0 predecessor, or its existing receipt.')
        already = False
        after = [dict(row, sha256=hashlib.sha256(replacements[row['relative']]).hexdigest(),
                      bytes=len(replacements[row['relative']])) if row['relative'] in replacements else row for row in current]
        receipt = {'epoch': seal.UPGRADE_EPOCH, 'predecessor_sha256': seal.UPGRADE_PREDECESSOR,
            'target_sha256': target_hash, 'profile': str(profile), 'test_token': data['token'], 'key': key,
            'old_seal_sha256': expected_seal, 'old_seal_file_sha256': sha256(seal_path),
            'bank_record_sha256': old['bank_record_sha256'], 'file_sha256': old['file_sha256'], 'target': old['target'],
            'current_bank_record_sha256': bank_authority['current_bank_record_sha256'],
            'failed_history_leaf_sha256': bank_authority['failed_history_leaf_sha256'], 'metadata_archive_proof': evidence,
            'build_manifest': manifest, 'build_manifest_sha256': seal._hash(manifest),
            'artifacts_before': current, 'artifacts_after': after, 'generation_before': data['generation']}
        value = {'schema': 1, 'receipt': receipt, 'receipt_sha256': seal._hash(receipt)}
    return {'state': state, 'data': data, 'profile': profile, 'original': original,
            'seal_path': seal_path, 'receipt_path': receipt_path, 'receipt': value,
            'replacements': replacements, 'already_installed': already, 'bundle_sha256': bundle_hash}


def plan(state, bundle, expected_seal, metadata_archive_proof=None, metadata_archive_sha256=None):
    context = preparation(state, bundle, expected_seal, metadata_archive_proof, metadata_archive_sha256)
    row = context['receipt']['receipt']
    return {'schema': 1, 'ok': True, 'operation': 'plan-explicit-test-script-upgrade',
            'state': str(context['state']), 'profile': str(context['profile']), 'profile_writes': 0,
            'epoch': row['epoch'], 'old_seal_sha256': row['old_seal_sha256'],
            'predecessor_sha256': row['predecessor_sha256'], 'target_sha256': row['target_sha256'],
            'receipt_sha256': context['receipt']['receipt_sha256'], 'bundle_sha256': context['bundle_sha256'],
            'old_bank_record_sha256': row['bank_record_sha256'], 'current_bank_record_sha256': row['current_bank_record_sha256'],
            'failed_history_leaf_sha256': row['failed_history_leaf_sha256'],
            'already_installed': context['already_installed'], 'existing_artifacts_retained': len(row['artifacts_before']),
            'changed_mod_files': [SCRIPT, NATIVE], 'save_files_written': False, 'bank_written': False,
            'old_seal_written': False, 'replay_requested': False,
            'scope': 'Closed installation only; runtime reconciliation still requires an exact paused native load receipt.'}


@profiles.serialized
def install(state, bundle, expected_seal, guard=test_profile.require_closed,
            metadata_archive_proof=None, metadata_archive_sha256=None):
    guard()
    context = preparation(state, bundle, expected_seal, metadata_archive_proof, metadata_archive_sha256)
    state, data, profile, original = (context[name] for name in ('state', 'data', 'profile', 'original'))
    before_saves = save_hashes(profile)
    before_original = test_profile.inventory(original)
    before_seal = sha256(context['seal_path'])
    before_bank = sha256(profile / 'TD1_OccultHybridApexData' / 'form_bank.json')
    incoming = []
    recovery = profiles.writable(state.parent / 'artifact-recovery')
    guard()
    recovery.mkdir(exist_ok=True)
    for row in data['artifacts']:
        relative = profiles.artifact_relative(row)
        if relative in context['replacements']:
            raw = context['replacements'][relative]
            fresh = dict(row, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            stage = profiles.recovery_path(state, fresh, True)
            if not stage.exists():
                guard()
                with stage.open('xb') as output: output.write(raw)
            if sha256(stage) != fresh['sha256']:
                raise ValueError('The audited migration staging blob differs.')
            fresh['source'] = str(stage)
        else:
            fresh = dict(row, source=str(test_profile.unlinked(profile / 'Mods' / relative)))
        incoming.append(fresh)
    guard()
    # This immutable authorization is durable before the artifact journal. A
    # partial install cannot authorize replay: the receiver rehashes all inputs.
    if not context['receipt_path'].exists():
        seal._write(context['receipt_path'], context['receipt'])
    elif seal._read(context['receipt_path']) != context['receipt']:
        raise ValueError('The migration receipt changed; no overwrite is allowed.')
    if not context['already_installed']:
        profiles.install_rows(state, incoming, guard)
    guard()
    _state, after, _profile, _original = profiles.load(state)
    expected = context['receipt']['receipt']['artifacts_after']
    if (artifact_evidence(after, profile) != expected or not profiles.status(state)['ready_to_launch'] or
            save_hashes(profile) != before_saves or sha256(context['seal_path']) != before_seal or
            sha256(profile / 'TD1_OccultHybridApexData' / 'form_bank.json') != before_bank or
            after['token'] != data['token'] or after.get('bundle') != data.get('bundle') or
            test_profile.inventory(original) != before_original):
        raise RuntimeError('Migration postflight failed; journal recovery blobs and original evidence were retained.')
    return {'schema': 1, 'ok': True, 'operation': 'install-explicit-test-script-upgrade',
            'epoch': seal.UPGRADE_EPOCH, 'profile': str(profile),
            'receipt_sha256': context['receipt']['receipt_sha256'], 'receipt_path': str(context['receipt_path']),
            'target_sha256': context['receipt']['receipt']['target_sha256'], 'already_installed': context['already_installed'],
            'retained_artifacts_verified': 14, 'save_files_unchanged_verified': True,
            'bank_unchanged_verified': True, 'old_seal_unchanged_verified': True,
            'protected_original_unchanged_verified': True, 'replay_requested': False,
            'scope': 'Script installed; this does not claim native reload, migration replay, or appearance parity.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--seal-sha256', required=True)
    parser.add_argument('--metadata-archive-proof', type=Path)
    parser.add_argument('--metadata-archive-sha256')
    parser.add_argument('--install', action='store_true', help='Install only under the reusable lock and closed-game guards')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.output is not None:
        state, _data, profile, original = profiles.load(args.state)
        output = profiles.writable(args.output)
        if output == state or any(output == p or p in output.parents for p in (profile, original)):
            raise ValueError('Proof output must stay outside both profiles and cannot replace the journal.')
    if args.install:
        result = install(args.state, args.bundle, args.seal_sha256,
            metadata_archive_proof=args.metadata_archive_proof, metadata_archive_sha256=args.metadata_archive_sha256)
    else:
        result = plan(args.state, args.bundle, args.seal_sha256, args.metadata_archive_proof, args.metadata_archive_sha256)
    if args.output is not None: write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
