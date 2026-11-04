"""Carry native pelt/texture values absent from EA's occult save schema.

One inert, checksummed proto2 unknown field travels with the existing native
occult record. No external bank, executable payload, new Sim or trait is used.
An occupied native/foreign field number refuses replacement. All other wire
fields, including unknown groups and future fields, remain byte-for-byte.
"""
import copy
import hashlib
import json
from . import form_appearance as appearance, outfit_snapshot as wire

FIELD = 500001777
MAGIC = b'TD1_APEX_OCCULT_APPEARANCE_V1\x00'
MAX_BYTES = 12 * 1024 * 1024
EXTRA_FIELDS = {'pelt_layers', 'custom_texture'}


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode('ascii')


def _varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128); value >>= 7
    result.append(value)
    return bytes(result)


def _parts(record):
    if FIELD in record.DESCRIPTOR.fields_by_number:
        raise ValueError('Native schema occupies the Apex appearance field; no extension replaced.')
    raw = record.SerializeToString()
    if len(raw) > MAX_BYTES:
        raise ValueError('Native occult record exceeds its extension bound.')
    offset, remaining, carried = 0, [], []
    while offset < len(raw):
        start = offset
        number, kind, offset, value = wire.field(raw, offset)
        if number == FIELD:
            if kind != 2 or not value.startswith(MAGIC):
                raise ValueError('Foreign data occupies the Apex appearance field; originals retained.')
            carried.append(value)
        else:
            remaining.append(raw[start:offset])
    if len(carried) > 1:
        raise ValueError('Duplicate Apex appearance extensions; no ambiguous authority accepted.')
    return b''.join(remaining), carried


def _unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate appearance extension key.')
        result[key] = value
    return result


def read(record):
    _, carried = _parts(record)
    if not carried:
        return {}
    row = json.loads(carried[0][len(MAGIC):].decode('ascii'), object_pairs_hook=_unique,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite extension.')))
    if (not isinstance(row, dict) or set(row) != {'schema', 'occult_type', 'fields', 'sha256'} or
            type(row['schema']) is not int or row['schema'] != 1 or
            type(row['occult_type']) is not int or row['occult_type'] != int(record.occult_type) or
            not isinstance(row['fields'], dict) or not row['fields'] or
            set(row['fields']) - EXTRA_FIELDS or
            any(name in record.DESCRIPTOR.fields_by_name for name in row['fields']) or
            hashlib.sha256(_encode({key: row[key] for key in ('schema', 'occult_type', 'fields')})).hexdigest() != row['sha256']):
        raise ValueError('Apex appearance extension identity/schema/checksum differs.')
    for name, value in row['fields'].items():
        decoded = appearance.decode(value)
        if name == 'pelt_layers' and decoded is not None and not isinstance(decoded, bytes):
            raise ValueError('Native pelt extension requires complete bytes or returned null.')
        if name == 'custom_texture' and decoded is not None and (type(decoded) is not int or not 0 <= decoded < 1 << 64):
            raise ValueError('Native texture extension requires uint64 or returned null.')
    return copy.deepcopy(row['fields'])


def write(record, fields):
    extra = {name: copy.deepcopy(row) for name, row in fields.items()
             if name in EXTRA_FIELDS and name not in record.DESCRIPTOR.fields_by_name}
    if not extra:
        return
    retained, _ = _parts(record)
    read(record)  # A damaged existing frame never authorizes replacement.
    body = {'schema': 1, 'occult_type': int(record.occult_type), 'fields': extra}
    frame = MAGIC + _encode(dict(body, sha256=hashlib.sha256(_encode(body)).hexdigest()))
    raw = retained + _varint((FIELD << 3) | 2) + _varint(len(frame)) + frame
    if len(raw) > MAX_BYTES:
        raise ValueError('Complete appearance extension exceeds its bound; no native write.')
    candidate = type(record)()
    candidate.ParseFromString(raw)
    if read(candidate) != extra or _parts(candidate)[0] != retained:
        raise ValueError('Native protobuf did not preserve its extension and all unrelated wire fields.')
    record.CopyFrom(candidate)
    if read(record) != extra or _parts(record)[0] != retained:
        raise ValueError('Native extension copy did not retain its complete readback.')
