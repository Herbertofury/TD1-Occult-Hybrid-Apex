"""Build an exact deterministic development script archive; no live install."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile
from source_manifest import write_json


def build(source, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Build outputs must be outside source inputs.')
    paths = [source / 'td1_occult_hybrid_apex.py'] + sorted((source / 'apex_core').rglob('*.py'))
    records, payloads = [], []
    for path in paths:
        if path.is_symlink() or source not in path.resolve().parents:
            raise ValueError('Linked/outside source input.')
        payload = path.read_bytes()
        name = path.relative_to(source).as_posix()
        ast.parse(payload.decode('utf-8-sig'), filename=name, feature_version=(3, 7))
        records.append({'module': name, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
        payloads.append((name, payload))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Archive content is source, never machine-version .pyc or personal data.
    with zipfile.ZipFile(str(output), 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(payloads):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload, compresslevel=9)
    with zipfile.ZipFile(str(output)) as archive:
        if archive.testzip() is not None or sorted(archive.namelist()) != sorted(name for name, _ in payloads):
            raise RuntimeError('Archive verification failed.')
        for name, payload in payloads:
            if archive.read(name) != payload:
                raise RuntimeError('Embedded source mismatch: ' + name)
    manifest = {'schema': 1, 'artifact': output.name, 'status': 'development-not-runtime-accepted',
                'python_source_syntax': '3.7', 'modules': records,
                'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'build': 'python tools/build_script.py --output dist/dev/ApexOccultHybrid.ts4script',
                'limitations': ['Script build only; standalone package/core/CAS/color parity and all runtime gates remain open.']}
    write_json(output.with_suffix('.manifest.json'), manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / 'Source')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))
