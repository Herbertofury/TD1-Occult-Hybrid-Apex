"""Exact minimal MCCC interoperability recipe in the retained test profile."""
import hashlib
from pathlib import Path
import zipfile
import reusable_profile as profiles
from source_manifest import sha256, write_json
import test_profile

MCCC_SHA256 = '5596e47a5d4dab0c4800e80426caf17d28d15508cd711848f083b9c9f63672c9'
MEMBERS = ('mc_cmd_center.package', 'mc_cmd_center.ts4script', 'mc_cas.ts4script', 'mc_dresser.ts4script')


@profiles.serialized
def configure(state, archive=None, remove=False, guard=test_profile.require_closed):
    guard()
    state, data, profile, _original = profiles.load(state)
    if not profiles.status(state)['ready_to_launch']:
        raise ValueError('Exact isolated profile is required before MCCC test changes.')
    existing = [row for row in data['artifacts'] if row.get('test_addon') == 'mccc-2026.5.0']
    keep = [row for row in data['artifacts'] if row not in existing]
    recovery = profiles.writable(state.parent / 'artifact-recovery')
    recovery.mkdir(exist_ok=True)
    if remove:
        generated = []
        for relative in sorted(profiles.MCCC_DATA):
            source = profiles.writable(profile / 'Mods' / relative)
            if source.is_file():
                raw, digest = source.read_bytes(), sha256(source)
                target = profiles.writable(recovery / (digest + '.mccc-data'))
                if not target.exists():
                    with target.open('xb') as stream:
                        stream.write(raw)
                if sha256(target) != digest:
                    raise ValueError('MCCC settings/log recovery failed.')
                generated.append({'relative': relative, 'sha256': digest, 'recovery': str(target)})
        latest = recovery / 'mccc-generated-data-latest.json'
        if latest.exists():
            prior_digest = sha256(latest)
            archived = profiles.writable(recovery / ('mccc-generated-data-' + prior_digest + '.json'))
            if not archived.exists():
                with archived.open('xb') as stream:
                    stream.write(latest.read_bytes())
            if sha256(archived) != prior_digest:
                raise ValueError('Previous MCCC data recovery manifest was not preserved.')
        write_json(latest, {'test_token': data['token'], 'files': generated})
        for row in generated:
            target = profiles.writable(profile / 'Mods' / row['relative'])
            if sha256(target) != row['sha256']:
                raise ValueError('MCCC generated data changed before removal.')
            guard(); target.unlink()  # Exact fixed path, externally preserved.
        return profiles.install_rows(state, keep, guard)
    if archive is None:
        raise ValueError('The exact MCCC 2026.5.0 archive is required.')
    archive = test_profile.unlinked(archive)
    if archive.stat().st_size > 16 * 1024 * 1024 or sha256(archive) != MCCC_SHA256:
        raise ValueError('MCCC archive differs from the verified official baseline.')
    incoming = []
    with zipfile.ZipFile(archive) as container:
        for name in MEMBERS:
            entries = [row for row in container.infolist() if row.filename == name]
            if len(entries) != 1 or entries[0].file_size > 8 * 1024 * 1024:
                raise ValueError('MCCC archive has duplicate/missing/oversize required members.')
            raw = container.read(name)
            if name.endswith('.package') and not raw.startswith(b'DBPF') or name.endswith('.ts4script') and not raw.startswith(b'PK'):
                raise ValueError('MCCC member has the wrong container type.')
            digest = hashlib.sha256(raw).hexdigest()
            source = profiles.writable(recovery / (digest + '.mccc' + Path(name).suffix))
            if not source.exists():
                with source.open('xb') as stream:
                    stream.write(raw)
            if sha256(source) != digest:
                raise ValueError('MCCC staging verification failed.')
            incoming.append({'name': name, 'relative': 'MCCC/' + name, 'source': str(source),
                             'bytes': len(raw), 'sha256': digest, 'test_addon': 'mccc-2026.5.0',
                             'archive_sha256': MCCC_SHA256})
    result = profiles.install_rows(state, keep + incoming, guard)
    return dict(result, test_addon='mccc-2026.5.0', scope='Only MCCC core, CAS and Dresser; no original Mods or unrelated MCCC modules.')
