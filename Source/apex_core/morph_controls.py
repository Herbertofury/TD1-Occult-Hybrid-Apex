"""Edit one observed appearance value, retaining unrelated wire bytes exactly.

Schema facts: BlobSimFacialCustomizationData fields 2..5 are modifier lists;
Modifier field 1 is its uint64 key and field 2 is a float32 amount. Unknown
fields, preset sculpts, duplicate keys and inactive aged groups are preserved.
"""
import math
import re
import struct
from .outfit_snapshot import field, varint
from . import form_appearance as appearance

GROUPS = {2: 'Face', 3: 'Body', 4: 'Aged face', 5: 'Aged body'}
PHYSIQUE = ('Heavy', 'Fit', 'Lean', 'Bony', 'Pregnant', 'Wide hips', 'Narrow hips', 'Wide waist', 'Narrow waist')


def chunks(raw):
    if not isinstance(raw, bytes) or len(raw) > 1024 * 1024:
        raise ValueError('Facial attributes must be bounded native bytes.')
    result, offset = [], 0
    while offset < len(raw):
        start = offset
        number, kind, offset, value = field(raw, offset)
        result.append((number, kind, value, raw[start:offset]))
        if len(result) > 16384:
            raise ValueError('Facial attribute field bound exceeded.')
    return result


def encoded_varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128); value >>= 7
    result.append(value)
    return bytes(result)


def modifier(raw):
    values = chunks(raw)
    keys, amounts = [], []
    for number, kind, value, chunk in values:
        if number == 1:
            if kind == 0: keys.append(value)
            elif kind == 1: keys.append(struct.unpack('<Q', chunk[-8:])[0])
            else: raise ValueError('Unknown modifier key layout.')
        if number == 2:
            if kind != 5: raise ValueError('Unknown modifier amount layout.')
            amounts.append(struct.unpack('<f', chunk[-4:])[0])
    if not amounts: amounts = [0.0]  # Protobuf's absent float32 field is zero.
    if len(keys) != 1 or len(amounts) != 1 or not keys[0] or not math.isfinite(amounts[0]):
        raise ValueError('Modifier key/amount is missing, ambiguous or nonfinite.')
    return keys[0], amounts[0], values


def inspect(fields):
    result = []
    if 'facial_attributes' in fields:
        raw = appearance.decode(fields['facial_attributes'])
        counts = {}
        for group, kind, payload, _ in chunks(raw):
            if group not in GROUPS: continue
            if kind != 2: raise ValueError('Unknown facial modifier group layout.')
            key, amount, _ = modifier(payload)
            index = counts.get(group, 0); counts[group] = index + 1
            result.append(dict(field='facial_attributes', group=group, index=index, key=str(key), value=amount,
                label=GROUPS[group] + ' / {:016X}'.format(key), native_bounds_verified=False))
    if 'physique' in fields:
        value = appearance.decode(fields['physique'])
        if not isinstance(value, str) or len(value) > 4096: raise ValueError('Unknown physique representation.')
        parts = value.split(',')
        if len(parts) > 32 or not parts: raise ValueError('Invalid physique component count.')
        ordinal = 0
        for index, text in enumerate(parts):
            if not text.strip(): continue  # Native physique strings retain a trailing comma.
            amount = float(text)
            if not math.isfinite(amount): raise ValueError('Nonfinite physique component.')
            result.append(dict(field='physique', group=0, index=index, key=None, value=amount,
                label=PHYSIQUE[ordinal] if ordinal < len(PHYSIQUE) else 'Physique component {}'.format(ordinal),
                native_bounds_verified=False))
            ordinal += 1
    return result


def replace(fields, request):
    expected = {'field', 'group', 'index', 'key', 'before', 'value'}
    if not isinstance(request, dict) or set(request) != expected:
        raise ValueError('Exact appearance slider request required.')
    if (type(request['group']) is not int or type(request['index']) is not int or
            type(request['before']) not in (int, float) or type(request['value']) not in (int, float) or
            not math.isfinite(request['before']) or not math.isfinite(request['value'])):
        raise ValueError('Finite exact slider values and numeric ordinals required.')
    matching = [row for row in inspect(fields) if all(row[key] == request[key] for key in ('field','group','index','key'))]
    if len(matching) != 1 or matching[0]['value'] != request['before']:
        raise ValueError('Appearance slider identity/value changed; inspect again.')
    value = request['value']
    try: number = struct.pack('<f', value)
    except (OverflowError, struct.error): raise ValueError('Slider value exceeds float32 representation.')
    if not math.isfinite(struct.unpack('<f', number)[0]): raise ValueError('Slider value exceeds float32 representation.')
    result = dict(fields)
    if request['field'] == 'physique':
        parts = appearance.decode(fields['physique']).split(',')
        # The game's native physique getter returns a fixed three-decimal
        # string, including its trailing comma. Match an observed native
        # representation before journaling, rather than accepting a draft
        # that the setter will immediately reformat and reject on readback.
        native_format = all(re.fullmatch(r'[+-]?\d+\.\d{3}', part)
                            for part in parts if part.strip())
        parts[request['index']] = format(value, '.3f' if native_format else '.9g')
        result['physique'] = appearance.encode(','.join(parts))
    else:
        raw = appearance.decode(fields['facial_attributes']); rewritten, index = [], 0
        for group, kind, payload, chunk in chunks(raw):
            if group == request['group']:
                if index == request['index']:
                    key, _, child = modifier(payload)
                    payload = b''.join(entry[:-4] + number if n == 2 else entry for n, _, _, entry in child)
                    if not any(n == 2 for n, _, _, _ in child): payload += b'\x15' + number
                    chunk = encoded_varint((group << 3) | 2) + encoded_varint(len(payload)) + payload
                index += 1
            rewritten.append(chunk)
        result['facial_attributes'] = appearance.encode(b''.join(rewritten))
    return result
