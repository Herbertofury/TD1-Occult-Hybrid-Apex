# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded read-only DBPF 2.1 access for explicitly pinned large packages.

Index rows stream from one open descriptor; only requested keys are retained.
The caller must supply a whole-file SHA-256 and keep the file stable. No game
assets, temporary files or catalogs are written. This is not a filesystem
snapshot and cannot defeat a malicious concurrent writer that restores state.
"""
import hashlib
from contextlib import contextmanager
import os
import re
import stat
import struct
import threading
import zlib
from dataclasses import dataclass

MAX_PACKAGE = 8 * 1024 * 1024 * 1024
MAX_INDEX = 128 * 1024 * 1024
MAX_ROWS = 250_000
MAX_KEYS = 128
MAX_MATCHES = 32
MAX_PAYLOAD_BUDGET = 64 * 1024 * 1024
HASH_CHUNK = 1024 * 1024
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_TGI = re.compile(r'[0-9A-F]{8}:[0-9A-F]{8}:[0-9A-F]{16}\Z')


class PackageError(ValueError):
    pass


class MissingResource(PackageError):
    pass


class AmbiguousResource(PackageError):
    pass


class UnsupportedResource(PackageError):
    pass


@dataclass(frozen=True)
class ResourceRow:
    key: tuple
    ordinal: int
    offset: int
    stored_size: int
    memory_size: int
    compression: int
    committed: int
    deleted: bool


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _path_identity(info):
    # Windows lstat and fstat can expose different ctime meanings for one file.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _valid_key(key):
    return (isinstance(key, tuple) and len(key) == 3 and all(type(v) is int for v in key)
            and 0 <= key[0] <= 0xffffffff and 0 <= key[1] <= 0xffffffff
            and 0 <= key[2] <= 0xffffffffffffffff)


def parse_tgi(text):
    """Parse the preview catalog's canonical uppercase resource identifier."""
    if not isinstance(text, str) or not _TGI.fullmatch(text):
        raise PackageError('invalid canonical TGI')
    return tuple(int(field, 16) for field in text.split(':'))


def payload_budget(row):
    # Python's zlib output and the RefPack bytearray-to-bytes conversion can
    # temporarily hold two expanded buffers. This is accounting, not an RSS cap.
    copies = 2 if row.compression in (0x5a42, 0xffff) else 1
    return row.stored_size + row.memory_size * copies


def decode_refpack(data, expected):
    if not isinstance(data, bytes) or type(expected) is not int or not 0 <= expected <= MAX_PAYLOAD_BUDGET or len(data) + expected * 2 > MAX_PAYLOAD_BUDGET:
        raise PackageError('invalid RefPack input')
    pos = 0
    def byte():
        nonlocal pos
        if pos >= len(data):
            raise PackageError('truncated RefPack')
        b = data[pos]; pos += 1
        return b
    flags = byte()
    if byte() != 0xfb:
        raise PackageError('unsupported RefPack header')
    declared = 0
    for _ in range(4 if flags & 0x80 else 3):
        declared = declared * 256 + byte()
    if declared != expected:
        raise PackageError('RefPack size mismatch')
    out = bytearray(expected)
    used = 0
    ended = False
    while pos < len(data) and not ended:
        op = byte()
        length = distance = 0
        if op <= 0x7f:
            b = byte(); literals = op & 3; length = ((op & 0x1c) >> 2) + 3; distance = ((op & 0x60) << 3) + b + 1
        elif op <= 0xbf:
            b = byte(); c = byte(); literals = b >> 6; length = (op & 0x3f) + 4; distance = ((b & 0x3f) << 8) + c + 1
        elif op <= 0xdf:
            b = byte(); c = byte(); d = byte(); literals = op & 3; length = ((op & 0x0c) << 6) + d + 5; distance = ((op & 0x10) << 12) + (b << 8) + c + 1
        elif op <= 0xfb:
            literals = ((op & 0x1f) << 2) + 4
        else:
            literals = op & 3; ended = True
        if pos + literals > len(data) or used + literals + length > expected:
            raise PackageError('invalid RefPack extent')
        out[used:used + literals] = data[pos:pos + literals]; pos += literals; used += literals
        if length and distance > used:
            raise PackageError('invalid RefPack distance')
        # Exponentially extend overlapping backreferences without one Python
        # iteration per output byte. A single RefPack command copies <= 1028.
        start = used - distance
        while length:
            amount = min(used - start, length)
            out[used:used + amount] = out[start:start + amount]
            used += amount; length -= amount
    if not ended or used != expected or pos != len(data):
        raise PackageError('incomplete RefPack')
    return bytes(out)


class PinnedPackage:
    """Read bounded selections from a SHA-pinned package on one open handle."""
    def __init__(self, path, expected_sha256):
        if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
            raise PackageError('whole-file SHA-256 required')
        self._file = None
        self._lock = threading.Lock()
        self.source_sha256 = expected_sha256
        self.max_read = 0
        try:
            before = os.lstat(path)
            if stat.S_ISLNK(before.st_mode) or getattr(before, 'st_file_attributes', 0) & 0x400:
                raise PackageError('reparse point or symlink not supported')
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(path, flags)
            try:
                self._file = os.fdopen(fd, 'rb', buffering=65536)
            except BaseException:
                os.close(fd)
                raise
            info = os.fstat(self._file.fileno())
            if not stat.S_ISREG(info.st_mode) or not 96 <= info.st_size <= MAX_PACKAGE or _path_identity(before) != _path_identity(info):
                raise PackageError('invalid or changed package')
            self._signature = _signature(info)
            self.source_size = info.st_size
            if self._hash() != expected_sha256:
                raise PackageError('source digest mismatch')
            self._check()
            header = self._read_at(0, 96)
            if header[:4] != b'DBPF' or struct.unpack_from('<II', header, 4) != (2, 1):
                raise PackageError('unsupported DBPF')
            self.row_count, low, self.index_size = struct.unpack_from('<III', header, 36)
            self.index_offset = struct.unpack_from('<I', header, 64)[0] or low
            if self.row_count > MAX_ROWS or self.index_size > MAX_INDEX or self.index_offset + self.index_size > self.source_size:
                raise PackageError('index limit or extent')
            if self.row_count or self.index_size:
                if self.index_offset < 96 or self.index_size < 4:
                    raise PackageError('invalid index extent')
            elif self.index_offset > self.source_size:
                raise PackageError('invalid empty index')
            self._check()
        except BaseException:
            self.close()
            raise

    def close(self):
        with self._operation():
            if self._file is not None:
                self._file.close(); self._file = None

    @contextmanager
    def _operation(self):
        # One shared file cursor; reject overlapping calls instead of mixing reads.
        if not self._lock.acquire(blocking=False):
            raise PackageError('package operation already active')
        try:
            yield
        finally:
            self._lock.release()

    def __enter__(self):
        if self._file is None:
            raise PackageError('closed package')
        return self

    def __exit__(self, *_):
        self.close()

    def _check(self):
        if self._file is None or _signature(os.fstat(self._file.fileno())) != self._signature:
            raise PackageError('source changed or closed')

    def _read(self, length):
        self.max_read = max(self.max_read, length)
        data = self._file.read(length)
        if len(data) != length:
            raise PackageError('truncated package')
        return data

    def _read_at(self, offset, length):
        if offset < 0 or length < 0 or offset + length > self.source_size:
            raise PackageError('read outside package')
        self._file.seek(offset)
        return self._read(length)

    def _hash(self):
        self._file.seek(0)
        digest = hashlib.sha256()
        remaining = self.source_size
        while remaining:
            data = self._read(min(HASH_CHUNK, remaining))
            digest.update(data); remaining -= len(data)
        return digest.hexdigest()

    def iter_rows(self):
        """Yield rows; exhaust or close the iterator before another operation."""
        with self._operation():
            yield from self._iter_rows_unlocked()

    def _iter_rows_unlocked(self):
        self._check()
        if not self.row_count and not self.index_size:
            return
        self._file.seek(self.index_offset)
        end = self.index_offset + self.index_size
        def take(n):
            if self._file.tell() + n > end:
                raise PackageError('truncated index')
            return self._read(n)
        def u32():
            return struct.unpack('<I', take(4))[0]
        def u16():
            return struct.unpack('<H', take(2))[0]
        flags = u32()
        if flags & ~7:
            raise PackageError('unsupported index flags')
        shared = [u32() if flags & (1 << n) else None for n in range(3)]
        if self.row_count * 16 > end - self._file.tell():
            raise PackageError('index count exceeds extent')
        for ordinal in range(self.row_count):
            type_id, group, high = [shared[n] if shared[n] is not None else u32() for n in range(3)]
            low, offset, size_bits, memory = u32(), u32(), u32(), u32()
            extended = bool(size_bits & 0x80000000); stored = size_bits & 0x7fffffff
            compression, committed = (u16(), u16()) if extended else (0, 1)
            deleted = compression == 0xffe0
            if not deleted and (offset + stored > self.source_size or
                    (stored and (offset < 96 or offset < end and offset + stored > self.index_offset))):
                raise PackageError('resource outside package or overlapping index')
            yield ResourceRow((type_id, group, (high << 32) | low), ordinal, offset, stored, memory, compression, committed, deleted)
        if self._file.tell() != end:
            raise PackageError('unsupported index trailing bytes')
        self._check()

    def resolve_many(self, keys):
        with self._operation():
            return self._resolve_many_unlocked(keys)

    def _resolve_many_unlocked(self, keys):
        if not isinstance(keys, (tuple, list)) or not 1 <= len(keys) <= MAX_KEYS or any(not _valid_key(k) for k in keys) or len(set(keys)) != len(keys):
            raise PackageError('invalid selected keys')
        result = {key: [] for key in keys}
        for row in self._iter_rows_unlocked():
            if row.key in result:
                matches = result[row.key]
                if len(matches) >= MAX_MATCHES:
                    raise PackageError('candidate limit')
                matches.append(row)
        return result

    def read_many(self, keys):
        """Return exact-key payloads only if every selection is unique and safe."""
        with self._operation():
            return self._read_many_unlocked(keys)

    def _read_many_unlocked(self, keys):
        self._check()
        matches = self._resolve_many_unlocked(keys)
        selected = []
        for key in keys:
            rows = matches[key]
            if not rows:
                raise MissingResource('missing selected key')
            if len(rows) != 1:
                raise AmbiguousResource('duplicate selected key')
            row = rows[0]
            if row.deleted or row.committed != 1 or row.compression not in (0, 0x5a42, 0xffff):
                raise UnsupportedResource('deleted or unsupported resource')
            selected.append(row)
        if sum(payload_budget(row) for row in selected) > MAX_PAYLOAD_BUDGET:
            raise PackageError('selected payload budget')
        if any(row.compression == 0 and row.stored_size != row.memory_size for row in selected):
            raise PackageError('uncompressed size mismatch')
        output = {}
        for row in selected:
            stored = self._read_at(row.offset, row.stored_size)
            if row.compression == 0:
                payload = stored
            elif row.compression == 0x5a42:
                decoder = zlib.decompressobj()
                try:
                    payload = decoder.decompress(stored, row.memory_size + 1)
                except zlib.error as exc:
                    raise PackageError('invalid zlib') from exc
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise PackageError('incomplete or trailing zlib')
            else:
                payload = decode_refpack(stored, row.memory_size)
            if len(payload) != row.memory_size:
                raise PackageError('expanded size mismatch')
            output[row.key] = payload
        self._check()
        if self._hash() != self.source_sha256:
            raise PackageError('source digest changed')
        self._check()
        return output
