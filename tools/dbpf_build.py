"""Bounded DBPF 2.x build primitives; deterministic resource-preserving output.

Format reference: https://github.com/thequux/s4py/blob/master/lib/s4py/package/dbpf.py
This narrow implementation is independent. Foundry's Rust reader verifies real
builds separately; no live profile/game files are written by this module.
"""
import hashlib
import struct
import zlib

MAX_RESOURCE = 32 * 1024 * 1024
MAX_PACKAGE = 256 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(raw):
    if len(raw) < 96 or len(raw) > MAX_PACKAGE or raw[:4] != b'DBPF':
        raise ValueError('Invalid/bounded DBPF input.')
    header = struct.unpack('<24I', raw[:96])
    if header[1] != 2 or header[2] not in (0, 1):
        raise ValueError('Unsupported DBPF version.')
    count, offset, length = header[9], header[16] or header[10], header[11]
    if not count or offset < 96 or offset + length > len(raw) or count > 100000:
        raise ValueError('Invalid DBPF index extent/count.')
    index = memoryview(raw)[offset:offset + length]
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
    resources = {}
    for _ in range(count):
        kind, group, high = [value if value is not None else integer() for value in shared]
        low, start, packed_size, memory_size = integer(), integer(), integer(), integer()
        compression_word = integer() if packed_size & 0x80000000 else 0
        compression, size = compression_word & 0xffff, packed_size & 0x7fffffff
        if compression == 0xffe0:
            continue
        if start < 96 or start + size > offset or size > MAX_RESOURCE or memory_size > MAX_RESOURCE:
            raise ValueError('Invalid DBPF resource extent.')
        key = (kind, group, (high << 32) | low)
        if key in resources:
            raise ValueError('Duplicate resource key inside a package.')
        stored = raw[start:start + size]
        if compression == 0x5a42:
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(stored, MAX_RESOURCE + 1)
            if decoder.unused_data or decoder.unconsumed_tail or not decoder.eof:
                raise ValueError('Invalid/bounded zlib resource.')
        elif compression in (0, 0xffff):
            decoded = stored
        else:
            raise ValueError('Unclassified baseline compression: {:04X}'.format(compression))
        if len(decoded) != memory_size:
            raise ValueError('DBPF memory size mismatch.')
        resources[key] = decoded
    if position != len(index):
        raise ValueError('Unexplained DBPF index bytes.')
    return resources


def build(resources):
    if not resources or len(resources) > 100000:
        raise ValueError('A real package requires a bounded, nonempty resource map.')
    bodies, index = bytearray(), bytearray(struct.pack('<I', 0))
    for key, payload in sorted(resources.items()):
        if len(key) != 3 or not all(isinstance(value, int) and not isinstance(value, bool) for value in key):
            raise ValueError('Invalid resource identity.')
        kind, group, instance = key
        if not 0 <= kind <= 0xffffffff or not 0 <= group <= 0xffffffff or not 0 <= instance <= 0xffffffffffffffff:
            raise ValueError('Resource identity outside format range.')
        if not isinstance(payload, bytes) or len(payload) > MAX_RESOURCE:
            raise ValueError('Invalid/bounded resource contents.')
        stored = zlib.compress(payload, 9)
        start = 96 + len(bodies)
        bodies.extend(stored)
        index.extend(struct.pack('<8I', kind, group, instance >> 32, instance & 0xffffffff,
                                 start, len(stored) | 0x80000000, len(payload), 0x00015a42))
    header = bytearray(96)
    header[:4] = b'DBPF'
    struct.pack_into('<II', header, 4, 2, 1)
    struct.pack_into('<I', header, 36, len(resources))
    struct.pack_into('<I', header, 44, len(index))
    struct.pack_into('<II', header, 60, 3, 96 + len(bodies))
    output = bytes(header + bodies + index)
    if len(output) > MAX_PACKAGE or read(output) != resources:
        raise ValueError('Package round-trip verification failed.')
    return output


def tgi(key):
    return '{:08X}:{:08X}:{:016X}'.format(*key)


def merge(inputs, overrides=None):
    resources, owners, records = {}, {}, []
    overrides = overrides or {}
    for owner, incoming in inputs:
        for key, payload in sorted(incoming.items()):
            old_owner = owners.get(key)
            if key in resources and resources[key] != payload:
                selected = overrides.get(tgi(key))
                if selected not in (old_owner, owner):
                    raise ValueError('Unresolved resource overlap: ' + tgi(key))
                records.append({'tgi': tgi(key), 'owners': [old_owner, owner], 'selected': selected})
                if selected == old_owner:
                    continue
            resources[key], owners[key] = payload, owner
    return resources, owners, records
