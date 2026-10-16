"""Inventory authorized baseline archives/packages using Foundry's Rust DBPF parser.

Never import baseline script modules. Publish resource identities/coverage only,
not third-party binaries or EA resource bodies. Exact inputs remain private.
"""
import argparse
import collections
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from xml.etree import ElementTree
import zipfile
import zlib
from source_manifest import sha256, write_json

MAX_RESOURCE = 32 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bounded_resource(raw, row):
    start, length, size = row['offset'], row['stored_size'], row['memory_size']
    if min(start, length, size) < 0 or start + length > len(raw) or size > MAX_RESOURCE:
        raise ValueError('Baseline resource extent exceeds bounds.')
    data = raw[start:start + length]
    if row['compression'] == 0x5A42:
        decoder = zlib.decompressobj()
        data = decoder.decompress(data, MAX_RESOURCE + 1)
        if decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
            raise ValueError('Invalid/bounded compressed baseline resource.')
    elif row['compression'] not in (0, 0xFFFF):
        return None
    if len(data) != size:
        raise ValueError('Baseline decompressed size mismatch.')
    return data


def package(raw, foundry, directory):
    input_file, output_file = directory / 'input.package', directory / 'index.json'
    input_file.write_bytes(raw)
    if output_file.exists():
        output_file.unlink()
    subprocess.run([str(foundry), 'inspect', str(input_file), '--output', str(output_file)],
                   check=True, capture_output=True, timeout=30)
    index = json.loads(output_file.read_text(encoding='utf-8'))
    rows = []
    for entry in index['entries']:
        key = entry['key']
        row = {'tgi': '{:08X}:{:08X}:{:016X}'.format(key['kind'], key['group'], key['instance']),
               'type': '{:08X}'.format(key['kind']), 'stored_bytes': entry['stored_size'],
               'memory_bytes': entry['memory_size'], 'compression': '{:04X}'.format(entry['compression'])}
        decoded = bounded_resource(raw, entry)
        if decoded is None:
            row['content_inspected'] = False
        else:
            row.update({'content_inspected': True, 'content_sha256': digest(decoded)})
            if decoded.startswith(b'STBL'):
                row['format'] = 'STBL'
            elif decoded[:3] in (b'FWS', b'CWS', b'ZWS'):
                row.update({'format': 'SWF', 'swf_version': decoded[3]})
            elif decoded.lstrip().startswith(b'<'):
                if b'<!DOCTYPE' in decoded.upper() or b'<!ENTITY' in decoded.upper():
                    raise ValueError('Unsupported baseline XML entities.')
                try:
                    xml = ElementTree.fromstring(decoded)
                    row.update({'format': 'XML', 'root': xml.tag, 'name': xml.get('n'),
                                'class': xml.get('c'), 'instance_type': xml.get('i'),
                                'named_fields': sorted({node.get('n') for node in xml.iter() if node.get('n')})})
                except ElementTree.ParseError:
                    row['format'] = 'unresolved-text'
        rows.append(row)
    rows.sort(key=lambda row: row['tgi'])
    return {'dbpf_version': [index['major'], index['minor']], 'resource_count': len(rows),
            'resource_types': dict(sorted(collections.Counter(row['type'] for row in rows).items())), 'resources': rows}


def scripts(raw):
    result = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            if info.file_size > MAX_RESOURCE:
                raise ValueError('Oversize baseline script module.')
            payload = archive.read(info)
            row = {'path': info.filename, 'bytes': len(payload), 'sha256': digest(payload)}
            if info.filename.endswith('.pyc'):
                row['pyc_magic'] = payload[:4].hex()
            result.append(row)
    return result


def inventory(baseline, foundry):
    baseline, foundry = Path(baseline).resolve(strict=True), Path(foundry).resolve(strict=True)
    archives, packages = [], []
    with tempfile.TemporaryDirectory(prefix='apex-baseline-') as temp:
        directory = Path(temp)
        for path in sorted(baseline.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in ('.zip', '.package'):
                continue
            if path.is_symlink():
                raise ValueError('Linked baseline input.')
            name = path.relative_to(baseline).as_posix()
            raw = path.read_bytes()
            record = {'file': name, 'bytes': len(raw), 'sha256': digest(raw)}
            if path.suffix.lower() == '.package':
                record.update(package(raw, foundry, directory))
                packages.append(record)
            else:
                record['entries'] = []
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    for info in sorted(archive.infolist(), key=lambda item: item.filename):
                        if info.is_dir():
                            continue
                        if info.file_size > MAX_RESOURCE:
                            raise ValueError('Oversize baseline archive member.')
                        payload = archive.read(info)
                        item = {'path': info.filename, 'bytes': len(payload), 'sha256': digest(payload)}
                        if info.filename.endswith('.package'):
                            item.update(package(payload, foundry, directory))
                        elif info.filename.endswith('.ts4script'):
                            item['modules'] = scripts(payload)
                        record['entries'].append(item)
                archives.append(record)
    return {'schema': 2, 'algorithm': 'SHA-256', 'inspection_tool': 'Sims 4 Foundry Rust DBPF parser',
            'inspection_tool_sha256': sha256(foundry), 'archives': archives, 'packages': packages,
            'proof_scope': 'Input identity and bounded structural/resource coverage; no baseline module executed; no current-game/runtime parity claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--foundry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = inventory(args.baseline, args.foundry)
    write_json(args.output, data)
    print(json.dumps({'ok': True, 'archives': len(data['archives']), 'loose_packages': len(data['packages']),
                      'resources': sum(item.get('resource_count', 0) for arc in data['archives'] for item in arc['entries']) + sum(item['resource_count'] for item in data['packages'])}))
