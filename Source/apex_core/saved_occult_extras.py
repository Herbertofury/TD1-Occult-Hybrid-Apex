"""Read load-bound occult extras from the indexed save when EA strips unknowns.

The loader's immutable core must equal the indexed record's complete core.
No bank, prior runtime, guessed slot, file write or missing form is accepted.
One bounded in-memory cache avoids decoding the household save per Sim.
"""
import hashlib
from pathlib import Path
import struct
import zlib
from . import outfit_snapshot as wire, occult_appearance_extension as extension
from .overlay_loader import _unlinked, sidecar_paths

_CACHE = {}
MAX_BYTES = 128 * 1024 * 1024


def fields(raw):
    offset = 0
    while offset < len(raw):
        number, kind, offset, value = wire.field(raw, offset)
        yield number, kind, value


def _one(raw, number, kind):
    rows = [(k, v) for n, k, v in fields(raw) if n == number]
    if len(rows) != 1 or rows[0][0] != kind:
        raise ValueError('Indexed save identity or record is absent/ambiguous/untyped.')
    if kind == 1:
        # wire.field leaves fixed-width values opaque; locate the exact bytes.
        offset = 0
        while offset < len(raw):
            start = offset
            n, k, offset, value = wire.field(raw, offset)
            if n == number:
                return struct.unpack('<Q', raw[offset - 8:offset])[0]
    return rows[0][1]


def _signature(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def refpack(raw, expected):
    """Bounded overlap-capable RefPack decoder; same contract as catalog reader."""
    offset = 0
    def take(count):
        nonlocal offset
        if count < 0 or offset + count > len(raw):
            raise ValueError('Truncated native RefPack input.')
        value = raw[offset:offset + count]; offset += count
        return value
    header = take(2)
    if int.from_bytes(header, 'big') & 0x1fff != 0x10fb or header[0] & 1:
        raise ValueError('Unsupported native RefPack header.')
    declared = int.from_bytes(take(4 if header[0] & 0x80 else 3), 'big')
    if declared != expected or not 0 <= declared <= MAX_BYTES:
        raise ValueError('Native RefPack size differs.')
    output = bytearray()
    while True:
        code = take(1)[0]; count = distance = 0
        if code < 0x80:
            extra = take(1)[0]; literals, count = code & 3, ((code >> 2) & 7) + 3
            distance = ((code & 0x60) << 3) + extra + 1
        elif code < 0xc0:
            a, b = take(2); literals, count = a >> 6, (code & 63) + 4
            distance = ((a & 63) << 8) + b + 1
        elif code < 0xe0:
            a, b, c = take(3); literals, count = code & 3, ((code & 12) << 6) + c + 5
            distance = ((code & 16) << 12) + (a << 8) + b + 1
        else:
            literals = ((code & 31) + 1) * 4 if code < 0xfc else code & 3
        if len(output) + literals + count > expected:
            raise ValueError('Native RefPack command exceeds its bound.')
        output.extend(take(literals))
        if count:
            if distance > len(output):
                raise ValueError('Native RefPack backreference precedes input.')
            block = bytes(output[-distance:][:min(count, distance)])
            output.extend((block * ((count + len(block) - 1) // len(block)))[:count])
        if code >= 0xfc:
            if len(output) != expected or offset != len(raw):
                raise ValueError('Native RefPack stop/trailing bytes differ.')
            return bytes(output)


def resource(raw, guid):
    if not 96 <= len(raw) <= MAX_BYTES or raw[:4] != b'DBPF':
        raise ValueError('Bounded native DBPF save required.')
    header = struct.unpack('<24I', raw[:96])
    count, start, length = header[9], header[16] or header[10], header[11]
    if (header[1] != 2 or header[2] not in (0, 1) or not 0 < count <= 1000000 or
            start < 96 or not 4 <= length <= 36 * count + 16 or start + length > len(raw)):
        raise ValueError('Native save index/version/count differs.')
    index = raw[start:start + length]; offset = 0
    def integer():
        nonlocal offset
        if offset + 4 > len(index):
            raise ValueError('Truncated save index.')
        value = struct.unpack_from('<I', index, offset)[0]; offset += 4
        return value
    flags = integer()
    if flags & ~7:
        raise ValueError('Unknown native index layout.')
    shared = [integer() if flags & (1 << bit) else None for bit in range(3)]
    matches = []
    for _ in range(count):
        kind, group, high = [value if value is not None else integer() for value in shared]
        low, position, stored, size = integer(), integer(), integer(), integer()
        compression = integer() & 0xffff if stored & 0x80000000 else 0
        stored &= 0x7fffffff
        if compression == 0xffe0:
            continue
        if kind == 13:
            if (group != 0 or (high << 32) | low != guid or position < 96 or
                    not 0 < stored <= MAX_BYTES or not 0 < size <= MAX_BYTES or
                    position + stored > len(raw) or
                    not (position + stored <= start or position >= start + length)):
                raise ValueError('Native save resource identity/extent differs.')
            data = raw[position:position + stored]
            if compression == 0x5a42:
                decoder = zlib.decompressobj(); data = decoder.decompress(data, size + 1)
                if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
                    raise ValueError('Unresolved native save compression.')
            elif compression in (0xffff, 0xfffe) and data[:2] in (b'\x10\xfb', b'\x50\xfb', b'\x90\xfb', b'\xd0\xfb'):
                data = refpack(data, size)
            elif compression not in (0, 0xffff):
                raise ValueError('Unsupported native save compression; no inferred payload.')
            if len(data) != size:
                raise ValueError('Native save decoded size differs.')
            matches.append(data)
    if offset != length or len(matches) != 1 or _one(matches[0], 1, 0) != guid:
        raise ValueError('Indexed save GUID or resource count differs.')
    return matches[0]


def indexed_records(raw, sim_id, household_id):
    sims = [value for n, k, value in fields(raw) if n == 6 and k == 2
            and _one(value, 1, 1) == sim_id]
    if not sims:
        return []  # Fresh Tray allocations have no record in this disk save.
    if len(sims) != 1 or _one(sims[0], 4, 1) != household_id:
        raise ValueError('Indexed Sim/household identity differs.')
    attributes = _one(sims[0], 30, 2)
    tracker = _one(attributes, 17, 2)
    return [value for n, k, value in fields(tracker) if n == 3 and k == 2]


def read(backend, sim, record):
    existing = extension.read(record)
    if existing:
        return existing, {'source': 'native-incoming-record', 'verified': True}
    services = getattr(backend, 'services', None)
    if services is None:
        return {}, {'source': 'indexed-save', 'verified': False, 'reason': 'no-native-persistence'}
    persistence = services.get_persistence_service()
    slot = persistence.get_save_slot_proto_buff().slot_id
    guid = persistence.get_save_slot_proto_guid()
    if type(slot) is not int or not 0 < slot < 0xffffffff:
        return {}, {'source': 'indexed-save', 'verified': False, 'reason': 'no-exact-native-slot'}
    if type(guid) is not int or not 0 < guid < 1 << 32:
        raise ValueError('Native load GUID differs; no disk extras authorized.')
    native, _ = sidecar_paths(backend.__file__)
    profile = native.parent.parent.parent.parent
    path = _unlinked(profile / 'saves' / ('Slot_%08x.save' % slot))
    before = _signature(path)
    if not 96 <= before[2] <= MAX_BYTES:
        raise ValueError('Native save exceeds the indexed-reader bound.')
    key = str(path), before, guid
    if key not in _CACHE:
        raw = path.read_bytes()
        if _signature(path) != before or len(raw) != before[2]:
            raise ValueError('Native save changed while its extension source was read.')
        data = resource(raw, guid)
        # Keep one save source per runtime, not an unbounded export cache.
        _CACHE.clear(); _CACHE[key] = (data, hashlib.sha256(raw).hexdigest())
    data, file_sha = _CACHE[key]
    matches = []
    for raw_record in indexed_records(data, int(sim.id), int(sim.household_id)):
        candidate = type(record)(); candidate.ParseFromString(raw_record)
        if int(candidate.occult_type) == int(record.occult_type):
            matches.append(candidate)
    if not matches:
        return {}, {'source': 'indexed-save', 'verified': False, 'reason': 'no-existing-source-owner'}
    if len(matches) != 1 or extension._parts(matches[0])[0] != extension._parts(record)[0]:
        raise ValueError('Indexed load core differs from the immutable incoming record; no stale extras.')
    if _signature(path) != before:
        raise ValueError('Indexed source changed before its load-bound readback.')
    result = extension.read(matches[0])
    return result, {'source': 'indexed-save-matching-native-load-core', 'verified': bool(result),
                    'file_sha256': file_sha, 'slot_id': slot, 'save_guid': str(guid),
                    'sim_id': str(sim.id), 'form_flags': int(record.occult_type),
                    'appearance_written': False, 'save_written': False}
