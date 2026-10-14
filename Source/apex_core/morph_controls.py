"""Edit one observed appearance value, retaining unrelated wire bytes exactly.

Schema facts: BlobSimFacialCustomizationData fields 2..5 are modifier lists;
Modifier field 1 is its uint64 key and field 2 is a float32 amount. Unknown
fields, preset sculpts, duplicate keys and inactive aged groups are preserved.
"""
import math
import re
import struct
import hashlib
from .outfit_snapshot import field, varint
from . import form_appearance as appearance

GROUPS = {2: 'Face', 3: 'Body', 4: 'Aged face', 5: 'Aged body'}
PHYSIQUE = ('Heavy', 'Fit', 'Lean', 'Bony', 'Pregnant', 'Wide hips', 'Narrow hips', 'Wide waist', 'Narrow waist')
_MODIFIER_INDEX = None
_MODIFIER_INDEX_OWNER = None


def effective_modifier(backend, resource_tgi, expected_sha256):
    """Require the actual loaded definition before adding a previously zero key."""
    from . import cas_catalog
    match = re.fullmatch(r'C5F6763E:([0-9A-F]{8}):([0-9A-F]{16})', resource_tgi or '')
    if match is None or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256 or ''):
        raise ValueError('Exact modifier TGI and decompressed resource SHA256 required.')
    expected_key = (0xC5F6763E, int(match.group(1), 16), int(match.group(2), 16))
    if not expected_key[2]: raise ValueError('Zero modifier resource is not editable.')
    provider = getattr(backend, '_studio_modifier_resource', None)
    if callable(provider):
        raw = provider(resource_tgi)
    else:
        from sims4 import resources
        global _MODIFIER_INDEX, _MODIFIER_INDEX_OWNER
        if _MODIFIER_INDEX_OWNER is not resources or _MODIFIER_INDEX is None:
            index = {}
            for ordinal, key in enumerate(resources.list(type=expected_key[0])):
                if ordinal >= 100000: raise ValueError('Native modifier index exceeds its bound.')
                if getattr(key, 'instance', None) == 0:
                    # A real merged owner slider package indexes the native
                    # zero sentinel. It cannot address a Sim modifier; retain
                    # its catalog diagnosis without rejecting every valid key.
                    continue
                values = cas_catalog._key_values(key, expected_key[0])
                if values in index: raise ValueError('Duplicate native modifier index key.')
                index[values] = key
            _MODIFIER_INDEX, _MODIFIER_INDEX_OWNER = index, resources
        if expected_key not in _MODIFIER_INDEX:
            raise ValueError('The requested modifier definition is not loaded in this game.')
        value = resources.ResourceLoader(_MODIFIER_INDEX[expected_key]).load_raw(silent_fail=True)
        raw = bytes(value) if value is not None else None
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1024 * 1024:
        raise ValueError('The effective modifier resource is unavailable or exceeds its bound.')
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('This modifier ID loads another definition; competing packages cannot be adjusted as separate IDs.')
    return str(expected_key[2])


def add(fields, group, key, value):
    """Append one absent, explicitly resource-verified modifier; retain all bytes."""
    if (type(group) is not int or group not in GROUPS or not isinstance(key, str) or
            not re.fullmatch(r'[1-9][0-9]{0,19}', key) or not 0 < int(key) < 1 << 64 or
            type(value) not in (int, float) or not math.isfinite(value)):
        raise ValueError('Exact modifier group/key and finite amount required.')
    raw = appearance.decode(fields.get('facial_attributes', appearance.encode(b'')))
    rows = inspect(fields)
    if any(row['field'] == 'facial_attributes' and row['group'] == group and row['key'] == key for row in rows):
        raise ValueError('This modifier is already stored; edit its exact observed row instead.')
    if len(chunks(raw)) >= 16384: raise ValueError('Facial attribute field bound exceeded.')
    try: amount = struct.pack('<f', value)
    except (OverflowError, struct.error): raise ValueError('Modifier amount exceeds float32 representation.')
    if not math.isfinite(struct.unpack('<f', amount)[0]): raise ValueError('Modifier amount exceeds float32 representation.')
    child = b'\x08' + encoded_varint(int(key)) + b'\x15' + amount
    after = dict(fields)
    # Native assignment serializes known repeated fields by field number.
    # Appending a body modifier after aged fields causes an exact readback
    # mismatch even though every modifier value is correct. Insert within its
    # own group; retain every existing chunk and repeated-row order verbatim.
    parts = chunks(raw)
    matches = [i for i, row in enumerate(parts) if row[0] == group]
    at = matches[-1] + 1 if matches else next((i for i, row in enumerate(parts)
        if group < row[0] <= 5), len(parts))
    encoded = encoded_varint((group << 3) | 2) + encoded_varint(len(child)) + child
    after['facial_attributes'] = appearance.encode(b''.join(row[3] for row in parts[:at]) + encoded +
        b''.join(row[3] for row in parts[at:]))
    return _base_genetic_modifier(after, group, key, value)


def _base_genetic_modifier(fields, group, key, value):
    """Base modifiers must agree with the same owner's genetic base on reload.

    GeneticData field 1 contains BlobSimFacialCustomizationData. A real native
    return relocated an edited group-3 amount into group 5 and restored group 3
    from the unchanged genetic base. Match only this explicit base key. Aged
    groups remain separate; parts, growth, physique and unknown wire fields are
    retained. This is not a whole-genetics replacement from facial attributes.
    """
    if group not in (2,3) or 'genetic_data' not in fields: return fields
    gene_raw = appearance.decode(fields['genetic_data'])
    gene_chunks = chunks(gene_raw)
    nested = [(n,k,p,c) for n,k,p,c in gene_chunks if n == 1]
    if len(nested) > 1 or any(k != 2 for n,k,p,c in nested):
        raise ValueError('Genetic sculpt/modifier field is ambiguous or uses another wire layout.')
    base = nested[0][2] if nested else b''
    base_fields = {'facial_attributes': appearance.encode(base)}
    rows = [r for r in inspect(base_fields) if r['group'] == group and r['key'] == key]
    if len(rows) > 1:
        raise ValueError('Duplicate genetic base modifier keys require explicit ordinal correspondence.')
    if rows:
        row = rows[0]; request = {name: row[name] for name in ('field','group','index','key')}
        request.update(before=row['value'],value=value)
        # No genetic_data is included in this inner request, so no recursion.
        rewritten = appearance.decode(replace(base_fields, request)['facial_attributes'])
    else:
        rewritten = appearance.decode(add(base_fields,group,key,value)['facial_attributes'])
    child = b'\x0a' + encoded_varint(len(rewritten)) + rewritten
    output = b''.join(child if n == 1 else raw for n,k,p,raw in gene_chunks)
    if not nested: output += child
    if len(output) > 1024 * 1024: raise ValueError('Genetic modifier payload exceeds its byte bound.')
    result = dict(fields); result['genetic_data'] = appearance.encode(output)
    return result


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
    if request['field'] == 'facial_attributes':
        return _base_genetic_modifier(result, request['group'], request['key'], value)
    return result
