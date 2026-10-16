"""Detached native appearance messages for every independently named form.

Project complete appearance fields onto a captured SimData byte message. No
Sim is loaded, changed, instantiated or saved. Unrelated/unknown wire chunks
remain exact, and the runtime descriptor supplies field numbers and types.
"""
import base64
import hashlib
import math
import struct
from . import form_appearance as appearance
from .outfit_snapshot import field, MAX_BYTES


def owner_id(state, identity):
    from .lifestates import name
    if (not isinstance(identity, str) or not 1 <= len(identity) <= 64 or
            identity[0] not in 'abcdefghijklmnopqrstuvwxyz' or
            any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in identity)):
        raise ValueError('An exact independent form identity is required.')
    return name(state).lower() + '/' + identity


def _varint(value):
    raw = bytearray()
    while value >= 128:
        raw.append((value & 127) | 128)
        value >>= 7
    raw.append(value)
    return bytes(raw)


def _chunks(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('Native appearance message exceeds its byte bound.')
    rows, offset = [], 0
    while offset < len(raw):
        start = offset
        number, wire, offset, value = field(raw, offset)
        rows.append((number, wire, value, raw[start:offset]))
        if len(rows) > 100000:
            raise ValueError('Native appearance field count exceeds its bound.')
    return rows


def _encode(descriptor, value):
    number, kind = descriptor['number'], descriptor['type']
    if value is None:
        return b''  # An explicitly absent captured field stays absent.
    if descriptor.get('repeated'):
        if not isinstance(value, (tuple, list)) or len(value) > 1024:
            raise ValueError('A repeated native appearance field requires its complete bounded sequence.')
        singular = dict(descriptor, repeated=False)
        return b''.join(_encode(singular, item) for item in value)
    if kind in ('message', 'bytes', 'string'):
        if kind == 'message' and isinstance(value, tuple) and len(value) == 2 and value[0] == 'protobuf':
            value = value[1]
        if kind == 'string':
            if not isinstance(value, str):
                raise ValueError('Native appearance text has a different type.')
            value = value.encode('utf-8')
        if not isinstance(value, bytes) or len(value) > MAX_BYTES:
            raise ValueError('Native appearance bytes have a different type or exceed their bound.')
        if kind == 'message':
            _chunks(value)  # Validate framing without dropping unknown fields.
        return _varint(number << 3 | 2) + _varint(len(value)) + value
    if kind in ('uint32', 'uint64', 'fixed32', 'fixed64'):
        bits = 32 if kind.endswith('32') else 64
        if type(value) is not int or not 0 <= value < 1 << bits:
            raise ValueError('Native appearance integer has a different type or exceeds its bound.')
        if kind.startswith('fixed'):
            return _varint(number << 3 | (5 if bits == 32 else 1)) + value.to_bytes(bits // 8, 'little')
        return _varint(number << 3) + _varint(value)
    if kind in ('float', 'double'):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Native appearance float is not finite.')
        try:
            raw = struct.pack('<f' if kind == 'float' else '<d', value)
        except (OverflowError, struct.error):
            raise ValueError('Native appearance float exceeds its native range.')
        return _varint(number << 3 | (5 if kind == 'float' else 1)) + raw
    raise ValueError('Unsupported native appearance field type; no partial form projected.')


def _custom_tattoos(descriptor, mapping, schemas, original):
    """The native wrapper exposes repeated tattoo messages as body-type keys."""
    if descriptor.get('type') != 'message' or descriptor.get('repeated') is not True or len(mapping) > 1024:
        raise ValueError('Custom tattoo storage differs from its native repeated-message descriptor.')
    child = schemas.get(descriptor.get('message_type'))
    fields = {row['name']: row for row in child} if isinstance(child, list) else {}
    body, texture = fields.get('body_type'), fields.get('texture_id')
    if (body is None or texture is None or body['type'] != 'uint32' or texture['type'] != 'uint64' or
            body.get('repeated') or texture.get('repeated') or body['number'] == texture['number']):
        raise ValueError('Custom tattoo body/texture fields are not represented by the current native schema.')
    old = {}
    for number, wire, value, _chunk in original:
        if number != descriptor['number']: continue
        if wire != 2: raise ValueError('Custom tattoo message has a different wire type.')
        chunks = _chunks(value)
        keys = [item for item in chunks if item[0] == body['number']]
        if len(keys) != 1 or keys[0][1] != 0 or keys[0][2] in old:
            raise ValueError('Custom tattoo records lack unique native body-type keys.')
        old[keys[0][2]] = chunks
    singular = dict(descriptor, repeated=False)
    result = []
    for key, value in sorted(mapping.items()):
        # Keep unknown child fields for matching records instead of rebuilding
        # the whole tattoo message from only today's two known members.
        raw = b''.join(chunk for number, _wire, _value, chunk in old.get(key, ())
                       if number not in (body['number'], texture['number']))
        raw += _encode(body, key) + _encode(texture, value)
        result.append(_encode(singular, ('protobuf', raw)))
    return b''.join(result)


def project(capture, fields):
    """Return a new SimData message; never mutate the input or an owner."""
    if not isinstance(capture, dict) or capture.get('native_message_type') != 'EA.Sims4.Persistence.SimData':
        raise ValueError('Use the exact captured native SimData descriptor.')
    raw = base64.b64decode(capture['native_base64'], validate=True)
    if hashlib.sha256(raw).hexdigest() != capture.get('native_sha256'):
        raise ValueError('Native source message differs from its captured digest.')
    schema = capture['field_schemas'].get(capture['native_message_type'])
    if not isinstance(schema, list) or not schema:
        raise ValueError('Native source descriptor is missing.')
    by_name, numbers = {}, set()
    for row in schema:
        if (not isinstance(row, dict) or not isinstance(row.get('name'), str) or
                type(row.get('number')) is not int or not 0 < row['number'] < 1 << 29 or
                row['name'] in by_name or row['number'] in numbers):
            raise ValueError('Native descriptor identity is duplicated or malformed.')
        by_name[row['name']] = row
        numbers.add(row['number'])
    values = appearance.payload(fields)
    if '__outfits__' not in values:
        raise ValueError('A form requires its complete captured outfit message.')
    replacements = {}
    aliases = {'facial_attributes': 'facial_attr', '__outfits__': 'outfits'}
    rows = _chunks(raw)
    for name, value in values.items():
        descriptor = by_name.get(aliases.get(name, name))
        if descriptor is None:
            raise ValueError('The native descriptor cannot represent this captured appearance field: ' + name)
        if name == 'parts_custom_tattoos' and isinstance(value, dict):
            replacements[descriptor['number']] = _custom_tattoos(descriptor, value, capture['field_schemas'], rows)
        else:
            replacements[descriptor['number']] = _encode(descriptor, value)
    # No gameplay, identity, membership, name, age or service field is changed.
    result = b''.join(chunk for number, _wire, _value, chunk in rows if number not in replacements)
    result += b''.join(replacements[number] for number in sorted(replacements))
    _chunks(result)
    return dict(native_hex=result.hex(), sha256=hashlib.sha256(result).hexdigest(),
                native_bytes=len(result), native_message_type=capture['native_message_type'])
