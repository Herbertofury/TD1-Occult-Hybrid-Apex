"""Native GeneticData comparison with exact cross-list growth duplicates.

The installed descriptor has PartDataList parts_list#5 and growth_parts_list#6.
EA's setter removes an identical growth PartData from parts_list. Keep every
unique part and complete unknown row/container/root bytes. Raw retained
appearance payloads are never rewritten by this read-only comparison.
"""
from .outfit_snapshot import field, MAX_BYTES


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
