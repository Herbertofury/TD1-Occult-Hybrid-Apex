"""Build/check the one-off Rust metadata executable against its exact inputs."""
import argparse
import json
from pathlib import Path
import subprocess

from source_manifest import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Metadata/target/release/apex-catalog.exe'
MANIFEST = ROOT / 'Metadata/target/release/apex-catalog.manifest.json'


def inputs():
    root = ROOT / 'Metadata'
    paths = [root/'Cargo.toml', root/'Cargo.lock']
    paths += sorted((root/'src').glob('*.rs'))
    paths += sorted((root/'data').glob('*.json'))
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p) for p in paths}


def verify():
    info = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (info.get('schema') != 1 or info.get('source_inputs') != inputs() or
            info.get('sha256') != sha256(OUTPUT) or OUTPUT.read_bytes()[:2] != b'MZ'):
        raise ValueError('Metadata companion differs from its exact built source inputs.')
    return info


def build():
    before = inputs()
    subprocess.run(['cargo', 'build', '--manifest-path', str(ROOT/'Metadata/Cargo.toml'),
                    '--release', '--locked'], cwd=str(ROOT), check=True)
    if before != inputs():
        raise ValueError('Metadata sources changed during the build.')
    result = subprocess.run([str(OUTPUT), '--help'], check=True, text=True, capture_output=True)
    for command in ('wcif-import', 'wcif-index', 'source-index', 'source-refresh', 'sync', 'query', 'usage-import', 'optimize'):
        if command not in result.stdout:
            raise ValueError('Metadata executable is missing an advertised explicit job.')
    write_json(MANIFEST, {'schema': 1, 'sha256': sha256(OUTPUT), 'bytes': OUTPUT.stat().st_size,
                        'source_inputs': before, 'service_installed': False,
                        'runtime': 'explicit standalone job; never loaded as a game script'})
    return verify()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(verify() if args.check else build(), indent=2))
