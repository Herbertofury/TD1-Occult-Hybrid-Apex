"""Read six exact installed client texture keys without exporting game assets.

Called only by the artwork worker. Indexes and requested image extents are
bounded; no whole-package hashing, writes, Sim access or render-thread I/O.
Conflicting installed resources are reported rather than choosing a lookalike.
"""
import hashlib
import os
from pathlib import Path
import re
import struct
import zlib

MAX_IMAGE = 128 * 1024
MAX_INDEX = 36 * 1000000 + 16
MAX_INDEX_TOTAL = 512 * 1024 * 1024


def unlinked(path):
    path = Path(os.path.abspath(str(path)))
    for part in (path,) + tuple(path.parents):
        info = part.lstat()
        if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked installed artwork input is unsupported.')
    return path


def game_root(dll_path):
    directory = unlinked(dll_path)
    if tuple(part.lower() for part in directory.parts[-4:]) != ('game', 'bin', 'python', 'dlls'):
        raise ValueError('Installed artwork requires the game Python/DLLs path.')
    root = directory.parents[3]
    if not unlinked(root / 'Game' / 'Bin' / 'TS4_x64.exe').is_file():
        raise ValueError('The installed game executable is absent.')
    return root


def signature(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def containers(root):
    directories = [root / 'Data' / 'Client']
    directories.extend(path for path in root.iterdir() if re.fullmatch(r'(?:EP|GP|SP)\d+', path.name, re.I))
    result = []
    for directory in directories:
        if not directory.exists():
            continue
        unlinked(directory)
        for path in directory.iterdir():
            if re.fullmatch(r'Client(?:Full|Delta)Build\d+\.package', path.name, re.I):
                if not unlinked(path).is_file():
                    raise ValueError('Installed artwork container is not a regular file.')
                result.append(path)
    if len(result) > 4096:
        raise ValueError('Installed artwork container count exceeds its bound.')
    return sorted(result)


def selected(stream, wanted, budget):
    """Return exact indexed extents, rejecting malformed/duplicate records."""
    raw = stream.read(96)
    if len(raw) != 96 or raw[:4] != b'DBPF':
        raise ValueError('Installed artwork requires a DBPF container.')
    h = struct.unpack('<24I', raw)
    count, start, length = h[9], h[16] or h[10], h[11]
    size = os.fstat(stream.fileno()).st_size
    if h[1] != 2 or h[2] not in (0, 1) or not 0 <= count <= 1000000:
        raise ValueError('Unsupported installed artwork DBPF version/count.')
    if count == 0:
        if start or length or size != 96:
            raise ValueError('Invalid empty installed artwork container.')
        return {}, budget, hashlib.sha256(raw).hexdigest()
    if start < 96 or not 4 <= length <= min(MAX_INDEX, 36 * count + 16) or start + length > size or length > budget:
        raise ValueError('Installed artwork index exceeds its bound.')
    stream.seek(start)
    index = stream.read(length)
    position = 0
    def integer():
        nonlocal position
        if position + 4 > len(index):
            raise ValueError('Truncated installed artwork index.')
        value = struct.unpack_from('<I', index, position)[0]
        position += 4
        return value
    flags = integer()
    if flags & ~7:
        raise ValueError('Unsupported installed artwork shared index.')
    shared = [integer() if flags & (1 << bit) else None for bit in range(3)]
    matches = {}
    for _ in range(count):
        kind, group, high = [value if value is not None else integer() for value in shared]
        low, offset, stored, decoded = integer(), integer(), integer(), integer()
        extended = integer() if stored & 0x80000000 else 0
        compression = extended & 0xffff
        stored &= 0x7fffffff
        identity = kind, group, (high << 32) | low
        if identity not in wanted or compression == 0xffe0:
            continue
        if (identity in matches or extended >> 16 not in (0, 1) or
                not 0 < stored <= MAX_IMAGE or not 0 < decoded <= MAX_IMAGE or offset < 96 or
                offset + stored > size or not (offset + stored <= start or offset >= start + length)):
            raise ValueError('Installed artwork resource extent/identity differs.')
        matches[identity] = offset, stored, decoded, compression
    if position != length:
        raise ValueError('Trailing installed artwork index bytes.')
    return matches, budget - length, hashlib.sha256(raw + index).hexdigest()


def decode(raw, size, compression):
    if compression == 0x5a42:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(raw, size + 1)
        if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise ValueError('Unresolved installed artwork zlib stream.')
    elif compression in (0xffff, 0xfffe) and raw[:2] in (b'\x10\xfb', b'\x50\xfb', b'\x90\xfb', b'\xd0\xfb'):
        from .saved_occult_extras import refpack
        raw = refpack(raw, size)
    elif compression not in (0, 0xffff):
        raise ValueError('Unsupported installed artwork compression.')
    if len(raw) != size:
        raise ValueError('Installed artwork decoded size differs.')
    return raw


def read(root, identities):
    identities = frozenset(identities)
    if (not 0 < len(identities) <= 6 or
            any(len(key) != 3 or any(type(v) is not int for v in key) or
                not 0 < key[0] <= 0xffffffff or not 0 <= key[1] <= 0xffffffff or
                not 0 < key[2] <= 0xffffffffffffffff for key in identities)):
        raise ValueError('One to six exact installed image keys are required.')
    root = unlinked(root)
    result, budget = {}, MAX_INDEX_TOTAL
    for path in containers(root):
        before = signature(path)
        with path.open('rb') as stream:
            matches, budget, index_sha = selected(stream, identities, budget)
            for identity, (offset, stored, size, compression) in matches.items():
                stream.seek(offset)
                raw = stream.read(stored)
                if len(raw) != stored:
                    raise ValueError('Truncated installed artwork payload.')
                image = decode(raw, size, compression)
                digest = hashlib.sha256(image).hexdigest()
                source = dict(container=str(path.relative_to(root)), index_sha256=index_sha,
                              offset=offset, stored_bytes=stored, compression=compression)
                row = result.setdefault(identity, dict(raw=image, sha256=digest, sources=[]))
                if row['sha256'] != digest:
                    row['conflict'] = True
                row['sources'].append(source)
        if signature(path) != before:
            raise ValueError('Installed artwork container changed during its read.')
    return result
