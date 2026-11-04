"""Fetch a pinned, private offline Python 3.7 bytecode compiler; no global install."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

URL = 'https://www.python.org/ftp/python/3.7.9/python-3.7.9-embed-amd64.zip'
SHA256 = '18627a097adf47829a847053febac5532376075243e233bd9ec61d6ea09dee1f'
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / '.work' / 'build-python37'


def fetch(output=DEFAULT_OUTPUT, archive=None):
    output = Path(output).absolute()
    if output.exists():
        raise ValueError('Private compiler output already exists; refusing to overwrite it.')
    if archive:
        raw = Path(archive).read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=30) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Python compiler archive does not match the pinned official distribution.')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        infos = bundle.infolist()
        if len(infos) > 100 or sum(info.file_size for info in infos) > 64 * 1024 * 1024:
            raise ValueError('Unexpected compiler archive extent.')
        for info in infos:
            if '/' in info.filename or '\\' in info.filename or info.filename in ('.', '..') or info.is_dir():
                raise ValueError('Compiler archive must contain only flat regular files.')
        output.mkdir(parents=True, exist_ok=False)
        for info in infos:
            with (output / info.filename).open('xb') as stream:
                stream.write(bundle.read(info))
    # Embedded _pth isolation ignores PYTHONHASHSEED. Retain the original config
    # under a non-active name; the builder supplies a private PYTHONHOME, disables
    # site/user imports and fixes hash seed so frozenset constants are reproducible.
    (output / 'python37._pth').rename(output / 'python37._pth.compiler-disabled')
    return {'ok': True, 'compiler': str(output / 'python.exe'), 'archive_sha256': SHA256,
            'source': URL, 'scope': 'private build-time compiler only; no global Python/PATH changes'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    print(json.dumps(fetch(args.output, args.archive), indent=2))
