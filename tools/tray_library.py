"""Read/copy complete native Tray groups; originals and payload bytes stay intact.

Household v1/v2 headers and protobuf envelopes are checked before projecting
Sim bytes. Export/import archives retain metadata, images, unknown fields and
the native footer. Appearance extraction uses the separately licensed worker.
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile
from cas_resource_catalog import no_redirected_ancestors, file_hash
from save_metadata import fields

NAME = re.compile(r'0x[0-9a-f]{8}!0x([0-9a-f]{16})\.(trayitem|householdbinary|hhi|sgi|blueprint|room|bpi|rmi)\Z', re.I)
MAX_FILE = 16 * 1024 * 1024
MAX_GROUP = 64 * 1024 * 1024


def read(path, limit=MAX_FILE):
    path = Path(path).absolute(); no_redirected_ancestors(path)
    if not path.is_file() or not 0 < path.stat().st_size <= limit: raise ValueError('Tray file is absent or exceeds its bound.')
    before = path.stat(); raw = path.read_bytes(); after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('Tray file changed during its read.')
    return raw


def keys(name):
    match = NAME.fullmatch(name)
    if match is None: raise ValueError('Exact native Tray filename required.')
    instance, ext = match.groups()
    return instance[2:12].lower(), int(instance[12:], 16), ext.lower()


def groups(folder):
    folder = Path(folder).absolute(); no_redirected_ancestors(folder)
    files = sorted(p for p in folder.iterdir() if p.is_file() and NAME.fullmatch(p.name))
    if len(files) > 100000: raise ValueError('Tray library file count exceeds its bound.')
    bases = [p for p in files if keys(p.name)[2] == 'trayitem']
    result = {p.name: [p] for p in bases}
    for path in files:
        base, offset, ext = keys(path.name)
        if ext == 'trayitem': continue
        eligible = [p for p in bases if keys(p.name)[0] == base and keys(p.name)[1] <= offset]
        if eligible: result[max(eligible, key=lambda p: keys(p.name)[1]).name].append(path)
    return result


def sims(raw):
    if not isinstance(raw, bytes) or len(raw) < 8 or len(raw) > MAX_FILE: raise ValueError('Bounded native household bytes required.')
    version, size = struct.unpack_from('<II', raw)
    if version not in (1, 2) or size != len(raw) - 4: raise ValueError('Unknown or truncated Tray household header.')
    if version == 2:
        if len(raw) < 16: raise ValueError('Truncated v2 household header.')
        reserved, extent = struct.unpack_from('<II', raw, 8)
        if reserved or extent > len(raw) - 16 or len(raw) - 16 - extent > 4096: raise ValueError('Native v2 household extent differs.')
        payload = raw[16:16 + extent]
    else: payload = raw[8:]
    household = [v for n, w, v in fields(payload) if n == 1 and w == 2]
    if len(household) != 1: raise ValueError('Native household payload is absent or ambiguous.')
    entries, names = [], []
    for number, wire, value in fields(household[0]):
        if number == 6:
            if wire != 2: raise ValueError('Native household Sim field type differs.')
            entries.append(value)
        elif number == 3:
            if wire != 2: raise ValueError('Native household name type differs.')
            names.append(value.decode('utf-8'))
    if not 0 < len(entries) <= 128 or len(names) > 1 or any(len(n) > 256 for n in names):
        raise ValueError('Native household Sim/name count differs or exceeds its bound.')
    return {'name': names[0] if names else '', 'version': version,
            'sims': [base64.b64encode(v).decode('ascii') for v in entries]}


def inspect(path, expected, worker=None):
    raw = read(path); digest = hashlib.sha256(raw).hexdigest()
    if digest != expected: raise ValueError('Tray household differs from its exact expected hash.')
    envelope = sims(raw)
    if worker is None:
        from preview_cli import http
        worker = lambda value: http('/v1/tray/inspect', value)
    result = worker({'sims': envelope['sims']})
    if result.get('ok') is not True or result.get('game_contacted') is not False or result.get('disk_assets_written') is not False:
        raise ValueError('Tray projection worker refused its read-only contract.')
    return dict(result, household_name=envelope['name'], household_sha256=digest, filename=Path(path).name,
                header_version=envelope['version'], scope='Exact retained native Sim bytes and represented appearance owners; gameplay paste excluded.')


def preview_forms(sim, household_sha256, identity, selection):
    """Build exact memory-only source requests without borrowing game forms."""
    from cas_resource_catalog import digest, sha
    sha(household_sha256)
    guid = selection['history_lane'].split(':', 1)[0]
    result = []
    for form in sim['forms']:
        raw = base64.b64decode(form['fields']['__outfits__']['value'], validate=True)
        outfits, counts = [], {}
        for number, wire, value in fields(raw):
            if number != 1: continue
            if wire != 2: raise ValueError('Native Tray outfit-list field differs.')
            outfit = list(fields(value)); ids = [(w,v) for n,w,v in outfit if n==1]; categories = [(w,v) for n,w,v in outfit if n==2]
            if len(ids)>1 or len(categories)>1 or any(w!=0 for w,v in ids+categories): raise ValueError('Native Tray outfit identity/category differs.')
            ids=[v for w,v in ids];categories=[v for w,v in categories]
            category = categories[0] if categories else 0; ordinal = counts.get(category,0); counts[category]=ordinal+1
            outfits.append(dict(index=len(outfits),outfit_id=str(ids[0] if ids else 0),category=category,number=ordinal+1))
        if not outfits: continue
        render_hash=digest(json.dumps(form['fields'],sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode())
        request=dict(ok=True,sim_id=sim['sim_id'],form=form['form'],fields=form['fields'],native_sim=sim['native_sim'],native_sha256=sim['native_sha256'],
            lane=guid+':0:'+sim['sim_id']+':'+str(form['form'])+':tray-'+household_sha256+':runtime-'+str(identity['pid']),
            appearance_sha256=render_hash,render_sha256=render_hash,preview_id=None,outfit_index=0,outfit_id=outfits[0]['outfit_id'],
            appearance_source='tray:'+household_sha256,save_guid=guid,runtime_pid=identity['pid'],save_file_written=False,history_written=False)
        result.append(dict(name=sim['name'],request=request,outfits=outfits))
    return result


def export(folder, item, destination):
    from reusable_profile import writable
    destination = writable(destination)
    if destination.exists() or destination.suffix.lower() != '.zip': raise ValueError('Use a new external Tray ZIP filename.')
    selected = groups(folder).get(item)
    if not selected or len(selected) > 256: raise ValueError('Select one bounded native Tray item group.')
    payloads = {p.name: read(p) for p in selected}
    if sum(map(len, payloads.values())) > MAX_GROUP: raise ValueError('Tray group exceeds its bound.')
    manifest = {'schema': 1, 'item': item, 'files': {n: hashlib.sha256(v).hexdigest() for n, v in payloads.items()}}
    with destination.open('xb') as stream:
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, raw in payloads.items(): archive.writestr(name, raw)
            archive.writestr('ApexTrayManifest.json', json.dumps(manifest, sort_keys=True))
    return dict(ok=True, files=len(payloads), bytes=sum(map(len, payloads.values())), sha256=file_hash(destination), source_files_written=False)


def import_bundle(archive, state):
    import reusable_profile
    from apex_cli import require_isolated
    require_isolated(state)
    _, _, active, _ = reusable_profile.load(state)
    target = reusable_profile.writable(active / 'Tray')
    raw = read(archive, MAX_GROUP)
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist(); names = [i.filename for i in infos]
        if len(names) != len(set(names)) or not 2 <= len(names) <= 257 or any(i.flag_bits & 1 or i.is_dir() for i in infos):
            raise ValueError('Tray archive has duplicate, encrypted or unbounded entries.')
        if (any(n != 'ApexTrayManifest.json' and not NAME.fullmatch(n) for n in names)
                or any(not 0 < i.file_size <= (65536 if i.filename == 'ApexTrayManifest.json' else MAX_FILE) for i in infos)
                or sum(i.file_size for i in infos) > MAX_GROUP):
            raise ValueError('Tray archive paths/types/extents differ.')
        manifest = json.loads(z.read('ApexTrayManifest.json'))
        if manifest.get('schema') != 1 or set(manifest.get('files', {})) != set(names) - {'ApexTrayManifest.json'}:
            raise ValueError('Tray archive manifest differs from its file inventory.')
        payloads = {n: z.read(n) for n in manifest['files']}
        if any(hashlib.sha256(v).hexdigest() != manifest['files'][n] for n, v in payloads.items()): raise ValueError('Tray archive bytes differ from their hashes.')
        base, offset, _ = keys(manifest['item'])
        if (keys(manifest['item'])[2] != 'trayitem' or manifest['item'] not in payloads
                or sum(keys(n)[2] == 'trayitem' for n in payloads) != 1
                or any(keys(n)[0] != base or keys(n)[1] < offset for n in payloads)):
            raise ValueError('Archive combines different Tray item groups.')
    paths = {n: reusable_profile.writable(target / n) for n in payloads}
    for name, path in paths.items():
        if path.exists() and file_hash(path) != manifest['files'][name]: raise ValueError('Existing Tray filename differs; no file was overwritten.')
    target.mkdir(exist_ok=True)
    created = []
    try:
        for name, path in paths.items():
            if path.exists(): continue
            with path.open('xb') as stream: stream.write(payloads[name])
            created.append((path, manifest['files'][name]))
    except Exception:
        for path, expected in created:
            if file_hash(path) != expected: raise ValueError('Imported file changed; no concurrent edit was removed.')
            path.unlink()
        raise
    return {'ok': True, 'created': len(created), 'already_identical': len(paths)-len(created), 'existing_files_overwritten': False}
