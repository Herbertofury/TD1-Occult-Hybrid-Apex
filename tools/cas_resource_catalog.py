"""Read-only CASP provenance and a pinned, loopback-only Studio package broker.

Catalog IDs from GetCatalogItem are NOT CASP TGIs. Callers supply an exact CASP
TGI and the effective resource's SHA256; absent that evidence we do not resolve.
Original packages are only read. Studio receives a fresh external cache copy.
The installed Studio contract opens a package, not a selected CASP resource.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CASP = 0x034AEECB
STBL = 0x220557DA
CAS_THUMB = 0x3C1AF1F2
MAX_RESOURCE = 32 * 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
MAX_RESPONSE = 512 * 1024
MAX_ROWS = 1024
CACHE_ROOT = Path(__file__).resolve().parents[1] / '.work' / 'cas-resource-cache'
STUDIO = Path(r'C:\Program Files (x86)\Sims 4 Studio\S4Studio.exe')
STUDIO_HASHES = {
    'S4Studio.exe': '08947983b273494ecfe84dec56fefe0953c353c84c2ae81c09f9d18819e2f4d1',
    'S4Studio.dll': '28d77b36473da0d0e0e6a34c9a15ffe497a26db399eade2d19dd42fcd5d90efd',
}
SHA = re.compile(r'[0-9a-f]{64}\Z')
TGI = re.compile(r'([0-9A-Fa-f]{8}):([0-9A-Fa-f]{8}):([0-9A-Fa-f]{16})\Z')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def key(value):
    match = TGI.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError('An exact type:group:instance TGI is required.')
    return tuple(int(part, 16) for part in match.groups())


def tgi(value):
    return '{:08X}:{:08X}:{:016X}'.format(*value)


def sha(value):
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ValueError('A lowercase SHA256 is required.')
    return value


def signature(path):
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _hashed_extent(path, offset, length):
    """Hash one complete stream and retain only its header/requested extent.

    The returned resource bytes participate in the same SHA as the complete
    source. File size/times are quick refusal evidence, never content proof.
    This also avoids hashing a file and then returning a separate raced read.
    """
    h, header, extent, position = hashlib.sha256(), bytearray(), bytearray(), 0
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
            if position < 96:
                header.extend(block[:96 - position])
            first, last = max(0, offset - position), min(len(block), offset + length - position)
            if first < last:
                extent.extend(block[first:last])
            position += len(block)
    return h.hexdigest(), bytes(header), bytes(extent)


class Package:
    """Stream the DBPF index; decompress only requested bounded resources."""
    def __init__(self, path, origin):
        if origin not in ('mod', 'ea', 'thumbnail-cache'):
            raise ValueError('An explicit mod/ea/thumbnail-cache origin is required.')
        self.path, self.origin = Path(path).resolve(strict=True), origin
        self.before, self.entries = signature(self.path), {}
        with self.path.open('rb') as stream:
            raw = stream.read(96)
            if len(raw) != 96 or raw[:4] != b'DBPF':
                raise ValueError('Not a DBPF package.')
            header = struct.unpack('<24I', raw)
            count, start, length = header[9], header[16] or header[10], header[11]
            if header[1] != 2 or header[2] not in (0, 1) or not 0 < count <= 1000000:
                raise ValueError('Unsupported DBPF version/count.')
            if start < 96 or length > 36 * count + 16 or start + length > self.before[2]:
                raise ValueError('Invalid DBPF index extent.')
            stream.seek(start)
            index = stream.read(length)
        position = 0
        def integer():
            nonlocal position
            if position + 4 > len(index):
                raise ValueError('Truncated DBPF index.')
            value = struct.unpack_from('<I', index, position)[0]
            position += 4
            return value
        flags = integer()
        if flags & ~7:
            raise ValueError('Unknown DBPF shared-index flags.')
        shared = [integer() if flags & (1 << bit) else None for bit in range(3)]
        for _ in range(count):
            kind, group, high = [value if value is not None else integer() for value in shared]
            low, offset, stored, size = integer(), integer(), integer(), integer()
            compression = (integer() & 0xffff) if stored & 0x80000000 else 0
            stored &= 0x7fffffff
            if compression == 0xffe0:
                continue
            item = (kind, group, (high << 32) | low)
            empty = offset == stored == size == compression == 0
            if (item in self.entries or (not empty and
                    (offset < 96 or offset + stored > self.before[2] or
                     not (offset + stored <= start or offset >= start + length)))):
                raise ValueError('Duplicate/invalid DBPF resource extent.')
            self.entries[item] = (offset, stored, size, compression)
        if position != length or signature(self.path) != self.before:
            raise ValueError('Unexplained index bytes or package changed during indexing.')
        self.source_sha256, hashed_header, hashed_index = _hashed_extent(self.path, start, length)
        if hashed_header != raw or hashed_index != index or signature(self.path) != self.before:
            raise ValueError('Package changed during content-bound indexing.')

    def read(self, item):
        if signature(self.path) != self.before:
            raise ValueError('Package changed since indexing.')
        offset, stored, size, compression = self.entries[item]
        if max(stored, size) > MAX_RESOURCE:
            raise ValueError('Resource exceeds its read bound.')
        observed_sha256, _header, raw = _hashed_extent(self.path, offset, stored)
        if (len(raw) != stored or signature(self.path) != self.before or
                observed_sha256 != self.source_sha256):
            raise ValueError('Package changed during resource read.')
        if compression == 0x5a42:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(raw, size + 1)
            if decoder.unused_data or decoder.unconsumed_tail or not decoder.eof:
                raise ValueError('Invalid/bounded zlib resource.')
        elif compression in (0xffff, 0xfffe) and raw[:2] in (b'\x10\xfb', b'\x50\xfb', b'\x90\xfb', b'\xd0\xfb'):
            raw = refpack(raw, size)
        elif compression not in (0, 0xffff):
            raise ValueError('Unsupported compression {:04X}.'.format(compression))
        if len(raw) != size:
            raise ValueError('Resource decoded-size mismatch.')
        return raw


class Reader:
    def __init__(self, raw):
        self.raw, self.position, self.limit = raw, 0, len(raw)

    def take(self, count):
        if count < 0 or self.position + count > self.limit:
            raise ValueError('Truncated metadata.')
        value = self.raw[self.position:self.position + count]
        self.position += count
        return value

    def value(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))[0]

    def count(self, maximum):
        count = self.value('i')
        if not 0 <= count <= maximum:
            raise ValueError('Unbounded metadata array.')
        return count


def refpack(raw, expected):
    """Independent bounded protocol reader; format reference Gibbed.RefPack.

    https://github.com/gibbed/Gibbed.RefPack/blob/master/Decompression.cs
    """
    r = Reader(raw)
    header = r.take(2)
    if int.from_bytes(header, 'big') & 0x1fff != 0x10fb or header[0] & 1:
        raise ValueError('Unsupported RefPack header.')
    declared = int.from_bytes(r.take(4 if header[0] & 0x80 else 3), 'big')
    if declared != expected or not 0 <= declared <= MAX_RESOURCE:
        raise ValueError('RefPack decoded size differs/exceeds its bound.')
    output = bytearray()
    while True:
        code = r.value('B')
        count, distance = 0, 0
        if code < 0x80:
            extra = r.value('B')
            literals, count = code & 3, ((code >> 2) & 7) + 3
            distance = ((code & 0x60) << 3) + extra + 1
        elif code < 0xc0:
            a, b = r.take(2)
            literals, count = a >> 6, (code & 63) + 4
            distance = ((a & 63) << 8) + b + 1
        elif code < 0xe0:
            a, b, c = r.take(3)
            literals, count = code & 3, ((code & 12) << 6) + c + 5
            distance = ((code & 16) << 12) + (a << 8) + b + 1
        else:
            literals = ((code & 31) + 1) * 4 if code < 0xfc else code & 3
        if len(output) + literals + count > expected:
            raise ValueError('RefPack command exceeds its decoded bound.')
        output.extend(r.take(literals))
        if count:
            if distance > len(output):
                raise ValueError('RefPack back-reference precedes output.')
            start = len(output) - distance
            block = bytes(output[start:start + min(count, distance)])
            output.extend((block * ((count + len(block) - 1) // len(block)))[:count])
        if code >= 0xfc:
            if len(output) != expected or r.position != len(raw):
                raise ValueError('RefPack stop length/trailing bytes differ.')
            return bytes(output)


def casp_metadata(raw):
    if not 64 <= len(raw) <= 1024 * 1024:
        raise ValueError('CASP length is invalid.')
    r = Reader(raw)
    version, table = r.value('I'), r.value('I') + 8
    if version not in range(44, 53) or not 64 <= table < len(raw):
        raise ValueError('CASP version/reference-table layout is unverified.')
    r.limit = table
    if r.value('i') != 0:
        raise ValueError('CASP preset data is unsupported.')
    length = 0
    for n in range(5):
        byte = r.value('B')
        length |= (byte & 127) << (7 * n)
        if not byte & 128:
            break
    else:
        raise ValueError('Invalid CASP name length.')
    if length > 4096 or length % 2:
        raise ValueError('Invalid CASP name length.')
    name = r.take(length).decode('utf-16-be')
    r.take(16)
    if version >= 50:
        r.take(2)
    r.take(r.count(512) * 8 if version >= 51 else 16)
    r.take(8)
    r.take(r.count(4096) * 6)
    r.take(4)
    title, description = r.value('I'), r.value('I')
    r.take(5)
    body = r.value('I')
    r.take(4)
    age_gender, species = r.value('I'), r.value('I')
    pack = r.value('h')
    r.take(10)
    r.take(r.value('B') * 4)
    r.take(1)
    thumb_index = r.value('B')
    count = raw[table]
    if table + 1 + 16 * count != len(raw):
        raise ValueError('Invalid CASP IGT reference table.')
    refs = []
    for i in range(count):
        instance, group, kind = struct.unpack_from('<QII', raw, table + 1 + 16 * i)
        refs.append(tgi((kind, group, instance)))
    if thumb_index >= count and thumb_index != 0:
        raise ValueError('CASP thumbnail reference index is invalid.')
    return {'version': version, 'internal_name': name or None, 'title_key': title,
            'description_key': description, 'body_type': body, 'age_gender': age_gender,
            'species': species, 'pack_id': pack,
            'variant_thumbnail_tgi': refs[thumb_index] if thumb_index < count else None}


def stbl_strings(raw):
    r = Reader(raw)
    if r.take(4) != b'STBL' or r.value('H') != 5 or r.value('B') != 0:
        raise ValueError('Unsupported STBL header.')
    count = r.value('Q')
    r.take(2)
    declared = r.value('I')
    if count > 500000 or declared > MAX_RESOURCE:
        raise ValueError('Unbounded STBL.')
    values = {}
    for _ in range(count):
        ident = r.value('I')
        r.take(1)
        value = r.take(r.value('H')).decode('utf-8')
        if ident in values:
            raise ValueError('Duplicate STBL string identity.')
        values[ident] = value
    if r.position != len(raw):
        raise ValueError('Unexplained STBL bytes.')
    return values


def thumbnail_png(raw):
    """Decode genuine PNG/JPEG or TS4 JPEG+ALFA PNG; never emit a placeholder."""
    from PIL import Image
    if not raw.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8')) or len(raw) > MAX_IMAGE:
        raise ValueError('Unsupported/encrypted thumbnail encoding.')
    with Image.open(io.BytesIO(raw)) as image:
        if not 0 < image.width <= 512 or not 0 < image.height <= 512:
            raise ValueError('Thumbnail dimensions exceed 512.')
        image.load()
        rgba = image.convert('RGBA')
    if raw.startswith(b'\xff\xd8') and raw[24:28] == b'ALFA':
        size = struct.unpack_from('>I', raw, 28)[0]
        if not 0 < size <= MAX_IMAGE or 32 + size > len(raw):
            raise ValueError('Invalid thumbnail alpha extent.')
        with Image.open(io.BytesIO(raw[32:32 + size])) as alpha:
            if alpha.size != rgba.size or alpha.format != 'PNG':
                raise ValueError('Thumbnail alpha dimensions/format mismatch.')
            alpha.load()
            rgba.putalpha(alpha.convert('L'))
    output = io.BytesIO()
    rgba.save(output, format='PNG')
    result = output.getvalue()
    if len(result) > MAX_IMAGE:
        raise ValueError('Decoded thumbnail exceeds image bound.')
    return result, rgba.width, rgba.height


def safe_cache_file(root, relative):
    no_redirected_ancestors(root)
    root = Path(root).resolve(strict=True)
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('Invalid cache-relative path.')
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('Cache contains a redirected path.')
    resolved = current.resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file() or resolved.stat().st_nlink != 1:
        raise ValueError('Cache file is not an independent regular copy.')
    return resolved


def write_cache(root, relative, raw):
    target = Path(root) / relative
    ensure_directory(root, target.parent.relative_to(root))
    if target.exists():
        if safe_cache_file(root, relative).read_bytes() != raw:
            raise ValueError('Existing content-addressed cache differs.')
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(raw)
    try:
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def ensure_directory(root, relative):
    root = Path(root)
    no_redirected_ancestors(root)
    root.mkdir(parents=True, exist_ok=True)
    current = root
    for part in Path(relative).parts:
        if part == '..':
            raise ValueError('Cache directory escapes its root.')
        current = current / part
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('Cache directory is redirected.')
        current.mkdir(exist_ok=True)
    return current


def no_redirected_ancestors(path):
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('Cache path contains parent traversal.')
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or getattr(ancestor, 'is_junction', lambda: False)():
            raise ValueError('Cache ancestor is redirected.')


def copy_package(package, root):
    directory = ensure_directory(root, 'packages')
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
        temp = Path(output.name)
        h = hashlib.sha256()
        with package.path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
                output.write(block)
    try:
        if signature(package.path) != package.before or h.hexdigest() != package.source_sha256:
            raise ValueError('Original package changed during copy.')
        package_hash = h.hexdigest()
        relative = 'packages/' + package_hash + '.package'
        target = Path(root) / relative
        if target.exists():
            if file_hash(safe_cache_file(root, relative)) != package_hash:
                raise ValueError('Existing package cache hash differs.')
        else:
            os.replace(temp, target)
        return relative, package_hash
    finally:
        temp.unlink(missing_ok=True)


def studio_executable():
    for name, expected in STUDIO_HASHES.items():
        path = STUDIO.parent / name
        if not path.is_file() or path.is_symlink() or file_hash(path) != expected:
            raise ValueError('The verified installed Sims 4 Studio build is unavailable/changed.')
    return STUDIO


def prepare(sources, requests, cache_dir, locale=0):
    """Trusted CLI preparation; HTTP clients cannot supply source paths or keys."""
    if (type(locale) is not int or not 0 <= locale <= 255 or
            not isinstance(requests, list) or len(requests) > MAX_ROWS or
            not isinstance(sources, list) or len(sources) > 10000):
        raise ValueError('Invalid locale/catalog bound.')
    for request in requests:
        if not isinstance(request, dict) or not {'resource_tgi', 'effective_resource_sha256'} <= set(request):
            raise ValueError('Every request needs an exact CASP TGI and effective-resource SHA256.')
        key(request['resource_tgi'])
        sha(request['effective_resource_sha256'])
        if 'body_type' in request and type(request['body_type']) is not int:
            raise ValueError('Equipped body type must be an exact integer.')
    cache = Path(cache_dir).absolute()
    ensure_directory(cache, '')
    cache = cache.resolve()
    packages = [Package(source['path'], source['origin']) for source in sources]
    names, name_errors = {}, []
    for package in packages:
        for item in package.entries:
            if item[0] != STBL or item[2] >> 56 != locale:
                continue
            try:
                data = package.read(item)
                for ident, value in stbl_strings(data).items():
                    names.setdefault(ident, []).append((value, tgi(item), digest(data)))
            except (ValueError, UnicodeError) as error:
                name_errors.append(str(error))
    try:
        studio_executable()
        studio_reason = None
    except (OSError, ValueError) as error:
        studio_reason = str(error)
    rows, records, copied = [], {}, {}
    for request in requests:
        item, expected = key(request['resource_tgi']), sha(request['effective_resource_sha256'])
        if item[0] != CASP:
            raise ValueError('Only exact CASP resources are supported.')
        ident = digest((tgi(item) + '\n' + expected).encode('ascii'))
        if ident in records:
            raise ValueError('Duplicate requested effective CASP identity.')
        row = {'resource_id': ident, 'resource_tgi': tgi(item),
               'effective_resource_sha256': expected, 'status': 'unresolved',
               'display_name': None, 'name_status': 'unresolved',
               'preferred_name': None, 'preferred_name_status': 'unresolved',
               'package_name': None, 'code_name': None, 'body_type': None,
               'provenance': None, 'reason': None,
               'thumbnail': {'status': 'unresolved', 'url': None, 'sha256': None,
                             'width': None, 'height': None, 'reason': 'Exact thumbnail unavailable.'},
               'studio_open': {'status': 'unavailable', 'selection': 'containing-package',
                               'resource_selection_supported': False, 'reason': 'Provenance unresolved.'}}
        matching, errors = [], []
        for package in packages:
            if package.origin == 'thumbnail-cache' or item not in package.entries:
                continue
            try:
                data = package.read(item)
                if digest(data) == expected:
                    matching.append((package, data))
            except ValueError as error:
                errors.append(str(error))
        record = {'row': row, 'package_file': None, 'thumbnail_file': None}
        if len(matching) != 1:
            row['status'] = 'ambiguous' if len(matching) > 1 else 'unresolved'
            row['reason'] = 'Multiple packages contain the effective bytes.' if matching else 'No package matches the effective CASP hash.'
            if errors:
                row['reason'] += ' ' + '; '.join(errors[:3])
        else:
            package, data = matching[0]
            try:
                meta = casp_metadata(data)
                if 'body_type' in request and request['body_type'] != meta['body_type']:
                    raise ValueError('Equipped body type disagrees with the CASP metadata.')
                if package.path not in copied:
                    copied[package.path] = copy_package(package, cache)
                relative, package_hash = copied[package.path]
                record['package_file'] = relative
                row.update(status='resolved', body_type=meta['body_type'], metadata=meta)
                row['provenance'] = {'origin': package.origin, 'package_sha256': package_hash,
                                     'resource_sha256': expected, 'package_filename': package.path.name,
                                     'relationship': 'matching-container',
                                     'effective_load_source_verified': False}
                row['package_name'] = package.path.name
                row['code_name'] = meta['internal_name'] or None
                values = names.get(meta['title_key'], []) if meta['title_key'] else []
                distinct = {entry[0] for entry in values if entry[0] and entry[0].strip()}
                if len(distinct) == 1 and not name_errors:
                    row['preferred_name'], row['preferred_name_status'] = next(iter(distinct)), 'localized-title'
                    row['name_evidence'] = [{'string_table_tgi': entry[1], 'resource_sha256': entry[2]} for entry in values]
                elif package.origin == 'mod':
                    row['preferred_name'], row['preferred_name_status'] = package.path.name, 'cc-package-filename'
                    row['name_reason'] = 'Localized title unavailable/conflicting; exact original CC package filename.'
                elif row['code_name']:
                    row['preferred_name'], row['preferred_name_status'] = row['code_name'], 'casp-internal-name'
                    row['name_reason'] = 'Localized title unavailable/conflicting; genuine internal CASP name.'
                row['display_name'], row['name_status'] = row['preferred_name'], row['preferred_name_status']
                row['studio_open'].update(status='ready' if studio_reason is None else 'unavailable', reason=studio_reason)
                gender = request.get('gender')
                if gender not in (None, 'male', 'female'):
                    raise ValueError('Thumbnail gender must be male/female or absent.')
                thumb_keys = [(CAS_THUMB, group, item[2]) for group in
                              ([0x102] if gender == 'male' else [2] if gender == 'female' else [2, 0x102])]
                candidates, thumbnail_errors = [], []
                for provider in packages:
                    for thumb_key in thumb_keys:
                        if thumb_key in provider.entries:
                            try:
                                raw = provider.read(thumb_key)
                                pixels, width, height = thumbnail_png(raw)
                                candidates.append((pixels, width, height, tgi(thumb_key), digest(raw)))
                            except (ValueError, OSError) as error:
                                thumbnail_errors.append(str(error))
                if thumbnail_errors:
                    row['thumbnail']['reason'] = 'An exact thumbnail candidate could not be verified: ' + '; '.join(thumbnail_errors[:3])
                elif candidates and len({digest(candidate[0]) for candidate in candidates}) == 1:
                    pixels, width, height, thumb_key, resource_hash = candidates[0]
                    image_hash = digest(pixels)
                    relative = 'thumbnails/' + image_hash + '.png'
                    write_cache(cache, relative, pixels)
                    record['thumbnail_file'] = relative
                    row['thumbnail'] = {'status': 'resolved', 'url': '/v1/resources/' + ident + '/thumbnail',
                                        'sha256': image_hash, 'width': width, 'height': height, 'reason': None,
                                        'resource_tgi': thumb_key, 'resource_sha256': resource_hash,
                                        'association': 'installed-studio-casp-key'}
                elif candidates:
                    row['thumbnail']['reason'] = 'Conflicting exact thumbnail resources; effective thumbnail is unproved.'
            except (ValueError, OSError, UnicodeError) as error:
                row.update(status='unresolved', reason=str(error), display_name=None,
                           name_status='unresolved', preferred_name=None,
                           preferred_name_status='unresolved', package_name=None, code_name=None)
                row['studio_open'].update(status='unavailable', reason=str(error))
        row['cache_proof'] = digest(canonical(record))
        rows.append(row)
        records[ident] = record
    result = {'schema': 1, 'items': rows}
    if len(canonical(result)) > MAX_RESPONSE:
        raise ValueError('Catalog exceeds the 512 KiB transport bound.')
    manifest = {'schema': 1, 'records': records}
    encoded = canonical(manifest)
    manifest_hash = digest(encoded)
    relative = 'catalog-' + manifest_hash + '.json'
    write_cache(cache, relative, encoded)
    return {'manifest': str(cache / relative), 'manifest_sha256': manifest_hash,
            'catalog': result}


class Broker:
    def __init__(self, manifest, expected_sha256):
        self.manifest = Path(manifest).resolve(strict=True)
        self.cache = self.manifest.parent
        self.manifest_hash = sha(expected_sha256)
        if self.manifest.stat().st_size > 2 * MAX_RESPONSE:
            raise ValueError('Pinned catalog manifest hash/size differs.')
        raw = self.manifest.read_bytes()
        if digest(raw) != self.manifest_hash:
            raise ValueError('Pinned catalog manifest hash/size differs.')
        payload = json.loads(raw)
        if payload.get('schema') != 1 or not isinstance(payload.get('records'), dict) or len(payload['records']) > MAX_ROWS:
            raise ValueError('Unsupported catalog manifest.')
        self.records = payload['records']
        for ident, record in self.records.items():
            sha(ident)
            row = record['row']
            if row['resource_id'] != ident:
                raise ValueError('Catalog row identity differs.')
            proof = row.pop('cache_proof')
            expected = digest(canonical(record))
            row['cache_proof'] = proof
            if proof != expected:
                raise ValueError('Catalog cache proof differs.')
        self.catalog = canonical({'schema': 1, 'items': [r['row'] for r in self.records.values()]})
        if len(self.catalog) > MAX_RESPONSE:
            raise ValueError('Catalog transport exceeds its bound.')

    def thumbnail(self, ident):
        record = self.records[sha(ident)]
        row = record['row']['thumbnail']
        if row['status'] != 'resolved' or not record['thumbnail_file']:
            raise ValueError('Thumbnail is unresolved.')
        path = safe_cache_file(self.cache, record['thumbnail_file'])
        if path.stat().st_size > MAX_IMAGE:
            raise ValueError('Thumbnail cache exceeds its byte bound.')
        raw = path.read_bytes()
        if len(raw) > MAX_IMAGE or digest(raw) != row['sha256']:
            raise ValueError('Thumbnail cache hash differs.')
        return raw

    def open(self, ident, proof, launcher=None):
        record = self.records[sha(ident)]
        row = record['row']
        if sha(proof) != row['cache_proof'] or row['status'] != 'resolved' or row['studio_open']['status'] != 'ready':
            raise ValueError('Studio open requires this resolved, pinned cache proof.')
        manifest = safe_cache_file(self.cache, self.manifest.name)
        if manifest.stat().st_size > 2 * MAX_RESPONSE or file_hash(manifest) != self.manifest_hash:
            raise ValueError('Pinned catalog manifest changed before open.')
        if row['thumbnail']['status'] == 'resolved':
            self.thumbnail(ident)
        executable = studio_executable()
        source = safe_cache_file(self.cache, record['package_file'])
        if file_hash(source) != row['provenance']['package_sha256']:
            raise ValueError('Sealed package cache hash differs before copy.')
        relative = 'open/' + ident + '/' + uuid.uuid4().hex + '.package'
        ensure_directory(self.cache, 'open/' + ident)
        target = self.cache / relative
        # Copy and verify the bytes actually passed to Studio, so original paths
        # and mutable sealed-cache files cannot be opened through this endpoint.
        shutil.copyfile(source, target)
        target = safe_cache_file(self.cache, relative)
        if file_hash(target) != row['provenance']['package_sha256']:
            target.unlink()
            raise ValueError('Package cache/copy hash differs.')
        (launcher or subprocess.Popen)([str(executable), str(target)], shell=False,
                                       cwd=str(executable.parent))
        return {'ok': True, 'resource_id': ident, 'selection': 'containing-package',
                'resource_selection_supported': False}


def handler(broker):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def allowed(self):
            return (self.headers.get('Host') in ('127.0.0.1:8022', 'localhost:8022') and
                    self.headers.get('Origin') in (None, 'http://127.0.0.1:8022', 'http://localhost:8022'))

        def reply(self, status, raw, kind='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if not self.allowed():
                self.reply(403, canonical({'ok': False, 'reason': 'Loopback origin required.'}))
                return
            if self.path == '/v1/resources':
                self.reply(200, broker.catalog)
                return
            match = re.fullmatch(r'/v1/resources/([0-9a-f]{64})/thumbnail', self.path)
            try:
                if match is None:
                    raise ValueError('Unknown typed route.')
                self.reply(200, broker.thumbnail(match.group(1)), 'image/png')
            except (KeyError, ValueError, OSError) as error:
                self.reply(404, canonical({'ok': False, 'reason': str(error)}))

        def do_POST(self):
            try:
                if not self.allowed() or self.path != '/v1/open':
                    raise ValueError('Loopback typed open route required.')
                if self.headers.get('Content-Type') != 'application/json' or self.headers.get('Transfer-Encoding'):
                    raise ValueError('A bounded JSON request is required.')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 512:
                    raise ValueError('Invalid open-request length.')
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict) or set(value) != {'resource_id', 'cache_proof'}:
                    raise ValueError('Only exact resource_id/cache_proof fields are accepted.')
                self.reply(200, canonical(broker.open(value['resource_id'], value['cache_proof'])))
            except (KeyError, ValueError, OSError) as error:
                self.reply(409, canonical({'ok': False, 'reason': str(error)}))
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('prepare')
    build.add_argument('--input', required=True, help='JSON with sources and exact hash-bound CASP requests.')
    build.add_argument('--cache', default=str(CACHE_ROOT), help='Cache beneath the repository external .work cache.')
    build.add_argument('--locale', type=int, default=0)
    serve = commands.add_parser('serve')
    serve.add_argument('--manifest', required=True)
    serve.add_argument('--expected-manifest-sha256', required=True)
    args = parser.parse_args(argv)
    cache_path = Path(args.cache if args.command == 'prepare' else args.manifest).absolute()
    no_redirected_ancestors(cache_path)
    cache_path, fixed_root = cache_path.resolve(), CACHE_ROOT.resolve()
    if cache_path != fixed_root and fixed_root not in cache_path.parents:
        raise ValueError('CLI cache/manifest must stay within the fixed external .work CAS resource cache.')
    if args.command == 'prepare':
        raw = Path(args.input).read_bytes()
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Preparation input exceeds its bound.')
        data = json.loads(raw)
        result = prepare(data['sources'], data['requests'], args.cache, args.locale)
        print(json.dumps(result, ensure_ascii=False))
        return result
    broker = Broker(args.manifest, args.expected_manifest_sha256)
    with ThreadingHTTPServer(('127.0.0.1', 8022), handler(broker)) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
