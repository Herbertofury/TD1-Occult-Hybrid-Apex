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


def project_record(capture, fields, native_kind):
    """Project onto the full occult-record loader, including exact genetics.

    The primary loader regenerates genetics from equipped parts. The record
    loader reads the complete supplied genetic message. Keep the complete root
    appearance too: pelt layers/custom texture have no occult-record fields.
    All work is detached wire data; no membership or gameplay Sim is changed.
    """
    if type(native_kind) is not int or native_kind not in (1,2,4,8,16,32,64):
        raise ValueError('A projected appearance needs its exact native rendering kind.')
    projected=project(capture,fields)
    schemas=capture['field_schemas']
    def schema(name):
        rows=schemas.get(name)
        if not isinstance(rows,list) or not rows:raise ValueError('Missing native appearance record descriptor.')
        by_name={};numbers=set()
        for row in rows:
            if (not isinstance(row,dict) or not isinstance(row.get('name'),str) or type(row.get('number')) is not int or
                    not 0<row['number']<2**29 or row['name'] in by_name or row['number'] in numbers):
                raise ValueError('Ambiguous native appearance record descriptor.')
            by_name[row['name']]=row;numbers.add(row['number'])
        return by_name
    def child(by_name,name,repeated=False):
        field=by_name.get(name)
        if (field is None or field.get('type')!='message' or field.get('repeated') is not repeated or
                not isinstance(field.get('message_type'),str)):
            raise ValueError('Native appearance record path is not represented by its descriptor.')
        return field
    def singular(rows,descriptor):
        found=[row for row in rows if row[0]==descriptor['number']]
        if len(found)>1 or found and found[0][1]!=2:raise ValueError('Native appearance path has duplicate or invalid messages.')
        return found[0][2] if found else b''
    def replace(rows,descriptor,raw):
        return b''.join(row[3] for row in rows if row[0]!=descriptor['number'])+_encode(descriptor,('protobuf',raw))
    root_schema=schema(capture['native_message_type']);attributes=child(root_schema,'attributes')
    attributes_schema=schema(attributes['message_type']);tracker=child(attributes_schema,'occult_tracker')
    tracker_schema=schema(tracker['message_type']);records=child(tracker_schema,'occult_sim_infos',True)
    record_schema=schema(records['message_type']);kind=record_schema.get('occult_type')
    if kind is None or kind.get('type')!='uint32' or kind.get('repeated'):
        raise ValueError('Native appearance record lacks its exact occult identity.')
    root_rows=_chunks(bytes.fromhex(projected['native_hex']))
    attribute_rows=_chunks(singular(root_rows,attributes));tracker_rows=_chunks(singular(attribute_rows,tracker))
    matched=None;record_count=0
    for index,row in enumerate(tracker_rows):
        if row[0]!=records['number']:continue
        record_count+=1
        if row[1]!=2 or record_count>7:raise ValueError('Native appearance record inventory is invalid.')
        identity=[part for part in _chunks(row[2]) if part[0]==kind['number']]
        if len(identity)!=1 or identity[0][1]!=0:raise ValueError('Native appearance record identity is ambiguous.')
        if identity[0][2]==native_kind:
            if matched is not None:raise ValueError('The selected native appearance record is duplicated.')
            matched=index
    record_rows=_chunks(tracker_rows[matched][2]) if matched is not None else []
    replacements={kind['number']:_encode(kind,native_kind)}
    for name,value in appearance.payload(fields).items():
        descriptor=record_schema.get('outfits' if name=='__outfits__' else name)
        if descriptor is None:
            if name in ('pelt_layers','custom_texture'):continue  # Retained in the complete root projection.
            raise ValueError('Native record cannot represent a captured appearance field: '+name)
        if name=='parts_custom_tattoos' and isinstance(value,dict):
            replacements[descriptor['number']]=_custom_tattoos(descriptor,value,schemas,record_rows)
        else:replacements[descriptor['number']]=_encode(descriptor,value)
    selected=b''.join(row[3] for row in record_rows if row[0] not in replacements)
    selected+=b''.join(replacements[number] for number in sorted(replacements))
    record_chunk=_encode(dict(records,repeated=False),('protobuf',selected))
    updated=b''.join(record_chunk if index==matched else row[3] for index,row in enumerate(tracker_rows))
    if matched is None:
        if record_count>=7:raise ValueError('No room for the detached exact appearance record.')
        updated+=record_chunk
    result=replace(root_rows,attributes,replace(attribute_rows,tracker,updated))
    _chunks(result)
    return dict(native_hex=result.hex(),sha256=hashlib.sha256(result).hexdigest(),native_bytes=len(result),
                native_message_type=capture['native_message_type'])
