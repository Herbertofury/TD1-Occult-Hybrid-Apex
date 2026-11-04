"""Native GeneticData comparison with exact cross-list growth duplicates.

The installed descriptor has PartDataList parts_list#5 and growth_parts_list#6.
EA's setter removes an identical growth PartData from parts_list. Keep every
unique part and complete unknown row/container/root bytes. Raw retained
appearance payloads are never rewritten by this read-only comparison.
"""
from .outfit_snapshot import field, MAX_BYTES
import math
import struct
from functools import lru_cache

NORMALIZE_CACHE_BYTES = 128 * 1024


def _varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128); value >>= 7
    result.append(value)
    return bytes(result)


def _fields(raw):
    offset, rows = 0, []
    while offset < len(raw):
        start = offset
        number, kind, offset, value = field(raw, offset)
        rows.append((number, kind, value, raw[start:offset]))
        if len(rows) > 4096:
            raise ValueError('Genetics field count exceeds its bound.')
    return rows


def _parts(raw):
    rows, count = _fields(raw), 0
    for number, kind, value, _chunk in rows:
        if number != 1:
            continue
        count += 1
        if kind != 2 or count > 1024:
            raise ValueError('Genetics PartDataList exceeds its native contract.')
        identifiers = {}
        for child, wire, item, _raw in _fields(value):
            if child in (1, 2):
                if wire != 0 or child in identifiers:
                    raise ValueError('Genetics PartData identity is ambiguous.')
                identifiers[child] = item
        if (set(identifiers) != {1, 2} or not 0 < identifiers[1] < 2**64 or
                not 0 <= identifiers[2] < 2**32):
            raise ValueError('Genetics PartData identity is incomplete.')
    return rows


def normalize(raw):
    """Opaque unsupported data stays exact; only the inspected layout projects."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('Genetics snapshot must be bounded bytes.')
    return _small_normalize(raw) if type(raw) is bytes and len(raw) <= NORMALIZE_CACHE_BYTES else _normalize(raw)


@lru_cache(maxsize=32)
def _small_normalize(raw):
    return _normalize(raw)


def _normalize(raw):
    try:
        rows = _fields(raw)
        known, contracts = {}, {1: 2, 2: 2, 3: 5, 4: 0, 5: 2, 6: 2}
        for number, kind, value, chunk in rows:
            if number in contracts:
                if number in known or kind != contracts[number]:
                    return raw
                known[number] = (value, chunk)
        if 5 not in known or 6 not in known:
            return raw
        base, growth = _parts(known[5][0]), _parts(known[6][0])
    except ValueError:
        return raw  # Unrecognized bytes never authorize omission or guessing.
    growth_values = {value for number, kind, value, _chunk in growth if number == 1}
    retained = b''.join(chunk for number, kind, value, chunk in base
                        if number != 1 or value not in growth_values)
    known[5] = (retained, _varint((5 << 3) | 2) + _varint(len(retained)) + retained)
    # Stable known-field order; preserve all unknown chunks at their positions.
    ordered = iter(known[number][1] for number in sorted(known))
    return b''.join(next(ordered) if number in known else chunk
                    for number, _kind, _value, chunk in rows)


def mirror_voice(raw, pitch=None, actor=None):
    """Match only GeneticData's native voice mirrors to selected scalar state.

    EA rewrites #3/#4 when restoring genetics/voice. Selective paste must keep
    the destination voice unless those scalar fields were explicitly selected.
    Sculpt, physique, parts, growth and unknown bytes retain source provenance.
    Unsupported layouts remain opaque; no missing genetic field is invented.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('Genetics must be bounded native bytes.')
    try:
        rows = _fields(raw)
    except ValueError:
        return raw
    if not {5, 6} <= {number for number, _kind, _value, _chunk in rows}:
        return raw
    contracts, known = {1: 2, 2: 2, 3: 5, 4: 0, 5: 2, 6: 2}, {}
    for number, kind, value, chunk in rows:
        if number in contracts:
            if number in known or kind != contracts[number]:
                raise ValueError('Native genetics has ambiguous known fields; no selective paste.')
            known[number] = (value, chunk)
    _parts(known[5][0]); _parts(known[6][0])
    replacements = {}
    if 3 in known:
        if type(pitch) not in (int, float) or not math.isfinite(pitch):
            raise ValueError('Genetics voice mirror requires an exact available native pitch.')
        try:
            packed = struct.pack('<f', pitch)
        except (OverflowError, struct.error):
            raise ValueError('Genetics voice pitch exceeds its native float32 contract.')
        if not math.isfinite(struct.unpack('<f', packed)[0]):
            raise ValueError('Genetics voice pitch is not a finite native float32.')
        replacements[3] = known[3][1][:-4] + packed
    if 4 in known:
        if type(actor) is not int or not 0 <= actor < 1 << 32:
            raise ValueError('Genetics voice mirror requires an exact available native actor.')
        from .outfit_snapshot import varint
        chunk = known[4][1]
        _key, header = varint(chunk, 0)
        replacements[4] = chunk[:header] + _varint(actor)
    return b''.join(replacements.get(number, chunk) for number, _kind, _value, chunk in rows)
