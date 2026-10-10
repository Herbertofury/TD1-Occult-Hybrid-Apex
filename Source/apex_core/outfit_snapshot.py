"""Stable category grouping without dropping any serialized outfit fields.

The installed OutfitList schema uses repeated field 1 and OutfitData category
field 2. Native load/save can reorder category groups. Order *within* a category
is outfit-index identity and must remain unchanged. Every child byte, including
unknown fields and full uint64 colors, is retained verbatim.
"""
MAX_BYTES = 8 * 1024 * 1024


def varint(raw, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(raw):
            raise ValueError('Truncated outfit protobuf.')
        byte = raw[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError('Outfit protobuf varint exceeds uint64.')
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError('Invalid outfit protobuf varint.')


def field(raw, offset, depth=0):
    start = offset
    key, offset = varint(raw, offset)
    number, kind = key >> 3, key & 7
    if number == 0 or number >= 1 << 29 or depth > 32:
        raise ValueError('Invalid outfit protobuf field.')
    content = offset
    if kind == 0:
        value, offset = varint(raw, offset)
    elif kind in (1, 5):
        offset += 8 if kind == 1 else 4
        value = None
    elif kind == 2:
        count, offset = varint(raw, offset)
        content = offset
        offset += count
        value = raw[content:offset]
    elif kind == 3:
        value = None
        while True:
            child_key, child_end = varint(raw, offset)
            if child_key & 7 == 4:
                if child_key >> 3 != number:
                    raise ValueError('Mismatched outfit protobuf group.')
                offset = child_end
                break
            _, _, offset, _ = field(raw, offset, depth + 1)
    else:
        raise ValueError('Invalid outfit protobuf wire type.')
    if offset > len(raw):
        raise ValueError('Truncated outfit protobuf field.')
    return number, kind, offset, value


def category(raw):
    offset, result = 0, 0
    while offset < len(raw):
        number, kind, offset, value = field(raw, offset)
        if number == 2:
            if kind != 0 or value >= 1 << 32:
                raise ValueError('Unknown outfit category layout.')
            result = value
    return result


def normalize(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('Outfit snapshot is not bounded bytes.')
    offset, fields, outfits = 0, [], []
    while offset < len(raw):
        start = offset
        number, kind, offset, value = field(raw, offset)
        chunk = raw[start:offset]
        is_outfit = number == 1
        if is_outfit:
            if kind != 2 or len(outfits) >= 1024:
                raise ValueError('Unknown or excessive OutfitList entries.')
            outfits.append((category(value), chunk))
        fields.append((is_outfit, chunk))
    # Python's stable sort preserves category-relative outfit indices.
    ordered = iter(chunk for _, chunk in sorted(outfits, key=lambda item: item[0]))
    return b''.join(next(ordered) if is_outfit else chunk for is_outfit, chunk in fields)
