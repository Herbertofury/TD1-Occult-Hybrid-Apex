"""SHA-256 inventory of staged Git source and exact separately supplied artifacts.

Source identities use canonical Git blobs, independent of checkout line endings.
Unstaged source edits are rejected so a manifest cannot describe an older staged
input while the build silently consumes different working-tree source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False) as stream:
            temporary = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows readers/antivirus can briefly hold the destination without
        # delete sharing. Retry only this atomic publication of already-flushed
        # evidence; callers must never replay a game operation to repair a log.
        for attempt in range(11):
            try:
                os.replace(temporary, str(path))
                break
            except PermissionError as error:
                if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 10:
                    raise
                time.sleep(0.05)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def manifest(root, output, artifacts=()):
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve()
    entries = subprocess.check_output(['git', 'ls-files', '-z', '--stage'], cwd=str(root)).decode('utf-8').split('\0')
    rows = []
    for entry in sorted(set(entries) - {''}):
        identity, name = entry.split('\t', 1)
        mode, oid, stage = identity.split()
        path = root / name
        if path.resolve() == output or name.startswith('manifests/'):
            continue
        if stage != '0' or mode not in ('100644', '100755'):
            raise ValueError('Tracked source must be an unconflicted regular file: ' + name)
        if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
            raise ValueError('Tracked input is missing, linked or outside the checkout: ' + name)
        working_oid = subprocess.check_output(
            ['git', 'hash-object', '--path=' + name, '--stdin'],
            input=path.read_bytes(), cwd=str(root)).decode('ascii').strip()
        if working_oid != oid:
            raise ValueError('Stage this source change before creating/checking the manifest: ' + name)
        canonical = subprocess.check_output(['git', 'cat-file', 'blob', oid], cwd=str(root))
        rows.append({'path': name, 'mode': mode, 'bytes': len(canonical),
                     'sha256': hashlib.sha256(canonical).hexdigest()})
    external = []
    labels = set()
    for label, path in artifacts:
        if label in labels:
            raise ValueError('Duplicate artifact label: ' + label)
        labels.add(label)
        path = Path(path).resolve(strict=True)
        external.append({'label': label, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    return {'schema': 2, 'algorithm': 'SHA-256', 'source_encoding': 'canonical-git-index-blobs', 'source_files': rows,
            'artifacts': sorted(external, key=lambda row: row['label'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('manifests/source.json'))
    parser.add_argument('--artifact', nargs=2, action='append', default=[], metavar=('LABEL', 'FILE'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    current = manifest(args.root, output, args.artifact)
    if args.check:
        if json.loads(output.read_text(encoding='utf-8')) != current:
            raise SystemExit('Manifest mismatch: an input changed, disappeared or was added.')
    else:
        write_json(output, current)
    print(json.dumps({'ok': True, 'source_files': len(current['source_files']), 'artifacts': len(current['artifacts'])}))


if __name__ == '__main__':
    main()
